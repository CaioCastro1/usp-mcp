"""A ferramenta `modulos`: busca em linguagem natural e o texto da resposta.

**A busca roda aqui, não no modelo.** Ninguém pergunta por "3032/5080"; pergunta
por "o módulo de sistemas eletrônicos". Casar isso no servidor custa zero token,
e a regra que segura o custo é uma só: **em dúvida, candidato; grade só quando
a busca resolve para um módulo.** Uma ambiguidade nunca vira 50 grades.

**O casamento é o mínimo que passou na medição de 26/10:** sem acento e sem
caixa, sem palavra vazia, e toda palavra da busca é prefixo de alguma do alvo,
com folga de 2 letras para palavras de 6+ ("telecom" acha "telecomunicações",
"eletrônicos" acha "eletrônica"). Erro de digitação no meio da palavra não é
tratado de propósito: o modelo corrige digitação melhor, e de graça.

**Ressalva só quando o dado a produz** (Achado 1 de `notas/custo-em-token.md`):
o que vale sempre — só a Poli tem módulo, elegibilidade não sai daqui, o que é
O/C/L — está na descrição, que se paga uma vez por sessão.
"""
from __future__ import annotations

import re
import unicodedata

from .indice import Indice, Modulo

__all__ = ["normalizar", "casa", "e_sigla", "filtrar", "responder"]

# Artigos e preposições, mais as palavras que estão em todo nome e não
# discriminam nada: "engenharia" está em todos os 50.
_VAZIAS = frozenset({
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "em", "no", "na",
    "para", "com", "modulo", "modulos", "materia", "materias", "disciplina",
    "disciplinas", "engenharia",
})
_SIGLA = re.compile(r"^[A-Z0-9]{5,8}$")
_TRES_DIGITOS = re.compile(r"\d{3}")
_CODIGO = re.compile(r"^\s*(\d{4,5})\s*[/ ]\s*(\d{1,4})\s*$")

# Invariante 7: quando corta, diz quanto cortou.
TETO_CANDIDATOS = 20
TETO_DISCIPLINAS = 25


def normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _palavras(texto: str) -> list[str]:
    return [p for p in normalizar(texto).split() if len(p) > 1 and p not in _VAZIAS]


def _raiz(palavra: str) -> str:
    return palavra[:-2] if len(palavra) >= 6 else palavra


def casa(busca: str, alvo: str) -> bool:
    pedidas = _palavras(busca)
    if not pedidas:
        return False
    do_alvo = normalizar(alvo).split()
    return all(any(a.startswith(_raiz(p)) for a in do_alvo) for p in pedidas)


def e_sigla(texto: str) -> bool:
    compacto = "".join(texto.split()).upper()
    return bool(_SIGLA.match(compacto) and _TRES_DIGITOS.search(compacto))


def _so_vazias(busca: str) -> bool:
    return not _palavras(busca) and not _CODIGO.match(busca)


def filtrar(modulos, busca: str) -> list[Modulo]:
    codigo = _CODIGO.match(busca)
    if codigo:
        alvo = f"{codigo.group(1)}/{codigo.group(2)}"
        return [m for m in modulos if m.codigo == alvo]
    return [m for m in modulos if casa(busca, f"{m.nome} {m.curso}")]


# --- pedaços de texto --------------------------------------------------------

def _carga(m: Modulo) -> str:
    return f"{m.carga_total} h" if m.carga_total is not None else "carga não publicada"


def _divisao(m: Modulo) -> str:
    partes = [f"{rotulo} {valor}" for rotulo, valor in (
        ("obrigatória", m.carga_obrigatoria), ("eletiva", m.carga_eletiva),
        ("livre", m.carga_livre)) if valor]
    return " · ".join(partes)


def _semestre(s: int | None) -> str:
    return f"{s}º semestre ideal" if s is not None else "sem semestre ideal"


def _ressalvas(modulos) -> list[str]:
    por: dict[str, list[str]] = {}
    for m in modulos:
        por.setdefault(m.situacao, []).append(m.codigo)
    linhas = []
    if por.get("sem_grade"):
        n = len(por["sem_grade"])
        linhas.append(f"⚠ {n} com a grade vazia no Jupiter — só a carga foi publicada: "
                      f"{', '.join(por['sem_grade'])}.")
    if por.get("nao_publicado"):
        n = len(por["nao_publicado"])
        linhas.append(f"⚠ {n} sem grade nem carga publicadas no Jupiter: "
                      f"{', '.join(por['nao_publicado'])}.")
    if por.get("falhou"):
        n = len(por["falhou"])
        linhas.append(f"⚠ {n} não puderam ser lidos agora (o JupiterWeb falhou nesta "
                      f"consulta) e ficaram de fora: {', '.join(por['falhou'])}.")
    return linhas


# --- as cinco formas de resposta --------------------------------------------

def _ranking(indice: Indice) -> str:
    ms = indice.modulos
    linhas = [f"{len(ms)} módulos e percursos da Poli, por curso. Carga = horas que o "
              "currículo do módulo exige."]
    com_carga = [m for m in ms if m.carga_total is not None]
    if com_carga:
        menor = min(m.carga_total for m in com_carga)
        empatados = [m for m in com_carga if m.carga_total == menor]
        linhas.append("Menor carga: " + "; ".join(
            f"{menor} h — {m.nome_curto} ({m.codigo})" for m in empatados) + ".")
    grupos: dict[str, list[Modulo]] = {}
    for m in ms:
        grupos.setdefault(m.codcur, []).append(m)
    for codcur in sorted(grupos, key=lambda c: (grupos[c][0].curso or c, c)):
        membros = sorted(grupos[codcur], key=lambda m: (
            m.carga_total is None, m.carga_total or 0, m.nome_curto))
        linhas.append("")
        linhas.append(f"{membros[0].curso or 'Curso'} ({codcur})")
        for m in membros:
            divisao = _divisao(m)
            detalhe = f" ({divisao})" if divisao else ""
            n = len(m.disciplinas)
            linhas.append(f"  {_carga(m)}{detalhe}  {m.nome_curto} — {m.codigo}, "
                          f"{n} disc.")
    ressalvas = _ressalvas(ms)
    if ressalvas:
        linhas.append("")
        linhas.extend(ressalvas)
    return "\n".join(linhas)


def _um(m: Modulo) -> str:
    linhas = [f"{m.nome_curto} — {m.codigo} · curso: {m.curso or m.codcur}"]
    divisao = _divisao(m)
    carga = f"Carga exigida: {_carga(m)}" + (f" ({divisao})" if divisao else "")
    linhas.append(f"{carga}. {len(m.disciplinas)} disciplinas.")
    por_semestre: dict[int | None, list] = {}
    for d in m.disciplinas:
        por_semestre.setdefault(d.semestre, []).append(d)
    for s in sorted(por_semestre, key=lambda s: (s is None, s or 0)):
        linhas.append("")
        linhas.append(_semestre(s))
        for d in sorted(por_semestre[s], key=lambda d: (d.tipo, d.sigla)):
            linhas.append(f"  {d.tipo} {d.sigla} {d.nome} "
                          f"({d.creditos_aula}+{d.creditos_trabalho})")
    ressalvas = _ressalvas([m])
    if ressalvas:
        linhas.append("")
        linhas.extend(ressalvas)
    return "\n".join(linhas)


def _candidatos(busca: str, escolhidos: list[Modulo]) -> str:
    linhas = [f'"{busca}" casou com {len(escolhidos)} módulos. Peça um pelo código '
              "para ver as disciplinas:"]
    for m in sorted(escolhidos, key=lambda m: m.codigo)[:TETO_CANDIDATOS]:
        linhas.append(f"  {m.codigo} {m.nome_curto} — {_carga(m)} — {m.curso or m.codcur}")
    if len(escolhidos) > TETO_CANDIDATOS:
        linhas.append(f"  … e mais {len(escolhidos) - TETO_CANDIDATOS}. Refine a busca.")
    return "\n".join(linhas)


def _nenhum(busca: str, indice: Indice) -> str:
    cursos = sorted({(m.codcur, m.curso) for m in indice.modulos})
    linhas = [f'Nenhum módulo casou com "{busca}". Os cursos da Poli que têm módulo:']
    linhas.extend(f"  {codcur} {curso}".rstrip() for codcur, curso in cursos)
    linhas.append("Busque pelo nome do módulo, pelo curso ou pelo código (3032/5080).")
    return "\n".join(linhas)


def _por_disciplina(pedida: str, escopo: list[Modulo]) -> str:
    alcancados = [m for m in escopo if m.disciplinas]
    if e_sigla(pedida):
        sigla = "".join(pedida.split()).upper()
        achados = [(m, d) for m in alcancados for d in m.disciplinas if d.sigla == sigla]
        if achados:
            n = len({m.codigo for m, _ in achados})
            linhas = [f"{sigla} {achados[0][1].nome} — em {n} "
                      f"{'módulo' if n == 1 else 'módulos'}:"]
            linhas.extend(f"  {m.codigo} {m.nome_curto} ({d.tipo}, {_semestre(d.semestre)})"
                          for m, d in achados)
        else:
            parecidas = sorted({(d.sigla, d.nome) for m in alcancados for d in m.disciplinas
                                if d.sigla[-4:] == sigla[-4:] and d.sigla[:2] == sigla[:2]})
            linhas = [f"{sigla} não aparece em nenhum módulo da Poli."]
            if parecidas:
                linhas[0] += " Siglas parecidas que aparecem:"
                linhas.extend(f"  {s} {nome}" for s, nome in parecidas)
            else:
                linhas[0] += " Nenhuma sigla parecida aparece nos módulos."
    else:
        grupos: dict[str, tuple[str, list[Modulo]]] = {}
        for m in alcancados:
            for d in m.disciplinas:
                if casa(pedida, d.nome):
                    grupos.setdefault(d.sigla, (d.nome, []))[1].append(m)
        if not grupos:
            linhas = [f'Nenhuma disciplina dos módulos casou com "{pedida}".']
        else:
            linhas = [f'"{pedida}" casou com {len(grupos)} disciplinas dos módulos:']
            for sigla in sorted(grupos)[:TETO_DISCIPLINAS]:
                nome, ms = grupos[sigla]
                onde = ", ".join(f"{m.nome_curto} ({m.codigo})" for m in ms)
                linhas.append(f"  {sigla} {nome} — {onde}")
            if len(grupos) > TETO_DISCIPLINAS:
                linhas.append(f"  … e mais {len(grupos) - TETO_DISCIPLINAS}. Refine a busca.")
    fora = _ressalvas([m for m in escopo if m.situacao != "ok"])
    if fora:
        linhas.append("")
        linhas.append("A busca não alcança os módulos sem grade:")
        linhas.extend(fora)
    return "\n".join(linhas)


def responder(indice: Indice, *, busca: str = "", disciplina: str = "") -> str:
    escopo = list(indice.modulos)
    if busca.strip() and not _so_vazias(busca):
        escolhidos = filtrar(escopo, busca)
        if not escolhidos:
            return _nenhum(busca, indice)
        if not disciplina.strip():
            if len(escolhidos) == 1:
                return _um(escolhidos[0])
            return _candidatos(busca, escolhidos)
        escopo = escolhidos
    if disciplina.strip():
        return _por_disciplina(disciplina, escopo)
    return _ranking(indice)
