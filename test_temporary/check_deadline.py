import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

from usp_mcp.moodle.cliente import ClienteMoodle
from usp_mcp.moodle.o_que_vence import o_que_vence

token = None
with open(os.path.join(parent_dir, '.env')) as f:
    for line in f:
        if line.startswith('MOODLE_TOKEN='):
            token = line.strip().split('=', 1)[1]
            # Handle possible quotes
            token = token.strip('"\'')
            break

if not token:
    print("No token")
    sys.exit(1)

cliente = ClienteMoodle(token=token, url="https://edisciplinas.usp.br")
resultado = o_que_vence(cliente, dias=90)
print(resultado.texto)
