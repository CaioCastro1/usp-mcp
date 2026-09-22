# Custo em token do lado de cá — medição de 22/09/2026

Este repositório mediu o custo do **cru** desde a Fase 1: 541 kB para 35 eventos
de calendário, 1 MB para as entregas sem escopo, e a projeção que reduz isso a
0,5%–6% (`notas/fase1-moodle.md`, §9 do `SPEC1.md`). O outro lado nunca foi
medido: **o que a ferramenta devolve ao modelo**, que é o que de fato ocupa
contexto depois que a projeção já fez o trabalho dela.

Medido aqui, e sem gastar chamada da conta.

## Como

Dois caminhos, ambos offline, nenhum toca a rede da USP.

**Estático** — `initialize` + `tools/list` de cada servidor, pelo cliente stdio de
`tests/handshake/conftest.py`. Os três servidores respondem essas duas mensagens
sem construir o cliente da API, que é por que isso roda sem credencial.

**Por chamada** — cada ferramenta via `chamar_ferramenta(..., cliente=dublê)`,
com as fixtures versionadas como resposta do e-Disciplinas. O `site_info` é
sintético (o cru tem `userid` e nome) e declara as treze funções que as
ferramentas pedem, para que a saída medida seja a boa e não a de "não alcança".

**Contagem.** Bytes por `len(texto.encode())`. Tokens por `tiktoken`
(`o200k_base`), instalado num ambiente efêmero (`uv run --with`) só para esta
medição e **não adotado** — mesmo tratamento que o `pypdf` recebeu em 01/09. Não
é o tokenizador do Claude; serve para a ordem de grandeza e, principalmente, para
a razão entre formas de texto, que é o achado que importa.

## O estático: 5.262 tokens por sessão, antes da primeira pergunta

| servidor | `instructions` | `tools/list` | total | ferramentas |
|---|---:|---:|---:|---:|
| moodle | 551 | 3.581 | **4.132** | 11 |
| jupiter | 0 | 622 | 622 | 2 |
| rucard | 0 | 508 | 508 | 1 |
| | | | **5.262** | 14 |

Por ferramenta do Moodle (descrição + esquema, em tokens):

| | descrição | esquema | soma |
|---|---:|---:|---:|
| `ja_entreguei` | 223 | 199 | 422 |
| `questionarios` | 220 | 198 | 418 |
| `material` | 216 | 197 | 413 |
| `atrasadas` | 279 | 106 | 385 |
| `baixar_arquivo` | 109 | 257 | 366 |
| `o_que_mudou` | 168 | 183 | 351 |
| `avisos` | 182 | 113 | 295 |
| `notas` | 166 | 104 | 270 |
| `o_que_vence` | 110 | 130 | 240 |
| `disciplinas` | 161 | 76 | 237 |
| `diagnostico` | 165 | 19 | 184 |

Isto é maior que qualquer resposta individual do servidor, e é pago mesmo na
sessão em que ninguém pergunta nada.

Dois desperdícios medidos dentro dele:

- **A descrição do parâmetro `disciplina` é idêntica em quatro ferramentas**, 67
  tokens cada: 268 no total, 201 dos quais são repetição literal.
- **Os campos `title` gerados pelo pydantic** (`"_ja_entregueiArguments"`,
  `"Disciplina"`) somam ~127 tokens nos 14 esquemas. **Não são removíveis**: o SDK
  deriva o schema da assinatura da função (`usp_mcp/adaptador.py`), e suprimi-los
  exigiria um gerador de schema próprio. Fica registrado como custo que não
  controlamos.

## Por chamada

Com as fixtures versionadas (PTC3314; 74 matrículas):

| ferramenta | bytes | tokens | resposta | aviso de dado | prosa fixa |
|---|---:|---:|---:|---:|---:|
| `material` | 6.712 | **2.569** | 2.369 | 126 | 91 |
| `disciplinas` | 3.219 | **1.350** | 1.136 | 52 | 168 |
| `o_que_vence` | 2.807 | 1.093 * | 1.093 | 0 | 0 |
| `avisos` | 3.289 | 948 | 798 | 43 | 107 |
| `diagnostico` | 1.874 | 473 † | 473 | 0 | 0 |
| `atrasadas` | 1.274 | 325 | 73 | 37 | **215** |
| `ja_entreguei` | 978 | 310 | 153 | 37 | 120 |
| `o_que_mudou` | 1.018 | 285 | 195 | 22 | 68 |
| `notas` | 491 | 165 | 88 | 45 | 32 |

\* O dublê devolve a fixture inteira ignorando `timesortfrom/to`: são ~4 meses de
eventos, não os 14 dias do padrão. Em produção o número é uma fração disto,
porque a janela vai como parâmetro da chamada (T32/T33). Regra 11 do `CLAUDE.md`.

† Depende do caminho absoluto do `.env` desta máquina e de quantas funções o
token alcança — por isso `diagnostico` fica fora do orçamento de
`tests/moodle/test_custo.py`.

Não medidos: `questionarios` (não há fixture de `mod_quiz_*` no repositório) e
`baixar_arquivo` (devolve caminho em disco; por decisão de 01/09 ela não extrai
texto, o que economiza ~2.679 tokens por PDF).

## Achado 1 — a prosa invariável é paga duas vezes

**801 tokens**, espalhados por sete ferramentas, saem idênticos a toda chamada. E
a descrição da própria ferramenta — que o cliente carrega a sessão inteira — já
os contém. Sobreposição de vocabulário de conteúdo entre o bloco `⚠` e a
descrição:

| ferramenta | bloco | sobreposição |
|---|---|---:|
| `ja_entreguei` | "cobre só TAREFA; questionário use `questionarios`" | **92%** |
| `atrasadas` | "para ver TODAS as entregas use `ja_entreguei`…" | **85%** |
| `o_que_mudou` | "diz QUE mudou, nunca O QUE mudou" | 71% |
| `atrasadas` | "diz o que REGISTRA, não o que você fez" | 58% |
| `avisos` | "quem escreveu cada tópico não sai daqui" | 50% |
| `notas` | "esta é a nota FINAL; item a item, diga a disciplina" | 50% |
| `material` | "o link do arquivo interno não é entregue aqui" | 39% |
| `disciplinas` | "'Em andamento' sai das datas do espaço" | 21% |
| `disciplinas` | "use a SIGLA ou o RÓTULO inteiro" | 10% |

O caso extremo é `atrasadas`: **215 dos seus 325 tokens de resposta são texto que
a descrição de 279 tokens já diz**, quase palavra por palavra. Não é troca de
custo-por-chamada por custo-por-sessão — é a mesma frase, duas vezes, na mesma
sessão. As duas últimas linhas da tabela são o contraste que fecha o argumento:
ali a resposta diz algo que a descrição não diz.

As ressalvas **dependentes de dado** ("2 atividades não puderam ser lidas com
esta credencial", "38 das 45 matrículas sem nota", "2 tópicos truncados em 600
caracteres") somam 362 tokens no conjunto e não são repetição: são o Invariante 7
funcionando.

## Achado 2 — o campo que anota custa mais que o dado anotado

Em `material`, para as 57 linhas de item:

| | tokens |
|---|---:|
| os 57 nomes de arquivo | ~460 |
| os 57 blocos `[tipo, tamanho, data]` | **933** |
| \- só os trechos `, NNN kB` | 304 |
| as 55 descrições do professor entre parênteses | 810 |

O bloco que descreve o arquivo custa o dobro do nome do arquivo.

## Achado 3 — `disciplinas` gasta 42% da resposta com o passado

Das 74 matrículas, 62 estão encerradas (2021 a 2026) e saem em toda chamada como
lista de rótulos por ano: **565 dos 1.350 tokens**. As 10 em andamento, que são a
resposta à pergunta, custam 476.

## Achado 4 — o `~bytes/4` do projeto subestima, e subestima onde dói

O `CONVENTIONS.md` §1 adota `bytes/4` como estimativa de token. Contra o
tokenizador:

| saída | `bytes/4` | real | razão |
|---|---:|---:|---:|
| `disciplinas` | 804 | 1.350 | **1,68×** |
| `o_que_vence` | 701 | 1.093 | 1,56× |
| `material` | 1.678 | 2.569 | 1,53× |
| `notas` | 122 | 163 | 1,33× |
| `ja_entreguei` | 244 | 306 | 1,25× |
| `avisos` | 822 | 943 | 1,15× |
| `o_que_mudou` | 254 | 282 | 1,11× |
| `diagnostico` | 468 | 471 | 1,01× |
| `atrasadas` | 318 | 319 | 1,00× |
| **conjunto** | 5.415 | 7.496 | **1,38×** |

O padrão explica a si mesmo, e a ordem da tabela é a explicação: **prosa em
português fica perto de 4 bytes por token; código, nome de arquivo e data não.**
`atrasadas` é quase só prosa e bate 1,00×; `disciplinas` é quase só rótulo
(`PSI3322-2026-REOF`, `PME3100-203-2023`) e erra por 68%. `material` mistura os
dois e fica no meio, com nomes como `tensao_Zl=150_pulso.gif`.

**A consequência:** a tabela de custo do `SPEC1.md` é otimista exatamente nas
respostas em forma de listagem, que são as caras. O `bytes/4` continua servindo
para o **cru** — ali a razão medida foi 1,00× a 1,15×, porque JSON do Moodle é
prosa e chave repetida. Para custo de **saída**, o número honesto sai de
tokenizador, e esta nota é onde ele mora.

## O resultado, medido depois (22/09/2026)

Mesmo método, mesmas fixtures, mesmo tokenizador, com os quatro cortes dentro:

| ferramenta | antes | depois | |
|---|---:|---:|---|
| `disciplinas` | 1.350 | **664** | −51% |
| `atrasadas` | 319 | **190** | −40% |
| `ja_entreguei` | 306 | **220** | −28% |
| `notas` | 163 | **131** | −20% |
| `material` | 2.569 | **2.166** | −16% |
| `o_que_mudou` | 282 | **246** | −13% |
| `avisos` | 943 | 943 | 0% |
| `o_que_vence` | 1.093 | 1.093 | 0% |
| **soma** | **7.025** | **5.653** | **−20%** |
| estático (3 servidores) | 5.262 | 5.194 | −1,3% |

Uma sessão típica — `disciplinas`, `material`, `o_que_vence` — cai de 5.012 para
3.923 tokens de resposta, 22% menos.

**Os dois zeros são decisão, não esquecimento.** `avisos` ficou porque o
`_COBERTURA` dela protege leituras nos dois sentidos, e o teste A15 afirma
justamente o segundo (§9, 22/09). `o_que_vence` não tinha prosa invariável para
cortar: a `cobertura` dele é uma frase só, e legítima.

**E o estático mal se moveu, que era o esperado.** Ele é a maior linha isolada da
tabela (5.194 de ~9.100 numa sessão típica) e ficou quase intacto por decisão: a
descrição de cada ferramenta virou a casa canônica do contrato quando a ressalva
saiu da resposta, e encurtar as duas pontas na mesma mudança é como um invariante
se perde. Quem quiser mexer aí de novo começa por `questionarios` (418 tokens de
descrição e esquema, e custo de resposta ainda desconhecido — ver o backlog).

## Os outros dois servidores — medidos em 22/09/2026

A medição acima cobriu o Moodle. Jupiter e RUCard entraram depois, pelo mesmo
método: dublê de transporte, fixtures versionadas, nenhuma chamada à USP.
Nenhum dos dois tem `instructions`, então o `tools/list` é o estático inteiro.

### Jupiter — 622 tokens de estático, e o estático custa mais que a chamada

| | descrição | esquema | soma |
|---|---:|---:|---:|
| `disciplina` | 140 | 261 | **401** |
| `requisitos` | 138 | 83 | 221 |

| saída | tokens |
|---|---:|
| `disciplina` PSI3323 (padrão) | 175 |
| `disciplina` PTC3314 (padrão) | 194 |
| `disciplina` PTC3314 + inglês | 276 |
| `disciplina` PTC3314 `secoes=["todas"]` | 789 |
| `requisitos` PSI3323 (1 currículo) | 98 |
| `requisitos` PTC3313 (sem exigência) | 151 |
| `requisitos` MAT2455 (23 currículos) | **747** |

**O padrão de só-ementa já fez o corte grande, e a medição confirma:** a ficha
inteira custa 789 tokens e o padrão, 194 — 75% cortados pela decisão de 14/09.
Três consultas típicas custam menos que o `tools/list` que as anuncia.

Dois desperdícios medidos, e nenhum foi cortado nesta passagem (ver backlog):

- **`requisitos` repete um valor constante 23 vezes.** Em MAT2455,
  `(integral, 3º período ideal)` sai em toda linha de currículo — **230 tokens,
  31% da resposta** — e tem **um único valor distinto**. É o mesmo achado do
  `[tipo, tamanho, data]` do `material`.
- **`disciplina` repete a própria descrição.** A linha "⚠ Pré-requisito não vem
  por aqui: use a ferramenta requisitos" tem **80% de sobreposição** com a
  descrição da ferramenta — exatamente o limiar do canário OR3.

O que **não** vale mexer: os 261 tokens do esquema do `disciplina` são 65% do
custo estático dele, e carregam o enum de `secoes` — que é o que faz o padrão
barato existir. Trocar isso por resposta cara é pior negócio.

### RUCard — a resposta mais cara do projeto inteiro, e sem teto que a cubra

Estático: 508 tokens, numa ferramenta só. O `bandejao` tem o **maior esquema
único do projeto**, 302 tokens.

| saída | bytes | tokens |
|---|---:|---:|
| 1 RU, só almoço | 318 | 113 |
| 4 RUs, só almoço | 926 | 332 |
| 4 RUs, dia inteiro | 1.601 | 565 |
| semana, só almoço | 4.560 | 1.482 |
| **semana, tudo** | **8.018** | **2.642** |

**A semana custa mais que qualquer resposta do Moodle** — 2.642 tokens contra
2.166 do `material` já cortado — e o teto de `tests/rucard/test_custo.py`
(R34, 4.500 B) **não a alcança**: ele foi medido em 31/08 sobre "o pior caso
(4 RUs × 2 refeições)", que era verdade então; o `dia="semana"` chegou depois,
com o R46, e ninguém remediu. A saída da semana está 78% acima daquele teto sem
nada ficar vermelho — "verde na suíte não é verde no que ela não alcança",
outra vez.

E a causa da repetição é específica: o rodapé que iça item comum existe
(`Em todas as refeições acima:`), e a regra dele é **comum a TODAS as refeições
da resposta**. No dia, com poucos blocos, ela pega o arroz. Na semana, a
interseção de sete blocos × sete dias encolhe a quase nada, e
`Arroz / feijão / arroz integral` fica inline **32 vezes — 256 tokens, 10% da
resposta**. A regra falha exatamente onde a repetição é pior. Somando os itens
que aparecem em cinco linhas ou mais: 429 tokens, 16% da resposta.

### E o `bytes/4` erra aqui também, na outra direção

| | `bytes/4` | real | razão |
|---|---:|---:|---:|
| RUCard, 1 RU | 79 | 113 | **1,43×** |
| RUCard, semana | 2.004 | 2.642 | 1,32× |
| Jupiter `disciplina` (padrão) | 176 | 194 | 1,10× |
| Jupiter `disciplina` `todas` | 883 | 789 | **0,89×** |

Nome de prato em português (`Escondidinho de shimeji`, `Salada de almeirão`)
tokeniza pior que prosa; texto corrido longo de ementa tokeniza **melhor** que
4 B/token. A regra do Achado 4 se confirma nos dois extremos.

## O que isto virou

O desenho está em
`docs/superpowers/specs/2026-09-22-custo-em-token-design.md`; a decisão, no §9 do
`SPEC1.md`. A guarda é `tests/moodle/test_custo.py`, que mede a mesma coisa em
bytes — determinístico, sem dependência nova — e falha tanto quando a saída
cresce quanto quando o teto fica frouxo demais para detectar o próximo
crescimento.
