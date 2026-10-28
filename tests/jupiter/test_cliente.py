"""T13-T25: o corpo da requisição é contrato.

O DWR responde 200 para corpo malformado. Sem estes testes, um erro de
serialização aparece como campo vazio, não como falha — e nenhuma outra
camada da suíte pega isso.

A allowlist mora aqui, e não em arquivo próprio, porque a allowlist É a
fronteira do cliente.
"""
import concurrent.futures
import json

import pytest

from tests.jupiter.conftest import fonte_de
from usp_mcp.jupiter import cliente, dwr, ferramentas

# §4.2 de notas/jupiter-recon.md, verbatim.
CORPO_ESPERADO = [
    "callCount=1",
    "windowName=",
    "c0-scriptName=ControlePublicoDWR",
    "c0-methodName=obter",
    "c0-id=0",
    "c0-param0=string:pubObterDisciplina",
    "c0-e1=string:PSI3323",
    "c0-e2=number:0",
    "c0-param1=Object_Object:{coddis:reference:c0-e1, verdis:reference:c0-e2}",
    "batchId=0",
    "instanceId=0",
    "page=%2Fjupiterweb%2FjupCarreira.jsp",
    "scriptSessionId=0000000000000000",
]

# `pubListarColegiado` e `pubListarCursoEntrada` SAÍRAM desta lista em 14/09,
# com decisão registrada no §9: elas não respondem pergunta nenhuma sozinhas —
# servem para marcar se um `codcur` é curso de ingresso, e é essa marca que
# impede "não consta" de sair como "extinto". `pubObterInfoCurso` continua fora
# por outro motivo, agora medido: devolve objeto vazio.
CONSULTAS_FORA_DA_FATIA = [
    "pubObterInfoCurso",
    "pubListarDiscipResp",
    "recuperarProjetoPedagogico",
    # Saiu da fatia em 14/09 (§9): exigia um `codcur` que a API não deixa
    # descobrir corretamente, e `requisitos(sigla)` responde sem ele.
    "pubListarRequisitoDisciplina",
]

# §4.1 do recon: os métodos genéricos do bean. executarBatch é o análogo
# exato de tool_mobile_call_external_functions — executor que anula
# qualquer filtro por nome de consulta.
METODOS_GENERICOS = [
    "executarBatch",
    "executar",
    "obterArquivo",
    "obterRelatorio",
    "obterCsv",
    "obterPdf",
    "obterZip",
    "obterWebdoc",
    "obterProgresso",
]


@pytest.fixture
def grav(gravador, psi3323):
    """Só o gravador. O cliente é construído DENTRO de cada teste: construí-lo
    aqui faria o NotImplementedError virar erro de setup em vez de falha, e o
    vermelho deixaria de ser legível."""
    return gravador([psi3323])


@pytest.mark.contrato
def test_t13_corpo_bate_linha_a_linha_com_o_recon(grav):
    g = grav
    cliente.ClienteJupiter(g).obter_disciplina("PSI3323")
    assert g.chamadas[0]["corpo"].splitlines() == CORPO_ESPERADO


@pytest.mark.contrato
def test_t14_objeto_serializado_por_referencia(grav):
    g = grav
    cliente.ClienteJupiter(g).obter_disciplina("PSI3323")
    corpo = g.chamadas[0]["corpo"]
    assert "\nc0-e1=string:PSI3323\n" in corpo, "cada c0-eN precisa de linha própria"
    assert "\nc0-e2=number:0\n" in corpo
    assert "reference:c0-e1" in corpo and "reference:c0-e2" in corpo
    assert "coddis:string:" not in corpo, "valor embutido no param em vez de referência"


@pytest.mark.contrato
def test_t15_valor_string_e_percent_encoded():
    # O charset do encode NÃO foi verificado na Fase 1 (§8 do recon). A
    # asserção fica no que é observável: nada de espaço cru na linha.
    corpo = dwr.serializar(
        metodo="obter",
        consulta="pubObterDisciplina",
        params={"coddis": "MAT 2454", "verdis": 0},
    )
    linha = next(l for l in corpo.splitlines() if l.startswith("c0-e1="))
    assert " " not in linha, f"espaço cru na linha do valor: {linha!r}"
    assert "%20" in linha


@pytest.mark.contrato
def test_t16_roteamento_do_metodo(gravador, psi3323, ingresso_poli):
    g1 = gravador([psi3323])
    cliente.ClienteJupiter(g1).obter_disciplina("PSI3323")
    assert g1.chamadas[0]["url"].endswith("ControlePublicoDWR.obter.dwr")

    g2 = gravador([ingresso_poli])
    cliente.ClienteJupiter(g2).listar_cursos_entrada("3")
    assert g2.chamadas[0]["url"].endswith("ControlePublicoDWR.listar.dwr")


@pytest.mark.contrato
def test_t17_stateless_sem_cookie_e_sem_handshake(grav):
    g = grav
    cliente.ClienteJupiter(g).obter_disciplina("PSI3323")
    assert len(g.chamadas) == 1, (
        "houve requisição extra antes: o handshake __System.generateId é "
        "dispensável (§4.4 do recon, verificado)"
    )
    assert "Cookie" not in g.chamadas[0]["cabecalhos"]
    assert "scriptSessionId=0000000000000000" in g.chamadas[0]["corpo"]
    assert "generateId" not in g.chamadas[0]["url"]


@pytest.mark.politica
def test_t18_user_agent_identificavel_com_contato(grav):
    g = grav
    cliente.ClienteJupiter(g).obter_disciplina("PSI3323")
    ua = g.chamadas[0]["cabecalhos"].get("User-Agent", "")
    assert "usp-mcp" in ua, f"User-Agent não identifica o projeto: {ua!r}"
    assert "http" in ua or "@" in ua, f"User-Agent sem contato: {ua!r}"
    for anonimo in ("curl", "python-urllib", "python-requests"):
        assert anonimo not in ua.lower()


@pytest.mark.politica
def test_t19_cliente_nao_le_segredo_nem_emite_credencial(monkeypatch, grav):
    monkeypatch.setenv("MOODLE_TOKEN", "NUNCA_DEVE_SER_LIDO_0000")
    monkeypatch.setenv("RUCARD_HASH", "NUNCA_DEVE_SER_LIDO_1111")
    g = grav
    cliente.ClienteJupiter(g).obter_disciplina("PSI3323")

    cab = g.chamadas[0]["cabecalhos"]
    assert "Authorization" not in cab and "Cookie" not in cab
    assert "NUNCA_DEVE_SER_LIDO" not in json.dumps(g.chamadas, ensure_ascii=False)

    fonte = fonte_de(cliente)
    for segredo in ("MOODLE_TOKEN", "RUCARD_HASH", "Authorization"):
        assert segredo not in fonte, (
            f"{segredo!r} em cliente.py. O Jupiter é público e o §6 do SPEC1 "
            "põe ele num servidor hospedado: ele não pode virar portador de "
            "credencial num refactor futuro."
        )


@pytest.mark.contrato
def test_t20_duas_perguntas_iguais_uma_requisicao(grav):
    g = grav
    c = cliente.ClienteJupiter(g)
    c.obter_disciplina("PSI3323")
    c.obter_disciplina("PSI3323")
    assert len(g.chamadas) == 1, "sem cache: a mesma pergunta bateu duas vezes na USP"


@pytest.mark.politica
def test_t21_ttl_segue_a_taxa_de_mudanca_do_dado(gravador, psi3323):
    # Comportamento, não constante: uma asserção sobre a constante testa o
    # valor; esta testa a regra do Invariante 5.
    relogio = {"t": 0.0}
    g = gravador([psi3323])
    c = cliente.ClienteJupiter(g, relogio=lambda: relogio["t"])

    c.obter_disciplina("PSI3323")
    relogio["t"] = 60 * 60 * 24 * 29
    c.obter_disciplina("PSI3323")
    assert len(g.chamadas) == 1, (
        "TTL curto demais: ementa muda por semestre, não por dia. O TTL segue "
        "a taxa de mudança do dado, não a frequência da pergunta."
    )

    relogio["t"] = 60 * 60 * 24 * 181
    c.obter_disciplina("PSI3323")
    assert len(g.chamadas) == 2, "TTL infinito: a ementa muda entre semestres"


@pytest.mark.contrato
def test_t22_requisicoes_nao_se_sobrepoem(psi3323):
    estado = {"dentro": False, "sobreposicoes": 0}

    def transporte(url, corpo, cabecalhos):
        if estado["dentro"]:
            estado["sobreposicoes"] += 1
        estado["dentro"] = True
        try:
            return 200, psi3323
        finally:
            estado["dentro"] = False

    c = cliente.ClienteJupiter(transporte)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(c.obter_disciplina, ["PSI3323", "PTC3314", "MAT2454", "PME3344"]))

    assert estado["sobreposicoes"] == 0, (
        "requisições sobrepostas. O §7 do recon pede concorrência 1, e o §8 "
        "registra que 26 requisições sem 429 NÃO provam que não haja rate limit."
    )


@pytest.mark.politica
@pytest.mark.parametrize(
    "metodo,consulta",
    [("listar", q) for q in CONSULTAS_FORA_DA_FATIA]
    + [(m, "pubObterDisciplina") for m in METODOS_GENERICOS],
)
def test_t23_superficie_travada_em_cinco_consultas(grav, metodo, consulta):
    c = cliente.ClienteJupiter(grav)
    with pytest.raises(cliente.ConsultaNegada):
        c._chamar(metodo=metodo, consulta=consulta, params={})
    assert set(cliente.CONSULTAS_PERMITIDAS) == {
        "pubObterDisciplina",
        "pubListarCursoEntrada",
        "pubListarColegiado",
        "pubGradeCurricular",
        "pubObterInfoCursoWeb",
    }, "a fatia tem cinco consultas; uma sexta precisa de decisão registrada no §9"


@pytest.mark.politica
def test_t24_negado_continua_negado_com_allow_writes(monkeypatch, grav):
    monkeypatch.setenv("USP_MCP_ALLOW_WRITES", "1")
    c = cliente.ClienteJupiter(grav)
    with pytest.raises(cliente.ConsultaNegada):
        c._chamar(metodo="executarBatch", consulta="pubObterDisciplina", params={})


@pytest.mark.politica
def test_t25_ferramenta_nao_aceita_nome_de_consulta():
    import inspect

    parametros = set(inspect.signature(ferramentas.disciplina).parameters)
    proibidos = {"consulta", "metodo", "funcao", "query", "scriptName", "methodName"}
    assert not (parametros & proibidos), (
        f"a ferramenta aceita {sorted(parametros & proibidos)} como argumento. "
        "Uma ferramenta que recebe o nome da consulta deixa de ter superfície, "
        "e a allowlist inteira vira decoração."
    )
    assert "_chamar" not in fonte_de(ferramentas), (
        "a ferramenta chama o choke point direto: o nome da consulta tem que "
        "estar fixo em cliente.py, não montado na camada de ferramenta."
    )
