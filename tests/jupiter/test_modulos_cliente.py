"""T100-T108: as fixtures, a superfície e o cliente da fatia de módulos.

**Asserção sobre o que FOI ENVIADO** (regra 11 do CLAUDE.md): o defeito que
fechou esta fatia em 14/09 foi um `tipo=N` mandado onde o currículo pedia
`tipo=V`. O dublê devolve o que o teste manda, então só o parâmetro enviado
pega esse erro.
"""
import pytest

from tests.git import esta_ignorado
from tests.jupiter.conftest import FIXTURES, MODULOS, RAIZ, GetPorTipo, RoteadorDWR
from usp_mcp.jupiter import cliente, erros, politica

pytestmark = pytest.mark.contrato


@pytest.mark.parametrize("chave", sorted(MODULOS))
def test_t100_fixture_de_modulos_existe_e_nao_esta_vazia(chave):
    p = FIXTURES / MODULOS[chave]
    assert p.is_file(), f"fixture ausente: {p}. Ausência é FALHA, não skip."
    assert p.stat().st_size > 0, f"fixture vazia: {p}"


@pytest.mark.parametrize("chave", sorted(MODULOS))
def test_t101_fixture_de_modulos_esta_no_git(chave):
    assert not esta_ignorado(FIXTURES / MODULOS[chave], RAIZ)


def test_t101b_os_cem_envelopes_estao_la(respostas_modulos):
    grades = [k for k in respostas_modulos if k.startswith("pubGradeCurricular|")]
    fichas = [k for k in respostas_modulos if k.startswith("pubObterInfoCursoWeb|")]
    assert len(grades) == len(fichas) == 50


@pytest.mark.politica
@pytest.mark.parametrize("metodo,consulta", [
    ("listar", "pubGradeCurricular"),
    ("obter", "pubObterInfoCursoWeb"),
])
def test_t102_as_duas_consultas_da_fatia_passam_so_pelo_metodo_delas(metodo, consulta):
    assert politica.decidir(metodo, consulta).permitida
    outro = "obter" if metodo == "listar" else "listar"
    assert not politica.decidir(outro, consulta).permitida


@pytest.mark.politica
def test_t103_jupcursolista_passa_e_obterturma_continua_negado():
    assert politica.decidir_caminho("jupCursoLista").permitida
    negado = politica.decidir_caminho("obterTurma")
    assert not negado.permitida
    assert "obterTurma" in negado.motivo


def _cliente(respostas_modulos, lista_n, lista_v, *, status=200):
    get = GetPorTipo(lista_n, lista_v, status=status)
    rot = RoteadorDWR(respostas_modulos)
    return cliente.ClienteJupiter(rot, transporte_get=get), rot, get


def test_t104_a_lista_pede_a_poli_e_o_tipo_certos(respostas_modulos, lista_n, lista_v):
    c, _, get = _cliente(respostas_modulos, lista_n, lista_v)
    assert c.obter_lista_cursos_poli("V") == lista_v
    assert get.urls == ["https://uspdigital.usp.br/jupiterweb/jupCursoLista?codcg=3&tipo=V"]


def test_t105_tipo_fora_de_n_e_v_e_negado_antes_da_rede(respostas_modulos, lista_n, lista_v):
    c, _, get = _cliente(respostas_modulos, lista_n, lista_v)
    with pytest.raises(erros.ConsultaNegada):
        c.obter_lista_cursos_poli("V&codcg=8")
    assert get.urls == []


def test_t106_pagina_com_200_que_nao_e_a_lista_vira_erro_e_nao_entra_no_cache(
    respostas_modulos, lista_n, lista_v
):
    falsa = b"<html><title>Jupiterweb</title><body>manuten\xe7\xe3o</body></html>"
    c, _, get = _cliente(respostas_modulos, falsa, falsa)
    for _ in range(2):
        with pytest.raises(erros.RespostaInvalida) as exc:
            c.obter_lista_cursos_poli("N")
    assert "lista de cursos" in str(exc.value)
    assert len(get.urls) == 2, "a página recusada não pode ter ido para o cache"


def test_t107_grade_e_ficha_mandam_os_tres_parametros(respostas_modulos, lista_n, lista_v):
    c, rot, _ = _cliente(respostas_modulos, lista_n, lista_v)
    grade = c.grade_curricular("3032", "5080", "V")
    ficha = c.info_curriculo("3032", "5080", "V")
    assert rot.enviados == [
        "pubGradeCurricular|3032|5080|V",
        "pubObterInfoCursoWeb|3032|5080|V",
    ]
    assert len(grade) == 31
    assert ficha["cgahortot"] == "360"


def test_t108_ficha_vazia_vira_dicionario_vazio(respostas_modulos, lista_n, lista_v):
    c, _, _ = _cliente(respostas_modulos, lista_n, lista_v)
    ficha = c.info_curriculo("3033", "6000", "V")
    assert isinstance(ficha, dict)
    assert ficha.get("cgahortot") is None
