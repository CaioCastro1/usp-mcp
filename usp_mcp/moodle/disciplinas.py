"""As suas matrículas: a resolução sigla → `courseid`, e a ferramenta que as mostra.

Este módulo nasceu só como tradutor — o modelo recebe "PSI3323" e o Moodle só
entende `courseid` — e ganhou a ferramenta `disciplinas` em 14/09/2026, na mesma
casa e de propósito: **a lista que responde "quais matérias eu tenho?" é a mesma
que `carregar` já busca e já cacheia para resolver sigla.** Nenhuma função nova
entrou na allowlist por causa dela, e a segunda pergunta não gasta chamada
nenhuma. Separá-la em outro módulo teria criado um segundo caminho para a mesma
lista, que é como um cache vira dois caches que discordam.

Antes dela, o único jeito de alguém ver as próprias siglas era **provocar um
erro**: pedir `material` de uma sigla que não existe e ler a lista que o
Invariante 7 faz `resolver` cuspir no motivo. Funcionava, e é constrangedor.

A tradução é a razão de a fatia de material custar três funções e não uma, e
vale registrar o preço medido, porque ele é o que justifica o cache:

| | cru | projetado |
|---|---|---|
| `core_enrol_get_users_courses` | 104.712 B (~26.178 tokens) | 7.816 B para as 74 |

Buscar 104 kB toda vez que alguém pergunta "o que tem em PSI3323" é reconfirmar
a cada pergunta um dado que muda **uma vez por semestre**. O Invariante 5 pede
TTL colado na taxa de mudança do dado, não na frequência da pergunta — daí
`TTL_DISCIPLINAS`.

O `userid` é derivado do token, nunca configurado: §9 de 28/08 mediu que
`get_users_courses` com userid errado devolve `[]` com HTTP 200, que é a falha
silenciosa que o Invariante 6 proíbe. O modo perigoso é o valor errado, não o
ausente — por isso não há como passá-lo à mão por aqui.

**A decisão de desenho da ferramenta está em `minhas_disciplinas`**, no fim do
arquivo: o que fazer com as dezenas de matrículas de semestre passado que a
resposta traz junto com as do semestre corrente.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime

from .erros import ErroMoodle
from .projecao import FUSO_SAO_PAULO, data_de
from .texto import normalizar as _normalizar

# Um semestre. Matrícula não muda entre duas perguntas sobre material.
TTL_DISCIPLINAS = 60 * 60 * 24 * 120

# `shortname` no e-Disciplinas é "SIGLA<separador>ano[<separador>turma]", e o
# separador NÃO é só o hífen. Medido em 15/09/2026 nas duas capturas desta
# conta: em 74 matrículas aparecem `-` (69), `_` (2), espaço (1), `.` (1) e
# nenhum separador (1) — `PSI3323-2026` e `PRO3811-202-2026` ao lado de
# `PEA3301_2026_1sem`, `PSI3211 2025`, `2166.2023i` e `PCS3335`.
#
# Cortar só no hífen custou caro e não em teoria: `PEA3301_2026_1sem` (o
# semestre corrente) virava a sigla `PEA330120261SEM` enquanto `PEA3301-2021`
# ficava com `PEA3301` sozinha. Perguntar por "PEA3301" tinha UMA candidata, e
# `material` respondia com 177 itens sobre a de 2021 — sem ambiguidade nenhuma
# para detectar, porque do ponto de vista da resolução não havia.
_SEPARADOR = re.compile(r"[\W_]+")


@dataclass(frozen=True)
class Disciplina:
    """`inicio` e `fim` entraram em 14/09 com a ferramenta, e são os dois únicos
    campos que a projeção guarda sem precisar para resolver sigla.

    Custam ~16 B por matrícula e são o que permite responder "quais matérias eu
    tenho AGORA" sem uma segunda chamada: sem eles a única saída seria adivinhar
    o semestre pelo sufixo do `shortname`, e o `shortname` real tem 23 formatos
    diferentes nesta conta (de `PSI3323-2026` a `AEX-IF-00020.01`).

    Ausentes por default porque `enddate: 0` existe de verdade na resposta do
    e-Disciplinas — e "não declarado" não é "encerrada" (DI7).
    """

    courseid: int
    sigla: str
    rotulo: str
    nome: str
    inicio: datetime | None = None
    fim: datetime | None = None


@dataclass(frozen=True)
class Resolucao:
    """Três desfechos, e nenhum deles é lista vazia sem explicação.

    `disciplina` preenchida quando resolveu; `candidatas` quando o termo casou
    com mais de uma e escolher seria errar calado; `motivo` sempre que não
    resolveu, dizendo o que foi pedido e o que existe (Invariante 6).
    """
    disciplina: Disciplina | None
    candidatas: tuple[Disciplina, ...] = ()
    motivo: str | None = None


def sigla_de(rotulo: str) -> str:
    """O primeiro pedaço alfanumérico do rótulo. "PTC3314-2026" -> "PTC3314".

    Deliberadamente **sem forma**: não há aqui nenhum "três letras e quatro
    dígitos". A convenção da USP não é a de outras instituições, e o que se pode
    afirmar dos dois lados é só que a sigla, quando existe, vem primeiro. Cortar
    no primeiro separador é uma regra que a USP satisfaz por construção e que
    não inventa nada sobre quem não a segue.

    O limite fica declarado no lugar certo: onde o primeiro pedaço NÃO é a sigla
    ("2026S2-BIO-101" devolve "2026S2"), não há corte que conserte — quem acha a
    disciplina é a busca pelo rótulo, em `resolver`.
    """
    for pedaco in _SEPARADOR.split(rotulo or ""):
        if sigla := _normalizar(pedaco):
            return sigla
    return ""


def projetar_disciplinas(bruto) -> list[Disciplina]:
    """29 chaves por disciplina viram 5. As outras 24 não respondem nada daqui.

    `summary`, `courseimage`, `overviewfiles` e `progress` respondem por quase
    todo o payload e por nada da pergunta. `courseimage` é ainda uma URL de
    `pluginfile.php`, a família de endereço que o Invariante 3 mantém fora de
    toda resposta deste servidor.
    """
    lista = []
    for curso in bruto or ():
        rotulo = curso.get("shortname") or ""
        lista.append(
            Disciplina(
                courseid=curso.get("id"),
                sigla=sigla_de(rotulo),
                rotulo=rotulo,
                nome=curso.get("fullname") or "",
                inicio=data_de(curso.get("startdate")),
                fim=data_de(curso.get("enddate")),
            )
        )
    return lista


def _dia(quando: datetime | None) -> str:
    """"03/08/2026" — e o ANO aqui não é excesso.

    `texto.formatar_data` escreve prazo ("dom 06/09 23:59") e omite o ano de
    propósito, porque prazo é de agora. Isto é vigência de matrícula, e uma
    lista que cobre sete anos sem o ano não localiza nada: PMT3100 de 2023 e
    PMT3100 de 2024 ficariam idênticas. São grafias diferentes porque são
    coisas diferentes — J18 pede uma grafia só para a MESMA coisa.

    Mora acima de `resolver` desde 15/09/2026 porque passou a ter dois leitores:
    a lista da ferramenta e a lista de candidatas de uma ambiguidade. É o mesmo
    período nos dois lugares, e J18 pede a mesma grafia para a mesma coisa.
    """
    return quando.strftime("%d/%m/%Y") if quando is not None else "?"


def _periodo(disciplina: Disciplina) -> str:
    return f"{_dia(disciplina.inicio)} a {_dia(disciplina.fim)}"


def _rotulo_com_periodo(disciplina: Disciplina) -> str:
    """O rótulo, e a vigência entre parênteses quando o Moodle declarou alguma.

    Sem data nenhuma o parêntese sairia "(? a ?)", que ocupa espaço para dizer
    que não sabe — e numa lista de desempate é justamente o ruído que atrapalha
    quem está tentando distinguir duas matrículas.
    """
    if disciplina.inicio is None and disciplina.fim is None:
        return disciplina.rotulo
    return f"{disciplina.rotulo} ({_periodo(disciplina)})"


# Uma matrícula sem vigência declarada não ganha nem a frente nem o fim da fila
# por acidente: ela vai para o fim, onde "não sei quando foi" pertence.
_SEM_VIGENCIA = datetime.min.replace(tzinfo=FUSO_SAO_PAULO)


def _mais_recentes_primeiro(disciplinas):
    """As candidatas ordenadas pela vigência, a mais recente na frente.

    Ordenar é informação; escolher é decisão. Esta função faz a primeira e não
    encosta na segunda — quem lê a lista encontra a matrícula do semestre
    corrente onde o olho cai primeiro, e continua sendo quem escolhe.
    """
    por_rotulo = sorted(disciplinas, key=lambda d: d.rotulo)
    return sorted(
        por_rotulo,
        key=lambda d: d.fim or d.inicio or _SEM_VIGENCIA,
        reverse=True,
    )


def resolver(disciplinas, termo: str) -> Resolucao:
    """Identificador exato primeiro; depois pedaço do rótulo ou do nome.

    A ordem importa, e importa mais desde que o rótulo entrou na busca: com
    match parcial primeiro, "PTC3312" casaria consigo mesma e com qualquer
    PTC3312-XXX, virando ambiguidade onde havia resposta. O mesmo vale um nível
    abaixo — "PCS3110-2S" é o rótulo INTEIRO de uma matrícula e pedaço do rótulo
    de outra, e é por isso que rótulo exato entra no primeiro degrau ao lado da
    sigla, e não junto do casamento por pedaço.

    O rótulo entrou porque ele é o que a ferramenta `disciplinas` imprime na
    tela, e copiá-lo de volta não achava nada: medido em 15/09/2026, 69 dos 74
    rótulos desta conta não resolviam quando digitados inteiros. É também o que
    torna a disciplina alcançável onde a sigla não é o primeiro pedaço do rótulo
    (`2026S2-BIO-101` procurado como "BIO101").

    Não há degrau para "começo de sigla": ele virou caso particular do pedaço de
    rótulo. A sigla é, por construção, o primeiro pedaço do rótulo, então toda
    sigla que começa com o termo tem o termo dentro do rótulo.
    """
    alvo = _normalizar(termo)
    if not alvo:
        return Resolucao(None, motivo="Nenhuma disciplina informada.")

    exatas = [
        d for d in disciplinas
        if d.sigla == alvo or _normalizar(d.rotulo) == alvo
    ]
    if len(exatas) == 1:
        return Resolucao(exatas[0])
    parciais = exatas or [
        d for d in disciplinas
        if alvo in _normalizar(d.rotulo) or alvo in _normalizar(d.nome)
    ]

    if len(parciais) == 1:
        return Resolucao(parciais[0])

    if parciais:
        # Invariante 6: escolher uma entre várias é errar calado. O motivo lista
        # as candidatas porque "ambíguo" sozinho não diz a quem lê o que fazer.
        #
        # Desempatar pela data — "ela quis dizer a do semestre corrente" — foi
        # recusado, e a recusa é o miolo desta correção: o defeito que ela
        # conserta ERA uma escolha calada, e trocá-la por outra só mudaria de
        # quem é a pergunta que passa a ser respondida errado. Além disso as
        # datas daqui são as do espaço da disciplina e não as da matrícula
        # oficial (trancamento não chega, e `enddate: 0` existe de verdade):
        # desempatar por elas seria construir resposta confiante sobre um dado
        # que este módulo já declara incerto. Ordena, mostra o período, e
        # devolve a escolha.
        candidatas = _mais_recentes_primeiro(parciais)
        vistos, rotulos = set(), []
        for d in candidatas:
            if d.rotulo not in vistos:
                vistos.add(d.rotulo)
                rotulos.append(_rotulo_com_periodo(d))
        return Resolucao(
            None,
            candidatas=tuple(candidatas),
            motivo=(
                f"{termo!r} casa com mais de uma disciplina: {'; '.join(rotulos)}. "
                "Repita com o rótulo inteiro — é ele que distingue duas "
                "matrículas da mesma sigla."
            ),
        )

    # Invariante 7: "não achei" nunca sai como lista vazia muda. Listar o que
    # existe é o que separa "errei a sigla" de "não estou matriculado".
    siglas = ", ".join(sorted({d.sigla for d in disciplinas if d.sigla}))
    return Resolucao(
        None,
        motivo=(
            f"Não encontrei disciplina para {termo!r} entre as suas matrículas "
            f"no e-Disciplinas. Siglas disponíveis: {siglas}."
        ),
    )


class _Cache:
    """Cache de processo com relógio injetável.

    Injetável para que o teste verifique a REGRA (busca de novo depois do TTL) e
    não o valor da constante — se o teste dependesse do valor, mudar o TTL viraria
    mudar o teste, e o teste deixaria de proteger.
    """

    def __init__(self) -> None:
        self.disciplinas: list[Disciplina] | None = None
        self.userid: int | None = None
        self.carregado_em: float = 0.0

    def valido(self, agora: float) -> bool:
        return (
            self.disciplinas is not None
            and 0 <= agora - self.carregado_em < TTL_DISCIPLINAS
        )


_cache = _Cache()


def limpar_cache() -> None:
    """Descarta o cache. Existe para o teste, e é dele que o teste depende para
    não herdar o estado do vizinho — cache de processo compartilhado entre casos
    produz verde que nunca chamou nada."""
    global _cache
    _cache = _Cache()


def carregar(cliente, agora=None) -> list[Disciplina]:
    """As disciplinas do dono, do cache ou do Moodle. Duas chamadas na primeira vez.

    `core_webservice_get_site_info` só existe aqui para derivar o `userid` —
    §9 de 28/08 — e o valor derivado é o que viaja no parâmetro, nunca um
    configurado à mão.
    """
    relogio = agora if agora is not None else time.monotonic
    momento = relogio()

    if _cache.valido(momento):
        return _cache.disciplinas

    info = cliente.chamar("core_webservice_get_site_info")
    userid = info.get("userid") if isinstance(info, dict) else None
    if not userid:
        raise ErroMoodle(
            "O e-Disciplinas não devolveu o `userid` do token em "
            "`core_webservice_get_site_info`. Sem ele não dá para listar as "
            "disciplinas, e chutar um valor devolveria lista vazia com cara de "
            "'você não tem matrícula'."
        )

    bruto = cliente.chamar("core_enrol_get_users_courses", userid=userid)
    _cache.disciplinas = projetar_disciplinas(bruto)
    _cache.userid = userid
    _cache.carregado_em = momento
    return _cache.disciplinas


def userid_do_token(cliente, agora=None) -> int:
    """O `userid` que o token derivou, sem gastar uma chamada a mais.

    Ele já é buscado aqui — `carregar` precisa dele para pedir as matrículas — e
    ficava jogado fora. Quem passou a precisar dele foi `notas` (14/09): as duas
    funções de `gradereport_` têm `userid [opt=0]`, e o catálogo registra que o
    que o 0 faz **não foi verificado**. Mandar o id explícito troca um default
    desconhecido por um valor derivado do próprio token.

    Não existe caminho para passá-lo à mão, pelo mesmo motivo de sempre: §9 de
    28/08 mediu que userid ERRADO devolve `[]` com HTTP 200. O modo perigoso é o
    valor errado, não o ausente.
    """
    carregar(cliente, agora=agora)
    return _cache.userid


# --------------------------------------------------------------------------
# A ferramenta `disciplinas`: "quais matérias eu tenho?"
#
# Ela mora aqui, e não num módulo próprio, porque a lista que responde a
# pergunta é a MESMA que `carregar` cacheia para resolver sigla. Um módulo
# separado teria de ou reimportar `carregar` (e então este comentário estaria lá
# em vez de aqui) ou abrir um segundo caminho até `core_enrol_get_users_courses`
# — que é como um cache vira dois caches que discordam.
# --------------------------------------------------------------------------

EM_ANDAMENTO = "em andamento"
A_COMECAR = "a começar"
ENCERRADA = "encerrada"
SEM_PERIODO = "sem período"


@dataclass(frozen=True)
class RespostaDisciplinas:
    """Saída da ferramenta. As contagens saem daqui e não do texto porque quem
    chama (a fronteira MCP, e o teste) não deveria ter de reabrir a prosa para
    saber quantas matrículas foram resumidas."""

    texto: str
    total: int
    em_andamento: int
    encerradas: int
    sem_periodo: int
    vazio_por: str | None = None


def situacao_de(disciplina: Disciplina, momento: datetime) -> str:
    """Em que pé está uma matrícula, pelas datas que o e-Disciplinas declara.

    Quatro desfechos e não dois, e os dois extras não são zelo:

    - `enddate: 0` chega na resposta real (duas das 74 matrículas da fixture),
      e chamar isso de encerrada seria inventar um fato sobre a vida acadêmica
      de quem pergunta. "Não declarado" vira bloco próprio (DI7).
    - matrícula para o semestre que vem existe antes de o semestre começar, e
      ela não está em andamento nem encerrada (DI15).
    """
    if disciplina.fim is None:
        return SEM_PERIODO
    if disciplina.fim <= momento:
        return ENCERRADA
    if disciplina.inicio is not None and disciplina.inicio > momento:
        return A_COMECAR
    return EM_ANDAMENTO


def _linha_completa(disciplina: Disciplina) -> str:
    # Sigla primeiro porque é ela que se digita na próxima pergunta; o rótulo
    # ao lado porque é ele que desambigua duas matrículas da mesma sigla.
    nome = f" — {disciplina.nome}" if disciplina.nome else ""
    return f"  {disciplina.sigla} ({disciplina.rotulo}){nome} — {_periodo(disciplina)}"


def _bloco_compacto(disciplinas) -> list[str]:
    """As encerradas, como CONTAGEM por ano em que terminaram.

    **Até 22/09/2026 isto listava o rótulo de cada uma**, e media 565 dos 1.350
    tokens da resposta — 42%, para responder a uma pergunta que ninguém fez. As
    10 em andamento, que são a resposta, custavam 476.

    O ano fica porque é o que orienta a segunda pergunta ("o que eu fiz em
    2024?"), e ela agora custa uma ida a mais, só para quem a faz. Os rótulos
    continuam alcançáveis por `todas`, e o rodapé diz isso: o corte é do padrão,
    não da ferramenta.

    A contagem é de MATRÍCULA e não de sigla: `PSI3322-2026` e
    `PSI3322-2026-REOF` são duas, e contá-las como uma esconderia uma delas —
    o mesmo motivo que fazia a lista antiga usar o rótulo.
    """
    por_ano: dict[int, int] = {}
    for d in disciplinas:
        por_ano[d.fim.year] = por_ano.get(d.fim.year, 0) + 1
    return [
        "  " + " · ".join(
            f"{ano}: {quantas}" for ano, quantas in sorted(por_ano.items(), reverse=True)
        )
    ]


# O `_COMO_USAR` que morava aqui — "use a SIGLA ou o RÓTULO INTEIRO, que é o que
# distingue duas matrículas da mesma sigla" — saiu em 22/09/2026. Ele é
# roteamento, e o roteamento já está no lugar onde o cliente o lê sem custo
# extra: o esquema do parâmetro `disciplina` das quatro ferramentas que o pedem
# diz exatamente isso, palavra por palavra. Era a mesma frase paga duas vezes na
# mesma sessão (`notas/custo-em-token.md`).

# O `_DE_ONDE_SAI` que morava aqui — "'Em andamento' sai das datas que o
# e-Disciplinas declara para o espaço da disciplina, e não da sua matrícula
# oficial" — mudou de casa em 22/09/2026, e foi para a DESCRIÇÃO desta
# ferramenta, inteiro. Ele não é ressalva sobre esta resposta: é contrato sobre o
# que a ferramenta significa, verdadeiro em toda chamada e igual em todas. Na
# descrição o cliente o lê uma vez por sessão; aqui ele saía a cada chamada da
# ferramenta mais chamada do servidor.


def minhas_disciplinas(
    cliente, todas: bool = False, momento=None
) -> RespostaDisciplinas:
    """"Quais matérias eu tenho?" — e o que fazer com as de anos atrás.

    **A decisão.** A conta do dono tem dezenas de matrículas e só um punhado é
    do semestre corrente (74 e 10 na fixture real de 31/08; 45 ao vivo em
    14/09 — os dois números discordam e nenhum dos dois muda o desenho). Quem
    pergunta "quais matérias eu tenho" está perguntando do agora: despejar a
    lista inteira com nome e período faria a resposta certa ficar enterrada em
    dezenas de linhas de semestres que já acabaram, e um modelo lendo isso
    escolhe a errada.

    O que foi recusado, e por quê:

    - **Filtrar as antigas fora.** Seria o corte mais limpo de ler e o único
      que quebra o Invariante 7: a matrícula antiga sumiria da resposta, e
      perguntar "e PMT3100?" devolveria "não achei" — que é indistinguível de
      "você não cursou". Fora.
    - **Paginar com teto.** Teto é a ferramenta certa quando o custo cresce com
      o tamanho (`ja_entreguei` paga uma chamada por entrega). Aqui a lista já
      está em memória, cacheada, e paginá-la cobraria uma segunda pergunta por
      um dado que já foi buscado.

    O que ficou: **corte de DETALHE, nunca de EXISTÊNCIA.** As do semestre
    corrente saem completas; as encerradas saem só com o rótulo, agrupadas pelo
    ano em que terminaram; e o corte é declarado com o parâmetro que o desfaz
    (`todas`). Nenhuma matrícula some da resposta em nenhum modo.

    `momento` é um DATETIME (o instante da pergunta) e o `agora` de `carregar` é
    um RELÓGIO (`time.monotonic`, para o TTL) — nomes diferentes de propósito,
    porque passar um no lugar do outro compila e erra calado (mesma armadilha
    anotada em `ja_entreguei`).
    """
    momento = momento if momento is not None else datetime.now(FUSO_SAO_PAULO)
    # Um erro do cliente sobe daqui sem ser capturado: token recusado e "você
    # não tem matrícula nenhuma" são indistinguíveis para quem lê e têm curas
    # opostas — é o bug do §9 de 28/08 (DI10).
    lista = carregar(cliente)

    if not lista:
        # §9 de 28/08: `get_users_courses` com userid errado devolve `[]` com
        # HTTP 200. Vazio mudo aqui seria exatamente aquele bug de volta.
        return RespostaDisciplinas(
            texto=(
                "O e-Disciplinas não devolveu matrícula nenhuma para este "
                "token.\n\nIsso costuma ser uma de duas coisas, e elas têm "
                "curas diferentes: ou a conta realmente não tem disciplina "
                "neste Moodle, ou o token perdeu o vínculo com o usuário. "
                "`diagnostico` responde qual das duas é, com uma chamada."
            ),
            total=0,
            em_andamento=0,
            encerradas=0,
            sem_periodo=0,
            vazio_por="sem_matriculas",
        )

    por_situacao: dict[str, list[Disciplina]] = {
        EM_ANDAMENTO: [],
        A_COMECAR: [],
        ENCERRADA: [],
        SEM_PERIODO: [],
    }
    for d in lista:
        por_situacao[situacao_de(d, momento)].append(d)

    def _por_sigla(ds):
        return sorted(ds, key=lambda d: (d.sigla, d.rotulo))

    linhas = [f"As suas disciplinas no e-Disciplinas ({len(lista)} matrículas)."]

    correntes = _por_sigla(por_situacao[EM_ANDAMENTO])
    if correntes:
        linhas.append(f"\nEm andamento agora ({len(correntes)}):")
        linhas.extend(_linha_completa(d) for d in correntes)
    else:
        # Zero em andamento é resposta legítima (férias, ou lista inteira de
        # semestres passados) e não pode sair como bloco ausente: quem lê
        # concluiria que a ferramenta falhou em vez de que não há aula.
        linhas.append(
            "\nNenhuma matrícula em andamento agora, pelas datas do "
            "e-Disciplinas."
        )

    futuras = _por_sigla(por_situacao[A_COMECAR])
    if futuras:
        linhas.append(f"\nAinda não começaram ({len(futuras)}):")
        linhas.extend(_linha_completa(d) for d in futuras)

    encerradas = por_situacao[ENCERRADA]
    if encerradas:
        if todas:
            linhas.append(f"\nEncerradas ({len(encerradas)}):")
            linhas.extend(
                _linha_completa(d)
                for d in sorted(encerradas, key=lambda d: (d.fim, d.sigla), reverse=True)
            )
        else:
            linhas.append(
                f"\nEncerradas ({len(encerradas)}) — quantas por ano de término:"
            )
            linhas.extend(_bloco_compacto(encerradas))

    sem_periodo = _por_sigla(por_situacao[SEM_PERIODO])
    if sem_periodo:
        # Minúsculo no começo da frase de propósito: é este o primeiro "sem
        # período" do texto, e o bloco tem de vir antes do aviso que o explica.
        linhas.append(
            f"\nMatrículas sem período declarado no e-Disciplinas "
            f"({len(sem_periodo)}) — não dá para dizer se estão em andamento:"
        )
        linhas.extend(f"  {d.sigla} ({d.rotulo})" for d in sem_periodo)

    avisos = []
    if encerradas and not todas:
        # Invariante 7: o corte é declarado, com a contagem e com a cura — e
        # dizendo o que exatamente ficou de fora, que aqui é detalhe e não
        # matrícula.
        avisos.insert(
            0,
            f"Das {len(encerradas)} encerradas sai só a contagem por ano; o "
            "rótulo, o nome e o período de cada uma ficaram de fora. Peça de "
            "novo com `todas` para vê-los. Nenhuma matrícula foi omitida desta "
            "contagem.",
        )

    linhas.extend(f"\n⚠ {a}" for a in avisos)

    return RespostaDisciplinas(
        texto="\n".join(linhas),
        total=len(lista),
        em_andamento=len(correntes),
        encerradas=len(encerradas),
        sem_periodo=len(sem_periodo),
    )
