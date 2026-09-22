"""R38-R41: a fronteira MCP.

Fina de propósito, como as duas irmãs: o valor está na política, na projeção e
na ferramenta. O que só esta camada pode errar é a descrição que o modelo lê —
é ela que decide se "o que tem no bandejão hoje?" chega aqui ou vira busca na
web — o erro de nome desconhecido, e não arrastar o SDK para dentro da suíte.

R41 é o teste que a fronteira do Moodle não consegue ter: sem credencial
pessoal, a fronteira inteira roda ponta a ponta offline.
"""
import ast
import datetime
import pathlib

import pytest

from tests.rucard.conftest import HASH_DE_TESTE
from usp_mcp.rucard import erros, server
from usp_mcp.rucard.cliente import ClienteRucard

SEGUNDA = datetime.date(2026, 8, 24)


@pytest.mark.politica
def test_r38_descricao_fala_a_lingua_de_quem_pergunta():
    (ferramenta,) = server.listar_ferramentas()
    descricao = ferramenta["description"]

    for vazamento in ("/menu", "restaurants", "hash", "workinghours", "RUCard servicos"):
        assert vazamento not in descricao, (
            f"{vazamento!r} na descrição: o modelo escolhe a ferramenta lendo "
            "isto, e ninguém pergunta em nome de rota."
        )
    for vocabulario in ("bandejão", "almoço", "jantar", "hoje", "prefeitura", "sexta", "semana"):
        assert vocabulario in descricao.lower()

    # Invariante 7 na própria descrição: o que a ferramenta NÃO tem evita que o
    # modelo prometa histórico, café da manhã ou saldo do cartão.
    baixo = descricao.lower()
    assert "café" in baixo and "semana" in baixo
    assert "saldo" in baixo or "cartão" in baixo


@pytest.mark.politica
def test_r38b_o_schema_declara_os_quatro_rus_e_nao_convida_a_inventar_id():
    (ferramenta,) = server.listar_ferramentas()
    propriedades = ferramenta["inputSchema"]["properties"]

    assert ferramenta["inputSchema"]["required"] == []
    assert ferramenta["inputSchema"]["additionalProperties"] is False
    # "hoje, almoço, os quatro" é o caso mais comum: ele tem que ser o default.
    assert propriedades["dia"].get("default") == "hoje"

    enumerado = propriedades["restaurantes"]["items"]["enum"]
    assert enumerado == ["central", "prefeitura", "fisica", "quimicas"], (
        "o schema é onde o modelo aprende que só existem quatro RUs aqui, e "
        "pelo NOME que a pessoa fala — id numérico é detalhe da API. Sem enum, "
        "ele inventa e recebe negativa da allowlist: erro certo pela via mais cara."
    )
    descricao_do_dia = propriedades["dia"]["description"].lower()
    assert "sexta" in descricao_do_dia and "semana" in descricao_do_dia
    assert set(propriedades["refeicao"]["enum"]) == {
        "almoco", "jantar", "cafe", "todas"
    }


@pytest.mark.politica
def test_r39_nome_desconhecido_levanta_erro_legivel():
    with pytest.raises(erros.ErroRucard) as exc:
        server.chamar_ferramenta("saldo_do_cartao", {})
    assert "saldo_do_cartao" in str(exc.value)
    assert "bandejao" in str(exc.value)


@pytest.mark.politica
def test_r40_importar_o_servidor_nao_exige_o_sdk():
    arvore = ast.parse(pathlib.Path(server.__file__).read_text(encoding="utf-8"))
    for no in arvore.body:  # só o nível de módulo
        if isinstance(no, ast.Import):
            nomes = [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            nomes = [no.module or ""]
        else:
            continue
        for nome in nomes:
            assert not nome.startswith("mcp"), (
                f"import de topo de {nome!r}: a suíte roda sem o SDK, e isso "
                "quebraria a coleta por uma dependência que as funções puras "
                "nem usam."
            )


@pytest.mark.contrato
def test_r41_fronteira_ponta_a_ponta_offline(gravador, respostas_da_fatia):
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao", {"dia": "24/08/2026", "refeicao": "almoco"}, cliente=cliente
    )

    assert "24/08/2026" in texto and "seg" in texto
    assert "CENTRAL" in texto and "QUÍMICAS" in texto
    assert "Iscas de tilápia empanadas" in texto, "o cardápio não chegou ao texto"
    assert "1065" in texto, "calorias fora do texto: é parte do 'vale a pena'"
    assert "R$ 2,00" in texto
    # O 7 não serve jantar; pedindo só almoço, isso não deve poluir a saída.
    assert "jantar" not in texto.lower()


@pytest.mark.contrato
def test_r41b_o_texto_declara_o_que_nao_sabe(gravador, respostas_da_fatia):
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao", {"dia": "25/12/2026"}, cliente=cliente
    )
    assert "⚠" in texto, "o aviso do Invariante 7 sumiu na formatação"
    assert "24/08/2026" in texto


@pytest.mark.contrato
def test_r47_item_comum_a_todas_as_refeicoes_sai_uma_vez_no_rodape(
    gravador, respostas_da_fatia
):
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta("bandejao", {"dia": "24/08/2026"}, cliente=cliente)

    # Em 24/08 os sete pratos abertos têm "Minipão / refresco" e o arroz: uma vez cada.
    assert texto.count("Minipão / refresco") == 1
    assert texto.count("Arroz / feijão / arroz integral") == 1
    (rodape,) = [l for l in texto.splitlines() if l.startswith("Em todas as refeições acima:")]
    assert "Minipão / refresco" in rodape and "Arroz / feijão / arroz integral" in rodape
    assert "Iscas de tilápia empanadas" in texto, "o que varia continua na linha"


@pytest.mark.contrato
def test_r47b_com_uma_refeicao_so_nao_ha_rodape_e_a_linha_fica_inteira(
    gravador, respostas_da_fatia
):
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao",
        {"dia": "24/08/2026", "refeicao": "almoco", "restaurantes": ["central"]},
        cliente=cliente,
    )
    assert "Em todas as refeições" not in texto
    linha = next(l for l in texto.splitlines() if "Iscas de tilápia" in l)
    assert "Minipão / refresco" in linha and "Arroz / feijão / arroz integral" in linha


@pytest.mark.contrato
def test_r46_dia_semana_e_uma_chamada_de_ferramenta_com_os_sete_dias(
    gravador, respostas_da_fatia
):
    transporte = gravador(respostas_da_fatia)
    cliente = ClienteRucard(transporte, hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao", {"dia": "semana", "refeicao": "almoco"}, cliente=cliente, hoje=SEGUNDA
    )

    assert texto.startswith("Bandejão — semana de 24/08/2026 a 30/08/2026")
    assert "sex 28/08" in texto
    assert "Lombo com molho de limão" in texto, "terça no Central: um dia que não é hoje"
    assert "CENTRAL · almoço" in texto and "QUÍMICAS · almoço" in texto
    assert "jantar" not in texto.lower()
    assert sorted(transporte.rotas()) == ["menu/6", "menu/7", "menu/8", "menu/9", "restaurants"]


@pytest.mark.contrato
def test_r46b_dia_fechado_na_semana_e_uma_palavra_nao_um_paragrafo(
    gravador, respostas_da_fatia
):
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao",
        {"dia": "semana", "refeicao": "almoco", "restaurantes": ["central"]},
        cliente=cliente, hoje=SEGUNDA,
    )
    linha = next(l for l in texto.splitlines() if l.strip().startswith("sáb 29/08"))
    assert linha.strip() == "sáb 29/08: não serve"


# R46c — o teto do texto semanal — mudou para `test_custo.py` em 22/09/2026, com
# os mesmos números e a companhia que faltava: o teto do dia, a razão de redução
# e a asserção de que a semana numa chamada sai mais barata que os sete dias um
# a um. Aqui ele media o custo longe de onde o custo é declarado, e dava para ler
# a conta inteira do RUCard sem descobrir que o recorte mais pedido gasta 78%
# acima do teto do dia. Este arquivo continua com o que só a fronteira erra: a
# forma do texto (R46, R46b, R47, R48).


@pytest.mark.contrato
def test_r48_horario_constante_na_semana_sobe_pro_cabecalho_do_ru(
    gravador, respostas_da_fatia
):
    # Medido em 14/09/2026: o horário é igual em todos os dias abertos para 6
    # dos 7 pares RU+refeição da fixture — só o jantar do 9 varia (dia útil até
    # 19:45, sábado até 19:00). Repetir um horário constante 5 a 7 vezes por
    # semana é o mesmo desperdício que a fatoração de itens já corrigia.
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao", {"dia": "semana", "refeicao": "todas"}, cliente=cliente, hoje=SEGUNDA
    )

    (cabecalho_central,) = [l for l in texto.splitlines() if l.startswith("CENTRAL · almoço")]
    assert "11:15 às 14:15" in cabecalho_central
    linha_segunda = next(
        l for l in texto.splitlines() if l.strip().startswith("seg 24/08") and "Iscas" in l
    )
    assert "11:15" not in linha_segunda, "horário constante não repete na linha do dia"


@pytest.mark.contrato
def test_r48b_horario_que_varia_entre_dia_util_e_sabado_continua_na_linha_do_dia(
    gravador, respostas_da_fatia
):
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    texto = server.chamar_ferramenta(
        "bandejao", {"dia": "semana", "refeicao": "todas"}, cliente=cliente, hoje=SEGUNDA
    )

    (cabecalho_jantar_quimicas,) = [
        l for l in texto.splitlines() if l.startswith("QUÍMICAS · jantar")
    ]
    assert "17:30" not in cabecalho_jantar_quimicas, (
        "o jantar do 9 varia entre dia útil e sábado: um horário só no "
        "cabeçalho mentiria no sábado (§ design, R48b)"
    )
    linha_sabado = next(
        l for l in texto.splitlines() if l.strip().startswith("sáb 29/08") and "19:00" in l
    )
    assert "17:30 às 19:00" in linha_sabado
