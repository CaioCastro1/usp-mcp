"""Fronteira MCP do RUCard (§6 do SPEC1).

O servidor mora dentro do subpacote, nunca na raiz: o §6 separa entrypoint local
com credencial pessoal (Moodle, stdio) de servidor público cacheável, e a
estrutura reflete isso em vez de deixar a separação só na prosa.

**Este é o mais hospedável dos três.** A hash do RUCard é compartilhada e
embutida no app oficial: ninguém manda credencial, o cache é compartilhável e o
dado é público. Hoje ele fala stdio porque é a mesma canalização dos outros
dois; a opção de hospedar continua aberta, e continua aberta *porque* não há
segredo para vazar (há teste de política que falha se isso mudar).

A camada é fina de propósito. O valor está na política, na projeção do catálogo
e na ferramenta. `listar_ferramentas` e `chamar_ferramenta` são funções puras que
qualquer adaptador chama sem o SDK instalado; `main()` é a casca stdio, e só ela
importa o SDK — import de topo quebraria a suíte, que roda sem ele.
"""
from __future__ import annotations

from ..anotacoes import SO_LEITURA, para_o_sdk
from .cliente import ClienteRucard, transporte_http
from .erros import ErroRucard
from .ferramentas import SEMANA, bandejao, bandejao_semana

_NOME_FERRAMENTA = "bandejao"

_ROTULO = {"cafe": "café da manhã", "almoco": "almoço", "jantar": "jantar"}


def listar_ferramentas() -> list[dict]:
    """Descreve a ferramenta como o MODELO a vê.

    A descrição usa o vocabulário de quem pergunta — "bandejão", "almoço",
    "hoje", "vegetariana" — e nunca o nome da rota por trás. É isso que faz o
    modelo escolher esta ferramenta diante de uma pergunta em português em vez
    de sair procurando na web.

    E ela diz o que NÃO faz (Invariante 7 aplicado à descrição): sem isso o
    modelo promete café da manhã, cardápio de semana passada e saldo do cartão,
    que são três coisas que esta API não dá.
    """
    return [
        {
            "name": _NOME_FERRAMENTA,
            "description": (
                "Cardápio dos bandejões da USP na Cidade Universitária — Central, "
                "Prefeitura (PUSP-CB), Física e Químicas. Diz o que tem no almoço "
                "e no jantar de um dia, com calorias, preço de aluno, horário e a "
                "opção do dia (marcada como vegetariana quando o RU marca), nos "
                "quatro restaurantes de uma vez, para comparar onde vale a pena "
                "comer. Com dia='semana' traz os sete dias numa chamada só. Use "
                "para 'o que tem no bandejão hoje', 'o que tem na sexta?', 'que "
                "dia tem lasanha essa semana?', 'vale a pena almoçar na "
                "Prefeitura?', 'que horas fecha o jantar', 'o das Químicas abre "
                "no sábado?'. LIMITES: só a semana corrente (não há cardápio de "
                "outra semana, nem passada nem futura); não há cardápio de café "
                "da manhã publicado, só o horário; e nada de saldo, extrato ou "
                "recarga do cartão."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dia": {
                        "type": "string",
                        "description": (
                            "'hoje', 'amanhã', um dia da semana ('sexta', "
                            "'sábado'), 'semana' para os sete dias de segunda a "
                            "domingo, ou uma data como 26/08/2026. Nome de dia é "
                            "o dessa semana, mesmo que já tenha passado: só a "
                            "semana corrente tem cardápio."
                        ),
                        "default": "hoje",
                    },
                    "refeicao": {
                        "type": "string",
                        "enum": ["almoco", "jantar", "cafe", "todas"],
                        "description": (
                            "Qual refeição. 'todas' traz almoço e jantar. "
                            "'cafe' responde o horário e diz que o cardápio não "
                            "é publicado."
                        ),
                        "default": "todas",
                    },
                    "restaurantes": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["central", "prefeitura", "fisica", "quimicas"],
                        },
                        "description": (
                            "Quais bandejões: central (Central), prefeitura "
                            "(PUSP-CB, o da Prefeitura do campus), fisica "
                            "(Física), quimicas (Químicas). Omita para comparar "
                            "os quatro."
                        ),
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            # Cardápio é consulta e nada mais: não há rota de escrita nesta API,
            # e a política deste servidor já proíbe saldo, extrato e recarga.
            # A razão de cada campo de `SO_LEITURA` mora ao lado dele.
            "annotations": SO_LEITURA,
        }
    ]


_SEP_ITENS = " · "


def _rodape_quase(item: str, faltam: list[str]) -> str:
    """A linha do item quase-comum. Nomear as exceções não é enfeite: sem elas,
    "em quase todas" deixa quem lê sem saber a quais refeições a linha se
    aplica, e um recorte que não se declara é limite silencioso."""
    return f"Em quase todas: {item} — não em {', '.join(faltam)}"


def fatorar(refeicoes: list[tuple[str, dict]]) -> tuple[set[str], list[tuple[str, list[str]]]]:
    """Itens que saem das linhas e sobem para o rodapé, em dois grupos.

    Devolve `(comuns, quase)`: os presentes em TODAS as refeições abertas, e uma
    lista de `(item, rótulos das refeições que NÃO o têm)`. Com menos de duas
    refeições não há o que fatorar. A projeção estruturada não muda: isto é só
    texto.

    **A regra estrita sozinha deixava passar o caso mais caro.** Até 22/09/2026
    só existia a interseção, e o argumento escrito aqui era que "na maioria"
    exigiria marcar exceções e o ganho (~20 B por refeição) não pagava a
    complexidade. O que mudou foi a escala do caso semanal, medida depois: a
    semana custa 8.018 B, 88% disso em linhas de cardápio, e o arroz sozinho são
    1.085 B — 14% do texto. Ele escapa da interseção por um detalhe de grafia,
    `Arroz / feijão / arroz integral` em 32 das 38 refeições abertas e
    `Arroz / feijão preto / arroz integral` nas outras 6.

    **E o critério não é proporção, é custo.** Nenhum limiar de "maioria" foi
    escolhido a dedo: o item sobe quando o que ele economiza nas linhas paga a
    linha de rodapé que o nomeia com as exceções — a mesma conta que faria à
    mão quem estivesse decidindo. É isso que impede a regra de piorar o texto
    quando as exceções são muitas ou o item é curto, e é isso que responde à
    objeção original: a complexidade que não se pagava está numa conta de duas
    linhas, e ela se recusa sozinha quando não vale.

    A economia é estimada em `n × (item + separador)`, o que ignora o caso em
    que o item era o único da linha. Estimativa para MAIS trabalho, nunca para
    menos texto: errar aqui adia uma fatoração, não esconde um item.
    """
    abertas = [
        (rotulo, set(dados["itens"]))
        for rotulo, dados in refeicoes
        if dados.get("situacao") == "aberto" and dados.get("itens")
    ]
    if len(abertas) < 2:
        return set(), []

    comuns = set.intersection(*(itens for _, itens in abertas))

    quase: list[tuple[str, list[str]]] = []
    for item in sorted({i for _, itens in abertas for i in itens} - comuns):
        faltam = [rotulo for rotulo, itens in abertas if item not in itens]
        presentes = len(abertas) - len(faltam)
        if presentes < 2:
            continue
        economia = presentes * len((item + _SEP_ITENS).encode())
        custo = len(_rodape_quase(item, faltam).encode()) + 1
        if economia > custo:
            quase.append((item, faltam))
    return comuns, quase


def _rodape(comuns: set[str], quase: list[tuple[str, list[str]]]) -> list[str]:
    linhas = []
    if comuns:
        linhas.append("Em todas as refeições acima: " + _SEP_ITENS.join(sorted(comuns)))
    linhas.extend(_rodape_quase(item, faltam) for item, faltam in quase)
    return linhas


def _linha_da_refeicao(nome_ru: str, qual: str, dados: dict,
                       fora_da_linha=frozenset()) -> list[str]:
    rotulo = _ROTULO[qual]
    situacao = dados["situacao"]

    if situacao != "aberto":
        return [f"{nome_ru} · {rotulo}: {dados.get('detalhe') or situacao}"]

    cabecalho = [f"{nome_ru} · {rotulo}"]
    if dados.get("horario"):
        cabecalho.append(dados["horario"])
    if dados.get("preco_aluno"):
        cabecalho.append(f"R$ {dados['preco_aluno']} (aluno)")
    if dados.get("calorias"):
        cabecalho.append(f"{dados['calorias']} kcal")

    linhas = [" · ".join(cabecalho)]
    # Itens numa linha só, separados por ' · ': sete itens por refeição em
    # quatro RUs seriam 56 linhas, e o teto de custo (R37b) existe para impedir
    # que a formatação engorde sem ninguém ver.
    itens = [i for i in dados.get("itens") or () if i not in fora_da_linha]
    if itens:
        linhas.append("  " + " · ".join(itens))
    if dados.get("opcao"):
        marca = " [marcada como vegetariana]" if dados.get("opcao_vegetariana_marcada") else ""
        linhas.append(f"  Opção: {dados['opcao']}{marca}")
    return linhas


def formatar(resposta: dict) -> str:
    """Texto para o modelo ler. Compacto, e com o que não se sabe no fim."""
    linhas = [f"Bandejão — {resposta['dia_semana']} {resposta['data']}"]

    refeicoes = [
        (f"{ru['nome']} {_ROTULO[qual]}", ru["refeicoes"][qual])
        for ru in resposta["restaurantes"]
        for qual in resposta["refeicoes"]
        if ru["refeicoes"].get(qual)
    ]
    comuns, quase = fatorar(refeicoes)
    fora_da_linha = comuns | {item for item, _ in quase}

    for ru in resposta["restaurantes"]:
        for qual in resposta["refeicoes"]:
            dados = ru["refeicoes"].get(qual)
            if dados:
                linhas.extend(_linha_da_refeicao(ru["nome"], qual, dados, fora_da_linha))

    linhas.extend(_rodape(comuns, quase))

    # Invariante 7: o que a ferramenta NÃO sabe vai junto, nunca por omissão.
    for aviso in resposta.get("avisos") or ():
        linhas.append(f"⚠ {aviso}")

    return "\n".join(linhas)


# Situação de refeição não aberta, numa palavra: na semana são até 28 linhas de
# dia, e a frase inteira do `detalhe` em cada uma custaria mais que o cardápio.
# O detalhe continua na projeção estruturada.
_SITUACAO_CURTA = {
    "nao_serve": "não serve",
    "fechado": "fechado",
    "indisponivel": "indisponível",
    "sem_cardapio_publicado": "sem cardápio publicado",
}


def _horario_comum(dias: list[dict], id_ru: str, qual: str) -> str | None:
    """O horário sobe pro cabeçalho do RU quando é o MESMO em todo dia aberto da
    semana — é o mesmo desperdício que a fatoração de itens corrige, e a mesma
    regra estrita: só com um único valor entre os abertos. O jantar do 9 varia
    (19:45 em dia útil, 19:00 no sábado) e por isso continua na linha do dia."""
    horarios = {
        ru["refeicoes"][qual]["horario"]
        for d in dias
        for ru in d["restaurantes"]
        if ru["id"] == id_ru and ru["refeicoes"].get(qual, {}).get("situacao") == "aberto"
    }
    return horarios.pop() if len(horarios) == 1 else None


def formatar_semana(resposta: dict) -> str:
    """Texto da semana para o modelo ler: um bloco por RU e refeição, um dia por
    linha. Horário sobe pro cabeçalho quando é o mesmo em toda a semana; quando
    varia entre dias (o 9 fecha o jantar às 19:45 em dia útil e às 19:00 no
    sábado) continua na linha do dia — um valor só no cabeçalho mentiria."""
    linhas = [f"Bandejão — semana de {resposta['inicio']} a {resposta['fim']}"]
    dias = resposta["dias"]
    refeicoes_pedidas = resposta["refeicoes"]

    todas = [
        (f"{d['dia_semana']} {ru['nome']} {_ROTULO[qual]}", ru["refeicoes"][qual])
        for d in dias
        for ru in d["restaurantes"]
        for qual in refeicoes_pedidas
        if ru["refeicoes"].get(qual)
    ]
    comuns, quase = fatorar(todas)
    fora_da_linha = comuns | {item for item, _ in quase}

    # A ordem dos RUs é a do primeiro dia em que cada um aparece: um RU pode
    # faltar num dia (semana não publicada) sem sumir do texto.
    ordem: list[tuple[str, str]] = []
    for d in dias:
        for ru in d["restaurantes"]:
            if (ru["id"], ru["nome"]) not in ordem:
                ordem.append((ru["id"], ru["nome"]))

    for id_ru, nome in ordem:
        for qual in refeicoes_pedidas:
            preco = next(
                (
                    ru["refeicoes"][qual].get("preco_aluno")
                    for d in dias
                    for ru in d["restaurantes"]
                    if ru["id"] == id_ru and ru["refeicoes"].get(qual, {}).get("preco_aluno")
                ),
                None,
            )
            horario_comum = _horario_comum(dias, id_ru, qual)
            cabecalho = f"{nome} · {_ROTULO[qual]}"
            if horario_comum:
                cabecalho += f" · {horario_comum}"
            if preco:
                cabecalho += f" · R$ {preco} (aluno)"
            linhas.append(cabecalho)

            for d in dias:
                rotulo_dia = f"{d['dia_semana']} {d['data'][:5]}"
                ru = next((r for r in d["restaurantes"] if r["id"] == id_ru), None)
                if ru is None:
                    linhas.append(f"  {rotulo_dia}: sem cardápio publicado para este dia")
                    continue
                dados = ru["refeicoes"].get(qual)
                if not dados:
                    continue
                if dados["situacao"] != "aberto":
                    curta = _SITUACAO_CURTA.get(dados["situacao"], dados["situacao"])
                    linhas.append(f"  {rotulo_dia}: {curta}")
                    continue
                partes = [rotulo_dia]
                if dados.get("horario") and not horario_comum:
                    partes.append(dados["horario"])
                if dados.get("calorias"):
                    partes.append(f"{dados['calorias']} kcal")
                itens = [i for i in dados.get("itens") or () if i not in fora_da_linha]
                linha = "  " + " · ".join(partes) + ": " + " · ".join(itens)
                if dados.get("opcao"):
                    marca = (
                        " [marcada como vegetariana]"
                        if dados.get("opcao_vegetariana_marcada") else ""
                    )
                    linha += f" | Opção: {dados['opcao']}{marca}"
                linhas.append(linha)

    linhas.extend(_rodape(comuns, quase))

    for aviso in resposta.get("avisos") or ():
        linhas.append(f"⚠ {aviso}")

    return "\n".join(linhas)


def chamar_ferramenta(nome: str, argumentos: dict, *, cliente=None, hoje=None) -> str:
    """Despacha para a ferramenta pedida, ou levanta erro legível.

    Nome desconhecido levanta `ErroRucard` citando o nome pedido: "ferramenta
    não existe" e "ferramenta existe mas não achou nada" têm curas diferentes
    para quem lê, e devolver vazio confundiria os dois (Invariante 6).

    `cliente` é injetável — e, como no Jupiter e diferente do Moodle, a
    fronteira inteira roda offline contra fixture, porque não falta credencial
    nenhuma para isso. `hoje` é injetável só para os testes da semana: sem ele,
    "semana" seria a de quem roda o teste.
    """
    if nome != _NOME_FERRAMENTA:
        raise ErroRucard(
            f"Ferramenta desconhecida: {nome!r}. A única ferramenta exposta por "
            f"este servidor é {_NOME_FERRAMENTA!r} — ela responde cardápio, "
            "horário e preço, e não mexe em cartão nem em saldo."
        )

    if cliente is None:
        # Nenhuma credencial pessoal é montada aqui: a hash é pública e sai do
        # ambiente (§1.2), e o cliente falha legível se ela não estiver lá.
        cliente = ClienteRucard(transporte_http)

    dia = argumentos.get("dia", "hoje")
    refeicao = argumentos.get("refeicao", "todas")
    restaurantes = argumentos.get("restaurantes")

    if (dia or "hoje").strip().lower() == SEMANA:
        return formatar_semana(
            bandejao_semana(
                refeicao=refeicao, restaurantes=restaurantes, cliente=cliente, hoje=hoje
            )
        )

    return formatar(
        bandejao(
            dia=dia, refeicao=refeicao, restaurantes=restaurantes,
            cliente=cliente, hoje=hoje,
        )
    )


def main() -> None:  # pragma: no cover — casca stdio
    """Adaptador stdio real. O import do SDK fica aqui dentro, não no topo: a
    suíte importa este módulo sem o SDK instalado, e um import de topo quebraria
    a coleta por causa de uma dependência que as funções puras nem usam.

    Coberto por `tests/handshake/` desde 31/08/2026: aquele teste sobe este
    processo, aperta a mão e compara o que sai no fio com o que
    `listar_ferramentas()` declara. E por E1-E4
    (`tests/rucard/test_erro_no_fio.py`) desde 10/09/2026, que é onde a MENSAGEM
    DE ERRO passou a ser verificada no fio — nenhum dos dois alcançava isso, e
    por isso a fronteira ficou muda por uma versão inteira do SDK."""
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

    from usp_mcp.env import carregar_env

    # A hash vive no `.env` (§8), como no Moodle — com a diferença de que esta
    # não é credencial pessoal. Sem isto, o servidor sobe e falha na primeira
    # pergunta por uma variável que o arquivo tinha.
    carregar_env()

    from typing import Literal

    from usp_mcp.adaptador import anotar

    descritor = listar_ferramentas()[0]
    servidor = MCPServer(name="usp-mcp-rucard", version="1.1.0")

    def _bandejao(dia="hoje", refeicao="todas", restaurantes=None) -> str:
        # Assinatura explícita em vez de **kwargs: o SDK deriva daqui o schema
        # que o modelo vê, e **kwargs produziria ferramenta sem parâmetro.
        try:
            return chamar_ferramenta(
                descritor["name"],
                {"dia": dia, "refeicao": refeicao, "restaurantes": restaurantes},
            )
        except ErroRucard as exc:
            # `ToolError` é o canal que o SDK define para "falha prevista, a
            # mensagem é para o modelo ler" — sem isto, o 2.2.0 classifica
            # `ErroRucard` como crash e entrega 29 bytes de `Error executing
            # tool bandejao`, com a mensagem em português presa no stderr
            # (medido em 10/09/2026). Só `ErroRucard` é traduzido: um `KeyError`
            # continua sendo crash, e continua com o texto retido — é o
            # comportamento certo do SDK, não um efeito colateral.
            raise ToolError(str(exc)) from exc

    # O SDK lê a ASSINATURA, não o inputSchema declarado (§9, 31/08/2026). Sem
    # isto, o `enum` que ensina que só existem quatro RUs não chega ao modelo, e
    # ele inventa id para receber negativa da allowlist depois — erro certo pela
    # via mais cara. Os Literal ficam à vista aqui; H8 é quem os mantém iguais
    # aos do schema declarado.
    anotar(
        _bandejao,
        descritor["inputSchema"],
        {
            "dia": str,
            "refeicao": Literal["almoco", "jantar", "cafe", "todas"],
            "restaurantes": list[Literal["central", "prefeitura", "fisica", "quimicas"]] | None,
        },
    )
    # `annotations` vem do MESMO descritor que a descrição e o schema. Registrar
    # aqui um bloco escrito à mão seria criar a segunda cópia que envelhece
    # calada — quem obriga as duas fontes a concordarem é o A6. O import fica no
    # topo, e não aqui dentro como o do SDK, porque `usp_mcp.anotacoes` é
    # dicionário puro: ele só toca o SDK dentro de `para_o_sdk`.
    servidor.tool(
        name=descritor["name"],
        description=descritor["description"],
        annotations=para_o_sdk(descritor),
    )(_bandejao)

    servidor.run(transport="stdio")


def _auto_verificar() -> int:  # pragma: no cover — utilitário de linha de comando
    """`python -m usp_mcp.rucard.server --auto-verificar`: o que dá para checar
    sem tocar a rede da USP."""
    import os

    from usp_mcp.env import carregar_env

    print("ferramentas expostas :", [f["name"] for f in listar_ferramentas()])
    print("credencial pessoal   : NENHUMA (hash pública e compartilhada)")

    carregar_env()
    print("RUCARD_HASH          :",
          "presente" if os.environ.get("RUCARD_HASH") else "AUSENTE — copie .env.example")

    try:
        from mcp.server import MCPServer as _M
    except ImportError:
        print("SDK do MCP           : AUSENTE — pip install -r requirements.txt")
        return 1
    print("SDK do MCP           : presente")

    import inspect

    declarados = set(listar_ferramentas()[0]["inputSchema"]["properties"])
    servidor = _M(name="verificacao", version="0.0.0")

    @servidor.tool(name="bandejao", description="verificação")
    def _sonda(dia: str = "hoje", refeicao: str = "todas",
               restaurantes: list[str] | None = None) -> str:
        return ""

    reais = set(inspect.signature(_sonda).parameters)
    print("schema x assinatura  :",
          "OK" if declarados == reais else f"DIVERGEM {declarados ^ reais}")
    return 0 if declarados == reais else 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    if "--auto-verificar" in sys.argv:
        raise SystemExit(_auto_verificar())
    main()
