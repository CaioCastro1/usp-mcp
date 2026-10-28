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


@pytest.fixture
def producao(monkeypatch, respostas_modulos, lista_n, lista_v):
    """O caminho de produção (`cliente=None`): fábrica de cliente que conta
    construções, e um cache novo no lugar do global do processo."""
    construcoes = []

    def fabrica(transporte, **_):
        construcoes.append(1)
        return cliente.ClienteJupiter(RoteadorDWR(respostas_modulos),
                                      transporte_get=GetPorTipo(lista_n, lista_v))

    monkeypatch.setattr(server, "ClienteJupiter", fabrica)
    monkeypatch.setattr(server, "_CACHE_MODULOS", server.CacheDoIndice())
    return construcoes


def test_t125b_sem_cliente_injetado_o_indice_e_montado_uma_vez(producao):
    server.chamar_ferramenta("modulos", {})
    server.chamar_ferramenta("modulos", {"disciplina": "PMR3508"})
    assert len(producao) == 1


def test_t125c_usp_fora_do_ar_chega_como_erro_legivel(monkeypatch, producao, lista_n, lista_v):
    from usp_mcp.jupiter import erros

    class Fora:
        def __call__(self, url, corpo, cabecalhos):
            raise erros.JupiterIndisponivel("o JupiterWeb não respondeu (teste)")

    monkeypatch.setattr(server, "ClienteJupiter", lambda transporte, **_: cliente.ClienteJupiter(
        Fora(), transporte_get=GetPorTipo(lista_n, lista_v)))
    with pytest.raises(erros.ErroJupiter):
        server.chamar_ferramenta("modulos", {})
