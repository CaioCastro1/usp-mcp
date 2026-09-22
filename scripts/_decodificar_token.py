#!/usr/bin/env python3
"""Decodifica o payload do fluxo de `launch.php` do Moodle — pelo caminho antigo.

Lê no stdin a URL `moodlemobile://token=<base64>` — ou só o base64 — e imprime
no stdout, uma por linha, `siteid=`, `wstoken=` e `partes=`. Nunca o
`privatetoken`; forma errada reprova com mensagem legível no stderr e código 1.

**A regra do formato não mora mais aqui.** Desde 18/09/2026 ela está em
`usp_mcp/token/decodificar.py`, dentro do pacote, porque o `token.sh` virou
Python (`usp_mcp/token/cli.py`) e o entry point `usp-mcp-token` roda de qualquer
pasta, sem `scripts/` na frente. Este arquivo ficou como CASCA, e não foi
apagado, por dois motivos que têm teste:

- `scripts/fix-token.sh` faz `sys.path.insert(0, "scripts")` e importa
  `RE_32HEX` e `decodificar` daqui (T-tok-10 a T-tok-14);
- T-tok-1 a T-tok-9 executam este arquivo pelo stdin.

O pacote é achado PELA POSIÇÃO NO DISCO — a raiz, dois níveis acima — e não
pelo que já estiver em `sys.path`. É o que faz a raiz falsa dos testes usar a
cópia dela de `usp_mcp/token/`, e nunca a instalada no venv, que apontaria para
o checkout de verdade (e o `achar_env` de lá, para o `.env` de verdade).
"""
from __future__ import annotations

import pathlib
import sys

_RAIZ = str(pathlib.Path(__file__).resolve().parents[1])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from usp_mcp.token.decodificar import (  # noqa: E402 — o sys.path vem antes de propósito
    LINK,
    RE_32HEX,
    RE_HTTP,
    FormaErrada,
    analisar,
    decodificar,
    e_url_de_ida,
    main,
)

__all__ = [
    "LINK",
    "RE_32HEX",
    "RE_HTTP",
    "FormaErrada",
    "analisar",
    "decodificar",
    "e_url_de_ida",
    "main",
]

if __name__ == "__main__":
    main()
