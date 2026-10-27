"""T109-T115: da lista de cursos e dos envelopes ao índice dos módulos.

Os números aqui são os da captura (50 pares, 4 com grade vazia, 3 percursos
não publicados). Se a fixture for recapturada e eles mudarem, a mudança é
dado — vai para o §9 —, não ajuste de teste.
"""
import pytest

from tests.jupiter.conftest import GetPorTipo, RoteadorDWR
from usp_mcp.jupiter import cliente, erros, indice

pytestmark = pytest.mark.contrato


@pytest.fixture
def montado(respostas_modulos, lista_n, lista_v):
    rot = RoteadorDWR(respostas_modulos)
    c = cliente.ClienteJupiter(rot, transporte_get=GetPorTipo(lista_n, lista_v))
    return indice.montar_indice(c), rot


def test_t109_cinquenta_pares_todos_pelo_link_ativo(lista_n, lista_v):
    linhas = indice.ler_lista(lista_n) + indice.ler_lista(lista_v)
    modulos = {(l.codcur, l.codhab): l for l in linhas if l.modulo}
    assert len(modulos) == 50
    # O link comentado da lista N ainda diz tipo=N para os percursos; o ativo
    # diz V. Ler o comentado é mandar o tipo errado — o defeito de 14/09.
    assert {l.tipo for l in modulos.values()} == {"V"}
    assert modulos[("3033", "6000")].nome.endswith("Programa de Inteligência Artificial")


def test_t110_o_curso_de_cada_modulo_vem_da_linha_base_do_mesmo_codigo(lista_n, lista_v):
    base = indice.cursos_base(indice.ler_lista(lista_n) + indice.ler_lista(lista_v))
    assert base["3032"] == "Ciclo Básico - Engenharia Elétrica"
    assert base["3033"] == "Ciclo Básico - Engenharia Elétrica"


def test_t111_as_situacoes_do_dado_sao_as_medidas(montado):
    ind, _ = montado
    por = {}
    for m in ind.modulos:
        por.setdefault(m.situacao, set()).add(m.codigo)
    assert por["sem_grade"] == {"3052/5000", "3052/5010", "3022/5010", "3022/5000"}
    assert por["nao_publicado"] == {"3033/6000", "3113/6000", "3123/6000"}
    assert "falhou" not in por
    assert len(por["ok"]) == 43


def test_t112_o_modulo_5080_tem_31_eletivas_no_9o_e_10o(montado):
    ind, _ = montado
    (m,) = [m for m in ind.modulos if m.codigo == "3032/5080"]
    assert m.nome_curto == "Sistemas Eletrônicos Avançados"
    assert m.curso == "Ciclo Básico - Engenharia Elétrica"
    assert m.carga_total == 360 and m.carga_eletiva == 360
    assert len(m.disciplinas) == 31
    assert {d.tipo for d in m.disciplinas} == {"C"}
    assert {d.semestre for d in m.disciplinas} == {9, 10}


def test_t113_o_tipo_enviado_e_o_do_link(montado):
    _, rot = montado
    pares = [k for k in rot.enviados if k.startswith("pubGradeCurricular|")]
    assert len(pares) == 50
    assert all(k.endswith("|V") for k in pares), (
        "um par saiu com tipo diferente do link ativo — é o defeito que fechou "
        "esta fatia em 14/09"
    )


def test_t114_falha_de_um_modulo_nao_derruba_o_indice(respostas_modulos, lista_n, lista_v):
    class Quebra(RoteadorDWR):
        def __call__(self, url, corpo, cabecalhos):
            if "c0-e2=string:5080" in corpo:
                raise erros.JupiterIndisponivel("o JupiterWeb não respondeu (teste)")
            return super().__call__(url, corpo, cabecalhos)

    c = cliente.ClienteJupiter(Quebra(respostas_modulos), transporte_get=GetPorTipo(lista_n, lista_v))
    ind = indice.montar_indice(c)
    falhos = [m.codigo for m in ind.modulos if m.situacao == "falhou"]
    assert "3032/5080" in falhos
    assert len(ind.modulos) == 50


def test_t114b_lista_sem_modulo_vira_erro_legivel(respostas_modulos):
    vazia = b"<html><title>Jupiterweb</title><table><tr><td><a href=\"listarGradeCurricular?codcg=3&codcur=3033&codhab=0&tipo=N\">3033 0</a></td><td>Ciclo</td><td>integral</td></tr></table></html>"
    c = cliente.ClienteJupiter(RoteadorDWR(respostas_modulos), transporte_get=GetPorTipo(vazia, vazia))
    with pytest.raises(erros.RespostaInvalida) as exc:
        indice.montar_indice(c)
    assert "nenhum módulo" in str(exc.value)


def test_t115_o_cache_vale_sete_dias_e_guarda_indice_com_falha_so_dez_minutos():
    agora = [0.0]
    cache = indice.CacheDoIndice(relogio=lambda: agora[0])
    bom = indice.Indice(modulos=())
    construcoes = []

    def construir():
        construcoes.append(1)
        return bom

    assert cache.obter(construir) is bom
    agora[0] = indice.TTL_INDICE - 1
    cache.obter(construir)
    assert len(construcoes) == 1
    agora[0] = indice.TTL_INDICE + 1
    cache.obter(construir)
    assert len(construcoes) == 2

    falho = indice.Indice(modulos=(indice.Modulo(
        "3032", "5080", "V", "Módulo: X", "", None, None, None, None, (), falhou=True),))
    cache2 = indice.CacheDoIndice(relogio=lambda: agora[0])
    agora[0] = 0.0
    chamadas = []
    cache2.obter(lambda: chamadas.append(1) or falho)
    agora[0] = indice.TTL_INDICE_PARCIAL - 1
    cache2.obter(lambda: chamadas.append(1) or falho)
    assert len(chamadas) == 1, "índice parcial vale 10 min: sem isso, USP fora do ar é martelada"
    agora[0] = indice.TTL_INDICE_PARCIAL + 1
    cache2.obter(lambda: chamadas.append(1) or falho)
    assert len(chamadas) == 2, "índice com módulo falho não pode ficar 7 dias no cache"
