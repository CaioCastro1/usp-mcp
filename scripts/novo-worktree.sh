#!/usr/bin/env bash
# Abre um worktree pronto para trabalhar — da base certa, e com runtime próprio.
#
# Uso:  ./scripts/novo-worktree.sh <branch> [caminho]
#       ./scripts/novo-worktree.sh fix/acento-do-jupiter
#       ./scripts/novo-worktree.sh fix/acento .claude/worktrees/acento
#
# Sem `caminho`, o worktree nasce em `.claude/worktrees/<branch com / virando ->`,
# que é onde o app desktop já põe os dele.
#
# Por que existe, e é uma medição e não uma preferência: em 21/09/2026 a `main`
# local desta máquina estava 324 commits atrás do `origin/main`, com histórico
# divergente desde 31/08. Todo worktree aberto dali nascia dois dias no passado,
# e isso já custou um diagnóstico errado e um PR conflitante no mesmo dia. A
# causa é que `git worktree add -b x` ramifica do HEAD local, que ninguém
# garantiu estar em dia — então aqui ele ramifica do `origin/main`, depois de um
# fetch, e não do que estiver em disco.
#
# As três coisas que ele faz, e a quarta que ele NÃO faz:
#
#   1. `git fetch origin main`. É o único lugar deste repositório autorizado a
#      tocar a rede sem a pessoa pedir, e é porque isto é setup e não gate: um
#      fetch que não acontece devolve exatamente o worktree velho que o script
#      existe para não criar. O gate continua offline.
#   2. `git worktree add -b <branch> <caminho> origin/main` — do REMOTO. Se o
#      fetch falhar (sem rede, por exemplo), o script para aqui e diz, em vez de
#      cair calado para o ref antigo: worktree velho é o defeito, não o plano B.
#   3. O venv do worktree, com `-e ".[dev]"`. O venv é por diretório e não vem no
#      git; sem ele o `.mcp.json` derruba os três servidores com ENOENT em
#      `.venv/bin/python`, e o gate responde sobre o python do sistema. O `-e`
#      não é detalhe: sem ele não existem os entry points em `.venv/bin/`, e o
#      `tests/test_pacote.py` (P6) PULA em vez de exercitar o que o pacote promete.
#   4. **Não cria `.env` no worktree.** O `usp_mcp.env` acha o do checkout
#      sozinho, e um `.env` próprio aqui sombreia o verdadeiro — é o defeito que
#      o `token.sh` teve em 11/09/2026 (§9), e que a checagem 0 do gate teve
#      antes dele. Terceira vez, mesmo molde; aqui ele não se repete.

set -euo pipefail

# `cd` + `pwd` como no scripts/servidor.sh: normaliza, e falha aqui — com o
# diretório na mensagem — se o checkout sumiu debaixo de quem chamou.
raiz="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd -- "$raiz"

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "uso: $0 <branch> [caminho]" >&2
  echo "exemplo: $0 fix/acento-do-jupiter" >&2
  exit 2
fi

branch="$1"
caminho="${2:-.claude/worktrees/$(printf '%s' "$branch" | tr '/' '-')}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "isto não é um repositório git: $raiz" >&2
  exit 1
fi

if [ -e "$caminho" ]; then
  echo "já existe algo em '$caminho'." >&2
  echo "Escolha outro caminho, ou remova o worktree antigo primeiro:" >&2
  echo "  git worktree remove $caminho" >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/$branch"; then
  echo "a branch '$branch' já existe neste checkout." >&2
  echo "Este script abre branch NOVA a partir do origin/main. Para continuar" >&2
  echo "um trabalho já começado, use o git direto:" >&2
  echo "  git worktree add $caminho $branch" >&2
  exit 1
fi

echo "1/3  fetch origin main (é o único passo que toca a rede)"
if ! git fetch origin main; then
  echo >&2
  echo "o fetch falhou, e o script para aqui de propósito." >&2
  echo "Ramificar do refs/remotes/origin/main antigo devolveria justamente o" >&2
  echo "worktree desatualizado que este script existe para não criar." >&2
  exit 1
fi

echo "2/3  worktree em '$caminho', ramificando de origin/main"
git worktree add -b "$branch" "$caminho" origin/main

destino="$(cd -- "$caminho" && pwd)"

# O pulo é BARULHENTO, como o USP_MCP_GATE_SEM_SUITE do gate: quem pula não pode
# achar que passou. Existe para tests/test_novo_worktree.py exercitar a escolha
# da base sem pagar uma instalação de verdade a cada teste.
if [ "${USP_MCP_WORKTREE_SEM_VENV:-0}" = "1" ]; then
  echo "3/3  venv PULADO — USP_MCP_WORKTREE_SEM_VENV=1"
  echo "     O worktree NÃO está pronto para rodar: sem venv o .mcp.json derruba"
  echo "     os três servidores e o gate reprova na pre.b. Numa máquina de gente,"
  echo "     NÃO use."
else
  if command -v uv >/dev/null 2>&1; then
    echo "3/3  venv com uv (instala por hardlink, do cache único)"
    ( cd -- "$destino" && uv venv && uv pip install -e ".[dev]" )
  else
    echo "3/3  venv com python3 -m venv (uv não está no PATH)"
    ( cd -- "$destino" && python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]" )
  fi
fi

echo
echo "pronto: $destino"
echo "  branch '$branch', a partir de origin/main ($(git rev-parse --short origin/main))"
echo "  sem .env próprio, e é o certo: o usp_mcp.env acha o do checkout, e um"
echo "  .env aqui sombreia o verdadeiro."
echo
echo "Confira antes de trabalhar:"
echo "  cd $destino && ./scripts/gate.sh"
