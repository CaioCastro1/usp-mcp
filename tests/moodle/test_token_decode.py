"""Camada 1 — a decodificação do payload de `launch.php`.

Nenhum token real entra aqui, nem higienizado: o payload é montado no próprio
teste, com um `wstoken` sintético que tem a FORMA de 32 hex e não é credencial
de ninguém. Testar decodificação com token real seria gravar a credencial num
arquivo rastreado (Invariante 3) para verificar um regex.

O que estes testes alcançam é o §6 do desenho de 10/09: a unidade que os dois
scripts compartilham. O que eles NÃO alcançam — abrir navegador, ler clipboard,
escrever no `.env`, falar com a USP — está dito em voz alta no §7 do desenho, e
a regra 11 do `CLAUDE.md` é o motivo de dizer.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys

import pytest

from tests.moodle.conftest import RAIZ

pytestmark = pytest.mark.politica

HELPER = RAIZ / "scripts" / "_decodificar_token.py"

# Sintéticos. A forma é a do §1.3 do SPEC1.md; o conteúdo não abre nada.
SITEID = "0" * 32
WSTOKEN = "ab12cd34" * 4  # 32 hex
PRIVATE = "ffffffffffffffffffffffffffffffff"


def payload(*partes: str) -> str:
    """base64 de `a:::b:::c`, como o Moodle emite."""
    return base64.b64encode(":::".join(partes).encode()).decode()


def decodificar(entrada: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER)],
        input=entrada,
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )


def campos(saida: str) -> dict[str, str]:
    return dict(
        linha.split("=", 1) for linha in saida.strip().splitlines() if "=" in linha
    )


# --------------------------------------------------------------- o caminho bom


def test_extrai_o_wstoken_de_url_completa():
    """T-tok-1 — o que a pessoa copia do DevTools é a URL inteira."""
    r = decodificar(f"moodlemobile://token={payload(SITEID, WSTOKEN, PRIVATE)}")
    assert r.returncode == 0, r.stderr
    assert campos(r.stdout)["wstoken"] == WSTOKEN


def test_extrai_o_wstoken_de_base64_nu():
    """T-tok-2 — quem já sabe o fluxo cola só o base64."""
    r = decodificar(payload(SITEID, WSTOKEN, PRIVATE))
    assert r.returncode == 0, r.stderr
    assert campos(r.stdout)["wstoken"] == WSTOKEN


def test_devolve_o_siteid_para_a_conferencia_do_passaporte():
    """T-tok-3 — o §3.1 do desenho confere md5(wwwroot+passport) contra ele."""
    r = decodificar(payload(SITEID, WSTOKEN, PRIVATE))
    assert campos(r.stdout)["siteid"] == SITEID


def test_tolera_espaco_e_quebra_de_linha_ao_redor():
    """T-tok-4 — clipboard traz sujeira; ela não é erro de forma."""
    r = decodificar(f"  moodlemobile://token={payload(SITEID, WSTOKEN, PRIVATE)}/ \n")
    assert r.returncode == 0, r.stderr
    assert campos(r.stdout)["wstoken"] == WSTOKEN


# ------------------------------------------------------- o privatetoken não sai


def test_o_privatetoken_nao_aparece_na_saida():
    """T-tok-5 — §4 do desenho, e a asserção é sobre a saída, não a intenção.

    `tool_mobile_get_autologin_key` está no bloqueio permanente do §2.2. O
    terceiro campo do payload é o que a habilita: ele é decodificado por força
    do formato e tem de morrer aqui dentro.
    """
    r = decodificar(payload(SITEID, WSTOKEN, PRIVATE))
    assert PRIVATE not in r.stdout
    assert PRIVATE not in r.stderr


def test_a_saida_tem_so_os_campos_declarados():
    """T-tok-6 — um campo novo na saída é um vazamento em potencial."""
    r = decodificar(payload(SITEID, WSTOKEN, PRIVATE))
    assert set(campos(r.stdout)) == {"siteid", "wstoken", "partes"}


# ------------------------------------------------------------ a forma reprovada


@pytest.mark.parametrize(
    "entrada, porque",
    [
        ("não é base64 de jeito nenhum ###", "lixo colado"),
        ("", "nada colado"),
        (base64.b64encode(b"sozinho").decode(), "payload de uma parte"),
        (payload(SITEID, "curto", PRIVATE), "wstoken fora de 32 hex"),
        (payload(SITEID, WSTOKEN.upper(), PRIVATE), "wstoken em maiúscula"),
    ],
)
def test_forma_errada_reprova_com_mensagem(entrada, porque):
    """T-tok-7 — Invariante 6: erro legível, código ≠ 0, nada de stack trace."""
    r = decodificar(entrada)
    assert r.returncode != 0, f"passou com {porque}"
    assert r.stderr.strip(), f"reprovou calado com {porque}"
    assert "Traceback" not in r.stderr, f"cru na cara do usuário com {porque}"
    assert not campos(r.stdout), f"emitiu campo com {porque}"


def test_base64_minusculizado_reprova():
    """T-tok-8 — a armadilha do Chrome do §1.3.

    Com `urlscheme=http` o base64 cai na posição de host e o Chrome normaliza
    host para minúsculas. base64 é sensível a caixa: o resultado é um token
    corrompido com a forma certa. Reprovar é o comportamento correto; gravar
    um token de 32 hex que não autentica é o pior desfecho possível, porque
    parece sucesso.
    """
    bom = payload(SITEID, WSTOKEN, PRIVATE)
    r = decodificar(bom.lower())
    if r.returncode == 0:
        assert campos(r.stdout)["wstoken"] != WSTOKEN, (
            "minusculizar o base64 não deveria devolver o token intacto"
        )
    else:
        assert r.stderr.strip()


def test_nunca_ecoa_a_entrada_inteira_no_erro():
    """T-tok-9 — a entrada É a credencial; diagnóstico é forma, não conteúdo."""
    entrada = payload(SITEID, WSTOKEN, "x")[:-4] + "!!!!"
    r = decodificar(entrada)
    assert entrada not in r.stderr
    assert entrada not in r.stdout


# ---------------------------------------------- o fix-token.sh usa o mesmo helper

# O risco real da extracao do §6 do desenho nao e a decodificacao — e a fiacao:
# o fix-token.sh importa o helper com `sys.path.insert(0, "scripts")`, e um
# import quebrado passaria calado pela suite se ninguem rodasse o script. Estes
# testes rodam o script de verdade, num .env de mentira, num diretorio de
# mentira. Nunca no .env do repo: um teste que escreve no .env do dono e um
# teste que pode gravar credencial de teste na credencial de verdade.


@pytest.fixture
def raiz_falsa(tmp_path):
    """Uma raiz com scripts/, usp_mcp/ e .env proprios — os scripts fazem cd para ca.

    O `usp_mcp/env.py` vem junto de proposito: desde 11/09 o `fix-token.sh`
    localiza o `.env` por `achar_env`, e nao por `./.env`. Um fake sem ele
    testaria um script diferente do que esta no repo.

    `tmp_path` nao tem `.git` em pai nenhum, entao `achar_env` fica na raiz
    falsa e nunca alcanca o `.env` de verdade de quem roda a suite.

    `usp_mcp/token/` vem junto desde 18/09/2026, quando o `token.sh` virou
    involucro de `python -m usp_mcp.token` e a regra do formato saiu de
    `scripts/_decodificar_token.py` para `usp_mcp/token/decodificar.py` (o
    arquivo de `scripts/` ficou como casca que importa de la). A raiz falsa
    copia o que os scripts DEPENDEM, e a dependencia mudou de lugar — sem a
    copia, o involucro nao teria o que chamar e a casca nao teria de onde
    importar. E copia, nao symlink, para que o pacote achado seja o desta raiz
    e o `achar_env` dele continue apontando para o `.env` de mentira.
    """
    (tmp_path / "scripts").mkdir()
    for nome in ("fix-token.sh", "_decodificar_token.py"):
        destino = tmp_path / "scripts" / nome
        destino.write_bytes((RAIZ / "scripts" / nome).read_bytes())
        destino.chmod(0o755)
    (tmp_path / "usp_mcp").mkdir()
    for nome in ("__init__.py", "env.py"):
        (tmp_path / "usp_mcp" / nome).write_bytes((RAIZ / "usp_mcp" / nome).read_bytes())
    copiar_pacote_token(tmp_path)
    return tmp_path


def copiar_pacote_token(raiz) -> None:
    """Copia `usp_mcp/token/*.py` para dentro de `raiz/usp_mcp/`. Ver `raiz_falsa`."""
    destino = raiz / "usp_mcp" / "token"
    destino.mkdir(exist_ok=True)
    for arquivo in sorted((RAIZ / "usp_mcp" / "token").glob("*.py")):
        (destino / arquivo.name).write_bytes(arquivo.read_bytes())


def fix_token(raiz):
    return subprocess.run(
        ["bash", str(raiz / "scripts" / "fix-token.sh")],
        capture_output=True,
        text=True,
        cwd=raiz,
    )


def test_fix_token_normaliza_base64_colado_a_mao(raiz_falsa):
    """T-tok-10 — o caso que o fix-token.sh existe para consertar."""
    env = raiz_falsa / ".env"
    env.write_text(
        f"MOODLE_URL=https://exemplo.invalid\n"
        f"MOODLE_TOKEN=moodlemobile://token={payload(SITEID, WSTOKEN, PRIVATE)}\n"
        f"USP_MCP_ALLOW_WRITES=0\n",
        encoding="utf-8",
    )
    r = fix_token(raiz_falsa)
    assert r.returncode == 0, r.stderr
    depois = env.read_text(encoding="utf-8")
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in depois
    assert PRIVATE not in depois, "o privatetoken chegou ao disco"
    assert "USP_MCP_ALLOW_WRITES=0" in depois, "comeu outra linha do .env"
    assert WSTOKEN not in r.stdout + r.stderr, "ecoou o token"


def test_fix_token_e_idempotente(raiz_falsa):
    """T-tok-11 — rodar duas vezes não estraga o que já estava certo."""
    env = raiz_falsa / ".env"
    env.write_text(f"MOODLE_TOKEN={WSTOKEN}\n", encoding="utf-8")
    r = fix_token(raiz_falsa)
    assert r.returncode == 0, r.stderr
    assert env.read_text(encoding="utf-8") == f"MOODLE_TOKEN={WSTOKEN}\n"
    assert "nada a fazer" in r.stdout


def test_fix_token_com_forma_errada_nao_toca_o_env(raiz_falsa):
    """T-tok-12 — reprovar deixando o .env intacto, não meio escrito."""
    env = raiz_falsa / ".env"
    antes = "MOODLE_TOKEN=isso-nao-e-base64-###\nOUTRA=1\n"
    env.write_text(antes, encoding="utf-8")
    r = fix_token(raiz_falsa)
    assert r.returncode != 0
    assert r.stderr.strip()
    assert env.read_text(encoding="utf-8") == antes


def test_fix_token_sem_env_diz_o_que_fazer(raiz_falsa):
    """T-tok-13 — Invariante 6: a mensagem aponta a cura, não só a falta."""
    r = fix_token(raiz_falsa)
    assert r.returncode != 0
    assert "token.sh" in r.stderr or ".env.example" in r.stderr


def test_fix_token_acha_o_env_do_checkout_e_nao_o_do_worktree(tmp_path):
    """T-tok-14 — o `.env` do checkout principal, visto de dentro de um worktree.

    O `.env` e gitignorado, entao `git worktree add` nao o copia: um worktree
    novo nao tem o dele, e o de verdade esta no checkout que tem o `.git`
    diretorio. Um script que so olhasse `./.env` consertaria o arquivo errado —
    ou, pior, CRIARIA um `./.env` no worktree, que `achar_env` passaria a
    preferir, sombreando o verdadeiro em silencio. Mesmo defeito que a primeira
    versao do gate teve (§4 do CONVENTIONS.md).

    A montagem imita a real: `.git` DIRETORIO no principal (num worktree o
    `.git` e arquivo, e e assim que `achar_env` distingue os dois).
    """
    principal = tmp_path / "principal"
    (principal / ".git").mkdir(parents=True)
    env_verdadeiro = principal / ".env"
    env_verdadeiro.write_text(
        f"MOODLE_TOKEN=moodlemobile://token={payload(SITEID, WSTOKEN, PRIVATE)}\nOUTRA=1\n",
        encoding="utf-8",
    )

    wt = principal / ".claude" / "worktrees" / "algum"
    (wt / "scripts").mkdir(parents=True)
    (wt / "usp_mcp").mkdir()
    for nome in ("fix-token.sh", "_decodificar_token.py"):
        d = wt / "scripts" / nome
        d.write_bytes((RAIZ / "scripts" / nome).read_bytes())
        d.chmod(0o755)
    for nome in ("__init__.py", "env.py"):
        (wt / "usp_mcp" / nome).write_bytes((RAIZ / "usp_mcp" / nome).read_bytes())
    copiar_pacote_token(wt)  # a casca de scripts/ importa de la (ver raiz_falsa)
    assert not (wt / ".env").exists(), "montagem errada: o worktree nao pode ter .env"

    r = subprocess.run(
        ["bash", str(wt / "scripts" / "fix-token.sh")],
        capture_output=True, text=True, cwd=wt,
    )
    assert r.returncode == 0, r.stderr
    assert env_verdadeiro.read_text(encoding="utf-8") == f"MOODLE_TOKEN={WSTOKEN}\nOUTRA=1\n"
    assert not (wt / ".env").exists(), "criou um .env no worktree, sombreando o verdadeiro"
    assert WSTOKEN not in r.stdout + r.stderr, "ecoou o token"


# ------------------------------- a URL de IDA, e as duas fricoes de 12/09/2026

# A passagem real de um segundo usuario em 12/09/2026 (§B2 do ROADMAP) mediu
# duas fricoes no passo do link, e nenhuma e hipotese. A primeira: a pagina que o
# `launch.php` mostra com `confirmed=1` tem uma caixa verde, um botao cinza e um
# link azul escrito "Clique aqui se a aplicacao nao abrir automaticamente" —
# nada ali parece um token, e o texto do link promete ser um plano B dispensavel.
# O que foi para o clipboard na primeira tentativa foram os 137 bytes da URL da
# PROPRIA pagina. A segunda: nao havia como olhar o clipboard antes de entregar.

URL_DE_IDA = (
    "https://edisciplinas.usp.br/admin/tool/mobile/launch.php"
    "?service=moodle_mobile_app&passport=1234567890"
    "&urlscheme=moodlemobile&confirmed=1"
)


def test_a_url_de_ida_reprova_reconhecida_e_nao_adivinhada():
    """T-tok-15 — o decodificador nomeia o erro em vez de deduzi-lo do base64.

    Antes desta checagem a mesma entrada ja reprovava, mas pelo ramo do base64,
    com a causa no condicional ("o mais comum e ter copiado a URL do
    launch.php"). Reprovar estava certo; o diagnostico e que era um palpite, e
    ele nao dizia o que fazer. A assercao de que `base64` NAO aparece e o que
    trava isso: se alguem tirar o reconhecimento, a mensagem antiga volta e este
    teste cai.
    """
    r = decodificar(URL_DE_IDA)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert not campos(r.stdout), "emitiu campo para uma URL de ida"
    assert "base64" not in r.stderr.lower(), (
        "voltou a diagnosticar pelo ramo do base64 — a URL de ida tem de ser "
        "reconhecida antes, com a cura junto"
    )


def test_a_recusa_da_url_de_ida_diz_qual_link_e_que_e_botao_direito():
    """T-tok-16 — Invariante 6: a mensagem aponta a cura, e a cura e o link.

    "Copie o endereco do link" nao diz QUAL link numa pagina com tres elementos
    clicaveis; foi exatamente essa a fricao medida. Citar o texto do link e a
    parte acionavel da mensagem, nao enfeite.
    """
    r = decodificar(URL_DE_IDA)
    assert "Clique aqui se a aplicação não abrir automaticamente" in r.stderr
    assert "BOTÃO DIREITO" in r.stderr
    assert "moodlemobile://token=" in r.stderr


def test_a_recusa_da_url_de_ida_nao_ecoa_a_entrada():
    """T-tok-17 — a entrada pode ser a credencial; o diagnostico e de forma."""
    r = decodificar(URL_DE_IDA)
    assert URL_DE_IDA not in r.stderr + r.stdout
    # O TAMANHO da entrada pode sair — e forma, e e o que deixa "137 bytes"
    # reconhecivel para quem ja passou por isto. Os bytes, nunca.
    assert "passport=1234567890" not in r.stderr + r.stdout
    assert "edisciplinas.usp.br/admin" not in r.stderr + r.stdout


def test_o_base64_nu_continua_passando_depois_da_checagem_de_ida():
    """T-tok-18 — a checagem nova nao pode comer o caminho bom.

    `e_url_de_ida` reprova http(s) sem `token=`; um base64 nu nao e nem uma
    coisa nem outra e tem de seguir. Sem esta guarda, apertar o reconhecimento
    mais tarde quebraria em silencio quem cola so o payload.
    """
    r = decodificar(payload(SITEID, WSTOKEN, PRIVATE))
    assert r.returncode == 0, r.stderr
    assert campos(r.stdout)["wstoken"] == WSTOKEN


# ------------------------------------------- o token.sh, pelo caminho do stdin

# `pbpaste | ./scripts/token.sh` e um caminho de uso documentado no cabecalho do
# script. Ate 16/09 era o unico alcancavel pela suite, porque sem tty o script nao
# abria navegador (o `open` morava dentro de `[ -t 0 ]`). Desde 16/09 ele abre
# tambem sem terminal — quando o stdin vem vazio, que e a invocacao de abertura do
# fluxo em duas etapas —, entao TODO teste que passa pelo passo 3 precisa do `open`
# dublado de `navegador_dublado`, senao abre o navegador de quem roda a suite. O
# que abre, quando abre e o passaporte guardado entre as duas invocacoes estao em
# tests/moodle/test_token_navegador.py. Desde 17/09 a invocacao de abertura tambem
# FICA DE VIGIA no clipboard, lendo `pbpaste` a cada 0,5 s — e por isso TODO teste
# que passa por ela precisa do `pbpaste` dublado de `clipboard_dublado`, senao le o
# clipboard de quem roda a suite (ha uma pessoa usando esta maquina). O clipboard
# de verdade continua fora de alcance, de proposito; a captura automatica
# (`--auto`) segue exigindo tty.


@pytest.fixture
def raiz_token(raiz_falsa):
    """A raiz falsa do fix-token, mais o `token.sh` e um `.env` sem token.

    O `.venv/bin/python` e um link para o interpretador da suite porque e o que o
    script prefere (linha 44); sem ele o teste dependeria do `python3` do PATH,
    que pode nao ser o mesmo. O `.env` precisa ter `MOODLE_TOKEN` VAZIO: com um
    token de forma valida o script pede confirmacao para sobrescrever e, sem
    terminal, reprova antes de chegar ao passo do link.
    """
    destino = raiz_falsa / "scripts" / "token.sh"
    destino.write_bytes((RAIZ / "scripts" / "token.sh").read_bytes())
    destino.chmod(0o755)

    venv = raiz_falsa / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)

    (raiz_falsa / ".env").write_text(
        "MOODLE_URL=https://exemplo.invalid\nMOODLE_TOKEN=\nOUTRA=1\n",
        encoding="utf-8",
    )
    return raiz_falsa


def curl_dublado(raiz, corpo):
    """Um `curl` de mentira no PATH, e devolve o PATH para usar.

    O passo 6 do `token.sh` confirma o token contra a USP antes de gravar, e essa
    chamada fica no log da conta de quem roda (§1.1) — a suite nao a faz. O dube
    drena o stdin porque o script manda o campo por `curl -K -`: nao drenar
    deixaria o `printf` do outro lado do cano com SIGPIPE.
    """
    binario = raiz / "bin"
    binario.mkdir(exist_ok=True)
    falso = binario / "curl"
    falso.write_text("#!/bin/sh\ncat >/dev/null\ncat <<'JSON'\n" + corpo + "\nJSON\n")
    falso.chmod(0o755)
    return f"{binario}:{os.environ['PATH']}"


def navegador_dublado(raiz):
    """Um `open` de mentira em `raiz/bin`, que grava o argv e nunca abre nada.

    O dube registra cada chamada em `raiz/open.log`, uma linha por argv, e e por
    esse arquivo que test_token_navegador.py afirma O QUE foi aberto e QUANTAS
    vezes. Idempotente: a mesma pasta `bin/` que `curl_dublado` usa.
    """
    binario = raiz / "bin"
    binario.mkdir(exist_ok=True)
    falso = binario / "open"
    if not falso.exists():
        falso.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{raiz / 'open.log'}'\n")
        falso.chmod(0o755)
    return binario


MARCADOR_PAYLOAD = "{PAYLOAD}"


def clipboard_dublado(raiz, moodle_url="https://exemplo.invalid"):
    """Um `pbpaste` de mentira em `raiz/bin`, com ROTEIRO. Nunca o clipboard real.

    Ha uma pessoa usando a maquina em que a suite roda, e o clipboard dela nao e
    insumo de teste — nem para ler. O dube le `raiz/clipboard/<n>`, onde n e o
    numero da leitura (0 = a primeira), e vale o arquivo de indice mais alto <= n:
    o conteudo "fica" ate ser trocado, como num clipboard de verdade. Sem arquivo
    nenhum, imprime vazio.

    O marcador `{PAYLOAD}` num arquivo do roteiro vira o endereco do link DESTA
    rodada, calculado do passaporte que o script acabou de guardar em
    `.cache/passaporte` — e o que permite testar a vigia numa invocacao so, com
    um passaporte que o teste nao conhece de antemao. A formula e a do passo 5,
    para que "confere" seja confere de verdade.

    Cada leitura deixa uma linha em `raiz/pbpaste.log` com o INDICE, e so ele:
    o log nunca carrega conteudo, para que um teste de vazamento possa varrer a
    raiz inteira.
    """
    binario = raiz / "bin"
    binario.mkdir(exist_ok=True)
    programa = raiz / "pbpaste.py"
    programa.write_text(
        "import base64, hashlib, pathlib, re, sys\n"
        f"raiz = pathlib.Path({str(raiz)!r})\n"
        "d, c = raiz / 'clipboard', raiz / 'pbpaste.n'\n"
        "n = int(c.read_text()) if c.exists() else 0\n"
        "c.write_text(str(n + 1))\n"
        "with (raiz / 'pbpaste.log').open('a') as log:\n"
        "    log.write(f'{n}\\n')\n"
        "for i in range(n, -1, -1):\n"
        "    f = d / str(i)\n"
        "    if f.exists():\n"
        "        texto = f.read_text(encoding='utf-8')\n"
        f"        if {MARCADOR_PAYLOAD!r} in texto:\n"
        "            p = re.search(r'passaporte=(\\d+)', (raiz / '.cache' / 'passaporte').read_text()).group(1)\n"
        f"            siteid = hashlib.md5(({moodle_url!r} + p).encode()).hexdigest()\n"
        f"            b64 = base64.b64encode(':::'.join((siteid, {WSTOKEN!r}, {PRIVATE!r})).encode()).decode()\n"
        f"            texto = texto.replace({MARCADOR_PAYLOAD!r}, 'moodlemobile://token=' + b64)\n"
        "        sys.stdout.write(texto)\n"
        "        break\n",
        encoding="utf-8",
    )
    falso = binario / "pbpaste"
    falso.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{programa}'\n", encoding="utf-8")
    falso.chmod(0o755)
    return binario


def token_sh(raiz, colado, path=None, env=None, navegador=True, clipboard=True, args=()):
    """Roda o `token.sh` com o valor vindo do stdin. Nada aqui toca a rede, nada
    abre navegador e nada le o clipboard de verdade: com `navegador=True` (o
    padrao) o `open` do PATH e o dube de `navegador_dublado`, e com
    `clipboard=True` (o padrao) o `pbpaste` e o de `clipboard_dublado`. So os
    testes da maquina sem ferramenta desligam isso, e eles passam um PATH minimo
    que nao tem `open` nem `pbpaste` nenhum.

    A vigia dura 1 s por padrao aqui (USP_MCP_VIGIA_SEGUNDOS=1), e nao os 90 s
    do script: quem quer outro limite passa o seu em `env`. O roteiro do
    clipboard, quando ha, e escrito pelo teste antes de chamar.

    `SSH_CONNECTION`/`SSH_TTY` saem do ambiente porque o script, ao ve-las, se
    recusa a abrir navegador e a vigiar — certo numa sessao SSH de verdade, e
    ruido numa suite rodada por SSH que quer ver o dube ser chamado.
    """
    ambiente = {k: v for k, v in os.environ.items() if k not in ("SSH_CONNECTION", "SSH_TTY")}
    if path is not None:
        ambiente["PATH"] = path
    if navegador:
        ambiente["PATH"] = f"{navegador_dublado(raiz)}:{ambiente.get('PATH', '')}"
    if clipboard:
        ambiente["PATH"] = f"{clipboard_dublado(raiz)}:{ambiente.get('PATH', '')}"
    ambiente["USP_MCP_VIGIA_SEGUNDOS"] = "1"
    if env:
        ambiente.update(env)
    return subprocess.run(
        ["bash", str(raiz / "scripts" / "token.sh"), *args],
        input=colado,
        capture_output=True,
        text=True,
        cwd=raiz,
        env=ambiente,
    )


def test_o_script_cita_o_texto_do_link_e_manda_nao_clicar(raiz_token):
    """T-tok-19 — a cura da fricao 1, no texto que a pessoa de fato le.

    Asserir sobre a SAIDA e nao sobre o fonte: o bloco de instrucoes so existe no
    caminho manual, e e por ele que a pessoa passa. Um `grep` no arquivo passaria
    com o texto certo escrito num ramo que nunca executa.
    """
    r = token_sh(raiz_token, "")
    saida = r.stdout + r.stderr
    assert "Clique aqui se a aplicacao nao abrir automaticamente" in saida
    assert "NAO CLIQUE" in saida
    assert "Copiar endereco do link" in saida
    # Os dois chamarizes, nomeados para serem ignorados de proposito.
    assert "O seu cadastro foi confirmado" in saida
    assert "Ambientes" in saida


def test_o_script_recusa_a_url_de_ida_sem_tocar_o_env(raiz_token):
    """T-tok-20 — a conferencia pega o erro medido antes de qualquer decodificacao.

    O `.env` intacto e o passo 6 nunca alcancado sao a metade que importa: o que
    a pessoa fez de errado nao pode custar uma chamada no log da conta nem um
    `.env` meio escrito.

    A assercao de que o passo `4/7` NAO aparece e o que faz este teste ser sobre
    a CONFERENCIA. Sem ela o teste passava com a conferencia desligada, porque o
    decodificador recusa a mesma entrada logo em seguida, com uma mensagem
    parecida — verificado por sabotagem: tirar o `exit 1` do ramo `launch.php`
    nao quebrava nada. Duas camadas com a mesma mensagem sao boas de ter e
    pessimas de confundir num teste.
    """
    antes = (raiz_token / ".env").read_text(encoding="utf-8")
    r = token_sh(raiz_token, URL_DE_IDA)
    saida = r.stdout + r.stderr
    assert r.returncode != 0
    assert "4/7" not in saida, "passou da conferencia e so parou no decodificador"
    assert "URL de IDA" in saida
    assert "de VOLTA" in saida
    assert "Clique aqui se a aplicacao nao abrir automaticamente" in saida
    assert (raiz_token / ".env").read_text(encoding="utf-8") == antes
    assert "passport=1234567890" not in saida, "ecoou o valor colado"


def test_a_conferencia_nao_imprime_byte_nenhum_de_um_base64_nu(raiz_token):
    """T-tok-21 — Invariante 3 aplicado a checagem NOVA, que e o risco que ela cria.

    A conferencia a mao e `pbpaste | cut -c1-21`. Um `cut` incondicional dentro
    do script imprimiria 21 caracteres de token quando a pessoa cola so o base64
    — que e um caminho valido e documentado. So o prefixo do esquema pode sair, e
    so quando ele e o prefixo de verdade.
    """
    colado = payload(SITEID, WSTOKEN, PRIVATE)
    caminho = curl_dublado(raiz_token, '{"userid": 4242, "sitename": "dube"}')
    r = token_sh(raiz_token, colado, path=caminho)
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida  # o base64 nu e caminho bom, nao erro
    assert colado[:21] not in saida, "imprimiu 21 caracteres do payload colado"
    assert colado[:8] not in saida, "imprimiu o comeco do payload colado"
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"


def test_a_conferencia_confirma_o_prefixo_e_o_script_grava(raiz_token):
    """T-tok-22 — o caminho bom: a conferencia diz o que a pessoa queria ver.

    E o unico eco autorizado do valor: o prefixo do esquema, que e publico e tem
    zero byte de token depois do `=`. O resto da assercao e o contrato do script
    inteiro — grava os 32 hex, nunca imprime o valor.
    """
    colado = f"moodlemobile://token={payload(SITEID, WSTOKEN, PRIVATE)}"
    caminho = curl_dublado(raiz_token, '{"userid": 4242, "sitename": "dube"}')
    r = token_sh(raiz_token, colado, path=caminho)
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "confere: comeca com `moodlemobile://token=`" in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"
