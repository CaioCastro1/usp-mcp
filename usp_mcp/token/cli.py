"""Obtem o MOODLE_TOKEN e grava no .env — o §8 do SPEC1.md virado chamador.

Uso:  ./scripts/token.sh              # guiado, interativo
      usp-mcp-token                   # o mesmo, sem bash — e o comando do Windows
      pbpaste | ./scripts/token.sh    # se voce ja copiou a URL do redirect
      powershell -NoProfile -Command Get-Clipboard | ./scripts/token.sh   # o mesmo, no Git Bash
      Get-Clipboard | usp-mcp-token   # o mesmo, no PowerShell
      ./scripts/token.sh --sobrescrever   # trocar token que ja funciona, sem perguntar
      ./scripts/token.sh --auto           # tenta capturar o redirect sozinho (ver abaixo)
      ./scripts/token.sh --navegador="Google Chrome"   # so com --auto
      USP_MCP_NAO_ABRIR=1 ./scripts/token.sh           # nunca abre navegador
      USP_MCP_VIGIA_SEGUNDOS=0 ./scripts/token.sh      # nao vigia o clipboard (ver abaixo)
      USP_MCP_SEM_PAUSA=1 ./scripts/token.sh           # sem as paradas do passo 2

Tudo o que vale para `./scripts/token.sh` vale para `usp-mcp-token`: sao o mesmo
programa. O script bash e um involucro que acha o Python do venv e chama
`python -m usp_mcp.token` repassando argumentos, stdin e codigo de saida.

Em UMA invocacao sem terminal, que e como um agente de codigo roda isto:

      ./scripts/token.sh              # abre o navegador e FICA DE VIGIA no clipboard

Abre a pagina certa e, por ate 90 s, le o clipboard a cada 0,5 s esperando ele
MUDAR para algo que comece com `moodlemobile://token=`. Quando muda, segue
sozinho ate gravar; se a pessoa copiar a coisa errada, o script diz o que veio
errado e continua esperando. O que ja estava no clipboard nao conta, e o que
nao tem a forma certa nao e guardado, impresso nem medido. A vigia e anunciada
antes de comecar, no texto que a pessoa le. Sem pbpaste/wl-paste/xclip/PowerShell
(ou em sessao SSH, onde o clipboard alcancavel e o da maquina remota) nao ha
vigia, e o script cai no fluxo em DUAS invocacoes, que continua existindo:

      ./scripts/token.sh              # abre o navegador na pagina certa e sai com 3
      pbpaste | ./scripts/token.sh    # depois que a pessoa copiou o endereco do link

A primeira guarda o passaporte em .cache/passaporte (ao lado do .env, 0600) por
10 minutos; a segunda o reaproveita, e a conferencia do passo 5 continua valendo
entre as duas. Saida 3 = "aguardando o payload", nao erro: nada foi gravado. A
vigia que encerra sem o endereco sai do mesmo jeito, com 3.

Windows (desde 18/09/2026): nao precisa de bash. `pip install -e .` instala o
comando `usp-mcp-token` em `.venv\\Scripts\\usp-mcp-token.exe`, e ele e este
modulo. O que muda e o candidato de cada escolha: o clipboard vem do PowerShell
(`Get-Clipboard`), o navegador abre por `wslview` (WSL) ou `rundll32`, e a
chamada a USP vai pelo `curl.exe` que o Windows 10 traz. A ESCOLHA esta testada
com dubles no PATH (tests/moodle/test_token_windows.py); o comportamento num
Windows real NAO foi medido pelos autores. O que conferir esta em
docs/superpowers/specs/2026-09-18-windows-design.md (§6) e em
docs/superpowers/specs/2026-09-18-token-em-python-design.md.

Sete passos, na ordem em que estao no desenho de 10/09/2026
(docs/superpowers/specs/2026-09-10-script-token-moodle-design.md):

  1. prepara o .env            5. decodifica EM MEMORIA
  2. gera um passaporte        6. confirma o token contra a USP (1 chamada)
  3. pega o redirect           7. grava so os 32 hex no .env
  4. (manual por padrao)

O PADRAO e o caminho manual, e ele esta MEDIDO contra o e-Disciplinas (§9,
11/09/2026): com `confirmed=1` o Moodle nao redireciona, mostra uma pagina com
um link, e o endereco DESSE link e o token — "botao direito -> copiar endereco"
no lugar do DevTools. Leva ~20 s.

Duas fricoes desse passo foram MEDIDAS numa passagem real de um segundo usuario
em 12/09/2026, e o passo 3 as trata: (a) a pagina tem tres elementos e nenhum
parece um token, entao o script cita o texto do link em voz alta e avisa para
NAO clicar nele — clicar tenta abrir o app e nao copia nada; (b) nao havia como
conferir o clipboard antes de entregar, entao o script confere sozinho e
reconhece o erro nº 1, que e colar a URL do proprio launch.php.

`--auto` tenta antes a captura de scripts/_capturar_redirect.sh, que registra um
handler para um esquema nosso e recebe o redirect direto do navegador. Ela
funciona contra duble e NUNCA entregou contra a USP — por isso nao e o padrao.
Se nao entregar em 120 s, cai no manual sozinha.

Tres coisas que este script nao faz, de proposito:

  - Nunca imprime o valor do token, nem parcial (Invariante 3). O diagnostico
    fala de forma — quantos caracteres, quantas partes, confere ou nao.
  - Nunca grava o base64 cru no disco. Ele carrega o `privatetoken`, que
    habilita `tool_mobile_get_autologin_key` (bloqueio permanente do §2.2) —
    decodificar antes de escrever e o que impede o valor de existir em arquivo.
  - Nunca passa o token em argv. `ps aux` e legivel por qualquer processo do
    usuario; o passo 6 manda o campo por `curl -K -`, que le do stdin. Medido
    em 10/09/2026 contra um servidor local: o campo chega no corpo do POST. Em
    Python isso vale por construcao: o valor e uma variavel local, e o unico
    processo que o recebe e o curl, pelo stdin.

Nao renova token expirado sem navegador: `launch.php` autentica por sessao, e
o §1.3 registra que senha nao serve (SSO). Nao trata o token de `Attendance`.

Este modulo e o PORTE do scripts/token.sh de 18/09/2026, que tinha 875 linhas
de bash. Os sete passos, os comentarios e as mensagens vieram como estavam; o
que mudou de forma esta dito no proprio lugar. Os testes que exercitavam o
script (tests/moodle/test_token_*.py) continuam exercitando-o, atraves do
involucro, sem alteracao de asseracao.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from usp_mcp.token.decodificar import FormaErrada, analisar

# usp_mcp/token/cli.py -> sobe tres niveis ate a raiz do checkout (ou do
# worktree). E a mesma conta que usp_mcp/env.py faz, e tem de ser: o `.env`, o
# `.env.example` e o `scripts/_capturar_redirect.sh` sao achados a partir daqui,
# e o bash fazia `cd "$(dirname "$0")/.."` pelo mesmo motivo.
RAIZ = Path(__file__).resolve().parents[2]

FN = "core_webservice_get_site_info"

# Saida da invocacao que ABRE o navegador e para, aguardando o payload. Nao e 0:
# nada foi gravado, e 0 diria "token configurado" para quem so le o codigo — o
# falso sucesso do Invariante 6. Nao e 1: nao e erro. Mesmo molde do
# SAIDA_SEM_SUITE do gate.sh.
SAIDA_AGUARDANDO = 3

# Quanto tempo um passaporte guardado vale, em segundos. O porque esta no passo 2.
VALIDADE_PASSAPORTE = 600

# A forma que o clipboard tem de ter para o script AGIR sobre ele. Tudo depois
# de `token=` e a credencial; o prefixo e publico e e o unico pedaco do valor que
# alguma mensagem deste script pode citar.
ESQUEMA = "moodlemobile://token="

# Quantas vezes a vigia avisa sobre conteudo que NAO e o endereco antes de
# calar. Tres: o primeiro aviso ensina, o segundo confirma que a pessoa ainda
# esta tentando, o terceiro diz que vai calar. Depois disso quem copia dez coisas
# seguidas nao recebe dez broncas, e o unico evento que ainda fala e o acerto.
MAX_AVISOS_VIGIA = 3

# Os nomes que o PowerShell pode ter no PATH. Com `.exe` porque no WSL o Linux
# nao completa a extensao; sem ela porque o Git Bash completa; `pwsh` e o
# PowerShell 7, que a pessoa pode ter instalado. A ordem e a do token.sh.
LEITORES_POWERSHELL = ("powershell.exe", "powershell", "pwsh.exe", "pwsh")


@dataclass
class Rodada:
    """O que o bash guardava em variaveis globais: as flags, o que o passo 1
    descobriu sobre o .env, e o passaporte do passo 2."""

    tty: bool
    # --sobrescrever: trocar um token que ja funciona sem a pergunta do passo 1.
    # Existe porque `pbpaste | ./scripts/token.sh` nao tem terminal para perguntar.
    sobrescrever: bool = False
    # --manual: pular a captura automatica e colar a URL do redirect a mao.
    # O PADRAO E O MANUAL, por decisao de 11/09/2026 (§9). A captura automatica
    # funciona contra duble e NUNCA foi verificada contra o e-Disciplinas: tres
    # tentativas reais, tres falhas antes de o navegador entregar o redirect. Deixa-la
    # ligada por padrao custaria 120 s de espera em toda execucao, num caminho que
    # pode nem existir neste site (`forcedurlscheme`, linha 111, nao e observavel de
    # fora). O manual leva ~20 s e esta medido. `--auto` tenta a captura primeiro.
    manual: bool = True
    # --navegador="Google Chrome": abrir num navegador especifico. Vale so com --auto.
    # Medido: o Chrome pede confirmacao e o padrao do sistema nao.
    navegador: str = ""
    # Quanto tempo a vigia do clipboard dura, em segundos. 0 desliga e volta ao fluxo
    # em duas invocacoes. O porque dos 90 esta junto da vigia, no passo 3.
    vigia_segundos: int = 90

    env_file: Path | None = None
    moodle_url: str = ""
    # O cache mora junto do .env, pelo mesmo motivo: e o checkout que o projeto usa.
    # Gitignorado (`.cache/`). Guarda o userid (passo 7) e, por ate 10 min, o
    # passaporte da rodada em andamento (passo 2).
    cache_dir: Path | None = None
    arq_passaporte: Path | None = None

    passaporte: str = ""
    pass_guardado: str = ""
    pass_idade: int | None = None
    pass_velho: int | None = None

    # Qual ferramenta le o clipboard DESTA maquina. Vazio = nenhuma.
    clip: str = ""


# ------------------------------------------------------------------ a saida


def _preparar_saida() -> None:
    """Linha a linha, como o bash: quem le pelo cano (um agente) ve o anuncio da
    vigia ANTES da primeira leitura, e nao tudo de uma vez no fim. `errors=
    "replace"` porque o console do Windows pode nao ter os caracteres de algumas
    mensagens (o `…`, o travessao), e uma mensagem com `?` no lugar e melhor que
    um UnicodeEncodeError no meio do passo 3."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(line_buffering=True, errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def titulo(texto: str) -> None:
    print(f"\n\033[1m{texto}\033[0m")


def nota(texto: str) -> None:
    print(f"   {texto}")


def aviso(texto: str) -> None:
    print(f"   \033[33m! {texto}\033[0m")


def erro(texto: str) -> None:
    """`echo ... >&2`."""
    print(texto, file=sys.stderr)


def _ler_linha_do_terminal() -> str:
    """`IFS= read -r x < /dev/tty`. Onde nao ha /dev/tty (Windows), o stdin E o
    terminal — quem chama ja conferiu `[ -t 0 ]`."""
    try:
        with open("/dev/tty", encoding="utf-8", errors="replace") as tty:
            return tty.readline().rstrip("\n")
    except OSError:
        return sys.stdin.readline().rstrip("\n")


def _ler_segredo_do_terminal(prompt: str) -> str:
    """`printf prompt; IFS= read -rs valor < /dev/tty`: sem eco, e o Enter final
    vai para a tela como o `printf '\\n'` do bash fazia. `getpass` faz isso nos
    dois sistemas — /dev/tty com o eco desligado no Unix, `msvcrt` no Windows.

    O prompt vai POR ELE, e nao por um `print` antes, de proposito: o getpass
    desliga o eco e so depois escreve o prompt. Em bash havia uma janela entre o
    `printf` e o `read -s` em que um payload colado depressa demais ecoaria no
    terminal; aqui ela nao existe.
    """
    try:
        return getpass.getpass(prompt)
    except EOFError:
        return ""


# Uma parada curta entre dois passos do caminho manual. So existe quando ha uma
# PESSOA no terminal: sem tty (um agente rodando o script) nao ha Enter para
# esperar, e o texto sai inteiro na ordem, para o agente repassar um passo por
# mensagem. `USP_MCP_SEM_PAUSA=1` desliga, para quem ja sabe o caminho.
#
# A marca `[Enter]` no texto e o que a suite reconhece para responder (o arnes de
# pty em tests/moodle/test_token_navegador.py); o prompt do passo 3 nao a usa,
# porque la o que se digita e o payload e nao uma linha em branco.
def pausar(r: Rodada, mensagem: str) -> None:
    if not r.tty:
        return
    if os.environ.get("USP_MCP_SEM_PAUSA", "0") == "1":
        return
    print(f"\n   {mensagem} ", end="", flush=True)
    _ler_linha_do_terminal()
    print()


# ------------------------------------------------------- clipboard e navegador


# Estamos dentro do WSL? Sem spawn de processo, entao pode ser chamada a vontade.
# `WSL_DISTRO_NAME` e definido pelo proprio WSL e e o sinal que a suite usa para
# dirigir o teste; o `osrelease` cobre o shell que nasceu sem esse ambiente.
def e_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        osrelease = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "microsoft" in osrelease.lower()


def _primeiro_no_path(candidatos: tuple[str, ...]) -> str:
    for candidato in candidatos:
        if shutil.which(candidato):
            return candidato
    return ""


# Qual ferramenta le o clipboard DESTA maquina. Vazio = nenhuma, e sem ela nao
# ha vigia. `wl-paste` e `xclip` so contam com a sessao grafica que eles exigem:
# num servidor sem interface eles existem no PATH e falham, e "existe" mentiria.
#
# Windows (Git Bash ou WSL) nao tem nenhum dos tres. O que tem e o PowerShell,
# que vem com o sistema e le o clipboard com `Get-Clipboard`. Ele e o ULTIMO
# candidato: onde um dos tres existe e funciona, o leitor e o de sempre. No WSL
# o `powershell.exe` alcanca o clipboard do Windows, que e onde a pessoa copiou
# o link. A escolha esta testada com dubles no PATH (WIN1-3); o Get-Clipboard de
# verdade nao foi medido pelos autores (18/09/2026).
# ULTIMO candidato, porem, vale em Git Bash e NAO vale no WSL, e a diferenca e a
# correcao de 18/09 (§9): sob WSLg — o WSL2 com interface grafica, padrao no
# Windows 11 — `$DISPLAY` vem preenchido e `xclip` PASSA no teste acima. O leitor
# escolhido seria entao o do lado Linux, enquanto a pessoa copia o endereco no
# navegador do WINDOWS: a vigia esperaria os 90 s inteiros por uma mudanca que
# acontece do outro lado, calada. E o MESMO raciocinio que ja pos `wslview` na
# frente de `open` no lancador (spec de 18/09, §4, "com o WSLg, xdg-open abriria
# um navegador Linux") — ele valia para o leitor tambem, e faltava atravessar.
#
# Em Python isto e uma tabela por sistema e nao uma cadeia de `command -v`, mas
# a ORDEM e a mesma do bash, e e ela que os testes WIN1-3 e W1-W4 prendem.
def achar_leitor_de_clipboard() -> str:
    if e_wsl():
        clip = _primeiro_no_path(LEITORES_POWERSHELL)
        # Sem interop (o `/etc/wsl.conf` permite desliga-lo) nao ha o que preferir, e
        # cair na cadeia normal e melhor que nao ter leitor nenhum.
        if clip:
            return clip
    if shutil.which("pbpaste"):
        return "pbpaste"
    if shutil.which("wl-paste") and os.environ.get("WAYLAND_DISPLAY"):
        return "wl-paste"
    if shutil.which("xclip") and os.environ.get("DISPLAY"):
        return "xclip"
    return _primeiro_no_path(LEITORES_POWERSHELL)


# Le o clipboard. Falha (clipboard vazio no X11 devolve erro) vira vazio:
# vazio nao e conteudo, e a vigia o ignora.
#
# PowerShell: `-NoProfile` pula o perfil da pessoa, que e o que mais custa no
# arranque de cada leitura. O Get-Clipboard termina a linha em CRLF; o `\r` sai
# aqui para que a comparacao com o marco e a checagem do prefixo vejam o mesmo
# texto que um `pbpaste` devolveria.
#
# O `$(...)` do bash descartava as quebras de linha finais do que a ferramenta
# imprimia; o `rstrip("\n")` faz o mesmo, para que o marco e as leituras sejam
# comparados como eram.
def ler_clipboard(clip: str) -> str:
    if clip == "pbpaste":
        comando = ["pbpaste"]
    elif clip == "wl-paste":
        comando = ["wl-paste"]
    elif clip == "xclip":
        comando = ["xclip", "-selection", "clipboard", "-o"]
    elif clip in LEITORES_POWERSHELL:
        comando = [clip, "-NoProfile", "-Command", "Get-Clipboard"]
    else:
        return ""
    try:
        p = subprocess.run(
            comando,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
    except OSError:
        return ""
    saida = p.stdout
    if clip in LEITORES_POWERSHELL:
        saida = saida.replace("\r", "")
    return saida.rstrip("\n")


def aparar(texto: str) -> str:
    """Sem espaco/quebra de linha nas pontas."""
    return texto.strip()


def tem_a_forma(texto: str) -> bool:
    return texto.startswith(ESQUEMA)


def _md5(texto: str) -> str:
    return hashlib.md5(texto.encode()).hexdigest()


# O endereco responde ao passaporte DESTA rodada? Decodifica em memoria,
# pela mesma regra do passo 4, e compara o siteid com md5(wwwroot+passaporte)
# — a mesma formula do passo 5. Nada e impresso: a recusa do decodificador e
# engolida, porque aqui a pergunta e "e desta rodada?", nao "esta certo?".
def payload_e_desta_rodada(r: Rodada, endereco: str) -> bool:
    try:
        siteid, _wstoken, _partes = analisar(endereco)
    except FormaErrada:
        return False
    return bool(siteid) and siteid == _md5(r.moodle_url + r.passaporte)


# A vigia. Le o clipboard a cada 0,5 s por ate `segundos` e devolve o valor
# quando ele MUDAR para algo que comece com ESQUEMA; devolve None quando o
# tempo acaba. Quatro regras, e cada uma tem um motivo:
#
#   1. Privacidade. Vigiar e ler o clipboard repetidamente, e nessa janela a
#      pessoa pode copiar uma senha. O script so AGE sobre conteudo com a forma
#      exata; tudo o mais fica numa variavel, e comparado com a leitura anterior
#      e descartado. Nao vai para disco, nao e impresso, nao e contado — nem em
#      "N bytes", que e o tamanho de um segredo alheio. Base64 nu, que o caminho
#      por stdin aceita, NAO dispara a vigia: dispararia em qualquer coisa
#      parecida com base64, e o decodificador diria o tamanho ao recusar.
#   2. Clipboard velho. O que ja esta la quando a vigia comeca e o MARCO, nao um
#      achado: a URL de uma tentativa anterior dispararia na hora e daria um
#      passaporte que nao bate. So mudanca conta. Uma excecao, e ela e conferida:
#      se o marco ja tem a forma certa E responde ao passaporte desta rodada (que
#      pode ter sido reaproveitado de uma vigia que venceu), ele E desta rodada.
#   3. Tempo. Quem chama e um agente com teto por chamada (120 s por padrao no
#      Claude Code), e uma vigia infinita estoura o teto e deixa o agente sem
#      resposta nenhuma — o pior desfecho (Invariante 6). 90 s: o passo manual
#      leva ~20 s medidos, e sobram 30 s para o arranque, o `open` (ate 2 s), a
#      decodificacao, a chamada a USP e a gravacao, mesmo quando o acerto vem no
#      ultimo tique. Ajustavel por USP_MCP_VIGIA_SEGUNDOS; 0 desliga.
#   4. Forma errada ensina e segue. O erro nº 1 medido e copiar a URL da propria
#      pagina; hoje ele mata a tentativa. Aqui ele vira uma frase e a vigia
#      continua. Com teto: MAX_AVISOS_VIGIA avisos e depois silencio, para que
#      dez copias seguidas nao virem dez broncas.
def vigiar_clipboard(r: Rodada, segundos: int) -> str | None:
    marco = ler_clipboard(r.clip)
    t = aparar(marco)
    if tem_a_forma(t):
        if payload_e_desta_rodada(r, t):
            nota("o clipboard JA tinha um endereco com a forma certa, e ele responde ao")
            nota("passaporte DESTA rodada: e o da pagina que esta aberta. Seguindo sem esperar.")
            return t
        nota("o clipboard ja tinha um endereco com a forma certa, mas de OUTRA rodada (o")
        nota("passaporte nao bate). Ele fica como marco: so uma MUDANCA conta.")
    avisos = 0
    for _ in range(segundos * 2):
        time.sleep(0.5)
        leitura = ler_clipboard(r.clip)
        if leitura == marco:
            continue
        marco = leitura
        t = aparar(leitura)
        if not t:
            continue
        if tem_a_forma(t):
            nota(f"o clipboard mudou para algo que comeca com `{ESQUEMA}`: e o endereco do link.")
            nota("Seguindo sozinho a partir daqui.")
            return t
        avisos += 1
        if avisos > MAX_AVISOS_VIGIA:
            continue
        if "launch.php" in t or t.startswith(("http://", "https://")):
            # O caso medido (12/09/2026), e o unico em que da para dizer o que houve.
            aviso("o clipboard mudou, mas veio a URL de IDA — a da PAGINA — e nao a de VOLTA.")
            nota("As duas sao URLs, por isso se confundem; so a segunda carrega o token.")
            nota("BOTAO DIREITO no link azul 'Clique aqui se a aplicacao nao abrir")
            nota("automaticamente' -> 'Copiar endereco do link'. Nao clique com o esquerdo.")
            nota("Continuo de vigia; nada foi gravado.")
        else:
            aviso(f"o clipboard mudou, mas o que veio nao comeca com `{ESQUEMA}`.")
            nota("Ignorado: nao guardei, nao imprimi e nao digo o tamanho. Continuo de vigia.")
        if avisos == MAX_AVISOS_VIGIA:
            nota(f"Foram {MAX_AVISOS_VIGIA} avisos; daqui em diante so falo quando aparecer o endereco")
            nota("certo. Sigo de vigia ate o tempo acabar.")
    return None


# As duas saidas de emergencia do passo 2. Elas ficavam no caminho feliz, antes de
# a pessoa ter feito qualquer coisa, e somavam 7 das 23 linhas do bloco: o plano B
# do DevTools so interessa quando a pagina NAO renderiza, e o aviso do
# `urlscheme=http` e enderecado a quem edita a URL a mao, coisa que ninguem
# seguindo o script faz. Agora aparecem quando "deu errado" e fato e nao hipotese.
def dicas_quando_a_pagina_nao_coopera() -> None:
    nota("")
    nota("Se a pagina nao apareceu e o navegador tentou abrir um app, o caminho e o")
    nota("DevTools (Cmd+Opt+I) -> aba Network -> a linha bloqueada para")
    nota("`moodlemobile://token=…` e o que copiar.")
    nota("Se voce editou a URL a mao: nao troque por urlscheme=http. Nessa forma o")
    nota("base64 cai na posicao de host da URL, o Chrome minusculiza host, e base64 e")
    nota("sensivel a caixa — o token chega corrompido COM A FORMA CERTA (§1.3).")


# A saida da abertura que NAO chegou ao payload: diz o que sobra para a pessoa
# e como entregar, e sai com SAIDA_AGUARDANDO. Usada pela vigia que venceu e
# pela maquina onde nao ha vigia.
def sair_aguardando(r: Rodada) -> None:
    nota("O proximo passo e da PESSOA, na pagina que acabou de abrir (ou na URL acima):")
    nota("  botao DIREITO no link azul 'Clique aqui se a aplicacao nao abrir")
    nota("  automaticamente' -> 'Copiar endereco do link'. Nao clique com o esquerdo.")
    nota("Com o endereco no clipboard, rode:")
    nota("  pbpaste | ./scripts/token.sh")
    nota("  (Linux: wl-paste | ./scripts/token.sh  ou  xclip -selection clipboard -o | ./scripts/token.sh)")
    nota("  (Windows, no Git Bash ou WSL: powershell -NoProfile -Command Get-Clipboard | ./scripts/token.sh)")
    nota("  (Windows, no PowerShell: Get-Clipboard | usp-mcp-token)")
    nota("Ou rode ./scripts/token.sh de novo para eu voltar a vigiar o clipboard.")
    nota("Se passou --sobrescrever agora, passe de novo.")
    nota(f"O passaporte desta rodada esta em {r.arq_passaporte} por {VALIDADE_PASSAPORTE}s e")
    nota("serve uma vez: a proxima invocacao o reaproveita e a conferencia do passo 5 fecha.")
    nota("Nada foi gravado — o .env so muda depois de o token autenticar no passo 6.")
    nota(f"Saida {SAIDA_AGUARDANDO} = aguardando o payload, nao erro.")
    raise SystemExit(SAIDA_AGUARDANDO)


# Abre a URL no navegador padrao e DIZ o que aconteceu. Nunca derruba o script:
# nao conseguir abrir e um aviso com a cura (abra a URL a mao), nao um erro.
#
# Em segundo plano, com espera limitada. O _capturar_redirect.sh mediu em 11/09
# que `open` NAO retorna enquanto o navegador tem um dialogo modal aberto — um
# `open` sincrono aqui prenderia o script. Mas so disparar e seguir mentiria numa
# maquina sem sessao grafica, onde o `open` falha calado: por isso espera ate 2 s
# e reporta as tres saidas possiveis (voltou bem, falhou, ainda pendurado).
def abrir_navegador(url: str) -> None:
    if os.environ.get("USP_MCP_NAO_ABRIR", "0") == "1":
        nota("USP_MCP_NAO_ABRIR=1: nao abri navegador nenhum. Abra a URL acima a mao.")
        return
    # Numa sessao SSH o navegador que `open` alcanca e o da maquina REMOTA, e a
    # pessoa esta na local. Abrir la seria pior que nao abrir: a pagina apareceria
    # numa tela que ninguem esta olhando, logada em quem sabe que conta.
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        aviso("sessao SSH: um navegador aberto daqui abriria na maquina remota, nao na sua.")
        nota("Abra a URL acima no navegador da SUA maquina, logado na Senha Unica.")
        return
    # A ordem, e o porque de cada posicao:
    #   - `wslview` primeiro: so existe no WSL, e la e o unico que abre o navegador
    #     do WINDOWS, que e onde a pessoa esta logada na Senha Unica. Tem de vir
    #     antes do `open` porque no Ubuntu `/usr/bin/open` e o `openvt` do console
    #     (pacote kbd), que nao abre URL nenhuma — e antes do `xdg-open` porque,
    #     com o WSLg, este abriria um navegador Linux, que nao esta logado.
    #   - `open` e `xdg-open` como sempre foram.
    #   - `rundll32` por ultimo: e o ShellExecute do Windows por linha de comando,
    #     existe em todo Windows e recebe a URL como ARGUMENTO — sem passar pelo
    #     `cmd.exe /c start`, que trataria o `&` da URL como separador de comando.
    #     E o caminho do Git Bash, do WSL sem wslview, e do PowerShell. Com `.exe`
    #     primeiro pelo mesmo motivo do leitor de clipboard.
    # A escolha esta testada com dubles (WIN6); abrir de verdade em Windows nao
    # foi medido pelos autores (18/09/2026).
    if shutil.which("wslview"):
        lancador = "wslview"
    elif shutil.which("open"):
        lancador = "open"
    elif shutil.which("xdg-open") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        lancador = "xdg-open"
    elif shutil.which("rundll32.exe"):
        lancador = "rundll32.exe"
    elif shutil.which("rundll32"):
        lancador = "rundll32"
    else:
        aviso("nao ha como abrir navegador desta maquina (sem `open`/`xdg-open`/`wslview`/`rundll32`, ou sem sessao grafica).")
        nota("Abra a URL acima onde voce tem um navegador logado na Senha Unica.")
        return
    if lancador.startswith("rundll32"):
        comando = [lancador, "url.dll,FileProtocolHandler", url]
    else:
        comando = [lancador, url]
    try:
        processo = subprocess.Popen(
            comando, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except OSError:
        aviso(f"`{lancador}` falhou ao abrir a URL — sem sessao grafica, ou sem navegador padrao.")
        nota("Abra a URL acima a mao, num navegador logado na Senha Unica.")
        return
    try:
        codigo = processo.wait(timeout=2)
    except subprocess.TimeoutExpired:
        nota(f"chamei `{lancador}` e ele ainda nao voltou depois de 2 s — costuma ser um")
        nota("dialogo modal esquecido no navegador. Feche-o; se a pagina nao aparecer,")
        nota("abra a URL acima a mao. Seguindo sem esperar.")
        return
    if codigo == 0:
        nota(f"abri a URL no navegador padrao (`{lancador}`).")
    else:
        aviso(f"`{lancador}` falhou ao abrir a URL — sem sessao grafica, ou sem navegador padrao.")
        nota("Abra a URL acima a mao, num navegador logado na Senha Unica.")


# ---------------------------------------------------------------- o passaporte


# Le .cache/passaporte. Deixa em pass_guardado o passaporte se o arquivo estiver
# integro e dentro da validade (e a idade em pass_idade); senao pass_guardado fica
# vazio, pass_velho guarda a idade do que venceu (quando foi isso), e o arquivo e
# removido. Forma esperada: `passaporte=<digitos>` e `criado=<epoch>`. Qualquer
# outra coisa e lixo e sai do caminho — isto e material de sessao, nao estado que
# mereca conserto.
def carregar_passaporte_guardado(r: Rodada) -> None:
    assert r.arq_passaporte is not None
    if not r.arq_passaporte.is_file():
        return
    p = c = ""
    try:
        linhas = r.arq_passaporte.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for linha in linhas:
        if linha.startswith("passaporte=") and not p:
            p = linha[len("passaporte="):]
        elif linha.startswith("criado=") and not c:
            c = linha[len("criado="):]
    agora = int(time.time())
    if not p.isdigit() or not c.isdigit():
        _apagar(r.arq_passaporte)
        return
    idade = agora - int(c)
    # Idade negativa e relogio que andou para tras, ou arquivo vindo de outra
    # maquina: nao da para dizer quando nasceu, entao vale como vencido.
    if idade < 0 or idade > VALIDADE_PASSAPORTE:
        r.pass_velho = idade
        _apagar(r.arq_passaporte)
        return
    r.pass_guardado = p
    r.pass_idade = idade


def _apagar(arquivo: Path) -> None:
    """`rm -f`."""
    try:
        arquivo.unlink()
    except FileNotFoundError:
        pass


def _gravar_passaporte(r: Rodada) -> None:
    """`umask 077; mkdir -p; printf > arquivo`: o arquivo nasce 0600."""
    assert r.cache_dir is not None and r.arq_passaporte is not None
    try:
        os.makedirs(r.cache_dir, mode=0o700, exist_ok=True)
        fd = os.open(r.arq_passaporte, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"passaporte={r.passaporte}\ncriado={int(time.time())}\n")
    except OSError:
        erro(f"   nao consegui gravar {r.arq_passaporte} — sem ele a segunda invocacao nao confere.")
        raise SystemExit(1) from None


# ----------------------------------------------------------------- os passos


def passo_1_env(r: Rodada) -> None:
    titulo("1/7  .env")
    # NAO basta olhar ./.env. O `.env` e gitignorado, entao `git worktree add` nao o
    # copia e um worktree novo nao tem o dele — mas o lado Python acha o do checkout
    # principal subindo os diretorios (usp_mcp.env.achar_env). Se este script criasse
    # um ./.env no worktree, ele SOMBREARIA o de verdade: o token iria para um arquivo
    # que some com o worktree, e o `.env` que o projeto usa ficaria sem nada. E o mesmo
    # defeito que a primeira versao do gate teve (§4 do CONVENTIONS.md).
    # Engolir a falha aqui daria o pior desfecho: env_file vazio, um .env novo criado
    # no lugar errado, e a aparencia de sucesso. Se nao da para localizar, pare.
    try:
        from usp_mcp.env import achar_env, ler_env
    except Exception as e:  # noqa: BLE001 — a causa vai inteira para a pessoa
        erro("nao consegui localizar o .env — usp_mcp.env nao importou:")
        erro(f"  {type(e).__name__}: {e}")
        raise SystemExit(1) from None

    env_file = achar_env()
    if env_file is None:
        exemplo = RAIZ / ".env.example"
        if not exemplo.is_file():
            erro("sem .env e sem .env.example — repo incompleto")
            raise SystemExit(1)
        env_file = RAIZ / ".env"
        shutil.copyfile(exemplo, env_file)
        nota("nenhum .env encontrado; criei a partir do .env.example (esta no gitignore)")
    else:
        nota("gravando no .env que o projeto ja enxerga:")
        nota(f"  {env_file}")
    r.env_file = env_file

    # O bash fazia `set -a; . "$ENV_FILE"; set +a`: o arquivo vencia o ambiente.
    # Aqui ele e lido, nao sourceado, e nada dele vai para o ambiente dos
    # processos filhos — o MOODLE_TOKEN antigo nao tem por que chegar ao curl
    # nem ao navegador.
    valores = ler_env(env_file)
    if "MOODLE_URL" in valores:
        r.moodle_url = valores["MOODLE_URL"]
    else:
        r.moodle_url = os.environ.get("MOODLE_URL", "")
    if not r.moodle_url:
        r.moodle_url = "https://edisciplinas.usp.br"
    nota(f"MOODLE_URL={r.moodle_url}")

    r.cache_dir = env_file.parent / ".cache"
    r.arq_passaporte = r.cache_dir / "passaporte"

    # Um token que ja funciona nao se sobrescreve calado: o antigo CONTINUA ativo em
    # managetoken.php, e trocar sem avisar deixa dois vivos na conta e nenhum
    # registro de qual esta em uso. A lista de la mostra o NOME (16 chars), nao o valor.
    texto_env = env_file.read_text(encoding="utf-8", errors="replace")
    if re.search(r"^MOODLE_TOKEN=[a-f0-9]{32}$", texto_env, re.MULTILINE):
        aviso("o .env ja tem um MOODLE_TOKEN com forma valida.")
        nota("Na pratica isto costuma ser troca por si mesmo: a linha 89 do launch.php")
        nota("chama generate_token_for_current_user, que devolve o token EXISTENTE do")
        nota("servico em vez de cunhar um novo. Medido em 11/09/2026 numa rodada real —")
        nota("o valor gravado veio byte a byte igual ao que ja estava aqui.")
        nota("Token novo so nasce se a conta ainda nao tiver um para este servico; nesse")
        nota("caso o antigo continua ativo e se revoga em:")
        nota(f"  {r.moodle_url}/user/managetoken.php  ->  Reconfigurar")
        if r.sobrescrever:
            nota("--sobrescrever passado: seguindo.")
        elif r.tty:
            print("   Sobrescrever? [s/N] ", end="", flush=True)
            resp = _ler_linha_do_terminal()
            if resp[:1] not in ("s", "S", "y", "Y"):  # `case "$resp" in [sSyY]*)`
                print("   abortado, nada mudou.")
                raise SystemExit(0)
        else:
            # Sem terminal nao ha como perguntar, e sobrescrever calado e exatamente o
            # que esta confirmacao existe para impedir. Reprovar dizendo a cura. Vale
            # para o cano (`pbpaste | ...`) e para um agente sem terminal: no fluxo em
            # duas invocacoes, --sobrescrever vai nas duas.
            erro("   Sem terminal para confirmar (pipe, ou um agente rodando o script).")
            erro("   Rode num terminal, ou passe --sobrescrever se e isso que voce quer.")
            raise SystemExit(1)


# O §8 usa `passport=1234` fixo. Um passaporte proprio permite conferir o eco:
# o `siteid` do payload e md5(wwwroot + passaporte), entao um payload de outra
# tentativa ou de outra sessao aparece. Ver §3.1 do desenho — confere e avisa,
# NAO bloqueia: a formula esta recordada, nao medida contra o e-Disciplinas.
#
# O passaporte era por INVOCACAO, e isso anulava a conferencia no fluxo em duas
# etapas (um agente abre o navegador numa invocacao e a pessoa entrega o payload
# noutra): a segunda cunhava outro passaporte e o aviso saia em toda rodada boa,
# que e como se ensina alguem a ignorar um aviso (BACKLOG, 11/09). Agora ele e
# por RODADA:
#
#   - fica em .cache/passaporte, ao lado do .env, com permissao 0600. Nao e
#     segredo (vai na URL, e o servidor da USP o ve), mas e material de sessao:
#     quem o tem monta um payload que passa na conferencia. 0600 custa zero;
#   - vale VALIDADE_PASSAPORTE segundos (10 min) a partir de quando foi cunhado,
#     e reaproveita-lo NAO estende. O passo manual leva ~20 s medidos; 10 min
#     cobrem login na Senha Unica com segundo fator e uma distracao no meio, e
#     ficam muito aquem de "outra sessao", que e o que a conferencia existe para
#     pegar. Vencido, e descartado e outro nasce — e o passo 5 diz isso;
#   - serve UMA vez: morre no passo 5, quando e confrontado com um payload, bata
#     ou nao. Se o script morrer ANTES disso (colou a URL de ida, stdin vazio), o
#     arquivo fica, de proposito: e a proxima tentativa que vai usa-lo. Nao ha
#     `trap` apagando na saida — a validade e o coletor de lixo.
#
# O caminho de uma pessoa no terminal segue igual: ela roda, cola, e o passaporte
# nasce e morre na mesma invocacao. So muda que uma tentativa abortada no meio
# deixa o passaporte para a seguinte, e a aba do navegador que ficou aberta ainda
# confere.
def passo_2_passaporte(r: Rodada) -> tuple[str, str]:
    """Devolve (url_auto, url_manual)."""
    titulo("2/7  pegar o redirect do launch.php")
    carregar_passaporte_guardado(r)
    if r.pass_guardado:
        r.passaporte = r.pass_guardado
        nota(f"passaporte: reaproveitando o da rodada de ha {r.pass_idade}s (vale {VALIDADE_PASSAPORTE}s, uma vez).")
    else:
        r.passaporte = str(secrets.randbelow(9 * 10**9) + 10**9)
        _gravar_passaporte(r)
        if r.pass_velho is not None:
            nota(f"passaporte: o guardado tinha {r.pass_velho}s, acima dos {VALIDADE_PASSAPORTE}s de validade — descartado.")
        nota(f"passaporte: novo, guardado em {r.arq_passaporte} por {VALIDADE_PASSAPORTE}s, para uma rodada.")
    base = f"{r.moodle_url}/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport={r.passaporte}"

    # Duas URLs para os dois caminhos, e a diferenca esta no `urlscheme`:
    #   automatico: esquema NOSSO, que um handler temporario atende (ver
    #               scripts/_capturar_redirect.sh). O navegador entrega direto.
    #   manual:     `confirmed=1` faz o launch.php NAO redirecionar — ele renderiza
    #               uma pagina com o link cujo href E o `moodlemobile://token=…`
    #               (linhas 120-145 da 5.0 STABLE). Entao a instrucao vira "botao
    #               direito no link -> copiar endereco", em vez de abrir o DevTools.
    return f"{base}&urlscheme=uspmcp", f"{base}&urlscheme=moodlemobile&confirmed=1"


def _captura_automatica(r: Rodada, url_auto: str) -> str:
    nota("Tentando captura automatica. Como funciona: registro um handler temporario")
    nota("para `uspmcp://`, abro o launch.php com esse esquema, e o navegador")
    nota("entrega o redirect direto para o script — sem DevTools e sem colar nada.")
    nota("O handler e desregistrado no fim, inclusive se voce abortar com Ctrl+C.")
    nota("")
    ambiente = dict(os.environ)
    ambiente["USP_MCP_NAVEGADOR"] = r.navegador
    try:
        p = subprocess.run(
            ["bash", str(RAIZ / "scripts" / "_capturar_redirect.sh"), url_auto, "uspmcp", "120"],
            env=ambiente,
            cwd=RAIZ,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except OSError:
        p = None
    if p is not None and p.returncode == 0:
        titulo("3/7  recebido sem passar pelo terminal nem pelo clipboard")
        nota("captura automatica OK — nada foi colado e nada ficou no scrollback.")
        return p.stdout.rstrip("\n")
    aviso("a captura automatica nao entregou; seguindo no caminho manual.")
    return ""


def _stdin_inteiro() -> str:
    """`valor=$(cat)`: o stdin ate o fim, sem as quebras de linha finais."""
    if sys.stdin is None:
        return ""
    try:
        return sys.stdin.read().rstrip("\n")
    except (OSError, ValueError):
        return ""


def passo_3_redirect(r: Rodada, url_auto: str, url_manual: str) -> str:
    """Devolve o valor colado, lido ou vigiado. Sai com 3 quando ele nao veio."""
    valor = ""

    if not r.manual and r.tty:
        valor = _captura_automatica(r, url_auto)

    if valor:
        return valor

    titulo("2/7  (manual) abra esta URL no navegador LOGADO na Senha Unica")
    print(f"\n   {url_manual}\n")
    # Ate 18/09 esta linha terminava em "nao precisa de DevTools". A tranquilizacao
    # so serve para quem ja sabe o que e DevTools; para quem nao sabe, ela levanta
    # uma pergunta em vez de responder — e o plano B que a justificava saiu daqui.
    nota("Com `confirmed=1` o Moodle nao redireciona: ele mostra uma pagina, e o")
    nota("ENDERECO de um dos links dela e a sua chave.")
    if r.tty:
        abrir_navegador(url_manual)
    pausar(r, "Aperte [Enter] quando a pagina tiver aberto.")

    # Qual link. A instrucao antiga dizia "o link" e a pagina tem tres coisas
    # clicaveis: numa passagem real de um segundo usuario em 12/09/2026 o que foi
    # para o clipboard foi a URL da propria pagina. Nada ali se parece com um
    # token, e o texto do link certo promete ser um plano B dispensavel — por isso
    # ele e citado em voz alta, e por isso os dois chamarizes sao nomeados para
    # serem ignorados de proposito, em vez de ficarem de fora da instrucao.
    titulo("2/7  na pagina, ache o link azul")
    nota("A pagina tem tres coisas, e so UMA interessa:")
    nota("  caixa verde  'O seu cadastro foi confirmado'   -> ignore")
    nota("  botao cinza  'Ambientes'                       -> ignore")
    nota("  link azul    'Clique aqui se a aplicacao nao abrir automaticamente'")
    nota("               -> E ESTE. O texto promete plano B e mente: e o unico")
    nota("                  lugar da pagina onde o token existe.")
    pausar(r, "Aperte [Enter] quando tiver achado o link azul.")

    titulo("2/7  copie o ENDERECO dele, sem clicar")
    aviso("NAO CLIQUE nesse link. Clicar tenta abrir o app e nao copia nada.")
    nota("Botao DIREITO em cima dele -> 'Copiar endereco do link'. So isso.")

    titulo("3/7  cole a URL do link")
    if r.tty:
        nota("Nada aparece na tela enquanto voce cola — o valor e a credencial e nao")
        nota("deve ficar no scrollback do terminal.")
        valor = _ler_segredo_do_terminal(
            "\n   Cole e aperte Enter (ou Enter direto para eu ler do clipboard): "
        )
        if not valor:
            r.clip = achar_leitor_de_clipboard()
            if r.clip:
                valor = ler_clipboard(r.clip)
                if valor:
                    nota(f"li do clipboard (`{r.clip}`).")
            else:
                nota("sem pbpaste/wl-paste/xclip/powershell nesta maquina")
    else:
        # Sem terminal, o stdin decide o que esta invocacao e. Le-lo ANTES de abrir
        # qualquer coisa e o que mantem `pbpaste | ./scripts/token.sh` igual ao que
        # sempre foi: quem ja chegou com o payload nao quer um navegador abrindo.
        valor = _stdin_inteiro()  # pbpaste | ./scripts/token.sh
        if valor:
            nota("li do stdin.")
        else:
            # Stdin vazio e sem terminal: e um agente de codigo rodando o script. Ate
            # 16/09 isto imprimia a URL, NAO abria o navegador (o `open` morava dentro
            # do `[ -t 0 ]`) e morria em "Nada foi colado". De 16/09 a 17/09 abria a
            # pagina, guardava o passaporte e saia com 3 — e a pessoa tinha de dizer
            # "colei" para o agente rodar `pbpaste | ./scripts/token.sh`. Agora esta
            # invocacao ABRE a pagina certa e FICA DE VIGIA no clipboard: quando ele
            # mudar para o endereco do link, o script segue sozinho ate gravar. Uma
            # invocacao, zero mensagens da pessoa. O que sobra para ela e o botao
            # direito no link. A vigia so existe onde ha clipboard para vigiar; nos
            # outros casos o script diz por que e cai no fluxo em duas invocacoes.
            abrir_navegador(url_manual)
            r.clip = achar_leitor_de_clipboard()
            sem_vigia = ""
            if r.vigia_segundos == 0:
                sem_vigia = "USP_MCP_VIGIA_SEGUNDOS=0: vigia do clipboard desligada a pedido."
            elif os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
                # O mesmo motivo de nao abrir navegador por SSH: o clipboard que `pbpaste`
                # alcanca daqui e o da maquina REMOTA, e o endereco vai ser copiado na da
                # pessoa. Vigiar o clipboard errado esperaria para sempre por nada.
                sem_vigia = "sessao SSH: o clipboard que eu leria e o da maquina remota, e voce vai copiar na sua. Sem vigia."
            elif not r.clip:
                sem_vigia = "sem pbpaste/wl-paste/xclip/powershell nesta maquina (ou sem sessao grafica): nao ha clipboard para vigiar."

            if sem_vigia:
                titulo("3/7  aguardando o payload — rodada em duas etapas")
                aviso(sem_vigia)
                nota("Nao veio nada pelo stdin e nao ha terminal para perguntar.")
                sair_aguardando(r)

            # O anuncio vem ANTES da primeira leitura, no texto que a pessoa le. Nao e
            # para esconder: ela precisa saber que o clipboard esta sendo lido, o que
            # dispara, o que acontece com o resto, e como desligar.
            titulo("3/7  de vigia no clipboard — copie o endereco do link e eu sigo sozinho")
            nota(f"AVISO, antes de comecar: vou LER o clipboard desta maquina (`{r.clip}`) a cada")
            nota(f"0,5 s, por ate {r.vigia_segundos} s, esperando ele MUDAR para algo que comece com")
            nota(f"`{ESQUEMA}`. So isso me faz agir. Qualquer outra coisa que voce copiar")
            nota("nesse intervalo (uma senha, um trecho de texto) eu ignoro: nao guardo, nao")
            nota("imprimo, nao registro e nao digo o tamanho. O que ja esta no clipboard agora")
            nota("tambem nao conta — so mudanca.")
            nota("Se copiar a coisa errada, eu digo o que veio errado e continuo esperando.")
            nota("Para nao vigiar: USP_MCP_VIGIA_SEGUNDOS=0 ./scripts/token.sh (fluxo em duas")
            nota("invocacoes, com `pbpaste | ./scripts/token.sh` depois de copiar).")
            nota("")
            vigiado = vigiar_clipboard(r, r.vigia_segundos)
            if vigiado is None:
                titulo("3/7  vigia encerrada sem o endereco — rodada em duas etapas")
                nota(f"{r.vigia_segundos} s e o clipboard nao mudou para `{ESQUEMA}`. Parei de ler.")
                dicas_quando_a_pagina_nao_coopera()
                sair_aguardando(r)
            # `valor` veio da vigia: a conferencia abaixo e os passos 4-7 seguem como no
            # caminho por stdin.
            valor = vigiado or ""

    # --------------------------- confere o clipboard ANTES de gastar a tentativa
    # Fricao medida na mesma passagem de 12/09/2026: nao havia como olhar o que
    # estava no clipboard antes de entregar. Da para fazer a mao com
    # `pbpaste | cut -c1-21`, que mostra `moodlemobile://token=` e nada alem — mas
    # quem esta SEGUINDO o script nao tem por que inventar esse comando, entao ele
    # vira passo daqui. Custa zero e roda antes de qualquer decodificacao.
    #
    # O QUE PODE SER IMPRESSO, e isto e o Invariante 3 e nao estilo: no maximo o
    # prefixo do esquema, e SO quando o valor comeca exatamente com ele. Tudo
    # depois de `token=` e a credencial. Quando nao confere, a saida fala de forma
    # — quantos bytes — e nunca dos bytes: um `cut -c1-21` incondicional num base64
    # nu imprimiria 21 caracteres de token no scrollback.
    #
    # So existe no caminho manual. Na captura automatica o valor vem do navegador
    # com o esquema NOSSO (`uspmcp://`), nao passa por clipboard nenhum, e conferir
    # contra `moodlemobile://` ali daria alarme falso em toda rodada boa.
    bytes_ = len(valor.encode("utf-8", errors="replace"))
    if valor.startswith(ESQUEMA):
        nota(f"confere: comeca com `{ESQUEMA}`, {bytes_} bytes no total.")
    else:
        aviso(f"o que chegou ({bytes_} bytes) NAO comeca com `{ESQUEMA}`.")
        if "launch.php" in valor:
            # O caso medido, e o unico em que da para afirmar o que aconteceu.
            nota("Isto e a URL de IDA (a da pagina que voce abriu), e nao a de VOLTA.")
            nota("As duas sao URLs, e e por isso que se confundem; so a segunda")
            nota("carrega o token.")
            nota("Volte a pagina, BOTAO DIREITO no link azul 'Clique aqui se a")
            nota("aplicacao nao abrir automaticamente' -> 'Copiar endereco do")
            nota("link', e rode este script de novo. Nao clique com o esquerdo.")
            nota("O .env NAO foi tocado.")
            raise SystemExit(1)
        nota("Colar so o base64, sem o esquema na frente, tambem vale — o passo 4/7")
        nota("decide. Se nao for isso, refaca do passo 2.")
        dicas_quando_a_pagina_nao_coopera()
    return valor


def passo_4_decodifica(valor: str) -> tuple[str, str, int]:
    titulo("4/7  decodifica")
    # A regra do formato mora em usp_mcp/token/decodificar.py, em um lugar so — o
    # fix-token.sh usa a mesma regra. Ela devolve siteid/wstoken/partes e NUNCA o
    # privatetoken; se a forma estiver errada, a mensagem dela diz o que fazer, e
    # ela vai para o stderr como o helper de scripts/ sempre fez.
    try:
        siteid, wstoken, partes = analisar(valor)
    except FormaErrada as e:
        erro(str(e))
        raise SystemExit(1) from None
    nota(f"payload trazia {partes} parte(s); wstoken tem forma de 32 hex. OK.")
    if partes >= 3:
        nota("privatetoken descartado sem sair do decodificador (§2.2).")
    return siteid, wstoken, partes


def passo_5_passaporte(r: Rodada, siteid: str) -> None:
    titulo("5/7  confere o passaporte")
    esperado = _md5(r.moodle_url + r.passaporte)
    # Uso unico: o passaporte acaba de ser confrontado com um payload e morre aqui,
    # bata ou nao. Depois deste ponto qualquer nova invocacao cunha outro.
    assert r.arq_passaporte is not None
    _apagar(r.arq_passaporte)
    if siteid == esperado:
        nota("confere: o payload responde a ESTA rodada. Passaporte consumido.")
        return
    aviso("nao confere com md5(wwwroot+passaporte).")
    if r.pass_velho is not None:
        nota(f"O passaporte da rodada anterior tinha {r.pass_velho}s — acima dos")
        nota(f"{VALIDADE_PASSAPORTE}s de validade — e foi descartado no passo 2; este e novo,")
        nota("e por isso nao bate. Se o payload veio daquela pagina, e so isto.")
    nota("Isto e AVISO, nao bloqueio. E ELE SO CARREGA INFORMACAO se a pagina de onde")
    nota("voce copiou foi a que ESTA rodada abriu (ou imprimiu): o passaporte vale")
    nota(f"{VALIDADE_PASSAPORTE}s e uma rodada, entao um payload vindo de outra — sua, da")
    nota("mesma conta, perfeitamente valida — nao confere e esta tudo certo. Aconteceu")
    nota("em 11/09/2026, e o token autenticou no passo 6.")
    nota("Se a pagina foi a desta rodada, sobram duas leituras e o passo 6 desempata:")
    nota("  - autenticou: a formula e que esta errada aqui (wwwroot com/sem barra,")
    nota("    com/sem www). Registre no §9.")
    nota("  - falhou: o payload nao e desta conta.")


def passo_6_confirma(r: Rodada, wstoken: str) -> str:
    """Devolve o userid, como texto. Sai com 1 se o token nao autenticar."""
    titulo(f"6/7  confirma contra a USP — UMA chamada ({FN})")
    nota("Esta chamada fica no log da sua conta. E ela que faz 'gravei o token'")
    nota("significar 'o token funciona' — sem ela, voce descobre no primeiro uso.")
    # O token vai por `curl -K -` (stdin), nunca em argv: ps aux e legivel.
    # Verificar ANTES de gravar e o que impede o .env de guardar token que nao autentica.
    # O stderr do curl passa direto para a pessoa, como no bash: com `-sS` ele so
    # fala quando falha, e a falha dele e o diagnostico.
    try:
        p = subprocess.run(
            [
                "curl", "-sS", "-K", "-",
                f"{r.moodle_url}/webservice/rest/server.php",
                "--data-urlencode", f"wsfunction={FN}",
                "--data-urlencode", "moodlewsrestformat=json",
            ],
            input=f'data-urlencode = "wstoken={wstoken}"\n',
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except OSError:
        p = None
    if p is None or p.returncode != 0:
        erro("   curl falhou — a rede nao respondeu. O .env NAO foi tocado.")
        raise SystemExit(1)
    resp = p.stdout

    # Erro do Moodle chega como HTTP 200 com errorcode no corpo (§9, 01/09/2026):
    # quem checar status entrega JSON de erro achando que e sucesso.
    userid = _userid_da_resposta(resp)
    if userid is None:
        erro("   O .env NAO foi tocado: o token nao autentica e nao vale gravar.")
        erro("   Refaca do passo 2 — o mais comum e a sessao do navegador ter expirado.")
        raise SystemExit(1)
    nota("userid derivado do proprio token (nunca configurado a mao — §2 do CONVENTIONS).")
    return userid


def _userid_da_resposta(resp: str) -> str | None:
    try:
        d = json.loads(resp)
    except Exception:  # noqa: BLE001 — qualquer coisa que nao seja JSON
        sys.stderr.write("   a resposta nao e JSON. Cru, sem filtro (Invariante 6):\n")
        return None
    if not isinstance(d, dict):
        sys.stderr.write("   a resposta nao e JSON. Cru, sem filtro (Invariante 6):\n")
        return None
    if "exception" in d or "errorcode" in d:
        sys.stderr.write("   o Moodle recusou: %s / %s\n" % (d.get("errorcode", "?"), d.get("message", "?")))
        return None
    uid = d.get("userid")
    if not uid:
        sys.stderr.write("   autenticou mas nao trouxe userid — forma inesperada.\n")
        return None
    for campo in ("sitename", "fullname", "username", "release"):
        if d.get(campo):
            sys.stderr.write("   %-9s %s\n" % (campo + ":", d[campo]))
    return str(uid)


def passo_7_grava(r: Rodada, wstoken: str, userid: str) -> None:
    titulo("7/7  grava no .env")
    assert r.env_file is not None and r.cache_dir is not None
    # Em bash o token ia para o Python de gravacao por env var, nao por argv, pelo
    # mesmo motivo do passo 6. Aqui nao ha processo nenhum: e uma variavel local.
    alvo = r.env_file
    linhas = alvo.read_text(encoding="utf-8").splitlines(keepends=True)
    saida, achou = [], False
    for l in linhas:
        if re.match(r"^\s*MOODLE_TOKEN\s*=", l):
            saida.append(f"MOODLE_TOKEN={wstoken}\n")
            achou = True
        else:
            saida.append(l)
    if not achou:
        if saida and not saida[-1].endswith("\n"):
            saida.append("\n")
        saida.append(f"MOODLE_TOKEN={wstoken}\n")
    with open(alvo, "w", encoding="utf-8") as f:
        f.writelines(saida)
    print("   MOODLE_TOKEN gravado" + ("" if achou else " (linha nova)") + ". Valor nao impresso.")

    os.makedirs(r.cache_dir, exist_ok=True)
    (r.cache_dir / "userid").write_text(f"{userid}\n", encoding="utf-8")
    nota(f"{r.cache_dir}/userid preenchido — scripts/userid.sh ja acha o cache pronto")

    titulo("pronto")
    nota(f"Confira com uma chamada sua:  ./scripts/ws.sh {FN} | head -c 300")
    nota(f"Revogar este token:           {r.moodle_url}/user/managetoken.php -> Reconfigurar")
    nota("Invariante 4: essa credencial e pessoal e nao sai desta maquina.")


# ------------------------------------------------------------------- main


def _ajuda() -> str:
    """O que `--ajuda` imprime: este cabecalho, que era o do token.sh."""
    return (__doc__ or "").strip("\n")


def main(argv: list[str] | None = None) -> int:
    _preparar_saida()
    args = sys.argv[1:] if argv is None else list(argv)
    r = Rodada(tty=sys.stdin is not None and sys.stdin.isatty())

    for arg in args:
        if arg == "--sobrescrever":
            r.sobrescrever = True
        elif arg == "--manual":
            r.manual = True
        elif arg == "--auto":
            r.manual = False
        elif arg.startswith("--navegador="):
            r.navegador = arg[len("--navegador="):]
        elif arg in ("-h", "--ajuda", "--help"):
            print(_ajuda())
            return 0
        else:
            erro(f"opcao desconhecida: {arg} (use --ajuda)")
            return 2

    vigia = os.environ.get("USP_MCP_VIGIA_SEGUNDOS", "90")
    if not vigia.isdigit():
        erro(f"USP_MCP_VIGIA_SEGUNDOS='{vigia}' nao e um numero de segundos (0 desliga a vigia)")
        return 2
    r.vigia_segundos = int(vigia)

    passo_1_env(r)
    url_auto, url_manual = passo_2_passaporte(r)
    valor = passo_3_redirect(r, url_auto, url_manual)
    siteid, wstoken, _partes = passo_4_decodifica(valor)
    del valor
    passo_5_passaporte(r, siteid)
    userid = passo_6_confirma(r, wstoken)
    passo_7_grava(r, wstoken, userid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
