"""T124-T125: a ferramenta `modulos` na fronteira MCP."""
import pytest

from tests.jupiter.conftest import GetPorTipo, RoteadorDWR
from usp_mcp.jupiter import cliente, server

pytestmark = pytest.mark.politica


def test_t124_o_servidor_expoe_tres_ferramentas_e_modulos_so_le():
    por_nome = {f["name"]: f for f in server.listar_ferramentas()}
    assert list(por_nome) == ["disciplina", "requisitos", "modulos"]
    m = por_nome["modulos"]
    assert set(m["inputSchema"]["properties"]) == {"busca", "disciplina"}
    assert m["inputSchema"].get("required", []) == []
    assert m["annotations"]["readOnlyHint"] is True
    descricao = m["description"]
    for precisa in ("Poli", "menor carga", "NÃO diz quais módulos você pode escolher"):
        assert precisa in descricao
    for vazamento in ("DWR", "pubGradeCurricular", "jupCursoLista", "codhab"):
        assert vazamento not in descricao


def test_t125_chamar_ferramenta_responde_pelo_indice(respostas_modulos, lista_n, lista_v):
    c = cliente.ClienteJupiter(RoteadorDWR(respostas_modulos),
                               transporte_get=GetPorTipo(lista_n, lista_v))
    texto = server.chamar_ferramenta("modulos", {"disciplina": "PMR3508"}, cliente=c)
    assert texto.startswith("PMR3508 ")
