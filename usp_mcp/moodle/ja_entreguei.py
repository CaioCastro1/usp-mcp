"""A outra metade da véspera: "eu já entreguei isso?".

`o_que_vence` diz o que tem prazo; esta diz o que disso já foi feito. São a
mesma pergunta partida em duas, e o dono faz as duas na mesma noite — por isso
as datas saem com a mesma grafia (`texto.formatar_data`, J18) e cada saída
aponta para a outra ferramenta.

**A distinção que justifica a ferramenta inteira.** `mod_assign_get_assignments`
— que `material` já chama — diz o que existe e quando vence, e **nunca** diz o
que foi entregue. Quem sabe isso é `mod_assign_get_submission_status`, e o campo
que importa nela é `lastattempt.submission.status`, com quatro valores:

| valor | o que é |
|---|---|
| ausente | o aluno nunca abriu a entrega |
| `new` | aberta, nada dentro |
| `draft` | **rascunho salvo e NÃO enviado para correção** |
| `submitted` | entregue |
| `reopened` | reaberta para nova tentativa, e a nova ainda não foi enviada |

`draft` é o caso caro, e é a razão de esta ferramenta existir em vez de uma
resposta "olhe no site": o arquivo está lá, a tela mostra o arquivo lá, e o
professor não recebe nada. Uma palavra de diferença no payload, uma reprovação
de diferença na vida (J5).

**Duas decisões de custo, as duas medidas na fixture real de PTC3314 (12/09):**

1. **Entrega que não aceita envio não gasta chamada.** 2 dos 4 `assign` da
   disciplina têm `nosubmissions: 1` — são as duas provas presenciais, que o
   professor criou só para ter data (o mesmo par que `material` registra como
   "entregas sem anexo"). Perguntar o status delas gastaria metade das idas ao
   Moodle para receber "não entregou" sobre algo que não tem como entregar. Elas
   aparecem na saída com o motivo, porque não consultar não é sumir (J3).
2. **Teto de `TETO_CONSULTAS` consultas por invocação.** Esta é a primeira
   ferramenta do projeto que faz **N chamadas**, e o perfil dela está no
   catálogo (§3.5): barata em token, cara em latência, e cada ida fica no log da
   conta do dono (Invariante 5). PSI3472 tem 11 entregas, então o teto morde
   exatamente onde deve — e o corte é declarado, com o nome do parâmetro que o
   evita (J13).

**O que esta ferramenta não sabe, e diz:** questionário (`quiz`) não passa por
`mod_assign_*` — o calendário vê 6 disciplinas contra 4 que têm `assign` (§9,
28/08) — e prova presencial que o professor não modelou no Moodle não existe
para nenhuma das duas. Nota também não sai daqui: o payload de status não traz
`feedback` (catálogo §3.5), e um número que não veio não se inventa.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .disciplinas import carregar, resolver
from .erros import ErroMoodle
from .projecao import FUSO_SAO_PAULO
from .ressalvas import AUSENCIA, PRESENCA, Ressalva, emitir
from .texto import casa, formatar_data

# Quantas consultas de status uma invocação pode gastar. Ver decisão 2 da
# docstring: é teto de LATÊNCIA e de log da conta, não de contexto.
TETO_CONSULTAS = 10

# Os rótulos que quem pergunta lê. Maiúsculas porque a resposta inteira é uma
# linha por entrega e o estado é a única coisa que se procura na linha.
_ENTREGUE = "ENTREGUE"
_RASCUNHO = "RASCUNHO NÃO ENVIADO"
_NADA = "NADA ENVIADO"
_REABERTA = "REABERTA, nada enviado na nova tentativa"
_SEM_ENVIO = "não aceita envio pelo e-Disciplinas"

_POR_STATUS = {"submitted": _ENTREGUE, "draft": _RASCUNHO, "reopened": _REABERTA}


@dataclass(frozen=True)
class Entrega:
    """Um `assign` como `mod_assign_get_assignments` o descreve.

    `aceita_envio` é `nosubmissions == 0` invertido no nome de propósito: o
    campo do Moodle é uma negativa, e uma negativa lida ao contrário num `if`
    faria a ferramenta consultar exatamente as entregas que não existem.

    `courseid` entrou em 14/09 com `atrasadas`, que pergunta por várias
    disciplinas na mesma chamada: sem ele, a resposta traria "EP1" sem dizer
    de qual matéria. Aqui ele não é usado — esta ferramenta já tem a
    disciplina no cabeçalho —, e é opcional para que a projeção continue
    montável a partir de um `assign` solto.
    """

    assignid: int
    nome: str
    prazo: datetime | None
    aceita_envio: bool
    courseid: int | None = None


@dataclass(frozen=True)
class Situacao:
    """Uma entrega e o que se sabe dela. É a projeção inteira: tudo o que não
    está aqui foi descartado de propósito (J11)."""

    entrega: Entrega
    estado: str
    quando: datetime | None = None
    atrasada: bool = False
    corrigida: bool = False
    prorrogacao: datetime | None = None
    arquivos: tuple[str, ...] = ()


@dataclass(frozen=True)
class RespostaJaEntreguei:
    texto: str
    total: int
    consultadas: int
    truncado: bool
    vazio_por: str | None = None


def _data(carimbo) -> datetime | None:
    """Epoch positivo vira data; 0, None e não-inteiro viram "sem data".

    Mesma regra de `projecao._quando_de`, e pelo mesmo motivo: `duedate` aceita
    0, e epoch 0 viraria 01/01/1970 — uma entrega "atrasada há 56 anos".
    """
    if isinstance(carimbo, bool) or not isinstance(carimbo, int) or carimbo <= 0:
        return None
    return datetime.fromtimestamp(carimbo, FUSO_SAO_PAULO)


def projetar_entregas(bruto) -> tuple[Entrega, ...]:
    """`mod_assign_get_assignments` → a lista de entregas, ordenada por prazo.

    As 40 chaves por `assign` da resposta viram quatro. `intro`,
    `introattachments` e `submissionstatement` são as gordas, e as três já são
    resposta de `material` — repeti-las aqui seria pagar duas vezes pela mesma
    informação em duas ferramentas.

    Entrega sem prazo vai para o fim da lista, não para o começo: sem `duedate`
    ela não é a próxima coisa a vencer.
    """
    entregas = [
        Entrega(
            assignid=a.get("id"),
            nome=a.get("name") or "",
            prazo=_data(a.get("duedate")),
            aceita_envio=not a.get("nosubmissions"),
            courseid=curso.get("id"),
        )
        for curso in (bruto or {}).get("courses") or ()
        for a in curso.get("assignments") or ()
    ]
    # O sentinela leva fuso: comparar `datetime.min` ingênuo com uma data
    # ciente do fuso levanta TypeError, e aqui só não levanta hoje porque a
    # tupla nunca chega no segundo elemento com os dois tipos misturados.
    _FIM_DA_FILA = datetime.max.replace(tzinfo=FUSO_SAO_PAULO)
    return tuple(
        sorted(entregas, key=lambda e: e.prazo or _FIM_DA_FILA)
    )


def projetar_status(bruto, entrega: Entrega) -> Situacao:
    """A resposta de `mod_assign_get_submission_status` vira uma `Situacao`.

    **Os dois campos que este corte existe para descartar** são o
    `plugins[].editorfields[].text` — o texto inteiro que o aluno entregou — e o
    `assignmentdata.activity`, o enunciado inteiro em HTML. Nenhum dos dois
    responde "eu já entreguei isso?": o primeiro é o trabalho, e o segundo é
    resposta de `material`, que já o entrega como arquivo.

    Dos arquivos enviados sai o NOME e não a `fileurl` (J12). É a mesma regra de
    `material`, pelo mesmo motivo do Invariante 3: um endereço do webservice só
    serve com a credencial colada atrás.
    """
    ultima = (bruto or {}).get("lastattempt") or {}
    submissao = ultima.get("submission") or {}
    status = submissao.get("status")

    if not submissao or status == "new":
        # Ausente e `new` são a mesma resposta para quem pergunta — "não tem
        # nada lá" — e separá-las na saída seria vocabulário do Moodle vazando.
        #
        # `corrigida` e `prorrogacao` sobrevivem a este retorno desde 14/09, e
        # são as duas coisas que este ramo NÃO pode jogar fora. Nota lançada
        # sem envio registrado é quase sempre entrega feita fora do Moodle, e
        # `atrasadas` usa exatamente isso para não acusar quem já entregou
        # (AT8). E a prorrogação existe justamente para quem ainda NÃO enviou:
        # descartá-la aqui fazia esta ferramenta imprimir "PRAZO VENCIDO" para
        # quem tinha prazo até semana que vem — defeito encontrado ao reusar
        # a projeção em `atrasadas`, e que nenhum teste de `ja_entreguei` via
        # porque todos os casos de prorrogação tinham envio.
        return Situacao(
            entrega=entrega,
            estado=_NADA,
            corrigida=ultima.get("gradingstatus") == "graded",
            prorrogacao=_data(ultima.get("extensionduedate")),
        )

    quando = _data(submissao.get("timemodified"))
    prorrogacao = _data(ultima.get("extensionduedate"))

    # A prorrogação individual GANHA do prazo da turma: ela existe justamente
    # para este aluno, e ignorá-la faria a ferramenta chamar de atrasada uma
    # entrega que o professor liberou (J8).
    limite = prorrogacao or entrega.prazo
    atrasada = bool(
        quando is not None and limite is not None and quando > limite
    )

    arquivos = tuple(
        arquivo.get("filename") or ""
        for plugin in submissao.get("plugins") or ()
        for area in plugin.get("fileareas") or ()
        for arquivo in area.get("files") or ()
        if arquivo.get("filename")
    )

    return Situacao(
        entrega=entrega,
        estado=_POR_STATUS.get(status, status or _NADA),
        quando=quando,
        atrasada=atrasada,
        corrigida=(submissao.get("gradingstatus") or ultima.get("gradingstatus"))
        == "graded",
        prorrogacao=prorrogacao,
        arquivos=arquivos,
    )


def envio_registrado(situacao: Situacao) -> bool:
    """O e-Disciplinas recebeu a entrega para correção?

    Público desde 14/09 porque `atrasadas` faz a mesma pergunta e a resposta
    não pode ser escrita duas vezes: `RASCUNHO` e `REABERTA` parecem entrega
    na tela do Moodle e não são, e é essa exata distinção que as duas
    ferramentas existem para não deixar passar. Uma segunda cópia da regra é
    uma cópia que alguém atualiza sozinha.
    """
    return situacao.estado == _ENTREGUE


def _formatar_linha(s: Situacao, agora: datetime) -> str:
    prazo = formatar_data(s.entrega.prazo) if s.entrega.prazo else "sem prazo"
    linha = f"{prazo}  {s.entrega.nome}: {s.estado}"
    if s.quando is not None and s.estado != _NADA:
        linha += f" {formatar_data(s.quando)}"
    if s.estado in (_NADA, _RASCUNHO, _REABERTA):
        # A metade da pergunta que sobra depois de "não entreguei": ainda dá
        # tempo? O prazo que vale é o prorrogado, quando existe.
        limite = s.prorrogacao or s.entrega.prazo
        if limite is not None:
            linha += " — PRAZO VENCIDO" if limite < agora else " — ainda no prazo"
    if s.atrasada:
        linha += " — DEPOIS DO PRAZO"
    if s.prorrogacao is not None:
        # Dita mesmo quando não muda o veredito: é a explicação de por que uma
        # entrega feita depois do prazo da turma não está marcada como atrasada.
        linha += f" (prazo prorrogado para você até {formatar_data(s.prorrogacao)})"
    if s.corrigida:
        linha += " — já corrigida"
    if s.arquivos:
        linha += "\n    enviado: " + ", ".join(s.arquivos)
    return linha


# Até 17/09/2026 isto mandava para `o_que_vence`, que só sabe a data, e foi o
# beco em que o dono caiu ao perguntar por um questionário. A recusa continua
# (objeto diferente, funções diferentes, sem rascunho e com orçamento de
# tentativa); o que muda é o destino dela.
COBERTURA = (
    "Esta resposta cobre só TAREFA (`assign`) do e-Disciplinas. Questionário "
    "não passa por aqui: para saber se você já fez um questionário, se ainda "
    "dá e quantas tentativas sobram, use `questionarios`; para o que tem "
    "prazo, inclusive questionário, `o_que_vence`. Prova presencial que o "
    "professor não lançou no Moodle não existe em lugar nenhum."
)

_SEM_NOTA = (
    "Esta consulta diz se foi entregue e se já foi corrigida, e NÃO traz a "
    "nota: ela não vem neste pedido ao e-Disciplinas."
)

# As duas ressalvas invariáveis, e a leitura errada que cada uma desmente (ver
# `ressalvas.py`). Elas nunca saem juntas, e os três ramos desta ferramenta
# passaram a pedi-las pela mesma porta — antes a COBERTURA era escrita à mão em
# dois deles e a regra ficava em três lugares.
#
# `_SEM_NOTA` dispara com QUALQUER item listado, e o desenho de 22/09 dizia "só
# quando há item já corrigido". A diferença é deliberada: `emitir` é binário por
# construção, e distinguir "corrigido" exigiria ler `estado` por substring —
# frágil, e a economia não paga. Dispara mais do que o desenho pedia, nunca
# menos.
_RESSALVAS = (
    Ressalva(texto=COBERTURA, quando=AUSENCIA),
    Ressalva(texto=_SEM_NOTA, quando=PRESENCA),
)


def _quantos_warnings(bruto) -> int:
    """`warnings` da resposta, na mesma leitura das outras cinco ferramentas.

    Chave ausente, `null` e `[]` são o mesmo zero: um site que não devolve o
    campo não é um site que avisou coisa nenhuma, e tratar a ausência como erro
    faria a ferramenta gritar contra Moodle de outra faculdade.
    """
    return len((bruto or {}).get("warnings") or ())


def _aviso_da_lista(quantos: int) -> str:
    """As duas chamadas desta ferramenta avisam, e avisam coisas DIFERENTES.

    Esta é a da lista (`mod_assign_get_assignments`): o que ela põe em dúvida é
    a existência da entrega. Pode haver tarefa que nem chegou a aparecer, e
    nenhuma linha da resposta denuncia a falta — a lista fica com cara de
    completa. É o mesmo aviso que `atrasadas` dá, com a mesma contagem.
    """
    return (
        f"O e-Disciplinas avisou que {quantos} atividade(s) desta disciplina "
        "não puderam ser lidas com esta credencial: pode haver entrega fora "
        "desta lista."
    )


def _aviso_do_status(quantos: int) -> str:
    """E esta é a do status (`mod_assign_get_submission_status`).

    O que ela põe em dúvida não é a existência da entrega — essa apareceu —, é
    o VEREDITO impresso na linha dela. Por isso as duas contagens saem
    separadas em vez de somadas: "sumiu da lista" e "está na lista e o estado é
    duvidoso" têm curas diferentes, e um número só apagaria qual é qual.

    A unidade aqui é a ENTREGA e não o item de aviso, porque cada ida destas é
    sobre uma entrega só: dois `warnings` na mesma resposta continuam sendo uma
    entrega para conferir, e dizer "2" mandaria procurar uma que não existe.
    """
    return (
        f"O e-Disciplinas avisou ao responder sobre {quantos} entrega(s) desta "
        f"lista: o estado delas pode estar incompleto, e um {_NADA} aqui pode "
        "ser que não deu para ler — que não é a mesma coisa."
    )


def ja_entreguei(
    cliente, disciplina: str, entrega: str | None = None, agora=None
) -> RespostaJaEntreguei:
    """Uma disciplina, uma ida para listar as entregas, uma ida por entrega.

    Sigla que não resolve levanta erro legível **sem** pedir entrega nenhuma
    (J4): consultar o Moodle para descobrir que a pergunta estava errada é
    gastar chamada da conta do dono à toa. Mesma regra de `material`.
    """
    # `agora` aqui é um DATETIME (o instante da pergunta), e o `agora` de
    # `carregar` é um RELÓGIO (`time.monotonic`, para o TTL do cache). São
    # coisas diferentes com o mesmo nome em dois módulos vizinhos: passar um
    # no lugar do outro compila e erra calado, então nada é encaminhado.
    agora = agora if agora is not None else datetime.now(FUSO_SAO_PAULO)
    lista = carregar(cliente)
    resolucao = resolver(lista, disciplina)
    if resolucao.disciplina is None:
        raise ErroMoodle(resolucao.motivo)

    alvo = resolucao.disciplina
    # O escopo não é otimização: sem `courseids[0]` esta função devolve as 74
    # matrículas, 1 MB, ~251k tokens (§9, 28/08).
    bruto = cliente.chamar(
        "mod_assign_get_assignments", **{"courseids[0]": alvo.courseid}
    )
    todas = projetar_entregas(bruto)
    # Lido do bruto e não da projeção: `projetar_entregas` devolve só as
    # entregas, e o aviso é justamente sobre o que não virou entrega nenhuma.
    nao_listadas = _quantos_warnings(bruto)
    cabecalho = f"{alvo.sigla} ({alvo.rotulo}) — já entreguei?"

    if not todas:
        # 6 das 10 disciplinas do semestre não têm `assign` nenhum (§9, 12/09).
        # Vazio é comum aqui, e vazio mudo seria o falso "não tem nada".
        #
        # E é aqui que o aviso da lista pesa mais do que em qualquer outro
        # ramo: `courses` vazio COM warning é o Moodle dizendo "não te deixei
        # ver", enquanto a frase abaixo, sozinha, diz "não há o que entregar".
        # As duas leem igual e só uma manda dormir tranquilo.
        avisos = [_aviso_da_lista(nao_listadas)] if nao_listadas else []
        avisos.extend(emitir(_RESSALVAS, vazio=True))
        return RespostaJaEntreguei(
            texto=f"{cabecalho}\n\nEsta disciplina não tem nenhuma tarefa de "
            "entrega no e-Disciplinas."
            + "".join(f"\n\n⚠ {a}" for a in avisos),
            total=0,
            consultadas=0,
            truncado=False,
            vazio_por="sem_entregas",
        )

    filtro = (entrega or "").strip()
    escolhidas = [e for e in todas if casa(filtro, e.nome)]

    if filtro and not escolhidas:
        # "Nada com esse nome" ≠ "nada para entregar". Dizer o total é o que
        # permite a quem lê distinguir as duas — e nenhuma chamada de status
        # sai para um filtro que não casou (J15).
        #
        # O total também é uma afirmação, e o warning a enfraquece: a entrega
        # procurada pode estar exatamente entre as que não foram lidas.
        #
        # E a COBERTURA sai aqui também, desde 17/09/2026. Este é o ramo exato
        # de quem pergunta por um questionário pelo nome ("já entreguei o
        # Teste 12?"), e era o único que ficava mudo sobre questionário: listava
        # as quatro entregas e parava (J26).
        avisos = [_aviso_da_lista(nao_listadas)] if nao_listadas else []
        avisos.extend(emitir(_RESSALVAS, vazio=True))
        return RespostaJaEntreguei(
            texto=(
                f"{cabecalho}\n\nNenhuma entrega com {entrega!r} no nome. A "
                f"disciplina tem {len(todas)} entregas: "
                + ", ".join(e.nome for e in todas)
                + "."
                + "".join(f"\n\n⚠ {a}" for a in avisos)
            ),
            total=len(todas),
            consultadas=0,
            truncado=False,
            vazio_por="busca_sem_resultado",
        )

    # O corte fica com as entregas de prazo MAIS RECENTE, e não com as
    # primeiras: a pergunta é da véspera, e entrega de março não é o que se
    # pergunta em setembro. A lista já vem ordenada por prazo crescente.
    truncado = len(escolhidas) > TETO_CONSULTAS
    cortadas = len(escolhidas) - TETO_CONSULTAS if truncado else 0
    if truncado:
        escolhidas = escolhidas[-TETO_CONSULTAS:]

    situacoes = []
    status_incompletos = 0
    for alvo_entrega in escolhidas:
        if not alvo_entrega.aceita_envio:
            # Sem ida ao Moodle: não há status a consultar, e "não entregou"
            # sobre uma prova presencial seria uma acusação falsa (J3).
            situacoes.append(Situacao(entrega=alvo_entrega, estado=_SEM_ENVIO))
            continue
        # Um erro do cliente sobe daqui sem ser capturado (J17): falha de
        # credencial não pode virar "você não entregou nada".
        bruto_status = cliente.chamar(
            "mod_assign_get_submission_status", assignid=alvo_entrega.assignid
        )
        # Acumulado por ENTREGA e não por item de aviso — ver `_aviso_do_status`.
        if _quantos_warnings(bruto_status):
            status_incompletos += 1
        situacoes.append(projetar_status(bruto_status, alvo_entrega))

    consultadas = sum(1 for s in situacoes if s.entrega.aceita_envio)
    linhas = [cabecalho, "", *(_formatar_linha(s, agora) for s in situacoes)]

    avisos = []
    if truncado:
        # Invariante 7: o corte é dito, com a contagem e com a cura.
        avisos.append(
            f"Esta consulta custa uma ida ao e-Disciplinas por entrega, e para "
            f"em {TETO_CONSULTAS}: {cortadas} entrega(s) de prazo mais antigo "
            "ficaram de fora. Use o parâmetro `entrega` para perguntar por uma "
            "delas pelo nome."
        )
    # As duas origens, em dois avisos. A ordem é a da leitura: primeiro o que
    # pode faltar na lista, depois o que pode estar errado dentro dela.
    if nao_listadas:
        avisos.append(_aviso_da_lista(nao_listadas))
    if status_incompletos:
        avisos.append(_aviso_do_status(status_incompletos))
    # Este ramo só existe quando há entrega listada, então a ressalva que sai é
    # a de presença. A de ausência sai nos dois ramos de vazio, acima.
    avisos.extend(emitir(_RESSALVAS, vazio=False))

    linhas.extend(f"\n⚠ {a}" for a in avisos)

    return RespostaJaEntreguei(
        texto="\n".join(linhas),
        total=len(todas),
        consultadas=consultadas,
        truncado=truncado,
    )
