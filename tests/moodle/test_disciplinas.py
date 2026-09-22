"""DI1-DI14 — "quais matérias eu tenho?".

Até 14/09/2026 este servidor não respondia essa pergunta, e o único jeito de
alguém ver as próprias siglas era **provocar um erro**: pedir `material` de uma
sigla que não existe, para o Invariante 7 de `resolver` cuspir a lista inteira.

A ferramenta é a mais barata do projeto porque `disciplinas.carregar` já busca e
já cacheia essa lista para traduzir sigla em `courseid` — **nenhuma função nova
entra na allowlist**, e DI1 é a asserção que trava isso.

**A decisão que este arquivo pede para julgar é o que fazer com as matrículas
antigas.** A fixture real tem 74, e só 10 são do semestre em andamento; ao vivo,
em 14/09, o dono mediu 45 matrículas com 7 notas lançadas. Os dois números
discordam e nenhum dos dois muda o desenho: em qualquer um deles a maioria é de
semestre passado, e despejar a lista inteira com nome e período responde mal a
"quais matérias eu tenho?". O corte é de DETALHE e nunca de EXISTÊNCIA — DI4 é
quem garante que nenhuma sigla some, e DI5 que o corte é declarado com a cura.

Procedência do insumo: `users_courses.json` é **fixture REAL**, capturada e
higienizada (§3.3). Por causa da higienização, `fullname` vem embaralhado — daí
nenhum teste daqui afirmar o nome de uma disciplina; o que se afirma é a sigla,
o rótulo e o período, que a higienização preserva.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from tests.moodle.conftest import FIXTURE_DISCIPLINAS, ClienteFalso
from usp_mcp.moodle import disciplinas as dis
from usp_mcp.moodle.erros import ErroMoodle, MoodleIndisponivel
from usp_mcp.moodle.projecao import FUSO_SAO_PAULO

pytestmark = pytest.mark.contrato

USERID = 8214
# No meio do segundo semestre de 2026: as 10 matrículas com `enddate` em
# dezembro estão em andamento, e as 62 com `enddate` no passado, encerradas.
AGORA = datetime(2026, 9, 14, 16, 0, tzinfo=FUSO_SAO_PAULO)

# Os dois casos que a fixture real tem e que nenhum payload escrito à mão teria
# pensado em ter: matrícula com `enddate: 0`. Uma delas nem segue o formato
# "SIGLA-ano" do `shortname` (é uma atividade de extensão).
SEM_PERIODO = ("AEX-IF-00020.01", "MAT3457-2024")


@pytest.fixture(autouse=True)
def _cache_limpo():
    dis.limpar_cache()
    yield
    dis.limpar_cache()


def _cliente(disciplinas_brutas):
    return ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": USERID},
            "core_enrol_get_users_courses": disciplinas_brutas,
        }
    )


def _funcoes(cliente):
    return [f for f, _ in cliente.chamadas]


# --------------------------------------------------------------------------
# O que a ferramenta custa
# --------------------------------------------------------------------------


def test_di1_nenhuma_funcao_nova_e_chamada(disciplinas_brutas):
    """DI1 — a ferramenta inteira sai das duas chamadas que a resolução de sigla
    já fazia.

    Asserção sobre as funções ENVIADAS, e não sobre a saída: o dublê responderia
    igual a qualquer terceira função, e é justamente uma terceira função que esta
    ferramenta não pode ter. Se alguém acrescentar uma, o vermelho aparece aqui
    antes de aparecer na allowlist.
    """
    c = _cliente(disciplinas_brutas)

    dis.minhas_disciplinas(c, momento=AGORA)

    assert _funcoes(c) == [
        "core_webservice_get_site_info",
        "core_enrol_get_users_courses",
    ]


def test_di2_a_segunda_pergunta_nao_gasta_chamada_nenhuma(disciplinas_brutas):
    """DI2 — o cache de `carregar` (TTL de um semestre) vale para esta também.

    Matrícula não muda entre duas perguntas, e o Invariante 5 pede TTL colado na
    taxa de mudança do dado. Sem isto, perguntar duas vezes "quais matérias eu
    tenho" rebaixaria 98 kB de novo.
    """
    c = _cliente(disciplinas_brutas)

    dis.minhas_disciplinas(c, momento=AGORA)
    dis.minhas_disciplinas(c, momento=AGORA)

    assert len(c.chamadas) == 2, [f for f, _ in c.chamadas]


# --------------------------------------------------------------------------
# A decisão: o que acontece com as matrículas antigas
# --------------------------------------------------------------------------


def test_di3_as_do_semestre_em_andamento_vem_primeiro_e_completas(disciplinas_brutas):
    """DI3 — quem pergunta "quais matérias eu tenho" está perguntando do agora.

    As 10 do semestre corrente saem com sigla, rótulo e período; é a seção que
    responde a pergunta, e ela vem antes de qualquer coisa sobre semestre
    passado.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert r.em_andamento == 10, r.texto
    assert r.total == 74
    cabeca = r.texto.split("Encerradas")[0]
    for sigla in ("PTC3314", "PSI3323", "PSI3472", "PME3344", "PTC3360"):
        assert sigla in cabeca, f"{sigla} não está na seção do semestre corrente"


def test_di4_nenhuma_matricula_some_sem_ser_declarada(disciplinas_brutas):
    """DI4 — Invariante 7 no ponto exato em que esta ferramenta poderia falhar.

    **A asserção mudou em 22/09/2026, e a invariante não.** Até aqui, esta
    exigia que as 74 matrículas saíssem NOMEADAS na resposta padrão, as antigas
    em bloco compacto de rótulos. Aquele bloco media 565 dos 1.350 tokens da
    resposta — 42% — e respondia a uma pergunta que ninguém tinha feito
    (`notas/custo-em-token.md`). As encerradas viraram contagem por ano.

    O medo que esta asserção protegia continua respondido, e é por isso que ela
    mudou de forma em vez de sair: "uma sigla que suma daqui é uma disciplina
    que quem pergunta não tem como descobrir que existe". Com a contagem e o
    `todas` declarados na própria resposta, ela é descobrível — custa uma ida a
    mais, e só para quem faz a pergunta. O que este teste exige agora é o que
    sempre importou: que **nada saia da contagem** e que o caminho para os nomes
    esteja na resposta.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert r.total == len(disciplinas_brutas), "a contagem total não fecha"
    assert r.em_andamento + r.encerradas + r.sem_periodo == r.total, (
        "matrícula que não caiu em nenhum dos três blocos: some da contagem e "
        "some da resposta"
    )
    assert str(r.total) in r.texto, "o total não é dito a quem lê"

    # Nomeadas, as em andamento e as sem período — que são as que uma pergunta
    # sobre o semestre alcança sem parâmetro nenhum.
    nomeadas = [
        curso["shortname"]
        for curso in disciplinas_brutas
        if curso["shortname"] in r.texto
    ]
    assert len(nomeadas) == r.em_andamento + r.sem_periodo

    # E com `todas`, as 74 voltam a sair nomeadas: o corte é do padrão, não da
    # ferramenta. Sem esta metade, "cortar" e "perder" seriam a mesma coisa.
    dis.limpar_cache()
    r_todas = dis.minhas_disciplinas(_cliente(disciplinas_brutas), todas=True, momento=AGORA)
    faltando = [
        curso["shortname"]
        for curso in disciplinas_brutas
        if curso["shortname"] not in r_todas.texto
    ]
    assert not faltando, f"rótulos que `todas` também não mostra: {faltando}"


def test_di5_o_corte_de_detalhe_e_declarado_com_a_cura(disciplinas_brutas):
    """DI5 — Invariante 7 outra vez: cortou, declara, e diz como ver o resto.

    O que some das encerradas é o nome e o período, não a existência — e a
    resposta precisa dizer as duas coisas, senão quem lê conclui que o
    e-Disciplinas não sabe mais nada sobre aquelas matrículas.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert r.encerradas == 62
    assert "62" in r.texto
    assert "todas" in r.texto, "não nomeou o parâmetro que mostra o resto"


def test_di6_todas_abre_as_encerradas_e_o_padrao_nao(disciplinas_brutas):
    """DI6 — o parâmetro que a DI5 promete existe e faz o que promete.

    O nome sai da própria fixture em vez de escrito à mão: a fixture é
    higienizada e o `fullname` vem embaralhado (§3.3), então afirmar um nome
    literal aqui seria afirmar o embaralhamento.
    """
    antiga = [
        curso
        for curso in disciplinas_brutas
        if curso["shortname"] == "PMT3100-104-2023"
    ][0]

    c = _cliente(disciplinas_brutas)
    resumida = dis.minhas_disciplinas(c, momento=AGORA)
    completa = dis.minhas_disciplinas(c, todas=True, momento=AGORA)

    assert antiga["fullname"] not in resumida.texto
    assert antiga["fullname"] in completa.texto
    assert len(completa.texto) > len(resumida.texto)


def test_di7_matricula_sem_periodo_nao_vira_encerrada(disciplinas_brutas):
    """DI7 — `enddate: 0` é "o e-Disciplinas não declarou", nunca "acabou".

    As duas da fixture real são o caso que nenhum payload escrito à mão teria
    pensado em ter. Chamá-las de encerradas seria inventar um fato sobre a vida
    acadêmica de quem pergunta; escondê-las seria o falso vazio do Invariante 7.
    Elas saem em bloco próprio, com o motivo.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert r.sem_periodo == 2
    bloco = r.texto.split("sem período")[1]
    for rotulo in SEM_PERIODO:
        assert rotulo in bloco, f"{rotulo} não está no bloco de sem período"


def test_di8_a_saida_diz_de_onde_sai_o_em_andamento(disciplinas_brutas):
    """DI8 — Invariante 6: a resposta diz o que ela NÃO sabe.

    "Em andamento" aqui é a data que o e-Disciplinas declara para o espaço da
    disciplina, e não a matrícula oficial no JupiterWeb. Trancamento,
    cancelamento e disciplina que o professor nunca datou produzem divergência,
    e quem lê precisa saber disso antes de tratar a lista como matrícula.

    **Onde isso é dito mudou em 22/09/2026, e por isso o teste mudou de alvo.**
    A frase não é ressalva sobre ESTA resposta: é contrato sobre o que a
    ferramenta significa, idêntico em toda chamada. Passou para a descrição, que
    o cliente carrega uma vez por sessão, e saiu da resposta, que é a mais
    chamada do servidor. O teste exige as duas metades — que ela esteja na
    descrição, e que não tenha ficado **também** na resposta, porque o ganho
    inteiro desta mudança é não dizer a mesma coisa duas vezes.
    """
    from usp_mcp.moodle.server import listar_ferramentas

    descricao = next(
        f["description"] for f in listar_ferramentas() if f["name"] == "disciplinas"
    )
    assert "matrícula oficial" in descricao.lower()
    assert "jupiter" in descricao.lower()

    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert "matrícula oficial" not in r.texto.lower(), (
        "o contrato voltou a sair na resposta, e agora sai nos dois lugares"
    )


def test_di9_o_periodo_traz_o_ano(disciplinas_brutas):
    """DI9 — e por que aqui a grafia NÃO é a de `texto.formatar_data`.

    J18 pede uma grafia só para a mesma coisa, e esta não é a mesma coisa:
    `formatar_data` escreve prazo ("dom 06/09 23:59"), curto de propósito porque
    o prazo é de agora. Um período de vigência de 2023 sem o ano seria uma data
    que não localiza nada — a única coisa que distingue PMT3100 de PMT3130 numa
    lista de sete anos de matrícula é o ano.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, todas=True, momento=AGORA)

    assert "2023" in r.texto
    assert "/2026" in r.texto


# --------------------------------------------------------------------------
# Os modos de falha
# --------------------------------------------------------------------------


def test_di10_erro_do_cliente_sobe_e_nao_vira_lista_vazia(disciplinas_brutas):
    """DI10 — o bug do §9 de 28/08 aplicado a esta ferramenta.

    Token recusado e "você não tem matrícula nenhuma" são indistinguíveis para
    quem lê, e têm curas opostas. O erro sobe.
    """
    def _explode(_params):
        raise MoodleIndisponivel("o e-Disciplinas não respondeu")

    c = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": USERID},
            "core_enrol_get_users_courses": _explode,
        }
    )

    with pytest.raises(ErroMoodle):
        dis.minhas_disciplinas(c, momento=AGORA)


def test_di11_conta_sem_matricula_nenhuma_diz_por_que_esta_vazia():
    """DI11 — zero matrícula é resposta legítima, e rotulada.

    É o mesmo `vazio_por` de `o_que_vence`: lista vazia muda aqui seria
    exatamente o desfecho do userid errado de 28/08, que devolve `[]` com HTTP
    200.
    """
    c = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": USERID},
            "core_enrol_get_users_courses": [],
        }
    )

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert r.total == 0
    assert r.vazio_por == "sem_matriculas"
    assert len(r.texto) > 40, "vazio saiu mudo"


# --------------------------------------------------------------------------
# A projeção
# --------------------------------------------------------------------------


def test_di12_a_projecao_descarta_a_maior_parte_do_payload(disciplinas_brutas):
    """DI12 — 98 kB de cru viram alguns kB de texto, e o que sai é medido aqui.

    O cru é **fixture real** (98.171 B), então esta razão mede a resposta que o
    e-Disciplinas devolve de verdade — ao contrário das razões de `avisos` e
    `o_que_mudou`, que medem payload escrito à mão.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, momento=AGORA)

    cru = FIXTURE_DISCIPLINAS.stat().st_size
    assert len(r.texto.encode("utf-8")) < cru / 20, (
        f"{len(r.texto.encode('utf-8'))} B de texto para {cru} B de cru"
    )


def test_di13_o_que_a_projecao_descarta_nao_reaparece_no_texto(disciplinas_brutas):
    """DI13 — `summary`, `courseimage` e `progress` são quase todo o payload e
    não respondem nada da pergunta.

    A URL da imagem do curso é `pluginfile.php`, a mesma família de endereço que
    o Invariante 3 mantém fora de toda resposta deste servidor.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, todas=True, momento=AGORA)

    assert "pluginfile" not in r.texto
    assert "courseimage" not in r.texto
    # Um pedaço do `summary` da primeira matrícula: se ele aparecer, a projeção
    # deixou passar o campo mais gordo da resposta.
    assert disciplinas_brutas[0]["summary"][:40] not in r.texto


def test_di14_o_courseid_nao_vaza_para_quem_le(disciplinas_brutas):
    """DI14 — o número interno do Moodle não é vocabulário de quem pergunta.

    Quem lê responde à próxima pergunta com a SIGLA (é o que `material`,
    `notas`, `avisos` e as outras aceitam); o `courseid` só existiria na saída
    para ser copiado para um lugar que não o aceita.
    """
    c = _cliente(disciplinas_brutas)

    r = dis.minhas_disciplinas(c, todas=True, momento=AGORA)

    assert str(disciplinas_brutas[0]["id"]) not in r.texto


def test_di15_matricula_que_ainda_nao_comecou_nao_e_chamada_de_em_andamento():
    """DI15 — o quarto desfecho, e o único que a fixture real não tem.

    Matrícula para o semestre que vem existe antes de o semestre começar. Ela
    não está em andamento (a aula não começou), não está encerrada e tem período
    declarado — os três blocos anteriores estariam mentindo, cada um do seu
    jeito.

    O payload deste caso é **escrito à mão** e é minúsculo de propósito: só os
    quatro campos que a projeção lê. Os outros 25 já são exercitados contra a
    fixture real nos testes acima.
    """
    bruto = [
        {
            "id": 999001,
            "shortname": "PTC3450-2027",
            "fullname": "Disciplina do semestre que vem",
            "startdate": int(datetime(2027, 3, 1, tzinfo=FUSO_SAO_PAULO).timestamp()),
            "enddate": int(datetime(2027, 7, 1, tzinfo=FUSO_SAO_PAULO).timestamp()),
        }
    ]
    c = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": USERID},
            "core_enrol_get_users_courses": bruto,
        }
    )

    r = dis.minhas_disciplinas(c, momento=AGORA)

    assert r.em_andamento == 0
    assert r.encerradas == 0
    assert "PTC3450" in r.texto


# --------------------------------------------------------------------------
# DI16-DI23 — a sigla e o rótulo na resolução
#
# Medido em 15/09/2026 sobre as duas capturas reais desta conta
# (`users_courses.json`, de 31/08, com 74 matrículas; `users_courses_15-09.json`,
# com 47) e confirmado ao vivo contra o e-Disciplinas no mesmo dia.
#
# Dois defeitos, e nenhum dos dois é hipotético:
#
# 1. A sigla saía de `rotulo.split("-")[0]`, e o hífen não é o único separador
#    que esta conta usa. Em 74 matrículas aparecem `-` (69), `_` (2), espaço (1),
#    `.` (1) e nenhum (1). As três que sobram do hífen são do DONO e de HOJE:
#    `PEA3301_2026_1sem` e `PEA3306_2026_1sem` (semestre corrente) e
#    `PSI3211 2025`.
#
#    O estrago medido ao vivo: a conta tem `PEA3301_2026_1sem` (o semestre
#    corrente) e `PEA3301-2021` (cinco anos atrás). A regra do hífen dava
#    `PEA330120261SEM` para a de 2026 e `PEA3301` para a de 2021 — então
#    perguntar por "PEA3301" tinha UMA candidata só, e `material` respondia com
#    177 itens sobre a de 2021, sem ambiguidade nenhuma para detectar. Não é
#    "não acha": é acha a errada com confiança.
#
# 2. `resolver` nunca olhava o `rotulo`. Consequência medida: das 74 matrículas,
#    digitar o RÓTULO INTEIRO — que é exatamente o que a própria ferramenta
#    `disciplinas` imprime na tela — não achava nada em 69 delas (44 de 47 na
#    captura de 15/09).
# --------------------------------------------------------------------------

# Um por formato de `shortname` medido nas duas capturas, mais o caso de outra
# instituição que a nota de portabilidade descreve. O primeiro da lista é o que
# não pode quebrar: é a convenção que os alunos da USP usam hoje.
FORMATOS_REAIS = [
    ("PTC3314-2026", "PTC3314"),
    ("PRO3811-202-2026", "PRO3811"),
    ("PSI3322-2026-REOF", "PSI3322"),
    ("PEA3301_2026_1sem", "PEA3301"),
    ("PEA3306_2026_1sem", "PEA3306"),
    ("PSI3211 2025", "PSI3211"),
    ("2166.2023i", "2166"),
    ("PRO3200-2025.2", "PRO3200"),
    ("PCS3110-2024_2", "PCS3110"),
    ("PMT3100-2024-Primeiro Semestre", "PMT3100"),
    # Como está na fixture de 31/08: o nome depois do "Prof." é sintético
    # (§3.3, rede de honorífico do higienizador). O formato é o que importa.
    ("PME3100-203-2023 - Prof. Su Me La", "PME3100"),
    ("PSI3322-2'2026", "PSI3322"),
    ("PCS3335", "PCS3335"),
    ("0303200-2025", "0303200"),
    ("AEX-IF-00020.01", "AEX"),
    # Fora da USP o primeiro pedaço não é a sigla, e nenhuma regra de corte
    # conserta isso — quem conserta é a busca pelo rótulo (DI19).
    ("2026S2-BIO-101", "2026S2"),
]


def _bruto(shortname, courseid=1, nome="Disciplina", inicio=None, fim=None):
    """Só os cinco campos que `projetar_disciplinas` lê, todos presentes na
    captura real — a conferência de forma de `test_forma_real` reprova
    construtor de teste que invente campo."""
    return {
        "id": courseid,
        "shortname": shortname,
        "fullname": nome,
        "startdate": inicio,
        "enddate": fim,
    }


@pytest.mark.parametrize("rotulo,esperada", FORMATOS_REAIS, ids=[r for r, _ in FORMATOS_REAIS])
def test_di16_a_sigla_sai_do_primeiro_pedaco_seja_qual_for_o_separador(rotulo, esperada):
    """DI16 — o separador do `shortname` não é só o hífen.

    A lista inteira é formato MEDIDO nas duas capturas desta conta, e não
    formato imaginado. `PTC3314-2026 -> PTC3314` está em primeiro lugar de
    propósito: é a convenção que os alunos da USP usam hoje, e é ela que uma
    regra mais geral não pode quebrar para atender aos outros quinze.
    """
    (d,) = dis.projetar_disciplinas([_bruto(rotulo)])

    assert d.sigla == esperada, (
        f"o rótulo {rotulo!r} deu a sigla {d.sigla!r}. A sigla é o PRIMEIRO "
        f"pedaço alfanumérico do rótulo, que aqui é {esperada!r} — corte no "
        "primeiro separador, qualquer que ele seja, e não só no hífen."
    )


def test_di17_a_matricula_do_semestre_corrente_nao_fica_inalcancavel(disciplinas_brutas):
    """DI17 — o defeito medido ao vivo, escrito como teste.

    Esta conta tem `PEA3301_2026_1sem` (cursando) e `PEA3301-2021`. Enquanto a
    sigla saía do corte no hífen, a de 2026 ficava com a sigla
    `PEA330120261SEM` e "PEA3301" tinha uma candidata só — a de 2021. A resposta
    saía confiante e sobre a disciplina errada.

    O que este teste exige é que as duas passem a ter a MESMA sigla. Que a
    resposta a "PEA3301" vire uma pergunta em vez de uma escolha é o assunto do
    DI18; aqui o que se trava é que a de 2026 deixou de ser inalcançável pela
    sigla dela.
    """
    lista = dis.projetar_disciplinas(disciplinas_brutas)
    por_rotulo = {d.rotulo: d for d in lista}

    corrente = por_rotulo["PEA3301_2026_1sem"]
    antiga = por_rotulo["PEA3301-2021"]

    assert corrente.sigla == "PEA3301", (
        f"a matrícula do semestre corrente ficou com a sigla {corrente.sigla!r}: "
        "nenhuma pergunta escrita por quem cursa a disciplina chega até ela. "
        "Corte o rótulo no primeiro separador, e não no primeiro hífen."
    )
    assert corrente.sigla == antiga.sigla, (
        "as duas matrículas de PEA3301 têm de cair na mesma sigla — é ter "
        "siglas diferentes que faz a busca achar só a de 2021 e responder por "
        "ela sem avisar que a outra existe."
    )
    assert dis.resolver(lista, "PEA3301_2026_1sem").disciplina is corrente, (
        "o rótulo inteiro da matrícula do semestre corrente tem de resolver "
        "para ela: é o que a resposta ambígua vai mandar repetir."
    )


def test_di18_duas_matriculas_da_mesma_sigla_viram_pergunta_e_nao_escolha(
    disciplinas_brutas,
):
    """DI18 — e a escolha calada NÃO volta por outra porta.

    Depois do DI17 "PEA3301" casa com duas. A saída certa é a que este projeto
    já usa para ambiguidade: listar as candidatas e devolver a pergunta. Um
    desempate por data — "ela quis dizer a de 2026" — foi recusado de propósito:
    seria trocar uma escolha calada por outra, e as datas daqui são as do espaço
    da disciplina, não as da matrícula oficial (DI8).
    """
    lista = dis.projetar_disciplinas(disciplinas_brutas)

    r = dis.resolver(lista, "PEA3301")

    assert r.disciplina is None, (
        f"escolheu {r.disciplina.rotulo!r} entre duas matrículas de PEA3301 sem "
        "perguntar. Devolva as candidatas no motivo e deixe quem pergunta "
        "escolher — desempatar por data aqui é escolher calado do mesmo jeito."
    )
    assert {d.rotulo for d in r.candidatas} == {"PEA3301_2026_1sem", "PEA3301-2021"}
    for rotulo in ("PEA3301_2026_1sem", "PEA3301-2021"):
        assert rotulo in r.motivo, (
            f"{rotulo!r} não está no motivo: quem lê 'ambíguo' sem a lista não "
            "tem como formular a próxima pergunta."
        )
    assert r.candidatas[0].rotulo == "PEA3301_2026_1sem", (
        "a candidata mais recente tem de vir primeiro na lista. Ordenar é "
        "informação; o que não pode é ordenar e depois escolher sozinho."
    )


def test_di19_o_rotulo_entra_na_busca(disciplinas_brutas):
    """DI19 — o caso que a nota de portabilidade descreve, e o caso de casa.

    Num site cujo `shortname` seja `2026S2-BIO-101`, nenhuma regra de corte
    produz a sigla "BIO101" — quem acha é a busca pelo rótulo. E o caso de casa,
    medido: digitar o rótulo inteiro, que é o que a ferramenta `disciplinas`
    imprime na tela, não achava nada em 69 das 74 matrículas desta conta.
    """
    fora_da_usp = dis.projetar_disciplinas(
        [_bruto("2026S2-BIO-101", courseid=77, nome="Introducao a Biologia")]
    )
    r = dis.resolver(fora_da_usp, "BIO101")
    assert r.disciplina is not None, (
        "'BIO101' não achou o curso cujo shortname é '2026S2-BIO-101', com a "
        f"string literalmente lá. Motivo devolvido: {r.motivo!r}. Procure "
        "também dentro do `rotulo`, não só na sigla e no nome."
    )
    assert r.disciplina.courseid == 77

    lista = dis.projetar_disciplinas(disciplinas_brutas)
    perdidos = [
        curso["shortname"]
        for curso in disciplinas_brutas
        if dis.resolver(lista, curso["shortname"]).disciplina is None
    ]
    assert not perdidos, (
        f"{len(perdidos)} de {len(disciplinas_brutas)} rótulos não resolvem "
        f"quando digitados inteiros: {perdidos[:5]}. O rótulo é o que a "
        "ferramenta `disciplinas` mostra na tela — copiá-lo de volta tem de "
        "funcionar."
    )


def test_di20_sigla_exata_continua_ganhando_de_casamento_parcial():
    """DI20 — a não-regressão da ordem, agora que o rótulo entrou na busca.

    A ordem exata-antes-de-parcial existe porque com parcial primeiro "PTC3312"
    casaria consigo mesma e com qualquer PTC3312-XXX, virando ambiguidade onde
    havia resposta. Pôr o rótulo no casamento parcial é exatamente o jeito de
    ressuscitar isso, e é por isso que este teste está aqui.
    """
    lista = [
        dis.Disciplina(courseid=1, sigla="PTC3312", rotulo="PTC3312", nome="Redes"),
        dis.Disciplina(courseid=2, sigla="PTC3312", rotulo="PTC3312-202-2026",
                       nome="Redes turma 202"),
        dis.Disciplina(courseid=3, sigla="PTC3313", rotulo="PTC3313-2026", nome="Ondas"),
    ]

    r = dis.resolver(lista, "PTC3312")
    assert r.disciplina is None, (
        "duas matrículas com a sigla PTC3312 são ambiguidade de verdade, e a "
        "resposta certa é listar as duas."
    )
    assert {d.courseid for d in r.candidatas} == {1, 2}, (
        "a ambiguidade de sigla exata não pode arrastar a PTC3313 junto: quando "
        "existe casamento exato, é ele que forma a lista de candidatas."
    )

    # E o caso que a ordem protege: sigla exata resolve mesmo com o rótulo de
    # outra matrícula contendo o termo.
    duas = [
        dis.Disciplina(courseid=1, sigla="PTC3312", rotulo="PTC3312", nome="Redes"),
        dis.Disciplina(courseid=3, sigla="PTC3313", rotulo="PTC3313-2026", nome="Ondas"),
    ]
    assert dis.resolver(duas, "PTC3312").disciplina.courseid == 1, (
        "a sigla exata tem de resolver antes de qualquer casamento parcial"
    )


def test_di21_rotulo_exato_ganha_de_rotulo_que_apenas_o_contem():
    """DI21 — o outro lado da mesma ordem, do lado do rótulo.

    As duas formas existem nesta conta (`PCS3110-2S` e `PCS3111-2S-2025`): um
    rótulo que é começo de outro. Se o rótulo entrasse só como pedaço, digitar
    um rótulo INTEIRO e correto viraria ambiguidade — resposta virando pergunta,
    que é o pior desfecho dos três.
    """
    lista = [
        dis.Disciplina(courseid=1, sigla="PCS3110", rotulo="PCS3110-2S", nome="Redes"),
        dis.Disciplina(courseid=2, sigla="PCS3110", rotulo="PCS3110-2S-2025",
                       nome="Redes de novo"),
    ]

    r = dis.resolver(lista, "PCS3110-2S")

    assert r.disciplina is not None, (
        f"'PCS3110-2S' é o rótulo inteiro de uma das duas e virou ambiguidade: "
        f"{r.motivo!r}. Rótulo exato é casamento EXATO, e resolve antes de "
        "qualquer casamento por pedaço."
    )
    assert r.disciplina.courseid == 1


def test_di22_a_ambiguidade_continua_listando_as_candidatas_e_dizendo_o_que_fazer():
    """DI22 — o tratamento explícito de ambiguidade não pode ter virado outra coisa.

    Duas exigências, e a segunda mudou com o conserto: o motivo lista as
    candidatas, e manda repetir com o que de fato desempata. Antes era "a sigla
    completa"; depois do DI17 a sigla é justamente o que ficou ambíguo, e quem
    desempata é o rótulo — conselho que só passou a ser acionável porque o DI19
    fez o rótulo funcionar na busca.
    """
    lista = [
        dis.Disciplina(courseid=1, sigla="PMT3100", rotulo="PMT3100-2023", nome="Materiais"),
        dis.Disciplina(courseid=2, sigla="PMT3100", rotulo="PMT3100-2024", nome="Materiais"),
    ]

    r = dis.resolver(lista, "PMT3100")

    assert r.disciplina is None and len(r.candidatas) == 2
    assert "PMT3100-2023" in r.motivo and "PMT3100-2024" in r.motivo
    assert "rótulo" in r.motivo.lower(), (
        "o motivo tem de dizer que é o RÓTULO que desempata. Mandar repetir com "
        "'a sigla completa' é mandar repetir o que acabou de falhar."
    )


def test_di23_termo_que_nao_existe_continua_nao_casando(disciplinas_brutas):
    """DI23 — a busca ficou mais larga; não pode ter ficado larga demais.

    Casar de mais é pior do que casar de menos, porque transforma resposta em
    pergunta. O piso: um termo que não está em rótulo nenhum nem em nome nenhum
    continua caindo no "não achei" que lista o que existe.
    """
    lista = dis.projetar_disciplinas(disciplinas_brutas)

    r = dis.resolver(lista, "XYZ9999")

    assert r.disciplina is None and r.candidatas == (), (
        f"'XYZ9999' passou a casar com {[d.rotulo for d in r.candidatas]}"
    )
    assert "XYZ9999" in r.motivo and "PSI3323" in r.motivo


# --------------------------------------------------------------------------
# DI24-DI26: as encerradas param de ocupar 42% da resposta (22/09/2026)
#
# Medido em `notas/custo-em-token.md`: das 74 matrículas, 62 estão encerradas e
# saíam em toda chamada como lista de rótulos — 565 dos 1.350 tokens. As 10 em
# andamento, que são a resposta à pergunta, custavam 476.
# --------------------------------------------------------------------------


def test_di24_as_encerradas_saem_como_contagem_por_ano(disciplinas_brutas):
    """O ano fica, porque é o que orienta a segunda pergunta; os ~50 rótulos
    saem, porque ninguém perguntou por eles."""
    r = dis.minhas_disciplinas(_cliente(disciplinas_brutas))

    assert "2024: 14" in r.texto, "a contagem do ano não saiu"
    assert "MAC2166-2024" not in r.texto, "o rótulo de matrícula encerrada ficou"
    assert "PME3344" in r.texto, "a disciplina EM ANDAMENTO tem de continuar inteira"


def test_di25_a_resposta_diz_como_ver_as_encerradas(disciplinas_brutas):
    """Invariante 7: o corte é declarado, com a contagem e com a cura. Sem a
    segunda metade, "62 encerradas" vira um beco."""
    r = dis.minhas_disciplinas(_cliente(disciplinas_brutas))

    assert "62" in r.texto
    assert "todas" in r.texto


def test_di26_com_todas_os_rotulos_voltam(disciplinas_brutas):
    """O corte é do padrão, não da ferramenta: quem pede a lista recebe a lista,
    e é isso que faz o corte ser corte e não perda."""
    r = dis.minhas_disciplinas(_cliente(disciplinas_brutas), todas=True)

    assert "MAC2166-2024" in r.texto
