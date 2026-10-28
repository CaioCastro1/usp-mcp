"""T59-T66: o segundo transporte, a política de caminho e a ferramenta.

`listarCursosRequisitos` é GET de HTML — outra superfície que o DWR, e por isso
outra allowlist. O §2 do SPEC1 vale igual aqui: o default é negar, e um buscador
genérico de URL anularia qualquer filtro por nome de consulta.

**Asserção sobre o que FOI ENVIADO, não só sobre a saída** — a lição do T47: o
dublê devolve a fixture aconteça o que acontecer, então um teste que só olha o
resultado fica verde com a sigla trocada.
"""
import pytest

from usp_mcp.jupiter import cliente, erros, ferramentas, politica

pytestmark = pytest.mark.contrato


class GravadorGet:
    """Dublê do transporte GET: guarda a URL pedida e devolve a fixture."""

    def __init__(self, resposta, status=200):
        self.resposta = resposta
        self.status = status
        self.urls = []

    def __call__(self, url, cabecalhos):
        self.urls.append(url)
        return self.status, self.resposta


# --- política de caminho ---------------------------------------------------

def test_t59_caminho_fora_da_allowlist_e_negado():
    """`obterTurma` existe, é do mesmo host e traz nome de professor e sala.
    Não estar na fatia tem que bastar para ser negado."""
    decisao = politica.decidir_caminho("obterTurma")

    assert not decisao.permitida
    assert "obterTurma" in decisao.motivo


def test_t60_os_caminhos_permitidos_sao_os_das_fatias():
    assert politica.decidir_caminho("listarCursosRequisitos").permitida
    assert politica.CAMINHOS_PERMITIDOS == frozenset({"listarCursosRequisitos", "jupCursoLista"})


# --- cliente ---------------------------------------------------------------

def test_t61_a_sigla_enviada_e_a_sigla_pedida(psi3323_html):
    """T47 de novo: sem esta asserção, trocar a sigla por uma constante deixa a
    suíte verde, porque o dublê devolve a mesma fixture de qualquer jeito."""
    transporte = GravadorGet(psi3323_html)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    c.obter_requisitos("PTC3314")

    assert transporte.urls == [
        "https://uspdigital.usp.br/jupiterweb/listarCursosRequisitos?coddis=PTC3314"
    ]


def test_t62_o_cliente_devolve_bytes_nao_texto(psi3323_html):
    """Quem decide o charset é o recorte (ISO-8859-1). Se o cliente decodificar
    por conta, o acento chega corrompido e nenhum teste de contagem pega."""
    transporte = GravadorGet(psi3323_html)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    assert isinstance(c.obter_requisitos("PSI3323"), bytes)


def test_t63_status_diferente_de_200_vira_erro_legivel(psi3323_html):
    transporte = GravadorGet(psi3323_html, status=500)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    with pytest.raises(erros.RespostaInvalida, match="500"):
        c.obter_requisitos("PSI3323")


def test_t64_a_segunda_pergunta_igual_nao_vai_a_usp(psi3323_html):
    """Invariante 5. Requisito muda por currículo, não por pergunta."""
    transporte = GravadorGet(psi3323_html)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    c.obter_requisitos("PSI3323")
    c.obter_requisitos("PSI3323")

    assert len(transporte.urls) == 1


# --- ferramenta ------------------------------------------------------------

def test_t65_cada_curriculo_sai_marcado_por_pertencer_ao_ingresso(
    mat2455_html, ingresso_poli, colegiados, gravador
):
    """3033 consta na lista de ingresso; 3032 não. A marca não diz "extinto" —
    ênfase e módulo também ficam de fora da lista, e o JupiterWeb não distingue
    os três casos (§9, 14/09)."""
    c = cliente.ClienteJupiter(
        gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(mat2455_html),
    )
    ficha = ferramentas.requisitos("MAT2455", cliente=c)
    por_curso = {b["codcur"]: b for b in ficha["curriculos"]}

    assert por_curso["3033"]["ingresso"] is True
    assert por_curso["3032"]["ingresso"] is False


def test_t66_pagina_sem_curriculo_avisa_em_vez_de_devolver_lista_vazia(
    ptc3313_html, ingresso_poli, colegiados, gravador
):
    """Invariante 7. Lista vazia aqui seria lida como "não precisa de nada", e
    a fronteira de ênfase/módulo é justamente onde isso engana mais."""
    c = cliente.ClienteJupiter(
        gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(ptc3313_html),
    )
    ficha = ferramentas.requisitos("PTC3313", cliente=c)

    assert ficha["curriculos"] == []
    assert any("não conclua" in a.lower() for a in ficha["avisos"])


# --- T81: agrupar currículos com a mesma combinação de exigências (14/09) -----


def _mat2455(mat2455_html, ingresso_poli, colegiados):
    from usp_mcp.jupiter import cliente as _cliente, ferramentas
    from tests.jupiter.conftest import Gravador

    c = _cliente.ClienteJupiter(
        Gravador([colegiados, ingresso_poli]), transporte_get=GravadorGet(mat2455_html)
    )
    return ferramentas.requisitos("MAT2455", cliente=c)


def test_t81_mat2455_tem_23_curriculos_em_4_combinacoes(mat2455_html, ingresso_poli, colegiados):
    from usp_mcp.jupiter import ferramentas

    grupos = ferramentas.agrupar_curriculos(_mat2455(mat2455_html, ingresso_poli, colegiados)["curriculos"])

    assert len(grupos) == 4
    assert sum(len(membros) for _, membros in grupos) == 23
    assert [len(membros) for _, membros in grupos] == [13, 7, 2, 1], "maiores primeiro"


def test_t81b_o_tipo_separa_grupos_mesmo_com_as_mesmas_siglas(mat2455_html, ingresso_poli, colegiados):
    from usp_mcp.jupiter import ferramentas

    grupos = ferramentas.agrupar_curriculos(_mat2455(mat2455_html, ingresso_poli, colegiados)["curriculos"])
    por_codcur = {c["codcur"]: chave for chave, membros in grupos for c in membros}

    # 3250 exige MAT2454 + MAT3458 como requisito DURO; 3033 exige as mesmas como
    # FRACO. Mesmas siglas, grupos diferentes — é a informação que decide a matrícula.
    assert por_codcur["3250"] != por_codcur["3033"]
    assert {s for s, _, _, _ in por_codcur["3250"]} == {s for s, _, _, _ in por_codcur["3033"]}
    # 3033, 3032 e 3045 exigem a mesma coisa nos mesmos termos: um grupo só.
    assert por_codcur["3033"] == por_codcur["3032"] == por_codcur["3045"]
    # Os sete do projeto piloto (2000101) ficam juntos.
    piloto = {"3023", "3073", "3084", "3093", "3123", "3201", "3251"}
    assert len({por_codcur[c] for c in piloto}) == 1


def test_t81c_curriculo_sem_exigencia_forma_o_grupo_vazio_por_ultimo():
    from usp_mcp.jupiter import ferramentas

    a = {"codcur": "1", "exigencias": [{"sigla": "X", "nome": "x", "tipo": "requisito", "rotulo": "Requisito"}]}
    vazio = {"codcur": "2", "exigencias": []}
    grupos = ferramentas.agrupar_curriculos([vazio, a])
    assert grupos[-1][0] == () and grupos[-1][1] == [vazio]


# --- T94-T99: HTTP 200 não é prova de que a página é a certa ------------------
#
# O caminho do DWR já valida FORMA: sem o marcador de fim, o envelope não é
# envelope e `decodificar` recusa. O caminho HTML não validava nada — só o
# status. Qualquer corpo com 200 passava, `recortar` não achava `Curso:` e
# devolvia `[]`, e a ferramenta emitia o aviso de "nenhum currículo", que diz ao
# modelo que a disciplina pode não exigir nada. Com o TTL de um semestre, a
# resposta errada ficava até o processo morrer.
#
# **O marcador escolhido, e por quê.** A conjunção de dois: `<title>Jupiterweb`
# e a palavra `equisito` (que casa "Requisito", "requisitos" e "REQUISITOS"),
# as duas sem diferenciar maiúscula. Medido nas nove páginas HTML capturadas:
#
#   - as TRÊS fixturas de `listarCursosRequisitos` trazem as duas, inclusive a
#     de zero currículo, cujo único "equisito" está na frase que a própria
#     página exibe ("Disciplina não tem requisitos");
#   - a sigla NÃO serve: a fixtura de zero currículo não contém a própria;
#   - `Curso:` NÃO serve: é exatamente o que separa "tem currículo" de "não
#     tem", e usá-lo como marcador de forma transformaria a resposta legítima
#     de PTC3313 em erro — o defeito de hoje virado do avesso;
#   - o título sozinho NÃO serve: as seis outras páginas do JupiterWeb
#     capturadas têm o mesmo `<title>Jupiterweb</title>`;
#   - `equisito` sozinha é evidência fraca de que se chegou ao JupiterWeb: a
#     palavra cabe na página de manutenção de qualquer aplicação.
#
# **O limite, declarado em vez de escondido:** das seis outras páginas do
# JupiterWeb, a conjunção rejeita cinco. A sexta é a ficha da disciplina, que
# passa só porque carrega um LINK para esta mesma página. Este caminho nunca
# pede aquela URL, então a confusão não é alcançável — mas ela é real, e fica
# escrita.

PAGINAS_QUE_NAO_SAO_A_DE_REQUISITOS = {
    "manutencao": (
        b"<html><head><title>Sistema em manuten&ccedil;&atilde;o</title></head>"
        b"<body><h1>Servi&ccedil;o temporariamente indispon&iacute;vel</h1></body></html>"
    ),
    "login": (
        b"<html><head><title>USP Digital - Autentica&ccedil;&atilde;o</title></head>"
        b"<body><form action='login'><input name='usuario'></form></body></html>"
    ),
    "corpo_vazio": b"",
    "so_espaco": b"   \r\n\r\n   ",
    # O caso que o marcador de titulo sozinho deixaria passar: pagina do
    # JupiterWeb, mas nao esta.
    "outra_pagina_do_jupiter": (
        b"<html><head><title>Jupiterweb</title></head><body>"
        b"<div id='my_web_cabecalho'>Busca de Disciplina</div></body></html>"
    ),
}


@pytest.mark.parametrize("nome", sorted(PAGINAS_QUE_NAO_SAO_A_DE_REQUISITOS))
def test_t94_pagina_com_200_que_nao_e_a_de_requisitos_vira_erro_legivel(nome):
    bruto = PAGINAS_QUE_NAO_SAO_A_DE_REQUISITOS[nome]
    transporte = GravadorGet(bruto)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    with pytest.raises(erros.RespostaInvalida) as capturado:
        c.obter_requisitos("PSI3323")

    texto = str(capturado.value)
    assert len(texto) > 60, f"{len(texto)} caracteres: {texto!r}"
    assert "requisito" in texto.lower(), (
        f"a mensagem não diz que a página esperada era a de requisitos: {texto!r}"
    )
    # O cru não sobe: a mensagem é a resposta, e a página pode ter 66 kB.
    assert "<html" not in texto.lower() and "<title" not in texto.lower(), texto


@pytest.mark.parametrize(
    "fixtura", ["psi3323_html", "mat2455_html", "ptc3313_html"]
)
def test_t95_as_tres_paginas_reais_passam_pelo_marcador(fixtura, request):
    """A guarda contra um marcador apertado demais.

    `ptc3313_html` é a que importa: ela é a resposta LEGÍTIMA de zero currículo,
    e um marcador que exigisse `Curso:` (ou a própria sigla) a transformaria em
    erro. Trocaria um silêncio ruim por um vermelho mentiroso.
    """
    bruto = request.getfixturevalue(fixtura)
    transporte = GravadorGet(bruto)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    assert c.obter_requisitos("PSI3323") == bruto


def test_t96_a_pagina_recusada_nao_entra_no_cache(psi3323_html):
    """A outra metade do defeito: com o TTL de um semestre, uma página de
    manutenção guardada responderia errado pela vida inteira do processo."""
    transporte = GravadorGet(PAGINAS_QUE_NAO_SAO_A_DE_REQUISITOS["manutencao"])
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    with pytest.raises(erros.RespostaInvalida):
        c.obter_requisitos("PSI3323")

    # A USP voltou do ar: a segunda pergunta tem de sair de novo, e responder.
    transporte.resposta = psi3323_html
    assert c.obter_requisitos("PSI3323") == psi3323_html
    assert len(transporte.urls) == 2, (
        "a página inválida ficou no cache: a segunda pergunta não saiu"
    )


def test_t97_a_ferramenta_nao_chama_a_pagina_ruim_de_nenhum_curriculo(
    ingresso_poli, colegiados, gravador
):
    """Ponta a ponta: o aviso de "nenhum currículo" não pode nascer de uma
    página que nem era a de requisitos. Ele diz ao modelo que a disciplina
    talvez não exija nada — a conclusão mais cara de errar aqui."""
    c = cliente.ClienteJupiter(
        gravador([colegiados, ingresso_poli]),
        transporte_get=GravadorGet(PAGINAS_QUE_NAO_SAO_A_DE_REQUISITOS["manutencao"]),
    )

    with pytest.raises(erros.RespostaInvalida):
        ferramentas.requisitos("PSI3323", cliente=c)


def test_t98_a_sigla_vai_percent_encoded_na_url(psi3323_html):
    """`dwr.serializar` já usa `quote`; este caminho montava a URL por f-string.

    Uma sigla com `#` corta a URL no fragmento: o que sairia seria
    `?coddis=PSI` e a resposta seria de outra disciplina, com cara de certa.
    """
    transporte = GravadorGet(psi3323_html)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    c.obter_requisitos("PSI#3323")

    (url,) = transporte.urls
    assert url.endswith("?coddis=PSI%233323"), url
    assert "#" not in url, (
        "o `#` cru sobrevive na URL e tudo depois dele vira fragmento: a "
        "requisição sai sem o resto da sigla"
    )


def test_t99_sigla_com_espaco_e_barra_tambem_e_escapada(psi3323_html):
    """Duas outras que o f-string deixava passar cruas. `/` mudaria de rota."""
    transporte = GravadorGet(psi3323_html)
    c = cliente.ClienteJupiter(lambda *a: (200, ""), transporte_get=transporte)

    c.obter_requisitos("A B/C")

    (url,) = transporte.urls
    assert url.endswith("?coddis=A%20B%2FC"), url
