"""O ponteiro: "mudou alguma coisa em PTC3314 desde ontem?".

`core_course_get_updates_since` é a chamada mais barata do projeto — ~100 tokens
para 7 dias (catálogo §3.3) — e devolve **ponteiro, não conteúdo**: diz qual
`cmid` mudou e em quê (`discussions`, `contentfiles`, `submissions`,
`configuration`), e nada além disso. As duas decisões deste módulo saem daí.

## Decisão 1: a janela é por DIAS, e não um carimbo explícito

O parâmetro do Moodle é `since`, um epoch. A alternativa óbvia era expor esse
epoch — "o que mudou desde 1788900000" — e ela foi recusada por três razões, em
ordem de peso:

1. **Quem escolhe o valor é um modelo.** Epoch calculado por modelo erra, e erra
   para o lado invisível: um ano trocado põe `since` no futuro e a resposta volta
   vazia, dizendo "nada mudou". Esse é o falso vazio que o §9 de 28/08 registra
   como o modo de falha mais caro do projeto — ninguém estranha "nada mudou". A
   janela por dias não tem como produzir isso: `dias` é um inteiro pequeno, o
   código faz a aritmética, e `dias <= 0` é recusado com erro legível (M9).
2. **Duas grafias da mesma ideia no mesmo servidor.** `o_que_vence` já fala
   `dias`, e as duas ferramentas respondem a mesma noite. É o argumento do J18
   uma camada acima: quem lê as duas respostas precisa reconhecer que a janela é
   a mesma janela.
3. **A janela por extenso cabe na resposta; um epoch, não.** A saída diz "nos
   últimos 2 dias (desde sex 12/09 16:00)" — tem o número que o humano entende e
   o instante que a próxima pergunta precisa para encaixar.

O que a decisão custa: não dá para dizer "desde a última vez que olhei". A cura
é o instante exato impresso na saída (M7), que é a informação que o carimbo daria
de graça.

## Decisão 2: a tradução `cmid` → nome, e por que ela é condicional

O ponteiro sozinho não é resposta em português: *"o módulo 6372306 mudou os
arquivos"* não responde nada. Quem sabe o nome é `core_course_get_contents`, que
**já está na allowlist** desde 31/08 — nenhuma função nova é necessária para
isto. Mas ela é a chamada CARA: ~14.500 tokens crus por disciplina, contra ~100
do ponteiro.

Por isso ela só acontece **quando há mudança** (M3). O caso comum de "mudou
alguma coisa?" é *não*, e nesse caso a ferramenta custa uma chamada barata e
pronto. O custo do `get_contents` é de transporte e de latência, não de contexto:
dele sobram dois campos por módulo — nome e tipo —, que é a mesma economia que
`projecao.py` existe para fazer.

`cmid` que a tradução não acha **não some** (M5): `get_contents` esconde módulo
que o aluno não pode ver, e sumir com a linha faria a resposta jurar que nada
mais mudou. Sai com o número e com o motivo.

## O que esta ferramenta não sabe, e diz

Ela diz **que** mudou, nunca **o que** mudou. "Arquivo novo ou trocado" não
carrega qual arquivo é — quem responde isso é `material`; "tópico novo no fórum"
não carrega o que foi dito — quem responde é `avisos`. Sem essa frase na saída,
um modelo lê o ponteiro como se fosse o conteúdo (M15).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .disciplinas import carregar, resolver
from .erros import ErroMoodle
from .projecao import FUSO_SAO_PAULO
from .ressalvas import PRESENCA, Ressalva, emitir
from .texto import formatar_data

# Uma semana. "Mudou alguma coisa?" sem janela dita é a pergunta da semana, e o
# valor é declarado no `inputSchema` que o modelo lê e repetido no texto da
# resposta — janela que só existe no código é janela que quem lê não confere.
DIAS_PADRAO = 7

# Quantos módulos entram no texto. O ponteiro é barato e pode vir largo: uma
# reorganização de disciplina mexe em tudo de uma vez, e 60 linhas de
# "mudou a configuração" enterrariam o tópico novo do fórum.
TETO_MODULOS = 20

# O `name` de cada mudança, no vocabulário de quem pergunta. Os nomes vêm do
# core; um fora desta lista sai CRU, pela mesma regra do `modulename` de
# `o_que_vence` — rótulo desconhecido é melhor que rótulo inventado.
_MUDANCAS_PT = {
    "configuration": "mudou a configuração ou o nome",
    "contentfiles": "arquivo novo ou trocado",
    "fileareas": "arquivo novo ou trocado",
    "introfiles": "arquivo do enunciado novo ou trocado",
    "discussions": "tópico novo no fórum",
    "posts": "resposta nova no fórum",
    "submissions": "a sua entrega mudou",
    "gradeitems": "item de nota mexido",
    "grades": "nota lançada ou alterada",
    "attempts": "tentativa de questionário registrada",
    "comments": "comentário novo",
    "completion": "marca de conclusão mudou",
    "outcomes": "competência mexida",
    "ratings": "avaliação nova",
    "entries": "entrada nova",
    "pages": "página nova ou alterada",
}

# `modname` do módulo, para quem lê saber de que tipo de coisa se trata. Mesmo
# vocabulário de `o_que_vence`, ampliado: lá só tarefa e questionário aparecem,
# porque só elas geram evento de calendário.
_MODULOS_PT = {
    "assign": "tarefa",
    "quiz": "questionário",
    "forum": "fórum",
    "resource": "arquivo",
    "url": "link",
    "folder": "pasta",
    "page": "página",
    "label": "texto da página da disciplina",
    "choicegroup": "escolha de grupo",
}

# `contextlevel` que não é `module`: a própria disciplina mexeu (seção nova,
# nome trocado). Procurar um `cmid` que é id de curso não acharia nada e
# rotularia de "não identificado" uma mudança que tem nome (M14).
_CONTEXTO_MODULO = "module"


@dataclass(frozen=True)
class Mudanca:
    """Um módulo que mexeu, e em quê. É a projeção inteira."""

    cmid: int
    nome: str
    tipo: str
    o_que: tuple[str, ...]
    quando: datetime | None
    identificado: bool = True


@dataclass(frozen=True)
class RespostaOQueMudou:
    texto: str
    total: int
    mostrados: int
    truncado: bool
    sem_nome: int = 0
    vazio_por: str | None = None


def _data(carimbo) -> datetime | None:
    """Mesma regra das irmãs: epoch 0 é "sem data", nunca 01/01/1970."""
    if isinstance(carimbo, bool) or not isinstance(carimbo, int) or carimbo <= 0:
        return None
    return datetime.fromtimestamp(carimbo, FUSO_SAO_PAULO)


def indexar_modulos(bruto) -> dict[int, tuple[str, str]]:
    """`core_course_get_contents` → `{cmid: (nome, modname)}`.

    Dois campos por módulo, de umas 20. Tudo o mais da resposta mais gorda do
    Moodle fica de fora — `contents` com as `fileurl`, `description` em HTML,
    `dates`, `completiondata`. A `fileurl` em especial não pode vazar para cá
    (Invariante 3, M18): quem entrega arquivo é `baixar_arquivo`.
    """
    indice: dict[int, tuple[str, str]] = {}
    for secao in bruto or ():
        for modulo in secao.get("modules") or ():
            cmid = modulo.get("id")
            if isinstance(cmid, int) and not isinstance(cmid, bool):
                indice[cmid] = (
                    (modulo.get("name") or "").strip(),
                    modulo.get("modname") or "",
                )
    return indice


def projetar_mudancas(bruto, indice, courseid) -> tuple[Mudanca, ...]:
    """`core_course_get_updates_since` + o índice → as linhas da resposta.

    Ordenado pelo carimbo mais recente de cada módulo, decrescente: quem pergunta
    "o que mudou desde ontem" quer o topo da pilha.
    """
    mudancas: list[Mudanca] = []

    for inst in (bruto or {}).get("instances") or ():
        alvo = inst.get("id")
        tipos = []
        carimbos = []
        for u in inst.get("updates") or ():
            nome = u.get("name") or ""
            # `.get(nome) or nome` e não `.get(nome, nome)`: um nome conhecido
            # que mapeasse para string vazia cairia no dicionário e sumiria.
            tipos.append(_MUDANCAS_PT.get(nome) or nome or "mudou alguma coisa")
            if (quando := _data(u.get("timeupdated"))) is not None:
                carimbos.append(quando)

        if inst.get("contextlevel") != _CONTEXTO_MODULO:
            mudancas.append(
                Mudanca(
                    cmid=alvo if isinstance(alvo, int) else courseid,
                    nome="a própria disciplina",
                    tipo="",
                    o_que=tuple(dict.fromkeys(tipos)),
                    quando=max(carimbos, default=None),
                )
            )
            continue

        nome, modname = indice.get(alvo, ("", ""))
        mudancas.append(
            Mudanca(
                cmid=alvo if isinstance(alvo, int) else 0,
                nome=nome or f"módulo {alvo}",
                tipo=_MODULOS_PT.get(modname) or modname,
                # `dict.fromkeys` preserva a ordem e tira repetido: o mesmo tipo
                # pode vir duas vezes quando duas áreas de arquivo mexem.
                o_que=tuple(dict.fromkeys(tipos)),
                quando=max(carimbos, default=None),
                identificado=bool(nome),
            )
        )

    return tuple(
        sorted(
            mudancas,
            key=lambda m: m.quando or datetime.min.replace(tzinfo=FUSO_SAO_PAULO),
            reverse=True,
        )
    )


# A segunda metade desta frase — "para ver o arquivo use `material`, para ler o
# fórum `avisos`, para prazo `o_que_vence`" — saiu em 22/09/2026: é roteamento, e
# a descrição desta ferramenta já o diz com as mesmas palavras (sobreposição
# medida: 100%). Ficou a metade que é ressalva de verdade, e que a descrição não
# diz: que o e-Disciplinas responde esta pergunta com um ponteiro.
_SO_PONTEIRO = (
    "Isto diz QUE mudou, nunca O QUE mudou: o e-Disciplinas responde esta "
    "pergunta com um ponteiro, não com o conteúdo."
)

# Uma ressalva só, e de presença: ela existe para impedir a leitura "isto me
# conta o que mudou" de uma lista cheia de ponteiros. Na resposta vazia não há
# ponteiro nenhum para confundir com conteúdo, e até 22/09/2026 ela saía lá
# também — 245 tokens para avisar sobre uma lista que não existe.
_RESSALVAS = (Ressalva(texto=_SO_PONTEIRO, quando=PRESENCA),)


def _formatar_linha(m: Mudanca) -> str:
    quando = formatar_data(m.quando) if m.quando is not None else "sem data"
    rotulo = f"{m.nome} ({m.tipo})" if m.tipo else m.nome
    linha = f"{quando}  {rotulo}: {', '.join(m.o_que)}"
    if not m.identificado:
        # Invariante 7: a linha fica, e diz por que está sem nome. Sumir com ela
        # faria a resposta jurar que nada mais mudou.
        linha += (
            " — este módulo não deu para identificar: ele mudou e não aparece "
            "na lista de conteúdo desta disciplina"
        )
    return linha


def o_que_mudou(
    cliente, disciplina: str, dias: int = DIAS_PADRAO, agora=None
) -> RespostaOQueMudou:
    """Uma disciplina, uma chamada barata — e a cara só se houver o que traduzir.

    `agora` é o instante da pergunta (um `datetime`), e não o relógio do cache de
    `disciplinas` (`time.monotonic`). São coisas diferentes com o mesmo nome em
    dois módulos vizinhos, então nada é encaminhado — a mesma armadilha está
    anotada em `ja_entreguei`.
    """
    agora = agora if agora is not None else datetime.now(FUSO_SAO_PAULO)

    if not isinstance(dias, int) or isinstance(dias, bool) or dias < 1:
        # Antes de qualquer chamada. `dias=0` faz `since` ser agora e a resposta
        # volta vazia por construção; negativo põe `since` no futuro. Os dois
        # saem como "nada mudou", que é verdade, é inútil, e ninguém estranha —
        # exatamente o falso vazio que o Invariante 6 proíbe.
        raise ErroMoodle(
            f"A janela pedida foi de {dias} dias, e ela precisa ser de pelo "
            "menos 1: com zero ou menos, o e-Disciplinas responderia 'nada "
            "mudou' por construção, e essa resposta é indistinguível de uma "
            "disciplina parada. Peça de novo com um número de dias positivo."
        )

    lista = carregar(cliente)
    resolucao = resolver(lista, disciplina)
    if resolucao.disciplina is None:
        raise ErroMoodle(resolucao.motivo)

    alvo = resolucao.disciplina
    desde = agora - timedelta(days=dias)
    # `filter` NÃO é enviado (M17): ele é `[opt=[]]` e o vazio significa TODOS os
    # tipos, que é o documentado e é o que queremos. Escolher tipos aqui seria
    # decidir por quem pergunta o que conta como mudança.
    bruto = cliente.chamar(
        "core_course_get_updates_since",
        courseid=alvo.courseid,
        since=int(desde.timestamp()),
    )
    # Erro do cliente sobe daqui sem ser capturado (M12), e aqui isso pesa mais
    # que nas irmãs: "nada mudou" é uma resposta que quem lê aceita sem
    # estranhar, então uma falha engolida nunca seria descoberta.

    # "nos últimos 1 dias" é o tipo de frase que faz quem lê desconfiar do
    # resto da resposta. O singular custa uma linha.
    quanto = "no último dia" if dias == 1 else f"nos últimos {dias} dias"
    janela = f"{quanto} (desde {formatar_data(desde)})"
    cabecalho = f"{alvo.sigla} ({alvo.rotulo}) — o que mudou {janela}"
    avisos_da_api = len((bruto or {}).get("warnings") or ())

    if not (bruto or {}).get("instances"):
        # A chamada CARA não acontece: traduzir uma lista vazia pagaria ~14.500
        # tokens para dizer o que os ~100 já disseram (M3).
        partes = [f"{cabecalho}\n\nNada mudou nesta disciplina {janela}."]
        if avisos_da_api:
            # Este é o aviso que mais importa desta ferramenta: "nada mudou" com
            # uma atividade não verificada é meia resposta com cara de inteira.
            partes.append(
                f"{avisos_da_api} atividade(s) não puderam ser verificadas com "
                "esta credencial, então este 'nada mudou' não cobre todas."
            )
        partes.extend(emitir(_RESSALVAS, vazio=True))
        return RespostaOQueMudou(
            texto="\n".join([partes[0], *(f"\n⚠ {a}" for a in partes[1:])]),
            total=0,
            mostrados=0,
            truncado=False,
            vazio_por="sem_mudanca",
        )

    indice = indexar_modulos(cliente.chamar("core_course_get_contents", courseid=alvo.courseid))
    mudancas = projetar_mudancas(bruto, indice, alvo.courseid)

    truncado = len(mudancas) > TETO_MODULOS
    de_fora = len(mudancas) - TETO_MODULOS if truncado else 0
    mostradas = mudancas[:TETO_MODULOS]
    sem_nome = sum(1 for m in mostradas if not m.identificado)

    partes = [cabecalho, "", *(_formatar_linha(m) for m in mostradas)]

    lista_avisos = []
    if truncado:
        lista_avisos.append(
            f"{de_fora} mudança(s) mais antigas ficaram de fora: a resposta "
            f"para em {TETO_MODULOS} itens. Peça de novo com menos dias para "
            "ver menos coisa de uma vez."
        )
    if avisos_da_api:
        lista_avisos.append(
            f"{avisos_da_api} atividade(s) não puderam ser verificadas com esta "
            "credencial e não estão acima."
        )
    lista_avisos.extend(emitir(_RESSALVAS, vazio=False))

    partes.extend(f"\n⚠ {a}" for a in lista_avisos)

    return RespostaOQueMudou(
        texto="\n".join(partes),
        total=len(mudancas),
        mostrados=len(mostradas),
        truncado=truncado,
        sem_nome=sem_nome,
    )
