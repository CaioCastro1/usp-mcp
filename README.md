# usp-mcp

Feito por Caio Castro & João Pedro Gunthen

Consulta em português a sistemas acadêmicos da USP: o cardápio dos bandejões, os prazos e
o material do e-Disciplinas, e o catálogo de disciplinas do JupiterWeb.

Ele não tem interface própria. Você o conecta a um assistente e passa a poder perguntar em
linguagem comum. A resposta vem dos sistemas da USP, no momento da pergunta.

Qualquer assistente que fale MCP serve. Este guia mostra os passos com o Claude, porque é
o que os autores usam, e a seção *Onde ele funciona* conta o resto.

Projeto não-oficial, sem nenhum vínculo com a Universidade de São Paulo.

Você não precisa saber programar para usar, nem contribuir com nada: instale, conecte e
pergunte. Quem quiser mexer no código encontra o combinado em *Escopo e contribuição*.

## O que ele responde

| Pergunta que você faz | Onde ele busca |
|---|---|
| "O que tem no bandejão hoje, na sexta ou na semana inteira?" | Cardápio dos quatro restaurantes, com horário e preço |
| "Quais matérias eu tenho?" | Suas disciplinas no e-Disciplinas: as do semestre primeiro, com a sigla que as outras perguntas usam |
| "O que eu tenho para entregar essa semana?" | Tarefas e questionários do e-Disciplinas, com prazo |
| "Que arquivos tem em PTC3314?" | Lista o material da disciplina: regras, listas, provas antigas |
| "Baixa a lista 2 pra mim" | Baixa o arquivo e diz onde ele ficou no seu computador |
| "Já entreguei o EP1?" | O que você já enviou, o que ficou só como rascunho e se saiu no prazo |
| "Perdi algum prazo?" | O que já venceu e o e-Disciplinas não registra como entregue, rascunho salvo incluído |
| "Como estou de nota?" | As notas que o professor lançou no e-Disciplinas, de todas as disciplinas ou item a item de uma |
| "O professor avisou alguma coisa?" | Os recados nos fóruns da disciplina, o mural de avisos primeiro |
| "Mudou alguma coisa desde ontem?" | O que mexeu na disciplina nos últimos dias: arquivo novo, tópico novo, prazo alterado |
| "Quantos créditos vale MAC0110?" | Créditos, carga horária e ementa pela sigla; programa, bibliografia e avaliação sob pedido |
| "O que preciso ter feito antes de MAT2454?" | Pré-requisitos, pelo seu currículo |

Bandejão e JupiterWeb funcionam para qualquer pessoa. O e-Disciplinas mostra as **suas**
disciplinas, então ele precisa de uma chave sua, e obter essa chave dá um pouco mais de
trabalho. A seção *Configuração* explica.

## Onde ele funciona

O programa roda no seu computador, e o assistente fala com ele ali mesmo. Três lugares
costumam ser confundidos por terem o mesmo nome, e a diferença entre eles decide se a
instalação vai dar certo:

| Onde você pergunta | Funciona? |
|---|---|
| Claude Desktop, que é o **chat** no aplicativo de computador | sim, e é onde entra o bloco de configuração da próxima seção |
| Claude Code, no terminal ou na aba Code do aplicativo | sim, e o registro é por linha de comando |
| claude.ai aberto no **navegador** | não |

O navegador fica de fora porque, do lado do site, não existe nada capaz de conversar com um
programa que está na sua máquina. Não é um defeito à espera de conserto: é a outra face de
uma decisão registrada do projeto, que é a sua chave do e-Disciplinas nunca sair do seu
computador. Pelo navegador nem o bandejão responde, e ele nem chave usa.

O Claude aparece nesse quadro porque é o assistente que os autores usam, e não porque o
projeto precise dele. Por dentro, isto aqui é um servidor MCP comum, o padrão aberto que os
assistentes usam para falar com ferramentas, e não há uma linha de código escrita para um
assistente em particular. A seção *Detalhes técnicos*, no fim do arquivo, diz o que foi
medido a esse respeito.

## Instalando

Este é um MCP: um conjunto de ferramentas que um assistente passa a saber usar. A
instalação tem duas partes. Primeiro você baixa o projeto para o seu computador. Depois
você avisa o assistente que ele existe, e esse segundo passo muda conforme o lugar do
quadro acima.

Os comandos mudam conforme o sistema do seu computador, e por isso esta seção separa Mac,
Windows e Linux. Se não tiver certeza de qual é o seu: Mac tem uma maçã no canto de cima
da tela, Windows tem o botão Iniciar embaixo, e quem usa Linux costuma saber que usa.

### O caminho rápido

Se você já tem o Claude Code, escolha abaixo a mensagem do seu sistema, mande-a para ele
e pule o resto desta seção. Ele instala, confere, configura e te guia nos passos que
precisam da sua mão. Um deles acontece sempre, que é o da chave do e-Disciplinas. O outro
só aparece se faltar o Python ou o `git` no seu computador, e o quanto ele resolve sozinho
aí depende do sistema.

As três mensagens fazem a mesma coisa. O que muda são os caminhos e os comandos de cada
sistema, e é por isso que a mensagem de um sistema não serve num computador de outro: o
assistente segue o que está escrito, e a pessoa que colou não tem como perceber o erro.
A conferência que elas pedem roda sem internet e sem a chave, e é a mesma nos três.

As três mandam o assistente instalar o que faltar, e não só explicar como se instala. Até
onde ele consegue ir sozinho, porém, depende do sistema, e as mensagens dizem isso em vez
de prometer o mesmo nos três. No Windows, o `winget` já vem com o Windows 11 e faz a
instalação na sua conta: o Python entra sem perguntar nada, e o Git abre uma janela de
confirmação do sistema que é sua para responder. No Mac, com o Homebrew já instalado nada
é perguntado, mas instalar o próprio Homebrew pede a sua senha. No Linux, o instalador de
programas da distribuição exige `sudo`, e senha ninguém digita por você. A regra, nos
três, é a mesma: o assistente tenta instalar sozinho primeiro, e só pede "abra este site"
quando não existe instalador de programas ou quando a senha é necessária. Quando for
necessária, ele avisa logo no começo, em vez de você descobrir no meio.

#### No Mac

```text
Instale o usp-mcp neste computador e me conecte a ele. Estou num Mac.

1. Confira se existe Python 3.11 ou mais novo (`python3 --version`) e se existe o `git`,
   que é o programa que baixa o projeto no passo 2. Se faltar algum, instale você mesmo,
   em vez de só me explicar como se instala. Veja primeiro se este computador já tem o
   Homebrew, que é o instalador de programas mais usado no Mac: se `brew --version`
   responder, rode `brew install` com o que estiver faltando (`brew install python`,
   `brew install git`, ou os dois) e siga, porque isso não pede senha. Se não
   houver Homebrew, me diga isso antes de começar qualquer outra coisa: instalar o
   próprio Homebrew pede a minha senha de administrador, e quem digita a senha sou eu.
   Nesse caso me passe o comando que a página brew.sh mostra, espere eu rodar e digitar a
   senha, e continue. Se eu responder que prefiro não instalar o Homebrew, o caminho sem
   ele é baixar o Python em python.org e rodar `xcode-select --install`, que traz o `git`;
   aí também espere eu avisar que terminei.
2. Clone https://github.com/CaioCastro1/usp-mcp em ~/usp-mcp, crie um venv em
   ~/usp-mcp/.venv e instale com `~/usp-mcp/.venv/bin/pip install -e ~/usp-mcp`. Copie
   ~/usp-mcp/.env.example para ~/usp-mcp/.env.
3. Confira a instalação com este comando, que não usa internet nem chave:
   `~/usp-mcp/.venv/bin/python -m usp_mcp.rucard.server --auto-verificar`. Repita
   trocando `rucard` por `jupiter` e depois por `moodle`. Os três têm de terminar sem
   erro. O do moodle vai dizer que o MOODLE_TOKEN está AUSENTE, e isso é esperado: a
   chave é o passo 5.
4. Registre os três servidores no meu Claude Code, no escopo de usuário, com os nomes
   usp-moodle, usp-jupiter e usp-rucard, apontando para
   ~/usp-mcp/.venv/bin/usp-mcp-moodle, ~/usp-mcp/.venv/bin/usp-mcp-jupiter e
   ~/usp-mcp/.venv/bin/usp-mcp-rucard. Use o caminho completo, começando em /Users/,
   no lugar do ~.
5. O e-Disciplinas precisa de uma chave pessoal minha. Você deve rodar `~/usp-mcp/scripts/token.sh`
   e me guie pelo navegador. Não tente fazer esse passo sozinho: ele exige que eu clique.
   UM PASSO POR MENSAGEM: diga o que fazer, espere eu responder que fiz, e só então
   mande o próximo. Não me mande a lista inteira de uma vez.
6. No fim, rode de novo o comando do moodle do passo 3: agora ele tem de dizer que o
   MOODLE_TOKEN está presente. Me diga o que ficou funcionando e o que eu ainda preciso
   fazer.

Me explique em português comum. Eu não sei o que são MCP, venv, token, Homebrew nem
escopo de usuário: quando precisar de uma dessas palavras, diga numa frase o que ela
significa antes de usar.
```

#### No Windows

No Windows 11 você não precisa preparar nada antes de mandar a mensagem: o sistema já vem
com o `winget`, que é o instalador de programas da Microsoft, e a mensagem abaixo manda o
assistente usá-lo para instalar o Python e o Git se estiverem faltando. O Python entra só
na sua conta e não pergunta nada. O Git abre a janela de confirmação do Windows, a que
pergunta se você permite que o programa faça alterações no computador: responder é com
você, e numa conta que não seja de administrador ela pede a senha de uma que seja. Num
Windows mais antigo, que não tenha `winget`, o assistente cai no caminho dos sites
oficiais: o Python em python.org, marcando na instalação a caixa "Add python.exe to
PATH", e o Git em git-scm.com. Aí a instalação é sua, e ele espera.

```text
Instale o usp-mcp neste computador e me conecte a ele. Estou no Windows. Não use
comandos nem caminhos de Mac ou Linux: aqui o ambiente isolado não tem a pasta `bin`,
tem `Scripts`, e os programas terminam em `.exe`. Os comandos abaixo estão em
PowerShell; se você rodar por outro terminal, adapte a forma, mas mantenha `Scripts` e
`.exe`.

1. Confira se existe Python 3.11 ou mais novo (`python --version`) e se existe o `git`,
   que é o programa que baixa o projeto no passo 2. Se o `python` abrir a Microsoft Store
   ou não existir, conte como ausente. Se faltar algum dos dois, instale você mesmo, em
   vez de só me explicar como se instala: use o `winget`, que vem no Windows 11. Os
   comandos são `winget install --id Python.Python.3.13 -e --scope user` e
   `winget install --id Git.Git -e --scope user`; se `winget search Python.Python`
   mostrar uma versão 3 mais nova que a 3.13, use a mais nova. O do Python instala só na
   minha conta e não pergunta nada. O do Git abre a janela de confirmação do Windows, e
   quem responde sou eu: me avise antes que ela vai aparecer, e espere. Depois de
   instalar, abra uma janela nova do PowerShell e siga por ela: a janela que já estava
   aberta não enxerga o que acabou de ser instalado. Se este Windows não tiver `winget`,
   aí sim me diga para instalar pelos sites oficiais, o Python em python.org marcando a
   caixa "Add python.exe to PATH" e o Git em git-scm.com, e espere eu avisar que
   instalei.
2. Clone https://github.com/CaioCastro1/usp-mcp em $HOME\usp-mcp, crie um venv em
   $HOME\usp-mcp\.venv e instale com
   `& $HOME\usp-mcp\.venv\Scripts\pip install -e $HOME\usp-mcp`. Copie
   $HOME\usp-mcp\.env.example para $HOME\usp-mcp\.env.
3. Confira a instalação com este comando, que não usa internet nem chave:
   `& $HOME\usp-mcp\.venv\Scripts\python.exe -m usp_mcp.rucard.server --auto-verificar`.
   Repita trocando `rucard` por `jupiter` e depois por `moodle`. Os três têm de terminar
   sem erro. O do moodle vai dizer que o MOODLE_TOKEN está AUSENTE, e isso é esperado: a
   chave é o passo 5.
4. Registre os três servidores no meu Claude Code, no escopo de usuário, com os nomes
   usp-moodle, usp-jupiter e usp-rucard, apontando para
   C:\Users\MEU-USUARIO\usp-mcp\.venv\Scripts\usp-mcp-moodle.exe,
   C:\Users\MEU-USUARIO\usp-mcp\.venv\Scripts\usp-mcp-jupiter.exe e
   C:\Users\MEU-USUARIO\usp-mcp\.venv\Scripts\usp-mcp-rucard.exe, com o meu nome de
   usuário no lugar de MEU-USUARIO.
5. O e-Disciplinas precisa de uma chave pessoal minha. O comando que a obtém foi
   instalado no passo 2, ao lado dos três do passo 4, e roda aqui mesmo no PowerShell,
   você deve rodar esse comando e me guiar no passo a passo, sem trocar de terminal: \
   `& $HOME\usp-mcp\.venv\Scripts\usp-mcp-token.exe`. Ele abre o
   navegador e fica esperando eu copiar um endereço. Me guie pelo navegador. Não tente
   fazer esse passo sozinho: ele exige que eu clique. UM PASSO POR MENSAGEM: diga o que
   fazer, espere eu responder que fiz, e só então mande o próximo. Não me mande a lista
   inteira de uma vez. Se o comando encerrar sem receber o endereço, logo depois de eu
   copiar rode
   `Get-Clipboard | & $HOME\usp-mcp\.venv\Scripts\usp-mcp-token.exe`.
6. No fim, rode de novo o comando do moodle do passo 3: agora ele tem de dizer que o
   MOODLE_TOKEN está presente. Me diga o que ficou funcionando e o que eu ainda preciso
   fazer.

Me explique em português comum. Eu não sei o que são MCP, venv, token, winget nem
escopo de usuário: quando precisar de uma dessas palavras, diga numa frase o que ela
significa antes de usar.
```

#### No Linux

```text
Instale o usp-mcp neste computador e me conecte a ele. Estou no Linux.

1. Confira se existe Python 3.11 ou mais novo (`python3 --version`) e se existe o `git`,
   que é o programa que baixa o projeto no passo 2. Se faltar algum, diga de uma vez, no
   começo, que essa parte é minha: o instalador de programas daqui (`apt`, `dnf` ou
   `pacman`, conforme a distribuição) só roda com `sudo`, o `sudo` pede a minha senha, e
   senha quem digita sou eu. Não tente instalar sozinho nem me peça a senha. Veja qual
   dos três existe nesta máquina, monte o comando, me explique numa frase o que ele
   instala e espere eu rodar e avisar. Os pacotes são `python3`, `python3-venv` e `git`
   no Debian e no Ubuntu (`sudo apt install python3 python3-venv git`), `python3` e `git`
   no Fedora (`sudo dnf install python3 git`), e `python` e `git` no Arch
   (`sudo pacman -S python git`).
2. Clone https://github.com/CaioCastro1/usp-mcp em ~/usp-mcp, crie um venv em
   ~/usp-mcp/.venv e instale com `~/usp-mcp/.venv/bin/pip install -e ~/usp-mcp`. Copie
   ~/usp-mcp/.env.example para ~/usp-mcp/.env. Se a criação do venv falhar dizendo que
   falta o ensurepip, o pacote do sistema que falta costuma se chamar python3-venv, e
   vale a mesma regra do passo 1: monte o comando com `sudo`, me explique e espere eu
   rodar.
3. Confira a instalação com este comando, que não usa internet nem chave:
   `~/usp-mcp/.venv/bin/python -m usp_mcp.rucard.server --auto-verificar`. Repita
   trocando `rucard` por `jupiter` e depois por `moodle`. Os três têm de terminar sem
   erro. O do moodle vai dizer que o MOODLE_TOKEN está AUSENTE, e isso é esperado: a
   chave é o passo 5.
4. Registre os três servidores no meu Claude Code, no escopo de usuário, com os nomes
   usp-moodle, usp-jupiter e usp-rucard, apontando para
   ~/usp-mcp/.venv/bin/usp-mcp-moodle, ~/usp-mcp/.venv/bin/usp-mcp-jupiter e
   ~/usp-mcp/.venv/bin/usp-mcp-rucard. Use o caminho completo, começando em /home/, no
   lugar do ~.
5. O e-Disciplinas precisa de uma chave pessoal minha. Rode `~/usp-mcp/scripts/token.sh`
   e me guie pelo navegador. Não tente fazer esse passo sozinho: ele exige que eu clique.
   UM PASSO POR MENSAGEM: diga o que fazer, espere eu responder que fiz, e só então
   mande o próximo. Não me mande a lista inteira de uma vez. O script lê a área de
   transferência com `wl-paste` ou `xclip`; se não houver nenhum dos dois, ele avisa, e
   aí, logo depois de eu copiar o endereço, rode
   `wl-paste | ~/usp-mcp/scripts/token.sh` ou
   `xclip -selection clipboard -o | ~/usp-mcp/scripts/token.sh`, conforme o que existir.
6. No fim, rode de novo o comando do moodle do passo 3: agora ele tem de dizer que o
   MOODLE_TOKEN está presente. Me diga o que ficou funcionando e o que eu ainda preciso
   fazer.

Me explique em português comum. Eu não sei o que são MCP, venv, token, sudo nem escopo de
usuário: quando precisar de uma dessas palavras, diga numa frase o que ela significa
antes de usar.
```

O que acontece depois de colar, em qualquer dos três: o assistente roda os primeiros
passos sozinho e mostra o que está fazendo. Se faltar o Python ou o `git`, ele para logo
no primeiro passo, e o que acontece aí depende do sistema, como está acima: no Windows ele
instala, com a janela de confirmação do Git para você responder; no Mac com Homebrew ele
instala e segue sozinho; no Linux, e no Mac sem Homebrew, ele monta o comando e devolve a
vez para você, porque a senha é sua. No passo da chave ele para de novo e passa a falar
com você, uma instrução por vez: abrir a página do e-Disciplinas, achar o link, copiar o
endereço dele. Essa parada acontece sempre, e a seção *Configuração* descreve essa página
com calma, para o caso de você querer saber o que está clicando. Quando ele disser que
terminou, feche e abra o Claude Code: é aí que os três servidores passam a existir para
ele.

### O caminho manual

Você vai precisar do Python 3.11 ou mais novo. Para saber qual você tem, abra o terminal e
cole:

```bash
python3 --version
```

Se o Terminal responder que não conhece o comando `python3`, ou se o número for menor que
3.11, instale a versão atual pelo site python.org antes de seguir. Se você já usa o
Homebrew, `brew install python` também serve, e é o que o caminho rápido pede ao
assistente. Com uma versão mais antiga, o passo de instalação abaixo falha com uma
mensagem do pip que não explica o motivo.

Depois cole estes quatro comandos, um de cada vez:

```bash
git clone https://github.com/CaioCastro1/usp-mcp.git ~/usp-mcp
python3 -m venv ~/usp-mcp/.venv
~/usp-mcp/.venv/bin/pip install -e ~/usp-mcp
cp ~/usp-mcp/.env.example ~/usp-mcp/.env
```

O primeiro baixa o projeto para uma pasta chamada `usp-mcp` dentro da sua pasta pessoal. O
segundo cria, dentro dela, um ambiente isolado, sem alterar o Python nem os programas já
instalados no computador. O terceiro instala o projeto nesse ambiente. O quarto cria o
arquivo de configuração a partir do modelo que vem no projeto: ele já traz preenchida a
única coisa que o bandejão precisa, e é nele que a sua chave do e-Disciplinas vai ficar
guardada depois.

Tudo fica junto em `~/usp-mcp`, de propósito. O programa lê o arquivo de configuração de
dentro dessa pasta, então não instale o projeto em outro lugar separado dela. Para
desinstalar, basta apagar a pasta.

Se o Terminal disser que não conhece o comando `git`, no Mac ele mesmo oferece instalar na
hora: aceite, espere terminar e repita o primeiro comando.

Para conferir se deu certo:

```bash
ls ~/usp-mcp/.venv/bin | grep usp
```

Tem que aparecer `usp-mcp-jupiter`, `usp-mcp-moodle` e `usp-mcp-rucard`. Junto deles
aparece também `usp-mcp-token`, que é o programa da chave do e-Disciplinas e não um
servidor; ele entra na seção *Configuração*.

Agora avise o assistente que eles existem. Em qualquer um dos caminhos abaixo você troca
`SEU-USUARIO` pelo nome da sua conta no computador; se não souber qual é, o comando
`whoami` no Terminal responde.

**No Claude Desktop**, a configuração mora num arquivo. Pelo menu, o caminho até ele é
Configurações, depois Desenvolvedor, depois o botão que edita a configuração (em inglês,
Settings e Developer). Se preferir abrir o arquivo direto, no Mac ele é

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

e no Linux, `~/.config/Claude/claude_desktop_config.json`. Se ele estiver vazio, cole isto
inteiro:

```json
{
  "mcpServers": {
    "usp-rucard": { "command": "/Users/SEU-USUARIO/usp-mcp/.venv/bin/usp-mcp-rucard" },
    "usp-jupiter": { "command": "/Users/SEU-USUARIO/usp-mcp/.venv/bin/usp-mcp-jupiter" },
    "usp-moodle": { "command": "/Users/SEU-USUARIO/usp-mcp/.venv/bin/usp-mcp-moodle" }
  }
}
```

Se já tiver alguma coisa escrita, não troque o conteúdo pelo de cima: as três linhas `usp-`
entram dentro do `mcpServers` que já está lá, depois do que já existe, com uma vírgula
separando uma da outra.

**No Claude Code**, não há arquivo para editar à mão. Cole estes três comandos no Terminal,
um de cada vez:

```bash
claude mcp add usp-rucard --scope user -- /Users/SEU-USUARIO/usp-mcp/.venv/bin/usp-mcp-rucard
claude mcp add usp-jupiter --scope user -- /Users/SEU-USUARIO/usp-mcp/.venv/bin/usp-mcp-jupiter
claude mcp add usp-moodle --scope user -- /Users/SEU-USUARIO/usp-mcp/.venv/bin/usp-mcp-moodle
```

O `--scope user` é o que faz o registro valer em qualquer pasta, e não só na que você
estiver quando rodar o comando.

**Em outro assistente que fale MCP**, a ideia é a mesma: apontar o programa para os três
comandos que apareceram no passo anterior. Onde essa configuração se escreve muda de
assistente para assistente, e quem diz é a documentação de cada um.

No Linux, o começo do caminho é `/home/` em vez de `/Users/` nos dois blocos. No Windows os
caminhos são outros, e a subseção *No Windows*, logo abaixo, diz o que muda e o que ainda
não foi conferido por ninguém.

Feche e abra o assistente. Pronto: bandejão e JupiterWeb já respondem. O e-Disciplinas
ainda vai reclamar que falta a chave, e é a próxima seção.

Se algo não funcionar, este comando diz o que está no lugar e o que não está, sem usar
internet nem chave:

```bash
~/usp-mcp/.venv/bin/python -m usp_mcp.rucard.server --auto-verificar
```

Troque `rucard` por `jupiter` e por `moodle` para conferir os outros dois. O do moodle
dizer que a chave está ausente é o esperado até a próxima seção. No Windows, o comando é
`& $HOME\usp-mcp\.venv\Scripts\python.exe -m usp_mcp.rucard.server --auto-verificar`.

### No Windows

Os três programas são Python puro, sem uma linha específica de sistema operacional, e a
pasta onde guardam arquivos baixados existe no Windows também. Não há razão conhecida para
não funcionarem lá. Mas há uma diferença entre "não há razão conhecida" e "alguém viu
funcionar": **nenhum dos autores rodou o projeto no Windows**, e tudo nesta subseção foi
escrito num Mac, lendo documentação. Se você for a primeira pessoa a tentar, o que
funcionou e o que não funcionou é exatamente o relato que uma issue pede.

O que muda na instalação: o ambiente isolado que o Python cria no Windows não tem a pasta
`bin`, tem `Scripts`, e os comandos são um pouco diferentes. No PowerShell:

```powershell
git clone https://github.com/CaioCastro1/usp-mcp.git $HOME\usp-mcp
python -m venv $HOME\usp-mcp\.venv
& $HOME\usp-mcp\.venv\Scripts\pip install -e $HOME\usp-mcp
Copy-Item $HOME\usp-mcp\.env.example $HOME\usp-mcp\.env
```

Os três comandos instalados ficam em `$HOME\usp-mcp\.venv\Scripts\`, com a extensão
`.exe`: `usp-mcp-rucard.exe`, `usp-mcp-jupiter.exe` e `usp-mcp-moodle.exe`. É para eles
que o assistente aponta. No Claude Desktop o arquivo de configuração fica em
`%APPDATA%\Claude\claude_desktop_config.json`, e dentro de JSON cada barra invertida se
escreve dobrada:

```json
"usp-rucard": { "command": "C:\\Users\\SEU-USUARIO\\usp-mcp\\.venv\\Scripts\\usp-mcp-rucard.exe" }
```

No Claude Code é o mesmo comando dos outros sistemas, com o caminho do Windows:

```powershell
claude mcp add usp-rucard --scope user -- C:\Users\SEU-USUARIO\usp-mcp\.venv\Scripts\usp-mcp-rucard.exe
```

Para conferir o que ficou no lugar, sem internet e sem chave:

```powershell
& $HOME\usp-mcp\.venv\Scripts\python.exe -m usp_mcp.rucard.server --auto-verificar
```

Com `jupiter` e `moodle` no lugar de `rucard`, confere os outros dois. Com isso, bandejão
e JupiterWeb devem responder. De novo: em teoria; ninguém conferiu.

A chave do e-Disciplinas sai por um quarto comando, instalado junto com os três acima e na
mesma pasta: `usp-mcp-token.exe`. Ele roda no PowerShell, como o resto desta subseção:

```powershell
& $HOME\usp-mcp\.venv\Scripts\usp-mcp-token.exe
```

Este era o ponto fraco daqui até 18/09/2026, porque o programa que obtém a chave só
existia em bash e o Windows não tem bash: quem instalava no Windows precisava instalar
também o Git Bash e trocar de terminal só neste passo. O programa foi reescrito em Python
e virou o comando acima. O `scripts/token.sh` continua existindo para quem está no Mac ou
no Linux, e chama o mesmo código.

O programa sabe achar o Python de `.venv\Scripts`, ler a área de transferência pelo
PowerShell (`Get-Clipboard`) e abrir o navegador pelo `rundll32`. Antes de 18/09/2026 a
vigia descrita na seção *Configuração* não existia no Windows, e foi isso que o dono do
projeto encontrou ao instalar lá. Essas três escolhas estão testadas com dublês: o que
está provado é que o programa escolhe a ferramenta certa quando ela existe, não que a
ferramenta faz o que se espera num Windows real. Se a vigia não funcionar, o fluxo em dois
passos continua valendo: copie o endereço do link e rode

```powershell
Get-Clipboard | & $HOME\usp-mcp\.venv\Scripts\usp-mcp-token.exe
```

Dentro do WSL vale o caminho do Linux, o `scripts/token.sh`, e ele reconhece esse caso:
lê a área de transferência do Windows pelo `powershell.exe` e abre o navegador do Windows
pelo `wslview`. Mas o clone, o ambiente isolado e o `.env` que o script grava têm de ser
os mesmos que o assistente usa, e um ambiente isolado criado dentro do WSL não serve a um
assistente rodando no Windows. Quem instalar pelo WSL tem de instalar tudo lá e apontar o
assistente para lá. Isso tampouco foi conferido.

Os outros arquivos de `scripts/`, o de verificação antes de commit incluído, seguem sem
adaptação de propósito: são de quem mantém o projeto, e não de quem usa, e ainda
procuram `.venv/bin/python`. Nenhum passo da instalação passa por eles. Se você usar o
caminho rápido, a mensagem *No Windows* de lá já traz estes caminhos e este comando da
chave; a de Mac não serve aqui, e o assistente não tem como perceber sozinho.

## Configuração

Só o e-Disciplinas precisa disto. Bandejão e JupiterWeb funcionam sem nada.

A chave é sua e pessoal, e cada pessoa obtém a dela. Ela nunca sai do seu computador, e é
por isso que ninguém pode te dar uma pronta.

O script que a obtém já está no seu computador, na pasta do projeto que a instalação
baixou. Cole no terminal:

```bash
~/usp-mcp/scripts/token.sh
```

Se você instalou pelo caminho rápido, a pasta é a mesma.

No Windows o comando é outro, e roda no PowerShell:
`& $HOME\usp-mcp\.venv\Scripts\usp-mcp-token.exe`. Ele foi instalado junto com os três
servidores, e não fica na pasta `scripts`. É o mesmo programa do bloco acima, e tudo o que
esta seção diz vale para ele.

Ele abre uma página do e-Disciplinas no seu navegador. Você precisa já estar logado na
Senha Única. A página mostra três coisas, e duas são distração: a caixa verde "O seu
cadastro foi confirmado" e o botão cinza "Ambientes". O que importa é o link azul escrito
"Clique aqui se a aplicação não abrir automaticamente".

Clique nele com o **botão direito** e escolha "copiar endereço do link". Não clique com o
esquerdo: isso tenta abrir o aplicativo do Moodle e não copia nada. Volte no Terminal e
aperte Enter.

O script confere o que você copiou, testa a chave contra a USP e só então guarda. Se você
copiou o endereço errado, ele avisa e não estraga nada. A chave nunca aparece na tela.

Se quem roda o script é o assistente, e não você no Terminal, não há Enter para apertar:
o script fica de vigia no clipboard por até 90 segundos, lendo o que está lá a cada meio
segundo, e segue sozinho assim que aparecer um endereço que comece com
`moodlemobile://token=`. Ele avisa disso antes de começar. Só esse endereço faz o script
agir; qualquer outra coisa que você copiar nesse intervalo ele ignora, sem guardar,
mostrar ou dizer o tamanho, e o que já estava no clipboard antes não conta. Se você
copiar o endereço errado, ele diz o que veio errado e continua esperando. Passados os 90
segundos sem o endereço, ele para de ler e diz como entregar depois:
`pbpaste | ~/usp-mcp/scripts/token.sh` (no Windows, no PowerShell:
`Get-Clipboard | & $HOME\usp-mcp\.venv\Scripts\usp-mcp-token.exe`). Para rodar sem essa
vigia, defina `USP_MCP_VIGIA_SEGUNDOS=0` antes do comando. Num computador
sem ferramenta de clipboard (sem `pbpaste`, `wl-paste`, `xclip` nem PowerShell) a vigia não
existe e o script diz isso.

Quando é você no Terminal, o script para entre um passo e o outro e espera um Enter:
abrir a página, achar o link, copiar o endereço. É de propósito: as instruções todas de
uma vez ninguém lê. `USP_MCP_SEM_PAUSA=1` tira as paradas para quem já sabe o caminho.

No WSL, não instale `xclip` achando que resolve: ele lê a área de transferência do lado
Linux, e a sua está do lado Windows. O script já prefere o caminho certo ali.

Sobre o que vale no Windows, e o que ainda não foi conferido lá, está
na subseção *No Windows*, acima.

Ela fica guardada no arquivo `~/usp-mcp/.env`, na linha `MOODLE_TOKEN`. É o mesmo
arquivo que o programa lê, então não há nada para copiar de um lugar para outro: feche e
abra o assistente e o e-Disciplinas passa a responder. Você não precisa abrir esse
arquivo, mas se um dia abrir, é essa a linha.

Ela vence com o tempo e pode ser cancelada em `edisciplinas.usp.br`, em gerenciar tokens.
Se um dia o e-Disciplinas parar de responder, rode `~/usp-mcp/scripts/token.sh` de novo,
ou, no Windows, o comando do PowerShell acima.

## Usando

Depois de conectado, é só perguntar. Alguns exemplos do que funciona:

- "o que tem no bandejão da Física hoje no jantar?"
- "que dia tem lasanha essa semana?"
- "tem alguma coisa vencendo nos próximos 3 dias?"
- "quais arquivos tem em PTC3314?"
- "baixa o EP1 de PTC3314 e me explica o que ele pede"
- "quantos créditos vale MAC0110 e qual é a ementa?"

A última encadeia duas coisas: o projeto baixa o PDF e o assistente lê o arquivo para
responder.

Se você pedir algo que ele não sabe, a resposta diz o que faltou em vez de inventar. Vale
ler a seção *O que o projeto não responde* antes de concluir que quebrou.

## Como funciona

Cada um dos três comandos é um programa que fica em segundo plano aguardando perguntas do
assistente. Quem conversa com ele é o assistente, não você: executá-lo direto no terminal
não produz saída, porque não é para ser usado assim.

Quem decide qual ferramenta usar é o assistente, lendo a descrição de cada uma diante da
sua pergunta. Por isso as descrições são escritas na linguagem de quem pergunta, e não com
o nome técnico da função por trás.

O acesso à USP é limitado de propósito. De todas as operações que a sua chave permitiria,
só um punhado está liberado aqui, e por padrão todas são de leitura. Começar uma prova,
responder questionário ou mandar mensagem em seu nome estão bloqueados e continuam
bloqueados mesmo se alguém ligar a permissão de escrita. Entregar trabalho é a única
exceção que pode ser ligada, e a seção *Entregando trabalho* explica com que cuidados. O
motivo de tanta cerca é simples: quem escolhe o que chamar é um assistente interpretando
uma frase ambígua, e "manda ver a lista de exercícios" não pode ter caminho até entregar o
trabalho.

A sua chave do e-Disciplinas fica só no seu computador. Ela não vai para nenhum servidor,
nem para a nuvem. É por isso que o e-Disciplinas só funciona rodando local.

As respostas da USP são enxugadas antes de chegar ao assistente. A lista de disciplinas,
por exemplo, sai de 104.712 bytes para 7.816: o resto é metadado que não responde pergunta
nenhuma e só ocuparia espaço.

## Entregando trabalho

Por padrão o projeto só lê. Entregar trabalho no e-Disciplinas é a única exceção que pode
ser ligada, e ela vem desligada: enquanto você não ligar, essas ferramentas nem aparecem
para o assistente.

Para ligar, ponha `USP_MCP_ENTREGA=1` no arquivo `.env` e reinicie.

Aparecem então duas coisas separadas: salvar rascunho e entregar para correção. São duas
de propósito, porque "salva aí" e "entrega isso" estão a uma palavra de distância e só uma
das duas tem volta.

Entregar nunca acontece no primeiro pedido. O primeiro devolve um plano: qual atividade,
que arquivos estão anexados, qual é o prazo e o que exatamente vai mudar. Só o segundo
pedido, confirmando aquele plano, escreve. Se alguma coisa mudou entre um e outro, a
confirmação é recusada e o plano volta atualizado.

Três coisas para saber antes de ligar:

- Entregar para correção não tem desfazer, nem aqui nem pelo site.
- Salvar rascunho só funciona em atividade de texto online. Enviar arquivo não existe neste
  projeto atualmente, mas está sendo implementado.
- Trabalho em grupo é recusado, porque a entrega valeria também por pessoas que não estão
  na conversa.
- O MCP não responde testes ou questionários valendo nota, ou com submissões limitadas.

A confirmação em duas etapas protege contra acidente e contra frase ambígua. Ela não é um
cadeado: quem roda o projeto dentro de um assistente que também tem acesso ao terminal
pode contornar qualquer trava que o programa tente impor. Ligar ou não é decisão sua, e
vale tomá-la sabendo disso.

## O que o projeto não responde, e por quê

Histórico escolar, evolução do curso e saldo do RUCard ficam de fora. O motivo é falta de
caminho, não de trabalho. Medido em 14/09/2026:

- A parte pública e organizada do JupiterWeb é o catálogo de entrada. A grade dos cursos de
  ingresso da Poli para no 5º semestre (verificado em quatro cursos), e da ênfase (7º) e do
  módulo (9º) em diante não há grade, requisito nem código de curso alcançável.
- Dado pessoal exige a área logada, que não oferece chave como o Moodle. Só sessão de
  navegador, com dois cookies e um tempo de expiração ainda não medido.

O roteiro para medir isso está em
`docs/superpowers/plans/2026-09-14-jupiter-sessao-recon.md`. Nada dele foi executado.

Também não existem: histórico de cardápio, saldo do cartão, horário, sala e vagas.

Aviso de professor passou a existir em 14/09, e cobre o que foi escrito no fórum da
disciplina. Recado dado em sala e não postado não chega até lá, e nem o projeto nem o
e-Disciplinas têm como saber dele. Quem escreveu cada tópico não sai na resposta: o fórum é
o único lugar do e-Disciplinas em que a resposta traz nome de outras pessoas, e esses nomes
param aqui.

As notas que o projeto mostra são as que o professor lançou no e-Disciplinas, e só elas.
Prova corrigida no papel, nota combinada em aula e o histórico oficial da USP não estão
ali, e nenhuma soma que o projeto fizesse seria a sua média de verdade. O comentário
escrito do professor também não sai: a resposta avisa quando existe um para você ler na
página da disciplina.

A lista de disciplinas é a do e-Disciplinas, e o e-Disciplinas não é a sua matrícula
oficial. O que separa uma matéria "em andamento" de uma encerrada ali são as datas que o
professor declarou no espaço da disciplina: trancamento e cancelamento não chegam até lá, e
uma matéria sem data declarada aparece à parte, dizendo que não dá para saber. Matéria de
semestre passado continua na lista, com a sigla, porque você ainda pergunta sobre ela.

"Já entreguei o EP1?" responde só sobre tarefa. Questionário não entra, e prova marcada só
no quadro da sala não existe em sistema nenhum. A resposta diz isso quando você pergunta.

A lista do que ficou para trás é a mesma coisa vista pelo outro lado, e ela tem um limite
que vale ler devagar: o projeto sabe o que está registrado no e-Disciplinas, não o que você
fez. Entrega no papel, por e-mail, num sistema do laboratório, ou que o professor recebeu e
nunca lançou no site, não aparece como enviada. Por isso a resposta nunca diz que você não
entregou: ela diz que não há registro, e manda confirmar. Quando o professor já lançou a
nota sem receber arquivo, ela separa esse caso e não conta como falta.

Uma limitação que costuma confundir: ao listar material, o projeto diz o nome, o tipo e o
tamanho de cada arquivo, mas não devolve o endereço dele. Endereço sem a credencial não
abre, e quem baixa de fato é a ferramenta de download, sem nunca pôr a sua chave num
endereço.

## Escopo e contribuição

O repositório é público para ler, baixar e usar, sob licença MIT: você pode usar, modificar
e redistribuir, desde que mantenha o aviso de autoria. O texto completo está no arquivo
[`LICENSE`](LICENSE).

O que este projeto mais precisa não é código: é saber quando a USP mudou alguma coisa e a
resposta parou de bater. Se uma pergunta que funcionava parou, ou se o passo da chave
travou, [abra uma issue](https://github.com/CaioCastro1/usp-mcp/issues/new/choose): há um
modelo para cada um dos dois casos, e o relato leva meio minuto. **Nunca cole o valor do
seu token**, nem em issue, nem em log.

Mudança no código precisa de acordo antes da PR, porque o projeto se apoia em invariantes
que não são óbvios lendo o diff. Se você quer mexer, abra a issue primeiro; o combinado
inteiro está em [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

Uma observação para quem instalou pelo assistente e não veio programar: a pasta do projeto
tem, junto com o código, os documentos de quem o mantém, e um assistente que os lê pode
começar a propor mexer no código, abrir PR ou rever decisão do projeto. Isso é engano dele,
não pedido seu: basta dizer que você só quer usar. Desde 17/09/2026 o padrão já é esse, e
o raciocínio está em [`docs/agents/PAPEL-DA-SESSAO.md`](docs/agents/PAPEL-DA-SESSAO.md).
Na direção contrária vale o mesmo: se você **quer** contribuir, dizer isso uma vez basta.

## Rodando a partir do código

Esta seção é para quem vai mexer no código. Quem só quer usar, inclusive o e-Disciplinas,
já tem tudo o que precisa pela seção *Instalando*: ela baixa o projeto inteiro, e o
script da chave vem junto.

```bash
git clone git@github.com:CaioCastro1/usp-mcp.git && cd usp-mcp
uv venv
uv pip install -e ".[dev]"
cp .env.example .env
./scripts/gate.sh
```

`uv` cria o mesmo `.venv/` que `python3 -m venv` criaria (é o que `scripts/servidor.sh` e o
`.mcp.json` procuram), com uma diferença que importa neste Mac: instala por hardlink a partir
de um cache único, então dez checkouts não custam dez cópias do SDK. Se não tiver `uv`,
`python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"` continua funcionando.

O `cp` vem antes do gate porque sem `.env` ele reprova. A hash do RUCard é o único valor
que o gate precisa, e ela já vem preenchida no exemplo: é a chave embutida no app oficial,
pública e compartilhada, não credencial de ninguém. O gate roda offline e não toca a USP.

O `.mcp.json` versionado registra os três servidores sem segredo nenhum. Abra um cliente
MCP neste diretório e pergunte. Cada entrada chama `scripts/servidor.sh <sistema>`, e quem
resolve a raiz do checkout é o script, não o cliente.

Cliente que não faz `cd` no diretório do projeto, como o Claude Desktop, precisa do
caminho absoluto do lançador:

```json
{
  "mcpServers": {
    "usp-rucard": {
      "command": "<CAMINHO-DO-CHECKOUT>/scripts/servidor.sh",
      "args": ["rucard"]
    }
  }
}
```

O `.mcp.json` é relativo de propósito, porque é versionado e caminho absoluto de máquina
não entra em arquivo rastreado. O absoluto fica no arquivo de config da sua máquina.

### Detalhes técnicos

Três servidores MCP, treze ferramentas, quinze com a escrita de entrega ligada.
Comunicação por stdio, JSON-RPC, um processo por servidor. As treze têm medição contra a
USP de verdade registrada no §9 do `SPEC1.md`. As quatro de 14/09 (`avisos`, `o_que_mudou`,
`disciplinas` e `atrasadas`) nasceram numa cópia sem chave, contra resposta escrita à mão
ou capturada em agosto, e foram medidas ao vivo no mesmo dia; a metade de `atrasadas` que
era escrita à mão, o estado de cada entrega, virou captura real em 15/09
(`fixtures/moodle/submission_status_ec1.json`). As duas de entrega não entram em teste ao
vivo em fase nenhuma, de propósito.

Nada aqui é escrito para um assistente específico. A dependência de execução é uma só, o
`mcp`, que é o SDK oficial do protocolo, e a única vez em que a palavra Claude aparece
dentro de `usp_mcp/` é numa docstring citando o `CLAUDE.md`. A versão do protocolo é
negociada com quem chega, e não fixada numa só. Medido em 16/09/2026, nos três servidores:
cliente pedindo `2024-11-05` recebe `2024-11-05`, pedindo `2025-03-26` recebe `2025-03-26`
e pedindo `2025-06-18` recebe `2025-06-18`. Outros clientes MCP, como Cursor, Windsurf,
Zed, Continue e a extensão do VS Code, falam esse mesmo protocolo. Isso é o que se sabe
pelo protocolo em comum, e não o relato de alguém que tenha rodado este projeto dentro
deles: ninguém rodou ainda.

| Servidor | Ferramentas |
|---|---|
| `usp-rucard` | `bandejao` |
| `usp-moodle` | `o_que_vence`, `material`, `baixar_arquivo`, `diagnostico`, `ja_entreguei`, `notas`, `avisos`, `o_que_mudou`, `disciplinas`, `atrasadas` |
| `usp-moodle`, só com `USP_MCP_ENTREGA=1` | `salvar_rascunho`, `entregar` |
| `usp-jupiter` | `disciplina`, `requisitos` |

A superfície é allowlist: só saem daqui as funções nomeadas nela, por igualdade exata de
nome, e o default é negar. Sobre ela existe o bloqueio permanente do §2.2, que vale mesmo
com `USP_MCP_ALLOW_WRITES` ligada. A sua chave alcança 447 funções neste site, e é esse
número que faz as duas camadas existirem.

**As duas ferramentas que escrevem não existem por padrão.** `salvar_rascunho` e `entregar`
só aparecem no `tools/list` com `USP_MCP_ENTREGA=1` no ambiente. Desligada, elas não
existem, e não é o caso de uma ferramenta visível que recusa. Ligada, cada uma ainda exige
duas chamadas: a primeira devolve um plano do que mudaria, com um código; a segunda,
repetindo o código, é a que escreve. Se o estado mudar no e-Disciplinas entre as duas, o
código não confere e a resposta traz o plano novo em vez de escrever. Isso é forte contra
acidente e **fraco contra um modelo com shell**, e essa fraqueza é conhecida e aceita: quem
liga a flag precisa saber o que ligou.

`baixar_arquivo` entrega o caminho e não o conteúdo. Um blob em base64 custaria cerca de
302k tokens no PDF médio, e extrair o texto no servidor perderia as figuras. Numa lista
manuscrita escaneada isso devolveria 9 bytes e chamaria de sucesso (§9, 01/09 e 03/09). O
arquivo cai em `~/.cache/usp-mcp/moodle/`.

São três comandos e não um com argumento: o nome de cada um é o mesmo `serverInfo.name`
que o servidor responde no `initialize`. O porquê está no `pyproject.toml`. O
`usp-mcp-token`, que obtém a chave do e-Disciplinas, é um quarto comando instalado ao lado
deles, e não é servidor: é o mesmo programa que `scripts/token.sh` chama, e existe como
comando porque no Windows não há bash.

A conferência que a seção *Instalando* pede, `--auto-verificar`, existe nos três
servidores desde 31/08/2026 e é offline: lista as ferramentas expostas, diz se achou o
`.env` e se o SDK do MCP está instalado, e compara o schema que o modelo vê com a
assinatura de cada ferramenta. No Moodle diz também se a chave do e-Disciplinas está
presente, pela contagem de caracteres e nunca pelo valor. Ela só responde por
`python -m usp_mcp.<sistema>.server --auto-verificar`, com o Python do `.venv`, e de
qualquer pasta. Não responde pelo comando instalado: `usp-mcp-rucard --auto-verificar`
ignora o argumento, sobe o servidor stdio e, sem cliente na outra ponta, sai com código 0
sem imprimir nada (medido em 18/09/2026). Por isso o README só ensina a primeira forma.
Ela entrou no lugar do `scripts/gate.sh` e da ferramenta `diagnostico` no roteiro de
instalação em 18/09/2026: o gate é verificação de pré-commit, procura `.venv/bin/python`
e no Windows caía para o `python3` da Microsoft Store, com 58 testes reprovando por isso;
e `diagnostico` exige a chave e faz uma chamada à USP, que é justamente o que ainda não
existe no meio da instalação.

Desde 18/09/2026 os três prompts do caminho rápido mandam o assistente instalar o que
faltar, e não só ensinar a instalar. Os nomes de pacote foram conferidos no mesmo dia, e
não escritos de memória. No `winget`, `Python.Python.3.13` e `Git.Git` existem nos
manifestos oficiais (`microsoft/winget-pkgs`) e os dois trazem instalador de escopo de
usuário; o do Python entra com `InstallAllUsers=0 PrependPath=1` e sem exigência de
elevação, e o do Git declara `ElevationRequirement: elevatesSelf`, que é a janela de
confirmação do Windows que o README avisa em vez de prometer instalação calada. No
Homebrew, `brew install python` e `brew install git` resolvem para `python@3.14` e `git`.
No Linux, `python3`, `python3-venv` e `git` existem no Debian, `python3` e `git` no
Fedora, e `python` e `git` no Arch. O que está conferido é que os nomes existem e o que os
manifestos declaram; nenhum desses comandos foi rodado num Windows ou num Linux de
verdade. O `sudo` do Linux é o motivo de lá o texto parar e devolver a vez: senha não se
digita por procuração, e descobrir isso no meio do caminho é pior do que ler no começo.

Medido em 14/09/2026: instalação editável num venv limpo, e os três comandos subindo de
`/tmp` com cliente MCP real. Em 16/09/2026 o caminho manual da seção *Instalando* foi
percorrido inteiro numa pasta limpa, com ambiente vazio: a hash do bandejão chega ao
comando instalado a partir do `.env` do clone, e `scripts/token.sh` grava no mesmo
arquivo. Instalar o pacote sozinho, fora do clone (`pip install git+...`), não funciona:
o programa procura o `.env` na pasta do projeto, e em `site-packages` não há nenhum. Era o
que este README ensinava até 16/09. `pipx` e `uvx` não foram exercitados, e
`pip install --user` é barrado pelo PEP 668 no Python do Homebrew. Empacotar como MCP
Bundle (`.mcpb`) segue sem teste, descrito no §6.1 por leitura de documentação.

Ferramenta não nasce por conveniência: o critério está no §5, e as questões abertas do §4
fecham com dado registrado no §9. O `SPEC1.md` é a autoridade do projeto.

- `usp_mcp/`, os servidores, um pacote por sistema
- `tests/`, quatro camadas: política, contrato e handshake offline, `live` atrás de env var
- `notas/`, análise por sistema, com custo medido em bytes e tokens
- `fixtures/`, respostas capturadas; as do Moodle só entram no git depois de higienizadas, e o cru delas (`fixtures/moodle/raw/`) fica fora
- `scripts/`, chamadores da descoberta e o gate de pré-commit
- `docs/decisions/BACKLOG-correcoes.md`, a dívida que está em aberto
