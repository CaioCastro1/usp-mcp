"""O obtentor do `MOODLE_TOKEN`, em Python — o `scripts/token.sh` portado.

Por que um pacote próprio, e não um módulo em `usp_mcp/moodle/`:

- `usp_mcp/moodle/` é o SERVIDOR do e-Disciplinas: `politica`, `cliente`,
  ferramentas, `server`. Isto aqui é a ferramenta de INSTALAÇÃO que produz a
  credencial que aquele servidor lê. Ela roda uma vez, num terminal, com uma
  pessoa do outro lado; ele roda em stdio, para um modelo. Misturar os dois
  põe um `subprocess` de `curl` e uma vigia de clipboard ao lado de código
  que a allowlist e a suíte de política vigiam com outra régua.
- A suíte de `token.sh` monta uma raiz falsa e copia para lá só o que o
  script precisa (`tests/moodle/test_token_decode.py::raiz_falsa`). Um pacote
  fechado, sem import de `usp_mcp.moodle`, é o que deixa essa cópia continuar
  sendo três arquivos e não o repositório inteiro.
- O nome do comando é `usp-mcp-token`, ao lado de `usp-mcp-moodle` e dos
  outros dois no `pyproject.toml`. Em Windows ele vira
  `.venv\\Scripts\\usp-mcp-token.exe`, e é o que dispensa o Git Bash.

O que mora aqui:

- `cli.py`: os sete passos, as mensagens e os comentários do `token.sh`, como
  estavam em 18/09/2026. Leia o docstring dele — é a mesma ajuda que
  `usp-mcp-token --ajuda` imprime.
- `decodificar.py`: a regra do formato do payload, que `scripts/fix-token.sh`
  e `scripts/_decodificar_token.py` continuam usando pelo caminho antigo.
- `__main__.py`: o que `scripts/token.sh` chama (`python -m usp_mcp.token`).

Depende só da stdlib e de `usp_mcp.env`. O SDK do MCP não entra aqui, de
propósito: obter a chave não precisa dele, e um `import mcp` faria a
instalação da chave falhar por um motivo que não é dela.
"""
