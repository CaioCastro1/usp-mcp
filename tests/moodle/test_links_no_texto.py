"""L1-L12: os links que o professor deixa no TEXTO da página da disciplina.

O defeito, relatado pelo dono a partir de uso real: os slides de uma disciplina
estavam num link dentro de um bloco de texto (`label`, no vocabulário do Moodle),
`material` respondeu "não tem nenhum", e a resposta era falsa. `label` não tem
`contents`, então caía em `sem_conteudo` e o rodapé o chamava de "atividade com
consulta própria" — duas coisas que um bloco de texto não é.

**A amostra versionada NÃO cobre o caso, e isto é medido, não suposto.** Nas duas
capturas reais (`course_contents_psi3323.json`, 32 módulos; `_ptc3314.json`, 75
módulos) há ZERO módulos `label` e ZERO `href` em qualquer `description` ou
`summary`. L1 trava esse fato para que, no dia em que uma captura com `label`
entrar, alguém saiba que a medição de custo real ainda está por fazer. Os outros
testes usam um `label` sintético que copia as chaves do módulo real da fixture
(`id`, `contextid`, `modicon`, `noviewlink`, …) e só inventa o `description`.
"""
from __future__ import annotations

import json
import re

import pytest

from tests.moodle.conftest import (
    ENTREGAS_PSI3323_SEM_ANEXO,
    FIXTURE_CONTEUDO,
    FIXTURE_CONTEUDO_PTC3314,
    ClienteFalso,
)
from usp_mcp.moodle import arquivo as arq
from usp_mcp.moodle import disciplinas as disc
from usp_mcp.moodle import material as mat
from usp_mcp.moodle import texto

HOST = "https://edisciplinas.usp.br"
DRIVE = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz"
YOUTUBE = "https://youtu.be/dQw4w9WgXcQ"
PLUGINFILE = f"{HOST}/webservice/pluginfile.php/9600001/mod_label/intro/Aula1.pdf"


@pytest.fixture(autouse=True)
def _cache_limpo():
    disc.limpar_cache()
    yield
    disc.limpar_cache()


def _label(cmid: int, nome: str, descricao: str) -> dict:
    """Um `label` com a forma real de módulo da captura — só o texto é inventado.

    `label` não tem `url`, `contents` nem `contentsinfo`: é bloco de texto, e o
    Moodle só preenche `contents` para módulo que exporta arquivo.
    """
    return {
        "id": cmid,
        "name": nome,
        "instance": cmid + 1,
        "contextid": 9600000 + cmid,
        "visible": 1,
        "uservisible": True,
        "visibleoncoursepage": 1,
        "modicon": f"{HOST}/theme/image.php/edis/label/1787907095/monologo?filtericon=1",
        "modname": "label",
        "purpose": "content",
        "branded": False,
        "modplural": "Rótulos",
        "indent": 0,
        "onclick": "",
        "afterlink": None,
        "customdata": "",
        "noviewlink": True,
        "candisplay": True,
        "completion": 0,
        "downloadcontent": 1,
        "dates": [],
        "groupmode": 0,
        "description": descricao,
    }


def _secao(nome: str, modulos: list, summary: str = "") -> dict:
    return {"id": 1, "name": nome, "visible": 1, "summary": summary,
            "summaryformat": 1, "section": 1, "modules": modulos}


def _cliente(disciplinas_brutas, conteudo, arquivos=None) -> ClienteFalso:
    return ClienteFalso({
        "core_webservice_get_site_info": {"userid": 999},
        "core_enrol_get_users_courses": disciplinas_brutas,
        "core_course_get_contents": conteudo,
        "mod_assign_get_assignments": ENTREGAS_PSI3323_SEM_ANEXO,
    }, arquivos=arquivos)


# ------------------------------------------------------------ L1: a amostra

@pytest.mark.contrato
@pytest.mark.parametrize("fixture", [FIXTURE_CONTEUDO, FIXTURE_CONTEUDO_PTC3314], ids=lambda p: p.stem)
def test_L1_as_capturas_reais_nao_tem_label_nem_link_em_texto(fixture):
    """Medido em 17/09/2026: o caso relatado pelo dono não está na amostra.

    Se este teste um dia falhar é boa notícia — entrou uma captura com `label` —
    e a hora de medir o custo real e de trocar o sintético pelo dado.
    """
    bruto = json.loads(fixture.read_text(encoding="utf-8"))
    modnames = [m.get("modname") for s in bruto for m in s.get("modules") or ()]
    textos = [s.get("summary") or "" for s in bruto]
    textos += [m.get("description") or "" for s in bruto for m in s.get("modules") or ()]

    assert modnames.count("label") == 0
    assert not any("href" in t for t in textos)
    assert not any("http" in t for t in textos)

    # Consequência: a extração não muda NADA na projeção das capturas reais.
    c = mat.projetar_material(bruto)
    assert not any(i.no_texto for s in c.secoes for i in s.itens)
    assert c.links_ignorados == 0
    assert c.textos_sem_link == 0


# ----------------------------------------------------- L2-L4: o link aparece

@pytest.mark.contrato
def test_L2_link_externo_dentro_de_label_vira_item_com_titulo_e_contexto():
    """O caso do dono: slides num link dentro de um bloco de texto."""
    conteudo = [_secao("Semana 1", [_label(
        7001,
        "Informações do Cap 1 e Cap 2. Leiam antes da aula, e tragam...",
        '<p>Informações do Cap 1 e Cap 2. Leiam antes da aula, e tragam dúvidas.</p>'
        f'<p>Os <a href="{DRIVE}">slides do Cap 1</a> estão no Drive.</p>',
    )])]
    c = mat.projetar_material(conteudo)

    itens = [i for s in c.secoes for i in s.itens]
    assert len(itens) == 1
    (item,) = itens
    assert item.nome == "slides do Cap 1", "o título do link é o texto da âncora"
    assert item.tipo == "link"
    assert item.url_externa == DRIVE
    assert item.no_texto is True
    assert item.secao == "Semana 1"
    assert item.modulo.startswith("Informações do Cap 1"), (
        "o contexto é o começo do bloco de texto, que o Moodle já condensou em `name`"
    )
    assert "label" not in c.sem_conteudo, "bloco de texto não é atividade"
    assert c.total_itens == 1


@pytest.mark.contrato
def test_L3_a_resposta_da_ferramenta_mostra_o_link_e_diz_de_onde_veio(disciplinas_brutas):
    conteudo = [_secao("Semana 1", [_label(
        7001, "Informações do Cap 1",
        f'<p>Informações do Cap 1: <a href="{DRIVE}">slides</a>.</p>',
    )])]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323", agora=lambda: 0.0)

    assert r.total == 1
    assert DRIVE in r.texto
    assert "slides [link]" in r.texto
    assert "(Informações do Cap 1)" in r.texto
    assert "texto da página" in r.texto, "o rodapé diz que o link estava no texto, não publicado"
    assert "label" not in r.texto, "`label` é jargão do Moodle e não sai para quem lê"


@pytest.mark.contrato
def test_L4_busca_acha_o_link_pelo_titulo(disciplinas_brutas):
    conteudo = [_secao("Semana 1", [_label(
        7001, "Informações do Cap 1",
        f'<p><a href="{DRIVE}">Slides do Cap 1</a> e <a href="{YOUTUBE}">vídeo da aula</a>.</p>',
    )])]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323", busca="slides", agora=lambda: 0.0)

    assert r.mostrados == 1 and r.total == 2
    assert DRIVE in r.texto and YOUTUBE not in r.texto


# --------------------------------------------- L5-L7: o que é ruído, e por quê

@pytest.mark.politica
def test_L5_link_para_dentro_do_moodle_ancora_e_email_nao_sao_material(disciplinas_brutas):
    """Um link para `mod/forum/view.php` aponta para uma atividade que o rodapé já
    declara; `#topo` é âncora da própria página; `mailto:` é e-mail de pessoa.
    Nenhum é material — e nenhum some calado: o rodapé conta."""
    conteudo = [_secao("Geral", [_label(
        7002, "Avisos gerais",
        f'<p><a href="{HOST}/mod/forum/view.php?id=1">Fórum</a>, '
        f'<a href="{HOST}/course/view.php?id=2">outra turma</a>, '
        '<a href="/mod/quiz/view.php?id=3">quiz</a>, '
        '<a href="#topo">topo</a>, <a href="mailto:x@y.z">e-mail</a>, '
        '<a href="javascript:void(0)">x</a>.</p>',
    )])]
    cliente = _cliente(disciplinas_brutas, conteudo)
    r = mat.material(cliente, "PSI3323", agora=lambda: 0.0)

    assert r.total == 0, "nenhum destes é material"
    assert "x@y.z" not in r.texto
    assert "6 link" in r.texto, "o rodapé conta o que ficou de fora"
    assert "próprio e-Disciplinas" in r.texto


@pytest.mark.politica
def test_L6_arquivo_embutido_no_texto_e_listado_sem_a_url_e_baixavel(disciplinas_brutas, tmp_path):
    """Um PDF que o professor arrastou para dentro do bloco de texto chega como
    `href` para `webservice/pluginfile.php`. É arquivo interno: nome sai, endereço
    não (mesma regra dos `resource`), e `baixar_arquivo` o alcança pela mesma
    allowlist — sem uma linha nova no cliente."""
    conteudo = [_secao("Semana 1", [_label(
        7003, "Material da aula 1",
        f'<p>Material da aula 1: <a href="{PLUGINFILE}">apostila da aula 1</a>.</p>',
    )])]
    cliente = _cliente(disciplinas_brutas, conteudo, arquivos={PLUGINFILE: b"%PDF-1.4 x"})
    r = mat.material(cliente, "PSI3323", agora=lambda: 0.0)

    # O `[PDF]` que esta linha exigia até 22/09/2026 saiu do formato: o nome do
    # arquivo já diz a extensão, e repeti-la custava 933 tokens em PTC3314
    # (`notas/custo-em-token.md`). A propriedade que L6 defende é outra — o NOME
    # sai e o ENDEREÇO não —, e ela está nas quatro asserções abaixo.
    assert "Aula1.pdf" in r.texto
    assert "(apostila da aula 1)" in r.texto, "o título da âncora é o rótulo do professor"
    assert "pluginfile.php" not in r.texto
    assert "/webservice/" not in r.texto
    assert "token" not in r.texto.lower()

    disc.limpar_cache()
    baixado = arq.baixar_arquivo(cliente, "PSI3323", "aula1", agora=lambda: 0.0, raiz=tmp_path)
    assert cliente.downloads == [PLUGINFILE]
    assert "pluginfile.php" not in baixado.texto


@pytest.mark.contrato
def test_L7_link_que_repete_o_de_um_modulo_url_nao_sai_duas_vezes(conteudo_bruto):
    """O módulo `url` de PSI3323 costuma repetir a própria URL no `description`.
    Listar duas vezes seria pagar token para dizer a mesma coisa."""
    bruto = json.loads(json.dumps(conteudo_bruto))
    for s in bruto:
        for m in s["modules"]:
            if m["modname"] == "url":
                url = m["contents"][0]["fileurl"]
                m["description"] = f'<p>Planilha: <a href="{url}">aqui</a></p>'
                break
        else:
            continue
        break
    c = mat.projetar_material(bruto)

    assert c.total_itens == 29, "o link repetido entrou como item novo"
    urls = [i.url_externa for s in c.secoes for i in s.itens if i.url_externa]
    assert len(urls) == len(set(urls))


# --------------------------------------- L8-L10: quando não dá para dizer o que é

@pytest.mark.contrato
def test_L8_link_sem_titulo_sai_com_o_host_como_nome_e_diz_que_nao_tem_titulo(disciplinas_brutas):
    """Âncora que embrulha só uma imagem, ou cujo texto é a própria URL, não diz o
    que é. A saída não inventa: usa o host como nome e declara a falta."""
    conteudo = [_secao("Semana 2", [_label(
        7004, "Vídeo",
        f'<p><a href="{YOUTUBE}"><img src="{HOST}/x.png"></a> '
        f'<a href="{DRIVE}">{DRIVE}</a></p>',
    )])]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323", agora=lambda: 0.0)

    assert r.total == 2
    assert "youtu.be [link, sem título no texto]" in r.texto
    assert "drive.google.com [link, sem título no texto]" in r.texto
    assert "x.png" not in r.texto, "`src` de imagem não é link"


@pytest.mark.contrato
def test_L9_texto_sem_link_nenhum_fica_de_fora_e_o_rodape_conta(disciplinas_brutas):
    """Bloco de texto puro ("não haverá aula dia 20") não é arquivo nem link. Fica
    de fora, mas o rodapé nomeia a SEÇÃO que tem texto — quem lê sabe que a página
    tem texto que esta ferramenta não mostra, e onde pedi-lo."""
    conteudo = [_secao("Geral", [
        _label(7005, "Não haverá aula dia 20", "<p>Não haverá aula dia 20.</p>"),
        _label(7006, "Tragam calculadora", "<p>Tragam calculadora.</p>"),
    ])]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323", agora=lambda: 0.0)

    assert r.vazio_por == "sem_material"
    assert "1 seção tem texto escrito na página" in r.texto and "Geral" in r.texto
    assert "atividades" not in r.texto, "texto não é atividade, e o rodapé antigo dizia que era"


@pytest.mark.contrato
def test_L10_link_no_resumo_da_secao_entra_na_secao(disciplinas_brutas):
    """O `summary` da seção é o mesmo texto da página, só que sem módulo."""
    conteudo = [_secao("Semana 3", [], summary=f'<p>Ver <a href="{YOUTUBE}">aula gravada</a>.</p>')]
    c = mat.projetar_material(conteudo)

    (item,) = [i for s in c.secoes for i in s.itens]
    assert item.nome == "aula gravada" and item.secao == "Semana 3" and item.modulo == ""
    assert mat.rotulo_do_modulo(item) is None


# ------------------------------------------------- L11-L12: o extrator e o custo

@pytest.mark.contrato
def test_L11_o_extrator_de_links_mora_em_texto_e_traduz_entidade():
    """Uma semântica de HTML só (`sem_html` já mora lá): `&amp;` na URL vira `&`,
    e o título perde a marcação mas não as palavras."""
    achados = texto.links(
        '<a href="https://a.b/c?x=1&amp;y=2">um <b>dois</b></a> '
        "<A HREF='https://d.e'>três</A> <a name=\"sem-href\">quatro</a>"
    )
    assert achados == [("https://a.b/c?x=1&y=2", "um dois"), ("https://d.e", "três")]
    assert texto.links("") == [] and texto.links("<p>sem link</p>") == []


@pytest.mark.contrato
def test_L12_custo_por_link_e_pequeno_e_o_texto_ao_redor_nao_sai(disciplinas_brutas):
    """Medido sobre as capturas reais: os `summary` de PSI3323 somam 14.313 B e os
    `description` 1.986 B, contra ~6.500 B da projeção inteira — emitir o texto ao
    redor mais que triplicaria a resposta. Por isso o que sai por link é uma linha
    com título, tipo, URL e o começo do bloco (que o Moodle já cortou em `name`).
    Um bloco de 2 kB com um link custa o mesmo que um de 20 B com o mesmo link."""
    texto_longo = "<p>" + ("Leiam o capítulo com atenção antes da aula. " * 40) + "</p>"
    curto = [_secao("S", [_label(7007, "Leiam o capítulo com atenção antes da aula. Leiam o c...",
                                  f'<p><a href="{DRIVE}">slides</a></p>')])]
    longo = [_secao("S", [_label(7007, "Leiam o capítulo com atenção antes da aula. Leiam o c...",
                                  texto_longo + f'<p><a href="{DRIVE}">slides</a></p>' + texto_longo)])]
    assert len(json.dumps(longo)) > 2000

    r_curto = mat.material(_cliente(disciplinas_brutas, curto), "PSI3323", agora=lambda: 0.0)
    disc.limpar_cache()
    r_longo = mat.material(_cliente(disciplinas_brutas, longo), "PSI3323", agora=lambda: 0.0)

    assert r_curto.texto == r_longo.texto
    linha = re.search(r"  - slides \[link\]\n.*\n.*", r_curto.texto).group(0)
    assert len(linha.encode()) < 250, f"um link custa {len(linha.encode())} B"
