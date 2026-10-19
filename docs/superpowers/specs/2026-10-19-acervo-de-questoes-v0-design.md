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
4. Duas saídas geradas a partir dos JSON: um site estático restrito, para quem
   não usa IA, e um arquivo por tema, para os agentes lerem.

**Não entra (V1 ou depois):** upload por terceiros, Supabase, conector MCP
remoto com login, a ferramenta `questoes` no usp-mcp, conferência de gabarito
por LLM, apelido público de crédito.

| Disciplina | Sigla | Origem da sigla |
|---|---|---|
| Cálculo Diferencial e Integral II | MAT2454 | Moodle do dono (MAT2454-2024) e Jupiter |
| Física II | 4323102 | Moodle do dono (4323102-2025) e Jupiter |
| Cálculo Diferencial e Integral IV | MAT2456 | Moodle do dono (MAT2456-2025) e Jupiter |
| Física IV | 4323204 | Moodle do dono (4323204-203-2025) e Jupiter |

## Onde mora

Num **repositório próprio e privado** (`acervo`), separado do usp-mcp, que é
público. O repositório guarda JSON, o validador e o gerador das saídas. O git é
a fonte da verdade: o Drive, o site e, na V1, o Supabase são saídas geradas, e
trocar de saída não muda os dados.

```
acervo/
  schemas/                       JSON Schema dos dois contratos
  usp/
    MAT2454/
      temas.json
      2024-2-P1.json             um arquivo por documento de origem
      2024-2-L3.json
      avulsa-3f9a2c1e.json
  scripts/
    validar.py                   o CI inteiro
    gerar.py                     site e um arquivo por tema
  .github/workflows/validar.yml
```

Nome de arquivo: `{ano}-{semestre}-{tipo}{rotulo}.json`, e `avulsa-{hash8}.json`
para avulsa. O validador confere que o nome bate com o conteúdo.

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
      "figura": null               // ou { "descricao": "…", "arquivo": "figuras/…" }
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
- **A autoria fica fora do conteúdo.** O que circula não leva e-mail. Na V0 o
  registro é o histórico do git; na V1, `envio` vira um UUID aleatório que aponta
  para uma tabela visível só para os mantenedores. Nunca um hash do e-mail: com a
  lista de e-mails `@usp.br`, ele se desfaz por força bruta. É isso que permite
  retirar e bloquear todos os envios de quem envenenar o acervo.

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
| V7 | Nenhum tema em uso sumiu do `temas.json` |
| V8 | A `resolucao` termina em `\boxed{…}` quando `resposta.tipo` é `numero` ou `expressao` |
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

## As saídas (`scripts/gerar.py`)

As duas são geradas no CI depois do validador, e nenhuma é editada à mão.

- **Um arquivo por tema**, `{sigla}/{tema}.md`, com todas as questões daquele
  tema (enunciado, gabarito, resolução e rótulos), mais um `{sigla}/indice.md`.
  Isso responde à crítica de que o Drive agrega mal: a agregação vem pronta, e o
  agente abre um arquivo por pergunta. Um tema com ~15 questões de ~5 KB dá
  ~20 mil tokens.
- **Um site estático**, com uma página por disciplina, por tema e por documento,
  e LaTeX renderizado no navegador. É para quem não usa IA: navegar e imprimir
  uma lista de questões de um tema. Hospedado no Cloudflare Pages, com o
  Cloudflare Access na frente restringindo a `@usp.br`.

## O que medir antes de construir as saídas

| # | Medida | O que decide |
|---|---|---|
| M1 | O Gemini e o Claude leem `.md` cru de uma pasta do Drive compartilhada com o usuário? | Se o export por tema sai como `.md` ou precisa virar Google Doc |
| M2 | O Cloudflare Access aceita login Google restrito a `@usp.br` no plano gratuito, e com quantos usuários? | Se o site restrito fica de graça na V0 |
| M3 | Quanto tempo leva transcrever uma prova inteira com o assistente? | A premissa do impacto (~15 min) |

## Ordem de construção

1. Os JSON Schema e o `validar.py`, com fixtures de documentos ruins, uma por
   regra, para provar que cada regra reprova.
2. Os quatro `temas.json`, a partir dos rascunhos do Apêndice A.
3. Uma prova transcrita de ponta a ponta, para achar onde o contrato está errado
   antes de transcrever o resto.
4. O resto da semente: umas 3 a 5 provas por disciplina, espalhadas nos anos.
5. M1 e M2, e depois o `gerar.py`.
6. O teste com colegas numa prova real deste semestre.

## Como saber se a V0 deu certo

- **Reuso:** consultas por questão. Cada consulta depois da primeira é uma
  transcrição evitada. É a métrica central.
- Quantos colegas usaram, e quantas vezes.
- Uma pergunta no fim: "ajudou a estudar para a prova?".

## O que fica em aberto

- Os termos do Polishare permitem republicar questões transcritas de lá?
- A posição de direito autoral do projeto.
- A conferência de gabarito por LLM: crowdsourcing (o assistente de quem consulta
  resolve e devolve "bateu") ou paga pelo projeto.
- Se o app do Gemini aceita conector MCP próprio (V1).
- Se o Moodle expõe identificador estável do arquivo além do `cmid`.
- Termo de uso e LGPD, antes de entrar gente de fora.

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
