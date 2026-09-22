"""P1-P6: o `pyproject.toml` promete um pacote instalável — e o entry point sobe.

O B1 do ROADMAP trocou "instalar é `git clone` + venv" por "instalar é
`pip install`". A promessa toda cabe em três linhas de `[project.scripts]`, e é
exatamente o tipo de promessa que passa despercebida quando quebra: uma string
errada ali não falha na importação, não falha na coleta e não falha no gate —
falha na máquina de quem instalou, na primeira vez, com o servidor não subindo.

**Verde na suíte não é verde no que ela não alcança** (item 11 do `CLAUDE.md`),
e aqui isso tem forma conhecida: este projeto já teve um `main()` escrito contra
a API antiga do SDK com 99/99 testes passando. A casca stdio só é verificada por
processo real, e é por isso que P6 existe e é o teste que importa desta bateria —
os cinco acima dele leem arquivo, P6 **instala, sobe e aperta a mão**.

A divisão do trabalho, para ninguém achar que um cobre o outro:

| | o que olha | custa |
|---|---|---|
| P1 | a tabela de scripts contra o glob `usp_mcp/*/server.py` | um `read_text` |
| P2 | runtime é só `mcp`; `pytest` não entra; bate com o `requirements.txt` | um `read_text` |
| P3 | cada alvo de entry point RESOLVE — módulo importável, `main` chamável | um import |
| P4 | o nome do comando é o `serverInfo.name` (L2 trava o outro lado) | nada |
| P5 | a `version` do pacote é a que o `initialize` anuncia | um `ast.parse` |
| P6 | o comando INSTALADO sobe o servidor certo, de outro cwd | um processo |
| P7 | o User-Agent que vai para a USP diz a versão do pacote | um import |

Nada aqui toca a rede da USP nem lê credencial: P6 para no `initialize`, como o
handshake e como L1/L2 — nos três servidores o cliente da API só é construído
dentro de `chamar_ferramenta`.

Sem marcador, como `tests/test_documentacao.py`: não é allowlist (`politica`)
nem forma contra fixture (`contrato`). P6 é `handshake` porque sobe processo e
precisa do SDK.
"""
from __future__ import annotations

import ast
import pathlib
import sysconfig
import tomllib

import pytest

from tests.handshake.conftest import (
    RAIZ,
    ClienteStdio,
    com_sdk,
    descobrir_servidores,
    sistema_de,
)

PYPROJECT = RAIZ / "pyproject.toml"

# Descoberta, nunca lista escrita à mão — a mesma razão de H9 e L2. É esta linha
# que faz P1 reprovar no dia em que um quarto sistema nascer sem o quarto entry
# point: a lista à mão do `pyproject.toml` continua sendo lista à mão, mas passa
# a ser comparada com o disco em vez de envelhecer calada.
SISTEMAS = [sistema_de(m) for m in descobrir_servidores()]

# Onde o `pip install` DESTE ambiente põe os console scripts. Perguntar por
# `shutil.which` no PATH acharia o comando de outro venv e faria P6 testar a
# instalação errada — verde honesto sobre o pacote errado ainda é falso-verde.
#
# E `sysconfig`, não `Path(sys.executable).parent`: o `.venv/bin/python` é um
# SYMLINK para o interpretador do sistema, então `.resolve()` sai do venv e
# aponta para um `bin/` que nunca teve os comandos. Custou um `sss` no primeiro
# `pytest` deste arquivo — P6 pulando em silêncio dentro do ambiente onde ele é
# o teste que mais importa. Ficou barulhento porque o skip diz o motivo; fosse
# um `if` calado, teria virado decoração no gate.
BIN = pathlib.Path(sysconfig.get_path("scripts"))

MOTIVO_SEM_INSTALACAO = (
    "o pacote não está instalado NESTE ambiente, então não há console script "
    "para exercitar. Rode `.venv/bin/python -m pip install -e \".[dev]\"` na raiz "
    "do checkout. Este skip NÃO é o caso normal: com o README de hoje seguido de "
    "cima para baixo, o entry point existe e P6 roda no gate."
)


def _pyproject() -> dict:
    assert PYPROJECT.is_file(), (
        f"{PYPROJECT} não existe. Sem ele o projeto volta a ser `git clone` + "
        "venv, que é o que o B1 do ROADMAP fechou."
    )
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _scripts() -> dict[str, str]:
    tabela = _pyproject()["project"].get("scripts")
    assert tabela, (
        "o `pyproject.toml` não declara `[project.scripts]`. Sem entry point o "
        "pacote é instalável e inútil: instalar passa a pôr um módulo no "
        "site-packages sem dar comando nenhum a quem instalou."
    )
    return tabela


# ------------------------------------------------- P1: a tabela contra o disco


# Os comandos que NÃO são servidores. Lista fechada e à mão, de propósito: um
# nome novo aqui exige que alguém escreva no `pyproject.toml` por que ele existe,
# em vez de a tabela crescer calada. Hoje é um só — o obtentor da chave do
# e-Disciplinas, portado de bash para Python em 18/09/2026 para o Windows não
# precisar do Git Bash (`usp_mcp/token/`).
FERRAMENTAS = {"usp-mcp-token": "usp_mcp.token.cli:main"}


def test_p1_ha_um_entry_point_por_servidor_descoberto():
    scripts = _scripts()
    esperado = {
        f"usp-mcp-{sistema}": f"usp_mcp.{sistema}.server:main" for sistema in SISTEMAS
    }
    servidores = {nome: alvo for nome, alvo in scripts.items() if nome not in FERRAMENTAS}

    assert servidores == esperado, (
        "a tabela `[project.scripts]` divergiu de `usp_mcp/*/server.py`.\n"
        f"  declarado: {servidores}\n"
        f"  no disco : {esperado}\n"
        "Foi a decisão de três entry points que criou esta dívida (está escrita "
        "no `pyproject.toml`), e é este teste que a cobra: um quarto sistema sem "
        "o quarto comando nasceria instalável e inalcançável. Um comando que NÃO "
        "é servidor entra em FERRAMENTAS, neste arquivo, com o porquê no pyproject."
    )
    ferramentas = {nome: alvo for nome, alvo in scripts.items() if nome in FERRAMENTAS}
    assert ferramentas == FERRAMENTAS, (
        f"as ferramentas declaradas são {ferramentas}; este teste conhece {FERRAMENTAS}. "
        "Os dois lados têm de andar juntos: o `pyproject.toml` diz o que existe, e "
        "esta lista diz que alguém olhou."
    )


def test_p1b_o_entry_point_da_ferramenta_resolve_e_nao_exige_o_sdk():
    """O `usp-mcp-token` é o comando que uma pessoa roda ANTES de o servidor
    funcionar, para obter a credencial. Ele não pode depender do SDK do MCP: a
    instalação da chave falharia por um motivo que não é dela.

    Num processo LIMPO, e não neste: `tests/handshake/conftest.py` já pode ter
    importado `mcp` aqui, e `"mcp" in sys.modules` mediria o vazio.
    """
    import subprocess
    import sys

    for _nome, alvo in FERRAMENTAS.items():
        caminho, _, atributo = alvo.partition(":")
        r = subprocess.run(
            [
                sys.executable, "-c",
                f"import importlib, sys; m = importlib.import_module({caminho!r}); "
                f"assert callable(getattr(m, {atributo!r}, None)), 'nao resolve'; "
                "print('mcp' in sys.modules)",
            ],
            capture_output=True, text=True, cwd=RAIZ, timeout=60,
        )
        assert r.returncode == 0, f"`{alvo}` não resolve:\n{r.stderr}"
        assert r.stdout.strip() == "False", f"importar `{caminho}` puxou o SDK do MCP"


# ------------------------------------------- P2: runtime é só o SDK, não o pytest


def test_p2_o_runtime_declara_so_o_mcp_e_nunca_o_pytest():
    projeto = _pyproject()["project"]
    runtime = projeto.get("dependencies", [])

    # A asserção literal, e não "pytest não aparece": um `mcp` que virasse
    # `mcp[cli]` ou ganhasse um vizinho passaria num teste frouxo, e o núcleo
    # deste projeto é stdlib pura por decisão registrada (§9, 31/08/2026).
    assert runtime == ["mcp>=2,<3"], (
        f"as dependências de runtime são {runtime}. O contrato é `mcp>=2,<3` e "
        "nada mais: o núcleo dos três sistemas é stdlib pura, e é por isso que o "
        "import do SDK mora dentro de `main()`."
    )

    # Dito duas vezes de propósito. A frouxa acima pega a lista inteira mudando;
    # esta pega o erro ESPECÍFICO que o B1 convida — copiar o
    # `requirements-dev.txt` para dentro do runtime na pressa de fazer a suíte
    # instalar junto.
    nomes = " ".join(runtime).lower()
    assert "pytest" not in nomes, (
        "`pytest` entrou nas dependências de RUNTIME. Ele é de desenvolvimento: "
        "quem instala este pacote quer subir um servidor stdio, não rodar a "
        "suíte deste repositório. O lugar dele é `[project.optional-dependencies] dev`."
    )

    dev = _pyproject()["project"].get("optional-dependencies", {}).get("dev", [])
    assert any("pytest" in item for item in dev), (
        f"o extra `dev` é {dev} e não traz `pytest`. Sem ele "
        '`pip install -e ".[dev]"` deixa de ser o comando único que o README '
        "promete, e volta a ser dois `-r`."
    )

    # `requirements.txt` não some e não pode divergir: os três `main()` mandam
    # `pip install -r requirements.txt` quando o SDK falta, e há teste sobre essa
    # frase. Duas declarações da mesma dependência em dois arquivos é exatamente
    # a forma que o §9 de 12/09 registra como cara — então ela fica travada aqui.
    declarado_no_txt = [
        linha.strip()
        for linha in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    assert declarado_no_txt == runtime, (
        f"`requirements.txt` declara {declarado_no_txt} e o `pyproject.toml` "
        f"declara {runtime}. São dois arquivos dizendo a mesma coisa; quando "
        "divergem, quem instalou por um caminho roda contra outra versão do SDK "
        "do que quem instalou pelo outro, e o sintoma aparece no fio."
    )


# ---------------------------------------------- P3: o alvo do entry point RESOLVE


@pytest.mark.parametrize("sistema", SISTEMAS)
def test_p3_cada_alvo_de_entry_point_e_importavel_e_chamavel(sistema):
    import importlib

    alvo = _scripts()[f"usp-mcp-{sistema}"]
    caminho, _, atributo = alvo.partition(":")

    # Importar aqui é seguro e é o ponto: o import do SDK mora DENTRO de
    # `main()`, então o módulo carrega mesmo num ambiente sem `mcp`. Se um dia
    # alguém subir esse import para o topo, este teste é um dos que acusa.
    modulo = importlib.import_module(caminho)
    funcao = getattr(modulo, atributo, None)

    assert callable(funcao), (
        f"`{alvo}` não resolve: `{caminho}` não expõe `{atributo}` chamável. "
        "P1 só compara strings — uma string bem-formada apontando para o nada "
        "passa lá e falha na máquina de quem instalou."
    )


# ------------------------------------- P4: o comando tem o nome que o servidor diz


@pytest.mark.parametrize("sistema", SISTEMAS)
def test_p4_o_nome_do_comando_e_o_nome_que_o_servidor_anuncia(sistema):
    # Metade de um par. L2 assere que `serverInfo["name"] == f"usp-mcp-{sistema}"`
    # contra o processo vivo; aqui se assere a MESMA fórmula do lado do pacote.
    # Juntos, os dois dizem que a palavra na config do cliente e a palavra no
    # handshake são a mesma — sem este teste precisar subir processo nenhum.
    assert f"usp-mcp-{sistema}" in _scripts(), (
        f"não há comando `usp-mcp-{sistema}`. O nome não é livre: é o mesmo "
        "`serverInfo.name` que o servidor responde no `initialize` (L2), e essa "
        "igualdade é o que faz a config do cliente e o log do handshake falarem "
        "a mesma palavra."
    )


# ------------------------------------------- P5: uma versão só, nos dois lugares


def _versao_anunciada(sistema: str) -> str:
    """A `version=` do `MCPServer(...)` do `main()` daquele servidor, por AST.

    Por AST e não por import: o valor só nasce dentro de `main()`, que exige o
    SDK e sobe o servidor de verdade. Por AST e não por regex: `version=` aparece
    mais de uma vez no arquivo (o `--auto-verificar` constrói um servidor-sonda
    com `version="0.0.0"`), e casar a linha errada daria um teste que reprova o
    número certo.
    """
    fonte = (RAIZ / "usp_mcp" / sistema / "server.py").read_text(encoding="utf-8")
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.Call):
            continue
        argumentos = {
            kw.arg: kw.value for kw in no.keywords if isinstance(kw.value, ast.Constant)
        }
        nome = argumentos.get("name")
        if nome is not None and nome.value == f"usp-mcp-{sistema}":
            versao = argumentos.get("version")
            assert versao is not None, (
                f"o `MCPServer(name='usp-mcp-{sistema}')` perdeu o `version=`. "
                "O `initialize` passaria a anunciar o default do SDK, e o número "
                "do pacote deixaria de significar alguma coisa para quem reporta bug."
            )
            return versao.value
    raise AssertionError(
        f"não achei `MCPServer(name='usp-mcp-{sistema}', version=...)` em "
        f"usp_mcp/{sistema}/server.py. Se a construção mudou de forma, este "
        "teste passou a medir o vazio — conserte-o em vez de apagá-lo."
    )


@pytest.mark.parametrize("sistema", SISTEMAS)
def test_p5_a_versao_do_pacote_e_a_que_o_initialize_anuncia(sistema):
    do_pacote = _pyproject()["project"]["version"]
    do_servidor = _versao_anunciada(sistema)

    assert do_pacote == do_servidor, (
        f"o pacote diz {do_pacote!r} e `usp-mcp-{sistema}` anuncia "
        f"{do_servidor!r} no handshake. Duas verdades sobre o mesmo processo: "
        "quem reportar problema citando a versão instalada vai descrever um "
        "servidor que não é o que está rodando."
    )


# ------------------------------- P6: o comando instalado sobe, de outro cwd, e fala


def _comando(sistema: str) -> pathlib.Path:
    return BIN / f"usp-mcp-{sistema}"


@pytest.mark.handshake
@com_sdk
@pytest.mark.skipif(
    not (BIN / f"usp-mcp-{SISTEMAS[0]}").exists() if SISTEMAS else True,
    reason=MOTIVO_SEM_INSTALACAO,
)
@pytest.mark.parametrize("sistema", SISTEMAS)
def test_p6_o_entry_point_instalado_sobe_o_servidor_certo(sistema, tmp_path):
    comando = _comando(sistema)
    assert comando.exists(), (
        f"`usp-mcp-{SISTEMAS[0]}` existe em {BIN} e `{comando.name}` não. "
        "Uma instalação pela metade é pior que nenhuma: o cliente configurado "
        "para o servidor que faltou falha com 'command not found' e o usuário "
        "conclui que o projeto não funciona."
    )

    # `cwd=tmp_path` é a asserção de verdade, igual a L1: o ponto do pacote é
    # rodar SEM checkout na frente. Um entry point que só suba com o cwd na raiz
    # não resolve nada que o `servidor.sh` já não resolvesse.
    with ClienteStdio(
        f"usp_mcp.{sistema}.server", comando=[str(comando)], cwd=tmp_path
    ) as cliente:
        info = cliente.apertar_mao()
        assert info["serverInfo"]["name"] == f"usp-mcp-{sistema}", (
            f"`{comando.name}` subiu {info['serverInfo']['name']!r}. O entry "
            "point aponta para o módulo errado — é o erro que P1 não pega, "
            "porque lá as duas strings estão bem-formadas."
        )
        assert cliente.vivo()


# ------------------------------- P7: o que o projeto diz sobre si mesmo do lado de lá


def test_p7_o_user_agent_diz_a_versao_do_pacote():
    """P7 — a versão viajava copiada à mão, e envelheceu calada.

    Até 17/09/2026 os dois clientes traziam o literal `usp-mcp/0.1` no
    User-Agent, e o pacote foi para `1.0.0` em 15/09 sem que nada reclamasse:
    esse número não quebra chamada nenhuma e a USP não o lê, então nenhum teste
    tinha por que olhar. É a mesma família do `Castro1` de 14/09 — defeito que
    só aparece na máquina de quem está do outro lado.

    P5 já trava a versão contra o que o `initialize` anuncia. P7 trava contra o
    que sai no fio, que é o único lugar em que uma pessoa de fora da USP pode
    nos identificar.
    """
    from usp_mcp import AGENTE
    from usp_mcp.jupiter.cliente import AGENTE as do_jupiter
    from usp_mcp.rucard.cliente import AGENTE as do_rucard

    do_pacote = _pyproject()["project"]["version"]

    assert AGENTE.startswith(f"usp-mcp/{do_pacote} "), (
        f"o User-Agent é {AGENTE!r} e o pacote diz {do_pacote!r}. Quem "
        "administra o sistema do outro lado lê essa string para saber quem "
        "está batendo, e ela está descrevendo outra versão."
    )
    assert "0+sem-instalacao" not in AGENTE, (
        "o agente caiu no valor de fora-de-instalação. Ele existe para checkout "
        "solto; num ambiente com `pip install -e` presente, ele significa que a "
        "metadata do pacote não foi encontrada — e P7 mediria o vazio."
    )
    assert do_jupiter == do_rucard == AGENTE, (
        "os clientes deixaram de compartilhar o agente do pacote. Dois literais "
        "iguais em arquivos diferentes divergem: foi exatamente assim que a "
        "versão ficou em 0.1."
    )
