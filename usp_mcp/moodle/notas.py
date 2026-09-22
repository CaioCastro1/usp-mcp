"""Nota: "como estou?" — e as duas visões que o e-Disciplinas tem dela.

**Uma ferramenta com parâmetro opcional, e não duas.** A decisão está no §9 de
14/09; o resumo é que o critério do §5 é a PERGUNTA, não a função da API. "Como
estou de nota?" e "como estou de nota em PTC3314?" são a mesma pergunta com e
sem escopo — quem pergunta a segunda depois da primeira não mudou de assunto,
estreitou. Duas ferramentas obrigariam o modelo a escolher entre `notas` e
`notas_da_disciplina` por uma diferença que é um parâmetro, e é assim que ele
chama a errada quando a frase é ambígua. O catálogo (§3.7) diz das duas funções
que "não competem, se complementam — a escolha é por pergunta"; aqui a escolha é
do código, à mão, e determinística:

| pergunta | função | o que ela dá |
|---|---|---|
| sem disciplina | `gradereport_overview_get_course_grades` | a nota final de cada matrícula, três campos por linha |
| com disciplina | `gradereport_user_get_grade_items` | item a item de UM curso, com a nota e o peso de cada um |

A Regra de Ouro (§3.1) fica de pé: uma função por invocação, escolhida à mão,
nunca as duas "para ter as duas visões" (N3).

**O que esta ferramenta NÃO diz, e por quê: de quanto era a nota.** Até 15/09/2026
o módulo montava um campo `maximo` a partir de `grademax` e o renderizador
imprimia "8,50 de 10,00" quando houvesse valor. Nunca houve: a captura real de
15/09 (`fixtures/moodle/grade_items_ptc3314.json`, 20 itens, 26 chaves
distintas) não traz `grademax` em item nenhum, nem com esse nome nem com outro.
Das três chaves que falam de nota, `graderaw`, `gradeformatted` e
`percentageformatted` dizem QUANTO se tirou; de quanto era, nenhuma diz. O
`.get` devolvia `None`, o campo nascia vazio e o `if` do renderizador comia a
falta em silêncio — a saída nunca mentiu, e foi por isso que o campo morto
sobreviveu a uma suíte verde. Ele saiu inteiro, com o texto que o prometia.

Derivar de `percentageformatted` sobre `graderaw` foi considerado e descartado:
duas casas decimais de percentual arredondado sobre uma nota arredondada devolvem
um máximo aproximado, e um "de 10,00" calculado é indistinguível de um recebido
para quem lê. Inferência apresentada como dado é o que o Invariante 6 proíbe.
F8, em `tests/moodle/test_forma_real.py`, é o que impede a chave de voltar.

**Os dois parâmetros que este módulo manda e a API não exige.** As duas funções
declaram `userid [opt=0]`, e `grade_items` declara `courseid [opt=0]` — o
Apêndice B do catálogo registra que **ninguém verificou** o que o 0 faz ali
("pode ser erro, pode ser todos os cursos e uma resposta gigante"). Uma
ferramenta que depende de um default não verificado promete o que não sabe. E há
um agravante no `grade_items`: a descrição do core é "a lista de itens de nota
para os usuários **de um curso**", então num token com capacidade de correção a
ausência de `userid` traz terceiros. O id derivado do token fecha as duas portas
e custa zero chamada — `disciplinas.carregar` já o buscou para resolver a sigla.

**Nota é dado pessoal (§3.3), e metade deste módulo é sobre o que não sai.**
`userfullname` e `useridnumber` (o número USP) vêm no payload e não respondem
nota nenhuma. O `feedback` — o comentário do professor em HTML — responde "o que
eu errei", que é outra pergunta, e é o campo gordo: descartado **com contagem**,
porque sumir com ele calado esconderia que existe comentário para ler
(Invariante 7). Bloco de nota de outro aluno, se aparecer, é ignorado e a saída
diz quantos foram.

Medido em 14/09 (forma documentada, valores sintéticos — a ressalva de
procedência está no §9): 5 itens de nota custam 5.161 B crus e saem em ~530 B de
texto; a visão geral das 74 matrículas custa 6.391 B crus e sai em ~350 B quando
três disciplinas têm nota lançada.
"""
from __future__ import annotations

from dataclasses import dataclass

from .disciplinas import carregar, resolver, userid_do_token
from .erros import ErroMoodle

# O que o Moodle devolve como "não tem nota" nas duas visões. String, não None:
# `grade` vem `"-"` já formatado para exibição.
_SEM_NOTA = ("", "-", None)

# `itemtype` do item que é a nota final da disciplina. Ele chega com `itemname`
# VAZIO, e sem rótulo vira a linha sem nome — logo a mais importante da lista.
_TOTAL_DO_CURSO = "course"


@dataclass(frozen=True)
class NotaDeCurso:
    """Uma linha da visão geral: a disciplina e a nota final dela."""

    sigla: str
    nota: str


@dataclass(frozen=True)
class ItemDeNota:
    """Uma linha da visão de uma disciplina."""

    nome: str
    nota: str
    peso: str
    oculta: bool = False
    total_do_curso: bool = False


@dataclass(frozen=True)
class RespostaNotas:
    texto: str
    total: int
    mostrados: int
    vazio_por: str | None = None


def _texto(valor) -> str:
    return "" if valor is None else str(valor)


def projetar_visao_geral(bruto, disciplinas) -> tuple[list[NotaDeCurso], int]:
    """`overview` → (linhas com nota, quantas matrículas ficaram sem nota).

    A tradução `courseid` → sigla é o que separa esta resposta de uma tabela de
    número contra número: `overview` devolve o id e a nota, e mais nada.
    `courseid` que não está nas matrículas conhecidas mantém o id como rótulo em
    vez de sumir — some seria o Invariante 7 quebrado num caso raro, que é onde
    ele costuma ser quebrado.

    `rank`/`maxrank` ficam de fora: a posição na turma é o desempenho dos
    OUTROS, e a pergunta é sobre o meu.
    """
    por_id = {d.courseid: d for d in disciplinas}
    linhas: list[NotaDeCurso] = []
    sem_nota = 0

    for grade in (bruto or {}).get("grades") or ():
        nota = _texto(grade.get("grade")).strip()
        if nota in _SEM_NOTA:
            sem_nota += 1
            continue
        disciplina = por_id.get(grade.get("courseid"))
        linhas.append(
            NotaDeCurso(
                sigla=disciplina.sigla if disciplina else f"curso {grade.get('courseid')}",
                nota=nota,
            )
        )

    return linhas, sem_nota


def projetar_itens(bruto, userid) -> tuple[list[ItemDeNota], int, int]:
    """`grade_items` → (itens, quantos têm comentário, blocos de terceiro ignorados).

    Das chaves por item sobram três — nome, nota e peso. A contagem exata da
    captura de 15/09/2026, conferida item a item: 26 chaves distintas, das quais
    23 vêm em todos os 20 itens, `cmid` em 17 e o par `weightraw`/`weightformatted`
    em 10. É por isso que o peso degrada em vez de ser exigido: metade dos itens
    desta disciplina não o traz, e item sem peso não é item quebrado.

    As descartadas não são gordura acidental: `cmid`, `iteminstance` e
    `categoryid` são endereçamento interno, e `percentageformatted` é a mesma
    nota em percentual — responde "quanto tirei" de novo, com outra unidade.

    Esta docstring já descreveu o descarte de `averageformatted` (a média da
    turma) e a origem de `percentageformatted` como `graderaw/grademax`. Nenhum
    dos dois campos existe na captura: era o mesmo erro que o cabeçalho de
    `tests/moodle/test_forma_real.py` registra ter custado caro em 14/09 — razão
    de projeção escrita contra um dicionário imaginado. Corrigido em 15/09 contra
    a captura, que é também de onde sai a contagem acima.
    """
    itens: list[ItemDeNota] = []
    com_comentario = 0
    de_terceiros = 0

    for bloco in (bruto or {}).get("usergrades") or ():
        if bloco.get("userid") != userid:
            # Só acontece com token que tem capacidade de correção, e o §7 do
            # catálogo registra que ninguém verificou se este tem. Ignorar é a
            # decisão; ignorar calado é o que o Invariante 7 proíbe.
            de_terceiros += 1
            continue
        for item in bloco.get("gradeitems") or ():
            if item.get("feedback"):
                com_comentario += 1
            oculta = bool(item.get("gradeishidden") or item.get("gradehiddenbydate"))
            nota = _texto(item.get("gradeformatted")).strip()
            total = item.get("itemtype") == _TOTAL_DO_CURSO
            itens.append(
                ItemDeNota(
                    nome=_texto(item.get("itemname")).strip()
                    or ("Total do curso" if total else "(item sem nome)"),
                    nota=nota,
                    peso=_texto(item.get("weightformatted")).strip(),
                    oculta=oculta,
                    total_do_curso=total,
                )
            )

    return itens, com_comentario, de_terceiros


def _avisos_de(bruto) -> list[str]:
    """`warnings` vira aviso em vez de sumir — mesma regra de `material`."""
    if quantos := len((bruto or {}).get("warnings") or ()):
        return [
            f"{quantos} item(ns) de nota não puderam ser lidos com esta "
            "credencial e não estão acima."
        ]
    return []


def _formatar_item(item: ItemDeNota) -> str:
    if item.oculta:
        # Invariante 6: "ainda não corrigiram" e "corrigiram e o professor não
        # liberou" têm curas diferentes, e a segunda não é perguntar amanhã.
        nota = "nota ocultada pelo professor"
    elif item.nota in _SEM_NOTA:
        nota = "sem nota lançada"
    else:
        # A nota, e só a nota. O "de 10,00" que esta linha já tentou montar
        # dependia de um `grademax` que a resposta não traz (ver o cabeçalho do
        # módulo): o `if` que o protegia nunca foi verdadeiro uma vez sequer, e
        # o que ele de fato fazia era esconder o campo morto.
        nota = item.nota
    linha = f"  {item.nome}: {nota}"
    if item.peso and item.peso not in _SEM_NOTA and not item.total_do_curso:
        linha += f" (peso {item.peso})"
    return linha


def notas(cliente, disciplina: str | None = None) -> RespostaNotas:
    """A pergunta, com ou sem escopo. Uma função de nota por invocação."""
    lista = carregar(cliente)
    # Derivado do token, nunca configurado. Cache quente: zero chamada nova.
    userid = userid_do_token(cliente)

    if disciplina:
        return _de_uma_disciplina(cliente, lista, disciplina, userid)
    return _de_todas(cliente, lista, userid)


def _de_todas(cliente, disciplinas, userid) -> RespostaNotas:
    bruto = cliente.chamar("gradereport_overview_get_course_grades", userid=userid)
    # Erro do cliente sobe daqui sem ser capturado (N17): credencial recusada
    # não pode virar "você não tem nota nenhuma".
    linhas, sem_nota = projetar_visao_geral(bruto, disciplinas)
    total = len(linhas) + sem_nota

    if not linhas:
        return RespostaNotas(
            texto=(
                "Nenhuma nota lançada ainda em nenhuma das suas "
                f"{total} matrículas no e-Disciplinas.\n\n⚠ Isto é o que o "
                "sistema respondeu, não uma falha de leitura: nota só aparece "
                "aqui depois que o professor a lança e a libera."
            ),
            total=total,
            mostrados=0,
            vazio_por="sem_nota_lancada",
        )

    partes = [
        f"Notas finais por disciplina ({len(linhas)} com nota lançada):",
        *(f"  {l.sigla}: {l.nota}" for l in sorted(linhas, key=lambda x: x.sigla)),
    ]

    avisos = []
    if sem_nota:
        # Invariante 7: o e-Disciplinas devolve as matrículas TODAS, e a maioria
        # do semestre em andamento ainda não tem nota. Listar 70 linhas de "-"
        # enterraria as que respondem; omitir calado mentiria sobre o total.
        avisos.append(
            f"{sem_nota} das {total} matrículas ainda não têm nota lançada e "
            "não aparecem acima — inclui semestres anteriores, porque o "
            "e-Disciplinas devolve todas as matrículas e não as deste semestre."
        )
    # A frase "esta é a nota FINAL; para ver item a item, pergunte de novo
    # dizendo a disciplina" saiu daqui em 22/09/2026. Ela não era ressalva, era
    # roteamento — e a descrição desta ferramenta já diz as duas metades, com
    # estas palavras: "Sem disciplina, dá a nota final de cada uma. Com
    # disciplina, abre item a item". A descrição está no contexto do cliente a
    # sessão inteira; repeti-la aqui era pagar a mesma frase duas vezes. Nenhuma
    # ressalva invariável sobrou nesta ferramenta, e por isso ela não importa
    # `ressalvas.py`: o que sai daqui para baixo depende todo do dado.
    avisos.extend(_avisos_de(bruto))

    partes.extend(f"\n⚠ {a}" for a in avisos)
    return RespostaNotas(texto="\n".join(partes), total=total, mostrados=len(linhas))


def _de_uma_disciplina(cliente, disciplinas, disciplina, userid) -> RespostaNotas:
    resolucao = resolver(disciplinas, disciplina)
    if resolucao.disciplina is None:
        # Sem gastar chamada de nota: consultar o Moodle para descobrir que a
        # pergunta estava errada é gastar chamada da conta do dono à toa.
        raise ErroMoodle(resolucao.motivo)

    alvo = resolucao.disciplina
    bruto = cliente.chamar(
        "gradereport_user_get_grade_items", courseid=alvo.courseid, userid=userid
    )
    itens, com_comentario, de_terceiros = projetar_itens(bruto, userid)
    cabecalho = f"{alvo.sigla} ({alvo.rotulo}) — suas notas"

    if not itens:
        return RespostaNotas(
            texto=(
                f"{cabecalho}\n\nEsta disciplina não tem nenhum item de nota "
                "criado no e-Disciplinas.\n\n⚠ Isto não quer dizer que não há "
                "avaliação: prova corrigida no papel e nota que o professor não "
                "lança no sistema não existem aqui."
            ),
            total=0,
            mostrados=0,
            vazio_por="sem_item_de_nota",
        )

    # O total do curso é a linha que se procura primeiro, e por isso vai por
    # último: é onde o olho para depois de ler os itens que a compõem.
    ordenados = sorted(itens, key=lambda i: i.total_do_curso)
    partes = [cabecalho, "", *(_formatar_item(i) for i in ordenados)]

    avisos = []
    if com_comentario:
        # Descartar o comentário é decisão de projeção; descartar calado faria a
        # ferramenta esconder que existe texto do professor para ler.
        avisos.append(
            f"{com_comentario} item(ns) têm comentário escrito pelo professor. "
            "O texto não sai aqui: ele responde 'o que eu errei', que é outra "
            "pergunta, e é a parte cara da resposta. Ele está na página da "
            "disciplina no e-Disciplinas."
        )
    if de_terceiros:
        avisos.append(
            f"{de_terceiros} bloco(s) de nota de OUTRO aluno vieram nesta "
            "resposta e foram ignorados — esta ferramenta só mostra as suas."
        )
    avisos.extend(_avisos_de(bruto))

    partes.extend(f"\n⚠ {a}" for a in avisos)
    return RespostaNotas(
        texto="\n".join(partes), total=len(itens), mostrados=len(itens)
    )
