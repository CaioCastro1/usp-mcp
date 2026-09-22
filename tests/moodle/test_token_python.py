"""TK1-TK8: o obtentor do token em Python — o caminho que nao passa por bash.

Em 18/09/2026 o `scripts/token.sh` (875 linhas de bash) foi PORTADO para
`usp_mcp/token/cli.py`, e o script virou um involucro de `python -m
usp_mcp.token`. O motivo e o Windows: la nao ha bash, e a pessoa tinha de
instalar e abrir o Git Bash so para este passo, enquanto todo o resto da
instalacao e PowerShell. Agora o pacote instala `usp-mcp-token` (em Windows,
`.venv\\Scripts\\usp-mcp-token.exe`), que e o mesmo programa.

Os testes que ja exercitavam o script (`test_token_decode.py`,
`test_token_navegador.py`, `test_token_windows.py`) continuam exercitando-o
atraves do involucro, sem mudanca de asseracao — sao eles que provam que o
porte nao mudou o comportamento. O que ELES nao alcancam, e estes cobrem, e o
que e novo:

  TK1  o entry point esta em `[project.scripts]` e o comando INSTALADO sobe de
       outra pasta e responde `--ajuda` com o cabecalho, sem tocar .env nenhum;
  TK2  o modulo roda SEM bash — `python -m usp_mcp.token` na raiz falsa —, e faz
       as mesmas coisas que o involucro faz: recusa a URL de ida sem tocar o
       .env, e abre/guarda o passaporte/sai 3 quando nao ha payload. E o caminho
       do Windows, menos o `.exe`;
  TK3  o involucro repassa argumentos e codigo de saida: opcao desconhecida sai
       2 pela mensagem do Python, `--ajuda` sai 0 com o mesmo texto;
  TK4  o token nao passa pelo argv do curl NEM no Python: o argv que o dube
       recebeu nao tem `wstoken`, tem `-K`, e o stdin dele tem o token (a
       regra 11 do CLAUDE.md, aplicada ao processo que de fato roda);
  TK5  a regra do formato mora em UM lugar: a casca `scripts/_decodificar_token.py`
       expoe os mesmos objetos de `usp_mcp.token.decodificar`, e o `fix-token.sh`
       continua importando dela (T-tok-10 a T-tok-14 ja rodam o script);
  TK6  `.env` vence o ambiente, como o `. "$ENV_FILE"` do bash: um MOODLE_URL
       herdado do ambiente de quem roda nao substitui o do arquivo;
  TK7  o involucro em bash e FINO: nao decide nada alem de qual Python — nenhum
       dos sete passos, nenhuma mensagem para a pessoa, nenhuma leitura de
       clipboard sobrou nele;
  TK8  o `.env` gravado nao carrega `\\r`, mesmo quando o payload chegou pelo
       stdin com CRLF, que e como o `Get-Clipboard | usp-mcp-token` do
       PowerShell entrega.

Nenhum token real entra aqui, nada toca a rede, nada le o clipboard de verdade.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
import sysconfig

import pytest

from tests.moodle.conftest import RAIZ
from tests.moodle.test_token_decode import (  # noqa: F401 — as fixtures entram pelo namespace
    PRIVATE,
    SITEID,
    URL_DE_IDA,
    WSTOKEN,
    clipboard_dublado,
    navegador_dublado,
    payload,
    raiz_falsa,
    raiz_token,
    token_sh,
)
from tests.moodle.test_token_navegador import (
    JSON_OK,
    SAIDA_AGUARDANDO,
    aberturas,
    arquivo_passaporte,
    ler_passaporte,
    passaporte_da_url,
    payload_para,
)

pytestmark = pytest.mark.politica

# Onde o `pip install -e` DESTE ambiente pos os console scripts (mesmo motivo do
# `BIN` de tests/test_pacote.py: `shutil.which` acharia o de outro venv).
BIN = pathlib.Path(sysconfig.get_path("scripts"))
COMANDO = BIN / "usp-mcp-token"


def sem_bash(raiz, colado, path=None, env=None, args=()):
    """`python -m usp_mcp.token` na raiz falsa — o que o involucro faz, sem ele.

    Mesmo ambiente que `token_sh`: `open` e `pbpaste` dublados no PATH, vigia de
    1 s, sem SSH. O PYTHONPATH aponta para a raiz falsa pelo mesmo motivo que o
    involucro o poe: e o pacote DAQUELA raiz que tem de subir, com o `achar_env`
    apontando para o `.env` de mentira.
    """
    ambiente = {k: v for k, v in os.environ.items() if k not in ("SSH_CONNECTION", "SSH_TTY")}
    if path is not None:
        ambiente["PATH"] = path
    ambiente["PATH"] = f"{clipboard_dublado(raiz)}:{navegador_dublado(raiz)}:{ambiente.get('PATH', '')}"
    ambiente["PYTHONPATH"] = str(raiz)
    ambiente["USP_MCP_VIGIA_SEGUNDOS"] = "1"
    if env:
        ambiente.update(env)
    return subprocess.run(
        [sys.executable, "-m", "usp_mcp.token", *args],
        input=colado,
        capture_output=True,
        text=True,
        cwd=raiz,
        env=ambiente,
        timeout=120,
    )


def curl_que_grava_argv_e_stdin(raiz) -> str:
    """Um `curl` dube que guarda o argv (separado por NUL) e o stdin, e devolve
    o PATH. E o `ps aux` do teste, como T4 de test_token_fora_do_argv.py."""
    binario = raiz / "bin-curl"
    binario.mkdir(exist_ok=True)
    falso = binario / "curl"
    falso.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\0' \"$@\" > '{raiz / 'curl.argv'}'\n"
        f"cat > '{raiz / 'curl.stdin'}'\n"
        f"cat <<'JSON'\n{JSON_OK}\nJSON\n",
        encoding="utf-8",
    )
    falso.chmod(0o755)
    return f"{binario}:{os.environ['PATH']}"


# ------------------------------------------------- TK1: o comando instalado


def test_tk1_o_entry_point_esta_declarado_e_aponta_para_o_cli():
    import tomllib

    scripts = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts.get("usp-mcp-token") == "usp_mcp.token.cli:main", (
        f"`[project.scripts]` e {scripts}; falta `usp-mcp-token = \"usp_mcp.token.cli:main\"`. "
        "Sem ele o Windows volta a precisar do Git Bash para obter a chave."
    )


@pytest.mark.skipif(
    not COMANDO.exists(),
    reason=(
        "o pacote nao esta instalado NESTE ambiente, entao nao ha `usp-mcp-token` "
        "para exercitar. Rode `.venv/bin/python -m pip install -e \".[dev]\"` na "
        "raiz do checkout — e o que registra o comando novo em .venv/bin/."
    ),
)
def test_tk1b_o_comando_instalado_sobe_de_outra_pasta_e_responde_ajuda(tmp_path):
    """`cwd=tmp_path` e a asseracao de verdade, como P6: em Windows a pessoa roda
    o `.exe` de onde estiver. `--ajuda` sai ANTES do passo 1, entao nada de .env
    e tocado — e o `tmp_path` sem .env nenhum e o que prova isso."""
    r = subprocess.run([str(COMANDO), "--ajuda"], capture_output=True, text=True, cwd=tmp_path, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "Obtem o MOODLE_TOKEN e grava no .env" in r.stdout
    assert "usp-mcp-token" in r.stdout, "a ajuda nao cita o comando sem bash"
    assert "Sete passos" in r.stdout
    assert not (tmp_path / ".env").exists()
    assert r.stderr == ""


# ------------------------------------------------------ TK2: roda sem bash


def test_tk2_sem_bash_a_url_de_ida_e_recusada_sem_tocar_o_env(raiz_token):
    """O mesmo que T-tok-20 afirma pelo involucro, agora pelo modulo direto."""
    antes = (raiz_token / ".env").read_text(encoding="utf-8")
    r = sem_bash(raiz_token, URL_DE_IDA)
    saida = r.stdout + r.stderr
    assert r.returncode == 1, saida
    assert "1/7" in saida and "2/7" in saida and "3/7" in saida
    assert "4/7" not in saida, "passou da conferencia"
    assert "URL de IDA" in saida
    assert (raiz_token / ".env").read_text(encoding="utf-8") == antes
    assert "passport=1234567890" not in saida, "ecoou o valor colado"


def test_tk2b_sem_bash_a_abertura_abre_guarda_o_passaporte_e_sai_3(raiz_token):
    """O mesmo que N1 afirma pelo involucro: o argv do `open`, o passaporte
    guardado e o codigo 3 — agora sem processo bash nenhum na frente."""
    r = sem_bash(raiz_token, "")
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    ab = aberturas(raiz_token)
    assert len(ab) == 1, ab
    p_arq, _ = ler_passaporte(raiz_token)
    assert passaporte_da_url(ab[0]) == p_arq
    assert "AVISO, antes de comecar: vou LER o clipboard" in saida
    assert "Saida 3 = aguardando" in saida
    assert "Get-Clipboard | usp-mcp-token" in saida, "a saida 3 nao ensina o comando do PowerShell"


def test_tk2c_sem_bash_a_entrega_pelo_stdin_grava(raiz_token):
    """N5, sem bash: `Get-Clipboard | usp-mcp-token` e isto."""
    r = sem_bash(raiz_token, payload_para("1234567890"), path=curl_que_grava_argv_e_stdin(raiz_token))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "li do stdin." in saida
    assert "7/7" in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert aberturas(raiz_token) == []
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"


# ------------------------------------------------ TK3: o involucro repassa


def test_tk3_o_involucro_repassa_argumentos_e_codigo_de_saida(raiz_token):
    pelo_involucro = token_sh(raiz_token, "", args=("--opcao-que-nao-existe",))
    direto = sem_bash(raiz_token, "", args=("--opcao-que-nao-existe",))
    assert pelo_involucro.returncode == direto.returncode == 2
    assert "opcao desconhecida: --opcao-que-nao-existe (use --ajuda)" in pelo_involucro.stderr
    assert pelo_involucro.stderr == direto.stderr
    assert aberturas(raiz_token) == [], "abriu navegador com opcao invalida"


def test_tk3b_o_involucro_e_o_modulo_dao_a_mesma_ajuda(raiz_token):
    pelo_involucro = token_sh(raiz_token, "", args=("--ajuda",))
    direto = sem_bash(raiz_token, "", args=("--ajuda",))
    assert pelo_involucro.returncode == direto.returncode == 0
    assert pelo_involucro.stdout == direto.stdout
    assert "Obtem o MOODLE_TOKEN" in direto.stdout


def test_tk3c_a_saida_3_atravessa_o_involucro(raiz_token):
    """O codigo proprio da abertura (3) e o que um agente le. Um involucro que
    o trocasse por 0 ou 1 quebraria o contrato do fluxo em duas invocacoes."""
    r = token_sh(raiz_token, "")
    assert r.returncode == SAIDA_AGUARDANDO
    assert arquivo_passaporte(raiz_token).exists()


# ------------------------------------------- TK4: o token fora do argv do curl


def test_tk4_o_token_nao_vai_para_o_argv_do_curl_e_vai_pelo_stdin(raiz_token):
    r = sem_bash(raiz_token, payload_para("1234567890"), path=curl_que_grava_argv_e_stdin(raiz_token))
    assert r.returncode == 0, r.stdout + r.stderr
    argv = [a for a in (raiz_token / "curl.argv").read_bytes().decode("utf-8").split("\0") if a]
    entregue = (raiz_token / "curl.stdin").read_text(encoding="utf-8")

    vazados = [a for a in argv if WSTOKEN in a or "wstoken" in a]
    assert not vazados, f"o token foi para o argv do curl: {vazados!r}"
    assert "-K" in argv and "-" in argv, f"o curl foi chamado sem `-K -`: {argv!r}"
    assert f'data-urlencode = "wstoken={WSTOKEN}"' in entregue, "o token nao foi pelo stdin"
    assert "wsfunction=core_webservice_get_site_info" in argv
    assert "moodlewsrestformat=json" in argv


# ---------------------------------------- TK5: a regra do formato em um lugar


def test_tk5_a_casca_de_scripts_expoe_os_objetos_do_pacote():
    """`scripts/_decodificar_token.py` continua existindo (fix-token.sh e
    T-tok-1..9 o usam), mas a regra mora no pacote: os objetos sao os MESMOS."""
    spec = importlib.util.spec_from_file_location(
        "casca_decodificar", RAIZ / "scripts" / "_decodificar_token.py"
    )
    assert spec and spec.loader
    casca = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(casca)

    from usp_mcp.token import decodificar as pacote

    assert casca.decodificar is pacote.decodificar
    assert casca.analisar is pacote.analisar
    assert casca.RE_32HEX is pacote.RE_32HEX
    assert casca.LINK == pacote.LINK
    fonte = (RAIZ / "scripts" / "_decodificar_token.py").read_text(encoding="utf-8")
    assert "def analisar" not in fonte and "b64decode" not in fonte, (
        "a casca voltou a ter a regra do formato: duas copias divergem na "
        "primeira vez que o Moodle mudar de versao"
    )


def test_tk5b_analisar_nao_imprime_e_decodificar_imprime():
    """As duas portas da mesma regra, e o que as separa e quem le a mensagem:
    `analisar` levanta sem tocar o stderr (e o que a vigia usa, em silencio);
    `decodificar` imprime e sai 1 (o contrato que o fix-token.sh importa)."""
    import io
    from contextlib import redirect_stderr

    from usp_mcp.token.decodificar import FormaErrada, analisar, decodificar

    capturado = io.StringIO()
    with redirect_stderr(capturado):
        with pytest.raises(FormaErrada) as e:
            analisar(URL_DE_IDA)
    assert capturado.getvalue() == "", "analisar() escreveu no stderr"
    assert "URL de IDA" in str(e.value)
    assert URL_DE_IDA not in str(e.value), "a mensagem ecoa a entrada"

    capturado = io.StringIO()
    with redirect_stderr(capturado):
        with pytest.raises(SystemExit) as saida:
            decodificar(URL_DE_IDA)
    assert saida.value.code == 1
    assert "URL de IDA" in capturado.getvalue()

    assert analisar(f"moodlemobile://token={payload(SITEID, WSTOKEN, PRIVATE)}") == (SITEID, WSTOKEN, 3)


# ----------------------------------------------- TK6: o .env vence o ambiente


def test_tk6_o_moodle_url_do_env_vence_o_do_ambiente(raiz_token):
    """O bash fazia `set -a; . "$ENV_FILE"`: o arquivo vencia. Um `carregar_env`
    (que faz `setdefault`) aqui inverteria isso e mandaria a pessoa para o
    e-Disciplinas de verdade num teste — ou para o site errado num uso."""
    r = sem_bash(raiz_token, "", env={"MOODLE_URL": "https://outro.invalid"})
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "MOODLE_URL=https://exemplo.invalid" in saida
    assert "outro.invalid" not in saida
    assert "exemplo.invalid" in aberturas(raiz_token)[0]


def test_tk6b_ler_env_e_o_mesmo_parser_que_carregar_env(tmp_path):
    """Uma implementacao para a leitura do `.env`, usada pelos dois lados."""
    from usp_mcp.env import carregar_env, ler_env

    (tmp_path / ".env").write_text(
        "# comentario\nexport A=1\nB = 'dois'\nC=\"tres\"\nSEM_IGUAL\n=vazio\n", encoding="utf-8"
    )
    assert ler_env(tmp_path / ".env") == {"A": "1", "B": "dois", "C": "tres"}
    for chave in ("A", "B", "C"):
        os.environ.pop(chave, None)
    os.environ["A"] = "ja-estava"
    try:
        assert carregar_env(tmp_path) == tmp_path / ".env"
        assert os.environ["A"] == "ja-estava", "carregar_env deixou de ser setdefault"
        assert os.environ["B"] == "dois"
    finally:
        for chave in ("A", "B", "C"):
            os.environ.pop(chave, None)


# --------------------------------------------------- TK7: o involucro e fino


def test_tk7_o_involucro_nao_tem_logica_alem_de_achar_o_python():
    fonte = (RAIZ / "scripts" / "token.sh").read_text(encoding="utf-8")
    codigo = "\n".join(l for l in fonte.splitlines() if l.strip() and not l.lstrip().startswith("#"))
    assert "exec" in codigo and "-m usp_mcp.token" in codigo
    for sobra in ("1/7", "passaporte=", "pbpaste", "Get-Clipboard", "curl", "launch.php", "sleep"):
        assert sobra not in codigo, f"o involucro voltou a ter logica propria: {sobra!r}"
    assert len(codigo.splitlines()) < 25, "o involucro cresceu; a logica e do cli.py"


# ------------------------------------------------------- TK8: CRLF no stdin


def test_tk8_o_crlf_do_powershell_no_stdin_nao_vai_para_o_env(raiz_token):
    """`Get-Clipboard | usp-mcp-token` entrega a linha com `\\r\\n`. O bash ja
    engolia isso porque o decodificador faz `strip()`; aqui se afirma o
    resultado, que e o que importa: 32 hex no `.env`, e nenhum `\\r`."""
    r = sem_bash(raiz_token, payload_para("1234567890") + "\r\n", path=curl_que_grava_argv_e_stdin(raiz_token))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    texto = (raiz_token / ".env").read_text(encoding="utf-8")
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in texto
    assert "\r" not in texto
