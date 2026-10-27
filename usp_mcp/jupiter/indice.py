"""O índice dos módulos da Poli: a lista de cursos e os envelopes, uma vez só.

As três perguntas da ferramenta `modulos` são sobre TODOS os módulos — "qual
tem menor carga", "onde está esta disciplina" —, e o dado para isso são 2
páginas e 100 chamadas DWR (~22 s, medido em 27/10). Feito por pergunta, isso
seria a ferramenta chamada "mais vezes do que deveria". Feito uma vez, o
índice guarda só o que a resposta usa: 6 campos de cada disciplina e 6 de
carga, contra os 17 de cada registro cru (~104 mil tokens no total).

**O `tipo` é o do link ATIVO da lista.** Cada linha traz o link duas vezes —
um comentado em `<!-- -->`, com o `tipo` antigo, e o que a página usa. Os
comentários saem antes de qualquer leitura: o comentado diz `N` para os
percursos e o ativo diz `V`, e foi um `tipo` errado que fez a medição de 14/09
concluir que módulo não tinha grade.

**Módulo é reconhecido pela seção ou pelo prefixo, nunca por palavra do nome.**
"Trilha Formativa" virou "Percurso Formativo" entre duas medições (22 e 27/10).
A seção "Módulo" da tabela e o prefixo "Módulo:" são estrutura; o nome é texto.
"""
from __future__ import annotations

import html
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .erros import JupiterErro, JupiterIndisponivel, RespostaInvalida

__all__ = ["Linha", "Disciplina", "Modulo", "Indice", "ler_lista", "cursos_base",
           "montar_indice", "CacheDoIndice", "TTL_INDICE"]

# Uma semana. Módulo muda por revisão de currículo, não por semana; mas a grade
# do currículo novo cresceu de 67 para 89 registros entre 14/09 e 22/10, e um
# índice sem validade num servidor que fica de pé por semanas mentiria calado.
TTL_INDICE = 7 * 24 * 3600

_COMENTARIO = re.compile(r"<!--.*?-->", re.S)
_LINHA = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
_CELULA = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
_LINK = re.compile(
    r"listarGradeCurricular\?codcg=\d+&(?:amp;)?codcur=(\d+)&(?:amp;)?codhab=(\d+)"
    r"&(?:amp;)?tipo=([A-Z])"
)
_TAG = re.compile(r"<[^>]+>")
_PREFIXO_DO_NOME = re.compile(r"^(?:Engenharia - )?(?:Módulo:\s*)?")


@dataclass(frozen=True)
class Linha:
    codcur: str
    codhab: str
    tipo: str
    nome: str
    modulo: bool


@dataclass(frozen=True)
class Disciplina:
    sigla: str
    nome: str
    creditos_aula: int
    creditos_trabalho: int
    semestre: int | None
    tipo: str  # O obrigatória, C optativa eletiva, L optativa livre


@dataclass(frozen=True)
class Modulo:
    codcur: str
    codhab: str
    tipo: str
    nome: str
    curso: str
    carga_total: int | None
    carga_obrigatoria: int | None
    carga_eletiva: int | None
    carga_livre: int | None
    disciplinas: tuple[Disciplina, ...]
    falhou: bool = False

    @property
    def codigo(self) -> str:
        return f"{self.codcur}/{self.codhab}"

    @property
    def nome_curto(self) -> str:
        """Sem "Módulo:" nem "Engenharia - ": estão em todo nome e não dizem nada.
        "Percurso Formativo:" fica — é o que distingue o percurso do módulo."""
        return _PREFIXO_DO_NOME.sub("", self.nome)

    @property
    def situacao(self) -> str:
        if self.falhou:
            return "falhou"
        if not self.disciplinas and self.carga_total is None:
            return "nao_publicado"
        if not self.disciplinas:
            return "sem_grade"
        return "ok"


@dataclass(frozen=True)
class Indice:
    modulos: tuple[Modulo, ...]


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", trecho))).strip()


def ler_lista(bruto: bytes) -> list[Linha]:
    """Toda linha com link de grade, na ordem da página, marcada se é módulo.

    O nome é a penúltima célula nas duas listas: `N` tem [link, nome, período]
    e `V` tem [link, curso, nome, período].
    """
    pagina = _COMENTARIO.sub("", bruto.decode("iso-8859-1"))
    linhas: list[Linha] = []
    secao = ""
    for tr in _LINHA.finditer(pagina):
        bloco = tr.group(0)
        link = _LINK.search(bloco)
        if link is None:
            cabecalho = _texto(bloco)
            if cabecalho.startswith("Módulo"):
                secao = "modulo"
            elif cabecalho.startswith("Curso"):
                secao = "curso"
            continue
        celulas = [_texto(c) for c in _CELULA.findall(bloco)]
        if len(celulas) < 3:
            continue
        nome = celulas[-2]
        codcur, codhab, tipo = link.groups()
        linhas.append(Linha(codcur, codhab, tipo, nome,
                            modulo=secao == "modulo" or nome.startswith("Módulo:")))
    return linhas


def cursos_base(linhas: list[Linha]) -> dict[str, str]:
    """O nome do curso de cada `codcur`: a linha não-módulo de `codhab` 0, ou a
    de menor `codhab`. É o que deixa "elétrica" achar os módulos do 3032, cujo
    nome não diz o curso."""
    base: dict[str, str] = {}
    candidatas = sorted((l for l in linhas if not l.modulo),
                        key=lambda l: (l.codhab != "0", int(l.codhab)))
    for linha in candidatas:
        base.setdefault(linha.codcur, linha.nome)
    return base


def _inteiro(valor) -> int | None:
    if valor in (None, ""):
        return None
    return int(valor)


def _soma(ficha: dict, *campos: str) -> int | None:
    valores = [_inteiro(ficha.get(c)) for c in campos]
    if all(v is None for v in valores):
        return None
    return sum(v or 0 for v in valores)


def _disciplina(registro: dict) -> Disciplina:
    return Disciplina(
        sigla=registro["coddis"],
        nome=registro["nomdis"],
        creditos_aula=_inteiro(registro.get("creaul")) or 0,
        creditos_trabalho=_inteiro(registro.get("cretrb")) or 0,
        semestre=_inteiro(registro.get("numsemidl")),
        tipo=registro.get("tipobg") or "?",
    )


def _ler_modulo(cliente, linha: Linha, curso: str) -> Modulo:
    # Só falha de TRANSPORTE ou de RESPOSTA é isolada. `ConsultaNegada` sobe:
    # política negando uma consulta da própria fatia é defeito de código, e
    # escondê-la num "não pôde ser lido" seria o silêncio do Invariante 6.
    try:
        ficha = cliente.info_curriculo(linha.codcur, linha.codhab, linha.tipo)
        grade = cliente.grade_curricular(linha.codcur, linha.codhab, linha.tipo)
    except (JupiterIndisponivel, RespostaInvalida, JupiterErro):
        return Modulo(linha.codcur, linha.codhab, linha.tipo, linha.nome, curso,
                      None, None, None, None, (), falhou=True)
    return Modulo(
        codcur=linha.codcur,
        codhab=linha.codhab,
        tipo=linha.tipo,
        nome=linha.nome,
        curso=curso,
        carga_total=_inteiro(ficha.get("cgahortot")),
        carga_obrigatoria=_soma(ficha, "cgahorobgaul", "cgahorobgtrb"),
        carga_eletiva=_soma(ficha, "cgaoptcplaul", "cgaoptcpltrb"),
        carga_livre=_soma(ficha, "cgaoptlreaul", "cgaoptlretrb"),
        disciplinas=tuple(_disciplina(r) for r in grade or ()),
    )


def montar_indice(cliente) -> Indice:
    """As duas listas, e ficha + grade de cada módulo, uma requisição por vez
    (a porta do cliente já serializa: Invariante 5)."""
    linhas = (ler_lista(cliente.obter_lista_cursos_poli("N"))
              + ler_lista(cliente.obter_lista_cursos_poli("V")))
    base = cursos_base(linhas)
    vistos: set[tuple[str, str]] = set()
    modulos: list[Modulo] = []
    for linha in linhas:
        par = (linha.codcur, linha.codhab)
        if not linha.modulo or par in vistos:
            continue
        vistos.add(par)
        modulos.append(_ler_modulo(cliente, linha, base.get(linha.codcur, "")))
    if not modulos:
        raise RespostaInvalida(
            "as listas de cursos da Poli vieram sem nenhum módulo. Elas tinham a "
            "forma certa, então a tabela mudou de layout ou a seção sumiu. NÃO "
            "leia isto como 'a Poli não tem módulo' — em 26/10 eram 50."
        )
    return Indice(tuple(modulos))


class CacheDoIndice:
    """O índice de um processo, por `TTL_INDICE`. Um só, e montado uma vez por
    vez: duas perguntas simultâneas não podem fazer 200 chamadas à USP."""

    def __init__(self, *, relogio=time.monotonic, ttl: int = TTL_INDICE):
        self._relogio = relogio
        self._ttl = ttl
        self._guardado: tuple[float, Indice] | None = None
        self._porta = threading.Lock()

    def obter(self, construir: Callable[[], Indice]) -> Indice:
        with self._porta:
            if self._guardado and self._relogio() - self._guardado[0] < self._ttl:
                return self._guardado[1]
            indice = construir()
            # Índice com módulo falho NÃO fica: a próxima pergunta tenta de novo,
            # em vez de responder sem aquele módulo por uma semana.
            if not any(m.falhou for m in indice.modulos):
                self._guardado = (self._relogio(), indice)
            return indice
