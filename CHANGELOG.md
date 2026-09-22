# Mudanças

O que mudou entre uma versão e a seguinte, para quem usa o projeto.

Este arquivo responde "o que mudou desde a versão que eu tenho". Ele **não** é o
registro de decisões: o porquê de cada escolha, com o dado que a fechou, mora no
§9 do `SPEC1.md`, e os desenhos ficam em `docs/superpowers/specs/`. Aqui vai o
efeito, lá vai a razão.

As versões seguem `MAIOR.MENOR.CORREÇÃO`. O que a versão promete está escrito no
§9 de 15/09/2026: nome de ferramenta e formato de argumento são interface
pública, e mudá-los é quebra. O texto das respostas fica de fora dessa promessa,
porque quem o lê é um modelo e travá-lo congelaria a parte que melhora com uso.

## Não lançado

### Novidades

- **A resposta da semana do bandejão encolheu 9%.** "Que dia tem lasanha essa
  semana?" ocupava 2.642 tokens do contexto do assistente e passa a ocupar 2.408,
  sem perder nada: o item que se repete em quase todas as refeições sobe uma vez
  para o rodapé, e as refeições que trazem outra coisa no lugar são nomeadas ali
  e seguem com a lista inteira na linha delas. Em bytes o corte é maior, 12%, mas
  o que conta é o token. A resposta de um dia não mudou.

- **Obter a chave do e-Disciplinas não precisa mais de bash.** O programa que
  obtém a chave foi reescrito em Python, e o pacote passa a instalar o comando
  `usp-mcp-token` ao lado dos três servidores. No Windows ele vira
  `.venv\Scripts\usp-mcp-token.exe`, e a pessoa roda do PowerShell que já abriu
  para instalar, sem Git Bash. O que ele faz é o mesmo de antes: abre a página,
  fica de vigia na área de transferência, confere a chave contra a USP e só então
  grava. `./scripts/token.sh` continua existindo e faz a mesma coisa (ele chama o
  Python); quem está no Mac ou no Linux não muda nada. No PowerShell, o fluxo em
  dois passos é `Get-Clipboard | usp-mcp-token`.

### Ainda não verificado contra dado real

- O comando no Windows foi escrito e testado num Mac, com dublês das ferramentas
  do Windows. O que está provado é que ele escolhe `Get-Clipboard`, `rundll32` e
  `curl.exe` quando é lá que está; não que essas ferramentas fazem o esperado num
  Windows de verdade. A lista do que conferir está no desenho de 18/09.

## 1.1.0 — 18/09/2026

Primeira leva depois da publicação. Nada do que existia mudou de nome ou de
formato; tudo aqui é acréscimo ou conserto.

### Novidades

- **Questionário agora tem resposta.** No Moodle, atividade e questionário são
  objetos diferentes, e até aqui só o primeiro era tratado: quem perguntasse
  sobre um questionário recebia "não passa por aqui". A ferramenta
  `questionarios` responde as três perguntas que ficavam sem resposta: já fiz,
  quantas tentativas sobram, e fechou sem eu ter feito. É leitura; abrir ou
  responder tentativa continua recusado.
- **O material lista os links que o professor põe no meio do texto.** Link solto
  dentro de um bloco de texto da página não saía: a ferramenta só devolvia
  arquivo e link postado como recurso. Quem perguntasse pelos slides podia ouvir
  que não havia nenhum, com os slides linkados na página.
- **O assistente passa a saber que existe uma capacidade desligada.** A escrita
  de entrega continua desligada por padrão, e agora o servidor conta que ela
  existe, o que custa e como se liga, sem pôr nada de novo para ser chamado.
- **Obter a chave do e-Disciplinas ficou de um passo.** O script abre a página
  sozinho e fica de vigia: assim que você copia o endereço do link, ele segue
  sem precisar de aviso. Copiar a coisa errada deixou de custar uma rodada, e o
  que ele lê da área de transferência está declarado antes de começar.

### Consertos

- Duas leituras de questionário que expunham enunciado e tentativa em curso
  entraram na lista de recusa permanente, antes que um teto por prefixo as
  alcançasse por tabela.
- O assistente tratava quem clona o repositório como mantenedor do projeto.
  Agora o padrão é sessão de uso, e manutenção é assumida só quando a pessoa
  pede ou quando o disco já respondeu.
- O canário da higienização comparava duas capturas diferentes e reprovava na
  máquina de quem tem as respostas cruas, sem nada estar errado.
- A documentação afirmava que um dos caminhos de envio de mensagem estava
  liberado, quando ele está recusado desde 31/08. Errava para o lado permissivo.

### Decidido e não feito

- **Enviar mensagem pelo Moodle: não.** Ler mensagem não reabre decisão nenhuma;
  enviar reabre, e contradiz a única recusa que o desenho da escrita declarou
  inegociável, que é não escrever em nome de quem não está na conversa. O
  desenho com as alternativas está em
  `docs/superpowers/specs/2026-09-17-mensagem-pelo-moodle-design.md`.

### Ainda não verificado contra dado real

- O conserto dos links no texto está correto por leitura do código e por teste
  com dado montado. Nenhuma captura que o projeto tem reproduz o caso, porque as
  duas disciplinas capturadas não usam bloco de texto. Há um teste que reprova
  no dia em que uma captura com esse formato entrar.
- A ferramenta de questionário depende de campos que a conta de aluno pode não
  receber. Ela degrada declarando o que não conseguiu ver, em vez de inventar.

## 1.0.0 — 17/09/2026

Primeira versão pública, sob licença MIT. Treze ferramentas em três servidores:
bandejão do RUCard, prazos e material do e-Disciplinas, catálogo do JupiterWeb.
