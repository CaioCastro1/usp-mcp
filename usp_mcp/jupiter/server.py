"""Fronteira MCP do Jupiter (§6 do SPEC1).

O pacote não tem servidor na raiz de propósito: o do Moodle é o entrypoint
LOCAL, porque carrega credencial pessoal que não pode sair da máquina do dono
(Invariante 4). **Este não carrega credencial nenhuma** — o `ControlePublicoDWR`
é público e stateless — e é justamente por isso que o §6 o coloca como candidato
a servidor hospedado, com cache compartilhado. Hoje ele fala stdio porque é a
mesma canalização do cliente; a opção de hospedar continua aberta, e continua
aberta *porque* não há segredo para vazar.

A camada é fina de propósito. O valor está na política (`politica.py`), no
envelope (`dwr.py`) e na ferramenta (`ferramentas.py`) — nada disso tem a ver
com protocolo MCP. `listar_ferramentas` e `chamar_ferramenta` são funções puras
que qualquer adaptador chama sem o SDK instalado; `main()` é a casca stdio, e
só ela importa o SDK — import de topo quebraria a suíte, que roda sem ele.

Uma coisa esta fronteira consegue e a do Moodle não: **ser testada ponta a ponta
offline.** Sem credencial, basta injetar o transporte e a fixture responde.
"""
from __future__ import annotations

from ..anotacoes import SO_LEITURA, para_o_sdk
from .cliente import ClienteJupiter, transporte_http
from .erros import ErroJupiter
from .ferramentas import agrupar_curriculos, disciplina, requisitos, resolver_secoes
from . import modulos as _modulos
from .indice import CacheDoIndice, montar_indice

_NOME_FERRAMENTA = "disciplina"
_NOME_REQUISITOS = "requisitos"
_NOME_MODULOS = "modulos"
_NOMES = (_NOME_FERRAMENTA, _NOME_REQUISITOS, _NOME_MODULOS)

# O índice dos módulos vive o processo inteiro (7 dias de validade). As outras
# duas ferramentas montam cliente novo por chamada; esta não pode, porque o
# índice custa 102 requisições.
_CACHE_MODULOS = CacheDoIndice()


def listar_ferramentas() -> list[dict]:
    """Descreve a ferramenta como o MODELO a vê.

    A descrição usa o vocabulário de quem pergunta — "créditos", "ementa",
    "pré-requisito", a sigla que o aluno já sabe — e nunca o nome da consulta
    DWR por trás. É isso que faz o modelo escolher a ferramenta certa diante de
    uma pergunta em português.
    """
    return [
        {
            "name": _NOME_FERRAMENTA,
            "description": (
                "Ficha de uma disciplina no catálogo público do JupiterWeb (USP), "
                "pela sigla: nome, créditos e carga horária sempre, e sob pedido "
                "ementa, objetivos, programa, bibliografia e avaliação. Use para "
                "'quantos créditos tem PTC3314', 'qual a ementa de MAT2454', 'o "
                "que cai em PME3344' (programa), 'como é a avaliação'. Por padrão "
                "vem só nome, créditos e ementa — peça as outras partes em "
                "`secoes`. Para pré-requisito use a ferramenta `requisitos`. NÃO "
                "traz horário de aula, sala nem vagas, e não busca por nome: "
                "precisa da sigla."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sigla": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina, como aparece no JupiterWeb — "
                            "por exemplo PTC3314 ou MAT2454. Espaço e caixa não "
                            "importam."
                        ),
                    },
                    "secoes": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "ementa", "objetivos", "programa",
                                "bibliografia", "avaliacao", "todas",
                            ],
                        },
                        "description": (
                            "Quais partes da ficha vir além de nome, créditos e "
                            "carga horária. Padrão: só a ementa. 'avaliacao' "
                            "junta método, critério e recuperação; 'objetivos' e "
                            "'programa' são os textos mais longos. Use ['todas'] "
                            "para a ficha inteira."
                        ),
                        "default": ["ementa"],
                    },
                    "ingles": {
                        "type": "boolean",
                        "description": (
                            "Inclui as versões em inglês dos textos. Padrão "
                            "falso: elas quase dobram o tamanho da resposta."
                        ),
                        "default": False,
                    },
                },
                "required": ["sigla"],
                "additionalProperties": False,
            },
            # Catálogo público, e o DWR por trás só tem consulta: não existe
            # rota que matricule, tranque ou altere nada. A razão de cada campo
            # de `SO_LEITURA` mora ao lado dele.
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_REQUISITOS,
            "description": (
                "O que é preciso ter cursado antes de uma disciplina da USP, "
                "pela sigla. A resposta vem POR CURRÍCULO, porque a exigência "
                "depende do currículo e não só da disciplina: a mesma matéria "
                "pode ser requisito duro num curso e 'fraco' (dá para "
                "matricular devendo) em outro, ou correquisito (cursa junto). "
                "Use para 'o que preciso ter feito antes de PTC3314', 'posso "
                "pegar essas duas juntas', 'dá pra me matricular devendo'. NÃO "
                "traz horário, sala nem vagas, e não sabe em que currículo "
                "você está — ela mostra todos e diz qual é curso de ingresso."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sigla": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina — PTC3314, MAT2455. Os "
                            "currículos novos usam código só de dígitos, como "
                            "2000101, e ele funciona igual."
                        ),
                    },
                },
                "required": ["sigla"],
                "additionalProperties": False,
            },
            # Mesma leitura do mesmo catálogo público, por outro recorte.
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_MODULOS,
            "description": (
                "Os módulos de formação da Escola Politécnica (Poli-USP) e os "
                "Percursos Formativos, pelo catálogo público do JupiterWeb. Sem "
                "argumentos: todos, agrupados por curso, com a carga horária "
                "exigida e o de menor carga no topo. Com `busca` (nome do módulo, "
                "do curso, ou o código como 3032/5080): se casar um só, as "
                "disciplinas dele por semestre ideal, com tipo (O obrigatória, C "
                "optativa eletiva, L optativa livre) e créditos aula+trabalho; se "
                "casar vários, só a lista para escolher. Com `disciplina` (sigla "
                "ou pedaço do nome): em que módulos ela aparece. Use para 'qual "
                "módulo tem menor carga', 'que módulos a Elétrica tem', 'que "
                "matérias tem o módulo de sistemas eletrônicos', 'algum módulo tem "
                "PMR3508'. Só a Poli tem módulo na USP. NÃO diz quais módulos você "
                "pode escolher: isso depende da sua ênfase e de regras da comissão "
                "de curso que o Jupiter não publica. A primeira pergunta da sessão "
                "demora uns 20 s; as seguintes são imediatas."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "busca": {
                        "type": "string",
                        "description": (
                            "Nome do módulo, do curso ou o código (3032/5080). "
                            "Acento e maiúscula não importam: 'sistemas "
                            "eletronicos', 'telecom', 'pre-mestrado eletrica'. "
                            "Vazio lista todos."
                        ),
                        "default": "",
                    },
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla (PMR3508) ou pedaço do nome ('aprendizado de "
                            "maquina') de uma disciplina: diz em que módulos ela "
                            "aparece."
                        ),
                        "default": "",
                    },
                },
                "additionalProperties": False,
            },
            # Mesma leitura do mesmo catálogo público.
            "annotations": SO_LEITURA,
        },
    ]


# O tipo da exigência, em português de quem vai se matricular. Verificado
# contra o HTML do JupiterWeb em 3 pares (§9, 14/09): `CR` é "Indicação de
# Conjunto", e chamá-lo de pré-requisito faz o aluno adiar a matrícula por um
# ano. `stamtrrcp="S"` é o "Requisito fraco" da página.
def rotulo_de(exigencia: dict) -> str:
    if exigencia.get("tipo") == "CR" or exigencia.get("tipo") == "correquisito":
        return "Correquisito (cursa junto)"
    if exigencia.get("fraco") or exigencia.get("tipo") == "requisito_fraco":
        return "Requisito fraco (dá para matricular devendo)"
    if exigencia.get("tipo") in ("PR", "requisito", None):
        return "Pré-requisito"
    return f"Exigência ({exigencia['tipo']})"


_ROTULOS = (
    ("ementa", "Ementa"),
    ("objetivos", "Objetivos"),
    ("programa", "Conteúdo programático"),
    ("bibliografia", "Bibliografia"),
    ("metodo_avaliacao", "Método de avaliação"),
    ("criterio_avaliacao", "Critério de avaliação"),
    ("norma_recuperacao", "Norma de recuperação"),
    ("nome_en", "Nome (inglês)"),
    ("ementa_en", "Ementa (inglês)"),
    ("objetivos_en", "Objetivos (inglês)"),
    ("programa_en", "Conteúdo programático (inglês)"),
)


def formatar(ficha: dict) -> str:
    """Texto para o modelo ler. Curto no topo, prosa depois.

    A carga horária aparece com a conta à vista de propósito: ela é calculada,
    não lida, e deixar isso explícito é o que impede alguém de "corrigir" para
    o campo `cgahoreto` — que vale zero.
    """
    linhas = [
        f"{ficha['sigla']} — {ficha['nome']}",
        f"Créditos: {ficha['creditos_aula']} aula + {ficha['creditos_trabalho']} "
        f"trabalho · Carga horária: {ficha['carga_horaria_total']} h "
        f"({ficha['creditos_aula']}×15 + {ficha['creditos_trabalho']}×30)",
        f"Tipo: {ficha['tipo']} · Ativação: {ficha['ativacao']}",
    ]

    for campo, rotulo in _ROTULOS:
        if ficha.get(campo):
            linhas.append(f"\n{rotulo}:\n{ficha[campo]}")

    # Invariante 7 na ficha: o que não veio é dito, para o modelo saber que
    # existe mais e como pedir.
    if ficha.get("secoes_omitidas"):
        linhas.append(
            "\n(Seções não incluídas: " + ", ".join(ficha["secoes_omitidas"])
            + '. Peça-as em secoes, ou secoes=["todas"].)'
        )

    # Invariante 7: o que a ferramenta NÃO sabe vai junto, nunca por omissão.
    for aviso in ficha.get("avisos") or ():
        linhas.append(f"\n⚠ {aviso}")

    return "\n".join(linhas)


def _cabecalho_do_grupo(chave: tuple) -> str:
    """As exigências de um grupo, agrupadas por rótulo: `Rótulo: A — nome; B — nome`."""
    if not chave:
        return "• (a página não traz linha de exigência para estes)"
    por_rotulo: dict[str, list[str]] = {}
    for sigla, nome, tipo, _rotulo in chave:
        por_rotulo.setdefault(rotulo_de({"tipo": tipo}), []).append(f"{sigla} — {nome}")
    return "• " + " | ".join(f"{r}: {'; '.join(itens)}" for r, itens in por_rotulo.items())


def _linha_do_curriculo(c: dict) -> str:
    marca = " [curso de ingresso]" if c["ingresso"] else ""
    return (
        f"    {c['codcur']} {c['habilitacao']} "
        f"({c['periodo']}, {c['periodo_ideal']}º período ideal){marca}"
    )


def formatar_requisitos(ficha: dict) -> str:
    """Texto para o modelo ler, agrupado por COMBINAÇÃO de exigências.

    O agrupamento não é estética: o tipo da exigência é propriedade do currículo
    (MAT2454 é dura em Minas e fraca em Elétrica), e a chave do grupo carrega o
    tipo — 3250 fica sozinho justamente por isso. O que sai é a repetição: em
    MAT2455, 18 dos 23 currículos tinham as mesmas duas linhas (§9, 14/09).
    """
    curriculos = ficha["curriculos"]
    # Sem currículo, o cabeçalho prometeria uma lista que não vem — e promessa
    # não cumprida na primeira linha é o que faz o modelo preencher o resto.
    if not curriculos:
        linhas = [f"Não há exigência listada para {ficha['sigla']} — leia o aviso:"]
    else:
        grupos = agrupar_curriculos(curriculos)
        if len(curriculos) == 1:
            linhas = [f"Exigências para cursar {ficha['sigla']}, por currículo:"]
        else:
            linhas = [
                f"Exigências para cursar {ficha['sigla']} — {len(curriculos)} "
                f"currículos, {len(grupos)} combinações diferentes:"
            ]
        for chave, membros in grupos:
            linhas.append("")
            linhas.append(_cabecalho_do_grupo(chave))
            linhas.extend(_linha_do_curriculo(c) for c in membros)

    for aviso in ficha.get("avisos") or ():
        linhas.append(f"\n⚠ {aviso}")

    return "\n".join(linhas)


def chamar_ferramenta(nome: str, argumentos: dict, *, cliente=None) -> str:
    """Despacha para a ferramenta pedida, ou levanta erro legível.

    Nome desconhecido levanta `ErroJupiter` citando o nome pedido: "ferramenta
    não existe" e "ferramenta existe mas não achou nada" têm curas diferentes
    para quem lê o erro, e devolver vazio confundiria os dois (Invariante 6).

    `cliente` é injetável — sem credencial, a fronteira inteira roda offline
    contra fixture. É a diferença entre esta e a do Moodle.
    """
    if nome not in _NOMES:
        raise ErroJupiter(
            f"Ferramenta desconhecida: {nome!r}. As ferramentas expostas por "
            f"este servidor são {', '.join(repr(n) for n in _NOMES)}."
        )

    if nome == _NOME_MODULOS:
        if cliente is None:
            indice = _CACHE_MODULOS.obter(
                lambda: montar_indice(ClienteJupiter(transporte_http))
            )
        else:
            indice = montar_indice(cliente)
        return _modulos.responder(
            indice,
            busca=argumentos.get("busca") or "",
            disciplina=argumentos.get("disciplina") or "",
        )

    if cliente is None:
        # Nenhuma credencial é montada aqui, e não há env de segredo a ler:
        # o bean é público e stateless (§4.4 do recon, verificado).
        cliente = ClienteJupiter(transporte_http)

    if nome == _NOME_REQUISITOS:
        return formatar_requisitos(requisitos(argumentos["sigla"], cliente=cliente))

    idiomas = ("pt", "en") if argumentos.get("ingles") else ("pt",)
    return formatar(
        disciplina(
            argumentos["sigla"], cliente=cliente,
            secoes=resolver_secoes(argumentos.get("secoes")), idiomas=idiomas,
        )
    )


def main() -> None:
    """Adaptador stdio real. O import do SDK fica aqui dentro, não no topo: a
    suíte importa este módulo sem o SDK instalado, e um import de topo quebraria
    a coleta por causa de uma dependência que as funções puras nem usam.

    **Tem teste, por dois caminhos que não se substituem.** T45-T48
    (`tests/jupiter/test_server_stdio.py`) rodam isto em processo, substituindo
    só `run()`, e alcançam o que o processo esconde: o corpo enviado e a
    mensagem de SDK ausente. `tests/handshake/` sobe o processo de verdade e
    compara o que sai NO FIO com o que `listar_ferramentas()` declara — foi lá
    que apareceu o schema mais pobre que o declarado. Foi este buraco que, na
    trilha do Moodle, escondeu um `main()` falando a API antiga do SDK com a
    suíte inteira verde.

    **E por um terceiro desde 10/09/2026.** E1-E4
    (`tests/jupiter/test_erro_no_fio.py`) olham a MENSAGEM DE ERRO no fio, que
    nenhum dos dois alcançava: os dois exercitam o caminho feliz e o handshake,
    e a fronteira ficou muda por uma versão inteira do SDK sem ninguém ver.
    """
    try:
        from mcp.server import MCPServer
        # `ToolError` existe no 2.0.0 e no 2.2.0, e entra no MESMO try: sem o
        # SDK, quem responde é a mensagem legível abaixo, não um traceback.
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError as exc:
        raise SystemExit(
            "O SDK do MCP (pacote `mcp`) não está instalado. Rode "
            "`.venv/bin/python -m pip install -r requirements.txt`. As funções "
            "`listar_ferramentas` e `chamar_ferramenta` funcionam sem ele."
        ) from exc

    from typing import Literal

    from usp_mcp.adaptador import anotar

    # Por nome, nunca por índice. `listar_ferramentas()[0]` registrava só a
    # primeira: a segunda ferramenta ficava DECLARADA e não anunciada, e quem
    # pegou isso foi o handshake — a suíte em processo estava verde.
    por_nome = {f["name"]: f for f in listar_ferramentas()}
    servidor = MCPServer(name="usp-mcp-jupiter", version="1.1.0")

    # Sem decorator de tradução de erro, por mais tentador que seja: o SDK
    # deriva o schema da ASSINATURA, e um wrapper `*args/**kwargs` faz o modelo
    # ver uma ferramenta de dois parâmetros chamados `args` e `kwargs`. Medido
    # pelo handshake H6/H7 ao tentar exatamente isso. A duplicação do `except`
    # é o preço da assinatura honesta.
    #
    # `ToolError` é o canal que o SDK define para "falha prevista, a mensagem é
    # para o modelo ler" — sem ele, o 2.2.0 classifica `ErroJupiter` como crash
    # e entrega 31 bytes de `Error executing tool` (medido em 10/09/2026),
    # jogando fora a frase que a `JupiterErro` extraiu dos 46 frames do Tomcat.
    # Só `ErroJupiter` é traduzido: `except Exception` devolveria o stack trace
    # que aquela classe existe para descartar, 116x o custo.

    def _disciplina(sigla, secoes=None, ingles=False) -> str:
        # Assinatura explícita em vez de **kwargs: o SDK deriva daqui o schema
        # que o modelo vê, e **kwargs produziria ferramenta sem parâmetro.
        try:
            return chamar_ferramenta(
                _NOME_FERRAMENTA, {"sigla": sigla, "secoes": secoes, "ingles": ingles}
            )
        except ErroJupiter as exc:
            raise ToolError(str(exc)) from exc

    def _requisitos(sigla) -> str:
        try:
            return chamar_ferramenta(_NOME_REQUISITOS, {"sigla": sigla})
        except ErroJupiter as exc:
            raise ToolError(str(exc)) from exc

    def _modulos_mcp(busca="", disciplina="") -> str:
        try:
            return chamar_ferramenta(
                _NOME_MODULOS, {"busca": busca, "disciplina": disciplina}
            )
        except ErroJupiter as exc:
            raise ToolError(str(exc)) from exc

    # O SDK lê a ASSINATURA, não o inputSchema declarado (§9, 31/08/2026): sem
    # isto, o aviso de que sem `codcur` não há pré-requisito não chega ao modelo.
    anotar(
        _disciplina,
        por_nome[_NOME_FERRAMENTA]["inputSchema"],
        {
            "sigla": str,
            "secoes": list[Literal[
                "ementa", "objetivos", "programa", "bibliografia", "avaliacao", "todas"
            ]] | None,
            "ingles": bool,
        },
    )
    anotar(_requisitos, por_nome[_NOME_REQUISITOS]["inputSchema"], {"sigla": str})
    anotar(_modulos_mcp, por_nome[_NOME_MODULOS]["inputSchema"],
           {"busca": str, "disciplina": str})

    for descritor, funcao in (
        (por_nome[_NOME_FERRAMENTA], _disciplina),
        (por_nome[_NOME_REQUISITOS], _requisitos),
        (por_nome[_NOME_MODULOS], _modulos_mcp),
    ):
        # `annotations` sai do MESMO descritor que a descrição e o schema, e o
        # laço garante que ferramenta nova não fique de fora por esquecimento:
        # quem entra na tupla acima entra anotada. Quem obriga o bloco do
        # descritor e o que sai no fio a concordarem é o A6.
        servidor.tool(
            name=descritor["name"],
            description=descritor["description"],
            annotations=para_o_sdk(descritor),
        )(funcao)

    servidor.run(transport="stdio")


def _auto_verificar() -> int:  # pragma: no cover — utilitário de linha de comando
    """`python -m usp_mcp.jupiter.server --auto-verificar`: o que dá para checar
    sem tocar a rede da USP."""
    print("ferramentas expostas :", [f["name"] for f in listar_ferramentas()])
    print("credencial exigida   : NENHUMA (bean público e stateless)")

    try:
        from mcp.server import MCPServer as _M
    except ImportError:
        print("SDK do MCP           : AUSENTE — pip install -r requirements.txt")
        return 1
    print("SDK do MCP           : presente")

    import inspect

    servidor = _M(name="verificacao", version="0.0.0")

    @servidor.tool(name="disciplina", description="verificação")
    def _sonda_disciplina(sigla: str, secoes: list[str] | None = None,
                          ingles: bool = False) -> str:
        return ""

    @servidor.tool(name="requisitos", description="verificação")
    def _sonda_requisitos(sigla: str) -> str:
        return ""

    @servidor.tool(name="modulos", description="verificação")
    def _sonda_modulos(busca: str = "", disciplina: str = "") -> str:
        return ""

    # Uma sonda por ferramenta declarada, nunca só a [0]: foi esse índice que
    # deixou a segunda ferramenta declarada e não anunciada em 14/09.
    sondas = {"disciplina": _sonda_disciplina, "requisitos": _sonda_requisitos,
              "modulos": _sonda_modulos}
    tudo_ok = True
    for ferramenta in listar_ferramentas():
        declarados = set(ferramenta["inputSchema"]["properties"])
        sonda = sondas.get(ferramenta["name"])
        reais = set(inspect.signature(sonda).parameters) if sonda else set()
        ok = declarados == reais
        tudo_ok = tudo_ok and ok
        print(f"schema x assinatura  : {ferramenta['name']:11}",
              "OK" if ok else f"DIVERGEM {declarados ^ reais}")
    return 0 if tudo_ok else 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    if "--auto-verificar" in sys.argv:
        raise SystemExit(_auto_verificar())
    main()
