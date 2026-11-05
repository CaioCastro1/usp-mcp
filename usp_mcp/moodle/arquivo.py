"""Baixar UM arquivo do espaço da disciplina, e entregar o CAMINHO.

A ferramenta não lê o arquivo: quem lê é o agente que chamou. A decisão é do §9
de 01/09/2026 e veio com número — entregar os bytes pelo canal MCP custaria
~302.000 tokens no PDF médio da amostra (base64), contra ~50 do caminho; e
extrair o texto no servidor custaria ~2.679, mas **perderia as figuras**, que num
acervo de eletrônica (circuitos, formas de onda, esquemas) são o conteúdo. Os
slides medidos têm 280–440 B de texto por página: são quase só imagem.

Convenção de erro, seguindo `material`: sigla que não resolve **levanta**, porque
é pergunta malformada e resolver antes evita gastar chamada da conta. O resto —
nada casou, casou demais, é link, passou do teto — **devolve** resposta com texto
explicativo, porque são resultados legítimos e o Invariante 6 pede que cada um
diga a própria cura.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import deposito
from .cliente import TETO_ARQUIVO_BYTES as _TETO_CLIENTE
from .disciplinas import carregar, resolver
from .erros import (
    CertificadoNaoVerificado,
    ErroMoodle,
    FuncaoBloqueada,
    MoodleIndisponivel,
    RespostaIlegivel,
    TokenInvalido,
)
from .material import acervo
from .texto import casa

# Rebatizado como nome DESTE módulo de propósito: o cliente guarda o teto do
# transporte, este é o teto da ferramenta. Mesmo valor, dois donos com razões
# diferentes — e é este nome que o `monkeypatch` do teste alcança.
TETO_ARQUIVO_BYTES = _TETO_CLIENTE

# Plural: os 19 PDFs de PSI3323 somam 15,9 MB (medido em 01/09). Dez arquivos e
# 100 MB é folga sobre o pior caso conhecido, e o corte é declarado.
TETO_PLURAL_ARQUIVOS = 10
TETO_PLURAL_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class Baixado:
    nome: str
    tipo: str
    mimetype: str | None
    tamanho: int
    caminho: Path
    fileid: str
    secao: str
    modulo: str
    reusado: bool


@dataclass(frozen=True)
class Link:
    nome: str
    url: str


@dataclass(frozen=True)
class Recusado:
    nome: str
    motivo: str


@dataclass(frozen=True)
class Candidato:
    nome: str
    tamanho: int | None
    secao: str
    modulo: str


@dataclass(frozen=True)
class RespostaArquivo:
    texto: str
    baixados: tuple[Baixado, ...] = ()
    links: tuple[Link, ...] = ()
    recusados: tuple[Recusado, ...] = ()
    candidatos: tuple[Candidato, ...] = ()


_AVISO_LEITURA = (
    "O arquivo está no disco DESTA máquina. Abra-o com a sua ferramenta de "
    "leitura de arquivos para ver o conteúdo — este servidor entrega o caminho, "
    "não o texto."
)


def _kb(n) -> str:
    return f"{n // 1024} kB" if n else "tamanho desconhecido"


# Motivo seguro por TIPO de exceção, nunca `str(exc)` cru: a mensagem de
# `FuncaoBloqueada` (cliente.py) embute a `fileurl` recusada e o prefixo
# esperado — ecoar isso no texto que vai ao modelo vazaria endereço mesmo
# sem vazar credencial, e violaria T99c/T68b (nenhuma URL de webservice no
# texto). O padrão é "não emitir a menos que", não o oposto: um tipo de
# `ErroMoodle` que ainda não existe cai no `else` genérico, que nunca
# carrega texto de exceção nenhum — assim um erro novo não pode criar um
# vazamento novo sem alguém decidir explicitamente que a mensagem dele é
# segura o bastante para entrar aqui.
def _motivo_seguro(exc: ErroMoodle) -> str:
    if isinstance(exc, FuncaoBloqueada):
        return "recusado por segurança: o endereço do arquivo não é do e-Disciplinas"
    if isinstance(exc, CertificadoNaoVerificado):  # antes do pai: é subclasse
        return "o certificado HTTPS do e-Disciplinas não pôde ser verificado ao baixar este arquivo"
    if isinstance(exc, MoodleIndisponivel):
        return "o e-Disciplinas não respondeu ao baixar este arquivo"
    if isinstance(exc, TokenInvalido):
        return "credencial recusada ao baixar este arquivo"
    if isinstance(exc, RespostaIlegivel):
        return "o e-Disciplinas devolveu algo ilegível ao baixar este arquivo"
    return "falha ao baixar este arquivo"


def _baixar_um(cliente, item, courseid: int, raiz) -> Baixado:
    """Baixa se preciso, grava, devolve o registro. Reuso é a existência do arquivo."""
    caminho = deposito.caminho_para(
        courseid=courseid,
        fileid=item.fileid,
        timemodified=int(item.modificado.timestamp()) if item.modificado else 0,
        filename=item.nome,
        raiz=raiz,
    )
    reusado = deposito.ja_baixado(caminho, item.tamanho)
    if not reusado:
        dados = cliente.baixar(item.fileurl_bruta, tamanho_esperado=item.tamanho)
        deposito.gravar(caminho, dados)

    return Baixado(
        nome=item.nome,
        tipo=item.tipo,
        mimetype=item.mimetype,
        tamanho=item.tamanho or caminho.stat().st_size,
        caminho=caminho,
        fileid=item.fileid,
        secao=item.secao,
        modulo=item.modulo,
        reusado=reusado,
    )


def baixar_arquivo(
    cliente,
    disciplina: str,
    nome: str,
    todos: bool = False,
    agora=None,
    raiz=None,
) -> RespostaArquivo:
    """Uma disciplina, um trecho de nome, um arquivo (ou vários com `todos`)."""
    lista = carregar(cliente, agora=agora)
    resolucao = resolver(lista, disciplina)
    if resolucao.disciplina is None:
        raise ErroMoodle(resolucao.motivo)

    alvo = resolucao.disciplina
    # `acervo` e não `get_contents` cru: é ele que traz também os anexos das
    # entregas (§9, 12/09). Sem isto esta ferramenta continuaria cega para o
    # enunciado do EC-1 mesmo depois de `material` aprender a listá-lo.
    conteudo = acervo(cliente, alvo.courseid)
    itens = [i for s in conteudo.secoes for i in s.itens]
    # Casamento por nome de arquivo, e só. O trabalho semântico — "qual destes
    # é a lista sobre carta de Smith" — é do modelo que leu a listagem, não de
    # uma heurística de string aqui: ele resolve sinônimo, abreviação e
    # contexto, e nenhuma regra de substring resolve. `material` emite o rótulo
    # do professor junto de cada arquivo exatamente para tornar essa escolha
    # possível. Decisão de 03/09 no §9, que também diz o que foi tentado antes.
    casados = [i for i in itens if casa(nome, i.nome)]
    cabecalho = f"{alvo.sigla} ({alvo.rotulo})"

    if not casados:
        return RespostaArquivo(
            texto=(
                f"{cabecalho} — nenhum arquivo com {nome!r} no nome. "
                f"A disciplina tem {conteudo.total_itens} itens no total. Use a "
                "ferramenta `material`: ela lista cada arquivo com o rótulo que o "
                "professor deu ao módulo — é ali que está o assunto, quando o nome "
                "do arquivo não diz. Escolha na lista e repita com o nome exato."
            )
        )

    if len(casados) > 1 and not todos:
        candidatos = tuple(
            Candidato(nome=i.nome, tamanho=i.tamanho, secao=i.secao, modulo=i.modulo)
            for i in casados
        )
        linhas = [
            f"{cabecalho} — {nome!r} casa com {len(casados)} arquivos. "
            "Nenhum foi baixado."
        ]
        linhas += [
            f"  - {c.nome} [{_kb(c.tamanho)}] — seção {c.secao!r}, módulo {c.modulo!r}"
            for c in candidatos
        ]
        if len({c.nome for c in candidatos}) > 1:
            linhas.append(
                "Repita com um trecho mais específico, ou com todos=true para "
                f"baixar os {len(casados)}."
            )
        else:
            # A colisão real de PSI3323 (T87): o nome dos candidatos é
            # IDÊNTICO. "Um trecho mais específico" promete o que quem lê não
            # consegue fazer, porque o casamento é por nome de arquivo — a
            # saída honesta é a única forma que de fato pega os dois.
            linhas.append(
                f"Os {len(casados)} candidatos têm o mesmo nome de arquivo — um "
                "trecho mais específico não vai distingui-los. Use todos=true "
                "para baixar todos."
            )
        return RespostaArquivo(texto="\n".join(linhas), candidatos=candidatos)

    return _entregar(cliente, cabecalho, casados, alvo.courseid, raiz, todos)


def _entregar(cliente, cabecalho, casados, courseid, raiz, todos) -> RespostaArquivo:
    """Separa link de arquivo, baixa o que dá, e monta o texto. `todos` entra
    aqui para a tarefa 5 acrescentar os tetos sem mexer no roteamento acima."""
    baixados: list[Baixado] = []
    links: list[Link] = []
    recusados: list[Recusado] = []
    acumulado = 0

    for item in casados:
        if not item.fileurl_bruta or not item.fileid:
            # Link externo (YouTube, Google Docs): a URL já é pública e sai
            # inteira. Baixá-lo mandaria o token para outro host — e a allowlist
            # do cliente recusaria, com razão.
            links.append(Link(nome=item.nome, url=item.url_externa or ""))
            continue
        if item.tamanho and item.tamanho > TETO_ARQUIVO_BYTES:
            recusados.append(
                Recusado(
                    nome=item.nome,
                    motivo=(
                        f"{_kb(item.tamanho)} passa do teto de "
                        f"{TETO_ARQUIVO_BYTES // (1024 * 1024)} MB por arquivo"
                    ),
                )
            )
            continue
        if todos and len(baixados) >= TETO_PLURAL_ARQUIVOS:
            recusados.append(
                Recusado(
                    nome=item.nome,
                    motivo=f"teto de {TETO_PLURAL_ARQUIVOS} arquivos por chamada",
                )
            )
            continue
        if todos and acumulado + (item.tamanho or 0) > TETO_PLURAL_BYTES and baixados:
            recusados.append(
                Recusado(
                    nome=item.nome,
                    motivo=f"teto de {TETO_PLURAL_BYTES // (1024 * 1024)} MB por chamada",
                )
            )
            continue
        if todos:
            # Invariante 6/7: no modo PLURAL um arquivo ruim não pode derrubar
            # o lote inteiro nem sumir calado — vira `Recusado` nomeado, e os
            # outros continuam. Isto cobre tanto falha de transporte quanto a
            # recusa de segurança de `cliente.baixar` (host fora da allowlist):
            # as duas são `ErroMoodle`, e as duas precisam chegar legíveis.
            try:
                baixado = _baixar_um(cliente, item, courseid, raiz)
            except ErroMoodle as exc:
                recusados.append(Recusado(nome=item.nome, motivo=_motivo_seguro(exc)))
                continue
        else:
            # No SINGULAR há exatamente um arquivo pedido: converter a falha
            # dele numa linha de "recusado" leria como um resultado parcial
            # que não existiu. A exceção sobe crua — aqui ela é a resposta
            # mais legível que existe (Invariante 6), não a mais silenciosa.
            baixado = _baixar_um(cliente, item, courseid, raiz)
        baixados.append(baixado)
        acumulado += item.tamanho or 0

    linhas = [f"{cabecalho} — {len(baixados)} arquivo(s) baixado(s)."]
    for b in baixados:
        marca = " (já estava em disco)" if b.reusado else ""
        linhas.append(f"\n{b.nome} [{b.tipo}, {_kb(b.tamanho)}]{marca}")
        # secao/modulo aqui também: sem isso, dois arquivos de mesmo nome
        # (a colisão real de T87/T88) produzem duas linhas de sucesso
        # idênticas, distinguíveis só pelo diretório numérico do caminho.
        linhas.append(f"  seção {b.secao!r}, módulo {b.modulo!r}")
        linhas.append(f"  {b.caminho}")
    for l in links:
        linhas.append(f"\n{l.nome} — é um link externo, não um arquivo do e-Disciplinas:")
        linhas.append(f"  {l.url}")
    # Invariante 7: o que não veio é NOMEADO, nunca omitido.
    for r in recusados:
        linhas.append(f"\n{r.nome} — não baixado: {r.motivo}")
    if baixados:
        linhas.append(f"\n⚠ {_AVISO_LEITURA}")

    return RespostaArquivo(
        texto="\n".join(linhas),
        baixados=tuple(baixados),
        links=tuple(links),
        recusados=tuple(recusados),
    )
