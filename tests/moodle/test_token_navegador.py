"""O `token.sh` sem terminal: abre o navegador, guarda o passaporte, sai aguardando.

Ate 16/09/2026 o `open` do passo 3 morava dentro de `[ -t 0 ]`. Um agente de
codigo roda o script sem terminal, entao ele via a URL impressa, navegador
nenhum, e o script morrendo em "Nada foi colado". Na rodada seguinte, com o
payload por `pbpaste |`, o passaporte era outro e a conferencia do passo 5
avisava em toda rodada boa — que e como se ensina alguem a ignorar um aviso
(BACKLOG, 11/09).

O desenho de 16/09 e uma rodada em duas invocacoes: a primeira abre a pagina
certa e guarda o passaporte em `.cache/passaporte` (0600, 10 min, uma vez); a
segunda o reaproveita. Estes testes afirmam as propriedades desse desenho com um
`open` dublado no PATH que grava o que recebeu — o `open` de verdade nunca roda
na suite (ver `navegador_dublado` em test_token_decode.py):

  N1  sem terminal e sem payload: abre a URL certa, guarda o passaporte com 0600,
      sai 3, e nao toca o .env nem chama o curl;
  N2  a segunda invocacao reaproveita o passaporte, a conferencia BATE, o token e
      gravado e o arquivo morre (uso unico); ela NAO abre navegador;
  N3  passaporte vencido nao e reaproveitado: outro nasce, e o passo 5 diz por
      que nao bateu — sem bloquear, porque o passo 6 e quem decide. O limite e o
      limite: por pouco dentro ainda vale;
  N4  uso unico de verdade: o mesmo payload de novo nao confere; consumir nao
      depende de bater; e um erro ANTES do passo 5 (a URL de ida) preserva o
      passaporte para a tentativa seguinte;
  N5  o caminho antigo intacto: `pbpaste | token.sh` sem rodada anterior nao abre
      navegador e grava como sempre; e a pessoa no terminal (pty de verdade)
      continua vendo o navegador abrir, colando e gravando numa invocacao so.

Mais os cantos de "abrir sem terminal pode surpreender": USP_MCP_NAO_ABRIR=1,
sessao SSH e maquina sem `open`/`xdg-open` — nos tres o script nao abre nada e
diz o que fez. Tudo offline; o `curl` e sempre um dube.

Desde 17/09 a abertura nao para em "sai com 3": ela FICA DE VIGIA no clipboard
e, quando ele muda para o endereco do link, segue sozinha ate gravar — uma
invocacao, zero mensagens da pessoa. A secao V afirma o desenho da vigia, com um
`pbpaste` dublado que segue um ROTEIRO (`clipboard_dublado`; o clipboard real
desta maquina nunca e lido pela suite):

  V1  detecta a mudanca e segue sozinha, com a conferencia do passo 5 batendo;
  V2  o que JA estava no clipboard nao dispara (so mudanca conta) — salvo se ja
      responde ao passaporte desta rodada, que e o caso de uma vigia que venceu
      e foi reaberta dentro da validade;
  V3  forma errada NAO encerra: a URL de ida vira uma frase e a vigia continua;
  V4  o limite de tempo e respeitado, com 2 leituras por segundo e a saida 3
      dizendo o que fazer;
  V5  o que nao casa nao vaza — nem o conteudo, nem o tamanho, nem em disco; e
      dez copias erradas nao viram dez broncas;
  V6  sem pbpaste/wl-paste/xclip, por SSH ou com USP_MCP_VIGIA_SEGUNDOS=0 nao ha
      vigia, o script diz por que e cai no fluxo em duas invocacoes;
  V7  base64 nu nao dispara a vigia (dispararia em qualquer coisa parecida com
      base64, e o decodificador diria o tamanho ao recusar).

Nenhum token real entra aqui: o payload e montado com o WSTOKEN sintetico do
test_token_decode.py, e o siteid e md5(MOODLE_URL + passaporte) calculado no
teste — a mesma formula que o passo 5 usa, para que "bate" seja bate de verdade.
"""
from __future__ import annotations

import hashlib
import os
import pty
import re
import select
import shutil
import signal
import stat
import sys
import time

import pytest

from tests.git import esta_ignorado
from tests.moodle.conftest import RAIZ
from tests.moodle.test_token_decode import (  # noqa: F401 — as fixtures entram pelo namespace
    MARCADOR_PAYLOAD,
    PRIVATE,
    SITEID,
    URL_DE_IDA,
    WSTOKEN,
    clipboard_dublado,
    curl_dublado,
    navegador_dublado,
    payload,
    raiz_falsa,
    raiz_token,
    token_sh,
)

pytestmark = pytest.mark.politica

# O que `raiz_token` grava no .env. A URL de abertura e derivada dela.
MOODLE_URL = "https://exemplo.invalid"
RE_URL_MANUAL = re.compile(
    re.escape(MOODLE_URL)
    + r"/admin/tool/mobile/launch\.php\?service=moodle_mobile_app"
    r"&passport=(\d{10})&urlscheme=moodlemobile&confirmed=1"
)
JSON_OK = '{"userid": 4242, "sitename": "dube"}'
SAIDA_AGUARDANDO = 3
VALIDADE = 600


# ------------------------------------------------------------------- ajudantes


def aberturas(raiz) -> list[str]:
    """Cada linha e o argv de uma chamada ao `open` dublado."""
    log = raiz / "open.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def passaporte_da_url(texto: str) -> str:
    m = RE_URL_MANUAL.search(texto)
    assert m, f"nao achei a URL do launch.php em: {texto[:300]!r}"
    return m.group(1)


def arquivo_passaporte(raiz):
    return raiz / ".cache" / "passaporte"


def ler_passaporte(raiz) -> tuple[str, int]:
    """(passaporte, criado). Afirma a FORMA inteira do arquivo: duas linhas e
    nada mais — em particular, nem payload nem token moram ali."""
    texto = arquivo_passaporte(raiz).read_text(encoding="utf-8")
    m = re.fullmatch(r"passaporte=(\d{10})\ncriado=(\d+)\n", texto)
    assert m, f"forma inesperada do arquivo do passaporte: {texto!r}"
    return m.group(1), int(m.group(2))


def envelhecer(raiz, segundos: int) -> None:
    """Recua o `criado` do passaporte guardado, sem mexer no valor."""
    p, c = ler_passaporte(raiz)
    arquivo_passaporte(raiz).write_text(
        f"passaporte={p}\ncriado={c - segundos}\n", encoding="utf-8"
    )


def payload_para(passaporte: str) -> str:
    """A URL de volta que o Moodle emitiria para ESTE passaporte."""
    siteid = hashlib.md5((MOODLE_URL + passaporte).encode()).hexdigest()
    return f"moodlemobile://token={payload(siteid, WSTOKEN, PRIVATE)}"


def curl_registrado(raiz) -> str:
    """Como `curl_dublado`, mas deixa rastro em `raiz/curl.log` a cada chamada.

    Serve para afirmar que a invocacao de abertura NAO chega ao passo 6: um
    `curl` que nao e chamado nao deixa arquivo.
    """
    binario = raiz / "bin"
    binario.mkdir(exist_ok=True)
    falso = binario / "curl"
    falso.write_text(
        "#!/bin/sh\n"
        f"printf 'chamado\\n' >> '{raiz / 'curl.log'}'\n"
        "cat >/dev/null\n"
        f"cat <<'JSON'\n{JSON_OK}\nJSON\n",
        encoding="utf-8",
    )
    falso.chmod(0o755)
    return f"{binario}:{os.environ['PATH']}"


def abrir(raiz, **kw):
    """A invocacao de abertura: sem terminal e com stdin vazio. O clipboard
    dublado nao tem roteiro, entao a vigia (1 s, pelo arnes) vence sem achar
    nada — e a abertura, como era ate 16/09, sai com 3."""
    kw.setdefault("path", curl_registrado(raiz))
    return token_sh(raiz, "", **kw)


def roteiro(raiz, passos: dict[int, str]) -> None:
    """O que o `pbpaste` dublado devolve na leitura de indice i, para cada i em
    `passos`; entre um indice e o seguinte o conteudo fica. Zera o contador e o
    log da rodada anterior, para que a leitura 0 seja a primeira desta."""
    d = raiz / "clipboard"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    for arquivo in ("pbpaste.n", "pbpaste.log"):
        (raiz / arquivo).unlink(missing_ok=True)
    for i, conteudo in passos.items():
        (d / str(i)).write_text(conteudo, encoding="utf-8")


def leituras(raiz) -> int:
    """Quantas vezes o `pbpaste` dublado foi chamado."""
    log = raiz / "pbpaste.log"
    return len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0


def vigiar(raiz, passos: dict[int, str], segundos: int = 3, **kw):
    """A abertura com um roteiro de clipboard e um limite de vigia proprio."""
    roteiro(raiz, passos)
    kw.setdefault("path", curl_registrado(raiz))
    env = dict(kw.pop("env", None) or {})
    env.setdefault("USP_MCP_VIGIA_SEGUNDOS", str(segundos))
    return token_sh(raiz, "", env=env, **kw)


def chamadas_ao_curl(raiz) -> int:
    log = raiz / "curl.log"
    return len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0


def path_minimo(tmp_path, *nomes_extras: str) -> str:
    """Um PATH so com o que o script usa ate o passo 3 — sem `open`, `xdg-open`,
    `pbpaste`, `wl-paste` nem `xclip`. E o chao de um servidor sem interface."""
    minimo = tmp_path / "bin_minimo"
    minimo.mkdir(exist_ok=True)
    for nome in ("bash", "dirname", "grep", "sed", "head", "date", "mkdir", "rm",
                 "sleep", "cat", "wc", "tr", "cut", "cp", *nomes_extras):
        real = shutil.which(nome)
        assert real, f"sem `{nome}` nesta maquina; o teste precisa dele para montar o PATH minimo"
        destino = minimo / nome
        if not destino.exists():
            destino.symlink_to(real)
    return str(minimo)


def entregar(raiz, colado: str, *args: str):
    """A invocacao de entrega: `pbpaste | ./scripts/token.sh [args]`."""
    return token_sh(raiz, colado, path=curl_dublado(raiz, JSON_OK), args=args)


# ------------------------------------------------------------ N1: a abertura


def test_n1_sem_terminal_e_sem_payload_abre_a_pagina_certa_e_sai_aguardando(raiz_token):
    """N1 — o que um agente de codigo ve na primeira invocacao.

    O que se afirma e o argv que o `open` recebeu (regra 11 do CLAUDE.md: o
    parametro enviado, nao a saida), a forma e a permissao do passaporte
    guardado, o codigo de saida proprio, e as duas coisas que NAO podem ter
    acontecido: o .env mudar e o curl ser chamado.
    """
    antes = (raiz_token / ".env").read_text(encoding="utf-8")
    r = abrir(raiz_token)
    saida = r.stdout + r.stderr

    assert r.returncode == SAIDA_AGUARDANDO, saida
    ab = aberturas(raiz_token)
    assert len(ab) == 1, f"esperava UMA chamada ao open, houve {len(ab)}: {ab}"
    p_url = passaporte_da_url(ab[0])
    assert ab[0].strip() == (
        f"{MOODLE_URL}/admin/tool/mobile/launch.php?service=moodle_mobile_app"
        f"&passport={p_url}&urlscheme=moodlemobile&confirmed=1"
    ), "o open recebeu algo alem da URL manual"

    p_arq, criado = ler_passaporte(raiz_token)
    assert p_arq == p_url, "o passaporte guardado nao e o da pagina aberta"
    assert abs(time.time() - criado) < 60
    modo = stat.S_IMODE(arquivo_passaporte(raiz_token).stat().st_mode)
    assert modo == 0o600, f"passaporte com permissao {oct(modo)}, esperava 0600"

    assert "abri a URL no navegador padrao" in saida
    assert "pbpaste | ./scripts/token.sh" in saida
    assert "Saida 3 = aguardando" in saida
    assert "6/7" not in saida, "chegou ao passo 6 sem payload"
    assert not (raiz_token / "curl.log").exists(), "chamou o curl sem ter token"
    assert (raiz_token / ".env").read_text(encoding="utf-8") == antes


def test_n1b_abrir_de_novo_dentro_da_validade_abre_a_mesma_pagina(raiz_token):
    """N1b — a abertura e idempotente: um agente que repete o comando nao
    invalida a aba que a pessoa ja tem aberta, e a validade NAO desliza."""
    abrir(raiz_token)
    p1, c1 = ler_passaporte(raiz_token)
    abrir(raiz_token)
    p2, c2 = ler_passaporte(raiz_token)
    assert (p1, c1) == (p2, c2), "reabrir cunhou outro passaporte ou renovou a validade"
    ab = aberturas(raiz_token)
    assert len(ab) == 2
    assert passaporte_da_url(ab[0]) == passaporte_da_url(ab[1]) == p1


# --------------------------------------------------------- N2: a reutilizacao


def test_n2_a_segunda_invocacao_reaproveita_o_passaporte_e_a_conferencia_bate(raiz_token):
    """N2 — o fluxo inteiro em duas invocacoes, e a conferencia com valor.

    "Bate" aqui e calculado, nao presumido: o siteid do payload e a md5 do
    passaporte que a PRIMEIRA invocacao guardou. Se a segunda cunhasse outro
    (o comportamento antigo), esta assercao falha com "nao confere".
    """
    abrir(raiz_token)
    p, _ = ler_passaporte(raiz_token)

    r = entregar(raiz_token, payload_para(p))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "reaproveitando o da rodada de ha" in saida
    assert "confere: o payload responde a ESTA rodada" in saida
    assert "nao confere" not in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert not arquivo_passaporte(raiz_token).exists(), "uso unico: devia ter sido consumido"
    assert len(aberturas(raiz_token)) == 1, "a invocacao de entrega abriu navegador"
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"


# ------------------------------------------------------------- N3: a validade


def test_n3_passaporte_vencido_nao_e_reaproveitado_e_o_passo_5_diz_por_que(raiz_token):
    """N3 — vencido e descartado, outro nasce, e a pessoa fica sabendo.

    Nao bloqueia: o desenho de 10/09 (§3.1) diz que a conferencia avisa porque
    a formula e recordada, e este teste nao muda isso. O que muda e a mensagem:
    ela nomeia a idade e a validade, em vez de deixar a pessoa adivinhar.
    """
    abrir(raiz_token)
    p_velho, _ = ler_passaporte(raiz_token)
    envelhecer(raiz_token, VALIDADE + 1)

    r = entregar(raiz_token, payload_para(p_velho))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida  # o passo 6 decide, e o dube autenticou
    assert "reaproveitando" not in saida
    assert f"acima dos {VALIDADE}s de validade" in saida
    assert "nao confere" in saida
    assert "foi descartado no passo 2" in saida
    assert not arquivo_passaporte(raiz_token).exists()
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")


def test_n3b_por_pouco_dentro_da_validade_ainda_vale(raiz_token):
    """N3b — o limite e o limite. Sem isto, um `-ge` no lugar de `-gt` passaria
    no N3 e recusaria um passaporte de 600 s por engano."""
    abrir(raiz_token)
    p, _ = ler_passaporte(raiz_token)
    envelhecer(raiz_token, VALIDADE - 5)
    r = entregar(raiz_token, payload_para(p))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "reaproveitando" in saida
    assert "confere: o payload responde a ESTA rodada" in saida


def test_n3c_abrir_de_novo_depois_de_vencido_cunha_outro(raiz_token):
    """N3c — a abertura tambem respeita a validade: um passaporte de ontem nao
    e o que vai para a pagina de hoje."""
    abrir(raiz_token)
    p1, _ = ler_passaporte(raiz_token)
    envelhecer(raiz_token, 3600)
    r = abrir(raiz_token)
    p2, c2 = ler_passaporte(raiz_token)
    assert p1 != p2
    assert abs(time.time() - c2) < 60
    assert "descartado" in r.stdout + r.stderr
    ab = aberturas(raiz_token)
    assert [passaporte_da_url(a) for a in ab] == [p1, p2]


def test_n3d_arquivo_ilegivel_e_lixo_e_nao_erro(raiz_token):
    """N3d — material de sessao nao merece conserto: forma estranha sai do
    caminho e a rodada segue com passaporte novo."""
    arquivo_passaporte(raiz_token).parent.mkdir(parents=True)
    arquivo_passaporte(raiz_token).write_text("passaporte=abc\ncriado=ontem\n", encoding="utf-8")
    r = abrir(raiz_token)
    assert r.returncode == SAIDA_AGUARDANDO, r.stdout + r.stderr
    p, _ = ler_passaporte(raiz_token)
    assert passaporte_da_url(aberturas(raiz_token)[0]) == p


# ------------------------------------------------------------ N4: o uso unico


def test_n4_o_mesmo_payload_de_novo_nao_confere(raiz_token):
    """N4 — uso unico: depois de consumido, o passaporte nao volta."""
    abrir(raiz_token)
    p, _ = ler_passaporte(raiz_token)
    assert entregar(raiz_token, payload_para(p)).returncode == 0

    # --sobrescrever porque o .env agora TEM token valido e nao ha terminal para
    # perguntar: e a protecao do passo 1 funcionando, nao o assunto deste teste.
    r = entregar(raiz_token, payload_para(p), "--sobrescrever")
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida  # a formula segue como aviso; o passo 6 decide
    assert "reaproveitando" not in saida
    assert "nao confere" in saida
    assert not arquivo_passaporte(raiz_token).exists()


def test_n4b_consumir_nao_depende_de_bater(raiz_token):
    """N4b — um payload de OUTRA rodada tambem gasta o passaporte: ele foi
    confrontado, e um passaporte confrontado nao serve para uma segunda
    tentativa de acertar por comparacao."""
    abrir(raiz_token)
    r = entregar(raiz_token, payload_para("1111111111"))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "nao confere" in saida
    assert not arquivo_passaporte(raiz_token).exists()


def test_n4c_erro_antes_do_passo_5_preserva_o_passaporte(raiz_token):
    """N4c — o erro nº 1 medido (colar a URL de ida) nao pode custar o
    passaporte: a pessoa volta a pagina, copia certo, e a conferencia ainda
    fecha. Se o arquivo morresse na leitura, a tentativa seguinte daria
    "nao confere" por culpa do script, nao dela."""
    abrir(raiz_token)
    p, c = ler_passaporte(raiz_token)

    r = entregar(raiz_token, URL_DE_IDA)
    assert r.returncode != 0
    assert "URL de IDA" in r.stdout + r.stderr
    assert ler_passaporte(raiz_token) == (p, c), "o erro de colagem consumiu o passaporte"

    r = entregar(raiz_token, payload_para(p))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "confere: o payload responde a ESTA rodada" in saida
    assert not arquivo_passaporte(raiz_token).exists()


# --------------------------------------------------- N5: o caminho antigo intacto


def test_n5_pbpaste_por_cano_sem_rodada_anterior_nao_abre_navegador_e_grava(raiz_token):
    """N5 — `pbpaste | ./scripts/token.sh` do jeito antigo, sem abertura antes.

    Tres coisas nao podem mudar: nao abre navegador (quem chegou com o payload
    nao quer uma aba nova), grava o token, e a conferencia avisa como sempre
    avisou — o payload nao e desta rodada, e a mensagem diz que esta tudo bem.
    """
    r = entregar(raiz_token, payload_para("1234567890"))
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert aberturas(raiz_token) == [], "o caminho por cano abriu navegador"
    assert "li do stdin." in saida
    assert "aguardando" not in saida
    assert "nao confere" in saida
    assert "esta tudo certo" in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert not arquivo_passaporte(raiz_token).exists()


def _rodar_com_tty(raiz, ambiente: dict[str, str], responder, timeout: float = 90.0):
    """Roda o `token.sh` atras de um pseudo-terminal de verdade.

    `[ -t 0 ]` e verdadeiro e `/dev/tty` e o pty: o script segue o caminho da
    pessoa. `responder(saida_ate_agora)` devolve o que "digitar" quando o
    prompt do passo 3 aparecer — so entao, porque e o `read -s` que desliga o
    eco, e digitar antes ecoaria o payload na tela que este teste afirma limpa.
    Devolve (saida, codigo).

    O passo 2 tem paradas (`pausar`, 18/09/2026), e uma pessoa no terminal
    responde a cada uma com Enter. O arnes faz o mesmo: uma linha em branco por
    `[Enter]` NOVO que aparecer na saida. Sem isto o script fica bloqueado no
    primeiro `read` e o laco so termina no timeout — que foi exatamente como
    este arnes quebrou quando as paradas entraram.
    """
    pid, fd = pty.fork()
    if pid == 0:  # filho: vira o script
        try:
            os.chdir(raiz)
            os.execve(shutil.which("bash"), ["bash", "scripts/token.sh"], ambiente)
        finally:
            os._exit(127)

    saida = b""
    respondido = False
    pausas_respondidas = 0
    fim = time.monotonic() + timeout
    try:
        while time.monotonic() < fim:
            pronto, _, _ = select.select([fd], [], [], 0.2)
            if not pronto:
                continue
            try:
                bloco = os.read(fd, 65536)
            except OSError:  # EIO: o outro lado fechou — o script terminou
                break
            if not bloco:
                break
            saida += bloco
            # As paradas do passo 2, uma linha em branco cada. Vem antes do
            # prompt do passo 3 e nao colidem com ele: aquele prompt diz "Cole e
            # aperte Enter" e nao carrega a marca `[Enter]`.
            vistas = saida.count(b"[Enter]")
            if vistas > pausas_respondidas:
                os.write(fd, b"\n" * (vistas - pausas_respondidas))
                pausas_respondidas = vistas
            if not respondido and b"Cole e aperte Enter" in saida:
                texto = saida.decode("utf-8", "replace").replace("\r", "")
                os.write(fd, responder(texto).encode() + b"\n")
                respondido = True
        else:
            os.kill(pid, signal.SIGKILL)
    finally:
        os.close(fd)
    _, status = os.waitpid(pid, 0)
    return saida.decode("utf-8", "replace").replace("\r", ""), os.waitstatus_to_exitcode(status)


def test_n5b_a_pessoa_no_terminal_continua_vendo_tudo_numa_invocacao_so(raiz_token):
    """N5b — o caminho de quem roda no terminal, com pty de verdade.

    O desenho de 10/09 (§7) media isto a mao, com pty, e dizia que a suite nao
    alcancava. Com o `open` dublado ela alcanca: navegador aberto UMA vez na URL
    com o passaporte desta invocacao, payload colado sem eco, conferencia
    batendo, token gravado, passaporte consumido. Tudo numa invocacao, como
    sempre foi — e sem "li do stdin" nem "aguardando", que sao dos outros dois
    caminhos.
    """
    ambiente = {k: v for k, v in os.environ.items() if k not in ("SSH_CONNECTION", "SSH_TTY")}
    # O `pbpaste` dublado entra no PATH por precaucao: o caminho do terminal so
    # le o clipboard se a pessoa der Enter em branco, e este teste digita o
    # payload — mas um PATH com o `pbpaste` real e um convite a ler o clipboard
    # de quem roda a suite no dia em que isso mudar.
    clipboard_dublado(raiz_token)
    ambiente["PATH"] = f"{navegador_dublado(raiz_token)}:{curl_dublado(raiz_token, JSON_OK)}"
    ambiente["TERM"] = "dumb"

    digitado: dict[str, str] = {}

    def responder(texto: str) -> str:
        digitado["valor"] = payload_para(passaporte_da_url(texto))
        return digitado["valor"]

    saida, codigo = _rodar_com_tty(raiz_token, ambiente, responder)

    assert codigo == 0, saida
    ab = aberturas(raiz_token)
    assert len(ab) == 1, f"esperava UMA chamada ao open, houve {len(ab)}: {ab}"
    assert passaporte_da_url(ab[0]) == passaporte_da_url(saida)
    assert "confere: o payload responde a ESTA rodada" in saida
    assert "li do stdin" not in saida
    assert "aguardando" not in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert not arquivo_passaporte(raiz_token).exists()
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"
    # O `read -s` e o que impede a credencial de ficar no scrollback. So o
    # prefixo do esquema pode aparecer (a conferencia o cita); o base64 depois
    # do `token=`, nunca.
    base64_digitado = digitado["valor"].split("token=", 1)[1]
    assert base64_digitado[:16] not in saida, "o payload colado ecoou no terminal"


# ------------------------------------- abrir sem terminal, sem surpreender ninguem


def test_usp_mcp_nao_abrir_desliga_o_navegador_e_diz_isso(raiz_token):
    """A mesma chave que `_capturar_redirect.sh` ja honra. O resto da abertura
    (passaporte guardado, saida 3) continua, porque a pessoa vai abrir a URL
    a mao e voltar com o payload."""
    r = abrir(raiz_token, env={"USP_MCP_NAO_ABRIR": "1"})
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert aberturas(raiz_token) == []
    assert "USP_MCP_NAO_ABRIR=1: nao abri navegador nenhum" in saida
    assert arquivo_passaporte(raiz_token).exists()


def test_sessao_ssh_nao_abre_navegador_e_diz_por_que(raiz_token):
    """Por SSH, `open` abriria na maquina remota. O script percebe e manda
    abrir na maquina da pessoa, em vez de abrir uma aba que ninguem ve."""
    r = abrir(raiz_token, env={"SSH_CONNECTION": "10.0.0.2 51234 10.0.0.1 22"})
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert aberturas(raiz_token) == []
    assert "sessao SSH" in saida
    assert "SUA maquina" in saida
    assert arquivo_passaporte(raiz_token).exists()
    # E nao vigia: o clipboard que `pbpaste` alcanca por SSH e o da maquina
    # remota, e o endereco vai ser copiado na da pessoa (V6).
    assert "o clipboard que eu leria e o da maquina remota" in saida
    assert leituras(raiz_token) == 0, "leu o clipboard numa sessao SSH"
    assert "pbpaste | ./scripts/token.sh" in saida


def test_maquina_sem_open_nem_xdg_open_diz_e_segue(raiz_token, tmp_path):
    """Servidor sem interface: PATH minimo com so o que o script usa ate o passo
    3, e sem `open` nem `xdg-open`. Ele diz que nao ha como abrir, e o resto da
    abertura segue — a URL esta impressa para ser aberta em outro lugar."""
    r = token_sh(
        raiz_token, "", path=path_minimo(tmp_path), navegador=False, clipboard=False,
        env={"DISPLAY": "", "WAYLAND_DISPLAY": ""},
    )
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "nao ha como abrir navegador desta maquina" in saida
    assert "Abra a URL acima" in saida
    assert not (raiz_token / "open.log").exists()
    assert arquivo_passaporte(raiz_token).exists()


# ---------------------------------------------------------- V: a vigia do clipboard


def test_v1_a_vigia_detecta_a_mudanca_e_segue_sozinha(raiz_token):
    """V1 — o pedido inteiro numa invocacao: abre, vigia, o clipboard muda para
    o endereco do link, e o script vai ate gravar. Zero mensagens da pessoa.

    O anuncio da vigia tem de vir ANTES de qualquer resultado dela, no texto
    que a pessoa le: o que e lido, com que frequencia, por quanto tempo, o que
    dispara, o que acontece com o resto e como desligar. Nao e para esconder.
    """
    r = vigiar(raiz_token, {0: "um texto qualquer que ja estava no clipboard", 2: MARCADOR_PAYLOAD})
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida

    anuncio = saida.find("AVISO, antes de comecar: vou LER o clipboard")
    achado = saida.find("o clipboard mudou para algo que comeca com `moodlemobile://token=`")
    assert 0 <= anuncio < achado, "a vigia agiu antes de se anunciar, ou nao se anunciou"
    assert "a cada" in saida and "0,5 s" in saida
    assert "por ate 3 s" in saida
    assert "USP_MCP_VIGIA_SEGUNDOS=0" in saida, "nao disse como desligar"
    assert "nao guardo, nao" in saida and "nao digo o tamanho" in saida

    assert "Seguindo sozinho a partir daqui" in saida
    assert "confere: o payload responde a ESTA rodada" in saida
    assert "nao confere" not in saida
    assert "vigia encerrada" not in saida
    assert "Saida 3" not in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert not arquivo_passaporte(raiz_token).exists(), "uso unico: devia ter sido consumido"
    assert len(aberturas(raiz_token)) == 1
    assert chamadas_ao_curl(raiz_token) == 1
    assert leituras(raiz_token) == 3, "marco + 2 leituras ate a mudanca no indice 2"
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"


def test_v2_o_que_ja_estava_no_clipboard_nao_dispara(raiz_token):
    """V2 — clipboard velho: o endereco de OUTRA rodada ja esta la quando a
    vigia comeca. Disparar nele daria um passaporte que nao bate; ele e o
    marco, e so uma mudanca conta. A vigia vence sem agir, e nada e gravado."""
    antes = (raiz_token / ".env").read_text(encoding="utf-8")
    r = vigiar(raiz_token, {0: payload_para("1111111111")}, segundos=1)
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "ja tinha um endereco com a forma certa, mas de OUTRA rodada" in saida
    assert "so uma MUDANCA conta" in saida
    assert "vigia encerrada sem o endereco" in saida
    assert "4/7" not in saida, "decodificou o que ja estava la"
    assert chamadas_ao_curl(raiz_token) == 0
    assert (raiz_token / ".env").read_text(encoding="utf-8") == antes
    assert arquivo_passaporte(raiz_token).exists(), "a vigia que venceu consumiu o passaporte"


def test_v2b_o_que_ja_estava_no_clipboard_dispara_se_responde_a_esta_rodada(raiz_token):
    """V2b — a excecao conferida do V2. A vigia venceu (a pessoa demorou), o
    agente rodou o script de novo dentro da validade: o passaporte e reaproveitado,
    a pagina aberta e a mesma, e o endereco que a pessoa copiou nesse meio tempo
    JA esta no clipboard — com o siteid deste passaporte. Esperar uma mudanca
    aqui seria esperar por nada: o link da pagina e o mesmo. O script confere
    (md5 do passaporte guardado) e segue sem esperar."""
    assert vigiar(raiz_token, {}, segundos=1).returncode == SAIDA_AGUARDANDO
    p, _ = ler_passaporte(raiz_token)

    r = vigiar(raiz_token, {0: payload_para(p)}, segundos=1)
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "reaproveitando o da rodada de ha" in saida
    assert "responde ao" in saida and "passaporte DESTA rodada" in saida
    assert "Seguindo sem esperar" in saida
    assert leituras(raiz_token) == 1, "esperou mudanca num endereco que ja era desta rodada"
    assert "confere: o payload responde a ESTA rodada" in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert not arquivo_passaporte(raiz_token).exists()


def test_v3_a_url_de_ida_nao_encerra_a_vigia_ensina_e_segue(raiz_token):
    """V3 — o ganho de verdade. O erro nº 1 medido (copiar a URL da propria
    pagina) matava a tentativa; de vigia, ele vira uma frase com a cura e a
    espera continua. A pessoa copia certo em seguida e o script grava, sem ter
    gastado o passaporte nem uma chamada na conta com o erro."""
    r = vigiar(raiz_token, {0: "", 2: URL_DE_IDA, 4: MARCADOR_PAYLOAD})
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "veio a URL de IDA" in saida
    assert "Copiar endereco do link" in saida
    assert "Continuo de vigia" in saida
    assert "Seguindo sozinho a partir daqui" in saida
    assert "confere: o payload responde a ESTA rodada" in saida
    assert chamadas_ao_curl(raiz_token) == 1, "a URL de ida custou uma chamada, ou o acerto nao chegou"
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    # A URL de ida nao e ecoada — nem o passaporte dela, nem o host.
    assert "passport=1234567890" not in saida
    assert "edisciplinas.usp.br/admin" not in saida


def test_v4_a_vigia_respeita_o_limite_e_sai_dizendo_o_que_fazer(raiz_token):
    """V4 — tempo. A chamada do agente tem teto; uma vigia que passa dele deixa
    o agente sem resposta. O limite e respeitado em leituras (2 por segundo, mais
    o marco) e em relogio, e a saida 3 diz o caminho que continua existindo:
    `pbpaste | ./scripts/token.sh`, ou rodar de novo para voltar a vigiar."""
    antes = (raiz_token / ".env").read_text(encoding="utf-8")
    inicio = time.monotonic()
    r = vigiar(raiz_token, {0: "nada muda"}, segundos=2)
    duracao = time.monotonic() - inicio
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert 2.0 <= duracao < 15.0, f"a vigia de 2 s durou {duracao:.1f} s"
    assert leituras(raiz_token) == 1 + 2 * 2, "marco + 2 leituras por segundo"
    assert "vigia encerrada sem o endereco" in saida
    assert "2 s e o clipboard nao mudou" in saida
    assert "pbpaste | ./scripts/token.sh" in saida
    assert "de novo para eu voltar a vigiar" in saida
    assert "Saida 3 = aguardando" in saida
    assert arquivo_passaporte(raiz_token).exists()
    assert (raiz_token / ".env").read_text(encoding="utf-8") == antes
    assert chamadas_ao_curl(raiz_token) == 0


SEGREDO_ALHEIO = "Senha-Que-Nao-E-Minha!2026#xyz-Q"  # 32 chars, como um token — de proposito


def test_v5_o_que_nao_casa_nao_vaza_em_lugar_nenhum(raiz_token):
    """V5 — privacidade. Na janela da vigia a pessoa copia uma senha e um trecho
    de e-mail antes de acertar. Nada dos dois pode sair: nem o conteudo, nem o
    tamanho ("N bytes" e o tamanho de um segredo alheio), nem em arquivo algum
    da raiz. O segredo tem 32 caracteres, a forma de um token, para que a
    assercao sobre o tamanho nao passe por acidente."""
    outro = "Rascunho-9f3k: reuniao adiada para quinta, avisar o pessoal"
    r = vigiar(raiz_token, {0: "", 2: SEGREDO_ALHEIO, 4: outro, 6: MARCADOR_PAYLOAD}, segundos=5)
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    for conteudo in (SEGREDO_ALHEIO, outro):
        assert conteudo not in saida, "ecoou conteudo que nao casou"
        assert conteudo[:8] not in saida, "ecoou o comeco de conteudo que nao casou"
        n = len(conteudo)
        assert f"{n} bytes" not in saida and f"{n} caracteres" not in saida, "disse o tamanho"
    assert saida.count("o clipboard mudou, mas o que veio nao comeca com") == 2
    assert "nao guardei, nao imprimi e nao digo o tamanho" in saida
    # Em disco: nada fora do proprio roteiro carrega o conteudo.
    for arquivo in raiz_token.rglob("*"):
        if arquivo.is_symlink() or not arquivo.is_file() or "clipboard" in arquivo.parts:
            continue
        assert SEGREDO_ALHEIO.encode() not in arquivo.read_bytes(), f"o segredo foi para {arquivo}"
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")


def test_v5b_dez_copias_erradas_nao_viram_dez_broncas(raiz_token):
    """V5b — a vigia ensina, mas nao insiste: tres avisos e depois silencio ate
    o acerto. Quem copia dez coisas seguidas le tres frases, nao dez."""
    passos = {0: ""}
    for i in range(1, 11):
        passos[i] = f"QZX-{i}-copia-que-nao-serve"
    passos[12] = MARCADOR_PAYLOAD
    r = vigiar(raiz_token, passos, segundos=8)
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert saida.count("o clipboard mudou, mas") == 3, "avisou mais (ou menos) que o teto"
    assert saida.count("daqui em diante so falo quando aparecer o endereco") == 1
    assert "QZX-" not in saida, "ecoou conteudo que nao casou"
    assert "Seguindo sozinho a partir daqui" in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")


def test_v6_sem_ferramenta_de_clipboard_nao_ha_vigia_e_o_fluxo_em_duas_etapas_segue(raiz_token, tmp_path):
    """V6 — portabilidade. Sem pbpaste/wl-paste/xclip (servidor sem interface)
    nao ha o que vigiar: o script diz isso, nao se anuncia de vigia, e cai no
    caminho de ontem — abre (aqui, com o `open` dublado), guarda o passaporte,
    sai 3 e diz para entregar por cano."""
    r = token_sh(
        raiz_token, "", path=path_minimo(tmp_path), clipboard=False,
        env={"DISPLAY": "", "WAYLAND_DISPLAY": "", "USP_MCP_VIGIA_SEGUNDOS": "90"},
    )
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "nao ha clipboard para vigiar" in saida
    assert "AVISO, antes de comecar" not in saida, "anunciou uma vigia que nao existe"
    assert not (raiz_token / "pbpaste.log").exists()
    assert len(aberturas(raiz_token)) == 1
    assert "pbpaste | ./scripts/token.sh" in saida
    assert "Saida 3 = aguardando" in saida
    assert arquivo_passaporte(raiz_token).exists()


def test_v6b_usp_mcp_vigia_segundos_zero_desliga_a_vigia_e_diz_isso(raiz_token):
    """V6b — o interruptor que o anuncio promete. Desligada, nenhuma leitura
    acontece e o fluxo em duas invocacoes segue como era."""
    r = abrir(raiz_token, env={"USP_MCP_VIGIA_SEGUNDOS": "0"})
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "vigia do clipboard desligada a pedido" in saida
    assert leituras(raiz_token) == 0
    assert "pbpaste | ./scripts/token.sh" in saida
    assert arquivo_passaporte(raiz_token).exists()


def test_v6c_limite_que_nao_e_numero_reprova_antes_de_abrir_qualquer_coisa(raiz_token):
    """V6c — Invariante 6: um valor errado na chave e erro legivel, nao uma
    vigia de duracao indefinida nem um navegador aberto a toa."""
    r = abrir(raiz_token, env={"USP_MCP_VIGIA_SEGUNDOS": "muito"})
    assert r.returncode == 2
    assert "USP_MCP_VIGIA_SEGUNDOS" in r.stderr
    assert aberturas(raiz_token) == []


def test_v7_base64_nu_nao_dispara_a_vigia(raiz_token):
    """V7 — o caminho por stdin aceita o base64 sem o esquema; a vigia NAO.
    Disparar nele obrigaria a decodificar qualquer coisa parecida com base64 que
    passe pelo clipboard, e o decodificador diz o tamanho ao recusar. De vigia,
    so a forma exata age; o base64 nu e "nao comeca com", sem tamanho."""
    antes = (raiz_token / ".env").read_text(encoding="utf-8")
    nu = payload(SITEID, WSTOKEN, PRIVATE)
    r = vigiar(raiz_token, {0: "", 2: nu}, segundos=2)
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "o clipboard mudou, mas o que veio nao comeca com" in saida
    assert "4/7" not in saida, "decodificou o base64 nu de vigia"
    assert nu[:8] not in saida
    assert f"{len(nu)} bytes" not in saida and f"{len(nu)} caracteres" not in saida
    assert (raiz_token / ".env").read_text(encoding="utf-8") == antes
    assert chamadas_ao_curl(raiz_token) == 0


def test_o_passaporte_guardado_e_gitignorado():
    """`.cache/` ja e ignorado por causa do userid; este teste prende que o
    passaporte mora la dentro e nao num caminho novo que alguem esqueca.
    A pergunta ao git mora em `tests.git.esta_ignorado`, e so la (G5)."""
    assert esta_ignorado(RAIZ / ".cache" / "passaporte", RAIZ), (
        ".cache/passaporte deixou de ser gitignorado"
    )


# ------------------------------- WSL: o leitor, que o lancador ja tinha resolvido
#
# A bateria W, e ela e estreita de proposito. O PR de 18/09 (`fix/windows`) poe o
# PowerShell como ULTIMO candidato a leitor, e para Git Bash isso esta certo: la
# nao ha `pbpaste`, `wl-paste` nem `xclip`, e o ultimo e o unico.
#
# No WSL nao. Sob WSLg — WSL2 com interface grafica, o padrao no Windows 11 —
# `$DISPLAY` vem preenchido e `xclip` PASSA, entao o leitor escolhido seria o do
# lado Linux enquanto a pessoa copia o endereco no navegador do WINDOWS: a vigia
# esperaria os 90 s por uma mudanca do outro lado, calada.
#
# O raciocinio ja estava escrito, e para o LANCADOR: o §4 daquele spec poe
# `wslview` na frente de `open` dizendo "com o WSLg, xdg-open abriria um navegador
# Linux, que nao esta logado na Senha Unica". Ele valia igual para o leitor, e
# faltava atravessar. O README daquele PR ja promete o comportamento certo — "no
# WSL ele le a area de transferencia do Windows pelo powershell.exe" —, entao o
# que estes testes prendem e a promessa que o codigo ainda nao cumpria.


def powershell_dublado(raiz):
    """Um `powershell.exe` de mentira que grava o argv e, no `Get-Clipboard`,
    entrega o roteiro de `clipboard_dublado` — o mesmo mecanismo do `pbpaste`."""
    binario = raiz / "bin-wsl"
    binario.mkdir(exist_ok=True)
    clipboard_dublado(raiz)  # escreve raiz/pbpaste.py, que o Get-Clipboard reusa
    falso = binario / "powershell.exe"
    falso.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{raiz / 'powershell.log'}'\n"
        "case \"$*\" in\n"
        f"  *Get-Clipboard*) exec '{sys.executable}' '{raiz / 'pbpaste.py'}' ;;\n"
        "esac\n"
    )
    falso.chmod(0o755)
    return binario


def wsl_com_sessao_grafica(raiz):
    """Uma maquina que parece WSLg: `xclip` e `wl-paste` presentes e funcionando,
    e o `powershell.exe` ao lado.

    Os dois primeiros existem de proposito. Sem eles o teste passaria por
    ausencia — o PowerShell seria escolhido porque nao havia outro — e nao
    provaria nada sobre a ORDEM, que e a correcao inteira.
    """
    binario = powershell_dublado(raiz)
    for nome in ("xclip", "wl-paste"):
        falso = binario / nome
        falso.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{raiz / f'{nome}.log'}'\n")
        falso.chmod(0o755)
    return binario


def linhas_do_log(raiz, nome) -> list[str]:
    log = raiz / f"{nome}.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def path_de_windows(raiz, tmp_path) -> str:
    """PATH controlado: os dubles do Windows, o `curl` registrado, e o minimo do
    sistema — SEM o `pbpaste` real desta maquina.

    O PATH do Mac que roda a suite tem `pbpaste` de verdade, e ele venceria a
    cadeia normal e faria o teste medir a maquina do desenvolvedor em vez do
    galho sob teste. Descoberto assim: a primeira versao do W2 herdava
    `os.environ['PATH']` por dentro do `curl_registrado`.
    """
    so_o_bin_do_curl = curl_registrado(raiz).split(":", 1)[0]
    return f"{wsl_com_sessao_grafica(raiz)}:{so_o_bin_do_curl}:{path_minimo(tmp_path)}"


def como_wsl(raiz, tmp_path, **kw):
    """Roda o script numa maquina que se anuncia como WSL, com sessao grafica.

    `WSL_DISTRO_NAME` e o sinal que o proprio WSL define — nao e uma porta dos
    fundos so para o teste. `DISPLAY`/`WAYLAND_DISPLAY` entram porque sem eles
    `xclip` e `wl-paste` seriam recusados pelo motivo errado, e o teste deixaria
    de ser sobre a ordem.
    """
    env = dict(kw.pop("env", None) or {})
    env.setdefault("WSL_DISTRO_NAME", "Ubuntu")
    env.setdefault("DISPLAY", ":0")
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    kw.setdefault("path", path_de_windows(raiz, tmp_path))
    kw.setdefault("clipboard", False)  # o `pbpaste` dublado venceria antes de tudo
    kw.setdefault("navegador", False)  # o lancador nao e o assunto desta bateria
    return token_sh(raiz, "", env=env, **kw)


def test_w1_no_wsl_o_leitor_e_o_do_windows_mesmo_com_xclip_disponivel(raiz_token, tmp_path):
    """W1 — a ordem, no lugar onde ela decide se a vigia espera pelo nada.

    `xclip` e `wl-paste` estao no PATH e a sessao grafica esta anunciada: o galho
    de cima PASSA. O que prova a correcao e o script preferir o do Windows
    mesmo assim.
    """
    r = como_wsl(raiz_token, tmp_path, env={"USP_MCP_VIGIA_SEGUNDOS": "2"})
    saida = r.stdout + r.stderr
    assert "vou LER o clipboard desta maquina (`powershell.exe`)" in saida, saida
    assert "(`xclip`)" not in saida
    assert linhas_do_log(raiz_token, "xclip") == [], "leu o clipboard do lado Linux"
    assert linhas_do_log(raiz_token, "wl-paste") == []


def test_w2_fora_do_wsl_o_xclip_continua_vencendo(raiz_token, tmp_path):
    """W2 — o par do W1, e o que impede a correcao de virar regressao.

    Num Linux comum com `xclip` e um `pwsh` instalado por acaso, o leitor tem de
    continuar sendo o `xclip` — que e o que o WIN3 do PR de 18/09 afirma para o
    Mac. Sem este teste, "preferir o PowerShell" poderia ter vazado para todo
    mundo e o W1 sozinho nao notaria.
    """
    # PATH sem o `bin/` da raiz de proposito: e la que mora o `pbpaste` dublado
    # (o `clipboard_dublado` o escreve, e o `powershell_dublado` o reusa para o
    # roteiro), e ele venceria a cadeia antes de `wl-paste` — deixando o teste
    # verde sem nunca exercer o galho grafico que ele afirma.
    r = token_sh(
        raiz_token,
        "",
        path=f"{wsl_com_sessao_grafica(raiz_token)}:{path_minimo(tmp_path)}",
        clipboard=False,
        navegador=False,
        env={"USP_MCP_VIGIA_SEGUNDOS": "2", "DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"},
    )
    saida = r.stdout + r.stderr
    assert "vou LER o clipboard desta maquina (`wl-paste`)" in saida, saida
    assert "(`powershell.exe`)" not in saida


def test_w4_no_wsl_a_vigia_le_pelo_windows_e_vai_ate_gravar(raiz_token, tmp_path):
    """W4 — o pedido inteiro pelo lado do Windows, numa invocacao.

    Tres segundos e nao um: o roteiro so muda na leitura 1, e uma janela curta
    demais encerraria a vigia antes — verde sem nunca ter lido, que e o oposto do
    que este teste afirma.
    """
    roteiro(raiz_token, {0: "coisa qualquer", 1: MARCADOR_PAYLOAD})
    r = como_wsl(raiz_token, tmp_path, env={"USP_MCP_VIGIA_SEGUNDOS": "3"})
    saida = r.stdout + r.stderr
    assert r.returncode == 0, saida
    assert "o clipboard mudou para algo que comeca com" in saida
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    leituras_win = [l for l in linhas_do_log(raiz_token, "powershell") if "Get-Clipboard" in l]
    assert leituras_win, "gravou sem ter lido pelo lado do Windows"
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"
    assert PRIVATE not in saida, "ecoou o privatetoken (§2.2)"


# --------------------------------------------- o passo 2 em etapas (18/09/2026)
#
# A bateria P. O bloco de instrucoes tinha 23 linhas e saia todo de uma vez,
# antes de a pessoa ter feito qualquer coisa. Uma terceira usuaria relatou, com
# estas palavras: "e MUITO texto que aparece quando ele e instalado, ninguem le".
#
# Sete dessas linhas nao eram do caminho feliz — o plano B do DevTools, que so
# interessa quando a pagina NAO renderiza, e o aviso do `urlscheme=http`,
# enderecado a quem edita a URL a mao. As duas sairam para
# `dicas_quando_a_pagina_nao_coopera`, e o que prende a mudanca sao os dois lados:
# que elas NAO aparecem no caminho feliz, e que elas APARECEM quando deu errado.
# Sem o segundo, "tirar do caminho feliz" e indistinguivel de "apagar".


def test_p1_o_caminho_feliz_nao_carrega_as_dicas_de_quando_da_errado(raiz_token):
    """P1 — o que saiu de cena, e a ordem do que ficou.

    A assercao olha o BLOCO DO PASSO 2, do inicio ate o `3/7`, e nao a saida
    inteira: esta invocacao termina com a vigia vencendo, que e um "deu errado" e
    por isso imprime as dicas de proposito (P2). Sem o corte, o teste procuraria o
    texto na saida onde ele DEVE estar e ficaria vermelho pelo motivo errado.
    """
    r = abrir(raiz_token)
    saida = r.stdout + r.stderr
    corte = saida.find("3/7")
    assert corte > 0, saida
    bloco = saida[:corte]
    assert "DevTools" not in bloco, "o plano B voltou para o caminho feliz"
    assert "urlscheme=http" not in bloco, "o aviso de editar a URL voltou ao caminho feliz"
    # As tres acoes, na ordem em que a pessoa as executa.
    passos = [
        saida.find("abra esta URL no navegador"),
        saida.find("na pagina, ache o link azul"),
        saida.find("copie o ENDERECO dele, sem clicar"),
    ]
    assert all(p >= 0 for p in passos), f"sumiu um dos tres passos: {passos}\n{saida}"
    assert passos == sorted(passos), f"os passos sairam fora de ordem: {passos}"


def test_p2_as_dicas_aparecem_quando_a_vigia_encerra_sem_o_endereco(raiz_token):
    """P2 — o par do P1, e o que separa "moveu" de "apagou"."""
    r = vigiar(raiz_token, {0: ""}, segundos=1)
    saida = r.stdout + r.stderr
    assert r.returncode == SAIDA_AGUARDANDO, saida
    assert "DevTools" in saida, saida
    assert "urlscheme=http" in saida


def test_p3_as_dicas_aparecem_quando_o_que_chegou_nao_tem_a_forma(raiz_token):
    """P3 — o outro momento: veio alguma coisa, e ela nao e o endereco.

    Diferente do P2 de proposito: aqui a pessoa CHEGOU a copiar algo, e a
    hipotese mais provavel passa a ser a pagina que nao renderizou.
    """
    r = token_sh(raiz_token, "isto nao e um endereco de token")
    saida = r.stdout + r.stderr
    assert "NAO comeca com" in saida, saida
    assert "DevTools" in saida


def test_p4_sem_terminal_nao_ha_parada_nenhuma(raiz_token):
    """P4 — a parada e para PESSOA. Um agente de codigo roda sem tty, e um `read`
    ali travaria o script ate o timeout de quem o chamou — que e um jeito caro de
    descobrir que a parada nao sabia distinguir os dois casos."""
    r = abrir(raiz_token)
    saida = r.stdout + r.stderr
    assert "[Enter]" not in saida, "pediu Enter a quem nao tem terminal"


def test_p5_no_terminal_as_paradas_existem_e_o_fluxo_chega_ao_fim(raiz_token):
    """P5 — o outro lado do P4, com pty de verdade.

    Duas paradas, uma por acao que a pessoa executa fora do terminal, e o fluxo
    inteiro ainda terminando em token gravado.
    """
    ambiente = {k: v for k, v in os.environ.items() if k not in ("SSH_CONNECTION", "SSH_TTY")}
    clipboard_dublado(raiz_token)
    ambiente["PATH"] = f"{navegador_dublado(raiz_token)}:{curl_dublado(raiz_token, JSON_OK)}"
    ambiente["TERM"] = "dumb"

    def responder(texto: str) -> str:
        return payload_para(passaporte_da_url(texto))

    saida, codigo = _rodar_com_tty(raiz_token, ambiente, responder)

    assert codigo == 0, saida
    assert saida.count("[Enter]") == 2, f"esperava DUAS paradas:\n{saida}"
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
    assert WSTOKEN not in saida, "ecoou o token (Invariante 3)"


def test_p6_usp_mcp_sem_pausa_desliga_as_paradas(raiz_token):
    """P6 — a saida para quem ja sabe o caminho e roda isto pela quinta vez.

    Mesma forma das outras chaves do script (`USP_MCP_NAO_ABRIR`,
    `USP_MCP_VIGIA_SEGUNDOS`): desliga o comportamento novo sem tirar o passo.
    """
    ambiente = {k: v for k, v in os.environ.items() if k not in ("SSH_CONNECTION", "SSH_TTY")}
    clipboard_dublado(raiz_token)
    ambiente["PATH"] = f"{navegador_dublado(raiz_token)}:{curl_dublado(raiz_token, JSON_OK)}"
    ambiente["TERM"] = "dumb"
    ambiente["USP_MCP_SEM_PAUSA"] = "1"

    def responder(texto: str) -> str:
        return payload_para(passaporte_da_url(texto))

    saida, codigo = _rodar_com_tty(raiz_token, ambiente, responder)

    assert codigo == 0, saida
    assert "[Enter]" not in saida, "parou mesmo com USP_MCP_SEM_PAUSA=1"
    assert "na pagina, ache o link azul" in saida, "desligar a parada comeu o passo"
    assert f"MOODLE_TOKEN={WSTOKEN}\n" in (raiz_token / ".env").read_text(encoding="utf-8")
