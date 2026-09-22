"""Orçamento de saída: quanto cada ferramenta devolve ao modelo (OR1-OR2).

Este projeto sempre mediu o **cru** que vem da USP — o §9 registra 541 kB para 35
eventos de calendário e a projeção que os reduz a 0,5%. O outro lado nunca teve
medida nem guarda: o que a ferramenta devolve, que é o que de fato ocupa contexto.
Medido em 22/09/2026 (`notas/custo-em-token.md`), `material` custava 2.569 tokens
por chamada e `disciplinas` 1.350 — mais do que qualquer coisa que a suíte
vigiasse.

**Por que em bytes, se a própria nota mostra que byte engana.** Um tokenizador
seria a segunda dependência de runtime deste projeto (hoje só `mcp`), e o
precedente está registrado: o `pypdf` foi instalado para medir os 19 PDFs em
01/09 e desinstalado depois, porque adotá-lo é decisão de §9 e não efeito
colateral de uma medida. Byte é ruim como unidade de custo e ótimo como unidade
de regressão — determinístico, sem versão de vocabulário no meio —, e a pergunta
que este arquivo faz não é "quanto custa": é "cresceu?". A tradução byte→token
mora na nota, medida uma vez, e varia de 1,00× a 1,68× conforme a forma da saída.

**O teto tem folga máxima, e isso é o teste de verdade.** Um teto generoso é um
teste que não verifica: se ele ficar 40% acima do tamanho real, qualquer
crescimento cabe dentro e nada fica vermelho. Por isso OR2 falha nos DOIS sentidos
— acima do teto e folgado demais abaixo dele. Quem cortar bytes baixa o teto no
mesmo commit; quem crescer, precisa dizer por quê. É o mesmo desenho do T39, que
trava a projeção do calendário em 4.000 caracteres, estendido ao resto.

**Três ferramentas ficam de fora, e cada ausência tem motivo:**

- `diagnostico` — o tamanho da saída dele depende do caminho absoluto do `.env`
  desta máquina e de quantas funções o token alcança. Nenhum dos dois é
  propriedade do nosso formato, e um teto sobre eles quebraria na máquina da
  próxima pessoa.
- `questionarios` — não há fixture de `mod_quiz_*` no repositório. Medir com
  entrada fabricada seria medir a fabricação (Regra 11 do `CLAUDE.md`).
- `baixar_arquivo` — a saída é caminho em disco, e o custo dela é o arquivo, não
  o texto. Por decisão de 01/09 ela não extrai texto justamente para isso.

**O que o dublê não prova aqui.** `o_que_vence` manda `timesortfrom/to` ao Moodle
e o dublê devolve a fixture inteira, ignorando a janela: o número abaixo é o de
~4 meses de eventos, não o dos 14 dias do padrão. Continua sendo medida boa de
regressão — mesma entrada, mesma saída — e não é medida de produção.
"""
from __future__ import annotations

import json

import pytest

from usp_mcp.moodle.server import chamar_ferramenta

from .conftest import ClienteFalso

# O `site_info` não é fixture versionada (o cru tem `userid` e nome). Este aqui é
# sintético e declara EXATAMENTE as funções que as ferramentas deste servidor
# pedem — sem elas, `diagnostico` e qualquer caminho que confira capacidade
# responderiam "não alcança", e mediríamos a saída de erro em vez da saída boa.
_FUNCOES = [
    "core_calendar_get_action_events_by_timesort",
    "core_course_get_contents",
    "core_course_get_updates_since",
    "core_enrol_get_users_courses",
    "core_webservice_get_site_info",
    "gradereport_overview_get_course_grades",
    "gradereport_user_get_grade_items",
    "mod_assign_get_assignments",
    "mod_assign_get_submission_status",
    "mod_forum_get_forum_discussions",
    "mod_forum_get_forums_by_courses",
    "mod_quiz_get_quizzes_by_courses",
    "mod_quiz_get_user_attempts",
]

SITE_INFO = {
    "userid": 123456,
    "username": "12345678",
    "fullname": "Nome Sintético",
    "sitename": "e-Disciplinas",
    "release": "5.0.8+ (Build: 20260722)",
    "siteurl": "https://edisciplinas.usp.br",
    "functions": [{"name": n, "version": "5.0"} for n in _FUNCOES],
    "downloadfiles": 1,
    "uploadfiles": 1,
}

# Teto em bytes da saída de cada ferramenta, com a entrada abaixo. Medido em
# 22/09/2026 e travado aqui: ver `notas/custo-em-token.md` para o que cada número
# significa em token, que é outra coisa e varia por ferramenta.
TETO = {
    "disciplinas": 3_300,
    "o_que_vence": 2_900,
    "material": 6_800,
    "avisos": 3_400,
    "notas": 560,
    "atrasadas": 1_350,
    "ja_entreguei": 1_050,
    "o_que_mudou": 1_100,
}

# Folga máxima entre o tamanho real e o teto. 15% é apertado o bastante para que
# um parágrafo novo estoure, e frouxo o bastante para que mexer numa palavra não
# obrigue a mexer no teto. Um teto frouxo é um teste que parou de verificar.
FOLGA_MAXIMA = 0.15


def _respostas(conteudo, entregas, disciplinas_brutas, eventos_brutos):
    """As respostas do e-Disciplinas, por nome de função, vindas das fixtures."""
    return {
        "core_webservice_get_site_info": SITE_INFO,
        "core_enrol_get_users_courses": disciplinas_brutas,
        "core_calendar_get_action_events_by_timesort": eventos_brutos,
        "core_course_get_contents": conteudo,
        "mod_assign_get_assignments": entregas,
        "mod_assign_get_submission_status": _fixture("submission_status_ec1.json"),
        "mod_forum_get_forums_by_courses": _fixture("forums_ptc3314.json"),
        "mod_forum_get_forum_discussions": _fixture("forum_discussions_avisos.json"),
        "gradereport_user_get_grade_items": _fixture("grade_items_ptc3314.json"),
        "gradereport_overview_get_course_grades": _fixture("grades_overview.json"),
        "core_course_get_updates_since": _fixture("updates_since_ptc3314.json"),
    }


def _fixture(nome: str):
    from .conftest import RAIZ

    caminho = RAIZ / "fixtures" / "moodle" / nome
    if not caminho.exists():
        # Fixture obrigatória: sumir daqui tem de FALHAR, nunca dar skip — o
        # mesmo motivo que a docstring do `conftest` dá. Um skip aqui produziria
        # um orçamento verde sem ter medido nada.
        raise AssertionError(f"fixture obrigatória ausente: {caminho}")
    return json.loads(caminho.read_text(encoding="utf-8"))


# Uma chamada por ferramenta, com o argumento que a exercita de verdade. PTC3314
# é a disciplina das fixtures de entrega, fórum e nota; usar outra sigla mediria
# o caminho de "não achei".
CASOS = [
    ("disciplinas", {}),
    ("o_que_vence", {}),
    ("material", {"disciplina": "PTC3314"}),
    ("avisos", {"disciplina": "PTC3314"}),
    ("notas", {}),
    ("atrasadas", {}),
    ("ja_entreguei", {"disciplina": "PTC3314"}),
    ("o_que_mudou", {"disciplina": "PTC3314"}),
]


@pytest.fixture
def saidas(conteudo_ptc3314, entregas_ptc3314, disciplinas_brutas, eventos_brutos):
    """O texto que cada ferramenta devolve, com as fixtures versionadas."""
    respostas = _respostas(
        conteudo_ptc3314, entregas_ptc3314, disciplinas_brutas, eventos_brutos
    )
    return {
        nome: chamar_ferramenta(nome, args, cliente=ClienteFalso(respostas))
        for nome, args in CASOS
    }


def test_or1_toda_ferramenta_do_orcamento_tem_teto(saidas):
    """OR1: o orçamento cobre o que ele diz cobrir.

    Sem isto, alguém acrescenta um caso em CASOS, esquece o teto, e o arquivo
    inteiro passa a medir uma ferramenta a menos sem ficar vermelho.
    """
    assert set(saidas) == set(TETO), (
        "CASOS e TETO descrevem as mesmas ferramentas e divergiram: "
        f"sem teto {sorted(set(saidas) - set(TETO))}, "
        f"sem caso {sorted(set(TETO) - set(saidas))}"
    )


@pytest.mark.parametrize("ferramenta", sorted(TETO))
def test_or2_saida_cabe_no_teto_e_o_teto_nao_e_frouxo(saidas, ferramenta):
    """OR2: falha nos dois sentidos — estourou, ou o teto deixou de medir."""
    tamanho = len(saidas[ferramenta].encode("utf-8"))
    teto = TETO[ferramenta]

    assert tamanho <= teto, (
        f"`{ferramenta}` devolve {tamanho} B, acima do teto de {teto} B. "
        "Se o crescimento é intencional, suba o teto NESTE commit e diga por "
        "quê — o teto é o registro de quanto contexto esta ferramenta ocupa."
    )

    folga = (teto - tamanho) / teto
    assert folga <= FOLGA_MAXIMA, (
        f"`{ferramenta}` devolve {tamanho} B contra teto de {teto} B: "
        f"{folga:.0%} de folga, acima dos {FOLGA_MAXIMA:.0%} permitidos. "
        "A saída encolheu e o teto não acompanhou — baixe o teto, senão ele "
        "para de detectar o próximo crescimento."
    )
