# Os módulos da Poli, pelo nome que o aluno usa — design

> 26/10/2026. A fatia `curso` foi fechada em 14/09 como "não será construída":
> a medição daquele dia concluiu que a superfície pública do JupiterWeb para no
> 5º semestre e que ênfase e módulo não têm grade alcançável. A conclusão estava
> errada por um parâmetro — `tipo=N` onde o currículo pedia `tipo=V` — e este
> desenho parte da correção. A pergunta que o justifica veio do dono, num
> projeto de uso: *"quais módulos estão disponíveis e qual tem menor carga?"* e
> *"existe algum módulo que tem PM3508?"*.

## O que foi medido, antes de qualquer desenho

Medição de 22 a 26/10/2026, dado público, sem credencial. Os crus ficaram no
scratchpad da sessão; os que a implementação precisar viram fixture versionada
(dado público, como o resto de `fixtures/jupiter/`).

### 1. A grade dos currículos "anteriores" responde com `tipo=V`

`pubGradeCurricular` sempre foi chamada com `tipo:"N"`, porque é o que o
`jupCarreira.js` usa. Para os códigos que só aparecem na lista de currículos
anteriores, `N` devolve **vazio** — e foi isso que 14/09 leu como "não existe".

| `codcur/codhab` | o quê | `tipo=N` | `tipo=V` |
|---|---|---|---|
| 3032/0 | Ciclo Básico Elétrica | 0 | 90 registros, 1º–6º |
| 3032/3180 | Ênfase Eletrônica e Sistemas | — | 39 registros, até o 10º |
| 3032/5080 | Módulo Sistemas Eletrônicos Avançados | 0 | **31 registros, 9º–10º** |

As seis disciplinas que a página do PSI lista como pré-aprovadas para o módulo
(PTC3415, PTC3405, PTC3451, PTC3444, PTC3429, PSI3483) estão entre as 31.

### 2. A lista de módulos só existe em HTML

`jupCursoLista?codcg=3&tipo=V` ("Cursos e Habilitações Anteriores", 125 kB)
lista 102 grades da Poli com o par `codcur/codhab` de cada uma, **todos os 47
módulos** incluídos. `jupCursoLista?codcg=3&tipo=N` (46 kB) lista os cursos de
ingresso e, numa seção "Módulo" à parte, os 3 Percursos Formativos de IA
(`codhab=6000`; até 22/10 chamados "Trilha Formativa" — o nome mudou entre duas
medições, e o link deles passou de `tipo=N` para `tipo=V`). Cada linha traz o
link duas vezes: um comentado em `<!-- -->`, com o `tipo` antigo, e o ativo. Só
o ativo vale. `pubListarCursoEntrada`, o único caminho DWR de descoberta, só
mostra ingresso. Nenhuma consulta DWR que liste os anteriores foi achada.

### 3. Só a Poli tem módulos

Varredura das 47 unidades em 26/10 (`jupCursoLista`, `tipo=N` e `tipo=V`, 930
grades no total): os 47 nomes com "Módulo" são todos da unidade 3. IME e FFLCH,
olhados de perto, têm habilitações de grade completa (BCC: 222 registros, 1º–8º)
e nenhuma camada.

### 4. A ficha do currículo funciona, e traz a carga

`pubObterInfoCursoWeb {codcur, codhab, tipo}` — lida no JS em 31/08 e nunca
chamada — devolve ~900 B: `cgahortot` (carga exigida), `cgahorobgaul` +
`cgahorobgtrb` (obrigatória), `cgaoptcplaul` (eletiva), `cgaoptlreaul` (livre),
`duridlcur`, `dtainicrl` e a regra em HTML (`obscrl`). Cargas medidas: 270 h
(Petróleo) a 750 h (Pesquisa em Produção, pré-mestrado); 33 dos 47 módulos
exigem 360 h.

O §9 de 14/09 diz que "nenhum payload do Jupiter tem campo de vigência". Este
tem `dtainicrl` — mas `15/07/2026` para o 3032, que é currículo "anterior": é a
data da **revisão** do currículo, não do início do curso. Não serve para
descartar geração antiga, e este desenho não a usa para isso.

### 5. Um terceiro `tipobg`: `C`

Até aqui só `O` (obrigatória) e `L` (optativa livre) estavam registrados. O
módulo 5080 é **todo** `C` (optativa eletiva). Código que trate só `O`/`L` perde
o módulo inteiro.

### 6. O dado tem quatro defeitos, e a saída precisa dizê-los

| defeito | onde |
|---|---|
| grade vazia, carga presente | 3052/5000 Lavra de Minas, 3052/5010 Tratamento de Minérios, 3022/5010 Real Estate, 3022/5000 Tec. e Gestão da Produção na Construção |
| grade **e** carga não publicadas | os 3 Percursos de IA: com o `tipo=V` do link, grade vazia e ficha toda `None` (27/10). Com `tipo=N` a grade vem cheia, mas é a do curso-base: o currículo novo ignora `codhab` (3033/0, /3150, /3180, /6000 devolvem os mesmos 89 registros). A ferramenta segue o link e **não** tenta o outro `tipo` |
| o mesmo nome em duas gerações | "Tecnologia e Gestão em Eng. de Computação" em 3032/5060 e 3122/5000 |

### 7. O currículo novo cresce com a turma

`pubGradeCurricular {3033, 0, N}`: 67 registros (1º–5º) em 14/09, 89 (1º–6º) em
22/10. Não afeta os módulos — que estão no 3032 e afins —, mas proíbe cache sem
validade.

### 8. Custo: o cru e o que a pergunta precisa

Medido com `tiktoken` (`o200k_base`) efêmero, como em `notas/custo-em-token.md`:

| | bytes | tokens |
|---|---:|---:|
| cru: ficha + grade dos 50 | 259.369 | **103.755** |
| "onde está PMR3508" | 113 | **35** |
| os 50 por carga | 3.701 | **1.411** |
| cru: grade de 1 módulo (5080) | 8.046 | 3.330 |
| a mesma, 5 dos 17 campos | 1.517 | **534** |

### 9. Linguagem natural casa no servidor

Normalizar (sem acento, sem caixa), tirar palavra vazia e exigir que toda
palavra da busca seja prefixo de alguma palavra do alvo acertou, sobre o dado
real: "sistemas eletrônicos" → 3 módulos; "telecom" → 3; "biomédica" → 1;
"aprendizado de máquina" → 4 disciplinas com seus módulos; "PM3508" → "não
existe; parecida: PMR3508". Errou **"pré-mestrado elétrica" → 0**, porque o nome
do módulo não diz o curso: o registro traz "Engenharia", e "Elétrica" só está no
nome do curso-base do mesmo `codcur` (3032/0, "Ciclo Básico - Engenharia
Elétrica").

## As perguntas que a ferramenta responde

Critério do §5 do `SPEC1.md`: pergunta real, feita pelo dono.

1. **"Quais módulos existem e qual tem menor carga?"**
2. **"Existe algum módulo que tem PMR3508?"** — e a mesma pergunta pelo nome:
   "que módulo tem aprendizado de máquina?"
3. **"Que disciplinas tem o módulo de sistemas eletrônicos avançados?"**

## O que ela NÃO responde, e diz que não responde

- **Quais módulos o aluno pode escolher.** A regra (módulo depende da ênfase,
  que depende do curso; muda por ano de ingresso; a CoC aceita aluno de fora)
  não está em campo nenhum do Jupiter, e o dono decidiu em 26/10 deixá-la fora.
  A ferramenta mostra **todos** os módulos com o curso de cada um; a descrição
  diz que elegibilidade não sai dela.
- **Plano de formatura, crédito cumprido, "o que falta".** Discutido e
  descartado em 26/10: exigiria codificar regra que só existe em prosa.
- **Pré-requisito.** Continua em `requisitos(sigla)`.
- **Ênfase e curso.** O modelo de dado serve, mas nenhuma pergunta registrada
  pede. Se voltar, volta por pergunta no §5.

## Desenho

### Uma ferramenta, `modulos`

Cada ferramenta nova custa a descrição em toda sessão, perguntada ou não (o
Jupiter estava em 622 tokens com duas). Três perguntas, uma ferramenta,
distinguidas por parâmetro:

```
modulos(busca: str = "", disciplina: str = "")
```

| chamada | resposta | meta |
|---|---|---|
| `modulos()` | os módulos por carga, menor primeiro: carga, divisão obrigatória/eletiva, nº de disciplinas, curso, nome | ≤ 1.500 tokens |
| `modulos(busca="sistemas eletronicos avancados")` → 1 módulo | carga e divisão, as disciplinas (sigla, nome, créditos, semestre ideal, tipo) agrupadas por semestre | ≤ 600 tokens para 31 disciplinas |
| `modulos(busca="telecom")` → vários | **só candidatos**: código, nome, curso, carga — nunca a grade de todos | ≤ 200 tokens |
| `modulos(busca="xyz")` → nenhum | "nenhum módulo casou" + os cursos que têm módulo (≈ 12 linhas) | ≤ 250 tokens |
| `modulos(disciplina="PMR3508")` | os módulos onde a sigla aparece | ≤ 100 tokens |
| `modulos(disciplina="aprendizado de maquina")` | as disciplinas cujo nome casa, cada uma com seus módulos | ≤ 400 tokens |
| `modulos(disciplina="PM3508")` → sigla inexistente | "não existe nos módulos"; siglas com os mesmos dígitos e o mesmo prefixo | ≤ 100 tokens |
| `busca` e `disciplina` juntos | a busca de disciplina restrita aos módulos que casaram | — |

A regra que mantém o custo baixo: **em dúvida, candidato; grade só quando a
busca resolve para um módulo.** Uma ambiguidade nunca vira 50 grades.

`busca` aceita código (`3032/5080`), nome do módulo ou nome do curso, em
qualquer combinação ("pré-mestrado elétrica"). `disciplina` aceita sigla
(espaço e caixa não importam, como em `disciplina`) ou pedaço do nome.

### O índice

Na primeira chamada, o servidor monta o índice dos módulos e guarda em memória:

1. `jupCursoLista?codcg=3&tipo=V` e `?tipo=N` (HTML) → os 50 pares e os nomes;
   o nome do curso-base de cada `codcur` sai da linha não-módulo de mesmo
   `codcur` na mesma lista (no 3032, "Ciclo Básico - Engenharia Elétrica").
2. Por par, `pubObterInfoCursoWeb` e `pubGradeCurricular`, com o `tipo` da linha
   do link **ativo** da linha (hoje `V` para todos os 50).

Latência medida em 27/10: mediana 0,21 s por chamada DWR, então ~22 s para as 102.

São 2 + 100 requisições, uma de cada vez (o `threading.Lock` do cliente já
existe pelo Invariante 5). **Critério de aceite: a primeira chamada termina em
menos de 60 s**, medido no canário `live`. Se não terminar, o índice passa a
ser gravado em disco e esta seção volta para revisão — não se resolve com
paralelismo.

Validade do índice: **7 dias**. Módulo muda por revisão de currículo, não por
semana; mas o §7 mostrou que a grade cresce dentro do semestre, e um índice sem
validade num servidor que fica de pé por semanas mentiria calado.

O cru não sai do servidor: o índice guarda só os 5 campos de grade que a saída
usa (`coddis`, `nomdis`, `creaul`, `cretrb`, `numsemidl`) mais `tipobg`, e os 6
de carga.

### Busca

`normalizar`: NFKD sem acento, minúscula, só `[a-z0-9 ]`. Palavras vazias:
artigos e preposições, mais "módulo", "matéria", "disciplina" e "engenharia"
(está em todo nome da Poli e não discrimina nada).

Casamento de texto: toda palavra da busca é **prefixo** de alguma palavra do
alvo, com folga de 2 letras no fim para palavras de 6+ ("telecom" →
"telecomunicacoes", "eletronicos" ↔ "eletronica"). Alvo de módulo = nome do
módulo + nome do curso-base. Alvo de disciplina = `nomdis`.

Sigla: depois de tirar espaço e caixa, se tem 5–8 alfanuméricos com três dígitos
seguidos, é sigla. Exata → resposta. Inexistente → parecidas: mesmos 4 dígitos
finais **e** mesmas 2 primeiras letras. Sem parecida, diz que não há.

Este algoritmo é o mínimo que passou nos casos do §9 da medição. Ele não tem
tolerância a erro de digitação no meio da palavra ("eletronicso"), e isso é
aceito: o modelo corrige digitação melhor do que um fuzzy matcher, e de graça.

### Ressalvas — dependentes do dado, nunca prosa fixa

`notas/custo-em-token.md`, Achado 1: texto invariável repetido em toda resposta
é pago duas vezes, porque a descrição já o diz. Então:

- **Na descrição (paga uma vez por sessão):** só a Poli tem módulo; não diz
  quais o aluno pode escolher; carga é a exigida pelo currículo.
- **Na resposta (só quando acontece):** "grade vazia no Jupiter" em vez de "0
  disciplinas" (§6); "grade e carga não publicadas no Jupiter" para os
  percursos; e, quando
  duas gerações casam com a mesma busca, as duas, com o código, sem escolher.
- Em nenhum lugar a palavra "extinto" ou "antigo" para os módulos da lista
  `tipo=V`: o rótulo do Jupiter é "Anteriores", e são os currículos em que os
  alunos de hoje estão.

### Erros

Mesmo tratamento do `requisitos`: falha de rede vira `JupiterIndisponivel` com
mensagem legível; HTML sem a tabela esperada vira `RespostaInvalida` (a lista
de 125 kB sem nenhum `listarGradeCurricular` não é "não tem módulo", é página
diferente). Falha de **um** módulo no meio da montagem não derruba o índice:
o módulo entra marcado "não foi possível ler" e a resposta diz quantos ficaram
de fora (Invariante 7).

### Superfície (Invariante 2)

| allowlist | hoje | depois |
|---|---|---|
| `CONSULTAS_PERMITIDAS` | `pubObterDisciplina`, `pubListarCursoEntrada`, `pubListarColegiado` | + `pubGradeCurricular` (`listar`), `pubObterInfoCursoWeb` (`obter`) |
| `CAMINHOS_PERMITIDOS` | `listarCursosRequisitos` | + `jupCursoLista` |

`jupCursoLista` é lista de curso: nome, código e período, sem pessoa. A trava do
T23 exige a decisão no §9 antes do commit, e ela entra junto.

`codcg` é fixo em `3` no código, não parâmetro: §3 mostrou que nenhuma outra
unidade tem módulo, e parâmetro que só aceita um valor é superfície à toa.

## Testes

Fixtures novas (dado público): as duas listas da Poli; `pubGradeCurricular` e
`pubObterInfoCursoWeb` de 3032/5080 (31 eletivas), 3112/5000 (onde está
PMR3508), 3052/5000 (grade vazia), 3033/6000 (percurso não publicado) e
3032/5100 (pré-mestrado). Um índice reduzido montado delas sustenta
os testes de busca e de custo.

- **Política:** as duas consultas e o caminho novos passam; `obterTurma`
  continua negado; o T23 atualizado.
- **Lista:** das fixtures sai 47 módulos + 3 percursos = 50, todos com `tipo`
  `V` lido do link ativo (o comentado diz `N`, e o teste prova que ele é
  ignorado); o curso-base de 3032 é "Ciclo Básico - Engenharia Elétrica". O
  módulo é reconhecido pela seção "Módulo" da tabela **ou** pelo prefixo
  "Módulo:" do nome — nunca pela palavra "Trilha", que já mudou uma vez.
- **Parâmetro enviado, não saída** (regra 11): o `tipo` que vai no corpo DWR é
  o do link ativo da lista. É o defeito de 14/09, e o dublê não o pegaria.
- **Busca:** a tabela do §9 da medição vira teste, **incluindo** "pré-mestrado
  elétrica" → os pré-mestrados do 3032, que é o caso que falhou.
- **Ressalvas:** cada linha da tabela do §6 produz a sua frase; resposta sem
  defeito não tem ressalva nenhuma.
- **Custo:** os tetos da tabela de chamadas em `tests/jupiter/test_custo.py`,
  em bytes e com folga máxima, como o OR2 do Moodle; mais o custo estático do
  `tools/list` do Jupiter, que sobe de 622 tokens e precisa ser medido e
  travado.
- **Handshake:** a terceira ferramenta é anunciada no fio (o defeito do
  `listar_ferramentas()[0]` de 14/09 é exatamente este caso).
- **Live** (atrás de `USP_MCP_LIVE=1`): o índice real monta em < 60 s, tem ≥ 45
  módulos, e PMR3508 está em 3112/5000.

## Documentação na mesma PR

- `SPEC1.md` §9: entrada de 26/10 com os fatos acima, **corrigindo
  explicitamente** a de 14/09 ("a superfície pública cobre só a metade de
  entrada") e o "nenhum payload tem vigência"; §1 ganha `tipobg=C` e `tipo=V`.
- `notas/jupiter-recon.md`: §4.1, os "não verificado" que fecharam
  (`pubObterInfoCursoWeb`); §5.1, o `tipo=V`.
- `docs/decisions/BACKLOG-correcoes.md`: as linhas de 14/09 sobre a fatia
  `curso` apontam para esta.
- `README.md`: a ferramenta nova na lista.
