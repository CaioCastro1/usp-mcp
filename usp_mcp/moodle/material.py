"""Os arquivos do espaço da disciplina — a pergunta, nas palavras do dono.

Não é "onde está o PDF da aula de hoje", que é como o §5 registrava a candidata.
É **descobrir o acervo**: regras da disciplina, listas de exercícios, provas
anteriores. Por isso a ferramenta lista tudo por padrão e a busca é por nome de
arquivo, não por data.

**Medido em PSI3323, e só nela** (§9, 31/08 — decisão do dono de aprofundar numa
amostra): 58.049 B crus por disciplina, ~6.486 B projetados (11,2%). 16 seções,
32 módulos, 29 itens com conteúdo — 19 PDF, 7 link externo, 1 docx, 1 jpeg, 1
octet-stream. A razão de 11,2% **não é fato do sistema**: uma disciplina com
resumo de seção longo pode ter razão bem pior, e isso só se sabe capturando
outras.

**A regra de segurança desta fronteira, e ela veio de medição.** Os 22 módulos
`resource` apontam para `edisciplinas.usp.br/webservice/pluginfile.php`, e baixar
de lá exige o token no request. Emitir uma URL com o token dentro põe a credencial
a um passo do contexto do modelo e de todo log por onde a resposta passar
(Invariante 3); emitir a URL sem o token entrega um endereço que não abre. Nos dois
casos a saída fica pior, então o endereço não sai. **Medido em 01/09: o token não
precisa ir na URL — o corpo do POST autentica igual** (§9), então quem baixa é o
servidor, sem que uma URL com segredo dentro chegue a existir. Os 7
módulos `url` apontam para fora (YouTube, Google Docs, sites de fabricante) e não
têm esse problema: esses saem inteiros, porque recusar tudo seria esconder o que
se sabe. O que identifica um arquivo interno — nome, tipo, tamanho, data — sai;
o endereço dele, não.

**O acervo não cabe numa chamada só, e isso é medição de 12/09/2026** (§9). Os
módulos `assign` chegam em `core_course_get_contents` com `contents` VAZIO: em
PTC3314 são 4, e dentro deles moram os enunciados dos exercícios computacionais —
`EP1-2026.pdf`, 218 kB. O `description` do módulo não ajuda (529 B de datas, zero
`href`). Quem tem o arquivo é `mod_assign_get_assignments`, e é por isso que
`acervo` faz DUAS chamadas — a segunda só quando a primeira encontra entrega, o
que mantém o Invariante 5 de pé para as disciplinas que não têm nenhuma.

**O link no meio do texto, e a amostra que não o tem (17/09/2026).** O dono
perguntou pelos slides de uma disciplina e ouviu "não tem nenhum"; os slides
estavam num `<a href>` dentro de um bloco de texto da página (`label`, no
vocabulário do Moodle). `label` não tem `contents`, então caía em `sem_conteudo`
e o rodapé o chamava de "atividade com consulta própria" — falso duas vezes.
Medido nas duas capturas versionadas: **zero** `label` e **zero** `href` em
qualquer `description` ou `summary` (PSI3323: 32 módulos, 4 `description`
somando 1.986 B, 11 `summary` somando 14.313 B; PTC3314: 75 módulos, 20
`description` somando 6.233 B, 19 `summary` somando 9.958 B). O defeito é
confirmado por leitura do código, não pela amostra; o custo real na disciplina
que o motivou fica por medir quando ela for capturada. O que se mediu foi o
contrário: emitir o texto ao redor do link custaria mais que a projeção inteira
(~6.500 B), e por isso o que sai por link é o título da âncora, a URL e o começo
do bloco — que o Moodle já cortou em `name`.
"""
from __future__ import annotations

import mimetypes
from urllib.parse import unquote, urlsplit

from dataclasses import dataclass
from datetime import datetime

from .disciplinas import carregar, resolver
from .erros import ErroMoodle
from .ressalvas import PRESENCA, Ressalva, emitir
from .texto import casa, links, normalizar, sem_html

# Host + caminho que caracterizam arquivo servido pelo webservice do Moodle, e
# que por isso exigiria o token para ser baixado.
_MARCAS_INTERNAS = ("/webservice/", "pluginfile.php")

# O módulo que é só texto na página da disciplina. Não tem `contents`, não tem
# `url` de visualização, e não é atividade: o que ele tem de material é o link
# que o professor deixou no meio da frase.
_MODULO_DE_TEXTO = "label"

# Caminhos que caracterizam página do próprio Moodle. Um link do texto para
# `/mod/forum/view.php` aponta para uma atividade que o rodapé já declara; para
# `/course/view.php`, para outra turma. Nenhum é material, e o host sozinho não
# basta para reconhecê-los: o texto pode trazer o link relativo, sem host.
_CAMINHOS_DO_MOODLE = (
    "/mod/", "/course/", "/user/", "/grade/", "/login/", "/my/", "/calendar/", "/theme/",
)

# Quantas entregas sem anexo o rodapé nomeia antes de virar contagem. Três é o
# que cabe numa linha e ainda deixa reconhecer o padrão do nome; o resto vira
# "e mais N", nunca silêncio.
_TETO_NOMES_NO_RODAPE = 3

# A única ressalva invariável desta ferramenta. Ela explica por que o ENDEREÇO do
# arquivo não sai (Invariante 3) e para onde ir para baixar de fato — e só tem
# sentido diante de arquivo interno listado. Ver `ressalvas.py`.
_LINK_NAO_SAI = (
    "O link do arquivo interno do e-Disciplinas não é entregue aqui: um "
    "endereço sem a credencial não abre, e um com ela poria a credencial "
    "no seu contexto — por isso ele não sai desta máquina, "
    "mesmo sabendo que a requisição de download autentica pelo corpo do "
    "pedido, sem precisar colar a credencial no endereço. Para baixar de "
    "fato um destes arquivos, use a ferramenta `baixar_arquivo`."
)

_RESSALVAS = (Ressalva(texto=_LINK_NAO_SAI, quando=PRESENCA),)

_TIPOS = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "documento",
    "application/msword": "documento",
    # O acervo de PTC3314 publica o mesmo enunciado em PDF e em ODT (12/09).
    # Sem esta linha o ODT saía como "arquivo", escondendo que é a mesma coisa
    # em outro formato — e nenhum `resource` da amostra de PSI3323 era ODT, que
    # é por que isto só apareceu quando as entregas entraram na lista.
    "application/vnd.oasis.opendocument.text": "documento",
    "application/vnd.oasis.opendocument.spreadsheet": "planilha",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "planilha",
    "image/jpeg": "imagem",
    "image/png": "imagem",
}


@dataclass(frozen=True)
class Item:
    nome: str
    tipo: str
    tamanho: int | None
    modificado: datetime | None
    url_externa: str | None
    # Campos para consumo INTERNO de `arquivo.py`, nunca impressos: T68b e T68c
    # são os guardas disso. `fileurl_bruta` é a `fileurl` como o Moodle a
    # devolveu — para um `resource` ela é a URL do webservice, para um `url` é o
    # endereço externo. O nome diz "bruta" e não "interna" porque as duas coisas
    # passam por aqui, e é `fileid` (ausente no link externo) que as separa.
    fileurl_bruta: str | None = None
    fileid: str | None = None
    mimetype: str | None = None
    secao: str = ""
    modulo: str = ""
    # Veio de um `<a href>` no texto da página, não de `contents`. O rodapé de
    # `material` conta estes para quem lê saber que o nome é o texto da âncora.
    no_texto: bool = False
    # A âncora não dizia o que é (embrulhava só uma imagem, ou o texto era a
    # própria URL). O nome vira o host, e a linha declara a falta.
    sem_titulo: bool = False


@dataclass(frozen=True)
class Secao:
    nome: str
    itens: tuple[Item, ...]
    # A prosa que o professor escreveu na página, em texto puro: o resumo da
    # seção e os blocos de texto dela, na ordem da página. Não sai na lista — sai
    # quando `material` é chamado com `texto`, e o rodapé diz que ela existe.
    # Medido em 24/09/2026: é onde o professor costuma escrever objetivos,
    # critério de avaliação e bibliografia (seção do topo de PTC3314: 5.414 B).
    texto: str = ""


@dataclass(frozen=True)
class Entrega:
    """Um módulo `assign` do espaço, como `get_contents` o descreve.

    Existe porque `get_contents` descreve a entrega mas **não** os arquivos dela:
    medido em 12/09/2026, os 4 `assign` de PTC3314 chegam com `contents` vazio e
    `description` sem link nenhum. O que sobra de útil é o `cmid` — é por ele que
    o anexo devolvido por `mod_assign_get_assignments` acha a seção onde aparecer.
    """

    cmid: int
    nome: str
    secao: str


@dataclass(frozen=True)
class AnexosDeEntrega:
    itens: tuple[Item, ...]
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Conteudo:
    secoes: tuple[Secao, ...]
    total_itens: int
    sem_conteudo: tuple[str, ...]
    entregas: tuple[Entrega, ...] = ()
    avisos: tuple[str, ...] = ()
    # Links do texto que NÃO viraram item (para dentro do Moodle, e-mail, âncora)
    # e blocos de texto sem link nenhum. Contados, nunca omitidos calados.
    links_ignorados: int = 0
    # Desde 24/09/2026 não vira mais linha no rodapé de `material` — o texto do
    # `label` passou a fazer parte de `Secao.texto`, e é `_secoes_com_texto` que
    # avisa disso, nomeando a seção em vez de contar blocos. O campo fica, porque
    # L1 o usa para travar o fato de que a amostra versionada não tem `label`.
    textos_sem_link: int = 0


@dataclass(frozen=True)
class RespostaMaterial:
    texto: str
    total: int
    mostrados: int
    vazio_por: str | None = None


def _tipo_de(modname: str, mimetype: str | None) -> str:
    if modname == "url":
        return "link"
    return _TIPOS.get(mimetype or "", "arquivo")


def _url_publica(bruto: str | None) -> str | None:
    """Devolve a URL só quando ela não depende de credencial para funcionar.

    Um endereço que só serve com o token colado atrás é um convite a colar o
    token. Ver a docstring do módulo.
    """
    if not bruto or not bruto.startswith("http"):
        return None
    if any(marca in bruto for marca in _MARCAS_INTERNAS):
        return None
    return bruto


def _fileid(bruto: str | None) -> str | None:
    """O primeiro segmento depois de `pluginfile.php/` — o id do arquivo.

    Não é segredo (a URL inteira é que exige credencial para servir de algo), e
    é o que distingue dois arquivos de mesmo nome: em PSI3323, `Dicas para a
    Prova.pdf` existe duas vezes, com ids 9599793 e 9599833.
    """
    if not bruto or "pluginfile.php/" not in bruto:
        return None
    return bruto.split("pluginfile.php/", 1)[1].split("/", 1)[0] or None


def projetar_material(bruto) -> Conteudo:
    """Seções → módulos → conteúdos vira uma lista curta com o que identifica.

    `author` e `userid` ficam de fora de propósito: vêm dentro de `contents`,
    são dado pessoal (§3.3) e não respondem "que arquivos tem aqui".
    """
    secoes: list[Secao] = []
    total = 0
    sem_conteudo: set[str] = set()

    entregas: list[Entrega] = []

    # Duas passadas, e a primeira é barata: os hosts do próprio Moodle (para
    # reconhecer link que aponta para dentro dele) e as URLs que `contents` já
    # publica (para não listar duas vezes o que o `description` de um módulo
    # `url` repete). Com uma passada só, o link do texto sairia antes de a
    # projeção saber que o módulo seguinte publica a mesma URL.
    hosts = _hosts_do_moodle(bruto)
    ja_vistas = _urls_ja_publicadas(bruto)
    links_ignorados = 0
    textos_sem_link = 0

    for secao in bruto or ():
        nome_secao = secao.get("name") or ""
        # O `summary` da seção é texto da página tanto quanto o `label`, só que
        # sem módulo: o link que mora nele entra na seção, sem rótulo de módulo.
        itens, ignorados = _links_do_texto(
            secao.get("summary"), secao=nome_secao, modulo="", hosts=hosts, ja_vistas=ja_vistas
        )
        links_ignorados += ignorados
        total += len(itens)
        prosa = [t for t in (sem_html(secao.get("summary") or ""),) if t]
        for modulo in secao.get("modules") or ():
            modname = modulo.get("modname") or ""
            nome_modulo = modulo.get("name") or ""
            if modname == _MODULO_DE_TEXTO:
                # Bloco de texto: o que ele tem de material é o link dentro dele.
                # Não vai para `sem_conteudo` porque não é atividade e não tem
                # consulta própria — o rodapé antigo dizia as duas coisas, e as
                # duas eram falsas. Texto sem link nenhum é contado à parte.
                do_texto, ignorados = _links_do_texto(
                    modulo.get("description"), secao=nome_secao, modulo=nome_modulo,
                    hosts=hosts, ja_vistas=ja_vistas,
                )
                links_ignorados += ignorados
                if not do_texto and not ignorados:
                    textos_sem_link += 1
                itens.extend(do_texto)
                total += len(do_texto)
                if (t := sem_html(modulo.get("description") or "")):
                    prosa.append(t)
                continue
            if modname == "assign":
                # Registrada mesmo sem `contents`, e é o registro que decide se
                # a segunda chamada vale a pena: sem `assign` nenhum, perguntar
                # por anexo de entrega só pode devolver vazio (Invariante 5).
                entregas.append(
                    Entrega(
                        cmid=modulo.get("id"),
                        nome=modulo.get("name") or "",
                        secao=secao.get("name") or "",
                    )
                )
            conteudos = modulo.get("contents") or ()
            if not conteudos:
                # Invariante 7: fórum e entrega não têm `contents`. Sumir com
                # eles faria a lista parecer o espaço inteiro quando não é.
                sem_conteudo.add(modname or "?")
            for conteudo in conteudos:
                itens.append(
                    _item_de(
                        conteudo,
                        modname=modname,
                        secao=nome_secao,
                        modulo=nome_modulo,
                    )
                )
                total += 1
            # O `description` de qualquer módulo tem a mesma forma que o do
            # `label`, e um link nele é material do mesmo jeito. O que já saiu
            # por `contents` (o `url` que repete a própria URL) não sai de novo.
            do_texto, ignorados = _links_do_texto(
                modulo.get("description"), secao=nome_secao, modulo=nome_modulo,
                hosts=hosts, ja_vistas=ja_vistas,
            )
            links_ignorados += ignorados
            itens.extend(do_texto)
            total += len(do_texto)
        secoes.append(Secao(nome=nome_secao, itens=tuple(itens), texto="\n".join(prosa)))

    return Conteudo(
        secoes=tuple(secoes),
        total_itens=total,
        sem_conteudo=tuple(sorted(sem_conteudo)),
        entregas=tuple(entregas),
        links_ignorados=links_ignorados,
        textos_sem_link=textos_sem_link,
    )


def _hosts_do_moodle(bruto) -> frozenset[str]:
    """Os hosts que o próprio payload diz serem do Moodle.

    Todo módulo traz `modicon` no host do site, e quase todo traz `url`; os
    `resource` trazem `fileurl` no webservice. Derivar daí, e não de
    configuração, é o que faz a regra valer para o Moodle de outra faculdade
    sem ninguém precisar dizer qual é o host.
    """
    hosts: set[str] = set()
    for secao in bruto or ():
        for modulo in secao.get("modules") or ():
            for chave in ("url", "modicon"):
                if (host := urlsplit(modulo.get(chave) or "").netloc):
                    hosts.add(host)
            for conteudo in modulo.get("contents") or ():
                fileurl = conteudo.get("fileurl") or ""
                if any(marca in fileurl for marca in _MARCAS_INTERNAS):
                    if (host := urlsplit(fileurl).netloc):
                        hosts.add(host)
    return frozenset(hosts)


def _urls_ja_publicadas(bruto) -> set[str]:
    return {
        conteudo.get("fileurl")
        for secao in bruto or ()
        for modulo in secao.get("modules") or ()
        for conteudo in modulo.get("contents") or ()
        if conteudo.get("fileurl")
    }


def _classificar(url: str, hosts: frozenset[str]) -> str:
    """`externo`, `arquivo` (do webservice, baixável) ou `ignorar`.

    `ignorar` cobre o que não é material: âncora da própria página (`#`),
    e-mail (`mailto:`), `javascript:`, link relativo (que só pode ser do próprio
    Moodle) e link absoluto para o host do Moodle ou para caminho de página
    dele. O que esses apontam ou já está na lista (um `resource`), ou é
    atividade que o rodapé declara, ou é outra turma.
    """
    if not url.startswith(("http://", "https://")):
        return "ignorar"
    if any(marca in url for marca in _MARCAS_INTERNAS):
        return "arquivo"
    partes = urlsplit(url)
    if partes.netloc in hosts or partes.path.startswith(_CAMINHOS_DO_MOODLE):
        return "ignorar"
    return "externo"


def _titulo_util(titulo: str, url: str) -> str | None:
    """O texto da âncora, quando ele diz algo que a URL não diz.

    Vazio (âncora que embrulha só uma imagem), a própria URL, ou coisa sem letra
    nem número não é título — e inventar um seria pior do que declarar que não
    há. `www.` sem esquema é URL escrita à mão, e é o caso mais comum de âncora
    cujo texto é o próprio endereço.
    """
    t = (titulo or "").strip()
    if not t or "://" in t or t.lower().startswith("www.") or not normalizar(t):
        return None
    if normalizar(t) in normalizar(url):
        return None
    return t


def _item_de_link(url: str, titulo: str, classe: str, *, secao: str, modulo: str) -> Item:
    titulo_util = _titulo_util(titulo, url)
    partes = urlsplit(url)
    if classe == "arquivo":
        # Arquivo que o professor arrastou para dentro do texto. O nome é o do
        # arquivo (é ele que `baixar_arquivo` casa e grava em disco, com
        # extensão); o título da âncora, quando há, é o rótulo — como o nome do
        # módulo é para um `resource`. Tamanho e data não vêm: o `href` é só a
        # URL, e o tipo sai da extensão, que é o que há.
        nome = unquote(partes.path.rsplit("/", 1)[-1]) or titulo_util or partes.netloc
        mimetype = mimetypes.guess_type(nome)[0]
        return Item(
            nome=nome,
            tipo=_tipo_de("", mimetype),
            tamanho=None,
            modificado=None,
            url_externa=None,
            fileurl_bruta=url,
            fileid=_fileid(url),
            mimetype=mimetype,
            secao=secao,
            modulo=titulo_util or modulo,
            no_texto=True,
        )
    return Item(
        nome=titulo_util or partes.netloc,
        tipo="link",
        tamanho=None,
        modificado=None,
        url_externa=url,
        secao=secao,
        modulo=modulo,
        no_texto=True,
        sem_titulo=titulo_util is None,
    )


def _links_do_texto(
    html: str | None, *, secao: str, modulo: str, hosts: frozenset[str], ja_vistas: set[str]
) -> tuple[list[Item], int]:
    """Os `<a href>` de um campo de texto viram itens; devolve também quantos
    foram ignorados por não serem material. URL repetida (já publicada por
    `contents`, ou já saída de outro bloco) não sai de novo e não conta como
    ignorada: o destino está na lista."""
    itens: list[Item] = []
    ignorados = 0
    for url, titulo in links(html or ""):
        classe = _classificar(url, hosts)
        if classe == "ignorar":
            ignorados += 1
            continue
        if url in ja_vistas:
            continue
        ja_vistas.add(url)
        itens.append(_item_de_link(url, titulo, classe, secao=secao, modulo=modulo))
    return itens, ignorados


def _item_de(conteudo: dict, *, modname: str, secao: str, modulo: str) -> Item:
    """Um `contents` do Moodle vira `Item`. UMA função, e é o que permite os anexos.

    O anexo de entrega chega de outra função do web service
    (`mod_assign_get_assignments`) com **os mesmos nomes de campo** — `filename`,
    `filesize`, `mimetype`, `timemodified`, `fileurl` — medido em 12/09/2026. Com
    a construção num lugar só, o anexo entra no acervo sem caso especial, e
    `baixar_arquivo` o acha sem saber que ele veio de outro endpoint.
    """
    return Item(
        nome=conteudo.get("filename") or modulo or "",
        tipo=_tipo_de(modname, conteudo.get("mimetype")),
        tamanho=conteudo.get("filesize") or None,
        modificado=_data(conteudo.get("timemodified")),
        url_externa=_url_publica(conteudo.get("fileurl")),
        fileurl_bruta=conteudo.get("fileurl"),
        fileid=_fileid(conteudo.get("fileurl")),
        mimetype=conteudo.get("mimetype"),
        secao=secao,
        modulo=modulo,
    )


def projetar_anexos_de_entrega(bruto, entregas) -> AnexosDeEntrega:
    """Os `introattachments` de cada entrega viram itens do acervo.

    O rótulo de cada anexo é o nome da ENTREGA, não o do arquivo: `EP1-2026.pdf`
    não diz nada, `EC-1 - Transitórios em LT` diz tudo — e é esse campo que
    `rotulo_do_modulo` imprime junto do arquivo.

    `warnings` vira aviso em vez de sumir (Invariante 7). Na captura de 12/09 são
    dois módulos com `No access rights in module context`: uma lista sem eles
    pareceria completa sem ser.
    """
    por_cmid = {e.cmid: e for e in entregas}
    itens: list[Item] = []

    for curso in (bruto or {}).get("courses") or ():
        for entrega in curso.get("assignments") or ():
            local = por_cmid.get(entrega.get("cmid"))
            nome_modulo = local.nome if local else (entrega.get("name") or "")
            secao = local.secao if local else ""
            for anexo in entrega.get("introattachments") or ():
                itens.append(
                    _item_de(anexo, modname="assign", secao=secao, modulo=nome_modulo)
                )

    avisos: list[str] = []
    if quantos := len((bruto or {}).get("warnings") or ()):
        avisos.append(
            f"{quantos} atividade(s) desta disciplina não puderam ser lidas com "
            "esta credencial — se houver arquivo nelas, ele não está acima."
        )

    return AnexosDeEntrega(itens=tuple(itens), avisos=tuple(avisos))


def _com_anexos(conteudo: Conteudo, anexos: AnexosDeEntrega) -> Conteudo:
    """Devolve o conteúdo com os anexos dentro da seção de cada entrega.

    Anexo cuja seção não existe na projeção (não deve acontecer: o `cmid` vem da
    mesma captura) entra numa seção própria em vez de sumir — Invariante 7 vale
    também para o caso que "não acontece".
    """
    if not anexos.itens:
        return conteudo

    por_secao: dict[str, list[Item]] = {}
    for item in anexos.itens:
        por_secao.setdefault(item.secao, []).append(item)

    secoes = [
        Secao(nome=s.nome, itens=s.itens + tuple(por_secao.pop(s.nome, ())), texto=s.texto)
        for s in conteudo.secoes
    ]
    secoes += [Secao(nome=nome, itens=tuple(itens)) for nome, itens in por_secao.items()]

    # `assign` sai de `sem_conteudo` porque deixou de ser verdade que a entrega
    # está fora da lista: ela aparece, pelos arquivos anexados a ela. As que não
    # têm anexo ganham aviso próprio em `material`, com a contagem.
    return Conteudo(
        secoes=tuple(secoes),
        total_itens=conteudo.total_itens + len(anexos.itens),
        sem_conteudo=tuple(n for n in conteudo.sem_conteudo if n != "assign"),
        entregas=conteudo.entregas,
        avisos=conteudo.avisos + anexos.avisos,
        links_ignorados=conteudo.links_ignorados,
        textos_sem_link=conteudo.textos_sem_link,
    )


def acervo(cliente, courseid: int) -> Conteudo:
    """Tudo que é arquivo no espaço da disciplina — de UMA ou de DUAS chamadas.

    A segunda só sai se a primeira disser que existe `assign`. É a diferença
    entre custo sob demanda e martelar a USP por uma resposta que já se sabe
    vazia (Invariante 5), e ela é medível: PTC3314 paga +8.651 B sobre os
    106.121 B de `get_contents` (8%); uma disciplina sem entrega paga zero.

    O escopo `courseids[0]` não é otimização: **sem ele** a função devolve as 74
    matrículas, 1 MB, ~251k tokens (§9, 28/08).

    Ponto único das duas ferramentas de propósito: `material` e `baixar_arquivo`
    faziam o mesmo par de linhas em duplicata, e a segunda ficaria cega para os
    anexos se só a primeira aprendesse a pedi-los.
    """
    conteudo = projetar_material(
        cliente.chamar("core_course_get_contents", courseid=courseid)
    )
    if not conteudo.entregas:
        return conteudo

    anexos = projetar_anexos_de_entrega(
        cliente.chamar("mod_assign_get_assignments", **{"courseids[0]": courseid}),
        conteudo.entregas,
    )
    return _com_anexos(conteudo, anexos)


def _data(carimbo) -> datetime | None:
    from .projecao import FUSO_SAO_PAULO

    if not carimbo:
        return None
    return datetime.fromtimestamp(int(carimbo), FUSO_SAO_PAULO)


def como_dict(conteudo: Conteudo) -> list[dict]:
    """Forma serializável — usada pela medição de custo da suíte."""
    return [
        {
            "secao": s.nome,
            "itens": [
                {
                    "nome": i.nome,
                    "tipo": i.tipo,
                    "tamanho": i.tamanho,
                    "modificado": i.modificado.isoformat() if i.modificado else None,
                    "modulo": rotulo_do_modulo(i),
                    "url": i.url_externa,
                }
                for i in s.itens
            ],
        }
        for s in conteudo.secoes
    ]


def rotulo_do_modulo(item: Item) -> str | None:
    """O nome que o professor deu ao módulo, quando ele acrescenta informação.

    **É a única descrição semântica que o e-Disciplinas oferece**, e ela era
    descartada: `Formulário Provas Substitutivas.pdf` mora no módulo "Formulário
    para pedido de prova substitutiva", e quem procurasse pelo tema não tinha
    como achar. Medido em 03/09: os nomes de módulo de PSI3323 custam ~328
    tokens, 20% da projeção — contra ~3.569 dos `summary` de seção, que é o
    campo caro e o que menos promete.

    Devolve `None` quando o módulo repete o nome do arquivo, o que acontece em
    **9 dos 29 itens**: imprimir os dois seria pagar token para dizer a mesma
    coisa duas vezes. A comparação é normalizada, então "Como criar uma rede
    privada virtual…" casa com o arquivo de mesmo nome apesar da pontuação.
    """
    if not item.modulo:
        return None
    mod, arq = normalizar(item.modulo), normalizar(item.nome)
    if not mod or mod in arq or arq in mod:
        return None
    return item.modulo


def _extensao(nome: str) -> str:
    """A extensão do nome do arquivo, sem o ponto e em minúscula. `""` se não há.

    Teto de 5 para não confundir extensão com o resto de um nome que tem ponto
    no meio ("Aula 3. Revisão"): nenhuma das extensões deste acervo passa disso.
    """
    _, ponto, resto = nome.rpartition(".")
    return resto.lower() if ponto and 0 < len(resto) <= 5 and resto.isalnum() else ""


def _rotulo_de_tipo(item: Item) -> str | None:
    """O tipo, ou `None` quando o nome do arquivo já o diz.

    Medido em 22/09/2026: os 57 blocos `[tipo, tamanho, data]` de PTC3314 custam
    933 tokens contra ~460 dos 57 nomes que eles anotam. Duas repetições dão
    quase tudo isso — `Lista 1.pdf [PDF, …]`, que diz PDF duas vezes na mesma
    linha, e `Provas.zip [arquivo, …]`, em que "arquivo" é o default genérico e
    não acrescenta nada a uma extensão visível.

    Fica quando acrescenta: `.odt` não soletra "documento", e `link` não tem
    extensão nenhuma — ali o rótulo é a única coisa que diz o que aquilo é.
    """
    extensao = _extensao(item.nome)
    if not extensao:
        return item.tipo
    if item.tipo == "arquivo" or extensao == item.tipo.lower():
        return None
    return item.tipo


# Acima disto o tamanho muda a decisão de baixar; abaixo, é ruído em toda linha.
# PTC3314 tem GIF de 178 MB ao lado de PDF de 400 kB, e o `filesize` declarado
# bate exatamente com os bytes recebidos (medido em 01/09), então ele prevê custo
# — só que prever custo de 400 kB não decide nada.
_TAMANHO_QUE_IMPORTA = 10 * 1024 * 1024


def _formatar_item(item: Item) -> str:
    dentro = []
    if (rotulo := _rotulo_de_tipo(item)) is not None:
        dentro.append(rotulo)
    if item.tamanho and item.tamanho >= _TAMANHO_QUE_IMPORTA:
        dentro.append(f"{item.tamanho // (1024 * 1024)} MB")
    if item.modificado:
        dentro.append(item.modificado.strftime("%d/%m/%Y"))
    if item.sem_titulo:
        dentro.append("sem título no texto")
    # Sem nada dentro não sai colchete vazio: `- Provas.zip []` é pior que
    # `- Provas.zip`, e é o caso do item sem data, sem tamanho grande e com a
    # extensão dizendo o tipo.
    linha = f"  - {item.nome}" + (f" [{', '.join(dentro)}]" if dentro else "")
    if (rotulo := rotulo_do_modulo(item)) is not None:
        linha += f"\n    ({rotulo})"
    if item.url_externa:
        linha += f"\n    {item.url_externa}"
    return linha


def _entregas_sem_anexo(conteudo: Conteudo) -> tuple[str, ...]:
    """As entregas que nenhum item do acervo cita como módulo de origem.

    Em PTC3314 são 2 de 4: as duas provas presenciais, que o professor criou
    como `assign` só para ter data. Nomeá-las é mais honesto do que o rodapé
    antigo, que declarava `assign` inteiro fora da lista mesmo quando metade
    dele estava dentro.
    """
    com_arquivo = {i.modulo for s in conteudo.secoes for i in s.itens}
    return tuple(e.nome for e in conteudo.entregas if e.nome not in com_arquivo)


def _secoes_com_texto(conteudo: Conteudo) -> list[str]:
    """Os nomes das seções que têm prosa na página, na ordem da página."""
    return [s.nome or "(sem seção)" for s in conteudo.secoes if s.texto]


def _avisos_do_texto(conteudo: Conteudo, mostrados: list[Item]) -> list[str]:
    """O que a leitura do texto da página achou e o que ela deixou de fora.

    Três contagens, e nenhuma some calada (Invariante 7): quantos itens da lista
    vieram do texto (para quem lê saber que o nome é o texto da âncora), quantos
    links não eram material, e quais seções têm texto que esta lista não mostra —
    é essa terceira que avisa que a página tem texto a mais para pedir.
    """
    avisos: list[str] = []
    if do_texto := sum(1 for i in mostrados if i.no_texto):
        quais = "1 dos itens acima estava" if do_texto == 1 else f"{do_texto} dos itens acima estavam"
        avisos.append(
            f"{quais} no texto da página da disciplina, não publicado(s) como "
            "arquivo ou link: o nome é o texto do link e o parêntese, quando há, "
            "é o começo do bloco de texto onde ele estava."
        )
    if conteudo.links_ignorados:
        avisos.append(
            f"{conteudo.links_ignorados} link(s) no texto da página apontam para "
            "dentro do próprio e-Disciplinas (outra atividade ou página do curso), "
            "para e-mail ou para âncora da própria página, e não foram listados: "
            "não são material."
        )
    # Substitui a contagem de "blocos de texto sem link", que só via `label`: o
    # resumo de seção sumia calado, e é ali que o professor costuma escrever o
    # critério de avaliação (24/09/2026). O texto do `label` agora é texto da seção,
    # então os dois avisos diriam a mesma coisa. Nomear a seção é o que deixa o
    # modelo pedir a certa; dizer para que serve é o que o faz ligar a pergunta
    # "como é a avaliação" a este parâmetro.
    if com_texto := _secoes_com_texto(conteudo):
        nomeadas = ", ".join(com_texto[:_TETO_NOMES_NO_RODAPE])
        if (sobra := len(com_texto) - _TETO_NOMES_NO_RODAPE) > 0:
            nomeadas += f", e mais {sobra}"
        quantas = "1 seção tem" if len(com_texto) == 1 else f"{len(com_texto)} seções têm"
        avisos.append(
            f"{quantas} texto escrito na página da disciplina, fora de arquivo e "
            f"de link, que esta lista não reproduz: {nomeadas}. É onde o professor "
            "costuma pôr critério de avaliação, pré-requisitos e bibliografia — "
            "para ler, chame de novo com `texto` igual ao nome da seção, ou `tudo`."
        )
    return avisos


def material(cliente, disciplina: str, busca: str | None = None, agora=None) -> RespostaMaterial:
    """Uma pergunta, uma disciplina. Resolve a sigla antes de gastar chamada.

    Sigla que não resolve levanta erro legível **sem** pedir conteúdo: consultar
    o Moodle para descobrir que a pergunta estava errada é gastar chamada da
    conta do dono à toa.
    """
    lista = carregar(cliente, agora=agora)
    resolucao = resolver(lista, disciplina)
    if resolucao.disciplina is None:
        raise ErroMoodle(resolucao.motivo)

    alvo = resolucao.disciplina
    conteudo = acervo(cliente, alvo.courseid)

    total = conteudo.total_itens
    filtro = (busca or "").strip()

    secoes = []
    mostrados = 0
    for secao in conteudo.secoes:
        itens = [i for i in secao.itens if casa(filtro, i.nome)]
        mostrados += len(itens)
        if itens:
            secoes.append((secao.nome, itens))

    cabecalho = f"{alvo.sigla} ({alvo.rotulo}) — material do espaço da disciplina"

    if total == 0:
        # Invariante 7: espaço vazio é resultado legítimo e rotulado, para não
        # se confundir com falha de credencial nem com sigla errada. Seis das
        # dez disciplinas do semestre não têm entrega nenhuma — vazio acontece.
        texto = (
            f"{cabecalho}\n\nA disciplina existe e está acessível, mas não há "
            "nenhum arquivo publicado no espaço dela."
        )
        # O vazio também tem de dizer o que a página tem e esta lista não: um
        # texto sem link, ou só links para dentro do Moodle, é vazio legítimo —
        # mas é vazio COM explicação, senão parece que a página está em branco.
        texto += "".join(f"\n\n⚠ {a}" for a in _avisos_do_texto(conteudo, []))
        return RespostaMaterial(texto=texto, total=0, mostrados=0, vazio_por="sem_material")

    if filtro and mostrados == 0:
        # "Nada com esse nome" ≠ "disciplina vazia". Dizer o total é o que
        # permite a quem lê distinguir as duas.
        return RespostaMaterial(
            texto=(
                f"{cabecalho}\n\nNenhum arquivo com {busca!r} no nome. "
                f"A disciplina tem {total} itens no total — repita sem busca "
                "para ver a lista inteira."
            ),
            total=total,
            mostrados=0,
            vazio_por="busca_sem_resultado",
        )

    linhas = [cabecalho]
    if filtro:
        # Invariante 7: filtrar é esconder, e esconder tem de ser declarado.
        linhas.append(f"Filtrado por {busca!r}: {mostrados} de {total} itens.")
    else:
        linhas.append(f"{total} itens.")

    for nome, itens in secoes:
        linhas.append(f"\n{nome}:" if nome else "\n(sem seção):")
        linhas.extend(_formatar_item(i) for i in itens)

    # A ressalva do link é de PRESENÇA, e o que a dispara é haver arquivo
    # INTERNO na lista — não haver item. Uma seção só de link externo não tem
    # endereço nenhum omitido, e explicar a omissão ali é explicar o que não
    # aconteceu. Até 22/09/2026 ela saía em toda resposta.
    itens_mostrados = [i for _, itens in secoes for i in itens]
    avisos = list(
        emitir(_RESSALVAS, vazio=not any(i.fileid for i in itens_mostrados))
    )
    if conteudo.sem_conteudo:
        avisos.append(
            "Não estão nesta lista: "
            + ", ".join(conteudo.sem_conteudo)
            + " — são atividades, não arquivos, e têm consulta própria."
        )
    if mudas := _entregas_sem_anexo(conteudo):
        # Invariante 7 aplicado ao que a segunda chamada NÃO achou: a entrega
        # sem arquivo anexado continua fora da lista, e dizer quais são é o que
        # separa "o professor não anexou nada" de "a ferramenta não olhou".
        #
        # Com teto, porque medir doeu: PSI3472 tem 10 das 11 entregas sem anexo
        # ("Lição aulas 1 e 2", "Lição aulas 3 e 4", …), e nomear as 10 produziu
        # um rodapé que enterrava os outros três avisos. O que o Invariante 7
        # exige é que o corte seja DITO — a contagem fica, os nomes é que são
        # amostra, e "e mais N" é o que impede a amostra de passar por lista.
        nomeadas = ", ".join(mudas[:_TETO_NOMES_NO_RODAPE])
        # `> 0` explícito, e não a verdade do walrus: abaixo do teto a subtração
        # dá NEGATIVO, que é truthy, e o rodapé anunciava "e mais -1". Saiu ao
        # vivo em PTC3314 (12/09/2026), com 2 entregas mudas e as 2 nomeadas.
        # Não é cosmético — quem lê é um modelo decidindo se já viu tudo, e um
        # resto inventado o manda procurar entrega que não existe.
        if (sobra := len(mudas) - _TETO_NOMES_NO_RODAPE) > 0:
            nomeadas += f", e mais {sobra}"
        avisos.append(
            f"{len(mudas)} de {len(conteudo.entregas)} entregas não têm arquivo "
            f"anexado ao enunciado e por isso não aparecem acima: {nomeadas}. "
            "O texto do enunciado, o prazo e a sua nota não são material — "
            "use `o_que_vence` para o prazo."
        )
    if conteudo.avisos:
        avisos.extend(conteudo.avisos)
    avisos.extend(_avisos_do_texto(conteudo, itens_mostrados))

    linhas.extend(f"\n⚠ {a}" for a in avisos)

    return RespostaMaterial(
        texto="\n".join(linhas), total=total, mostrados=mostrados
    )
