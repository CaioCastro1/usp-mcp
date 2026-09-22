#!/usr/bin/env bash
# Obtem o MOODLE_TOKEN e grava no .env — o §8 do SPEC1.md virado chamador.
#
# Uso:  ./scripts/token.sh              # guiado, interativo
#       pbpaste | ./scripts/token.sh    # se voce ja copiou a URL do redirect
#       ./scripts/token.sh --ajuda      # todas as opcoes e o desenho inteiro
#
# DESDE 18/09/2026 ESTE ARQUIVO E UM INVOLUCRO. A logica — os sete passos, o
# passaporte, a vigia do clipboard, a escolha de leitor e de navegador por
# sistema, a confirmacao contra a USP e a gravacao — mora em Python, em
# usp_mcp/token/cli.py, e e o mesmo programa que o entry point `usp-mcp-token`
# do pacote sobe. Este script so faz duas coisas: acha o interpretador e passa a
# bola, repassando argumentos, stdin e codigo de saida (`exec`). Leia o docstring
# do cli.py para o que o script FAZ; ele e o cabecalho que morava aqui.
#
# Por que um involucro e nao um `git rm`: todo lugar que ensina a obter a chave
# — README, CLAUDE.md, handoffs, e a suite que exercita o obtentor como processo
# (tests/moodle/test_token_*.py) — invoca ESTE caminho. Quem esta no Mac ou no
# Linux nao muda um dedo, e a suite continua valendo sem mudar asseracao.
#
# Por que o porte: em Windows nao ha bash. A pessoa tinha de instalar e abrir o
# Git Bash so para este passo, enquanto todo o resto da instalacao e PowerShell.
# Agora o comando la e `.venv\Scripts\usp-mcp-token.exe` — o mesmo codigo, sem
# bash no meio. O desenho esta em docs/superpowers/specs/2026-09-18-token-em-python-design.md.

set -euo pipefail
cd "$(dirname "$0")/.."

# Qual Python. O venv e por diretorio (§3 do CLAUDE.md) e o script prefere o
# dele. Em Windows (Git Bash) o venv nao tem bin/: e .venv/Scripts/python.exe.
# E fora do venv `python3` pode nao existir la — o instalador do python.org so
# cria `python` —, entao ele e o ultimo candidato. Sem nenhum, parar AQUI com a
# causa, em vez de morrer em "command not found" (Invariante 6).
PY=""
for candidato in .venv/bin/python .venv/Scripts/python.exe; do
  if [ -x "$candidato" ]; then PY="$candidato"; break; fi
done
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then PY="python3"
  elif command -v python >/dev/null 2>&1; then PY="python"
  else
    echo "nao achei Python: nem .venv/bin/python, nem .venv/Scripts/python.exe, nem python3/python no PATH." >&2
    echo "Crie o venv (README, secao Instalando) ou instale o Python 3.11+ e rode de novo." >&2
    exit 1
  fi
fi

# PYTHONPATH com a raiz na frente, alem do `-m` (que ja poe o diretorio atual em
# sys.path): e o pacote DESTE checkout que tem de subir, nao o que estiver
# instalado em outro venv do PATH. E o mesmo que o passo 1 do script antigo
# fazia para importar usp_mcp.env. `exec` para que o codigo de saida (0, 1, 2 ou
# 3 = aguardando) seja o do Python, sem um processo bash no meio.
PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m usp_mcp.token "$@"
