"""Camada 2 — a fixture versionada é segura e reproduzível.

Estes são os únicos testes da suíte que passam HOJE: `scripts/higienizar.py`
existe. Servem de piso — se eles ficarem vermelhos, nenhum outro teste significa
coisa alguma, porque o insumo deixou de ser confiável.

16/09/2026: T48 e T49 pulavam SEMPRE. Dependiam de um cru que não existe em
máquina nenhuma há semanas — o `raw/` do checkout principal tem sete arquivos e
nenhum é ele. O skip dizia "só existe na máquina do dono", e a cobertura que ele
escondia era exatamente a das duas propriedades que o higienizador promete. No
mesmo dia, revisão encontrou dado pessoal pontual em fixtures já publicadas que
nenhum teste aqui teria acusado.

Agora as propriedades são provadas sobre TODA fixture publicada e sobre um cru
sintético que exercita cada família (T48-T55), a varredura por conteúdo roda
sobre cada publicada (T56) e é sabotada de propósito (T57, no molde do F7 de
`test_forma_real`), e o cru real, quando existe, é canário de reprodução (T58)
— o único que pula, dizendo o que não conferiu, e nada além dele depende do cru.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.git import esta_ignorado
from tests.moodle.conftest import DIR_CRU, RAIZ

pytestmark = pytest.mark.contrato

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
FIXTURES = RAIZ / "fixtures" / "moodle"
PUBLICADAS = sorted(FIXTURES.glob("*.json"))
IDS = [p.stem for p in PUBLICADAS]

# `scripts/` não é pacote: o módulo é carregado pelo caminho. Importar em vez
# de só rodar por subprocess é o que permite afirmar sobre CADA valor.
_spec = importlib.util.spec_from_file_location("higienizar", RAIZ / "scripts" / "higienizar.py")
hig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hig)

# cru → publicada, e este mapa foi **medido** em 17/09/2026, não escrito de
# memória. O que existia antes afirmava três coisas erradas ao mesmo tempo, e
# nenhuma delas podia aparecer: dos sete pares declarados, cinco nomeavam um cru
# que não existe no disco (T58 pulava, calado), e os dois que existiam eram de
# OUTRA captura — 74 matrículas e 70 itens de nota no cru de 31/08 contra 47 e
# 45 nas publicadas de 15/09. Resultado: o canário reprovava o gate na máquina
# do dono acusando diferença de dado como se fosse de higienização, e no CI,
# onde `raw/` não existe, pulava inteiro. Zero verificação, nas duas pontas.
#
# A medição foi exaustiva e offline: higienizar cada um dos 14 crus e comparar
# com cada uma das 15 publicadas. Três reproduzem, byte a byte, e são estes.
# Uma delas desmente o comentário antigo em particular: a `users_courses.json`
# publicada TEM cru, e é o de 31/08 — a que não tem é a `users_courses_15-09`.
#
# As doze publicadas de fora não entram por decreto: três são fixtures de erro
# (sem cru por natureza), e as outras nove vêm da captura de 15/09, que foi
# publicada **sem guardar o cru**. Recapturar custa chamada da conta do dono
# (Regra de Ouro, §3.1) e é decisão dele, registrada no backlog. Quem publicar
# a próxima captura sem guardar o cru recria exatamente este buraco.
#
# `users_courses_15-09.json` é uma dessas nove, e o par que a nomeava prometia a
# única coisa que só T58 dá: PROCEDÊNCIA — que o arquivo versionado é mesmo a
# saída do higienizador sobre o cru, e não algo editado à mão depois. Essa
# promessa nunca foi cumprida para ela, porque o cru que o par apontava é o de
# 31/08, de outra captura. Quem cobre agora: ninguém, e ninguém pode enquanto o
# cru de 15/09 não for recapturado. O que sobra para ela não é procedência, é
# SEGURANÇA, e isso está coberto sem cru — T48b (estabilidade), T49 (forma e
# comprimento) e T56 (varredura por conteúdo, o teste que teria ficado vermelho
# em 15/09) rodam sobre cada publicada, ela inclusive. A procedência que o par
# de fato entrega, agora que aponta para o cru certo, é a da captura de 31/08.
PARES_CRU = {
    "action_events.json": "action_events.json",
    "course_contents_142033.json": "course_contents_psi3323.json",
    # Este par já foi invertido uma vez, no mesmo 17/09 em que foi medido:
    # `f453d6a` o reapontou para `users_courses_15-09.json` afirmando na
    # mensagem ter conferido, e a conferência diz o contrário. O cru do disco é
    # o de 31/08, com 74 matrículas; a publicada de mesmo nome também tem 74 e é
    # reproduzida byte a byte; a `users_courses_15-09.json` tem 47 e não é.
    # Medido de novo em 22/09/2026, offline, no mesmo molde exaustivo.
    "users_courses.json": "users_courses.json",
}

# Escrito à mão: sem isto, esvaziar `PARES_CRU` deixaria T58 verde sem comparar
# nada, que é a forma de falso-verde que este arquivo persegue — e foi
# literalmente o estado do arquivo até 17/09, com cinco pares fantasmas.
PARES_ESPERADOS = 3


def _cru_sintetico() -> dict:
    """Payload INVENTADO que exercita cada família do higienizador, com os três
    vazamentos de 15/09 reproduzidos em forma e com chaves que nunca apareceram
    em fixture nenhuma. Nenhum valor aqui é de gente real."""
    return {
        "userid": 654321,
        "useridnumber": "12345678",
        "fullname": "Fulana de Tal",
        "email": "fulana@exemplo.edu",
        "userprivateaccesskey": "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
        "userpictureurl": "https://edisciplinas.usp.br/pluginfile.php/1234567/user/icon/edis/f2?rev=123456789",
        "enrolledusercount": 87,
        "lastaccess": 1787869161,
        "timemodified": 1784131298,
        "shortname": "PME3100-203-2023 - Prof. F. Sobrenome",
        "idnumber": "PTC3312.2.2026205",
        "usergrades": [{
            "courseid": 142033,
            "gradeitems": [
                {
                    "id": 11, "cmid": 22, "itemname": "Teste semanal 1",
                    "graderaw": 6.19, "gradeformatted": "6,19",
                    "percentageraw": 61.9, "percentageformatted": "61,90 %",
                    "lettergradeformatted": "C", "rank": 3,
                    "feedback": "Muito bem, Fulana", "feedbackformat": 2,
                    "gradedatesubmitted": 1786839563, "gradedategraded": 1786839563,
                    "gradeishidden": False, "grademax": 10,
                },
                {
                    "id": 12, "cmid": 23, "itemname": "Sem nota",
                    "graderaw": None, "gradeformatted": "-", "percentageformatted": "-",
                    "gradedatesubmitted": None, "gradedategraded": None,
                },
            ],
        }],
        "lastattempt": {
            "submission": {
                "id": 14692794, "userid": 0,
                "timecreated": 1789348047, "timemodified": 1789348047,
                "plugins": [
                    {"type": "file", "fileareas": [{"area": "submission_files", "files": [{
                        "filename": "EP1_PTC3314_12345678.pdf",
                        "fileurl": "https://edisciplinas.usp.br/webservice/pluginfile.php/9599969/"
                                   "assignsubmission_file/submission_files/14692794/"
                                   "EP1_PTC3314_12345678.pdf?forcedownload=1",
                        "timemodified": 1789348047,
                    }]}]},
                    {"type": "onlinetext", "editorfields": [
                        {"name": "onlinetext", "text": "<p>Minha resposta</p>"},
                    ]},
                ],
            },
            "submissiongroupmemberswhoneedtosubmit": [111111, 222222],
            "gradingstatus": "notgraded",
            "timelimit": 0,
        },
        "modules": [{
            "id": 5, "name": "Slides Aula 01 - Prof. Sobrenome",
            "availabilityinfo": "Disponível se: Você faz parte de <strong>T-X-2026201</strong>",
            "contents": [{
                "filename": "Dicas para a Prova.pdf",
                "fileurl": "https://edisciplinas.usp.br/webservice/pluginfile.php/9599793/"
                           "mod_resource/content/2/Dicas%20para%20a%20Prova.pdf?forcedownload=1",
                "timemodified": 1784986757,
            }],
        }],
        "events": [{
            "editurl": "https://edisciplinas.usp.br/course/mod.php?update=6536226&return=1&sesskey=AbCdEf1234",
        }],
        # Chaves que NUNCA apareceram numa fixture — a rede tem de pegar mesmo assim.
        "relateduserfullname": "Beltrano Silva",
        "authoremail": "beltrano@exemplo.edu",
        "profileimageurlsmall": "https://edisciplinas.usp.br/pluginfile.php/7654321/user/icon/edis/f2",
        "submitteruserid": 4242,
        "grader": 777,
        "activity": "Entrega do EP1 da Fulana",
        "gradefordisplay": '<div class="text_to_html">7,50</div>',
        "author": {
            "id": 999, "fullname": "Ciclano",
            "urls": {"profileimage": "https://x/pluginfile.php/55555/user/icon/f1"},
        },
    }


def _forma(n, chave=None):
    """Tipo, ordem de chaves, contagem, bytes de string e dígitos de inteiro.

    A única exceção ao comprimento é a família opaca (`customdata`): blob do
    PHP que ninguém lê e que é ESVAZIADO de propósito desde 15/09. Aqui ela
    conta só o tipo — o que a docstring do higienizador declara."""
    if isinstance(n, dict):
        return {k: _forma(v, k) for k, v in n.items()}
    if isinstance(n, list):
        return ("lista", len(n), [_forma(v, chave) for v in n])
    if isinstance(n, bool) or n is None:
        return type(n).__name__
    if isinstance(n, str):
        if chave is not None and chave.lower() in hig.CAMPOS_OPACOS:
            return "str-opaca"
        return ("str", len(n.encode()))
    if isinstance(n, int):
        return ("int", len(str(abs(n))))
    return type(n).__name__


# --------------------------------------------------------------------------
# T45-T47: como eram
# --------------------------------------------------------------------------


def test_a_fixture_versionada_nao_tem_email(caminho_fixture):
    """T45 — §3.3 e Invariante 3."""
    texto = caminho_fixture.read_text(encoding="utf-8")
    if "@" not in texto:  # o regex é quadrático em texto longo sem arroba
        return
    for m in RE_EMAIL.findall(texto):
        assert m.endswith("exemplo.invalid"), f"e-mail real na fixture: domínio de {m}"


def test_a_fixture_versionada_nao_contem_segredo_do_env(caminho_fixture):
    """T46 — a asserção nunca imprime o valor que procura."""
    texto = caminho_fixture.read_text(encoding="utf-8")
    vazados = [
        nome
        for nome in ("MOODLE_TOKEN", "MOODLE_USERID", "RUCARD_HASH")
        if (v := os.environ.get(nome)) and len(v) >= 4 and v in texto
    ]
    assert vazados == [], f"segredo presente na fixture: {vazados}"


def test_a_fixture_esta_no_git_e_o_cru_nao(caminho_fixture):
    """T47 — a separação do .gitignore é o que torna a suíte portátil."""
    def rastreado(p: Path) -> bool:
        r = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(p.relative_to(RAIZ))],
            cwd=RAIZ, capture_output=True,
        )
        return r.returncode == 0
    assert rastreado(caminho_fixture), "fixture higienizada fora do git"
    # A chamada era relativa e por isso escapou do BUG-2 — mas passa pelo helper
    # do mesmo jeito: a regra é UM lugar que sabe perguntar (G5), não "os que
    # estavam errados". Sobrando um segundo lugar certo, o próximo call site
    # copia dele e o absoluto volta.
    assert esta_ignorado(
        RAIZ / "fixtures" / "moodle" / "raw" / "action_events.json", RAIZ
    ), "fixtures/moodle/raw/ deixou de ser ignorada"


# --------------------------------------------------------------------------
# T48-T49: as duas propriedades, provadas SEM cru
# --------------------------------------------------------------------------


def test_t48_higienizar_e_estavel_entre_processos(tmp_path):
    """T48 — mesmo valor → mesmo valor falso (§3.3), duas execuções byte-idênticas.

    Em processos separados de propósito: `hash()` de string muda a cada
    processo, e um higienizador que o usasse passaria numa comparação dentro
    do mesmo processo. Sem isto, cada regeneração produz um diff gigante e a
    fixture vira ruído no histórico.
    """
    entrada = tmp_path / "cru.json"
    entrada.write_text(json.dumps(_cru_sintetico()), encoding="utf-8")
    saidas = []
    for i in range(2):
        destino = tmp_path / f"s{i}.json"
        subprocess.run(
            [sys.executable, "scripts/higienizar.py", str(entrada), str(destino)],
            cwd=RAIZ, check=True, capture_output=True,
        )
        saidas.append(destino.read_bytes())
    assert saidas[0] == saidas[1]


@pytest.mark.parametrize("caminho", PUBLICADAS, ids=IDS)
def test_t48b_higienizar_e_estavel_sobre_cada_publicada(caminho):
    dado = json.loads(caminho.read_text(encoding="utf-8"))
    assert hig.higienizar(dado) == hig.higienizar(json.loads(caminho.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "dado",
    [pytest.param(p, id=p.stem) for p in PUBLICADAS] + [pytest.param(None, id="cru-sintetico")],
)
def test_t49_higienizar_preserva_forma_e_comprimento(dado):
    """T49 — o requisito que o §3.3 não tem e o teste de custo exige.

    Se o higienizador encolher os textos, a fixture deixa de sustentar a
    asserção de bytes/evento. Se trocar o tipo (a versão de 31/08 fazia `int`
    virar `float` em `graderaw`), `test_forma_real` passa a conferir
    construtor contra uma forma que o e-Disciplinas não tem.
    """
    cru = _cru_sintetico() if dado is None else json.loads(dado.read_text(encoding="utf-8"))
    assert _forma(hig.higienizar(cru)) == _forma(cru)


# --------------------------------------------------------------------------
# T50-T52: os três vazamentos de 15/09, um a um
# --------------------------------------------------------------------------


def test_t50_o_percentual_ao_lado_da_nota_trocada_e_trocado():
    """T50 — `percentageformatted` ficou real em `grade_items_ptc3314.json`
    enquanto `graderaw` e `gradeformatted` saíam sintéticos. Dizia a nota do
    mesmo jeito. Agora a família de nota é por prefixo, não por nome."""
    cru = _cru_sintetico()
    limpo = hig.higienizar(cru)
    a = cru["usergrades"][0]["gradeitems"][0]
    b = limpo["usergrades"][0]["gradeitems"][0]
    for campo in (
        "graderaw", "gradeformatted", "percentageraw", "percentageformatted",
        "lettergradeformatted", "rank", "feedback", "gradedatesubmitted", "gradedategraded",
    ):
        assert b[campo] != a[campo], f"{campo} passou intacto"
        assert type(b[campo]) is type(a[campo]), f"{campo} mudou de tipo"
    # A forma da nota sobrevive: vírgula, símbolo, uma casa antes da vírgula.
    assert re.fullmatch(r"\d\d,\d\d %", b["percentageformatted"])
    assert re.fullmatch(r"\d,\d\d", b["gradeformatted"])
    # O que descreve o ITEM, e não a nota do dono, fica.
    for campo in ("feedbackformat", "gradeishidden", "grademax", "id", "cmid", "itemname"):
        assert b[campo] == a[campo], f"{campo} é forma do item e foi trocado"
    # "Sem nota" é forma, não valor: o marcador fica.
    sem = limpo["usergrades"][0]["gradeitems"][1]
    assert (sem["gradeformatted"], sem["percentageformatted"], sem["graderaw"]) == ("-", "-", None)


def test_t51_numero_usp_no_nome_do_arquivo_e_trocado():
    """T51 — `EP1_PTC3314_<8 dígitos>.pdf` em `submission_status_ec1.json`, entrega
    em grupo: o número era provavelmente de um colega. O contexto do arquivo e
    o id da entrega no caminho ficam; o run de dígitos do nome sai marcado."""
    cru = _cru_sintetico()
    limpo = hig.higienizar(cru)
    arq = limpo["lastattempt"]["submission"]["plugins"][0]["fileareas"][0]["files"][0]
    assert re.fullmatch(r"EP1_PTC3314_0\d{7}\.pdf", arq["filename"]), arq["filename"]
    assert arq["fileurl"].startswith(
        "https://edisciplinas.usp.br/webservice/pluginfile.php/9599969/"
        "assignsubmission_file/submission_files/14692794/"
    )
    assert arq["fileurl"].endswith(arq["filename"] + "?forcedownload=1")
    # Material sem dígito longo não muda: os testes de download usam os reais,
    # e `%20` seguido de ano não pode virar run de dígitos.
    assert limpo["modules"][0]["contents"] == cru["modules"][0]["contents"]
    assert hig.higienizar({"fileurl": "https://x/pluginfile.php/1/c/Linhas%20e%20Ondas%202026.pdf"}) == {
        "fileurl": "https://x/pluginfile.php/1/c/Linhas%20e%20Ondas%202026.pdf"
    }


def test_t52_contexto_de_usuario_na_foto_e_trocado_mesmo_sob_chave_desconhecida():
    """T52 — `pluginfile.php/<n>/user/icon` em `forum_discussions_avisos.json`: o
    contexto é estável e único por pessoa, e era de um professor. Pega pela
    família (`*pictureurl`) E pelo conteúdo, para a próxima chave nova."""
    cru = _cru_sintetico()
    limpo = hig.higienizar(cru)
    assert re.fullmatch(
        r"https://edisciplinas\.usp\.br/pluginfile\.php/0\d{6}/user/icon/edis/f2\?rev=0\d{8}",
        limpo["userpictureurl"],
    ), limpo["userpictureurl"]
    solto = "veja https://edisciplinas.usp.br/pluginfile.php/1234567/user/icon/edis/f1"
    saida = hig.higienizar({"observacao": solto})["observacao"]
    assert "pluginfile.php/1234567/user/" not in saida
    assert re.search(r"pluginfile\.php/0\d{6}/user/icon/edis/f1$", saida)
    assert len(saida) == len(solto)


# --------------------------------------------------------------------------
# T53-T55: a CLASSE, não os casos
# --------------------------------------------------------------------------


def test_t53_credencial_sai_com_a_forma_e_sem_o_valor():
    """T53 — `userprivateaccesskey` é a chave do RSS da conta; `sesskey=` em
    `editurl` de `action_events.json` estava publicado desde 31/08."""
    cru = _cru_sintetico()
    limpo = hig.higienizar(cru)
    assert re.fullmatch(r"0000[0-9a-f]{28}", limpo["userprivateaccesskey"])
    assert limpo["userprivateaccesskey"] != cru["userprivateaccesskey"]
    assert re.search(r"&sesskey=0000[0-9A-Za-z]{6}$", limpo["events"][0]["editurl"])
    assert limpo["events"][0]["editurl"].startswith(
        "https://edisciplinas.usp.br/course/mod.php?update=6536226&return=1&"
    )
    # 32 hex debaixo de chave que ninguém previu.
    assert re.fullmatch(r"0000[0-9a-f]{28}", hig.higienizar({"foo": "9f8e7d6c5b4a39281706f5e4d3c2b1a0"})["foo"])


def test_t54_chave_nova_de_familia_conhecida_cai_na_rede():
    """T54 — o buraco era decidir por igualdade de nome. Nenhuma destas chaves
    está escrita no higienizador; todas caem por prefixo, sufixo ou contexto."""
    cru = _cru_sintetico()
    limpo = hig.higienizar(cru)
    for chave in (
        "relateduserfullname", "authoremail", "profileimageurlsmall", "submitteruserid",
        "grader", "activity", "gradefordisplay", "lastaccess", "useridnumber",
    ):
        assert limpo[chave] != cru[chave], f"{chave} passou intacto"
        assert type(limpo[chave]) is type(cru[chave]), f"{chave} mudou de tipo"
    assert re.fullmatch(r"0\d{7}", limpo["useridnumber"])
    assert limpo["gradefordisplay"].startswith('<div class="text_to_html">')
    # `author` como dicionário: `id` é de pessoa porque o pai diz.
    assert limpo["author"]["id"] != 999
    assert limpo["author"]["fullname"] != "Ciclano"
    assert "55555" not in limpo["author"]["urls"]["profileimage"]
    # Lista de colegas que faltam entregar: cada um é userid de terceiro.
    faltam = limpo["lastattempt"]["submissiongroupmemberswhoneedtosubmit"]
    assert faltam != [111111, 222222] and all(isinstance(x, int) and 10**5 <= x < 10**6 for x in faltam)
    # Debaixo de `submission`, `time*` é quando o DONO entregou.
    sub = limpo["lastattempt"]["submission"]
    assert sub["timecreated"] != 1789348047 and sub["timemodified"] != 1789348047
    assert sub["plugins"][0]["fileareas"][0]["files"][0]["timemodified"] != 1789348047
    # Entrega em texto e condição de acesso que nomeia a turma são texto livre.
    texto = sub["plugins"][1]["editorfields"][0]["text"]
    assert texto != "<p>Minha resposta</p>" and texto.startswith("<p>")
    assert limpo["modules"][0]["availabilityinfo"] != cru["modules"][0]["availabilityinfo"]
    # E o inverso — forma do curso, não do dono, fica como está.
    for chave in ("enrolledusercount", "timemodified", "idnumber"):
        assert limpo[chave] == cru[chave], f"{chave} é forma do curso e foi trocado"
    assert limpo["lastattempt"]["gradingstatus"] == "notgraded"
    assert limpo["lastattempt"]["timelimit"] == 0
    assert limpo["modules"][0]["id"] == 5
    assert limpo["usergrades"][0]["courseid"] == 142033
    assert sub["userid"] == 0, "zero em teamsubmission.userid significa 'do grupo'"
    assert sub["id"] == 14692794


def test_t55_nome_depois_de_honorifico_e_trocado_no_rotulo_que_e_produto():
    """T55 — `name` de módulo e `shortname` de turma não são trocados por
    inteiro (são o produto), mas "Prof. Fulano" dentro deles é gente. É a
    cura do BACKLOG de 15/09, que dizia que o higienizador "não tem como saber"."""
    cru = _cru_sintetico()
    limpo = hig.higienizar(cru)
    nome = limpo["modules"][0]["name"]
    assert nome.startswith("Slides Aula 01 - Prof. ") and "Sobrenome" not in nome
    assert len(nome.encode()) == len(cru["modules"][0]["name"].encode())
    sigla = limpo["shortname"]
    assert sigla.startswith("PME3100-203-2023 - Prof. ") and "Sobrenome" not in sigla
    assert len(sigla.encode()) == len(cru["shortname"].encode())


# --------------------------------------------------------------------------
# T56-T57: a varredura por conteúdo, e a sabotagem dela
# --------------------------------------------------------------------------


@pytest.mark.parametrize("caminho", PUBLICADAS, ids=IDS)
def test_t56_nenhuma_publicada_tem_forma_de_dado_pessoal(caminho):
    """T56 — roda sobre TODA fixture versionada, cega para o nome da chave.
    É o teste que teria ficado vermelho em 15/09."""
    assert hig.alertas(json.loads(caminho.read_text(encoding="utf-8"))) == []


def test_t57_a_varredura_pega_cada_forma_que_promete_pegar():
    """T57 — sabotagem da própria varredura, no molde do F7.

    Sem isto, um `alertas()` que não descesse em lista deixaria T56 verde sem
    olhar nada — o falso-verde que este arquivo existe para impedir.
    """
    plantados = {
        "email": ("dono@usp.br", "e-mail"),
        "icone": ("https://edisciplinas.usp.br/pluginfile.php/2468135/user/icon/edis/f2", "contexto de usuário"),
        "chave": ("9f8e7d6c5b4a39281706f5e4d3c2b1a0", "32 hex"),
        "sessao": ("https://x/course/mod.php?update=1&sesskey=AbCdEf1234", "credencial em parâmetro"),
        "filename": ("EP1_PTC3314_12345678.pdf", "Número USP"),
        "rotulo": ("Slides Aula 01 - Prof. Sobrenome", "honorífico"),
    }
    for chave, (valor, motivo) in plantados.items():
        achados = hig.alertas({"x": [{chave: valor}]})
        assert achados, f"a varredura não acusou {chave}"
        assert achados[0].startswith(f"x[0].{chave}:"), (chave, achados)
        assert motivo in achados[0], (chave, achados)
        assert valor not in achados[0], "a varredura não pode ecoar o valor"

    # A regra cura tudo que a varredura vê: depois de higienizar, silêncio.
    sujo = {"x": [{k: v for k, (v, _) in plantados.items()}]}
    assert hig.alertas(hig.higienizar(sujo)) == []

    # E não acusa o que é legítimo: contexto de curso, turma, tamanho em bytes,
    # e-mail sintético, honorífico já trocado, sesskey já trocado.
    limpo = {
        "fileurl": "https://edisciplinas.usp.br/webservice/pluginfile.php/9599969/mod_assign/introattachment/0/EP1-2026.pdf",
        "idnumber": "PTC3312.2.2026205",
        "value": "10485760",
        "email": "pessoa123456@exemplo.invalid",
        "name": "Slides Aula 01 - Prof. Di Nio",
        "editurl": "https://x/course/mod.php?update=6536226&return=1&sesskey=0000abcdef",
        "courseimage": "data:image/png;base64,iVBORw0KGgo12345678AAAA",
    }
    assert hig.alertas(limpo) == []


def test_t57b_a_cli_nao_grava_o_que_a_varredura_ainda_acusa(tmp_path):
    """Erra para o lado seguro: run de 8 dígitos em chave que família nenhuma
    prevê não é trocado (poderia ser qualquer coisa), mas também não entra no
    git em silêncio — a CLI recusa, diz o caminho e não diz o valor."""
    entrada = tmp_path / "cru.json"
    entrada.write_text(json.dumps({"observacao": "aluno 12345678 faltou"}), encoding="utf-8")
    destino = tmp_path / "saida.json"
    r = subprocess.run(
        [sys.executable, "scripts/higienizar.py", str(entrada), str(destino)],
        cwd=RAIZ, capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert not destino.exists(), "gravou fixture que a própria varredura acusa"
    assert "observacao" in r.stderr and "12345678" not in r.stderr


# --------------------------------------------------------------------------
# T58: o cru, quando existe, reproduz a publicada
# --------------------------------------------------------------------------


@pytest.mark.parametrize("cru,publicada", sorted(PARES_CRU.items()), ids=list(PARES_CRU.values()))
def test_t58_o_cru_quando_existe_reproduz_a_publicada(cru, publicada):
    """T58 — canário de reprodução. É o ÚNICO teste deste arquivo que depende do
    cru, e o skip diz exatamente o que não conferiu: só isto."""
    origem = DIR_CRU / cru
    if not origem.exists():
        pytest.skip(
            f"cru ausente: {origem}. Canário de reprodução, e só ele — as "
            "propriedades do higienizador são provadas em T48-T57 sem cru nenhum."
        )
    esperado = json.loads((FIXTURES / publicada).read_text(encoding="utf-8"))
    assert hig.higienizar(json.loads(origem.read_text(encoding="utf-8"))) == esperado


def test_t58b_o_canario_nao_pode_encolher_em_silencio():
    """T58b — anti-vácuo do T58, que é o único teste com skip embutido.

    T58 pula quando o cru não existe, e é o certo: no CI `raw/` não existe e
    nada disso é alcançável. Mas skip e lista vazia se parecem de fora, e um
    par removido para calar uma reprovação não deixaria rastro nenhum.
    """
    assert len(PARES_CRU) == PARES_ESPERADOS, (
        f"o canário de reprodução tem {len(PARES_CRU)} pares e a conta declarada "
        f"é {PARES_ESPERADOS}. Se um par saiu, diga aqui por que saiu e baixe o "
        "número junto — foi o que 17/09 fez ao trocar sete pares declarados por "
        "três medidos. Se um entrou, suba o número."
    )
