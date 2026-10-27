"""T38-T40, T74-T75 e T128: canário contra uspdigital.usp.br.

Até 14/09, no máximo três requisições reais por execução, escolhidas à mão.
O T128 (26/10) faz ~102 — as duas listas de curso da Poli e ficha + grade de
cada módulo —, porque o que ele verifica é o índice inteiro e o tempo de
montá-lo, que é critério de aceite da ferramenta `modulos`. Uma por vez, sem
laço sobre sigla. Decisão registrada no §9 de 26/10.

Compara FORMA e pertencimento, nunca valor exato que muda por semestre.
"""
import os

import pytest

from usp_mcp.jupiter import cliente, dwr

pytestmark = pytest.mark.live

MOTIVO = (
    "canário ao vivo desligado. Exporte USP_MCP_LIVE=1 para bater em "
    "uspdigital.usp.br. O §1.1 do SPEC1 registra que o sandbox não alcança a "
    "rede da USP: este teste só roda no terminal do dono."
)

ao_vivo = pytest.mark.skipif(os.environ.get("USP_MCP_LIVE") != "1", reason=MOTIVO)


def _chamar_de_verdade(sigla):
    corpo = dwr.serializar(
        metodo="obter",
        consulta="pubObterDisciplina",
        params={"coddis": sigla, "verdis": 0},
    )
    return cliente.transporte_http(
        f"{cliente.URL_BASE}/ControlePublicoDWR.obter.dwr",
        corpo,
        {"Content-Type": "text/plain", "User-Agent": cliente.AGENTE},
    )


@ao_vivo
def test_t38_forma_da_resposta_real_bate_com_a_fixture(psi3323):
    status, texto = _chamar_de_verdade("PSI3323")
    assert status == 200

    vivo = dwr.decodificar(texto)
    esperado = dwr.decodificar(psi3323)
    assert sorted(vivo) == sorted(esperado), (
        "as chaves de pubObterDisciplina mudaram: ou a fixture está velha, ou "
        "a API mudou de forma. Compare e atualize com decisão registrada no §9."
    )


@ao_vivo
def test_t39_sigla_inexistente_ainda_e_erro_no_corpo_com_200():
    status, texto = _chamar_de_verdade("ZZZ9999")
    assert status == 200, "o Jupiter sinaliza erro no CORPO, não no status"
    with pytest.raises(dwr.JupiterErro):
        dwr.decodificar(texto)


def test_t40_skip_diz_o_motivo_por_escrito():
    # A diferença entre "não rodou" e "não rodou, e aqui está por quê" é o
    # Invariante 6 aplicado à própria suíte.
    if os.environ.get("USP_MCP_LIVE") == "1":
        pytest.skip("canário ligado; este teste cobre o caminho desligado")
    assert "USP_MCP_LIVE=1" in MOTIVO
    assert "uspdigital" in MOTIVO
    assert len(MOTIVO) > 80


# --- T74-T75: a página de requisitos, ao vivo (fatia de 14/09) --------------
#
# UMA requisição real a mais por execução, e ela é a que a fatia inteira
# depende: o recorte é de HTML, e HTML muda sem aviso e sem versão.


@ao_vivo
def test_t74_a_pagina_de_requisitos_ainda_tem_a_forma_que_o_recorte_espera():
    """Compara FORMA, não conteúdo: currículo, período ideal e tipo.

    PTC3314 tem um currículo só (3032) e dois pré-requisitos — medido em
    14/09. Se a USP mexer no layout, é aqui que aparece, e não em produção.
    """
    from usp_mcp.jupiter import requisitos as recorte

    c = cliente.ClienteJupiter(cliente.transporte_http)
    blocos = recorte.recortar(c.obter_requisitos("PTC3314"))

    assert blocos, (
        "a página de requisitos de PTC3314 não rendeu currículo nenhum. Ou a "
        "USP mudou o layout, ou o registro sumiu — os dois pedem medição nova, "
        "não conserto às cegas."
    )
    (bloco,) = blocos
    assert bloco.codcur == "3032"
    assert bloco.periodo_ideal == 6
    assert {e.sigla for e in bloco.exigencias} == {"PTC3213", "PSI3213"}
    assert all(e.tipo in recorte.TIPOS.values() for e in bloco.exigencias), (
        "apareceu um tipo de exigência fora dos três mapeados em 14/09. O "
        "mapeamento é de 3 pontos, não uma lei — meça antes de estender."
    )


@ao_vivo
def test_t75_o_rotulo_cru_continua_sendo_um_dos_tres_conhecidos():
    """O tipo traduzido sai de um rótulo em português que a USP escreve. Se ela
    inventar um quarto, `desconhecido` aparece — e é melhor descobrir aqui."""
    from usp_mcp.jupiter import requisitos as recorte

    c = cliente.ClienteJupiter(cliente.transporte_http)
    blocos = recorte.recortar(c.obter_requisitos("PSI3323"))

    exigencia = blocos[0].exigencias[0]
    assert exigencia.rotulo in recorte.TIPOS
    assert exigencia.tipo == "correquisito"


@ao_vivo
def test_t128_o_indice_real_monta_em_menos_de_60_s_e_acha_pmr3508():
    """Critério de aceite do spec de 26/10: se a montagem passar de 60 s, o
    índice tem que ir para o disco e o desenho volta para revisão — não se
    resolve com paralelismo (Invariante 5)."""
    import time

    from usp_mcp.jupiter import indice

    inicio = time.monotonic()
    ind = indice.montar_indice(cliente.ClienteJupiter(cliente.transporte_http))
    decorrido = time.monotonic() - inicio

    assert decorrido < 60, f"o índice levou {decorrido:.0f} s para montar"
    assert len(ind.modulos) >= 45, (
        f"só {len(ind.modulos)} módulos — eram 50 em 26/10. Ou a lista mudou de "
        "layout, ou módulos saíram: os dois pedem medição, não conserto às cegas."
    )
    assert any(
        m.codigo == "3112/5000" and any(d.sigla == "PMR3508" for d in m.disciplinas)
        for m in ind.modulos
    ), "PMR3508 saiu de Mecatrônica Avançada (3112/5000)"
