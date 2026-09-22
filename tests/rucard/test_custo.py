"""R34-R37 e R58: custo.

Aqui o RUCard consegue a asserção que o Jupiter não conseguiu ter. Lá o payload
DWR *era* a resposta, e a razão de redução real ficou em ~1,8x. Aqui 6/7 do
payload é semana que ninguém pediu, mais um catálogo de 27,7 kB que é tabela de
apoio: a redução é grande, e é o motivo de existir projeção em vez de repasse.

Os tetos são medidos, com folga declarada, e a trava que não envelhece é a
CATEGÓRICA (R36/R58c) — número aperta com o tempo, conjunto de chaves não.

**São dois casos, e por muito tempo este arquivo só conhecia um.** R34-R37 medem
o DIA. A semana inteira numa chamada custava 8.018 B de texto contra um teto de
4.500 B escrito para o dia — 78% acima —, e quem lesse este arquivo concluiria
que a ferramenta cabe em 4.500 B. (Com a fatoração por custo de R59, do mesmo
dia, são 7.054 B; o excesso caiu de 78% para 57%, e não a zero — a semana é sete
vezes o conteúdo de um dia, e nenhuma formatação desfaz isso.) O teto do texto semanal existia, com o número
certo, mas morava na suíte da fronteira MCP, longe da conta: um teto que ninguém
relaciona ao orçamento não mostra custo nenhum. R58 traz o caso da semana para
cá, com teto PRÓPRIO — o do dia continua 4.500 B e não sobe para acomodá-la — e
com a asserção que justifica o número: a semana numa chamada é mais barata que
os sete dias pedidos um a um, que é a alternativa real de quem pergunta "que dia
tem lasanha".
"""
import datetime
import json

import pytest

from tests.rucard.conftest import HASH_DE_TESTE, texto
from usp_mcp.rucard import ferramentas, server
from usp_mcp.rucard.cliente import ClienteRucard

pytestmark = pytest.mark.contrato

SEGUNDA = datetime.date(2026, 8, 24)

# Medido em 31/08/2026 contra as fixtures da Fase 1, no pior caso (4 RUs × 2
# refeições): 3.367 B de estrutura e 1.929 B de texto, em 23 linhas. Um RU só
# com as duas refeições dá 970 B. Teto com ~34% de folga sobre o pior caso,
# porque o cardápio é texto livre e o tamanho varia com o que a USP escreve.
TETO_SAIDA_B = 4_500

# Cru que a resposta substitui: 4 menus mais o catálogo = 39.615 B nas fixtures,
# ~9.900 tokens, para responder sobre UM dia.
CRU_APROXIMADO_B = 39_615


def tamanho(o):
    return len(json.dumps(o, ensure_ascii=False, default=str).encode())


def _resposta(gravador, respostas_da_fatia):
    """Função, e não fixture do pytest: uma fixture que constrói o objeto sob
    teste transforma `FAILED` em `ERROR` (§4 do CONVENTIONS.md)."""
    cliente = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    return ferramentas.bandejao(cliente=cliente, hoje=SEGUNDA)


def test_r34_teto_absoluto_com_folga_declarada(gravador, respostas_da_fatia):
    resposta = _resposta(gravador, respostas_da_fatia)
    assert tamanho(resposta) <= TETO_SAIDA_B, f"saída: {tamanho(resposta)} B"


def test_r35_razao_de_reducao_medida_no_proprio_teste(gravador, respostas_da_fatia):
    resposta = _resposta(gravador, respostas_da_fatia)
    cru = sum(len(t.encode()) for t in respostas_da_fatia.values())
    assert cru > 30_000, "as fixtures encolheram: refaça a medida do §2 do spec"

    razao = cru / tamanho(resposta)
    assert razao > 10, (
        f"razão de redução {razao:.1f}x — abaixo do que justifica projetar. "
        "Se caiu, alguém passou a devolver a semana inteira ou o catálogo cru."
    )


def test_r35b_a_saida_nao_carrega_a_semana_que_ninguem_pediu(gravador, respostas_da_fatia):
    resposta = _resposta(gravador, respostas_da_fatia)
    despejo = json.dumps(resposta, ensure_ascii=False)
    # Datas dos outros seis dias da semana da Fase 1 não podem aparecer.
    for dia in ("25/08/2026", "26/08/2026", "27/08/2026", "28/08/2026",
                "29/08/2026", "30/08/2026"):
        assert dia not in despejo, (
            f"{dia} na resposta de 24/08: a projeção está devolvendo mais de um "
            "dia, e é 6/7 de payload que ninguém pediu."
        )
    # Nem o resto do catálogo.
    for gordura in ("EACH", "PIRACICABA", "latitude", "photourl", "hasCashier"):
        assert gordura not in despejo


def test_r36_conjunto_de_chaves_e_exatamente_o_declarado(gravador, respostas_da_fatia):
    resposta = _resposta(gravador, respostas_da_fatia)
    # A trava categórica: é assim que campo novo deixa de sobreviver por
    # descuido. R34 e R35 são numéricos e envelhecem; este não.
    assert set(resposta) == set(ferramentas.CAMPOS_SAIDA)

    for ru in resposta["restaurantes"]:
        assert set(ru) <= set(ferramentas.CAMPOS_RESTAURANTE), (
            f"campos fora do declarado no RU {ru.get('id')}: "
            f"{sorted(set(ru) - set(ferramentas.CAMPOS_RESTAURANTE))}"
        )
        for refeicao in ru["refeicoes"].values():
            assert set(refeicao) <= set(ferramentas.CAMPOS_REFEICAO), (
                f"campos fora do declarado numa refeição: "
                f"{sorted(set(refeicao) - set(ferramentas.CAMPOS_REFEICAO))}"
            )


def test_r37_erro_nunca_custa_mais_que_sucesso(gravador, respostas_da_fatia):
    resposta = _resposta(gravador, respostas_da_fatia)
    from usp_mcp.rucard.erros import ErroRucard

    respostas = dict(respostas_da_fatia)
    respostas["menu/6"] = (500, texto("erro_500"))
    cliente = ClienteRucard(gravador(respostas), hash_rucard=HASH_DE_TESTE)

    try:
        parcial = ferramentas.bandejao(
            cliente=cliente, hoje=SEGUNDA, restaurantes=["6"]
        )
        projetado = tamanho(parcial)
    except ErroRucard as exc:  # pragma: no cover — depende da regra de parcial
        projetado = tamanho({"erro": str(exc)})

    assert projetado < tamanho(resposta), (
        f"erro projetado {projetado} B >= sucesso {tamanho(resposta)} B. O HTML "
        "do Tomcat são 3.240 B que não respondem nada."
    )


def test_r37b_o_texto_para_o_modelo_tambem_tem_teto(gravador, respostas_da_fatia):
    resposta = _resposta(gravador, respostas_da_fatia)
    # A saída estruturada é o meio; o que chega ao modelo é o texto. Um teto só
    # na estrutura deixaria a formatação engordar sem ninguém ver.
    texto_formatado = server.formatar(resposta)
    assert len(texto_formatado.encode()) <= TETO_SAIDA_B
    assert len(texto_formatado.splitlines()) < 60


# --- R58: o teto da semana ---------------------------------------------------
#
# A semana não custa nada a mais na USP — são as mesmas 5 requisições de um dia,
# porque o `/menu` já devolve a semana e o cache é por RU (R45b trava isso). O
# que cresce é a RESPOSTA, e é ela que o modelo paga.
#
# Este teto nasceu de um achado da medição de custo de 22/09 e fecha duas linhas
# do backlog do mesmo dia: a resposta mais cara do projeto (2.642 tokens antes
# de R59, mais que qualquer coisa do Moodle) estava 78% acima do único teto que
# este arquivo declarava, o do DIA. O teto do texto semanal existia — R46c, na
# suíte da fronteira MCP, desde 14/09 —, e é isso que torna o caso interessante:
# não era teto faltando, era teto longe da conta. Um número que ninguém
# relaciona ao orçamento não mostra custo nenhum.
#
# **A forma é a de OR2 no Moodle, e a folga é máxima.** Um caso por recorte e
# arranjo, com teto de texto e de estrutura, e a asserção reprova nos DOIS
# sentidos: estourou, ou o teto ficou frouxo e parou de medir. Quem cortar bytes
# baixa o teto no mesmo commit — foi o que R59 fez com estes números.
#
# Medido em 22/09/2026 (4 RUs × 7 dias), depois de R59:
#
#     recorte · arranjo        texto     estrutura    texto antes de R59
#     almoço · alinhada        4.058 B    14.506 B     4.560 B
#     almoço · desencontrada   5.027 B    13.031 B     5.406 B
#     todas  · alinhada        7.054 B    21.932 B     8.018 B
#     todas  · desencontrada   7.836 B    19.372 B     8.677 B
#
# A estrutura não mudou com R59, e é de propósito: fatorar é decisão de TEXTO, e
# a projeção continua dizendo item por item o que veio em cada refeição.
#
# Os dois arranjos existem porque o caro NÃO é a semana alinhada: com um RU
# publicando outra semana, a fatoração rende menos e o texto sobe. Teto medido
# por um lado só já custou um defeito a este projeto (`BACKLOG-correcoes.md`,
# 12/09).
#
# R34 e R37b, do dia, seguem com a forma antiga (um teto só, folga de ~27%, e
# reprovando num sentido só). Não é esquecimento: o `TETO_SAIDA_B` cobre ao
# mesmo tempo a estrutura de 3.540 B e o texto de 1.601 B, e dar folga máxima
# aos dois exige separá-los. Está na linha de 22/09 do backlog que registra os
# testes de custo mais frouxos do Jupiter e do RUCard.
#
# O que estes tetos NÃO fazem: pegar a fatoração parando de render. Desligá-la
# cabe dentro deles (medido: 8.018 B sem a regra de custo, 8.841 B sem fatoração
# nenhuma, contra o teto de 9.000 B do pior arranjo). Quem pega isso é R58b,
# pela razão contra os sete dias, e as travas categóricas de R47/R48/R59 na
# fronteira. Teto é guarda de crescimento grosso — campo novo repetido 28 vezes,
# catálogo cru de volta —, e dizer que ele guarda mais do que guarda é como
# ficar sem nenhum.

# Os dois arranjos de fixture, por extenso. O segundo é o caro, e existe porque
# um RU fora da semana corrente é o caso comum de virada de semana (R27b).
ALINHADA = "os quatro RUs na semana da Fase 1"
DESENCONTRADA = "o RU 7 publicando outra semana"

# (recorte, arranjo) → (teto do texto, teto da estrutura), em bytes.
TETO_SEMANA_B = {
    ("almoco", ALINHADA): (4_650, 16_800),
    ("almoco", DESENCONTRADA): (5_800, 15_100),
    ("todas", ALINHADA): (8_100, 25_300),
    ("todas", DESENCONTRADA): (9_000, 22_400),
}

# A mesma de OR2: apertado o bastante para um parágrafo novo estourar, frouxo o
# bastante para mexer numa palavra não obrigar a mexer no teto.
FOLGA_MAXIMA = 0.15


def _respostas(arranjo, respostas_da_fatia):
    if arranjo == ALINHADA:
        return dict(respostas_da_fatia)
    return {**respostas_da_fatia, "menu/7": texto("menu_7_avisos")}


def _semana(gravador, respostas, refeicao):
    """A estrutura e o texto da semana, cada um com seu cliente.

    O texto sai por `chamar_ferramenta`, e não por `formatar_semana` direto: é o
    caminho que o modelo percorre, e um teto sobre a formatação que a fronteira
    não usa mediria outra coisa.
    """
    estrutura = ferramentas.bandejao_semana(
        refeicao=refeicao,
        cliente=ClienteRucard(gravador(respostas), hash_rucard=HASH_DE_TESTE),
        hoje=SEGUNDA,
    )
    formatado = server.chamar_ferramenta(
        "bandejao", {"dia": "semana", "refeicao": refeicao},
        cliente=ClienteRucard(gravador(respostas), hash_rucard=HASH_DE_TESTE),
        hoje=SEGUNDA,
    )
    return estrutura, formatado


@pytest.mark.parametrize("refeicao,arranjo", sorted(TETO_SEMANA_B))
def test_r58_a_semana_tem_teto_proprio(refeicao, arranjo, gravador, respostas_da_fatia):
    """Teto da semana, e não o do dia esticado para caber nela.

    `TETO_SAIDA_B` continua valendo 4.500 B para `bandejao` (R34, R37b): a cura
    de uma resposta 78% acima do orçamento não é afrouxar o orçamento do caso
    barato até a conta fechar — aí os dois custos somem de uma vez.

    Reprova nos dois sentidos, como OR2: teto que não acompanha um corte deixa
    de detectar o crescimento seguinte.
    """
    estrutura, formatado = _semana(
        gravador, _respostas(arranjo, respostas_da_fatia), refeicao
    )
    teto_texto, teto_estrutura = TETO_SEMANA_B[(refeicao, arranjo)]

    for medido, teto, o_que in (
        (len(formatado.encode()), teto_texto, "texto"),
        (tamanho(estrutura), teto_estrutura, "estrutura"),
    ):
        assert medido <= teto, (
            f"{o_que} da semana ({refeicao}, {arranjo}): {medido} B, acima do "
            f"teto de {teto} B. Se o crescimento é intencional, suba o teto "
            "NESTE commit e diga por quê."
        )
        folga = (teto - medido) / teto
        assert folga <= FOLGA_MAXIMA, (
            f"{o_que} da semana ({refeicao}, {arranjo}): {medido} B contra teto "
            f"de {teto} B, {folga:.0%} de folga, acima dos "
            f"{FOLGA_MAXIMA:.0%} permitidos. A saída encolheu e o teto não "
            "acompanhou — baixe o teto, senão ele para de medir."
        )

    assert len(formatado.splitlines()) < 80


def test_r58b_a_semana_numa_chamada_paga_por_si(gravador, respostas_da_fatia):
    """O teto da semana só se justifica contra a alternativa real.

    Quem pergunta "que dia tem lasanha?" não tem a opção de gastar 1.601 B: ou
    gasta a semana numa chamada, ou gasta sete chamadas de um dia. Medido em
    22/09/2026 na fixture alinhada: 7.054 B contra 10.421 B, razão 0,677 — e
    seis idas e voltas de ferramenta a menos, que não aparecem em byte nenhum.

    Esta asserção morde onde o teto não morde. Desligar a regra de custo de R59
    leva o texto a 8.018 B e desligar a fatoração inteira leva a 8.841 B — os
    dois dentro do teto de 9.000 B do pior arranjo, porque uma folga de 15% não
    tem como pegar uma regressão que cabe nela. A razão pega as duas: 0,751 e
    0,756 contra o limite de 0,73.

    **O horário no cabeçalho continua fora do alcance dela: 0,724, que passa
    raspando.** Está escrito porque a tentação seria apertar o limite até ela
    reprovar, e a 0,004 de distância ele deixaria de ser margem e viraria o
    valor medido com outro nome — qualquer variação de cardápio reprovaria o
    commit de outra pessoa. Quem guarda o horário é R48, categoricamente, e é o
    lugar certo: a propriedade é "não repetir o que não varia", não "caber em N
    bytes". A razão varia de 0,68 a 0,79 nos três arranjos de fixture, e por
    isso fica presa ao alinhado, onde a fatoração tem mais a ganhar.
    """
    cliente_semana = ClienteRucard(
        gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE
    )
    semana = server.formatar_semana(
        ferramentas.bandejao_semana(
            refeicao="todas", cliente=cliente_semana, hoje=SEGUNDA
        )
    )

    cliente_dia = ClienteRucard(gravador(respostas_da_fatia), hash_rucard=HASH_DE_TESTE)
    um_a_um = sum(
        len(
            server.formatar(
                ferramentas.bandejao(
                    dia=d.strftime("%d/%m/%Y"), refeicao="todas",
                    cliente=cliente_dia, hoje=SEGUNDA,
                )
            ).encode()
        )
        for d in ferramentas.dias_da_semana(SEGUNDA)
    )

    assert len(semana.encode()) < um_a_um * 0.73, (
        f"semana {len(semana.encode())} B contra {um_a_um} B em sete chamadas "
        f"(razão {len(semana.encode()) / um_a_um:.3f}): a economia caiu abaixo "
        "de 27% e a fatoração parou de render."
    )


def test_r58c_conjunto_de_chaves_da_semana_e_exatamente_o_declarado(
    gravador, respostas_da_fatia
):
    """A trava que não envelhece, agora no nível da semana.

    R36 cobre o dia, e a semana tem duas camadas que ele não enxerga: o
    envelope (`inicio`, `fim`, `dias`, `avisos`) e o recorte de cada dia dentro
    dele. Campo novo que escape por aqui multiplica por sete.
    """
    estrutura, _ = _semana(gravador, dict(respostas_da_fatia), "todas")

    assert set(estrutura) == set(ferramentas.CAMPOS_SEMANA)
    for dia in estrutura["dias"]:
        assert set(dia) == {"data", "dia_semana", "restaurantes"}, (
            f"campos fora do declarado no dia {dia.get('data')}: "
            f"{sorted(set(dia) - {'data', 'dia_semana', 'restaurantes'})}"
        )
        for ru in dia["restaurantes"]:
            assert set(ru) <= set(ferramentas.CAMPOS_RESTAURANTE)
            for refeicao in ru["refeicoes"].values():
                assert set(refeicao) <= set(ferramentas.CAMPOS_REFEICAO)
