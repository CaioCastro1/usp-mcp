"""Allowlist do bean público do JupiterWeb (Invariante 2).

Duas camadas, e a segunda não é redundante.

**Consultas** — `ControlePublicoDWR.obter` e `.listar` recebem o nome da consulta
como PRIMEIRO PARÂMETRO. Isso é RPC genérico com nome em string, e a allowlist
existe porque o default tem que ser negar: quem escolhe a consulta é um modelo
interpretando linguagem ambígua.

**Métodos** — o bean expõe também `executarBatch`, `executar`, `obterArquivo`,
`obterRelatorio`, `obterCsv`, `obterPdf`, `obterZip`, `obterWebdoc` e
`obterProgresso` (§4.1 do recon, lidos na interface DWR servida em produção).
`executarBatch` é o análogo exato de `tool_mobile_call_external_functions`
registrado no §9 de 31/08: um executor genérico **anula qualquer filtro por nome
de consulta**, porque a consulta passa a viajar dentro do lote. Filtrar só
consulta não bloqueia nada se o método for livre.

Por isso o bloqueio de método é permanente e ignora `permitir_escrita`: não há
flag que libere (§2.2). E é o que garante que um erro futuro na lista de
consultas ainda não abra o caminho genérico.
"""
from __future__ import annotations

from dataclasses import dataclass

# Fatia vertical: a ficha da disciplina, e as duas consultas de navegação que
# marcam se um `codcur` é curso de ingresso (fatia de requisitos, 14/09).
# `pubListarRequisitoDisciplina` SAIU em 14/09: exigia um `codcur` que a API não
# deixa descobrir corretamente, e `requisitos(sigla)` responde sem ele (§9).
#
# A fatia de módulos (26/10) acrescentou duas: a grade de um currículo e a
# ficha dele (carga exigida). Elas entraram por uma pergunta registrada no §5 e
# por uma medição que desfez a de 14/09 — `tipo=V` responde onde `tipo=N` vinha
# vazio (§9, 26/10).
# Crescer isto é decisão registrada no §9, não conveniência.
CONSULTAS_PERMITIDAS: dict[str, str] = {
    "pubObterDisciplina": "obter",
    "pubListarCursoEntrada": "listar",
    "pubListarColegiado": "listar",
    "pubGradeCurricular": "listar",
    "pubObterInfoCursoWeb": "obter",
}

# A SEGUNDA superfície: GET de HTML no mesmo host, fora do DWR. Um buscador
# genérico de URL anularia a allowlist de consulta inteira — é o `executarBatch`
# de novo, por outra porta. Por isso o caminho também é allowlist, e não há flag
# que a dispense.
#
# `jupCursoLista` (26/10) é a lista de cursos de uma unidade: código, nome e
# período, sem pessoa. É o ÚNICO lugar onde os módulos aparecem — nenhuma
# consulta DWR lista os currículos "anteriores".
#
# `obterTurma` fica de fora e é o caso que mostra por quê: mesmo host, mesmo
# parâmetro (a sigla), e traz nome de professor e sala — 110 kB de dado que a
# fatia não pediu.
CAMINHOS_PERMITIDOS: frozenset[str] = frozenset({"listarCursosRequisitos", "jupCursoLista"})

# A fatia de requisitos (14/09) acrescentou duas consultas de navegação. Elas
# não respondem pergunta nenhuma sozinhas: servem para dizer se um `codcur` é
# curso de ingresso, e essa marca é o que impede "não consta" de virar
# "extinto" na saída.
#
# Os únicos métodos do bean que esta fatia usa.
METODOS_PERMITIDOS: frozenset[str] = frozenset({"obter", "listar"})

# §4.1 do recon: o resto da interface. Negado sempre, com ou sem flag.
BLOQUEIO_PERMANENTE: frozenset[str] = frozenset(
    {
        # o bypass: a consulta viaja dentro do lote e escapa de qualquer filtro
        "executarBatch",
        "executar",
        # exportadores: devolvem arquivo, não dado — custo imprevisível e sem
        # forma verificada na Fase 1
        "obterArquivo",
        "obterRelatorio",
        "obterCsv",
        "obterPdf",
        "obterZip",
        "obterWebdoc",
        "obterProgresso",
        # outro bean, nunca chamado na Fase 1: assinatura lida, não testada
        "recuperarProjetoPedagogico",
    }
)


@dataclass(frozen=True)
class Decisao:
    """Resultado de `decidir`. `motivo` existe para o Invariante 6: um `False`
    pelado não diz o que fazer com o resultado."""

    permitida: bool
    motivo: str


def decidir(metodo: str, consulta: str, permitir_escrita: bool = False) -> Decisao:
    """Decide se a dupla (método, consulta) pode sair para a USP.

    `permitir_escrita` é a flag do Invariante 1 e **não libera nada aqui**: o
    bloqueio de método ignora a flag por definição, e nenhuma consulta da fatia
    escreve. O parâmetro existe para deixar essa ausência de efeito explícita no
    call site, em vez de a política simplesmente não aceitar a flag.
    """
    if metodo in BLOQUEIO_PERMANENTE:
        return Decisao(
            permitida=False,
            motivo=(
                f"método {metodo} está no bloqueio permanente — negado mesmo com "
                "permitir_escrita=True, pois não há flag que libere. Um executor "
                "genérico anula o filtro por nome de consulta."
            ),
        )

    if metodo not in METODOS_PERMITIDOS:
        return Decisao(
            permitida=False,
            motivo=f"método {metodo} não está na allowlist — o default é negar.",
        )

    if consulta not in CONSULTAS_PERMITIDAS:
        return Decisao(
            permitida=False,
            motivo=(
                f"consulta {consulta} não é uma das que esta ferramenta faz ao "
                f"JupiterWeb (a lista é fechada: {len(CONSULTAS_PERMITIDAS)} consultas)."
            ),
        )

    esperado = CONSULTAS_PERMITIDAS[consulta]
    if esperado != metodo:
        return Decisao(
            permitida=False,
            motivo=f"{consulta} é servida por '{esperado}', não por '{metodo}'.",
        )

    return Decisao(permitida=True, motivo=f"{consulta} via {metodo}.")


def decidir_caminho(caminho: str) -> Decisao:
    """Decide se um caminho HTML do JupiterWeb pode ser buscado.

    Sem `permitir_escrita`: GET de página pública não escreve, e uma flag aqui
    só serviria para dar a impressão de que existe caminho liberável.
    """
    if caminho in CAMINHOS_PERMITIDOS:
        return Decisao(permitida=True, motivo=f"{caminho} está na allowlist de caminho.")
    return Decisao(
        permitida=False,
        motivo=(
            f"caminho {caminho} não é uma das páginas que esta ferramenta lê no "
            f"JupiterWeb (a lista é fechada: {len(CAMINHOS_PERMITIDOS)} caminhos)."
        ),
    )
