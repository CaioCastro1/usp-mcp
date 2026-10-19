# Acervo de questões, V0 — design

> 19/10/2026. Sai de uma conversa de 14 a 19/10 entre o dono e o Claude, sem
> código. Ainda não há dado de uso: a V0 existe para medir se alunos usam um banco
> de questões pela IA, e se o formato serve ao agente.

## O problema

Cada aluno pede ao assistente para transcrever e resolver as mesmas provas
antigas, e o trabalho fica preso na conversa de quem fez. O Polishare compartilha
PDFs entre pessoas, mas PDF obriga a IA de cada aluno a refazer tudo do zero.

A proposta é um acervo de **questões estruturadas**, e não de arquivos. Quem
transcreve devolve a questão ao acervo, e quem vem depois consulta. Em escala,
isso vira crowdsourcing: cada aluno transcreve com os créditos de IA que já
gastaria estudando. Na V0, a semente é feita pelo dono e pelo Gunthen.

## Escopo da V0

**Entra:**

1. Dois contratos de dados versionados: `acervo.temas/v1` e `acervo.documento/v1`.
2. Um validador determinístico, rodando no CI do repositório do acervo.
3. A semente: as quatro disciplinas abaixo, com provas e listas que o dono cursou,
   baixadas pelo usp-mcp.
4. O sync do git para um Postgres no Supabase, a cada merge na `main`.
5. Um site que lê o Supabase, com login Google restrito a `@usp.br`, para quem
   não usa IA.
6. Um export de um arquivo por tema para uma pasta do Drive. É a única peça
   **provisória**: serve para os colegas testarem pela IA enquanto o conector não
   existe.

As peças 1, 2, 4 e 5 já são as da arquitetura final (próxima seção). A V0 adia
só o que é caro e incerto.

**Não entra (V1 ou depois):** o conector MCP remoto com login, o envio por
terceiros via bot, as funções "análogas ao GitHub" (status do envio, propor
correção, histórico), a ferramenta `questoes` no usp-mcp, a conferência de
gabarito por LLM e o apelido público de crédito.

| Disciplina | Sigla | Origem da sigla |
|---|---|---|
| Cálculo Diferencial e Integral II | MAT2454 | Moodle do dono (MAT2454-2024) e Jupiter |
| Física II | 4323102 | Moodle do dono (4323102-2025) e Jupiter |
| Cálculo Diferencial e Integral IV | MAT2456 | Moodle do dono (MAT2456-2025) e Jupiter |
| Física IV | 4323204 | Moodle do dono (4323204-203-2025) e Jupiter |

## Arquitetura final

```
ESCRITA                                       LEITURA

mantenedores ──── PR ─────┐                   ┌── conector MCP remoto ── Claude, Gemini, celular (V1)
                          ▼                   │
aluno via conector ─▶ bot abre PR ─▶ git ──CI (validar.py)──merge──CD (sincronizar.py)──▶ Supabase Postgres
        (V1)                                  ├── site, login Google @usp.br (V0)
                                              ├── export por tema no Drive (V0, provisório)
                                              └── usp-mcp local, ferramenta `questoes` (V1)
```

Princípios:

- **O git é a fonte da verdade; o banco é cópia de leitura.** O CI valida, e o
  CD reescreve o banco a cada merge. O banco é descartável: se corromper, ou se o
  schema mudar, ele é reconstruído do git.
- **Toda escrita passa pelo git, e ninguém precisa usar o GitHub.** Na V0 só os
  mantenedores escrevem, por PR direto. Na V1 o aluno diz ao assistente "envia
  essa questão", o conector chama uma função de envio, e um bot (uma GitHub App)
  faz o commit num branch e abre o PR. O merge é automático quando o CI passa, e
  o aluno recebe pelo assistente "publicada como …" ou "recusada: regra V11, NUSP
  no enunciado".
- **Um validador só**, o mesmo script, para PR de mantenedor e envio pelo bot.
- **O git dá de graça** histórico, revisão e retirada: a resposta a
  envenenamento é reverter todos os commits de um envio.
- **Toda leitura passa pelo Supabase.** Conector, site e ferramenta local
  consultam o mesmo banco, e o login `@usp.br` e as regras de acesso (RLS) ficam
  num lugar só.

### Análogo ao GitHub, sem o GitHub na frente (direção da V1)

Como o git está embaixo, as ideias do GitHub viram funções do produto, pelo
conector ou pelo site:

| No GitHub | No acervo |
|---|---|
| Pull request | **Envio**, com status (validando, publicada, recusada) e o motivo |
| PR que muda um arquivo existente | **Propor correção** numa questão: gabarito, tema, LaTeX |
| `git log` de um arquivo | **Histórico da questão**: quem mudou o gabarito de inferido para oficial, e quando |
| Revert | **Retirada** de todos os envios de uma conta |
| Página de contribuidor | **Apelido público opcional** |

"Propor correção" é a mais valiosa: é o que deixa o acervo melhorar com o uso sem
curadoria humana.

Os contratos não dependem do GitHub. Se o volume de envios um dia tornar o fluxo
de PR lento demais, a fonte da verdade pode virar o banco (uma tabela de versões
por questão), com o git como backup. O usuário não percebe a troca. Isso só se
decide com medida.

## Onde mora

Num **repositório próprio e privado** (`acervo`), separado do usp-mcp, que é
público. O repositório guarda os JSON, o validador, o sync e o gerador do export.

```
acervo/
  schemas/                       JSON Schema dos dois contratos
  usp/
    MAT2454/
      temas.json
      2024-2-P1.json             um arquivo por documento de origem
      2024-2-Lista3.json
      avulsa-3f9a2c1e.json
  scripts/
    validar.py                   o CI inteiro
    sincronizar.py               CD: reescreve o Postgres a partir dos JSON
    exportar.py                  um arquivo por tema para o Drive (provisório)
  supabase/                      schema das tabelas e regras de acesso
  site/                          o site, que lê o Supabase
  .github/workflows/
    validar.yml                  em todo PR
    publicar.yml                 no push para a main: sincronizar e exportar
```

Nome de arquivo: `{ano}-{semestre}-{tipo}{rotulo}[-{variante}].json`, e `avulsa-{hash8}.json`
para avulsa (o hash da primeira questão). O validador confere que o nome bate com o conteúdo.

## Contrato 1: `acervo.temas/v1`

Um por disciplina. É a lista fechada de temas que as questões podem declarar.

```jsonc
{
  "schema": "acervo.temas/v1",
  "instituicao": "usp",
  "sigla": "MAT2454",
  "nome": "Cálculo Diferencial e Integral II",
  "versao": 1,
  "derivado_de": "JupiterWeb, programa consultado em 2026-10-19",
  "blocos": [
    { "id": "b1", "nome": "Funções de várias variáveis e diferenciabilidade" },
    { "id": "b2", "nome": "Taylor e otimização" }
  ],
  "temas": [
    { "id": "regra-da-cadeia", "nome": "Regra da cadeia", "bloco": "b1" },
    { "id": "multiplicadores-de-lagrange", "nome": "Multiplicadores de Lagrange", "bloco": "b2" }
  ]
}
```

- **Blocos são obrigatórios**, com pelo menos um. Em Física IV o programa do
  Jupiter já vem em três blocos numerados; nas outras, quem semeia propõe os
  blocos.
- **`id` de tema** é kebab-case, sem acento, e único na disciplina.
- **`fora-do-programa` é um id reservado**, implícito em toda disciplina e sem
  bloco. Existe porque professor cobra o que não está no programa.
- **A lista só cresce de propósito:** um tema novo entra por mudança no
  `temas.json`, que sobe `versao`. Remover ou renomear um tema em uso faz o CI
  falhar.
- **De onde vem:** um rascunho sai do programa do Jupiter (ferramenta
  `disciplina`, `secoes=["programa"]`), e a revisão é humana. O programa não é
  limpo o bastante para virar a lista sozinho. Os rascunhos estão no Apêndice A.

## Contrato 2: `acervo.documento/v1`

Um arquivo por documento de origem: uma prova, uma lista ou uma questão avulsa.

```jsonc
{
  "schema": "acervo.documento/v1",
  "instituicao": "usp",
  "sigla": "MAT2454",
  "tipo": "P1",                    // P1 | P2 | P3 | PSub | PRec | Lista | Avulsa
  "rotulo": null,                  // número da lista ("3"); null nas provas
  "variante": null,                // turma ou versão, quando a mesma prova tem mais de uma
  "ano": 2024,                     // obrigatório, exceto em Avulsa
  "semestre": 2,                   // 1 | 2; obrigatório, exceto em Avulsa
  "completa": true,                // false quando só parte das questões foi transcrita
  "fonte": {
    "origem": "moodle",            // moodle | polishare | outro | sem_fonte
    "ref": "edisciplinas.usp.br/mod/resource/view.php?id=123456",
    "arquivo": "P1_2024.pdf",
    "sha256": "…",
    "obtida_em": "2026-10-20"
  },
  "envio": null,                   // V1: UUID aleatório do envio; na V0, o git é o registro
  "observacoes": null,             // errata ou ressalva da prova inteira, texto livre
  "questoes": [
    {
      "id": "usp-MAT2454-2024-2-P1-1a",
      "numero": "1a",
      "contexto": "Enunciado-pai do grupo 1, repetido em cada item.",
      "enunciado": "Markdown + LaTeX.",
      "alternativas": {},
      "temas": ["regra-da-cadeia"],
      "resposta": {
        "tipo": "expressao",       // numero | expressao | alternativa | multipla | qualitativa | desenho
        "valor": "…",
        "unidade": null,
        "tolerancia": null         // fração relativa, só em `numero`
      },
      "gabarito": "oficial",       // oficial | manual | conferido | inferido
      "resolucao": "Passo a passo em Markdown + LaTeX, terminando em \\boxed{…}.",
      "figura": null,              // ou { "descricao": "…", "arquivo": "figuras/…" }
      "observacoes": null          // errata desta questão, ex.: "o gabarito aceita as duas respostas"
    }
  ]
}
```

Decisões, com a razão de cada uma:

- **A unidade é o sub-item** (1a, 1b), com o `contexto` do grupo repetido. Isso
  duplica texto, mas cada registro fica autossuficiente para o agente, que pode
  receber só uma questão.
- **`temas` tem de 1 a 3 itens, e o primeiro é o principal.** Cada um está no
  `temas.json` da sigla, ou é `fora-do-programa`.
- **Não há campo de dificuldade.** É subjetivo, e dois contribuidores não
  preencheriam igual.
- **`gabarito` diz de onde veio a resposta:** `oficial` (do professor), `manual`
  (um humano conferiu), `conferido` (duas resoluções independentes concordaram,
  o que só vale na V1) e `inferido` (só um modelo calculou). O rótulo fica
  visível para quem estuda; o sistema classifica a confiança em vez de prometer
  correção.
- **`fonte` diz de onde veio o enunciado.** O `ref` não precisa abrir para quem
  lê: quem tem acesso confere, e o `sha256` permite que outro aluno confirme sem
  compartilhar o arquivo. `sem_fonte` entra com rótulo (prova em papel é o caso
  mais valioso). **O PDF não é guardado**: é onde moram nome, NUSP e o problema
  de direito autoral.
- **`completa: false`** existe pelo Invariante 7: uma prova com uma questão
  transcrita não pode parecer uma prova de uma questão.
- **A autoria fica fora do conteúdo.** O que circula não leva e-mail. Na V0 os
  únicos autores são os mantenedores, e o histórico do git basta. Na V1 o commit
  é do bot, nunca da pessoa: no lugar do e-mail, ele leva o UUID do envio num
  trailer (`Envio: e_7f3a…`), e o mesmo UUID vai no campo `envio`. A ligação
  entre envio e conta fica numa tabela `envios` no Supabase, legível só pelos
  mantenedores. Assim nem quem lê o repositório sabe de quem é cada questão. O
  UUID é aleatório, nunca um hash do e-mail: com a lista de e-mails `@usp.br`, o
  hash se desfaz por força bruta. É essa tabela que permite retirar e bloquear
  todos os envios de quem envenenar o acervo.

### IDs

- Prova ou lista: `{instituicao}-{sigla}-{ano}-{semestre}-{tipo}{rotulo}[-{variante}]-{numero}`.
  Exemplos: `usp-MAT2454-2024-2-P1-1a` e `usp-MAT2456-2025-2-Lista3-2`.
- Avulsa: `{instituicao}-{sigla}-avulsa-{hash8}-{numero}`, em que `hash8` são os
  8 primeiros hex do sha256 do enunciado normalizado (minúsculas, espaços
  colapsados).
- O ID é derivado, nunca escolhido, e o CI recusa um ID que não bate com os
  campos. Por isso uma questão avulsa de uma prova e a mesma questão transcrita
  dentro da prova, mais tarde, casam pelo ID e não duplicam. O hash só pega
  duplicata exata; detectar "parecida" fica para a V1.

## O validador (`scripts/validar.py`)

Python, rodado com `uv run`. Todas as regras são determinísticas e não fazem
chamada de rede nem de modelo, então o custo é zero. Ele falha o CI com uma
mensagem que diz arquivo, questão e regra.

| # | Regra |
|---|---|
| V1 | O arquivo valida contra o JSON Schema do `schema` declarado, e esse schema é conhecido |
| V2 | Enums válidos: `tipo`, `origem`, `gabarito`, `resposta.tipo` |
| V3 | `ano` e `semestre` presentes, exceto em `Avulsa`; `rotulo` presente só em `Lista` |
| V4 | O nome do arquivo bate com `ano`, `semestre`, `tipo` e `rotulo` |
| V5 | O `id` de cada questão é o derivado, e é único no acervo inteiro |
| V6 | Cada tema está no `temas.json` da sigla, ou é `fora-do-programa`; de 1 a 3 temas |
| V7 | Com `--base`, comparando com a base do PR: nenhum tema sumiu do `temas.json`, e toda mudança nele subiu a `versao`. Sem a base, um tema em uso que sumiu já reprova na V6 |
| V8 | A `resolucao` destaca a resposta num `\boxed{…}` não vazio quando `resposta.tipo` é `numero` ou `expressao`; comentário depois dele é permitido |
| V9 | Delimitadores de LaTeX balanceados (`$`, `$$`, chaves) em enunciado, contexto e resolução |
| V10 | `fonte.ref` nunca contém `token=` nem `pluginfile.php` (Invariante 3: a URL de arquivo do web service carrega o token) |
| V11 | Regex de dado pessoal nos campos de texto: NUSP (7 a 8 dígitos isolados), e-mail, CPF e telefone |
| V12 | Padrões óbvios de injeção nos campos de texto ("ignore as instruções", menção a ferramentas como `enviar_entrega`) |
| V13 | `sha256` com 64 hex quando `origem` é diferente de `sem_fonte` |

V9 é a parte fraca: balancear não é compilar. Parsear com KaTeX pegaria comando
inexistente, mas traz uma dependência em Node. Fica para quando um LaTeX quebrado
aparecer no site.

V11 e V12 pegam o óbvio, não o esperto. A defesa real contra envenenamento
continua no usp-mcp: conteúdo do acervo é dado e nunca instrução, e a entrega no
Moodle fica desligada por padrão e pede confirmação por chamada
(`2026-09-15-entrega-com-confirmacao-design.md`). Essa proteção passa a defender
também contra o acervo, e não pode ser afrouxada sem pensar nele.

## O banco (`scripts/sincronizar.py`)

Roda no `publicar.yml`, a cada push na `main`, depois do validador. Lê todos os
JSON e reescreve as tabelas numa transação só. Com alguns milhares de questões,
reescrever tudo leva segundos e não guarda estado que possa divergir do git;
sync incremental só se a medida pedir. A chave de serviço do Supabase fica como
segredo do GitHub, e só o CD a usa.

Tabelas:

- `disciplinas` e `temas`: o conteúdo dos `temas.json`.
- `documentos`: um por arquivo, com `tipo`, `ano`, `semestre`, `completa` e
  `fonte`.
- `questoes`: uma por sub-item. Colunas indexadas para filtrar (`sigla`, `tipo`,
  `ano`, `gabarito`, `temas text[]` com índice GIN), o JSON inteiro em `dados
  jsonb`, e um `tsvector` em português sobre enunciado e contexto para busca por
  texto.
- `envios` (V1): envio e conta, legível só pelos mantenedores.

A consulta típica é SQL comum:

```sql
select dados from questoes
where sigla = 'MAT2454' and 'regra-da-cadeia' = any(temas) and gabarito = 'oficial';
```

**Acesso:** Supabase Auth com o provedor Google. Só entra conta `@usp.br`, e
isso é conferido no servidor, pelo domínio do e-mail verificado; o parâmetro
`hd` sozinho é burlável. Uma regra de RLS dá leitura a qualquer usuário
autenticado e escrita a ninguém: escrever é privilégio do CD.

## As saídas de leitura

- **O site** lê o Supabase com o login acima: uma página por disciplina, por
  tema e por documento, LaTeX renderizado no navegador, e uma lista de questões
  de um tema para imprimir. É para quem não usa IA. Hospedagem estática
  (Cloudflare Pages, GitHub Pages ou Vercel); o login é do Supabase, e por isso
  não precisa de Cloudflare Access.
- **O export por tema** (`scripts/exportar.py`, provisório): `{sigla}/{tema}.md`
  com todas as questões daquele tema, mais um `{sigla}/indice.md`, numa pasta do
  Drive compartilhada com `@usp.br`. Ele existe porque, no Claude e no Gemini
  web, o agente só lê uma fonte restrita por um conector, e o do Drive já existe.
  A agregação vem pronta, então o agente abre um arquivo por pergunta. Um tema
  com ~15 questões de ~5 KB dá ~20 mil tokens. Sai quando o conector remoto
  entrar.

## O que medir

| # | Medida | O que decide |
|---|---|---|
| M1 | O Gemini e o Claude leem `.md` cru de uma pasta do Drive compartilhada com o usuário? | Se o export por tema sai como `.md` ou precisa virar Google Doc |
| M2 | O Supabase Auth aceita restringir o login Google a `@usp.br` no servidor (hook de autenticação ou checagem na RLS)? | Como o site e, depois, o conector restringem o acesso |
| M3 | Quanto tempo leva transcrever uma prova inteira com o assistente? | A premissa do impacto (~15 min) |

## Ordem de construção

1. Os JSON Schema e o `validar.py`, com fixtures de documentos ruins, uma por
   regra, para provar que cada regra reprova.
2. Os quatro `temas.json`, a partir dos rascunhos do Apêndice A.
3. Uma prova transcrita de ponta a ponta, para achar onde o contrato está errado
   antes de transcrever o resto.
4. O projeto no Supabase, o schema das tabelas e o `sincronizar.py`. M2.
5. O resto da semente: umas 3 a 5 provas por disciplina, espalhadas nos anos.
6. O site.
7. M1, e depois o `exportar.py`.
8. O teste com colegas numa prova real deste semestre.

## Depois da V0

Se a V0 mostrar uso: o conector MCP remoto lendo o mesmo Supabase (o que também
leva o acervo ao celular), o envio pelo bot, as funções da tabela "análogo ao
GitHub" e a ferramenta `questoes` no usp-mcp. Cai o export para o Drive.

## Como saber se a V0 deu certo

- **Reuso:** consultas por questão. Cada consulta depois da primeira é uma
  transcrição evitada. É a métrica central.
- Quantos colegas usaram, e quantas vezes.
- Uma pergunta no fim: "ajudou a estudar para a prova?".

## O que o primeiro teste mudou (19/10/2026)

O banco antigo de Física IV (P1 2022–2025 e P2 2019, 2022–2025, 102 questões, todas
com gabarito oficial) foi convertido para o contrato e validado. Três mudanças
saíram dele:

- **`observacoes`, na prova e na questão.** Os gabaritos têm errata que importa a
  quem estuda (o formulário da P2 2022 trazia ℏ errado, e as duas respostas
  valeram). Sem campo, ela sumia. O texto passa pelas mesmas V9, V11 e V12.
- **`numero` aceita romano** (`2-I`, `3-II-b`), porque é como as provas numeram.
- **V8 deixou de exigir que o `\boxed` feche a resolução.** Seis gabaritos oficiais
  fecham com um comentário depois da resposta.

E uma mudança de método: em Física IV, os blocos do programa do Jupiter não batiam
com as provas (Compton e Bohr caem na P2, não no último bloco). **Os blocos seguem
o que cai em P1, P2 e P3; o programa só ajuda a nomear os temas.**

## O que fica em aberto

- Os termos do Polishare permitem republicar questões transcritas de lá?
- A posição de direito autoral do projeto.
- A conferência de gabarito por LLM: crowdsourcing (o assistente de quem consulta
  resolve e devolve "bateu") ou paga pelo projeto.
- Se o app do Gemini aceita conector MCP próprio (V1).
- Se o Moodle expõe identificador estável do arquivo além do `cmid`.
- Termo de uso e LGPD, antes de entrar gente de fora.
- Quando, e se, a fonte da verdade sai do git para o banco.

## Apêndice A: rascunho dos temas (a revisar)

Saídos do programa do Jupiter em 19/10/2026. Os blocos são proposta, exceto em
Física IV, onde vêm do próprio programa.

**MAT2454, Cálculo II**
- b1, Funções de várias variáveis e diferenciabilidade: `limites-e-continuidade`,
  `diferenciabilidade`, `gradiente`, `regra-da-cadeia`, `teorema-do-valor-medio`
- b2, Taylor e otimização: `derivadas-de-ordem-superior` (inclui Schwarz),
  `formula-de-taylor`, `maximos-e-minimos`, `multiplicadores-de-lagrange`

**4323102, Física II**
- b1, Oscilações: `movimento-harmonico-simples`, `pendulos` (simples e físico),
  `oscilacoes-amortecidas`, `oscilacoes-forcadas-e-ressonancia`
- b2, Ondas: `equacao-de-onda` (inclui cordas vibrantes), `reflexao-de-ondas`,
  `superposicao-e-interferencia`, `batimentos`, `modos-normais`,
  `ondas-sonoras`, `efeito-doppler`

**MAT2456, Cálculo IV**
- b1, Séries: `integrais-improprias`, `sequencias-e-series-numericas`,
  `criterios-de-convergencia`, `convergencia-absoluta-e-condicional`,
  `series-de-potencias` (inclui raio e termo a termo), `serie-de-taylor`
- b2, Fourier: `series-de-fourier`, `convergencia-pontual`, `bessel-e-parseval`
- b3, Equações diferenciais: `edo-primeira-e-segunda-ordem`,
  `edo-linear-coeficientes-constantes`,
  `variacao-de-parametros-e-coeficientes-a-determinar`, `edo-por-series`

**4323204, Física IV** (blocos do próprio programa)
- b1: `interferencia`, `principio-de-huygens`, `difracao`,
  `cinematica-relativistica`
- b2: `dinamica-relativistica`, `fotons-e-corpo-negro`, `efeito-fotoeletrico`,
  `natureza-ondulatoria-das-particulas`
- b3: `espalhamento-compton`, `modelo-de-bohr`, `de-broglie`,
  `principio-da-incerteza`, `equacao-de-schrodinger`,
  `poco-de-potencial-e-tunelamento`, `atomo-de-hidrogenio`,
  `exclusao-e-estrutura-atomica`
