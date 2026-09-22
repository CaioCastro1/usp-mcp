# Custo em token das ferramentas — desenho

> Data: 22/09/2026. Fecha com medição, e a medição está em
> `notas/custo-em-token.md`. O que aqui é projeção está marcado como projeção.

## O problema, medido

Este projeto sempre mediu o custo do **cru** que vem da USP — o §9 do `SPEC1.md`
registra 541 kB para 35 eventos de calendário, 1 MB para as entregas sem escopo,
e a projeção que reduz isso a 0,5%–6%. O que nunca foi medido é o outro lado: o
que a ferramenta **devolve ao modelo**, que é o que de fato ocupa contexto.

Medido em 22/09/2026, offline, por dois caminhos que não tocam a rede nem gastam
chamada da conta:

- **estático** — `initialize` + `tools/list` de cada servidor, pelo cliente stdio
  de `tests/handshake/`;
- **por chamada** — cada ferramenta contra as fixtures versionadas, pelo dublê
  `ClienteFalso`.

| | tokens |
|---|---:|
| estático dos três servidores, por sessão | **5.262** |
| `material` (PTC3314, 57 itens) | **2.569** |
| `disciplinas` (74 matrículas) | **1.350** |
| `avisos` (1 fórum) | 948 |
| `atrasadas` | 325 |
| `ja_entreguei` | 310 |
| `o_que_mudou` | 285 |
| `notas` | 165 |

Três achados sustentam este desenho, e nenhum é opinião.

**1. A prosa invariável é paga duas vezes.** 801 tok espalhados por sete
ferramentas saem idênticos a cada chamada — e a descrição da própria ferramenta,
que está em contexto a sessão inteira, já os contém. Sobreposição de vocabulário
medida: `ja_entreguei` 92%, `atrasadas` 85%, `o_que_mudou` 71%, `atrasadas`
(segunda ressalva) 58%. Em `atrasadas`, 215 dos 325 tok da resposta são texto
que a descrição de 279 tok já diz, quase palavra por palavra. Não é troca de
custo-por-chamada por custo-por-sessão: é a mesma frase, duas vezes, na mesma
sessão.

**2. O campo que anota custa mais que o dado anotado.** Em `material`, o bloco
`[PDF, 2425 kB, 03/07/2026]` soma 933 tok — o dobro dos ~460 tok dos 57 nomes de
arquivo que ele descreve.

**3. Em `disciplinas`, 565 tok (42% da resposta) são as 62 matrículas
encerradas** — de 2021 a 2026, listadas em toda chamada, respondendo a uma
pergunta que ninguém fez.

### E uma correção de método

O `~bytes/4` que o `CONVENTIONS.md` §1 adota **subestima**, e subestima justamente
onde dói. Contra um tokenizador real (o200k; não é o do Claude, mas a direção é
robusta):

| saída | `bytes/4` | real | razão |
|---|---:|---:|---:|
| `disciplinas` | 804 | 1.350 | **1,68×** |
| `o_que_vence` | 701 | 1.093 | 1,56× |
| `material` | 1.678 | 2.569 | 1,53× |
| `atrasadas` | 318 | 319 | 1,00× |
| **conjunto** | 5.415 | 7.496 | **1,38×** |

O padrão explica a si mesmo: prosa em português fica perto de 4 B/token, e
**código, nome de arquivo e data não** — `PSI3322-2026-REOF` e
`tensao_Zl=150_pulso.gif` explodem. A consequência é que a tabela de custo do
`SPEC1.md` é otimista exatamente nas respostas em forma de listagem, que são as
caras. Números novos de custo de **saída** passam a sair de tokenizador; o
`bytes/4` continua servindo para o cru, onde a razão medida foi 1,00×–1,15×.

## A regra

**Uma ressalva invariável só sai quando a resposta desta chamada pode ser lida
errado sem ela.** Cada ressalva declara qual leitura errada desmente:

- **`ausencia`** — a lista vazia parece "não tem nada". Sai só quando a resposta
  está vazia.
- **`presenca`** — o dado listado parece mais do que é. Sai só quando há item.
- **`roteamento`** — "para X, use a ferramenta Y". **Nunca sai na resposta.** Mora
  na descrição, que o cliente carrega a sessão inteira.

`ausencia` e `presenca` são complementares: por construção nunca saem juntas.
Hoje as duas saem sempre, o que é o desperdício em uma frase.

Isto **não** afrouxa o Invariante 6. O Invariante 6 proíbe o silêncio que engana
— a lista vazia que parece "não tem nada", o erro cru engolido. A regra acima
preserva a ressalva exatamente onde essa leitura é possível, e a cala onde ela
só repete o que o cliente já leu. O que sai de cena é repetição, não aviso.

### Ressalva por ferramenta

| ferramenta | ressalva | classe | condição de saída |
|---|---|---|---|
| `atrasadas` | "diz o que REGISTRA, não o que você fez" | presença | há entrega listada — é aí que o modelo acusaria alguém de não ter entregue |
| `atrasadas` | "cobre só tarefa, não questionário" | ausência | lista vazia — é aí que "não devo nada" mente |
| `atrasadas` | "para todas as entregas use `ja_entreguei`…" | roteamento | nunca |
| `ja_entreguei` | "cobre só tarefa" | ausência | a disciplina não tem entrega nenhuma |
| `ja_entreguei` | "não traz a nota" | presença | há item já corrigido |
| `notas` | "esta é a final; item a item, diga a disciplina" | roteamento | nunca (era roteamento disfarçado de ressalva) |
| `o_que_mudou` | "diz QUE mudou, nunca O QUE" | presença | há mudança listada |
| `material` | "o link não sai daqui, use `baixar_arquivo`" | presença | há arquivo interno na lista |
| `avisos` | "quem escreveu não sai daqui" | presença | há tópico listado |
| `avisos` | "aviso dado em sala não entra" | ausência | lista vazia |
| `disciplinas` | "use a SIGLA ou o RÓTULO inteiro" | roteamento | nunca — o esquema do parâmetro `disciplina` das quatro consumidoras já diz isso |
| `disciplinas` | "'Em andamento' sai das datas do espaço" | contrato | vai para a descrição |

As ressalvas **dependentes de dado** — "2 atividades não puderam ser lidas com
esta credencial", "38 das 45 matrículas sem nota", "2 tópicos truncados em 600
caracteres" — não são tocadas por este desenho. Elas variam com a resposta, são
362 tok no conjunto, e são o Invariante 7 funcionando.

## Onde a regra mora

`usp_mcp/moodle/ressalvas.py`, um lugar só:

```python
@dataclass(frozen=True)
class Ressalva:
    texto: str
    quando: str  # "ausencia" | "presenca"

def emitir(ressalvas: Sequence[Ressalva], *, vazio: bool) -> list[str]
```

Cada ferramenta declara as suas como constante de módulo e chama `emitir`. A
alternativa — um `if` no ponto onde hoje há `partes.append(...)` — espalharia a
regra por sete módulos, e este repo já pagou duas vezes por isso: `texto.py`
existe porque duas semânticas de casamento por nome nasceram em módulos
diferentes e custaram o T83.

`quando` tem **dois** valores, `"ausencia"` e `"presenca"`, e só eles. As outras
duas classes da tabela acima não são valores: uma ressalva de `roteamento` e uma
de `contrato` não chegam a `ressalvas.py` — elas somem do código e passam a viver
na descrição da ferramenta. Deixá-las existir como dado convidaria a próxima
sessão a emiti-las "só nesse caso", que é como a regra volta a ser sempre.

## Listagens

**`material`** — o rótulo de tipo sai quando a extensão do arquivo já o diz
(`Lista 1.pdf [PDF, …]`); fica quando não diz (link externo, `.odg`,
`application/octet-stream`). O tamanho fica só acima de um teto: a mesma
disciplina tem GIF de 178 MB, e ali o número decide se vale baixar — a
medição de 01/09 registra que o `filesize` declarado bate exatamente com os
bytes recebidos, então ele prevê custo. Teto proposto: **10 MB**.

**`disciplinas`** — as encerradas viram contagem por ano
(`2026: 11 · 2025: 24 · 2024: 14 · 2023: 12 · 2021: 1`) e `todas` expande. A
descrição muda junto: ela hoje promete "vêm só com a sigla, agrupadas por ano —
nenhuma fica de fora", e passará a prometer a contagem e o caminho para a lista.
A saída declara a omissão, como já declara hoje.

## Estático

A explicação de `disciplina` é idêntica em quatro ferramentas, 67 tok cada. Ela
encolhe para um ponteiro curto no esquema, e o texto completo passa a morar uma
vez no `instructions`. Projeção: −160 tok.

Os campos `title` gerados pelo pydantic (~127 tok nos 14 esquemas,
`"_ja_entregueiArguments"`) **não são removíveis**: o SDK deriva o schema da
assinatura, e suprimi-los exigiria um gerador de schema próprio. Vão para o
backlog como custo medido que não controlamos, não como tarefa.

As onze descrições **não** encolhem. Com a regra das ressalvas, a descrição passa
a ser a casa canônica do contrato de cada ferramenta — encurtar as duas pontas na
mesma mudança é como um invariante se perde sem ninguém notar.

## O que impede a regressão

**`tests/moodle/test_custo.py`.** Mede a saída de cada ferramenta contra as
fixtures versionadas e falha acima de um teto por ferramenta. É o padrão do T39
(`528 kB crus → < 4.000 caracteres`) estendido às nove. Offline, sem credencial,
entra no gate.

O teto é contado em **bytes**, e não em tokens, apesar de a correção acima dizer
que bytes enganam. O motivo é que um tokenizador seria a segunda dependência de
runtime deste projeto (hoje só `mcp`), e o precedente já existe e está registrado:
o `pypdf` foi instalado para medir os 19 PDFs em 01/09 e **desinstalado depois**,
porque adotá-lo seria decisão de §9 e não efeito colateral de uma medida. O mesmo
vale aqui. Byte é ruim como unidade de custo e ótimo como unidade de regressão:
ele é determinístico, não depende de versão de vocabulário, e a pergunta que o
teste faz não é "quanto custa" — é "cresceu?". A tradução byte→token fica na
nota, medida uma vez, com o fator por ferramenta. O teto entra **antes** dos cortes, travando o estado de hoje; cada
corte depois baixa o teto no mesmo commit que o produz. Sem isso, a próxima
sessão desfaz este trabalho sem saber.

**O canário de duplicação.** Para cada ferramenta, nenhuma frase da saída pode
estar também na descrição dela. Duplicação nova vira vermelho por construção, em
vez de depender de alguém pensar em medir de novo — a mesma forma dos invariantes
mecânicos que este repo já usa (nenhum `--data-urlencode` no argv do `ws.sh`).

O canário compara **sentenças normalizadas**, não substrings: a saída e a
descrição são quebradas em frases, normalizadas (minúscula, sem acento, sem
pontuação, sem crase de código) e comparadas por igualdade de conjunto de
palavras acima de um limiar. O limiar entra em **0,8** e é constante nomeada, com
o motivo ao lado — abaixo disso ele reprovaria paráfrase legítima ("entrega" e
"tarefa" aparecem nos dois lados por serem o assunto, não por serem cópia).

## Ganho

Projeção aritmética sobre o medido, **não medição** — os números que valem saem
do teste de orçamento a cada corte:

| | hoje | projetado |
|---|---:|---:|
| `material` | 2.569 | ~2.030 |
| `disciplinas` | 1.350 | ~780 |
| `atrasadas` | 325 | ~180 |
| `ja_entreguei` | 310 | ~215 |
| `avisos` | 948 | ~880 |
| `notas` + `o_que_mudou` | 450 | ~390 |
| estático | 5.262 | ~5.100 |

Sessão típica (`disciplinas` + `material` + `o_que_vence`): ~5.000 → ~3.300 tok
de resposta.

## Entrega

Quatro mudanças, nesta ordem, cada uma com a Definição de Pronto do §5 do
`CLAUDE.md`:

1. **A medição** — `notas/custo-em-token.md`, decisão no §9, os `title` do
   pydantic no backlog, e `test_custo.py` travando o estado atual.
2. **`ressalvas.py`** e as sete ferramentas.
3. **As duas listagens** — mudam saída e descrição juntas.
4. **O estático** — `disciplina` e `instructions`.

## O que este desenho não faz

- **Não funde ferramenta.** Fundir `atrasadas` + `ja_entreguei` + `o_que_vence`
  num só com parâmetro de modo economizaria ~700 tok estáticos e violaria o §5 do
  `SPEC1.md`: nome de ferramenta vem da pergunta do dono, não da função da API.
- **Não muda o padrão de `material` para seções recentes.** Pareceu o corte óbvio
  (−1.200 tok) e o dado o desmente: em PTC3314 a apostila, as provas antigas e a
  carta de Smith estão todas na **primeira** seção. Um padrão por recência
  esconderia justamente o que mais se pede.
- **Não toca a projeção do cru.** Ela já entrega 0,5%–6%, e o gargalo mudou de
  lado.
- **Não toca `o_que_vence` nem `diagnostico`.** `o_que_vence` não tem prosa
  invariável (a `cobertura` dele é uma frase só, e é `ausencia` legítima);
  `diagnostico` é chamado uma vez e é só prosa por natureza.
