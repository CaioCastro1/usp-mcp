import sys
import os
from pathlib import Path
import json

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from usp_mcp.rucard.cliente import ClienteRucard, transporte_http
from usp_mcp.rucard.ferramentas import bandejao

def load_env():
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()

def main():
    load_env()
    try:
        cliente = ClienteRucard(transporte_http)
        resultado = bandejao(dia='hoje', restaurantes=['central'], cliente=cliente)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == '__main__':
    main()
