"""O que este servidor tem, inclusive o que está DESLIGADO, dito em prosa.

Nasceu de um defeito relatado por uso real (17/09/2026): o dono usou o
assistente, existia uma capacidade de escrita atrás de `USP_MCP_ENTREGA`, e o
assistente **não sabia que ela existe**. Não recusou — nem chegou a considerar.
Simplesmente não ofereceu, e a pessoa ficou sem saber que era possível.

A causa é de desenho, e o desenho estava certo: com a flag desligada as duas
ferramentas de escrita não entram no `tools/list`
(`docs/superpowers/specs/2026-09-15-entrega-com-confirmacao-design.md`, E14).
Ferramenta que aparece e sempre recusa ensina o modelo a insistir — ele a vê,
escolhe, gasta uma chamada, lê a negativa e procura o contorno. Só que o
`tools/list` era o ÚNICO canal pelo qual o servidor contava de si, e por isso
o preço daquela decisão acabou sendo o silêncio total.

**A saída é separar os dois canais, e o protocolo já os separa.** O `tools/list`
é a superfície de AÇÃO: o que está lá é chamável, e um item chamável que sempre
recusa é a armadilha que o desenho de 15/09 evitou. O campo `instructions` do
`initialize` é a superfície de INFORMAÇÃO: o cliente o lê uma vez, na abertura
da conexão, e não há nada ali para chamar. Uma frase em `instructions` não tem
como virar chamada gasta, nem recusa lida, nem contorno procurado — não existe o
laço que ensina a insistir, porque não existe a tentativa.

Por isso o texto daqui pode dizer o que a lista de ferramentas não pode.

**Regra que segura o crescimento deste texto:** `instructions` carrega só o que
o `tools/list` não tem como carregar. O que cada ferramenta faz e quando usá-la
já viaja na descrição dela, para o cliente que pergunta; repetir aqui seria
pagar os mesmos tokens duas vezes em toda conexão. Hoje o que sobra é um assunto
só — o estado da escrita —, e é por isso que o RUCard e o Jupiter não ganharam
`instructions` nenhuma: eles não têm escrita para ligar, e um campo com texto
que não ajuda a agir é a mesma má prática que a saída sem jargão combateu.

**Informação neutra, com o custo declarado, e nunca convite.** O padrão continua
sendo não escrever. O texto diz o que existe, o que custa (entregar não tem
desfazer) e quem liga — a pessoa dona do token, de propósito, no arquivo dela.
Diz também, com todas as letras, que ligar não é passo que o assistente dê por
conta própria. Isso não é um portão: um modelo com shell alcança o `.env` tanto
quanto alcança este arquivo, e o desenho de 15/09 já registra que o portão é
forte contra acidente e fraco contra um modelo decidido. É honestidade sobre
para quem é a decisão, no único lugar onde ela ainda pode ser lida antes de ser
tomada.

**Simétrico de propósito.** Com a flag ligada o texto muda e diz que está
ligada. Um texto que só falasse do estado desligado envelheceria calado no
servidor de quem ligou — e "o assistente sabe o que está ligado" é a mesma
pergunta, lida do outro lado.

**Segundo defeito de uso real, um dia depois (18/09/2026).** Com o texto acima
no ar, o dono pediu para entregar uma atividade e o assistente respondeu que
não controlava isso e não sabia onde ficava o `.env`. Fez exatamente o que o
texto mandava; o texto é que estava incompleto em duas coisas:

1. **Não dizia onde o arquivo está, e o servidor sabe.** `usp_mcp.env.achar_env()`
   devolve o caminho do `.env` que ESTE processo lê. Era informação na mão que
   não passava adiante — "no arquivo .env do servidor" mandava a pessoa procurar.
   Agora o caminho absoluto sai no texto, nos dois estados e nas duas versões
   (a curta do diagnóstico inclusive). Quando `achar_env()` devolve None (o
   pacote copiado para `site-packages`, por exemplo), o texto diz isso e diz por
   onde a variável entra então, em vez de inventar um caminho provável.
2. **Confundia "não ligar por conta própria" com "não ligar nunca".** São dois
   casos, e o texto passou a separá-los com todas as letras. Por iniciativa do
   assistente, ou por dedução do que a pessoa quis dizer, continua não sendo o
   caminho — pedido de entrega não é pedido de ligar. Quando a pessoa pede de
   forma inequívoca, o assistente pode editar aquele arquivo por ela.

Apontar o assistente para o `.env` traz uma regra de segurança que é
obrigatória e vem no mesmo parágrafo: **mexer só naquela linha e nunca imprimir
o conteúdo do arquivo**, porque ele guarda o `MOODLE_TOKEN`. Sem essa frase,
dar o caminho seria convidar o token a aparecer no meio de uma conversa. E como
quem abre o arquivo vai ver `USP_MCP_ALLOW_WRITES` logo acima, com "WRITES" no
nome, o texto diz o que ela faz de verdade: nada, nos três servidores.

O que NÃO mudou em 18/09: o padrão segue sendo não escrever, as duas ferramentas
seguem fora do `tools/list` com a flag desligada, e o texto segue sem palavra de
recomendação — o teste que proíbe `ligue`, `habilite`, `recomendo`, `basta` e
`é só` continua valendo, e a redação é que se curvou a ele.
"""
from __future__ import annotations

from ..env import achar_env
from .politica import NOME_DA_FLAG

# Os nomes das duas ferramentas de escrita. Escritos aqui, e não importados do
# `server`, porque é o `server` que importa este módulo: o caminho contrário
# fecharia um ciclo de import por causa de duas constantes de texto. Quem obriga
# os dois lados a concordarem é a suíte, que compara este par com o que o
# `listar_ferramentas()` anuncia quando a flag está ligada.
NOME_RASCUNHO = "salvar_rascunho"
NOME_ENTREGAR = "entregar"

# A outra variável de escrita do `.env`. Nomeada aqui só para o texto dizer o
# que ela faz (nada), e não para ser lida: este módulo não consulta o valor dela.
_A_OUTRA_FLAG = "USP_MCP_ALLOW_WRITES"

# A primeira coisa que o cliente lê, e a razão de o resto existir. Ela diz o que
# este texto NÃO é, para que ninguém o encha com o que já viaja na descrição de
# cada ferramenta.
_ABERTURA = (
    "Ferramentas de consulta ao e-Disciplinas (Moodle da USP). O que cada uma "
    "faz e quando usá-la está na descrição dela; aqui vai só o que a lista de "
    "ferramentas não tem como dizer."
)

# Como nomear uma disciplina vale para as SEIS ferramentas que pedem o
# parâmetro, e até 22/09/2026 esta explicação viajava inteira dentro de cada uma
# delas: 67 tokens seis vezes, no esquema, em toda sessão. Aqui ela custa uma
# vez. O esquema de cada parâmetro continua dizendo o essencial — que é sigla, e
# que espaço e caixa não importam —, porque é ali que o modelo olha na hora de
# montar a chamada; o que veio para cá é o detalhe que ele só precisa quando a
# sigla não basta.
_COMO_NOMEAR_DISCIPLINA = (
    "Nomear disciplina: a sigla serve quase sempre (PTC3314); quando ela se "
    "repete em anos diferentes, só o rótulo inteiro separa as matrículas "
    "(PTC3314-2026, PSI3322-2026-REOF). `disciplinas` lista os rótulos, e "
    "pedaço do nome também casa."
)


def escrita_ligada() -> bool:
    """A capacidade de escrita está ligada NESTE processo?

    Delega para a política, que é quem lê o ambiente, para que não existam dois
    lugares respondendo a mesma pergunta. Lido a cada chamada pelo mesmo motivo
    de lá: o `.env` é carregado depois do import.
    """
    from .politica import entrega_habilitada

    return entrega_habilitada()


def _onde_esta_o_env() -> str:
    """Uma frase com o caminho absoluto do `.env` que este processo lê.

    Pergunta ao `usp_mcp.env`, que é quem sabe, em vez de repetir a busca: se
    a regra de onde procurar mudar lá, o texto daqui acompanha sem ninguém
    lembrar de editar. Com None, diz que não achou e por onde a variável entra
    então — um caminho provável mandaria a pessoa editar um arquivo que o
    processo não lê, que é o defeito de 18/09 com outro nome.
    """
    caminho = achar_env()
    if caminho is None:
        return (
            "Este processo não achou arquivo .env nenhum (procurou na raiz do "
            "checkout e no checkout que tem o .git), então não há arquivo para "
            "editar: aqui a variável só entra pelo ambiente de quem sobe o "
            "servidor, como o bloco env da configuração do cliente MCP."
        )
    return f"O arquivo .env que este processo lê é {caminho}."


# A regra de segurança, escrita uma vez e usada nos dois estados: quem edita o
# `.env` para ligar e quem edita para desligar mexem no mesmo arquivo, e o
# `MOODLE_TOKEN` está lá nas duas vezes.
_COMO_EDITAR = (
    f"mexa só na linha de {NOME_DA_FLAG} (acrescente-a se não existir) e nunca "
    f"imprima nem cite o conteúdo do arquivo, nem em parte: ele guarda o "
    f"MOODLE_TOKEN, credencial pessoal de quem é dono da conta. A mudança só "
    f"vale depois de o servidor subir de novo, porque a variável é lida no "
    f"ambiente do processo, e este já subiu com o valor de agora."
)


def _desligada() -> str:
    # O fato nu, na versão que cabe em qualquer lugar: o diagnóstico usa esta,
    # e as instruções usam esta MAIS `_desligada_resto()`. Duas versões do mesmo
    # fato, uma contida na outra, e não dois textos que se parecem — foi assim
    # que este projeto aprendeu que a segunda cópia é a que envelhece calada.
    return (
        f"Escrita: DESLIGADA. Este servidor só lê o e-Disciplinas agora. Existe "
        f"uma capacidade de escrita neste projeto — salvar o texto do rascunho de "
        f"uma entrega, e enviar uma entrega para correção — e ela está desligada, "
        f"por isso as duas ferramentas dela não estão nesta conexão. Quem liga é "
        f"a pessoa dona do token, pondo {NOME_DA_FLAG}=1 no arquivo .env do "
        f"servidor e subindo o servidor de novo. {_onde_esta_o_env()} Enviar uma "
        f"entrega para correção NÃO tem desfazer, nem por aqui nem pela API do "
        f"Moodle."
    )


def _desligada_resto() -> str:
    if achar_env() is None:
        pedido = (
            "Já se a pessoa pedir, com todas as letras, que a escrita seja "
            "ligada, não há arquivo que você possa editar por ela: a variável "
            "entra por onde o servidor é subido, e quem sabe onde isso está é "
            "ela."
        )
    else:
        pedido = (
            "Já se a pessoa pedir, com todas as letras, que a escrita seja "
            f"ligada, você pode editar aquele arquivo por ela. Ao editar, "
            f"{_COMO_EDITAR}"
        )
    return (
        "Conte isso a quem perguntar o que dá para fazer por aqui, ou a quem "
        "pedir para entregar alguma coisa: que a capacidade existe, que está "
        "desligada, o que ela custa, onde ela liga, e que ligar é decisão de "
        "quem responde pela conta — não sua, e não deste processo. São dois "
        "casos, e eles não se misturam. Ligar por conta própria não é o caminho, "
        "e insistir também não: nem por iniciativa sua, nem por dedução do que a "
        "pessoa quis dizer — pedido de entrega com a escrita desligada é pedido "
        "de entrega, não pedido de ligar, e a resposta é contar o que está "
        "acima. Enquanto a variável não estiver no ambiente do servidor não há "
        f"ferramenta nenhuma para chamar, e não há o que tentar. {pedido} "
        f"{_A_OUTRA_FLAG}, a outra variável de escrita deste projeto, não é o "
        "caminho para isto: nos três servidores deste projeto ela não abre nada "
        "— nem estas duas ferramentas, nem a lista de bloqueio permanente — e "
        "pô-la em 1 não faz a escrita aparecer. Com a escrita ligada, cada uma "
        "das duas ainda pede duas chamadas — a primeira mostra o plano do que "
        "mudaria e não escreve nada."
    )


def _ligada() -> str:
    return (
        f"Escrita: LIGADA, por {NOME_DA_FLAG}=1 no ambiente deste servidor. "
        f"{_onde_esta_o_env()} As ferramentas `{NOME_RASCUNHO}` e "
        f"`{NOME_ENTREGAR}` estão nesta conexão e escrevem no e-Disciplinas em "
        f"nome de quem é dono do token. Cada uma pede duas chamadas: a primeira "
        f"devolve o plano do que mudaria e um código, e só a segunda, repetindo "
        f"o código, escreve. Enviar uma entrega para correção NÃO tem desfazer, "
        f"nem por aqui nem pela API do Moodle."
    )


def _ligada_resto() -> str:
    if achar_env() is None:
        volta = (
            "a variável está no ambiente de quem sobe o servidor, não num "
            "arquivo que você alcance por aqui, e quem sabe onde a pôs é ela."
        )
    else:
        volta = (
            f"você pode editar aquele arquivo por ela, com a mesma regra: "
            f"{_COMO_EDITAR}"
        )
    return (
        "Diga que a escrita está ligada quando ela for relevante para a "
        "conversa: quem ligou pode ter esquecido, e o custo de descobrir depois "
        "de enviar é o que não tem volta. Quem desliga é a mesma pessoa que "
        "ligou, tirando a variável do ambiente do servidor e subindo o servidor "
        "de novo — não é passo seu, nem por iniciativa própria nem por dedução. "
        f"Se ela pedir com todas as letras, {volta}"
    )


def estado_da_escrita(*, curto: bool = False) -> str:
    """O estado da escrita em prosa, na versão curta ou na inteira.

    `curto=True` devolve exatamente o primeiro parágrafo da versão inteira — não
    um resumo parecido. É o que garante que o diagnóstico e o `initialize` não
    digam coisas diferentes sobre o mesmo servidor.
    """
    if escrita_ligada():
        base, resto = _ligada(), _ligada_resto()
    else:
        base, resto = _desligada(), _desligada_resto()
    return base if curto else f"{base}\n\n{resto}"


def instrucoes() -> str:
    """O texto do campo `instructions` do `initialize`.

    Montado a cada subida do processo, e não constante de módulo, porque ele
    depende do ambiente: o servidor que sobe com a flag ligada diz outra coisa,
    e o caminho do `.env` é o daquela máquina.
    """
    return f"{_ABERTURA}\n\n{_COMO_NOMEAR_DISCIPLINA}\n\n{estado_da_escrita()}"
