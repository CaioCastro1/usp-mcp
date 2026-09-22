"""M1-M18 — "o que mudou em PTC3314 desde ontem?".

`core_course_get_updates_since` é a chamada mais barata do projeto (~100 tokens
para 7 dias, catálogo §3.3) e devolve **ponteiro, não conteúdo**: diz qual `cmid`
mudou e em quê, e nada mais. As duas consequências mandam neste arquivo:

1. **O ponteiro sozinho não responde.** "O módulo 6372306 mudou os arquivos" não
   é português. Traduzir `cmid` → nome exige `core_course_get_contents`, que já
   está na allowlist e é a chamada CARA (~14.500 tokens crus por disciplina).
   M3 e M4 são o par que trava a decisão de quando ela acontece: nunca quando não
   houve mudança nenhuma, que é o caso comum.
2. **A janela é por DIAS e não por carimbo**, e M1/M8/M9 travam isso. A
   justificativa está no §9 e no módulo; o resumo é que quem escolhe o parâmetro
   é um modelo, e epoch calculado por modelo erra para "não mudou nada", que é o
   falso vazio que ninguém consegue ver.

Procedência: a resposta de `updates_since` é **escrita à mão** (ressalva inteira
no `conftest`). O que é real são os `cmid`, que vêm de
`course_contents_ptc3314.json` — e é contra essa fixture real que a tradução é
exercitada, que é justamente a metade da ferramenta com como errar calada.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from tests.moodle.conftest import (
    CMID_APOSTILA,
    CMID_FORUM_AVISOS,
    CMID_QUE_NAO_EXISTE,
    ClienteFalso,
    mudancas_falsas,
)
from usp_mcp.moodle import disciplinas as dis
from usp_mcp.moodle import o_que_mudou as om
from usp_mcp.moodle.erros import ErroMoodle, MoodleIndisponivel
from usp_mcp.moodle.projecao import FUSO_SAO_PAULO

pytestmark = pytest.mark.contrato

USERID = 8214
PTC3314 = 142036
AGORA = datetime(2026, 9, 14, 16, 0, tzinfo=FUSO_SAO_PAULO)


@pytest.fixture(autouse=True)
def _cache_limpo():
    dis.limpar_cache()
    yield
    dis.limpar_cache()


def _cliente(disciplinas_brutas, conteudo, *, mudancas=None):
    return ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": USERID},
            "core_enrol_get_users_courses": disciplinas_brutas,
            "core_course_get_updates_since": (
                mudancas_falsas() if mudancas is None else mudancas
            ),
            "core_course_get_contents": conteudo,
        }
    )


def _funcoes(cliente):
    return [f for f, _ in cliente.chamadas]


# --------------------------------------------------------------------------
# A janela: dias, e não carimbo
# --------------------------------------------------------------------------


def test_m1_a_janela_vira_since_na_chamada(disciplinas_brutas, conteudo_ptc3314):
    """M1 — `dias` é parâmetro da CHAMADA (`since`), nunca filtro aplicado
    depois. Mesma regra do `timesortfrom` de `o_que_vence`: filtrar em memória já
    pagou o transporte que a projeção existe para evitar.

    Asserção sobre o parâmetro ENVIADO — o dublê devolveria a mesma resposta
    para qualquer `since`, então só isto pega uma janela calculada errado.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    om.o_que_mudou(c, "PTC3314", dias=3, agora=AGORA)

    enviado = c.params_de("core_course_get_updates_since")
    assert enviado["courseid"] == PTC3314
    assert enviado["since"] == int((AGORA - timedelta(days=3)).timestamp())


def test_m8_a_janela_padrao_e_de_uma_semana(disciplinas_brutas, conteudo_ptc3314):
    """M8 — "mudou alguma coisa?" sem janela dita é a pergunta da semana.

    O default é declarado no `inputSchema` que o modelo lê, e o texto da resposta
    o repete: uma janela que só existe no código é uma janela que quem lê não tem
    como conferir.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    enviado = c.params_de("core_course_get_updates_since")
    assert enviado["since"] == int((AGORA - timedelta(days=om.DIAS_PADRAO)).timestamp())
    assert str(om.DIAS_PADRAO) in r.texto


def test_m9_janela_sem_tamanho_e_erro_legivel_e_nao_resposta_vazia(
    disciplinas_brutas, conteudo_ptc3314
):
    """M9 — `dias=0` faz `since` ser agora, e "nada mudou entre agora e agora" é
    verdade e é inútil: sai lista vazia com cara de "a disciplina está parada".

    O Invariante 6 pede o contrário — erro legível antes de gastar chamada, e
    dizendo o que fazer. Negativo é pior ainda: `since` no futuro é pergunta que
    o Moodle aceita e responde com silêncio.
    """
    for dias in (0, -3):
        dis.limpar_cache()
        c = _cliente(disciplinas_brutas, conteudo_ptc3314)

        with pytest.raises(ErroMoodle) as erro:
            om.o_que_mudou(c, "PTC3314", dias=dias, agora=AGORA)

        assert str(dias) in str(erro.value)
        assert "core_course_get_updates_since" not in _funcoes(c), (
            f"gastou chamada com dias={dias}"
        )


def test_m7_a_janela_sai_por_extenso_com_o_instante_exato(
    disciplinas_brutas, conteudo_ptc3314
):
    """M7 — a saída diz DESDE QUANDO ela olhou, com dia e hora.

    É o que o carimbo explícito daria de graça e a janela por dias precisa
    escrever: sem isso, perguntar de novo amanhã não tem como ser encaixado com
    a resposta de hoje, e o buraco entre as duas passa despercebido.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    r = om.o_que_mudou(c, "PTC3314", dias=2, agora=AGORA)

    from usp_mcp.moodle.texto import formatar_data

    assert formatar_data(AGORA - timedelta(days=2)) in r.texto
    assert "2 dias" in r.texto


def test_m17_o_filtro_de_tipos_nao_e_enviado(disciplinas_brutas, conteudo_ptc3314):
    """M17 — `filter` é `[opt=[]]`, e vazio significa TODOS os tipos.

    Aqui, ao contrário do `perpage` de `avisos` e do `userid` de `notas`, o
    default não é uma incógnita: é o documentado, e é o que queremos. Mandar uma
    lista seria decidir por quem pergunta o que conta como mudança — e quem
    pergunta "mudou alguma coisa?" não pediu para escolher.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert "filter" not in c.params_de("core_course_get_updates_since")


def test_m2_sigla_que_nao_resolve_nao_gasta_chamada(
    disciplinas_brutas, conteudo_ptc3314
):
    """M2 — mesma regra das três irmãs: descobrir pelo Moodle que a pergunta
    estava errada gasta chamada da conta do dono à toa."""
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    with pytest.raises(ErroMoodle) as erro:
        om.o_que_mudou(c, "XYZ9999", agora=AGORA)

    assert "XYZ9999" in str(erro.value)
    assert "core_course_get_updates_since" not in _funcoes(c)


# --------------------------------------------------------------------------
# A tradução: o ponteiro sozinho não é resposta
# --------------------------------------------------------------------------


def test_m3_sem_mudanca_a_chamada_cara_nao_acontece(
    disciplinas_brutas, conteudo_ptc3314
):
    """M3 — o caso comum é "não mudou nada", e é o que mantém a ferramenta
    barata: `updates_since` custa ~100 tokens e `get_contents` custa ~14.500
    (catálogo §3.3). Traduzir uma lista vazia pagaria o caro para dizer o barato.

    E vazio não vira silêncio: sai rotulado, com a janela, porque "a disciplina
    está parada" e "eu perguntei errado" são indistinguíveis sem rótulo (§9,
    28/08).
    """
    c = _cliente(
        disciplinas_brutas, conteudo_ptc3314, mudancas=mudancas_falsas([])
    )

    r = om.o_que_mudou(c, "PTC3314", dias=5, agora=AGORA)

    assert "core_course_get_contents" not in _funcoes(c), (
        "traduziu cmid nenhum e gastou a chamada cara mesmo assim"
    )
    assert r.vazio_por == "sem_mudanca"
    assert "5 dias" in r.texto


def test_m4_com_mudanca_traduz_o_cmid_uma_vez_so(
    disciplinas_brutas, conteudo_ptc3314
):
    """M4 — a tradução acontece UMA vez, e os nomes saem da fixture real.

    "Apostila sobre Linhas e Ondas" é o `cmid` 6372306 de PTC3314 em
    `course_contents_ptc3314.json`. Se o teste inventasse o nome, ele provaria só
    que sabe ler o dicionário que escreveu.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert _funcoes(c).count("core_course_get_contents") == 1
    assert c.params_de("core_course_get_contents")["courseid"] == PTC3314
    assert "Apostila sobre Linhas e Ondas" in r.texto
    assert "Avisos" in r.texto
    assert str(CMID_APOSTILA) not in r.texto, "deixou o número no lugar do nome"


def test_m5_cmid_desconhecido_nao_some_da_lista(
    disciplinas_brutas, conteudo_ptc3314
):
    """M5 — Invariante 7 no caso raro, que é onde ele costuma ser quebrado.

    `get_contents` esconde módulo que o aluno não pode ver, e `updates_since`
    pode apontar para ele. Sumir com a linha faria a resposta jurar que nada mais
    mudou; manter o número diz que mudou algo que não deu para nomear.
    """
    c = _cliente(
        disciplinas_brutas,
        conteudo_ptc3314,
        mudancas=mudancas_falsas(
            [(CMID_QUE_NAO_EXISTE, [("configuration", 1788900000)])]
        ),
    )

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert str(CMID_QUE_NAO_EXISTE) in r.texto
    assert r.sem_nome == 1
    assert "não deu para identificar" in r.texto


def test_m14_mudanca_fora_de_modulo_nao_vira_modulo_zero(
    disciplinas_brutas, conteudo_ptc3314
):
    """M14 — `contextlevel` também vem `course`: é a própria disciplina mudando
    (seção nova, nome trocado), e não um módulo.

    Tratar tudo como módulo faria a resposta procurar um `cmid` que é id de
    curso, não achar, e rotular de "não identificado" uma mudança que tem nome.
    """
    c = _cliente(
        disciplinas_brutas,
        conteudo_ptc3314,
        mudancas=mudancas_falsas(
            [(PTC3314, [("configuration", 1788900000)])], contextlevel="course"
        ),
    )

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert "a própria disciplina" in r.texto
    assert r.sem_nome == 0


def test_m6_o_tipo_de_mudanca_sai_em_portugues_e_o_desconhecido_sai_cru(
    disciplinas_brutas, conteudo_ptc3314
):
    """M6 — `contentfiles` não é português, e "mudou alguma coisa" não é
    resposta. Nome fora da lista sai CRU, pela mesma regra do `modulename` de
    `o_que_vence`: um rótulo desconhecido é melhor que um rótulo inventado."""
    c = _cliente(
        disciplinas_brutas,
        conteudo_ptc3314,
        mudancas=mudancas_falsas(
            [
                (CMID_APOSTILA, [("contentfiles", 1788900000)]),
                (CMID_FORUM_AVISOS, [("coisanova", 1788910000)]),
            ]
        ),
    )

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert "contentfiles" not in r.texto
    assert "arquivo" in r.texto
    assert "coisanova" in r.texto, "inventou rótulo para um tipo que não conhece"


def test_m13_a_data_tem_a_mesma_grafia_das_outras_ferramentas(
    disciplinas_brutas, conteudo_ptc3314
):
    """M13 — J18 de novo: quem pergunta "o que mudou" e depois "o que vence" lê
    as duas respostas na mesma noite."""
    from usp_mcp.moodle.texto import formatar_data

    quando = 1788900000
    c = _cliente(
        disciplinas_brutas,
        conteudo_ptc3314,
        mudancas=mudancas_falsas([(CMID_APOSTILA, [("contentfiles", quando)])]),
    )

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert formatar_data(datetime.fromtimestamp(quando, FUSO_SAO_PAULO)) in r.texto


# --------------------------------------------------------------------------
# Teto, aviso, erro e cobertura
# --------------------------------------------------------------------------


def test_m10_teto_de_modulos_e_declarado_com_a_cura(
    disciplinas_brutas, conteudo_ptc3314
):
    """M10 — Invariante 7: o corte é dito, com a contagem e com o que fazer.

    O corte fica com as mudanças MAIS RECENTES: quem pergunta "o que mudou desde
    ontem" quer o topo da pilha, não o fundo.
    """
    muitas = [
        (CMID_APOSTILA + i, [("configuration", 1788900000 + i)])
        for i in range(om.TETO_MODULOS + 5)
    ]
    c = _cliente(
        disciplinas_brutas, conteudo_ptc3314, mudancas=mudancas_falsas(muitas)
    )

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert r.truncado
    assert r.mostrados == om.TETO_MODULOS
    assert "5" in r.texto and str(om.TETO_MODULOS) in r.texto
    assert "dias" in r.texto, "cortou sem dizer como estreitar a janela"


def test_m11_warning_da_api_vira_aviso(disciplinas_brutas, conteudo_ptc3314):
    """M11 — o que o Moodle recusou verificar é dito, senão a lista parece
    completa e "nada mais mudou" vira mentira por omissão."""
    c = _cliente(
        disciplinas_brutas,
        conteudo_ptc3314,
        mudancas=mudancas_falsas(com_warning=True),
    )

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert "não puderam ser verificad" in r.texto


def test_m12_erro_do_cliente_sobe_e_nao_vira_nada_mudou(
    disciplinas_brutas, conteudo_ptc3314
):
    """M12 — o outro lado do bug do §9 de 28/08. Aqui ele é pior que nas irmãs:
    "nada mudou" é uma resposta que quem lê ACEITA sem estranhar, então uma falha
    engolida aqui nunca seria descoberta."""

    def _explode(_params):
        raise MoodleIndisponivel("o e-Disciplinas não respondeu")

    c = _cliente(disciplinas_brutas, conteudo_ptc3314)
    c._respostas["core_course_get_updates_since"] = _explode

    with pytest.raises(MoodleIndisponivel):
        om.o_que_mudou(c, "PTC3314", agora=AGORA)


def test_m15_a_saida_diz_o_que_o_ponteiro_nao_sabe(
    disciplinas_brutas, conteudo_ptc3314
):
    """M15 — Invariante 6: esta função diz QUE mudou, e nunca O QUE mudou.

    Sem dizer isso, "arquivo novo ou trocado" lido por um modelo vira a
    afirmação de que ele sabe qual arquivo é.

    **A asserção mudou em 22/09/2026, e a propriedade não.** Até aqui ela
    procurava os nomes `material` e `avisos` na resposta — o roteamento para as
    ferramentas que sabem. Esse roteamento saiu do texto porque a descrição
    desta ferramenta já o dá, com as mesmas palavras (sobreposição medida: 100%,
    `notas/custo-em-token.md`), e a descrição está no contexto do cliente a
    sessão inteira. O que a resposta precisa dizer, e diz, é o que a descrição
    NÃO diz: que o e-Disciplinas responde esta pergunta com um ponteiro, não com
    o conteúdo. Procurar nome de ferramenta aqui media o mecanismo; procurar a
    palavra "ponteiro" mede a propriedade.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert "ponteiro" in r.texto, "não disse que o que chega é ponteiro"
    assert "nunca O QUE mudou" in r.texto, "não separou QUE mudou de O QUE mudou"


def test_m18_nenhuma_url_sai_na_resposta(disciplinas_brutas, conteudo_ptc3314):
    """M18 — a tradução lê `core_course_get_contents`, que é a resposta mais
    cheia de `fileurl` do projeto. Nada dela pode vazar para cá (Invariante 3)."""
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    assert "pluginfile.php" not in r.texto
    assert "http" not in r.texto


def test_m16_a_projecao_descarta_a_maior_parte_do_payload(
    disciplinas_brutas, conteudo_ptc3314
):
    """M16 — a razão, e o que ela mede.

    O `updates_since` é ponteiro e já vem pequeno; quem domina a conta é o
    `get_contents`, que é real (12/09) e do qual sobram DOIS campos por módulo.
    Por isso a asserção é sobre a soma das duas entradas: medir só o ponteiro
    esconderia o custo que a tradução acrescentou, que é a decisão de desenho
    deste módulo.
    """
    c = _cliente(disciplinas_brutas, conteudo_ptc3314)

    r = om.o_que_mudou(c, "PTC3314", agora=AGORA)

    cru = len(
        json.dumps(mudancas_falsas(), ensure_ascii=False).encode("utf-8")
    ) + len(json.dumps(conteudo_ptc3314, ensure_ascii=False).encode("utf-8"))
    projetado = len(r.texto.encode("utf-8"))

    assert cru / projetado > 50, (
        f"razão de {cru / projetado:.1f}x — a projeção parou de descartar"
    )
