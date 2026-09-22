"""T58-T77: `material` — os arquivos do espaço da disciplina.

A pergunta do dono, nas palavras dele: *descobrir os arquivos que aparecem no
espaço da disciplina*, porque muitos são regras da disciplina, listas de
exercícios e provas anteriores. **Não** é "onde está o PDF da aula de hoje", que
é como o §5 registrava a candidata — o valor está no acervo, não no arquivo do
dia. A diferença muda a ferramenta: sem `busca` ela lista tudo, e a busca é por
nome de arquivo, não por data.

**A amostra é uma só, por decisão do dono** (§9, 31/08). Todo número de proporção
aqui — a projeção, a mistura de tipos — vale para PSI3323. Os testes dizem isso
onde importa, para ninguém depois ler uma asserção como se fosse fato do sistema.

Três camadas de custo, e a do meio é a que torna a ferramenta possível:

| | cru | projetado |
|---|---|---|
| lista de disciplinas | 104.712 B | 1.026 B (só o semestre) |
| conteúdo de uma disciplina | 58.049 B | ~6.486 B |
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from tests.moodle.conftest import (
    ENTREGAS_PSI3323_SEM_ANEXO,
    FIXTURE_CONTEUDO,
    FIXTURE_DISCIPLINAS,
    ClienteFalso,
)
from usp_mcp.moodle import disciplinas as disc
from usp_mcp.moodle import erros, material as mat, politica
from usp_mcp.moodle.projecao import FUSO_SAO_PAULO

COURSEID_PSI3323 = 142033
COURSEID_PTC3314 = 142036


@pytest.fixture(autouse=True)
def _cache_limpo():
    """O cache de disciplinas é de processo, e teste não pode herdar o do vizinho.

    Sem isto, T65 leria o cache que T64 deixou — e passaria sem nunca ter
    chamado o Moodle, que é exatamente o falso-verde que esta suíte existe para
    não produzir. Vale para os testes da ferramenta pelo mesmo motivo.
    """
    disc.limpar_cache()
    yield
    disc.limpar_cache()


# ---------------------------------------------------------------- disciplinas

@pytest.mark.contrato
def test_projeta_a_lista_de_disciplinas_para_tres_campos(disciplinas_brutas):
    """T58 — 29 chaves por disciplina viram 3: só o que resolve sigla → courseid."""
    lista = disc.projetar_disciplinas(disciplinas_brutas)

    assert len(lista) == 74
    alvo = [d for d in lista if d.courseid == COURSEID_PSI3323]
    assert len(alvo) == 1, "PSI3323 sumiu da projeção"
    assert alvo[0].sigla == "PSI3323", (
        "a sigla sai do shortname sem o sufixo de ano: 'PSI3323-2026' → 'PSI3323'"
    )
    assert alvo[0].rotulo == "PSI3323-2026", "o shortname cru se perde na projeção"


@pytest.mark.contrato
def test_a_projecao_da_lista_corta_a_maior_parte_do_payload(disciplinas_brutas):
    """T59 — 26.178 tokens crus não podem atravessar até o modelo.

    O teto é generoso de propósito: trava a ordem de grandeza (medido 7,5% do
    cru), não o número exato, que mudaria com uma matrícula nova.
    """
    cru = len(FIXTURE_DISCIPLINAS.read_bytes())
    lista = disc.projetar_disciplinas(disciplinas_brutas)
    projetado = len(
        json.dumps([{"i": d.courseid, "s": d.sigla, "n": d.nome} for d in lista],
                   ensure_ascii=False).encode()
    )
    assert projetado < cru * 0.15, f"projeção em {100*projetado/cru:.1f}% do cru"


@pytest.mark.contrato
def test_resolve_a_sigla_para_o_courseid(disciplinas_brutas):
    """T60 — o modelo tem a sigla; o Moodle só entende courseid."""
    lista = disc.projetar_disciplinas(disciplinas_brutas)
    r = disc.resolver(lista, "PSI3323")

    assert r.disciplina is not None, r.motivo
    assert r.disciplina.courseid == COURSEID_PSI3323


@pytest.mark.contrato
def test_caixa_e_espaco_nao_atrapalham(disciplinas_brutas):
    """T61 — quem pergunta escreve 'psi 3323'. Mesma normalização do Jupiter."""
    lista = disc.projetar_disciplinas(disciplinas_brutas)
    for escrito in ("psi 3323", "PSI-3323", " psi3323 "):
        r = disc.resolver(lista, escrito)
        assert r.disciplina is not None, f"{escrito!r} não resolveu: {r.motivo}"
        assert r.disciplina.courseid == COURSEID_PSI3323


@pytest.mark.politica
def test_termo_ambiguo_nao_escolhe_sozinho():
    """T62 — Invariante 6: escolher uma entre várias é errar calado.

    Lista sintética, não a fixture: a higienização embaralha `fullname`, então
    casamento por nome não é exercitável contra ela. O que se testa aqui é a
    REGRA, e ela não depende do dado real.
    """
    lista = [
        disc.Disciplina(courseid=1, sigla="PTC3312", rotulo="PTC3312-2026", nome="Redes"),
        disc.Disciplina(courseid=2, sigla="PTC3313", rotulo="PTC3313-2026", nome="Ondas"),
    ]
    r = disc.resolver(lista, "PTC331")

    assert r.disciplina is None, "escolheu uma das duas sem perguntar"
    assert {d.courseid for d in r.candidatas} == {1, 2}
    assert "PTC3312" in r.motivo and "PTC3313" in r.motivo, (
        "o motivo tem de listar as candidatas — 'ambíguo' sozinho não ajuda quem lê"
    )


@pytest.mark.politica
def test_termo_sem_correspondencia_diz_o_que_existe(disciplinas_brutas):
    """T63 — Invariante 7: 'não achei' nunca sai como lista vazia muda.

    'Não estou matriculado' e 'errei a sigla' têm curas diferentes, e a saída
    tem de deixar o leitor distinguir as duas.
    """
    lista = disc.projetar_disciplinas(disciplinas_brutas)
    r = disc.resolver(lista, "XYZ9999")

    assert r.disciplina is None
    assert r.candidatas == ()
    assert "XYZ9999" in r.motivo, "o motivo não repete o que foi pedido"
    assert "PSI3323" in r.motivo, "o motivo não mostra nenhuma sigla que existe"


@pytest.mark.contrato
def test_a_lista_de_disciplinas_e_cacheada_por_semestre(disciplinas_brutas):
    """T64 — Invariante 5: TTL colado na taxa de mudança, não na da pergunta.

    Matrícula muda por semestre. Buscar 104 kB a cada pergunta sobre material é
    martelar a USP para reconfirmar algo que não mudou. O relógio é injetável
    para que o teste verifique a REGRA, não o valor da constante.
    """
    cliente = ClienteFalso({
        "core_webservice_get_site_info": {"userid": 999},
        "core_enrol_get_users_courses": disciplinas_brutas,
    })
    relogio = [1000.0]

    disc.carregar(cliente, agora=lambda: relogio[0])
    disc.carregar(cliente, agora=lambda: relogio[0] + 60)
    n_dentro = sum(1 for f, _ in cliente.chamadas if f == "core_enrol_get_users_courses")
    assert n_dentro == 1, "buscou de novo dentro do TTL"

    relogio[0] += disc.TTL_DISCIPLINAS + 1
    disc.carregar(cliente, agora=lambda: relogio[0])
    n_depois = sum(1 for f, _ in cliente.chamadas if f == "core_enrol_get_users_courses")
    assert n_depois == 2, "não buscou de novo depois do TTL expirar"


@pytest.mark.contrato
def test_o_userid_vem_do_token_nao_da_configuracao(disciplinas_brutas):
    """T65 — §9 de 28/08: `MOODLE_USERID` saiu da configuração porque userid
    errado devolve `[]` com HTTP 200 — a falha silenciosa do Invariante 6.
    O valor tem de ser derivado, e tem de ser o derivado que viaja."""
    cliente = ClienteFalso({
        "core_webservice_get_site_info": {"userid": 424242},
        "core_enrol_get_users_courses": disciplinas_brutas,
    })
    disc.carregar(cliente, agora=lambda: 0.0)

    # Asserção sobre o parâmetro ENVIADO, não sobre a saída.
    assert cliente.params_de("core_enrol_get_users_courses")["userid"] == 424242


# ------------------------------------------------------------------- material

@pytest.mark.contrato
def test_projeta_o_conteudo_preservando_secao_e_tipo(conteudo_bruto):
    """T66 — a forma medida de PSI3323: 16 seções, 29 itens, 19 deles PDF."""
    c = mat.projetar_material(conteudo_bruto)

    assert len(c.secoes) == 16
    assert c.total_itens == 29
    tipos = [i.tipo for s in c.secoes for i in s.itens]
    assert tipos.count("PDF") == 19, "os PDFs deixaram de ser reconhecidos por mimetype"
    assert tipos.count("link") == 7, "os módulos `url` deixaram de ser links externos"


@pytest.mark.contrato
def test_a_projecao_do_conteudo_cabe_no_contexto(conteudo_bruto):
    """T67 — 14.512 tokens crus por disciplina não atravessam; ~1.621 atravessam.

    O teto trava a ordem de grandeza medida em PSI3323 (11,2%). **Não é fato do
    sistema**: uma disciplina com resumo de seção longo pode ter razão pior, e
    isso só se sabe capturando outras (backlog, 31/08).
    """
    cru = len(FIXTURE_CONTEUDO.read_bytes())
    c = mat.projetar_material(conteudo_bruto)
    projetado = len(json.dumps(mat.como_dict(c), ensure_ascii=False).encode())

    assert projetado < cru * 0.25, f"projeção em {100*projetado/cru:.1f}% do cru"


@pytest.mark.politica
def test_nunca_emite_url_interna_do_moodle(conteudo_bruto):
    """T68 — Invariante 3, e é a asserção mais importante deste arquivo.

    Medido: os 22 `resource` apontam para `edisciplinas.usp.br/webservice/
    pluginfile.php`, e baixar de lá exige anexar o token na URL. Emitir essa URL
    põe a credencial a um passo do contexto do modelo e de qualquer log por onde
    a resposta passe. Link externo (YouTube, Google Docs) não tem esse problema
    e sai inteiro — T69.
    """
    c = mat.projetar_material(conteudo_bruto)
    urls = [i.url_externa for s in c.secoes for i in s.itens if i.url_externa]

    for u in urls:
        assert "pluginfile.php" not in u, f"URL interna emitida: host {u.split('/')[2]}"
        assert "webservice" not in u, f"URL de webservice emitida: host {u.split('/')[2]}"
    assert not any("token" in u.lower() for u in urls)


@pytest.mark.contrato
def test_link_externo_sai_inteiro(conteudo_bruto):
    """T69 — o outro lado do T68: recusar TUDO seria o Invariante 7 quebrado
    ao contrário — esconder o que se sabe. Os 7 `url` são externos e úteis."""
    c = mat.projetar_material(conteudo_bruto)
    externos = [i for s in c.secoes for i in s.itens if i.tipo == "link"]

    assert len(externos) == 7
    assert all(i.url_externa and i.url_externa.startswith("http") for i in externos)
    assert any("youtube.com" in i.url_externa for i in externos)


@pytest.mark.politica
def test_a_projecao_nao_carrega_quem_subiu_o_arquivo(conteudo_bruto):
    """T70 — `author` e `userid` vêm dentro de `contents` e são dado pessoal
    (§3.3). Eles não respondem "que arquivos tem aqui" e não têm por que
    atravessar a fronteira."""
    c = mat.projetar_material(conteudo_bruto)
    serializado = json.dumps(mat.como_dict(c), ensure_ascii=False)

    for campo in ("author", "userid", "usermodified"):
        assert f'"{campo}"' not in serializado


@pytest.mark.contrato
def test_declara_o_que_nao_tem_conteudo(conteudo_bruto):
    """T71 — Invariante 7. Fórum e entrega não têm `contents`, e sumir com eles
    faria a lista parecer o espaço inteiro da disciplina quando não é."""
    c = mat.projetar_material(conteudo_bruto)

    assert set(c.sem_conteudo) == {"forum", "assign"}


# ---------------------------------------------------------- a ferramenta toda

def _cliente_completo(disciplinas_brutas, conteudo_bruto):
    return ClienteFalso({
        "core_webservice_get_site_info": {"userid": 999},
        "core_enrol_get_users_courses": disciplinas_brutas,
        "core_course_get_contents": conteudo_bruto,
        "mod_assign_get_assignments": ENTREGAS_PSI3323_SEM_ANEXO,
    })


@pytest.mark.contrato
def test_uma_pergunta_uma_disciplina(disciplinas_brutas, conteudo_bruto):
    """T72 — o courseid resolvido é o que viaja, e o conteúdo é pedido de UMA.

    Sem asserção sobre o parâmetro enviado, trocar a resolução por um courseid
    fixo passaria: o dublê devolve a mesma fixture de qualquer jeito.
    """
    cliente = _cliente_completo(disciplinas_brutas, conteudo_bruto)
    r = mat.material(cliente, "PSI3323", agora=lambda: 0.0)

    assert cliente.params_de("core_course_get_contents")["courseid"] == COURSEID_PSI3323
    assert sum(1 for f, _ in cliente.chamadas if f == "core_course_get_contents") == 1
    assert "PSI3323" in r.texto

    # DUAS disciplinas, e não é preciosismo: com uma só, trocar a resolução por
    # `courseid=142033` fixo passa — medido, essa sabotagem sobreviveu à primeira
    # versão deste teste. Um valor fixo não pode acertar as duas.
    outro = _cliente_completo(disciplinas_brutas, conteudo_bruto)
    mat.material(outro, "PTC3314", agora=lambda: 0.0)
    assert outro.params_de("core_course_get_contents")["courseid"] == COURSEID_PTC3314


@pytest.mark.contrato
def test_a_busca_filtra_por_nome_de_arquivo(disciplinas_brutas, conteudo_bruto):
    """T73 — a pergunta real é 'onde está a regra', 'cadê a prova antiga'."""
    cliente = _cliente_completo(disciplinas_brutas, conteudo_bruto)
    r = mat.material(cliente, "PSI3323", busca="regras", agora=lambda: 0.0)

    assert "programacao_e_regras" in r.texto
    assert "Datasheet-UA741" not in r.texto, "a busca não filtrou nada"
    # Invariante 7: filtrar é esconder, e esconder tem de ser declarado.
    assert "29" in r.texto, "não disse quantos itens existem fora do filtro"


@pytest.mark.contrato
def test_busca_sem_resultado_diz_quantos_existem(disciplinas_brutas, conteudo_bruto):
    """T74 — Invariante 7. 'Nada com esse nome' e 'disciplina vazia' são coisas
    diferentes, e uma lista vazia não distingue as duas."""
    cliente = _cliente_completo(disciplinas_brutas, conteudo_bruto)
    r = mat.material(cliente, "PSI3323", busca="zzzznadaaqui", agora=lambda: 0.0)

    assert "zzzznadaaqui" in r.texto
    assert "29" in r.texto, "não disse que a disciplina tem 29 itens no total"


@pytest.mark.contrato
def test_disciplina_vazia_nao_se_confunde_com_disciplina_nao_achada(disciplinas_brutas):
    """T75 — 6 das 10 disciplinas do semestre não têm entrega nenhuma, então
    'espaço vazio' é resultado esperado e não pode sair como falha."""
    cliente = ClienteFalso({
        "core_webservice_get_site_info": {"userid": 999},
        "core_enrol_get_users_courses": disciplinas_brutas,
        "core_course_get_contents": [],
    })
    r = mat.material(cliente, "PSI3323", agora=lambda: 0.0)

    assert "PSI3323" in r.texto
    assert r.vazio_por == "sem_material"


@pytest.mark.politica
def test_sigla_desconhecida_nao_chega_a_pedir_conteudo(disciplinas_brutas, conteudo_bruto):
    """T76 — resolver antes de gastar: sigla errada não vira chamada à USP."""
    cliente = _cliente_completo(disciplinas_brutas, conteudo_bruto)

    with pytest.raises(erros.ErroMoodle) as exc:
        mat.material(cliente, "XYZ9999", agora=lambda: 0.0)

    assert "XYZ9999" in str(exc.value)
    assert not any(f == "core_course_get_contents" for f, _ in cliente.chamadas), (
        "pediu conteúdo de uma disciplina que não resolveu"
    )


@pytest.mark.politica
def test_a_allowlist_cresce_por_decisao_e_so_com_leitura():
    """T77 — a superfície passou de 1 para 4 (§9, 31/08), de 4 para 5 (12/09),
    de 5 para 6, de 6 para 8 e de 8 para 10 (14/09: `ja_entreguei`, `notas` e
    `avisos`), de 10 para 11 (14/09, `o_que_mudou`) e de 11 para 13 (17/09,
    `questionarios`).

    O teste continua travando o conjunto INTEIRO, que é o que impede a próxima
    sessão de acrescentar "só mais uma". Todas são leitura; nenhuma escreve, e
    nenhuma está no bloqueio permanente do §2.2 — o que importa dizer das
    vizinhas de nome de funções que estão: as duas de `mod_assign_` convivem
    com `submit_for_grading`, as duas de `mod_forum_` convivem com
    `add_discussion` e `delete_post`, e as duas de `mod_quiz_` convivem com as
    três de tentativa, as mais perigosas da lista — e com duas LEITURAS que
    entraram no bloqueio no mesmo dia que elas entraram aqui.
    """
    assert politica.ALLOWLIST == frozenset({
        "core_calendar_get_action_events_by_timesort",
        "core_webservice_get_site_info",
        "core_enrol_get_users_courses",
        "core_course_get_contents",
        "mod_assign_get_assignments",
        "mod_assign_get_submission_status",
        "gradereport_overview_get_course_grades",
        "gradereport_user_get_grade_items",
        "mod_forum_get_forums_by_courses",
        "mod_forum_get_forum_discussions",
        "core_course_get_updates_since",
        "mod_quiz_get_quizzes_by_courses",
        "mod_quiz_get_user_attempts",
    })
    assert not (politica.ALLOWLIST & politica.BLOQUEIO_PERMANENTE)
    for funcao in politica.ALLOWLIST:
        assert politica.decidir(funcao).permitida


@pytest.mark.politica
def test_t83_acento_nao_impede_o_casamento_por_nome():
    """Quem pergunta em português digita sem acento.

    A primeira versão descartava o caractere acentuado: "Eletrônica" virava
    "ELETRNICA" e "eletronica" virava "ELETRONICA" — nenhum casava com o outro.
    Achado ao vivo, com a pergunta do dono escrita sem acento; a suíte não pegava
    porque a higienização embaralha `fullname` e nenhum teste usava nome real.

    Lista sintética pelo mesmo motivo do T62: a regra não depende do dado real,
    e contra a fixture ela não é exercitável.
    """
    lista = [
        disc.Disciplina(courseid=1, sigla="PSI3323", rotulo="PSI3323-2026",
                        nome="Laboratório de Eletrônica I"),
        disc.Disciplina(courseid=2, sigla="MAT2455", rotulo="MAT2455-2026",
                        nome="Cálculo Diferencial e Integral III"),
    ]
    for escrito in ("eletronica", "eletrônica", "ELETRONICA", "Laboratorio de Eletronica"):
        r = disc.resolver(lista, escrito)
        assert r.disciplina is not None, f"{escrito!r} não resolveu: {r.motivo}"
        assert r.disciplina.courseid == 1

    # A sigla continua ganhando de qualquer casamento por nome.
    assert disc.resolver(lista, "MAT2455").disciplina.courseid == 2


# --- T68b, T68c, T102 -------------------------------------------------------

@pytest.mark.politica
def test_T68b_o_texto_entregue_ao_modelo_nunca_contem_url_interna(
    conteudo_bruto, disciplinas_brutas
):
    """T68 olha só `url_externa`; um campo novo no Item passaria por baixo dele.

    Esta asserção é sobre o que de fato chega ao modelo: o texto da resposta.
    """
    cliente = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": 1},
            "core_enrol_get_users_courses": disciplinas_brutas,
            "core_course_get_contents": conteudo_bruto,
            "mod_assign_get_assignments": ENTREGAS_PSI3323_SEM_ANEXO,
        }
    )
    disc.limpar_cache()
    resposta = mat.material(cliente, "PSI3323")

    assert "pluginfile.php" not in resposta.texto
    assert "/webservice/" not in resposta.texto
    assert "token" not in resposta.texto.lower()


@pytest.mark.politica
def test_T68c_como_dict_nao_carrega_a_url_interna(conteudo_bruto):
    """`como_dict` alimenta a medição de custo e é fácil de estender sem pensar."""
    import json as _json

    c = mat.projetar_material(conteudo_bruto)
    serializado = _json.dumps(mat.como_dict(c), ensure_ascii=False)

    assert "pluginfile.php" not in serializado
    assert "/webservice/" not in serializado


@pytest.mark.contrato
def test_T102_busca_por_nome_ignora_acento(conteudo_bruto, disciplinas_brutas):
    """Medido em 01/09: 'formulario' não achava 'Formulário Provas
    Substitutivas.pdf'. Mesmo bug do acento de T83, em outro lugar."""
    cliente = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": 1},
            "core_enrol_get_users_courses": disciplinas_brutas,
            "core_course_get_contents": conteudo_bruto,
            "mod_assign_get_assignments": ENTREGAS_PSI3323_SEM_ANEXO,
        }
    )
    disc.limpar_cache()
    resposta = mat.material(cliente, "PSI3323", busca="formulario")

    assert resposta.mostrados >= 1
    assert "Formulário" in resposta.texto


@pytest.mark.contrato
def test_T102b_o_item_carrega_secao_modulo_e_fileid(conteudo_bruto):
    """O que `arquivo.py` precisa para desempatar a colisão real."""
    c = mat.projetar_material(conteudo_bruto)
    itens = [i for s in c.secoes for i in s.itens if i.nome == "Dicas para a Prova.pdf"]

    assert len(itens) == 2, "a colisão real de PSI3323 sumiu da fixture"
    assert {i.fileid for i in itens} == {"9599793", "9599833"}
    assert all(i.secao and i.modulo for i in itens)
    assert all(i.fileurl_bruta and "pluginfile.php" in i.fileurl_bruta for i in itens)


@pytest.mark.politica
def test_T106_aviso_nao_afirma_a_premissa_refutada_e_aponta_baixar_arquivo(
    disciplinas_brutas, conteudo_bruto
):
    """§9 de 01/09/2026: o token autentica no CORPO do POST, não na URL — a
    premissa antiga ('baixá-lo exigiria a credencial NA URL') foi medida
    falsa, e o texto não pode mais afirmá-la. A parte verdadeira continua
    (a URL em si não sai, porque com token exporia a credencial e sem token
    não abre) — T68/T68b/T68c continuam garantindo isso. O que muda é que o
    aviso deixa de ser um beco sem saída e aponta para `baixar_arquivo`."""
    cliente = _cliente_completo(disciplinas_brutas, conteudo_bruto)
    r = mat.material(cliente, "PSI3323", agora=lambda: 0.0)

    # A premissa refutada (§9, 01/09): não é mais verdade que baixar "exige"
    # colar a credencial na URL — o corpo do POST autentica sozinho.
    assert "exige a sua credencial na URL" not in r.texto
    assert "exigiria" not in r.texto.lower()
    # A parte que continua certa: a URL em si não sai.
    assert "não sai desta máquina" in r.texto or "não sai" in r.texto
    # E a saída deixa de ser um beco sem saída ("abra pelo e-Disciplinas"):
    # aponta para a ferramenta que de fato baixa.
    assert "baixar_arquivo" in r.texto


# --- T106, T107: o rótulo do professor entra na listagem -------------------

@pytest.mark.contrato
def test_T106_o_nome_do_modulo_sai_quando_diz_algo_que_o_arquivo_nao_diz(
    conteudo_bruto, disciplinas_brutas
):
    """Medido em 03/09: o nome do módulo é a única descrição semântica que
    existe, e ela era jogada fora. `Formulário Provas Substitutivas.pdf` mora
    no módulo "Formulário para pedido de prova substitutiva" — quem procura por
    "pedido de prova substitutiva" não tinha como achar."""
    cliente = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": 1},
            "core_enrol_get_users_courses": disciplinas_brutas,
            "core_course_get_contents": conteudo_bruto,
            "mod_assign_get_assignments": ENTREGAS_PSI3323_SEM_ANEXO,
        }
    )
    disc.limpar_cache()
    texto = mat.material(cliente, "PSI3323").texto

    assert "Formulário para pedido de prova substitutiva" in texto
    assert "Tutorial básico para aprender a usar o Multisim" in texto


@pytest.mark.contrato
def test_T107_o_nome_do_modulo_e_omitido_quando_repete_o_do_arquivo(
    conteudo_bruto, disciplinas_brutas
):
    """9 dos 29 itens de PSI3323 têm módulo redundante com o nome do arquivo.
    Imprimir os dois seria pagar tokens para dizer a mesma coisa duas vezes."""
    cliente = ClienteFalso(
        {
            "core_webservice_get_site_info": {"userid": 1},
            "core_enrol_get_users_courses": disciplinas_brutas,
            "core_course_get_contents": conteudo_bruto,
            "mod_assign_get_assignments": ENTREGAS_PSI3323_SEM_ANEXO,
        }
    )
    disc.limpar_cache()
    texto = mat.material(cliente, "PSI3323").texto

    # arquivo e módulo idênticos: o rótulo não pode aparecer duas vezes
    assert texto.count("Planilha de Notas - PSI3323 - 2o. Semestre de 2026") == 1


# --------------------------------------------------------------------------
# O que a linha de item NÃO precisa dizer (22/09/2026)
#
# Medido em `notas/custo-em-token.md`: os 57 blocos `[tipo, tamanho, data]` de
# PTC3314 custam 933 tokens contra ~460 dos 57 nomes de arquivo que eles anotam.
# O que anota custava o dobro do anotado.
# --------------------------------------------------------------------------


def test_o_tipo_nao_se_repete_quando_a_extensao_ja_o_diz():
    """`Lista 1.pdf [PDF, …]` diz PDF duas vezes na mesma linha."""
    item = mat.Item(
        nome="Lista 1.pdf",
        tipo="PDF",
        tamanho=None,
        modificado=None,
        url_externa=None,
    )

    linha = mat._formatar_item(item)

    assert "Lista 1.pdf" in linha
    assert "PDF," not in linha and "[PDF]" not in linha


def test_o_tipo_generico_sai_quando_o_nome_tem_extensao():
    """"arquivo" não acrescenta nada a `Provas.zip` — quem lê vê a extensão."""
    item = mat.Item(
        nome="Provas.zip",
        tipo="arquivo",
        tamanho=None,
        modificado=None,
        url_externa=None,
    )

    assert "arquivo" not in mat._formatar_item(item)


def test_o_tipo_fica_quando_a_extensao_nao_o_diz():
    """`.odt` não soletra "documento", e `link` não tem extensão nenhuma: nos
    dois casos o rótulo é a única coisa que diz o que aquilo é."""
    odt = mat.Item(
        nome="EP1-2026.odt",
        tipo="documento",
        tamanho=None,
        modificado=None,
        url_externa=None,
    )
    externo = mat.Item(
        nome="Animação de ondas TEM",
        tipo="link",
        tamanho=None,
        modificado=None,
        url_externa="https://exemplo.invalid/x",
    )

    assert "documento" in mat._formatar_item(odt)
    assert "link" in mat._formatar_item(externo)


def test_o_tamanho_so_sai_quando_muda_a_decisao_de_baixar():
    """O `filesize` prevê o custo do download (medido em 01/09: bate exatamente
    com os bytes recebidos), e isso decide alguma coisa num GIF de 178 MB, não
    num PDF de 400 kB. PTC3314 tem os dois."""
    pequeno = mat.Item(
        nome="aula05.pdf",
        tipo="PDF",
        tamanho=441 * 1024,
        modificado=None,
        url_externa=None,
    )
    enorme = mat.Item(
        nome="tensao_Zl=150_senoide_v2.gif",
        tipo="arquivo",
        tamanho=178086 * 1024,
        modificado=None,
        url_externa=None,
    )

    assert "kB" not in mat._formatar_item(pequeno)
    assert "MB" in mat._formatar_item(enorme)


def test_a_data_continua_saindo_em_todo_item():
    """Ela responde "o que foi postado essa semana", que é pergunta real — e foi
    o único dos três campos que ficou inteiro."""
    item = mat.Item(
        nome="aula07.pdf",
        tipo="PDF",
        tamanho=None,
        modificado=datetime(2026, 8, 25, tzinfo=FUSO_SAO_PAULO),
        url_externa=None,
    )

    assert "25/08/2026" in mat._formatar_item(item)
