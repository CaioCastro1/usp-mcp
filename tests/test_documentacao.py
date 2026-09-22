r"""D1-D2: o README leva um clone limpo até o gate verde na ordem em que se lê.

Estes testes não olham código: olham a **ordem** das instruções. Existem porque
o primeiro comando que alguém novo roda neste repositório reprovava, e por um
motivo que a mensagem de erro não nomeava — o `./scripts/gate.sh` estava na
seção de instalação e o `cp .env.example .env` só aparecia na *Configuração*,
depois. Essa seção mudou de nome duas vezes em 14/09/2026: *Rodando* virou
*Instalando*, e depois o README foi reordenado para quem NÃO é técnico. Hoje
`## Instalando` é o caminho de quem só quer usar, e o fluxo que D1 e D2
descrevem mora em `## Rodando a partir do código`, que é a seção de quem mexe
no código e onde o gate vive.
Quem lê de cima para baixo levava um `FAILED` sobre `RUCARD_HASH` e nenhuma
pista de que faltava um passo que ainda nem tinha lido.

D3 é de 16/09/2026 e guarda o outro caminho, o de quem só usa. Até essa data o
caminho manual de `## Instalando` mandava `pip install git+...` num venv solto,
e isso põe o pacote em `site-packages`, onde `usp_mcp.env.achar_env` não acha
`.env` nenhum: o bandejão caía em `HashAusente` mandando copiar um
`.env.example` que a pessoa não tinha, e o token gravado pelo `token.sh` ficava
num clone que o servidor instalado nunca lia. D1 e D2 passavam verdes porque só
olham a outra seção. A cura foi o caminho manual clonar, criar o venv DENTRO do
clone e instalar editável, que é o layout que `env.py`, o `.mcp.json` e o
`servidor.sh` já suportam; D3 afirma os três passos pela string que se digita.

D4 é de 18/09/2026 e guarda o caminho rápido, que é a mensagem que a pessoa
cola no assistente. Até essa data era UMA mensagem, escrita num Mac para um Mac,
e ela quebrava em quatro lugares no Windows, três deles invisíveis para quem
cola: mandava rodar o `scripts/gate.sh`, que procura `.venv/bin/python`, caía no
`python3` da Microsoft Store e reprovava 58 testes (o dono do projeto viu o
assistente gastar sete minutos tentando entender se a quebra era real); apontava
para `.venv/bin/`, que no Windows é `.venv\Scripts\` com `.exe`; mandava rodar
`./scripts/token.sh` sem dizer que ali precisa do Git Bash; e terminava chamando
`diagnostico`, que exige a chave e toca a USP, no exato momento em que a chave é
o que falta. O gate, além disso, é ferramenta de pré-commit, e não tem o que
fazer num roteiro de instalação em sistema nenhum. A cura foi uma mensagem por
sistema, e a conferência virou o `--auto-verificar`, que é offline e não precisa
de chave. D4 afirma isso pelo texto: três blocos, cada um com o endereço do
repositório e o `--auto-verificar`, nenhum com gate, suíte ou `diagnostico`, e
os caminhos do sistema certo em cada um.

Dois pontos entraram depois, no mesmo dia. O primeiro: o obtentor da chave foi
portado para Python e ganhou o comando `usp-mcp-token`, então o passo 5 do
Windows deixou de precisar do Git Bash, e o que D4 guardava (Git Bash PRESENTE
no prompt do Windows) virou o contrário. O segundo: os prompts passaram a mandar
o assistente INSTALAR o que falta, e não só ensinar. Isso não é igual nos três
sistemas, e é por isso que D4 mede um gerenciador de pacotes por sistema em vez
de um só: `winget` instala sem senha, `brew` também depois de existir, e `apt`,
`dnf` e `pacman` exigem `sudo`. Prometer instalação automática onde a senha é
necessária seria a mesma classe de defeito do prompt escrito num Mac para um
Mac, só que descoberta no meio do caminho.

D5 é de 20/09/2026 e guarda o passo 5, que é o passo da chave e o único em que
a pessoa põe a mão. Ele falhou por dizer pouco duas vezes: o assistente leu
"Rode `token.sh`" como ordem para a PESSOA rodar e devolveu o teclado a ela, e,
sem o texto do link da página do e-Disciplinas, improvisava e mandava procurar a
coisa errada. D5 exige dos três, e não de um, porque a emenda anterior pegou o
Mac e o Windows e deixou o Linux para trás.

Documento também envelhece calado (é a lição do §9 de 31/08 sobre estado em
`CLAUDE.md`/`README.md`): a diferença aqui é que a ordem errada volta a doer em
toda pessoa nova, e não só na próxima sessão de IA.

Sem marcador: não são allowlist (`politica`) nem forma contra fixture
(`contrato`). São offline, puros e custam um `read_text` — entram no gate junto
com o resto.
"""
from __future__ import annotations

import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
README = RAIZ / "README.md"

# O comando exato, como se digita. Comparar a string que a pessoa copia — e não
# uma paráfrase tipo "menciona o .env" — é o que impede este teste de passar com
# um README que fala do assunto sem dar o comando.
CURA = "cp .env.example .env"


def bloco(titulo: str) -> str:
    """O corpo de uma seção `## <titulo>` do README, até a próxima `## `."""
    texto = README.read_text(encoding="utf-8")
    marca = f"\n## {titulo}\n"
    inicio = texto.find(marca)
    assert inicio != -1, (
        f"o README não tem mais a seção {titulo!r}. Se ela foi renomeada, este "
        "teste precisa saber: caso contrário ele passaria a medir o vazio."
    )
    inicio += len(marca)
    fim = texto.find("\n## ", inicio)
    return texto[inicio : fim if fim != -1 else len(texto)]


def test_d1_o_readme_manda_criar_o_env_antes_do_gate():
    contribuir = bloco("Rodando a partir do código")
    i_cura = contribuir.find(CURA)
    i_gate = contribuir.find("scripts/gate.sh")

    # As duas presenças são asserção própria, e não pressuposto: `find` devolve
    # -1 quando não acha, e -1 é menor que qualquer índice. Sem estas duas
    # linhas, um README que perdesse o `cp` passaria neste teste — o falso-verde
    # que o Invariante 6 proíbe, aqui na forma "comparei ausência com presença".
    assert i_cura != -1, (
        f"a seção Rodando a partir do código não traz {CURA!r}. Num clone limpo não existe `.env`, "
        "e sem ele o gate reprova falando de RUCARD_HASH — que não é o passo "
        "que faltou."
    )
    assert i_gate != -1, (
        "a seção Rodando a partir do código não chama mais o `scripts/gate.sh`. Se o gate saiu "
        "daqui, este teste está medindo outra coisa."
    )
    assert i_cura < i_gate, (
        "a seção Rodando a partir do código manda rodar o gate antes de criar o `.env`. Quem lê de "
        "cima para baixo reprova na primeira tentativa; a ordem no papel é a "
        "ordem em que os comandos são executados."
    )


def test_d2_o_readme_nao_manda_preencher_o_token_para_o_gate():
    contribuir = bloco("Rodando a partir do código")

    # Invariante 4: o token do Moodle é credencial pessoal. Um caminho de
    # "primeiros passos" que peça credencial para o commit passar transforma
    # colar segredo em pré-requisito de contribuir — e o gate é offline, não
    # precisa de token nenhum. O `.env.example` traz `MOODLE_TOKEN` vazio de
    # propósito, e D5 prova que vazio basta.
    assert "MOODLE_TOKEN" not in contribuir, (
        "a seção Rodando a partir do código pede o MOODLE_TOKEN. O gate roda offline e não toca a "
        "USP: exigir credencial pessoal aqui contraria o Invariante 4."
    )

    # E o token não pode simplesmente ter sumido do README para o teste acima
    # passar: ele continua sendo necessário para USAR o servidor do Moodle, e
    # esse lugar é a seção Configuração.
    assert "MOODLE_TOKEN" in bloco("Configuração"), (
        "o README parou de nomear a variável `MOODLE_TOKEN` na Configuração. "
        "Quem for de fato usar o Moodle precisa saber o nome dela."
    )


# Os comandos exatos do caminho manual, como se digitam. A ordem importa tanto
# quanto em D1: o `cp` tem de vir antes de o README dizer "Pronto".
CLONE = "git clone https://github.com/CaioCastro1/usp-mcp.git ~/usp-mcp"
INSTALACAO_EDITAVEL = "pip install -e ~/usp-mcp"
CURA_MANUAL = "cp ~/usp-mcp/.env.example ~/usp-mcp/.env"


def test_d3_o_caminho_manual_instala_dentro_do_clone_e_cria_o_env():
    instalando = bloco("Instalando")

    for passo in (CLONE, INSTALACAO_EDITAVEL, CURA_MANUAL):
        assert passo in instalando, (
            f"a seção Instalando não traz {passo!r}. O comando instalado só acha o "
            "`.env` se o pacote for instalado de dentro do clone (editável) e o "
            "`.env` for criado nesse clone; sem um dos três passos o bandejão cai "
            "em HashAusente e o token do `token.sh` nunca chega ao servidor."
        )

    # O layout que não funciona não pode voltar por engano: pacote em
    # `site-packages` não tem `.env` ao lado, e `achar_env` não procura em
    # mais lugar nenhum (decisão registrada no docstring de `usp_mcp/env.py`).
    assert "install git+" not in instalando, (
        "a seção Instalando voltou a instalar o pacote direto da URL do "
        "repositório, fora de um clone. Medido em 16/09/2026: nesse layout "
        "`achar_env()` devolve None e o bandejão não responde."
    )

    i_cura = instalando.find(CURA_MANUAL)
    i_pronto = instalando.find("Pronto:")
    assert i_pronto != -1, "a seção Instalando não diz mais 'Pronto:'; o teste mediria o vazio"
    assert i_cura < i_pronto, (
        "o README diz 'Pronto' antes de mandar criar o `.env`. Quem lê de cima "
        "para baixo abre o assistente sem a hash do bandejão."
    )


# A conferência que funciona sem chave e sem rede, nos três servidores, como se
# digita. É por `python -m` de propósito: o comando instalado (`usp-mcp-rucard`)
# ignora o argumento e sai com 0 sem imprimir nada, medido em 18/09/2026.
VERIFICACAO = "--auto-verificar"
REPOSITORIO = "https://github.com/CaioCastro1/usp-mcp"
# O que foi aprendido com uso e não pode sair da mensagem.
UM_PASSO = "UM PASSO POR MENSAGEM"
# Ferramenta de quem mantém, e a chamada que exige a chave: nenhuma entra no
# roteiro de instalação. `pytest` cobre "rode a suíte" em qualquer forma.
PROIBIDOS = ("gate.sh", "pytest", "diagnostico")

# Como cada sistema obtém a chave do e-Disciplinas, como se digita. Não é o
# mesmo comando nos três desde 18/09/2026: o obtentor foi portado para Python e
# ganhou um entry point, `usp-mcp-token`, e no Windows é ele que roda, em
# `.venv\Scripts\usp-mcp-token.exe`, no mesmo PowerShell dos outros passos. O
# `scripts/token.sh` virou invólucro fino e segue sendo o caminho de Mac e
# Linux. Este dicionário é a diferença escrita: um teste que só perguntasse
# "obtém a chave?" passaria com o prompt do Windows mandando abrir o Git Bash de
# novo.
OBTENTOR = {
    "Mac": "~/usp-mcp/scripts/token.sh",
    "Windows": r"\usp-mcp\.venv\Scripts\usp-mcp-token.exe",
    "Linux": "~/usp-mcp/scripts/token.sh",
}

# Como cada prompt manda instalar o que falta. A mensagem de 18/09/2026 mandava
# o assistente só ENSINAR a instalar ("me diga como instalar pelo site oficial e
# espere"); o dono pediu o contrário, e o contrário não é igual nos três, porque
# `sudo` pede senha e o assistente não tem como digitá-la.
#
# É o COMANDO e não o nome da ferramenta: uma sabotagem controlada mostrou que
# procurar só por "winget" ou por "senha" passa verde num prompt que perdeu a
# instrução e ficou com a palavra solta no glossário ou numa frase vizinha. No
# Linux são os três, porque nomear um gerenciador só mandaria o assistente
# adivinhar nas outras distribuições.
COMANDO_DE_INSTALACAO = {
    "Mac": ("brew install",),
    "Windows": ("winget install --id",),
    "Linux": ("sudo apt install", "sudo dnf install", "sudo pacman -S"),
}

# O nome nu de cada gerenciador, para a checagem contrária: o prompt de um
# sistema não pode citar o gerenciador de outro. Só `brew` e `winget` entram,
# porque `sudo` aparece legitimamente em frase que fala do Linux em geral.
GERENCIADOR = {"Mac": "brew", "Windows": "winget"}


def prompts_do_caminho_rapido() -> dict[str, str]:
    """Os blocos ```text da subseção *O caminho rápido*, por sistema."""
    instalando = bloco("Instalando")
    inicio = instalando.find("### O caminho rápido")
    fim = instalando.find("### O caminho manual")
    assert inicio != -1 and fim != -1 and inicio < fim, (
        "a seção Instalando perdeu *O caminho rápido* ou *O caminho manual*, ou "
        "trocou a ordem. Se a estrutura mudou, este teste precisa saber."
    )
    rapido = instalando[inicio:fim]

    prompts: dict[str, str] = {}
    for sistema in ("Mac", "Windows", "Linux"):
        marca = f"#### No {sistema}\n"
        i = rapido.find(marca)
        assert i != -1, (
            f"o caminho rápido não tem mais a subseção `#### No {sistema}`. Uma "
            "mensagem só, com 'se você estiver no Windows faça assim', é o que "
            "quebrava: o assistente escolhia errado e a pessoa não percebia."
        )
        i_abre = rapido.find("```text\n", i)
        i_fecha = rapido.find("\n```\n", i_abre + 1)
        assert i_abre != -1 and i_fecha != -1, f"a subseção {sistema} não tem um bloco ```text"
        prompts[sistema] = rapido[i_abre + len("```text\n") : i_fecha]
    return prompts


# O passo da chave é o único em que a pessoa mexe, e ele já falhou duas vezes
# por dizer pouco. Primeiro: "Rode `token.sh`", no meio de uma lista de comandos,
# foi lido pelo assistente como ordem para a PESSOA rodar, e ele pediu que ela
# rodasse na mão. A cura é o passo dizer de quem é cada parte, com "no seu
# terminal" grudado no "você mesmo". Sem isso, o "você" da frase depende de o
# modelo inferir quem fala com quem no meio de uma lista de comandos. Segundo: a
# página do e-Disciplinas tem três coisas clicáveis e duas são distração, e o
# prompt não dizia qual é a boa, então o assistente improvisava e mandava a
# pessoa procurar a coisa errada. Quem cola o prompt não cola o README junto, e
# a seção *Configuração*, que descreve a página, fica longe demais para ajudar.
#
# Os três de uma vez, e não um de cada vez: a emenda de 19/09/2026 pegou Mac e
# Windows e deixou o Linux para trás, porque não havia teste que exigisse os três.
QUEM_RODA = (
    "rode você mesmo, no seu terminal",
    "Não me peça para rodar esse comando",
)
# O texto do link, como aparece na página, e como se clica nele. Clicar com o
# esquerdo abre o aplicativo do Moodle e não copia nada.
LINK_AZUL = "Clique aqui se a aplicação não abrir automaticamente"
COMO_COPIAR = ("botão direito", "copiar endereço do link")


def uma_linha(texto: str) -> str:
    """O texto com as quebras de linha desfeitas, para comparar frase.

    O prompt é quebrado em ~88 colunas, e a quebra cai onde calhar: procurar a
    frase crua reprovaria por causa de um `\n` no meio dela, que é justamente o
    que não importa para quem cola.
    """
    return " ".join(texto.split())


def test_d5_o_passo_da_chave_diz_quem_roda_e_onde_esta_o_link():
    prompts = prompts_do_caminho_rapido()

    for sistema, prompt in prompts.items():
        corrido = uma_linha(prompt)
        for frase in QUEM_RODA:
            assert frase in corrido, (
                f"o prompt do {sistema} não diz, com todas as letras, que quem "
                f"roda o comando da chave é o assistente ({frase!r} não está "
                "lá). Medido em uso: sem isso ele lê 'Rode tal comando' como "
                "ordem para a pessoa e devolve o teclado para ela."
            )
        assert LINK_AZUL in corrido, (
            f"o prompt do {sistema} não cita o link azul {LINK_AZUL!r}. A "
            "página do e-Disciplinas ainda mostra a caixa verde 'O seu cadastro "
            "foi confirmado' e o botão cinza 'Ambientes', e sem o texto do link "
            "o assistente improvisa e manda a pessoa clicar na coisa errada."
        )
        for forma in COMO_COPIAR:
            assert forma in corrido, (
                f"o prompt do {sistema} não traz {forma!r}. É assim que se copia "
                "o endereço: com o botão esquerdo o navegador tenta abrir o "
                "aplicativo do Moodle e não copia nada."
            )


def test_d4_o_caminho_rapido_tem_um_prompt_por_sistema_e_confere_sem_chave():
    prompts = prompts_do_caminho_rapido()

    for sistema, prompt in prompts.items():
        assert REPOSITORIO in prompt, (
            f"o prompt do {sistema} não diz de onde clonar. Sem o endereço o "
            "assistente adivinha, e é o mesmo bug do `Castro1` de 14/09 por outro caminho."
        )
        assert VERIFICACAO in prompt, (
            f"o prompt do {sistema} não confere a instalação com `{VERIFICACAO}`. "
            "É a única conferência que roda sem chave e sem rede nos três sistemas."
        )
        # ` -m usp_mcp.` e não `python -m`: no Windows o interpretador é `python.exe`.
        assert " -m usp_mcp." in prompt, (
            f"o prompt do {sistema} roda o `{VERIFICACAO}` sem `python -m`. Pelo "
            "comando instalado o argumento é ignorado e a saída é 0 sem texto: um "
            "verde que não conferiu nada."
        )
        assert UM_PASSO in prompt, (
            f"o prompt do {sistema} perdeu o '{UM_PASSO}' do passo da chave. Foi "
            "aprendido com uso: a lista inteira de uma vez ninguém lê."
        )
        assert OBTENTOR[sistema] in prompt, (
            f"o prompt do {sistema} não obtém a chave do e-Disciplinas por "
            f"{OBTENTOR[sistema]!r}, que é a forma daquele sistema."
        )
        for comando in COMANDO_DE_INSTALACAO[sistema]:
            assert comando in prompt, (
                f"o prompt do {sistema} não traz `{comando}`, que é como se "
                "instala o que falta ali. Mandar a pessoa se virar com o site "
                "oficial quando existe instalador de programas é o que saiu "
                "daqui em 18/09/2026."
            )
        for outro, ferramenta in GERENCIADOR.items():
            if outro != sistema:
                assert ferramenta not in prompt, (
                    f"o prompt do {sistema} cita o `{ferramenta}`, que é de "
                    f"{outro}. É o mesmo defeito dos caminhos: o assistente segue "
                    "o que está escrito e a pessoa não tem como perceber."
                )
        for proibido in PROIBIDOS:
            assert proibido not in prompt, (
                f"o prompt do {sistema} cita `{proibido}`. Gate e suíte são de quem "
                "mantém o projeto, e `diagnostico` exige a chave que a instalação "
                "ainda não tem: nenhum dos três confere uma instalação."
            )

    # Os caminhos são do sistema certo, e não do sistema em que o README foi escrito.
    assert "Scripts" in prompts["Windows"] and ".exe" in prompts["Windows"], (
        "o prompt do Windows não fala de `Scripts` nem de `.exe`: é o venv do Mac "
        "de novo, e lá `.venv/bin/` não existe."
    )
    assert ".venv/bin" not in prompts["Windows"], (
        "o prompt do Windows aponta para `.venv/bin`. No Windows essa pasta não existe."
    )
    # Era o contrário até 18/09/2026, e a inversão é o ponto: enquanto o obtentor
    # só existia em bash, o prompt TINHA de mandar abrir o Git Bash. Com o porte
    # para Python, mandar é que passou a ser o defeito, porque põe de volta um
    # programa a instalar e uma troca de terminal no meio de um roteiro que é
    # todo PowerShell.
    assert "Git Bash" not in prompts["Windows"] and "token.sh" not in prompts["Windows"], (
        "o prompt do Windows voltou a mandar abrir o Git Bash ou rodar o "
        "`token.sh`. Desde 18/09/2026 o passo da chave é um comando do "
        "PowerShell como os outros, e o Git Bash deixou de ser pré-requisito."
    )
    assert "python.org" in prompts["Windows"] and "git-scm.com" in prompts["Windows"], (
        "o prompt do Windows não tem mais a saída pelos sites oficiais. Sem "
        "`winget`, que é o Windows 10, não sobra caminho nenhum."
    )
    # A senha é a fronteira do que o assistente consegue fazer sozinho, e os dois
    # sistemas em que ela aparece têm de dizê-la. Windows fica de fora de
    # propósito: lá o `winget` instala na conta do usuário, e o que o Git abre é
    # a janela de confirmação do sistema, que numa conta de administrador é um
    # clique e não uma senha.
    for sistema in ("Mac", "Linux"):
        assert "senha" in prompts[sistema], (
            f"o prompt do {sistema} não fala da senha. No Linux `apt`, `dnf` e "
            "`pacman` exigem `sudo`; no Mac, instalar o próprio Homebrew pede a "
            "senha, embora `brew install` depois não peça. Nos dois casos quem "
            "digita é a pessoa, e prometer instalação automática aqui é ela "
            "descobrir no meio que não dava."
        )
    for sistema in ("Mac", "Linux"):
        assert ".venv/bin" in prompts[sistema], f"o prompt do {sistema} não aponta para `.venv/bin`."
        assert "Scripts" not in prompts[sistema], (
            f"o prompt do {sistema} fala de `Scripts`, que é a pasta do Windows."
        )
