# CONVENTIONS — padrões deste repo

> **Este arquivo é de sessão de MANUTENÇÃO.** Ele supõe que você vai mexer no
> código deste repositório: gate, formato de commit, fluxo de merge, sigla de
> teste. Quem clonou para **usar** o projeto não precisa de nada daqui — o §0 do
> `CLAUDE.md` e o `PAPEL-DA-SESSAO.md`, ao lado, dizem o que vale nesse caso.
> (A pasta se chama `agents/` por acidente de origem, e o nome já enganou:
> veja a mesma ressalva no `.github/CONTRIBUTING.md`.)
>
> Complementa o `CLAUDE.md` (regras não-negociáveis) e o `SPEC1.md` (autoridade).
> Aqui vive o COMO. Seções que não se aplicam a este projeto foram apagadas em vez
> de deixadas como `<TODO>` morto — banco de dados e frontend não existem aqui.

## 0. Princípio guia: medir antes de desenhar

Toda resposta de API que entra no projeto ganha três números antes de qualquer
decisão sobre ela: **bytes**, **estimativa de tokens** e **quantas chamadas** foram
necessárias para responder à pergunta (§3.2 do `SPEC1.md`). Esses números decidem
mais sobre o desenho do que qualquer preferência estética — e são o que separa
"resumir no servidor" de "devolver cru".

O corolário: nunca despeje payload cru na janela. `scripts/capture.sh` existe para
que ler uma resposta de 251k tokens seja impossível por acidente.

## 1. Integrações externas

Uma API não documentada por vez, um client central por API. Regras que já
custaram medição para descobrir:

- **Moodle** (`scripts/ws.sh`): uma função por invocação, escolhida à mão. O script
  não itera sobre lista de propósito. Erro cru vai para stdout sem filtro
  (Invariante 6) — não engolir, não normalizar, não transformar em `[]`.
- **RUCard**: POST form-urlencoded (`GET` devolve 500 com HTML do Tomcat, não JSON).
  Todos os valores de `/restaurants` são string, inclusive booleanos — `hasCashier`
  vem `"false"` nos 18 RUs e é sempre errado; usar o tamanho de `cashiers`. Em
  `/menu`, `message.error` é booleano de verdade: as duas rotas não seguem a mesma
  regra. Resolver RU **por id**, nunca por `name`/`alias`.
- **Jupiter**: ver `notas/jupiter-recon.md` antes de tocar. Nenhum laço, nenhuma
  enumeração de id, nenhum catálogo baixado.

Cache com TTL colado na taxa de mudança do dado (Invariante 5), não na frequência
da pergunta.

## 2. Segredo e dado pessoal

- `.env` no gitignore, `.env.example` é forma e nunca conteúdo.
- Nenhum script imprime o valor de um token — só diagnóstico de forma
  (`fix-token.sh` é o modelo: valida 32 hex, nunca ecoa). Três corolários que o
  `token.sh` de 10/09 tornou explícitos: o valor **não passa por `argv`** (`ps aux`
  é legível por qualquer processo do usuário — use `curl -K -`, que lê do stdin, ou
  variável de ambiente), o base64 cru do fluxo de launch **não toca o disco** (ele
  carrega o `privatetoken`, que habilita autologin — decodifique antes de escrever),
  e a regra do formato mora em `scripts/_decodificar_token.py`, em um lugar só.
- Valor derivável não se configura à mão: `MOODLE_USERID` sai do próprio token via
  `core_webservice_get_site_info`, porque um userid errado devolve `[]` com HTTP 200
  e nenhum erro — o falso "não tem nada" que o Invariante 6 proíbe.
- Fixture com dado pessoal só entra no git depois da higienização do §3.3, que
  preserva a forma: mesmo id → mesmo valor falso.

## 3. Estrutura de código

**Python 3 + pytest.** O repo já rodava `python3`; `pytest` é a única dependência,
declarada em `requirements-dev.txt` e instalada num venv local (`.venv/`, no gitignore).

`usp_mcp/<sistema>/` por sistema (`jupiter/`, `moodle/`, `rucard/`), cada um com
`cliente.py` (transporte + allowlist na fronteira) e `ferramentas.py`. O que é comum aos
três mora em `usp_mcp/` (hoje `env.py` e `adaptador.py`). **O `server.py` mora dentro do
subpacote, nunca na raiz:** o §6 do `SPEC1.md` separa entrypoint local com credencial
(Moodle, stdio) de servidor público cacheável (Jupiter, RUCard), e a estrutura reflete
isso em vez de deixar a separação só na prosa. Testes em `tests/<sistema>/`.

Erro da API sobe como exceção com mensagem legível em português. O cru — stack trace,
classe interna do servidor — é descartado antes de qualquer log: no Jupiter isso são
1.978 tokens contra 17 da mensagem, e o cru é a resposta errada.

Nome de ferramenta vem da pergunta do dono, não da função do Moodle: `o_que_vence`
é bom nome, `get_action_events_by_timesort` não é (§5 do `SPEC1.md`).

### Notação dos testes: que letra mora em que arquivo

O código inteiro cita teste por sigla: `T78-T81`, `H6`, `P5`, `L2`, `A6`, `M17`,
`E1-E4`, `D1-D2`. Para quem escreveu, é taquigrafia útil. Para uma terceira
pessoa, "H6 pegou material em 31/08" não tem referente, e até 16/09/2026 não
havia arquivo nenhum dizendo o que cada letra significa. A tabela abaixo foi
derivada lendo os arquivos, e não de memória; a docstring de cada arquivo é a
fonte de verdade sobre o que aquela família cobre.

| Sigla | Arquivo | Do que trata |
|---|---|---|
| `A1-A8` | `tests/test_anotacoes.py` | a promessa de read-only chega ao cliente como campo |
| `A1-A20` | `tests/moodle/test_avisos.py` | a ferramenta `avisos` |
| `AT1-AT20` | `tests/moodle/test_atrasadas.py` | a ferramenta `atrasadas` |
| `C1-C9` | `tests/test_ci.py` | o workflow do CI |
| `D1-D2` | `tests/test_documentacao.py` | o README leva um clone limpo até o gate |
| `D3-D6` | `tests/test_gate.py` | a checagem 0 do gate, e o código de saída dele |
| `D1-D6` | `tests/moodle/test_diagnostico.py` | a ferramenta `diagnostico` |
| `DI1-DI23` | `tests/moodle/test_disciplinas.py` | a ferramenta `disciplinas` |
| `E1-E4` | `tests/{jupiter,moodle,rucard}/test_erro_no_fio.py` | o erro chega ao modelo, nos três sistemas |
| `E1-E6` | `tests/moodle/test_politica_entrega.py` | as duas condições que governam a escrita |
| `E7-E12` | `tests/moodle/test_entrega.py` | o plano de entrega e as recusas |
| `E13` | `tests/moodle/test_live.py` | o plano contra uma entrega real, sem escrever |
| `E14` | `tests/handshake/test_entrega_no_fio.py` | sem a flag, as ferramentas de escrita não existem no fio |
| `F1-F9` | `tests/moodle/test_forma_real.py` | nem o dublê monta campo que o e-Disciplinas não tem |
| `G1-G5` | `tests/test_git.py` | o helper que pergunta ao git se um caminho está ignorado |
| `H1-H10` | `tests/handshake/test_stdio.py` | o handshake stdio de cada servidor, como processo |
| `J1` | `tests/test_jargao.py` | o que sai do processo não cita o `SPEC1.md` |
| `J1-J25` | `tests/moodle/test_ja_entreguei.py` | a ferramenta `ja_entreguei` |
| `L1-L6` | `tests/test_lancador.py` | o `scripts/servidor.sh` |
| `M1-M18` | `tests/moodle/test_o_que_mudou.py` | a ferramenta `o_que_mudou` |
| `N1-N18` | `tests/moodle/test_notas.py` | a ferramenta `notas` |
| `P1-P6` | `tests/test_pacote.py` | o `pyproject.toml` e os entry points |
| `P1-P5` | `tests/moodle/test_politica.py` | a allowlist do Moodle (Invariante 2) |
| `R1-R59` | `tests/rucard/*.py` | o RUCard inteiro, uma faixa por arquivo |
| `T1-T5` | `tests/test_token_fora_do_argv.py` | o token não passa pela linha de comando do `curl` |
| `T1-T87` | `tests/jupiter/*.py` | o Jupiter inteiro, uma faixa por arquivo |
| `T68-T114` | `tests/moodle/*.py` | material, arquivo, depósito, cliente e fronteira do Moodle |
| `U1-U3` | `tests/test_urls_do_repo.py` | a URL que manda baixar o projeto aponta para ele |
| `W1-W2` | `tests/test_ws.py` | o `scripts/ws.sh` acha o `.env` |
| `TK1-TK8` | `tests/moodle/test_token_python.py` | o obtentor do token em Python (`usp_mcp/token/`): o entry point `usp-mcp-token` sobe, o módulo roda sem bash, o invólucro `token.sh` repassa código de saída, o token fica fora do argv do `curl` |
| `WIN1-WIN7` | `tests/moodle/test_token_windows.py` | o `token.sh` em Windows: leitor de clipboard, lançador e Python escolhidos com dublês no PATH |

Três coisas que a tabela revela e que valem ser ditas em voz alta, porque quem
cita uma sigla numa PR precisa saber:

1. **A letra sozinha não identifica o teste.** `A`, `D`, `E`, `J`, `P` e `T` são
   usadas por duas ou mais famílias, e `T` é usada por três: Jupiter, Moodle e o
   teste do token. Pior, as faixas de `T` do Jupiter e do Moodle se sobrepõem
   (`T68` e `T80-T82` existem nos dois). Ao citar, diga o arquivo ou o sistema
   junto: "T80 do Jupiter", não "T80".
2. **Número repetido dentro da mesma família existe.** `R42-R44` estão em
   `test_bandejao.py` e em `test_live.py`. O `pytest` não se importa, porque o
   identificador dele é o caminho mais o nome inteiro da função; quem se importa
   é a pessoa que leu a sigla numa PR.
3. **Nem todo teste tem sigla.** `tests/moodle/test_o_que_vence.py`,
   `test_projecao.py`, `test_higienizacao.py`, `test_token_decode.py` e
   `test_anexos_de_entrega.py` nomeiam a propriedade sem prefixo. Isso é
   escolha, não esquecimento: eles são citados pelo nome do arquivo.

**`BUG-N` não é família de teste.** É defeito medido, citado em `tests/git.py` e
`tests/test_git.py`. O número não está definido em lugar nenhum do repositório,
e `BUG-2` é o único que aparece: o defeito que as duas citações descrevem é o dos
12 testes que reprovavam pela causa errada, desenhado em
`docs/superpowers/specs/2026-09-10-check-ignore-em-caminho-nfd-design.md` e
fechado na PR #24. Defeito novo vai para `docs/decisions/BACKLOG-correcoes.md`,
que numera por data e não por sigla; não invente um `BUG-3`.

## 4. Antes de cada commit

```bash
./scripts/gate.sh
```

Três checagens, na ordem em que a mais barata que pode reprovar vem antes:

1. **Nenhum segredo do `.env` em arquivo rastreado** (Invariante 3). Primeiro porque é
   a única falha do gate que é irreversível — commit empurrado com segredo não se
   desfaz apagando o commit. Imprime o NOME da variável e o arquivo, nunca o valor.
   `RUCARD_HASH` no `.env.example` e no `SPEC1.md` é isento **por par**, não por
   variável: a mesma hash em qualquer outro arquivo reprova.
2. **`fixtures/moodle/raw/` segue gitignorada** (§3.3).
3. **A suíte offline**, incluindo a camada `handshake` — que sobe cada servidor como
   processo e aperta a mão com ele. Ela é offline de verdade: `initialize` e `tools/list`
   não passam por `chamar_ferramenta`, que é onde mora qualquer credencial. Custa ~6 s
   (um processo por servidor, escopo de sessão) e é o que impede o furo que ficou três
   vezes neste backlog — `main()` quebrado com a suíte verde.

   A camada `live` NÃO entra: precisa de rede e do token pessoal, e um gate que depende da
   USP estar de pé reprova commit por motivo errado.

O gate foi verificado sabotando cada checagem uma a uma — as três reprovam quando
devem (§9, 31/08/2026). A primeira versão dele passava sem ter verificado nada, porque
procurava o `.env` só no diretório atual e um worktree não tem o dele; hoje usa
`usp_mcp.env.achar_env` e **reprova** se não achar `.env` nenhum, em vez de reportar OK.

**Nenhum script procura o `.env` com `[ -f .env ]`** — a porta é a mesma,
`usp_mcp.env.achar_env`. A regra é frase e não conserto porque o defeito apareceu
três vezes: no gate, no `token.sh`/`fix-token.sh` e no `ws.sh` (§9, 12/09/2026). O
estrago dele não é falhar — é apontar a cura errada, mandando "copie `.env.example`"
para quem já tem o `.env` preenchido no checkout principal.

**Um teste que falha por erro de coleta, erro de setup ou fixture ausente não está
vermelho, está quebrado** — conserte antes de commitar. Os três casos que já morderam:
módulo ausente aborta a coleta inteira e some com os verdes; construir o objeto sob teste
numa fixture do pytest transforma `FAILED` em `ERROR`; e a fixture que sobe o servidor no
handshake fazia o mesmo com o caso mais importante da suíte (o servidor não sobe) — hoje
ela **guarda** o diagnóstico e quem reprova é o teste.

**Sabotagem se faz sobre árvore limpa.** Verificar um teste quebrando de propósito o que
ele protege é a prática deste repo (o gate, o handshake). Faça `git add` antes: o
`git checkout` que desfaz a sabotagem desfaz junto qualquer conserto não estagiado — e o
vermelho que sobra parece do teste, não da restauração (§9, 31/08/2026).

O gate não substitui a Definição de Pronto do `CLAUDE.md` §5 — ele cobre "nenhum
segredo entrou", e o dado registrado e o achado colateral continuam sendo humanos.

Mensagem de commit: `feat|fix|chore|docs|test(escopo): descrição`.

## 5. Fluxo de merge — `main` é a referência

| | Mudança direta | Trabalho faseado |
|---|---|---|
| Branch | `fix/…`/`feat/…` curta, saindo da `main` | 1 guarda-chuva `feat/<tema>-vN` + N branches de etapa saindo DELA |
| Destino do PR | `--base main` | Etapas: `--base <guarda-chuva>`. Só o PR final: `--base main` |

**A regra de ouro do faseado:** a `main` só aparece **uma vez**, no PR final.
Nunca force-push na `main`.

## 6. Verificação honesta

**Nunca afrouxe uma verificação para passar** — se o gate falha, o problema é o
código ou o dado. Uma verificação que não pode falhar não verifica nada.

O análogo desta regra na fase de descoberta: se uma questão do §4 do `SPEC1.md`
ainda não tem dado, ela continua aberta. Fechá-la por conveniência é afrouxar o
gate do projeto inteiro — e o Anexo A (§7) existe justamente como registro de uma
vez em que a tentação apareceu.
