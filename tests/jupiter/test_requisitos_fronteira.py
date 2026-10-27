"""T67-T73: a fronteira MCP da fatia de requisitos, e o bug que ela corrige.

O `formatar` que estava na `main` imprimia correquisito sob o rótulo
"Pré-requisito:". Não é omissão — é resposta errada: PSI3322 pode ser cursada
JUNTO com PSI3323, e o aluno que lesse a saída adiaria a matrícula por um ano.
"""
import pytest

from tests.jupiter.conftest import Gravador
from usp_mcp.jupiter import cliente, server
from tests.jupiter.test_requisitos_cliente import GravadorGet

pytestmark = pytest.mark.politica


def test_t67_o_servidor_expoe_tres_ferramentas():
    nomes = [f["name"] for f in server.listar_ferramentas()]

    assert nomes == ["disciplina", "requisitos", "modulos"]


def test_t68_requisitos_pede_so_a_sigla():
    """Nenhum `codcur` na superfície: a medição de 14/09 mostrou que o código
    descobrível é justamente o que não responde."""
    (ferramenta,) = [f for f in server.listar_ferramentas() if f["name"] == "requisitos"]
    schema = ferramenta["inputSchema"]

    assert schema["required"] == ["sigla"]
    assert set(schema["properties"]) == {"sigla"}
    for vazamento in ("codcur", "codhab", "DWR", "listarCursosRequisitos"):
        assert vazamento not in ferramenta["description"]


def test_t69_a_descricao_diz_que_a_resposta_e_por_curriculo():
    (ferramenta,) = [f for f in server.listar_ferramentas() if f["name"] == "requisitos"]
    descricao = ferramenta["description"].lower()

    assert "currículo" in descricao or "curso" in descricao
    assert "correquisito" in descricao or "junto" in descricao


def test_t70_correquisito_nao_sai_como_pre_requisito(
    psi3323_html, ingresso_poli, colegiados
):
    """O bug de 31/08, agora travado: o rótulo tem que dizer que cursa junto."""
    c = cliente.ClienteJupiter(
        Gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(psi3323_html),
    )
    saida = server.chamar_ferramenta("requisitos", {"sigla": "PSI3323"}, cliente=c)

    assert "PSI3322" in saida
    assert "junto" in saida.lower()
    linha = next(l for l in saida.splitlines() if "PSI3322" in l)
    assert "pré-requisito" not in linha.lower()


def test_t71_requisito_fraco_e_duro_saem_diferentes(
    mat2455_html, ingresso_poli, colegiados
):
    """Em 3032 dá para matricular devendo Cálculo II; em 3250 não. Achatar os
    dois apaga a informação que decide a matrícula."""
    c = cliente.ClienteJupiter(
        Gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(mat2455_html),
    )
    saida = server.chamar_ferramenta("requisitos", {"sigla": "MAT2455"}, cliente=c)

    assert "devendo" in saida.lower()
    assert saida.count("3032") >= 1 and saida.count("3250") >= 1


def test_t72_o_silencio_do_ptc3313_chega_ao_modelo(
    ptc3313_html, ingresso_poli, colegiados
):
    """Invariante 6: se a saída não disser, o modelo conclui que não há
    exigência — que é exatamente a conclusão errada na fronteira da ênfase."""
    c = cliente.ClienteJupiter(
        Gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(ptc3313_html),
    )
    saida = server.chamar_ferramenta("requisitos", {"sigla": "PTC3313"}, cliente=c)

    assert "não conclua" in saida.lower()
    assert "ênfase" in saida.lower()


def test_t73_disciplina_sem_curso_aponta_para_requisitos(gravador, psi3323):
    """Antes, pedia um par (codcur, codhab) que ninguém sabe de cabeça — e que
    a medição mostrou ser o par errado quando alguém sabe."""
    c = cliente.ClienteJupiter(gravador([psi3323]))
    saida = server.chamar_ferramenta("disciplina", {"sigla": "PSI3323"}, cliente=c)

    assert "requisitos" in saida


def test_t77_o_silencio_nao_escolhe_a_causa_que_nao_sabe(
    ptc3313_html, ingresso_poli, colegiados
):
    """Zero currículo tem DUAS causas possíveis e elas são indistinguíveis daqui.

    MAT2453 é Cálculo I, primeira do currículo: o silêncio dela é ausência real.
    PTC3313 é de ênfase: o silêncio é falta de registro. A página devolve a
    mesma coisa para as duas, e a saída dizia "da ênfase em diante esse endpoint
    costuma não ter registro" — explicação absurda para Cálculo I, e é o que
    uma pergunta de aceite pegou.

    O Invariante 7 não pede que a ferramenta saiba: pede que ela não invente
    qual das duas é.
    """
    c = cliente.ClienteJupiter(
        Gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(ptc3313_html),
    )
    saida = server.chamar_ferramenta("requisitos", {"sigla": "PTC3313"}, cliente=c)

    # As duas causas aparecem, e nenhuma é apresentada como a provável.
    assert "não conclua" in saida.lower()
    for causa in ("ênfase", "primeira"):
        assert causa in saida.lower(), f"a causa {causa!r} não é oferecida"
    for ranking in ("provavelmente", "costuma", "mais provável"):
        assert ranking not in saida.lower(), (
            f"{ranking!r} rankeia uma causa que a ferramenta não consegue medir"
        )


def _texto_de(sigla, html, ingresso_poli, colegiados):
    c = cliente.ClienteJupiter(
        Gravador([colegiados, ingresso_poli]), transporte_get=GravadorGet(html)
    )
    return server.chamar_ferramenta("requisitos", {"sigla": sigla}, cliente=c)


def test_t82_mat2455_sai_por_combinacao_e_cabe_em_3500_bytes(
    mat2455_html, ingresso_poli, colegiados
):
    # Medido em 14/09/2026: 6.238 B por currículo → 2.458 B por combinação. Folga ~40%.
    saida = _texto_de("MAT2455", mat2455_html, ingresso_poli, colegiados)

    assert len(saida.encode()) <= 3_500, f"{len(saida.encode())} B"
    assert "23 currículos, 4 combinações" in saida
    assert saida.count("3033") == 1, "cada currículo aparece uma vez"
    assert saida.count("Cálculo Diferencial e Integral II") <= 3, "uma vez por grupo que a exige"


def test_t82b_a_marca_de_ingresso_sobrevive_ao_agrupamento(
    mat2455_html, ingresso_poli, colegiados
):
    saida = _texto_de("MAT2455", mat2455_html, ingresso_poli, colegiados)
    linha_3033 = next(l for l in saida.splitlines() if l.strip().startswith("3033 "))
    linha_3032 = next(l for l in saida.splitlines() if l.strip().startswith("3032 "))
    assert linha_3033.endswith("[curso de ingresso]")
    assert "[curso de ingresso]" not in linha_3032
    assert "Ciclo Básico - Engenharia Elétrica" in linha_3033
    assert "3º período ideal" in linha_3033


def test_t82c_duro_e_fraco_ficam_em_cabecalhos_diferentes(
    mat2455_html, ingresso_poli, colegiados
):
    saida = _texto_de("MAT2455", mat2455_html, ingresso_poli, colegiados)
    cabecalhos = [l for l in saida.splitlines() if l.startswith("• ")]
    assert len(cabecalhos) == 4
    assert any(l.startswith("• Pré-requisito: MAT2454") for l in cabecalhos), "o grupo do 3250 (duro)"
    assert any(l.startswith("• Requisito fraco (dá para matricular devendo): MAT2454") for l in cabecalhos)
    assert any("2000101" in l for l in cabecalhos)


def test_t82d_um_curriculo_so_continua_legivel(psi3323_html, ingresso_poli, colegiados):
    saida = _texto_de("PSI3323", psi3323_html, ingresso_poli, colegiados)
    assert saida.startswith("Exigências para cursar PSI3323, por currículo:")
    assert "combinações" not in saida
    assert "• Correquisito (cursa junto): PSI3322" in saida
    assert "3032 " in saida

