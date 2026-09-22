"""C1-C8: o texto que conta ao assistente o que está desligado.

Camada 1, offline, sem rede e sem SDK: é texto contra uma decisão, como o
`test_politica_entrega.py` é tabela de nomes contra uma decisão.

O desenho está em
`docs/superpowers/specs/2026-09-17-assistente-sabe-o-que-esta-desligado-design.md`.
O defeito que ele conserta é de 17/09/2026 e veio de uso real: o assistente não
sabia que existe uma capacidade de escrita, porque com a flag desligada as duas
ferramentas não entram no `tools/list` e o `tools/list` era o único canal pelo
qual o servidor contava de si.

O que estes testes travam, e cada um é uma metade de uma frase que não pode se
partir:

1. **Saber.** O texto existe, diz que a capacidade existe, nomeia a variável e
   declara o custo (entregar não tem desfazer) — C1, C2.
2. **Sem insistir.** Ele não é convite, não manda ligar, e não entrega a receita
   de chamada nenhuma: nenhum nome de função do Moodle sai daqui — C4, C5.
3. **Sem envelhecer calado.** A versão curta do diagnóstico é literalmente o
   começo da inteira, os nomes de ferramenta batem com os que o servidor
   anuncia, e o texto tem teto de tamanho porque viaja em toda conexão — C3,
   C6, C7.
"""
from __future__ import annotations

import re

import pytest

from usp_mcp.moodle import capacidades, politica

pytestmark = pytest.mark.politica


@pytest.fixture
def desligada(monkeypatch):
    # `delenv` e não `setenv("0")`: o estado que interessa é "a pessoa não
    # ligou", e ele inclui a variável ausente. Sem isto o teste dependeria de
    # quem rodou a suíte — o `.env` do dono declara a flag.
    monkeypatch.delenv(politica.NOME_DA_FLAG, raising=False)


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setenv(politica.NOME_DA_FLAG, "1")


def test_c1_desligada_o_texto_conta_que_existe_o_que_custa_e_quem_liga(desligada):
    texto = capacidades.estado_da_escrita()

    assert "DESLIGADA" in texto, "o estado tem de sair em letra que não se perde"
    assert politica.NOME_DA_FLAG in texto, (
        "sem o nome da variável o texto informa que existe um caminho e esconde "
        "qual é — que é a metade inútil da informação"
    )
    assert ".env" in texto, "não disse ONDE a variável mora"
    assert "NÃO tem desfazer" in texto, (
        "o custo é metade do que faz a pessoa decidir, e é o que não volta"
    )
    assert "dona do token" in texto, "não disse de QUEM é a decisão"


def test_c2_ligada_o_texto_muda_e_nao_diz_que_esta_desligada(ligada):
    """C2 — o texto que só falasse do estado desligado envelheceria calado no
    servidor de quem ligou, e "o assistente sabe o que está ligado" é a mesma
    pergunta lida do outro lado."""
    texto = capacidades.estado_da_escrita()

    assert "LIGADA" in texto
    assert "DESLIGADA" not in texto, f"diz as duas coisas ao mesmo tempo:\n{texto}"
    assert capacidades.NOME_RASCUNHO in texto and capacidades.NOME_ENTREGAR in texto, (
        "com a escrita ligada as duas estão no `tools/list`, e nomeá-las aqui é "
        "o contrário de anunciar o que não existe"
    )
    assert "NÃO tem desfazer" in texto


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c3_a_versao_curta_e_o_comeco_exato_da_inteira(estado, request):
    """C3 — anti-drift entre os dois lugares que dizem a mesma coisa.

    O diagnóstico usa a curta e o `initialize` usa a inteira. Se fossem dois
    textos parecidos, o dia em que um mudasse seria o dia em que o servidor
    passaria a dizer duas coisas sobre si mesmo — e a segunda cópia é sempre a
    que envelhece calada.
    """
    request.getfixturevalue(estado)

    curta = capacidades.estado_da_escrita(curto=True)
    inteira = capacidades.estado_da_escrita()

    assert inteira.startswith(curta), (
        "a versão curta deixou de ser um pedaço da inteira:\n"
        f"curta: {curta!r}\ninteira: {inteira!r}"
    )
    assert len(inteira) > len(curta), "a inteira virou a curta — some um dos dois usos"


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c4_nenhum_nome_de_funcao_do_moodle_sai_neste_texto(estado, request):
    """C4 — informar não é entregar a receita.

    Este texto chega ao modelo na abertura de toda conexão. Nomear
    `mod_assign_submit_for_grading` ali seria escrever o alvo no mesmo lugar em
    que ele escolhe o que chamar — a mesma razão pela qual o diagnóstico conta
    as funções bloqueadas e não as nomeia. O que a pessoa precisa saber é o nome
    da VARIÁVEL e o custo, e os dois estão lá.
    """
    request.getfixturevalue(estado)
    texto = capacidades.instrucoes()

    nomeadas = sorted(
        f
        for f in (
            set(politica.ESCRITA_CONFIRMADA)
            | set(politica.BLOQUEIO_PERMANENTE)
            | set(politica.ALLOWLIST)
        )
        if f in texto
    )
    assert not nomeadas, f"o texto nomeia funções do Moodle: {nomeadas}"


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c5_o_texto_nao_manda_ligar(estado, request):
    """C5 — informação neutra, nunca convite.

    A regra é do dono e não muda: o padrão é não escrever, e a pessoa liga de
    propósito ou não liga. Um texto que RECOMENDE ligar reintroduz o defeito
    pelo outro lado — não ensina a insistir numa ferramenta, ensina a insistir
    numa configuração.
    """
    request.getfixturevalue(estado)
    texto = capacidades.instrucoes().lower()

    convites = [p for p in ("ligue", "habilite", "recomendo", "basta ", "é só ") if p in texto]
    assert not convites, f"o texto convida em vez de informar: {convites}\n{texto}"


def test_c6_o_texto_diz_que_ligar_nao_e_passo_do_assistente(desligada):
    """C6 — a única frase que cobre o buraco que o desenho não cobre.

    Quem lê isto tem shell na maior parte dos clientes, e alcança o `.env` tanto
    quanto alcança o código. Não há portão a construir aqui; há uma frase a
    dizer, e ela é sobre de quem é a decisão.
    """
    texto = capacidades.instrucoes()

    assert "Ligar por conta própria não é o caminho" in texto
    assert "insistir" in texto, (
        "o texto precisa dizer, para o próprio modelo, que não há o que tentar "
        "enquanto a variável não estiver lá"
    )


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c7_as_instrucoes_cabem_no_orcamento_de_toda_conexao(estado, request, env_em):
    """C7 — teto declarado, porque isto viaja em TODA conexão.

    O campo é o lugar certo para o que a lista de ferramentas não diz, e o lugar
    errado para o que ela já diz. Sem um teto, ele vira o sétimo README do
    repositório, pago em tokens por conexão. O número é generoso e existe para
    reprovar crescimento, não para brigar por uma frase.

    **Subiu de 2600 para 2650 em 22/09/2026, e a troca foi medida.** Entrou o
    parágrafo de como nomear uma disciplina (~250 caracteres), e ele saiu de
    SEIS esquemas de parâmetro onde viajava inteiro — 67 tokens cada, em toda
    sessão. Medido no handshake: o estático dos três servidores caiu de 20.225
    para 20.064 bytes. É o caso exato que a regra deste campo prevê: o
    `tools/list` até carrega essa explicação, mas só repetindo-a seis vezes.

    Foi teto subindo por decisão, e não por raspagem: o texto encostou em 2601,
    e encolher uma frase para caber em 2600 deixaria o número certo e o
    orçamento desonesto — um teto que se cumpre aparando prosa não mede mais
    nada.

    O teto subiu de 1800 para 2600 em 18/09/2026, e foi decisão, não folga: o
    texto ganhou o caminho do `.env`, a separação entre iniciativa própria e
    pedido explícito, a regra de não imprimir o arquivo e a menção à outra
    variável — cada um dos quatro é um defeito de uso real ou a segurança que
    vem junto dele (C9-C14). Medido com o caminho da fixture: cerca de 2300, desligada.
    Mede com `env_em`, e não com o `.env` de quem rodou, para que o número não
    dependa do tamanho do caminho na máquina de cada um.
    """
    request.getfixturevalue(estado)
    texto = capacidades.instrucoes()

    assert len(texto) <= 2650, (
        f"as instruções estão com {len(texto)} caracteres. Elas carregam só o "
        "que o `tools/list` não tem como carregar — o que cada ferramenta faz "
        "já viaja na descrição dela."
    )


def test_c8_os_nomes_daqui_sao_os_que_o_servidor_anuncia(ligada):
    """C8 — as duas constantes de texto contra o `tools/list` de verdade.

    `capacidades.py` não importa o `server` (seria ciclo), então os nomes estão
    escritos duas vezes. Este teste é o que impede as duas cópias de divergirem
    — um texto que fale de uma ferramenta com outro nome manda a pessoa procurar
    o que não existe.
    """
    from usp_mcp.moodle import server

    anunciadas = {f["name"] for f in server.listar_ferramentas()}

    assert {capacidades.NOME_RASCUNHO, capacidades.NOME_ENTREGAR} <= anunciadas, (
        "os nomes declarados em capacidades.py não são os que o servidor anuncia "
        f"com a flag ligada: {sorted(anunciadas)}"
    )


# ---------------------------------------------------------------------------
# C9-C14 (18/09/2026): o texto diz ONDE a variável mora e separa os dois casos.
#
# Segundo defeito de uso real, um dia depois do primeiro. O dono pediu para
# entregar uma atividade; o assistente respondeu que não controlava isso e que
# não sabia onde ficava o `.env`. Ele fez exatamente o que o texto mandava, e o
# texto é que estava incompleto em duas coisas:
#
# 1. Não dizia o caminho do arquivo, e o servidor sabe: `usp_mcp.env.achar_env()`
#    devolve o `.env` que ESTE processo lê. Informação na mão, não repassada.
# 2. "Ligar por conta própria não é o caminho" foi lido como "não ligar nunca".
#    São coisas diferentes, e o caso que faltava é o legítimo: a pessoa pedir,
#    com todas as letras. Nesse caso o assistente pode editar o arquivo por ela.
#
# Apontar o assistente para o `.env` traz uma regra de segurança junto: o arquivo
# guarda o `MOODLE_TOKEN`. Editar é mexer só naquela linha e nunca imprimir o
# conteúdo — sem isso, indicar o caminho é convidar o token para a conversa.


# 32 hex, a forma de um wstoken de verdade, para a asserção de vazamento não
# passar por um valor que nenhum texto teria motivo de conter.
TOKEN_FALSO = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def env_em(tmp_path, monkeypatch):
    """`achar_env()` passa a devolver um `.env` de mentira, num caminho longo e
    reconhecível, para que estas asserções não dependam do `.env` de quem rodou
    a suíte. O arquivo tem um token FALSO dentro, de propósito: prova que o
    texto nunca lê o arquivo, só aponta para ele."""
    caminho = tmp_path / "um" / "checkout" / "bem" / "fundo" / ".env"
    caminho.parent.mkdir(parents=True)
    caminho.write_text(
        f"MOODLE_TOKEN={TOKEN_FALSO}\n{politica.NOME_DA_FLAG}=0\n", encoding="utf-8"
    )
    monkeypatch.setattr(capacidades, "achar_env", lambda: caminho)
    return caminho


@pytest.fixture
def sem_env(monkeypatch):
    monkeypatch.setattr(capacidades, "achar_env", lambda: None)


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c9_o_texto_traz_o_caminho_absoluto_do_env_que_este_processo_le(
    estado, request, env_em
):
    """C9 — "no arquivo .env do servidor" sem caminho é a metade inútil da
    informação, e o servidor tem a outra metade na mão."""
    request.getfixturevalue(estado)

    assert env_em.is_absolute()
    assert str(env_em) in capacidades.instrucoes(), (
        "as instruções não dizem ONDE está o .env que este processo lê"
    )
    assert str(env_em) in capacidades.estado_da_escrita(curto=True), (
        "o diagnóstico usa a versão curta, e é para lá que a pessoa é mandada "
        "quando está configurando — o caminho tem de estar nela também"
    )


def test_c9b_o_caminho_vem_do_achar_env_de_verdade_e_nao_de_uma_string(desligada):
    """C9b — sem monkeypatch: o texto tem de concordar com `usp_mcp.env`.

    Um caminho escrito à mão passaria no C9 e mentiria em toda máquina que não
    fosse a de quem escreveu. O que vale é o que `achar_env()` devolve AQUI.
    """
    from usp_mcp.env import achar_env

    texto = capacidades.instrucoes()
    caminho = achar_env()
    if caminho is None:
        assert "não achou arquivo .env nenhum" in texto
    else:
        assert str(caminho.resolve()) in texto or str(caminho) in texto, (
            f"o texto não traz {caminho}, que é o .env que este processo lê"
        )


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c10_sem_env_o_texto_diz_isso_e_nao_inventa_caminho(estado, request, sem_env):
    """C10 — `achar_env()` devolve None (pacote copiado para site-packages, por
    exemplo). Honestidade em vez de um caminho provável: mandar a pessoa editar
    um arquivo que o processo não lê é o mesmo defeito com outro nome."""
    request.getfixturevalue(estado)
    texto = capacidades.instrucoes()

    assert "não achou arquivo .env nenhum" in texto
    assert not re.search(r"/\S*\.env\b", texto), (
        f"sem .env o texto ainda aponta para um caminho:\n{texto}"
    )
    assert politica.NOME_DA_FLAG in texto, "sem arquivo a variável continua existindo"
    assert "ambiente" in texto, (
        "sem arquivo, a variável só entra pelo ambiente de quem sobe o processo — "
        "o texto tem de dizer por onde, ou deixa a pessoa sem caminho nenhum"
    )


def test_c11_o_texto_separa_iniciativa_propria_de_pedido_explicito(desligada, env_em):
    """C11 — a frase do C6 continua, e ganha a outra metade.

    "Ligar por conta própria não é o caminho" cobre iniciativa do assistente e
    dedução do que a pessoa quis dizer. Não cobre — e o texto antigo deixava
    parecer que cobria — a pessoa pedir de forma inequívoca. Esse caso é
    legítimo, e o texto passa a dizê-lo com todas as letras.
    """
    texto = capacidades.instrucoes()

    # A metade que não muda: nem por iniciativa própria, nem por dedução.
    assert "Ligar por conta própria não é o caminho" in texto
    assert "dedução" in texto, (
        "o texto precisa fechar a porta da dedução: 'entrega isso' com a escrita "
        "desligada é pedido de entrega, não pedido de ligar"
    )
    # A metade que faltava: pedido inequívoco da pessoa.
    assert "com todas as letras" in texto
    assert "pode editar" in texto, (
        "o texto não diz o que fazer quando a PESSOA pede — foi isso que fez o "
        "assistente responder que 'não controlava' e parar"
    )
    # E o custo de a mudança não valer já: a variável é lida na subida.
    assert "subir de novo" in texto or "subindo o servidor de novo" in texto
    assert "lida no ambiente do processo" in texto


@pytest.mark.parametrize("estado", ["desligada", "ligada"])
def test_c12_editar_e_so_aquela_linha_e_nunca_imprimir_o_arquivo(
    estado, request, env_em, monkeypatch
):
    """C12 — a regra de segurança que vem junto com o caminho.

    O `.env` guarda o `MOODLE_TOKEN`. Apontar um assistente para lá sem esta
    instrução é convidar o token a aparecer no meio de uma conversa. O texto
    nomeia a variável (para o modelo saber POR QUE a regra existe) e nunca lê o
    arquivo — o token falso escrito pela fixture não pode sair daqui.
    """
    request.getfixturevalue(estado)
    monkeypatch.setenv("MOODLE_TOKEN", TOKEN_FALSO)
    texto = capacidades.instrucoes()

    assert "só na linha" in texto or "só naquela linha" in texto, (
        "o texto não restringe a edição à linha da variável"
    )
    assert "nunca imprima" in texto, "o texto não proíbe imprimir o arquivo"
    assert "MOODLE_TOKEN" in texto, (
        "sem dizer o que o arquivo guarda, a proibição parece capricho"
    )
    assert TOKEN_FALSO not in texto, "o texto leu o .env — e vazou o que tem dentro"


def test_c13_a_outra_variavel_e_nomeada_e_dita_pelo_que_faz(desligada, env_em):
    """C13 — `USP_MCP_ALLOW_WRITES` mora no mesmo arquivo e tem "WRITES" no nome.

    Quem for editar o `.env` vai vê-la. Sem uma frase aqui, a leitura óbvia é
    que ela liga a escrita — e ela não abre nada, nos três servidores. O texto
    diz o que ela faz de verdade, para ninguém pôr 1 nela achando que resolve.
    """
    texto = capacidades.instrucoes()

    assert "USP_MCP_ALLOW_WRITES" in texto
    assert "não abre nada" in texto, (
        "nomeou a variável e não disse que ela não faz o que o nome sugere"
    )


def test_c14_com_a_flag_ligada_o_caminho_de_volta_tem_a_mesma_regra(ligada, env_em):
    """C14 — simetria: desligar por pedido explícito é a mesma edição, com a
    mesma regra de segurança, e o mesmo "só vale depois de subir de novo"."""
    texto = capacidades.instrucoes()

    assert "com todas as letras" in texto
    assert "só na linha" in texto or "só naquela linha" in texto
    assert "MOODLE_TOKEN" in texto
    assert "subir de novo" in texto or "subindo o servidor de novo" in texto
