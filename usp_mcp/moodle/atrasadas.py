"""O que venceu e o e-Disciplinas não registra como entregue.

`o_que_vence` olha para a frente e `ja_entreguei` olha uma disciplina de cada
vez. Esta olha para trás e cruza as duas metades — o prazo que já passou e o
estado da entrega —, que é o que nenhuma das funções sabe sozinha:
`mod_assign_get_assignments` diz o prazo e nunca o que foi feito, e
`mod_assign_get_submission_status` diz o que foi feito e nunca por disciplina.
As duas já estavam na allowlist; **nenhuma função nova entrou por causa desta
ferramenta** (AT18), e a projeção e os tetos são os de `ja_entreguei`, importados
e não recopiados.

**O TOM É REQUISITO, E É A DECISÃO MAIS IMPORTANTE DESTE MÓDULO.** Esta é a
primeira resposta do projeto que acusa alguém, e a acusação é sobre um dado que
o e-Disciplinas só conhece pela metade: ele sabe o que foi REGISTRADO nele.
Entrega no papel, por e-mail, num sistema do laboratório, ou que o professor
recebeu e nunca lançou, é invisível daqui. Por isso, e em toda a saída:

1. **Nunca "você não entregou".** A frase é sempre sobre o registro: *"o
   e-Disciplinas não registra envio seu"*. A diferença não é diplomacia — uma é
   afirmação sobre a pessoa, a outra é sobre o sistema, e só a segunda é
   verificável daqui.
2. **Nota lançada sem envio registrado NÃO é falta** (AT8). `gradingstatus:
   "graded"` sem `submission` é, quase sempre, entrega que aconteceu fora do
   Moodle e nota que o professor pôs à mão. Contá-la como faltando seria o erro
   mais caro desta ferramenta: alarme sobre algo que já foi feito **e já foi
   corrigido**. É o único desmentido que a própria API oferece, e ele é usado.
3. **Prorrogação individual ainda válida não é atraso** (AT10, e é o J8 um passo
   adiante): ela existe justamente para este aluno.
4. **`nosubmissions` nunca vira acusação** (AT5). A prova presencial que o
   professor criou só para ter data não tem como ser entregue pelo site.
5. **Warning da API vira aviso** (AT13). "Nada em atraso" sobre uma lista que o
   Moodle avisou estar incompleta é o falso vazio do Invariante 7 no lugar em
   que ele custa mais caro: é esta resposta que faz alguém parar de procurar.

**O escopo, e por que ele não é uma disciplina obrigatória.** "O que eu devo?" é
pergunta de todas as matérias de uma vez — obrigar a sigla faria repetir a
pergunta dez vezes, e isso `ja_entreguei` já faz melhor. Sem sigla, o escopo são
as disciplinas **em andamento** (`disciplinas.situacao_de`, sem gastar chamada,
porque a lista já está cacheada), com teto de `TETO_DISCIPLINAS` por invocação.
O teto aqui é de BYTES e não de latência: a chamada é uma só, mas o payload
cresce com o número de `courseid` — a fixture real de PTC3314 tem 8.571 B para
quatro `assign` (7.975 B em disco), e o item 8 do `CLAUDE.md` proíbe ler
resposta crua acima de ~200 kB. Dez disciplinas nessa ordem de grandeza dão
~86 kB, que é ARITMÉTICA sobre uma disciplina medida e não uma medição: a única
captura desta função que existe cobre um curso. O que fica de fora do teto é
NOMEADO, e não contado (AT12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .disciplinas import EM_ANDAMENTO, carregar, resolver, situacao_de
from .erros import ErroMoodle
from .ja_entreguei import (
    COBERTURA,
    TETO_CONSULTAS,
    Situacao,
    envio_registrado,
    projetar_entregas,
    projetar_status,
)
from .projecao import FUSO_SAO_PAULO
from .ressalvas import AUSENCIA, PRESENCA, Ressalva, emitir
from .texto import formatar_data

# Quantas disciplinas uma invocação cobre. Ver a docstring do módulo: é teto de
# BYTES do payload cru, e não de latência — a chamada continua sendo uma só.
TETO_DISCIPLINAS = 10

_SEM_REGISTRO = "o e-Disciplinas não registra envio seu"
_RASCUNHO = "RASCUNHO SALVO, NÃO ENVIADO"

# A frase que separa o que o sistema sabe do que aconteceu.
#
# **Até 22/09/2026 ela saía em TODA resposta**, e o comentário que estava aqui
# defendia isso: "quem lê 'nada em atraso' também precisa saber que a lista só
# enxerga o que foi registrado". O argumento não se sustenta, e vale dizer por
# quê, porque desfazer decisão registrada sem explicação é como a próxima sessão
# a refaz. O risco que esta frase cobre é **acusar**: envio que existiu e o
# e-Disciplinas não registrou aparece na lista como falta, nunca como ausência.
# Na resposta vazia não há acusação nenhuma para desmentir — e o que aquela
# resposta precisa dizer é outra coisa, que é a `COBERTURA` logo abaixo: pode
# haver questionário fechado, que esta ferramenta não vê. As duas protegem
# leituras diferentes, e agora cada uma sai na sua (`ressalvas.py`).
_REGISTRO_NAO_E_FATO = (
    "Esta resposta diz o que o e-Disciplinas REGISTRA, e não o que você fez. "
    "Entrega no papel, por e-mail, em outro sistema, ou que o professor "
    "recebeu e não lançou aqui, não aparece como enviada. Confirme na página "
    "da disciplina ou com o professor antes de concluir que ficou faltando."
)

# O `_ONDE_VER_MAIS` que morava aqui saiu em 22/09/2026, e não foi perdido: ele
# está, quase palavra por palavra, na descrição desta ferramenta — medida a
# sobreposição de vocabulário, 85%. A descrição fica no contexto do cliente a
# sessão inteira; repeti-la na resposta era pagar a mesma frase duas vezes na
# mesma sessão. Roteamento não é ressalva, e por isso nem chega a `ressalvas.py`.

# As duas ressalvas invariáveis desta ferramenta, e a leitura errada que cada uma
# desmente. Ver `ressalvas.py` para a regra.
_RESSALVAS = (
    Ressalva(texto=_REGISTRO_NAO_E_FATO, quando=PRESENCA),
    Ressalva(texto=COBERTURA, quando=AUSENCIA),
)


@dataclass(frozen=True)
class RespostaAtrasadas:
    """As contagens saem daqui e não da prosa: quem chama não deveria ter de
    reabrir o texto para saber se a lista do que falta está vazia."""

    texto: str
    faltando: int
    entregues: int
    consultadas: int
    truncado: bool = False
    disciplinas_de_fora: int = 0
    vazio_por: str | None = None


def _dias_de_atraso(quando: datetime, agora: datetime) -> str:
    dias = (agora - quando).days
    if dias <= 0:
        return "venceu hoje"
    return f"venceu há {dias} dia" + ("s" if dias > 1 else "")


def _linha(s: Situacao, sigla: str, agora: datetime) -> str:
    prazo = s.entrega.prazo
    cabeca = f"  {formatar_data(prazo)}  {sigla} — {s.entrega.nome}"
    if s.estado == _RASCUNHO or "RASCUNHO" in s.estado:
        corpo = f": {_RASCUNHO}"
        if s.quando is not None:
            corpo += f" (salvo em {formatar_data(s.quando)})"
    else:
        corpo = f": {_SEM_REGISTRO}"
    linha = f"{cabeca}{corpo} — {_dias_de_atraso(prazo, agora)}"
    if s.arquivos:
        # O NOME do arquivo do rascunho, nunca o endereço (Invariante 3): é o
        # que faz quem lê reconhecer que o trabalho existe e só não foi enviado.
        linha += "\n      salvo lá: " + ", ".join(s.arquivos)
    return linha


def _escopo(lista, disciplina, agora):
    """As disciplinas que a consulta vai cobrir, e o que ficou de fora.

    Sigla que não resolve levanta antes de qualquer chamada (AT3): perguntar ao
    Moodle para descobrir que a pergunta estava errada gasta chamada da conta do
    dono à toa, e cada uma fica no log.
    """
    if disciplina:
        resolucao = resolver(lista, disciplina)
        if resolucao.disciplina is None:
            raise ErroMoodle(resolucao.motivo)
        return [resolucao.disciplina], []

    correntes = sorted(
        (d for d in lista if situacao_de(d, agora) == EM_ANDAMENTO),
        key=lambda d: (d.sigla, d.rotulo),
    )
    if not correntes:
        # Sem escopo, `mod_assign_get_assignments` devolveria as 74 matrículas
        # (1 MB, ~251k tokens — §9, 28/08). E uma lista vazia aqui leria como
        # "você não deve nada", que é a pior coisa que esta ferramenta pode
        # dizer sem ter olhado (AT15).
        raise ErroMoodle(
            "Nenhuma disciplina em andamento agora, pelas datas do "
            "e-Disciplinas — então não há escopo para procurar entrega "
            "vencida. Pergunte por uma disciplina pelo nome (parâmetro "
            "`disciplina`), inclusive de semestre passado; `disciplinas` lista "
            "todas as suas matrículas."
        )
    return correntes[:TETO_DISCIPLINAS], correntes[TETO_DISCIPLINAS:]


def atrasadas(cliente, disciplina: str | None = None, agora=None) -> RespostaAtrasadas:
    """Uma chamada para as entregas, uma por entrega vencida que aceita envio.

    `agora` é um DATETIME (o instante da pergunta), e não o relógio do cache de
    `carregar` — mesma armadilha anotada em `ja_entreguei` e em
    `minhas_disciplinas`, e o motivo de nada ser encaminhado adiante.
    """
    agora = agora if agora is not None else datetime.now(FUSO_SAO_PAULO)
    # Erro do cliente sobe daqui sem ser capturado (AT16): falha de credencial
    # virando "você está em dia" é a pior tradução possível — as duas leem
    # igual e só uma manda dormir tranquilo.
    lista = carregar(cliente)
    alvos, de_fora = _escopo(lista, disciplina, agora)
    sigla_de = {d.courseid: d.sigla for d in lista}

    bruto = cliente.chamar(
        "mod_assign_get_assignments",
        **{f"courseids[{i}]": d.courseid for i, d in enumerate(alvos)},
    )
    entregas = projetar_entregas(bruto)
    nao_lidas = len((bruto or {}).get("warnings") or ())

    vencidas = [e for e in entregas if e.prazo is not None and e.prazo < agora]
    sem_envio_possivel = [e for e in vencidas if not e.aceita_envio]
    consultaveis = [e for e in vencidas if e.aceita_envio]

    # O corte fica com as de prazo MAIS RECENTE: o que venceu ontem ainda dá
    # para correr atrás, e entrega de março não é o que se procura em setembro.
    truncado = len(consultaveis) > TETO_CONSULTAS
    cortadas = len(consultaveis) - TETO_CONSULTAS if truncado else 0
    if truncado:
        consultaveis = consultaveis[-TETO_CONSULTAS:]

    situacoes = [
        projetar_status(
            cliente.chamar("mod_assign_get_submission_status", assignid=e.assignid), e
        )
        for e in consultaveis
    ]

    faltando: list[Situacao] = []
    entregues: list[Situacao] = []
    corrigidas_sem_envio: list[Situacao] = []
    prorrogadas: list[Situacao] = []
    for s in situacoes:
        if s.prorrogacao is not None and s.prorrogacao > agora:
            prorrogadas.append(s)
        elif envio_registrado(s):
            entregues.append(s)
        elif s.corrigida:
            # O desmentido que a API oferece: nota lançada sem envio registrado
            # é entrega que aconteceu fora do Moodle (AT8).
            corrigidas_sem_envio.append(s)
        else:
            faltando.append(s)

    # Do mais recente para o mais antigo: a ordem em que dá para agir.
    faltando.sort(key=lambda s: s.entrega.prazo, reverse=True)

    escopo_dito = (
        f"{alvos[0].sigla} ({alvos[0].rotulo})"
        if disciplina
        else f"{len(alvos)} disciplina(s) em andamento"
    )
    linhas = [f"Entregas vencidas — {escopo_dito}:"]

    if faltando:
        linhas.append(f"\nSem registro de envio ({len(faltando)}):")
        linhas.extend(
            _linha(s, sigla_de.get(s.entrega.courseid, "?"), agora) for s in faltando
        )
    else:
        linhas.append(
            "\nNenhuma entrega vencida sem registro de envio. Pelo que o "
            "e-Disciplinas registra, não falta entregar nada com prazo já "
            "vencido."
        )

    if corrigidas_sem_envio:
        # Bloco próprio e não nota de rodapé: é o caso em que a leitura ingênua
        # do payload acusaria quem já entregou.
        linhas.append(
            f"\nVencidas, sem envio registrado, mas JÁ CORRIGIDAS "
            f"({len(corrigidas_sem_envio)}) — o professor lançou nota, então "
            "quase certamente a entrega aconteceu fora do e-Disciplinas:"
        )
        linhas.extend(
            f"  {formatar_data(s.entrega.prazo)}  "
            f"{sigla_de.get(s.entrega.courseid, '?')} — {s.entrega.nome}"
            for s in corrigidas_sem_envio
        )

    if prorrogadas:
        linhas.append(
            f"\nCom prazo prorrogado para você, ainda no prazo "
            f"({len(prorrogadas)}):"
        )
        linhas.extend(
            f"  {sigla_de.get(s.entrega.courseid, '?')} — {s.entrega.nome}: até "
            f"{formatar_data(s.prorrogacao)}"
            for s in prorrogadas
        )

    if sem_envio_possivel:
        linhas.append(
            f"\nVenceram e não aceitam envio pelo e-Disciplinas "
            f"({len(sem_envio_possivel)}) — prova ou atividade presencial que o "
            "professor lançou só para ter data:"
        )
        linhas.extend(
            f"  {formatar_data(e.prazo)}  {sigla_de.get(e.courseid, '?')} — {e.nome}"
            for e in sem_envio_possivel
        )

    if entregues:
        linhas.append(
            f"\n{len(entregues)} entrega(s) vencida(s) constam entregues, e por "
            "isso não estão na lista acima."
        )

    avisos = []
    if truncado:
        avisos.append(
            f"Esta consulta custa uma ida ao e-Disciplinas por entrega vencida, "
            f"e para em {TETO_CONSULTAS}: {cortadas} entrega(s) de prazo mais "
            "antigo não foram verificadas. Pergunte por elas com o parâmetro "
            "`disciplina`."
        )
    if de_fora:
        avisos.append(
            f"Esta consulta cobre {TETO_DISCIPLINAS} disciplinas por vez, e "
            f"{len(de_fora)} disciplina(s) em andamento ficaram de fora: "
            + ", ".join(d.sigla for d in de_fora)
            + ". Pergunte por elas com o parâmetro `disciplina`."
        )
    if nao_lidas:
        # Invariante 7 no ponto em que ele custa mais caro nesta ferramenta.
        avisos.append(
            f"O e-Disciplinas avisou que {nao_lidas} atividade(s) não puderam "
            "ser lidas com esta credencial: pode haver entrega vencida fora "
            "desta lista."
        )
    # A ressalva invariável depende da forma da resposta: com item listado sai a
    # que impede a acusação; sem nenhum, a que impede o falso "não devo nada".
    avisos.extend(emitir(_RESSALVAS, vazio=not faltando))

    linhas.extend(f"\n⚠ {a}" for a in avisos)

    return RespostaAtrasadas(
        texto="\n".join(linhas),
        faltando=len(faltando),
        entregues=len(entregues),
        consultadas=len(situacoes),
        truncado=truncado,
        disciplinas_de_fora=len(de_fora),
        vazio_por=None if faltando else "nada_em_atraso",
    )
