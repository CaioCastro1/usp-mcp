"""Carrega o `.env` para `os.environ` — o equivalente Python do
`set -a && . ./.env && set +a` da linha 15 do `scripts/ws.sh`.

Isto existe porque nada no lado Python fazia: só os scripts bash sourceavam o
arquivo. O efeito era um erro legível apontando a cura errada — a suíte dizia
"MOODLE_TOKEN está vazio, copie .env.example para .env" para quem já tinha o
`.env` preenchido, porque o valor nunca chegava a `os.environ` (§9, 31/08/2026).

Mora em `usp_mcp/` e não em `tests/` porque os dois lados precisam: a suíte e o
entrypoint stdio do Moodle. Decisão de 31/08/2026 — o `.env` (§8, gitignorado)
continua sendo a única casa do token, e o `.mcp.json` vai para o git sem segredo
nenhum. A alternativa descartada era o token vir do bloco `env` da configuração
do cliente MCP, que duplicaria o segredo num arquivo fácil de commitar por
acidente (Invariante 3).

Parser de stdlib de propósito: `python-dotenv` seria a primeira dependência de
runtime do projeto, e o formato aqui é `CHAVE=valor` com comentário.

**Onde este módulo NÃO procura, e por quê (16/09/2026).** O `.env` é achado a
partir da posição deste arquivo: a raiz do checkout, e dali para cima até o
`.git` de verdade. Isso cobre o checkout, o worktree e a instalação editável
(`pip install -e`), em que `__file__` continua apontando para a árvore. Não
cobre o pacote copiado para `site-packages` por um `pip install git+...`, e
medido em 16/09 era esse o caminho que o README ensinava: `achar_env()` devolvia
None, o bandejão caía em `HashAusente` e o token gravado pelo `token.sh` ficava
num clone que o servidor instalado nunca lia. A cura escolhida foi o README
instalar do jeito que este arquivo já suporta (um clone, o `.venv/` dentro dele,
instalação editável), e não ensinar este módulo a procurar em mais um lugar:

- embutir a `RUCARD_HASH` aqui, com o ambiente sobrepondo, resolveria o bandejão
  sem `.env` nenhum, mas a checagem 1 do gate (`scripts/_gate_segredos.py`)
  reprova o valor em qualquer arquivo rastreado fora do par
  `.env.example`/`SPEC1.md`, e o R8 do RUCard reprova em `usp_mcp/rucard/`. É
  decisão registrada, não esquecimento: o valor é público, e mesmo assim tem
  UMA casa;
- um caminho fixo do usuário (`~/.config/usp-mcp/.env`) ou o pai do venv
  seriam uma segunda resposta para "onde está o `.env`", e três entradas do §9
  (12/09) registram o que custa ter duas respostas para essa pergunta;
- o `MOODLE_TOKEN` no bloco `env` do cliente MCP já foi descartado acima, e
  obrigaria a pessoa a abrir o arquivo e copiar o segredo à mão.
"""
from __future__ import annotations

import os
from pathlib import Path

# usp_mcp/env.py → sobe dois níveis até a raiz do checkout (ou do worktree).
# Numa instalação editável isto continua sendo a árvore clonada; numa cópia em
# site-packages é o próprio site-packages, onde não há `.env` (ver o docstring).
_RAIZ = Path(__file__).resolve().parents[1]


def achar_env(raiz: Path | None = None) -> Path | None:
    """Onde está o `.env`, ou None se não estiver em lugar nenhum.

    O `.env` é gitignorado, então `git worktree add` não o copia e um worktree
    novo não tem o dele — mesma situação do cru do §3.3. Procura na raiz e, se
    não achar, sobe até o checkout que tem o `.git` de verdade (num worktree o
    `.git` é arquivo, não diretório).

    Devolve None em vez de levantar: "não tem `.env`" e "tem `.env` sem a
    chave" pedem mensagens diferentes, e quem chama é que sabe qual dar
    (Invariante 6).
    """
    raiz = raiz if raiz is not None else _RAIZ
    candidatos = [raiz / ".env"]
    for pai in raiz.parents:
        if (pai / ".git").is_dir():
            candidatos.append(pai / ".env")
            break
    for c in candidatos:
        if c.is_file():
            return c
    return None


def ler_env(arquivo: Path) -> dict[str, str]:
    """O que `set -a; . "$arquivo"; set +a` poria no ambiente, como dicionário.

    É o parser que `carregar_env` sempre teve, separado em 18/09/2026 porque o
    `usp_mcp.token` (o porte do `token.sh`) precisa da MESMA leitura com outra
    regra de precedência: o bash sourceava o `.env` e o arquivo vencia o
    ambiente, enquanto `carregar_env` faz `setdefault` e o ambiente vence. Um
    segundo parser dentro do `token` seria a "mesma pergunta com duas
    implementações" que o §9 de 12/09 registra como cara.

    Nenhum valor é impresso, nem em erro (Invariante 3): linha malformada é
    ignorada em silêncio em vez de ecoada.
    """
    valores: dict[str, str] = {}
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        # `export CHAVE=valor` é válido num arquivo feito para ser sourceado.
        chave = chave.removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if chave:
            valores[chave] = valor
    return valores


def carregar_env(raiz: Path | None = None) -> Path | None:
    """Põe o `.env` em `os.environ` e devolve o arquivo usado (ou None).

    `setdefault`, e não atribuição: **quem já está no ambiente ganha**. É o que
    mantém `USP_MCP_LIVE=1 pytest` valendo mesmo se o `.env` disser o
    contrário, o que deixa o bloco `env` de um cliente MCP sobrescrever o
    arquivo, e o que impede este carregador de ligar a camada live por baixo de
    quem não pediu.
    """
    arquivo = achar_env(raiz)
    if arquivo is None:
        return None
    for chave, valor in ler_env(arquivo).items():
        os.environ.setdefault(chave, valor)
    return arquivo
