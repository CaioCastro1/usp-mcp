"""`python -m usp_mcp.token`: o que `scripts/token.sh` executa depois de achar
o interpretador. O entry point `usp-mcp-token` aponta direto para
`usp_mcp.token.cli:main`; este arquivo existe para o invólucro bash e para
quem prefere chamar o módulo pelo nome."""
from __future__ import annotations

import sys

from usp_mcp.token.cli import main

if __name__ == "__main__":
    sys.exit(main())
