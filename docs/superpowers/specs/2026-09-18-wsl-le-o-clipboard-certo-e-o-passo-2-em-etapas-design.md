# O leitor de clipboard no WSL, e o passo 2 em etapas — design

> 18/09/2026, no mesmo dia e depois do `2026-09-18-windows-design.md`. Este
> documento **completa** aquele num ponto e **não** o revisa: o raciocínio que
> pôs `wslview` na frente de `open` valia igual para o leitor de clipboard, e
> faltava atravessar. O resto daquele desenho fica como está.

- **Origem:** passagem real de uma terceira usuária, em Windows, relatada por
  print da conversa dela com o próprio agente.
- **Arquivos:** `scripts/token.sh`, `tests/moodle/test_token_navegador.py`,
  `README.md`, `docs/decisions/BACKLOG-correcoes.md`
- **Não tocados, de propósito:** o lançador e o Python do `token.sh` (o
  `fix/windows` já resolveu os dois, e melhor — ver §4), `usp_mcp/`, os outros
  scripts.

## 1. O dado

Duas coisas saíram do relato, e elas são independentes.

A primeira: o agente dela inventou
`powershell.exe -NoProfile -Command "Get-Clipboard" | ./scripts/token.sh`, que
naquele momento não estava escrito em lugar nenhum. O `fix/windows` cobriu isso
horas depois, e essa metade já está resolvida.

A segunda, nas palavras dela: *"é MUITO texto que aparece quando ele é instalado,
ninguém lê. não tem como ir aparecendo passo a passo gradualmente?"*

## 2. O leitor de clipboard no WSL

### O defeito

O `fix/windows` põe o PowerShell como **último** candidato a leitor, e para Git
Bash isso está certo: lá não existe `pbpaste`, `wl-paste` nem `xclip`, e o último
é o único.

No WSL não. Sob WSLg — WSL2 com interface gráfica, o padrão no Windows 11 —
`$DISPLAY` vem preenchido e `xclip` **passa** no teste. O leitor escolhido é então
o do lado Linux, enquanto a pessoa copia o endereço no navegador do **Windows**: a
vigia espera os 90 s inteiros por uma mudança que acontece do outro lado, sem
dizer nada.

O argumento já estava escrito, e para o lançador. O §4 daquele desenho põe
`wslview` na frente de `open` dizendo, com todas as letras: *"com o WSLg,
`xdg-open` abriria um navegador Linux, que não está logado na Senha Única"*. É o
mesmo argumento, o mesmo `$DISPLAY`, o mesmo lado errado — só que aplicado ao
clipboard.

E o README daquele PR **já promete o comportamento certo**: *"O WSL também roda o
script, e ele reconhece esse caso: lê a área de transferência do Windows pelo
`powershell.exe`"*. Hoje isso é verdade no WSL sem interface gráfica e falso sob
WSLg. O que esta mudança faz é fazer o código cumprir a frase que já está no
repositório.

### A decisão

`e_wsl()` — `$WSL_DISTRO_NAME` preenchido, ou `/proc/sys/kernel/osrelease`
contendo `microsoft` — é consultada **antes** da cadeia gráfica, e só ali. Fora do
WSL nada muda: a ordem de sempre vale, e o PowerShell continua sendo o último
recurso, que é o que o WIN3 daquele PR afirma.

No WSL **sem** interop (o `/etc/wsl.conf` permite desligá-lo) o script cai na
cadeia normal em vez de ficar sem leitor: `xclip` ler o lado errado ainda é melhor
que não ter vigia nenhuma, e a mensagem de falta já nomeia o PowerShell.

### O que está medido

O dublê cobre a **escolha**, que é o que o Invariante 11 manda assertar:

- **W1** — sob WSL, com `xclip` e `wl-paste` presentes *e funcionando* e a sessão
  gráfica anunciada, o leitor é o do Windows. Os dois dublês existem de propósito:
  sem eles o teste passaria por ausência e não provaria nada sobre a ordem.
- **W2** — fora do WSL, com o PowerShell disponível, o leitor gráfico continua
  vencendo. É o que impede a correção de virar regressão, e o W1 sozinho não
  distingue "preferiu no WSL" de "preferiu para todo mundo".
- **W4** — o pedido inteiro pelo lado do Windows, numa invocação, até gravar.

Não medido, e igual ao que aquele desenho já registra: o que `Get-Clipboard` faz
num Windows real. Não sai de um Mac.

## 3. O passo 2 em etapas

O bloco tinha 23 linhas e saía inteiro antes da primeira ação. Sete delas não são
do caminho feliz:

- o plano B do DevTools, que só interessa quando a página **não** renderiza;
- o aviso sobre `urlscheme=http`, endereçado a quem edita a URL à mão.

As duas viraram `dicas_quando_a_pagina_nao_coopera()`, chamada nos dois momentos
em que "deu errado" é fato e não hipótese: a vigia que encerra sem o endereço, e o
valor que chega sem a forma certa.

Caiu junto a frase "não precisa de DevTools", que ficava no caminho feliz para
tranquilizar. Ela só tranquiliza quem já sabe o que é DevTools; para quem não
sabe, levanta uma pergunta em vez de responder — e é essa pessoa que a mudança
serve.

O que sobrou virou três paradas, uma por ação executada **fora** do terminal:
abrir a página, achar o link azul, copiar o endereço. `pausar()` só existe com
`[ -t 0 ]`: sem terminal não há Enter para esperar, e um `read` ali travaria o
script até o timeout de quem o chamou. `USP_MCP_SEM_PAUSA=1` desliga.

**O que prende a mudança são os dois lados** — que as dicas não aparecem no
caminho feliz (P1) e que aparecem quando deu errado (P2, P3). Sem o segundo,
"tirar do caminho feliz" é indistinguível de "apagar".

O arnês de pty da suíte entra na mudança: `_rodar_com_tty` respondia ao prompt do
passo 3 e só a ele, então as paradas novas o travavam até o timeout de 90 s. Ele
passa a responder com uma linha em branco a cada `[Enter]` novo.

**E a queixa dela não era sobre o script.** Na sessão dela quem falava era o
agente; o `token.sh` roda sem tty nesse caminho. Então o passo 3 do bloco colável
do README passa a declarar o regime — *um passo por mensagem, espere eu responder*
—, porque "explique passo a passo" um modelo cumpre entregando todos os passos
numa mensagem só.

## 4. O que foi tentado e descartado

**Um intervalo de vigia por leitor** (2 s para o PowerShell, contra 0,5 s), porque
cada leitura sobe um processo e a 0,5 s seriam 180 arranques em 90 s. Escrito,
testado, e **descartado antes de entrar**.

O motivo é o número: "200 a 800 ms de arranque" é estimativa, não medição, e
mudar o padrão da vigia com base nela é exatamente o que este projeto não faz — o
`--auto` está fora do padrão até hoje por não ter medição contra a USP. O preço
apareceu no ato: seis testes do `fix/windows` ficaram vermelhos, porque um
intervalo de 2 s numa janela de 1 s dá zero tiques e a vigia deixa de ler. Vai
para o `BACKLOG-correcoes.md` com a medição a fazer.

**Mexer no lançador**, que a primeira versão desta mudança fazia. O `fix/windows`
resolveu melhor: achou que no Ubuntu do WSL `/usr/bin/open` é o `openvt` do pacote
`kbd`, o que esta versão não tinha visto.
