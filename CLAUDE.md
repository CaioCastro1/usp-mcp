# CLAUDE.md — usp-mcp

> **Leia isto primeiro.** Este é o cérebro compartilhado das sessões de IA que
> **mantêm** este projeto. É curto de propósito. Para detalhe profundo, siga os
> ponteiros em "Referências". Escreva sempre em português.
>
> **Comece pelo §0:** ele diz se a sua sessão é uma dessas. Se não for, quase
> nada daqui para baixo se aplica a você.
>
> **`SPEC1.md` é a autoridade do projeto.** Este arquivo é o atalho operacional;
> quando os dois divergirem, o `SPEC1.md` está certo e este aqui está desatualizado.

## 0. Quem abriu esta pasta

**O padrão é sessão de USO.** O repositório é público, e quem clona quase sempre
quer perguntar do bandejão e do prazo de aula, não manter o projeto. Nessa
sessão: ajude a **instalar**, a **configurar** e a **usar** — e não proponha
mexer no código, não proponha PR, não decida nada sobre o projeto. Defeito do
projeto vira **issue**, em <https://github.com/CaioCastro1/usp-mcp/issues>, nunca
um commit. Instalar, criar o venv, rodar o `token.sh` e escrever no `.env`
continuam sendo uso: a fronteira é o código versionado e as decisões, não o
teclado.

**Vira sessão de manutenção com uma frase** — "quero mexer no código", "abre uma
PR" — e vale sem a frase quando o disco já respondeu: mais de uma linha em
`git worktree list`, branch local fora da `main`, ou `fixtures/moodle/raw/`
presente. Aí o resto deste arquivo vale inteiro. Quem está numa worktree com
branch aberta não precisa ser perguntado.

**Não tente descobrir o papel por outro caminho.** `.env` preenchido e `origin`
apontando para o repositório do dono são o que **todo** clone tem, inclusive o de
quem só usa. Permissão de push responde à pergunta errada: o papel é da sessão e
não da pessoa, e o dono também pergunta do bandejão.

Isto é um padrão, não uma cerca — contribuição é bem-vinda, e basta pedir. O
detalhe está em `docs/agents/PAPEL-DA-SESSAO.md`.

## 1. O produto (30 segundos)

Ferramentas MCP para responder perguntas reais sobre a vida acadêmica na USP:
cardápio dos bandejões (RUCard), prazos e material do e-Disciplinas (Moodle),
catálogo de disciplinas do JupiterWeb. Projeto não-oficial, sem vínculo com a
universidade, sobre APIs não documentadas descobertas por observação.

**Este arquivo não guarda estado, de propósito.** Nada aqui sobre que fase está
aberta, o que já foi construído ou quantos testes passam. Estado escrito em dois
lugares diverge, e este é o arquivo que toda sessão lê primeiro — a divergência
aqui é a mais cara de todas, porque contamina a sessão inteira antes da primeira
pergunta. Já aconteceu: por dois dias este parágrafo afirmou que não havia
servidor MCP nenhum enquanto dois rodavam (§9, 31/08).

**Onde ver o estado:** a última entrada do `§9 do SPEC1.md` diz o que foi
decidido e com que dado; o `README.md` resume em um parágrafo; o
`docs/decisions/BACKLOG-correcoes.md` lista a dívida aberta; e
`./scripts/gate.sh` responde em segundos o que de fato está verde. Nenhum dos
quatro é este arquivo.

## 2. Onde as coisas moram

| Caminho | O que é |
|---|---|
| `SPEC1.md` | Autoridade: fatos verificados, invariantes, questões abertas, registro de decisões (§9) |
| `usp_mcp/` | Código dos servidores MCP, um pacote por sistema: `politica`, `cliente`, ferramenta, `server` |
| `tests/` | Suíte em três camadas: `politica` e `contrato` offline, `live` atrás de env var |
| `notas/` | Análise por sistema, com custo medido em bytes e tokens |
| `fixtures/rucard/`, `fixtures/jupiter/` | Respostas cruas versionadas (dado público) |
| `fixtures/moodle/raw/` | Cru do Moodle — **fora do git**, tem dado pessoal não higienizado |
| `scripts/` | Chamadores de descoberta (`ws.sh`, `capture.sh`, `userid.sh`, `reduzir.py`), o obtentor de token (`token.sh`, com `fix-token.sh` para normalizar) e o gate (`gate.sh`) |
| `.env` / `.env.example` | Credenciais por env var; `.env` no gitignore |
| `pyproject.toml` | O pacote: um entry point por servidor, runtime só `mcp`, e a justificativa de cada escolha no próprio arquivo |
| `docs/` | Este scaffold: domínios, convenções, handoffs, backlog |

## 3. Comandos

```bash
# Obter o MOODLE_TOKEN e gravar no .env. Manual por padrao (copiar o endereco do
# link da pagina do launch.php) e confirma contra a USP antes de gravar. `--auto`
# tenta capturar o redirect sozinho — funciona contra duble, nao contra a USP.
./scripts/token.sh

# Chamada única ao web service do Moodle (uma função por invocação, escolhida à mão)
./scripts/ws.sh <funcao> [param=valor ...]

# Capturar para fixture imprimindo SÓ a medida (bytes/tokens/forma) — nunca o payload
./scripts/capture.sh <nome> <funcao> [param=valor ...]

# Derivar o userid do token (cacheado em .cache/userid); --refresh força nova chamada
./scripts/userid.sh [--refresh]

# Normalizar MOODLE_TOKEN no .env: aceita a URL crua do fluxo de launch (§8) e grava
# só o wstoken de 32 hex. Idempotente, e nunca imprime o valor (Invariante 3).
./scripts/fix-token.sh

# Medir quanto de cada resposta é resposta e quanto é transporte
python3 scripts/reduzir.py

# Cardápio de um RU (dado público, sem credencial pessoal)
curl -s -X POST https://uspdigital.usp.br/rucard/servicos/menu/6 -d "hash=$RUCARD_HASH"

# Abre worktree PRONTO: fetch, ramifica do origin/main (e não do HEAD local, que
# pode estar meses atrás — §9, 21/09/2026), cria o venv com `-e ".[dev]"` e NÃO
# cria .env. Prefira isto a `git worktree add` na mão.
./scripts/novo-worktree.sh <branch> [caminho]

# O venv é POR DIRETÓRIO e não vem no git: todo worktree novo precisa do seu,
# senão o .mcp.json falha com ENOENT em `.venv/bin/python`. uv cria o mesmo .venv/
# do python3 -m venv, por hardlink. O `-e` instala o pacote apontando para o
# checkout e põe os três entry points em .venv/bin/ — é o que o
# `tests/test_pacote.py` (P6) exige para não pular. O `novo-worktree.sh` acima já
# faz isto; esta linha é para worktree aberto na mão e para clone novo.
uv venv && uv pip install -e ".[dev]"

# O projeto é um PACOTE: um entry point por servidor, que sobe de qualquer pasta e
# sem checkout na frente. Três comandos e não um com argumento — o porquê está no
# `pyproject.toml`, ao lado da tabela `[project.scripts]`.
usp-mcp-rucard   # e usp-mcp-jupiter, usp-mcp-moodle

# Handshake stdio real com TODOS os servidores descobertos (offline; entra no gate)
.venv/bin/python -m pytest tests/handshake

# Este projeto funciona no Moodle de OUTRA faculdade? Uma requisicao, SEM credencial.
# Sai 0 (transporte ok), 1 (servico mobile desligado no site) ou 2 (URL nao e raiz
# de Moodle). Verde aqui NAO promete que as ferramentas respondem bem — ver §4 e §5
# de notas/portabilidade-moodle.md.
./scripts/compatibilidade.sh https://moodle.ggte.unicamp.br

# Gate antes de commit: .env presente, segredo no git, cru ignorado, suíte offline. Não toca a rede.
./scripts/gate.sh

# Rodar TODOS os testes, inclusive a camada que fala com a USP de verdade
USP_MCP_LIVE=1 .venv/bin/python -m pytest

# O que dá para checar do servidor sem tocar a rede nem gastar chamada da conta
.venv/bin/python -m usp_mcp.<sistema>.server --auto-verificar
```

## 4. Regras críticas (não negociáveis)

Os 8 invariantes vivem no **§2 do `SPEC1.md`** e valem mesmo que o dado sugira o
contrário. Os que mordem em toda sessão:

1. **Nunca varra a lista de funções do Moodle** (Regra de Ouro, §3.1). São 447
   funções habilitadas neste token; um sweep passa por `mod_quiz_start_attempt` e
   `mod_assign_submit_for_grading` com a credencial do dono. Uma função por
   invocação, escolhida à mão, com parâmetro real. Cada chamada fica no log da conta.
2. **Allowlist, nunca denylist** (Invariante 2). `tool_mobile_call_external_functions`
   é bloqueio permanente sem flag que libere — ela anula qualquer filtro por nome.
   O campo `type` do Moodle não é fronteira de segurança, e glob não é blindagem.
3. **Read-only por padrão** (Invariante 1), e nunca escrita implícita numa ferramenta
   de leitura. `USP_MCP_ALLOW_WRITES` continua sendo a flag que **não** abre nada,
   nos três servidores, e a lista de bloqueio permanente do §2.2 não é liberada por
   flag nenhuma. A exceção, e é uma só, entrou em 15/09/2026: duas funções de
   `mod_assign` saíram daquela lista para um conjunto próprio, e alcançá-las exige
   `USP_MCP_ENTREGA=1` **e** uma confirmação declarada por chamada. Sem a flag, as
   duas ferramentas que as usam não existem no `tools/list`. O desenho e o que ele
   não protege estão em
   `docs/superpowers/specs/2026-09-15-entrega-com-confirmacao-design.md`.
   Desde 17/09/2026 o servidor **conta em prosa** que essa capacidade existe e
   está desligada — no `instructions` do `initialize` e no fim do `diagnostico`,
   nunca com uma ferramenta a mais na lista. Se a próxima sessão pensar em
   resolver "o assistente não sabe" com um item novo no `tools/list`, leia antes
   `docs/superpowers/specs/2026-09-17-assistente-sabe-o-que-esta-desligado-design.md`:
   a razão de a lista de ferramentas ser o lugar errado está lá.
4. **Nenhum segredo no repositório** (Invariante 3). Nunca leia, imprima ou ecoe o
   valor de `MOODLE_TOKEN`. Fixture do Moodle só entra no git depois da higienização
   do §3.3 — nome, e-mail, `userid`, `fullname` de turma e notas viram valor sintético
   estável, preservando a forma.
5. **Credencial pessoal não sai da máquina do dono** (Invariante 4). Dado autenticado
   só no entrypoint local (stdio). Servidor hospedado não recebe token de ninguém,
   nem "só pra testar".
6. **Erro legível vence silêncio** (Invariante 6) e **sem limite silencioso**
   (Invariante 7). Nunca devolver lista vazia que parece "não tem nada". Se truncou,
   paginou ou amostrou, a saída diz isso. Não engolir erro cru da API.
7. **Não martelar a USP** (Invariante 5). Cache com TTL coerente com a taxa de mudança
   do dado (semana para cardápio, semestre para ementa), não com a frequência das
   perguntas.
8. **Nunca ler uma resposta crua acima de ~200 kB.** `capture.sh` imprime medida, não
   payload, exatamente para isso. `core_enrol_get_users_courses` sozinha já custa
   ~26.200 tokens.
9. **Antes de dizer que a rede da USP não dá, MEÇA** (§1.1). Do sandbox em nuvem
   do Cowork ela realmente não sai (proxy com allowlist), mas do Claude Code na
   máquina do dono ela sai — verificado em 31/08/2026. O que separa uma sessão do
   teste real é a **credencial**, não a rede: o token é pessoal e cada chamada
   fica no log da conta. Por isso a camada `live` fica atrás de `USP_MCP_LIVE=1`,
   e por isso ela é decisão do dono, não limitação de infraestrutura.
10. **Ferramenta não nasce por conveniência.** O critério para uma existir é o §5
    do `SPEC1.md`, e questão aberta do §4 fecha com dado registrado no §9 — não com
    opinião nem com o que a API oferece. O Anexo A (§7) é a lista de ferramentas
    derivada da API: está lá para ser confrontada, não seguida.
11. **Verde na suíte não é verde no que ela não alcança.** Já custou três bugs num
    dia só, um deles um entrypoint que nunca tinha funcionado com a suíte inteira
    verde. Antes de confiar num parâmetro, asserte sobre o parâmetro **enviado**,
    não sobre a saída — o dublê devolve o que o teste mandou.

## 5. Fluxo padrão de uma mudança

Branch curta saindo da `main` → PR → merge. `main` é a referência; nada de
force-push.

Mudança de **conhecimento** (fato novo sobre uma API, questão aberta fechada) vale
tanto quanto mudança de código: entra no `SPEC1.md` — fato no §1, decisão datada no
§9 com o dado que a fechou e o que foi descartado. Análise longa e medição vão para
`notas/`, e `notas/` não edita o `SPEC1.md` por conta própria.

### Definição de Pronto

1. O dado que sustenta a mudança está registrado (§9 do `SPEC1.md` para decisão,
   `notas/` para medição) — não só na janela da conversa.
2. Nenhum segredo nem dado pessoal não higienizado entrou no git.
3. Achado colateral foi para `docs/decisions/BACKLOG-correcoes.md` e a tarefa atual
   seguiu — sem desvio.

## 6. Referências (detalhe profundo)

| Assunto | Onde |
|---|---|
| Papel da sessão: uso × manutenção, e que sinal serve (§0) | `docs/agents/PAPEL-DA-SESSAO.md` |
| Autoridade do projeto: fatos, invariantes, decisões | `SPEC1.md` |
| Domínios do sistema (RUCard, Moodle, Jupiter) | `docs/domains/README.md` |
| Convenções deste repo | `docs/agents/CONVENTIONS.md` |
| Achados colaterais em aberto | `docs/decisions/BACKLOG-correcoes.md` |
| Handoff de sessão exploratória | `docs/handoffs/_TEMPLATE.md` |

---

*Mantenha este arquivo curto e **sem estado**. Se algo aqui ficar grande, mova o
detalhe para `SPEC1.md`/`docs/` e deixe só o ponteiro. Se for a resposta de "em
que pé estamos", não escreva aqui: aqui ela envelhece calada e a próxima sessão
começa com o mapa errado.*
