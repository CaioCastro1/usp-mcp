"""T45-T48: o adaptador stdio, contra o SDK que está REALMENTE instalado.

Este arquivo existe por causa de um bug histórico, não por simetria. Na trilha
do Moodle, o `main()` foi escrito contra a API antiga do SDK (`Server` +
`@list_tools`) e **nunca funcionou** — com a suíte 99/99 verde, porque nenhum
teste alcançava aquele caminho. O backlog registrou o mesmo buraco aqui, e é
ele que estes quatro testes fecham.

O que distingue estes dos T41-T44: aqueles exercitam as funções puras, que não
sabem o que é MCP. Estes fazem `main()` rodar de verdade, com o único ponto
substituído sendo `run()` — a chamada que bloquearia no stdin. Tudo antes dela
é o código real casando com o SDK real.

`run()` é substituído por um gravador em vez de ser evitado: assim o teste
também vê o transporte pedido. Trocar `stdio` por `sse` num refactor mudaria
onde o servidor escuta, e passaria despercebido.

Os três primeiros pulam sem o SDK instalado — a suíte roda sem ele (T43), e
pular declarando é melhor do que verde que não verificou nada (Invariante 6).
T48 não pula: ele testa justamente o caso do SDK ausente.
"""
import asyncio
import sys

import pytest

from tests.jupiter.conftest import Gravador
from usp_mcp.jupiter import server


@pytest.fixture
def servidor_montado(monkeypatch):
    """Roda `main()` até a borda do stdio e devolve o `MCPServer` que ele montou.

    Só `run()` é substituído. O import do SDK, a construção do servidor e o
    registro da ferramenta são o código de produção, contra o SDK instalado —
    que é exatamente onde o bug do Moodle morava.
    """
    mcp_server = pytest.importorskip("mcp.server")

    capturado = {}

    def _run_falso(self, transport="stdio", **kwargs):
        capturado["servidor"] = self
        capturado["transporte"] = transport

    monkeypatch.setattr(mcp_server.MCPServer, "run", _run_falso)
    server.main()

    assert "servidor" in capturado, "main() retornou sem chegar em run()"
    return capturado


@pytest.mark.contrato
def test_t45_main_registra_a_ferramenta_no_sdk_instalado(servidor_montado):
    # O bug do Moodle em uma asserção: se `main()` falar a API errada do SDK,
    # nada aqui chega a rodar.
    ferramentas = asyncio.run(servidor_montado["servidor"].list_tools())

    # Registrar por índice deixava a segunda ferramenta declarada e nunca
    # anunciada (achado do handshake, 14/09). A asserção é sobre o CONJUNTO.
    assert sorted(f.name for f in ferramentas) == ["disciplina", "modulos", "requisitos"]
    assert servidor_montado["transporte"] == "stdio", (
        "o adaptador deixou de escutar em stdio — o .mcp.json fala stdio"
    )

    # A descrição registrada é a que o T41 audita. Se as duas divergirem, o
    # T41 passa auditando um texto que o modelo nunca vê.
    declaradas = {f["name"]: f["description"] for f in server.listar_ferramentas()}
    for f in ferramentas:
        assert f.description == declaradas[f.name]


@pytest.mark.contrato
def test_t46_schema_derivado_casa_com_o_declarado(servidor_montado):
    """O SDK deriva o schema da ASSINATURA; `listar_ferramentas` o declara à mão.

    Divergir aqui é o erro que só apareceria em uso real: o modelo lê um
    parâmetro que o adaptador não aceita, ou deixa de ver um que existe.
    `--auto-verificar` já comparava os dois — mas só quando alguém lembra de
    rodá-lo.
    """
    ferramentas = asyncio.run(servidor_montado["servidor"].list_tools())
    declaradas = {f["name"]: f for f in server.listar_ferramentas()}

    for ferramenta in ferramentas:
        derivados = set(ferramenta.input_schema["properties"])
        declarados = set(declaradas[ferramenta.name]["inputSchema"]["properties"])
        assert derivados == declarados, (
            f"{ferramenta.name}: divergem {derivados ^ declarados}"
        )

        # Obrigatórios iguais dos dois lados. `sigla` segue obrigatória nas
        # ferramentas que a pedem: um default aqui viraria consulta sem
        # disciplina nenhuma. `modulos` não tem obrigatório (lista tudo).
        obrigatorios = declaradas[ferramenta.name]["inputSchema"].get("required", [])
        assert ferramenta.input_schema.get("required", []) == obrigatorios
        if ferramenta.name != "modulos":
            assert obrigatorios == ["sigla"]


@pytest.mark.contrato
def test_t47_call_tool_do_sdk_atravessa_ate_a_fixture(servidor_montado, psi3323, monkeypatch):
    """Ponta a ponta pelo SDK, offline: `call_tool` → adaptador → cliente → fixture.

    Só o transporte HTTP é substituído. Isto cobre o mapeamento dos parâmetros
    do SDK para o dicionário de `chamar_ferramenta` — um nome trocado ali
    devolveria erro de argumento só em uso real.
    """
    gravador = Gravador([psi3323])
    monkeypatch.setattr(server, "transporte_http", gravador)

    resultado = asyncio.run(
        servidor_montado["servidor"].call_tool("disciplina", {"sigla": "psi 3323"})
    )

    assert not resultado.is_error, resultado
    texto = resultado.content[0].text
    assert texto.startswith("PSI3323 — Laboratório de Eletrônica I")
    assert "3×15 + 0×30" in texto, "a conta da carga horária não atravessou o SDK"

    assert len(gravador.chamadas) == 1, (
        "sem curso não se consulta pré-requisito: uma chamada, não duas"
    )

    # A asserção sobre o corpo ENVIADO, não sobre a saída. O dublê devolve a
    # fixture aconteça o que acontecer: sem isto, trocar `sigla` por `codhab` no
    # mapeamento consulta a disciplina "0" e o teste segue verde formatando a
    # fixture de PSI3323. Medido — a primeira versão deste teste passava assim.
    # É a mesma lição do limite silencioso de 20 do Moodle (§9, 31/08).
    assert "string:PSI3323" in gravador.chamadas[0]["corpo"], (
        "a sigla pedida não chegou ao corpo da requisição"
    )


@pytest.mark.contrato
def test_t48_sem_o_sdk_a_falha_e_legivel_e_diz_a_cura(monkeypatch):
    # `None` em sys.modules faz o import falhar mesmo com o SDK instalado.
    monkeypatch.setitem(sys.modules, "mcp.server", None)

    with pytest.raises(SystemExit) as exc:
        server.main()

    # Invariante 6: erro legível vence silêncio, e diz o comando que resolve.
    mensagem = str(exc.value)
    assert "mcp" in mensagem
    assert "pip install -r requirements.txt" in mensagem
