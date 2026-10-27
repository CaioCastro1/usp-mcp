"""T100-T108: as fixtures, a superfície e o cliente da fatia de módulos.

**Asserção sobre o que FOI ENVIADO** (regra 11 do CLAUDE.md): o defeito que
fechou esta fatia em 14/09 foi um `tipo=N` mandado onde o currículo pedia
`tipo=V`. O dublê devolve o que o teste manda, então só o parâmetro enviado
pega esse erro.
"""
import pytest

from tests.git import esta_ignorado
from tests.jupiter.conftest import FIXTURES, MODULOS, RAIZ
from usp_mcp.jupiter import politica

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
