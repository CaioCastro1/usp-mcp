"""TP1-TP9: o texto escrito na página da disciplina, sob demanda.

O achado de uso (24/09/2026): o critério de avaliação de uma disciplina estava no
texto da seção do topo da página, e `material` não o mostrava nem dizia que ele
existia. A fixture de PTC3314 tem o caso — a seção do topo tem 5.414 B de texto
(higienizado, com o tamanho real).
"""
from __future__ import annotations

import json

import pytest

from tests.moodle.conftest import FIXTURE_CONTEUDO_PTC3314
from tests.moodle.test_links_no_texto import DRIVE, _cliente, _label, _secao
from usp_mcp.moodle import disciplinas as disc
from usp_mcp.moodle import material as mat
from usp_mcp.moodle.erros import ErroMoodle
from usp_mcp.moodle.texto import sem_html

COURSEID_PTC3314 = 142036


@pytest.fixture(autouse=True)
def _cache_limpo():
    disc.limpar_cache()
    yield
    disc.limpar_cache()


@pytest.mark.contrato
def test_TP1_o_texto_da_secao_junta_resumo_e_blocos_de_texto_em_ordem():
    modulo_assign = {"id": 8001, "name": "EC-1", "modname": "assign",
                     "description": "<p>Aberto: 1 set. Vencimento: 8 set.</p>", "contents": []}
    conteudo = [_secao("Geral", [
        _label(7101, "Avaliação", "<p>Critério: média das provas.</p>"),
        modulo_assign,
        _label(7102, "Slides", f'<p>Os <a href="{DRIVE}">slides</a> ficam aqui.</p>'),
    ], summary="<p>Objetivos da disciplina.</p>")]

    (secao,) = mat.projetar_material(conteudo).secoes

    assert secao.texto == "Objetivos da disciplina.\nCritério: média das provas.\nOs slides ficam aqui."
    assert "Vencimento" not in secao.texto, "description de atividade não é texto da página"


@pytest.mark.contrato
def test_TP1b_secao_sem_prosa_tem_texto_vazio_e_os_anexos_nao_o_apagam():
    bruto = json.loads(FIXTURE_CONTEUDO_PTC3314.read_text(encoding="utf-8"))
    c = mat.projetar_material(bruto)
    topo = c.secoes[0]
    assert topo.nome == "Ondas e Linhas"
    assert topo.texto == sem_html(bruto[0]["summary"])
    assert c.secoes[-1].texto == "", "a última seção de PTC3314 tem summary vazio"

    # `_com_anexos` reconstrói as seções; o texto tem de sobreviver.
    anexos = mat.AnexosDeEntrega(itens=(mat.Item(
        nome="EP1.pdf", tipo="PDF", tamanho=None, modificado=None,
        url_externa=None, secao="Ondas e Linhas"),))
    assert mat._com_anexos(c, anexos).secoes[0].texto == topo.texto


@pytest.mark.contrato
def test_TP2_o_rodape_diz_que_ha_texto_e_como_pedir(disciplinas_brutas, conteudo_ptc3314):
    """O defeito do achado: o resumo de seção sumia calado."""
    r = mat.material(_cliente(disciplinas_brutas, conteudo_ptc3314), "PTC3314", agora=lambda: 0.0)

    assert "19 seções têm texto escrito na página" in r.texto
    assert "Ondas e Linhas" in r.texto
    assert "e mais 16" in r.texto
    assert "`texto`" in r.texto and "`tudo`" in r.texto
    assert "summary" not in r.texto and "label" not in r.texto


@pytest.mark.contrato
def test_TP3_uma_secao_so_fica_no_singular(disciplinas_brutas):
    conteudo = [_secao("Geral", [], summary="<p>Tragam calculadora.</p>")]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323", agora=lambda: 0.0)

    assert r.vazio_por == "sem_material", "texto não é arquivo: o vazio continua vazio"
    assert "1 seção tem texto escrito na página" in r.texto
    assert "Geral" in r.texto


@pytest.mark.contrato
def test_TP4_texto_da_secao_do_topo_sai_inteiro_com_uma_chamada_so(disciplinas_brutas, conteudo_ptc3314):
    """A pergunta do dono. Asserção sobre o parâmetro ENVIADO, não só a saída."""
    cliente = _cliente(disciplinas_brutas, conteudo_ptc3314)
    r = mat.material(cliente, "PTC3314", agora=lambda: 0.0, texto="ondas e linhas")

    assert sem_html(conteudo_ptc3314[0]["summary"]) in r.texto
    assert r.texto.startswith("PTC3314 (")
    assert r.mostrados == 1 and r.total == 19 and r.vazio_por is None
    assert cliente.params_de("core_course_get_contents")["courseid"] == COURSEID_PTC3314
    nomes = [f for f, _ in cliente.chamadas]
    assert nomes.count("core_course_get_contents") == 1
    assert "mod_assign_get_assignments" not in nomes, "os anexos não servem ao texto"


@pytest.mark.contrato
def test_TP5_tudo_traz_todas_as_secoes_com_texto(disciplinas_brutas, conteudo_ptc3314):
    r = mat.material(_cliente(disciplinas_brutas, conteudo_ptc3314), "PTC3314",
                     agora=lambda: 0.0, texto="TUDO")
    assert r.mostrados == 19
    assert 9_000 < len(r.texto.encode()) < mat._TETO_TEXTO
    assert "⚠" not in r.texto, "nada cortado, nada a declarar"


@pytest.mark.contrato
def test_TP6_secao_que_nao_existe_lista_as_que_existem(disciplinas_brutas, conteudo_ptc3314):
    r = mat.material(_cliente(disciplinas_brutas, conteudo_ptc3314), "PTC3314",
                     agora=lambda: 0.0, texto="bibliografia")
    assert r.vazio_por == "secao_sem_texto" and r.mostrados == 0
    assert "'bibliografia'" in r.texto
    assert "Ondas e Linhas" in r.texto and "30 novembro - 6 dezembro" in r.texto
    assert "`tudo`" in r.texto


@pytest.mark.contrato
def test_TP7_busca_e_texto_juntos_e_erro_antes_de_qualquer_chamada(disciplinas_brutas, conteudo_ptc3314):
    cliente = _cliente(disciplinas_brutas, conteudo_ptc3314)
    with pytest.raises(ErroMoodle, match="um de cada vez"):
        mat.material(cliente, "PTC3314", busca="lista", texto="tudo", agora=lambda: 0.0)
    assert cliente.chamadas == []


@pytest.mark.contrato
def test_TP8_corte_por_tamanho_e_declarado(disciplinas_brutas):
    longo = "<p>" + ("x" * 9_000) + "</p>"
    conteudo = [_secao(f"S{i}", [], summary=longo) for i in range(3)]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323",
                     agora=lambda: 0.0, texto="tudo")
    assert len(r.texto.encode()) <= mat._TETO_TEXTO + 400, "teto + a linha do aviso"
    assert r.mostrados == 2
    assert "S2" in r.texto.split("⚠", 1)[1], "a seção que ficou de fora é nomeada"

    enorme = [_secao("Única", [], summary="<p>" + ("y" * 30_000) + "</p>")]
    disc.limpar_cache()
    r = mat.material(_cliente(disciplinas_brutas, enorme), "PSI3323",
                     agora=lambda: 0.0, texto="única")
    assert r.mostrados == 1 and "foi cortado" in r.texto


@pytest.mark.contrato
def test_TP9_pagina_sem_texto_diz_isso(disciplinas_brutas):
    conteudo = [_secao("Aula 1", [])]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323",
                     agora=lambda: 0.0, texto="tudo")
    assert r.vazio_por == "sem_texto" and r.total == 0
    assert "não tem texto escrito" in r.texto


@pytest.mark.contrato
def test_TP10_o_schema_de_material_tem_texto_opcional():
    from usp_mcp.moodle.server import listar_ferramentas

    (porta,) = [f for f in listar_ferramentas() if f["name"] == "material"]
    props = porta["inputSchema"]["properties"]
    assert props["texto"]["type"] == "string"
    assert "texto" not in porta["inputSchema"]["required"]
    assert "avaliação" in porta["description"] or "avaliada" in porta["description"]


@pytest.mark.contrato
def test_TP11_o_despacho_repassa_texto(disciplinas_brutas, conteudo_ptc3314):
    from usp_mcp.moodle.server import chamar_ferramenta

    cliente = _cliente(disciplinas_brutas, conteudo_ptc3314)
    saida = chamar_ferramenta(
        "material", {"disciplina": "PTC3314", "texto": "Ondas e Linhas"}, cliente=cliente
    )
    assert "texto da página da disciplina" in saida
    assert "mod_assign_get_assignments" not in [f for f, _ in cliente.chamadas]
