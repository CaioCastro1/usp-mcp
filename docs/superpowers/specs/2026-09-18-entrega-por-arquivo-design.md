# Entrega por arquivo: subir o arquivo da pessoa e apontar a entrega para ele

> 18/09/2026. O pedido é do dono, a partir de uso real: *dar um arquivo ao
> assistente e ele enviar como entrega no e-Disciplinas*. Hoje isso não existe,
> e é o que torna a escrita de 15/09 quase inútil para ele: as entregas reais
> dele são por arquivo, e a metade que grava só sabe texto online.
>
> Este spec é da mesma família de
> `docs/superpowers/specs/2026-09-15-entrega-com-confirmacao-design.md`, que já
> virou código (PR #68). Ele **não redesenha** aquele desenho: diz o que fica
> igual, o que muda, e por quê. As cinco camadas, a flag `USP_MCP_ENTREGA`, o
> plano em duas etapas com hash e a elicitação como apresentação continuam
> valendo palavra por palavra.
>
> **Só documento.** Zero linhas em `usp_mcp/`, zero chamadas ao e-Disciplinas.
> O que está medido aqui foi medido pelo dono em 18/09 (§2) ou lido das
> fixtures já versionadas e do fonte do Moodle. O que ainda não foi medido está
> no §10, com o comando, e é pré-requisito da implementação, não suposição.
>
> **As decisões de política não são deste documento.** São do dono, que foi
> explícito sobre isso. Onde há escolha, o texto apresenta as opções com custo,
> dá uma recomendação, e marca **⏳ pendente do dono**. O §13 reúne todas.

- **Prioridade:** alta. Sem isto a escrita de 15/09 recusa o caso real do dono.
- **Toca, quando implementado:** `usp_mcp/moodle/{politica,cliente,entrega,server}.py`,
  `tests/moodle/`, `tests/handshake/`, `.env.example`, `README.md`, `SPEC1.md` §2.2 e §9.
- **Não tocados por este spec:** tudo. É um documento.

## 1. O defeito, localizado no código de hoje

`usp_mcp/moodle/entrega.py`:

- **linha 470**, em `_recusa_de_rascunho`: recusa quando os tipos de envio da
  entrega não incluem `onlinetext`, com a frase *"Enviar arquivo exige subir o
  arquivo ao e-Disciplinas, que é coisa que nenhuma ferramenta daqui faz"*;
- **linha 718**, em `salvar_rascunho._escrever_rascunho`: o único `plugindata`
  que o módulo sabe montar é `plugindata[onlinetext_editor][text]`.

O mecanismo inteiro (localizar a entrega, ler o estado, montar o plano, hash,
elicitação, `cliente.escrever`) já existe e só sabe texto. O `README.md`
("Entregando trabalho") e a descrição de `salvar_rascunho` em `server.py` dizem
isso com todas as letras hoje, e estão certos.

**O quanto isso recusa, medido nas fixtures deste repositório**, sem chamada
nenhuma. `fixtures/moodle/assign_ptc3314.json` (captura de 12/09, higienizada):

| entrega | `teamsubmission` | `submissiondrafts` | plugin `file` | `maxfilesubmissions` | `maxsubmissionsizebytes` | `filetypeslist` | `onlinetext` |
|---|---|---|---|---|---|---|---|
| EC-1 - Transitórios em LT | 1 | 0 | ligado | 1 | 10.485.760 (10 MB) | `.pdf` | ausente |
| EC - 2 - Linhas em RPS | 1 | 0 | ligado | 1 | 10.485.760 (10 MB) | `.pdf` | ausente |
| Prova Presencial 1 e 2 | 0 | 0 | ausente | | | | ausente |

E `fixtures/moodle/submission_status_ec1.json` (15/09) confirma do lado do
estado: o plugin da submissão é `{"type": "file", "fileareas": [{"area":
"submission_files", ...}]}`. As duas entregas que aceitam envio são por
arquivo, uma por vez, PDF, 10 MB. Nenhuma tem texto online. É exatamente o que
o dono disse.

Quatro campos dessa tabela decidem o desenho e **nenhum deles é lido pelo código
hoje** (`grep submissiondrafts usp_mcp/` não acha nada): `submissiondrafts`,
`maxfilesubmissions`, `maxsubmissionsizebytes` e `filetypeslist`. O §5 e o §6
dizem o que cada um muda.

## 2. O que foi medido ao vivo em 18/09, pelo dono

Não reconferido aqui, e não é para reconferir: cada chamada fica no log da conta.

```
release: 5.0.8+ (Build: 20260722)
uploadfiles: 1        (o token do dono TEM permissão de subir)
447 funções alcançáveis
funções com "upload" no nome: NENHUMA
core_files_*: core_files_delete_draft_files, core_files_get_files,
              core_files_get_unused_draft_itemid
```

**A leitura disso:** o Moodle **não faz upload por função de web service**.
Ele tem um endpoint separado, `webservice/upload.php`, que recebe o arquivo por
POST `multipart/form-data` comum, com o token num campo do formulário. É por
isso que a varredura das 447 não acha nada com "upload" no nome: não há o que
achar. E as três `core_files_*` que existem são a prova de que o caminho é
esse: o Moodle expõe a peça de **antes** da subida (`get_unused_draft_itemid`,
que reserva uma área de rascunho) e a peça de **depois** (`delete_draft_files`,
que limpa uma; `get_files`, que lista). A subida em si é o `upload.php`.

O que já se sabia, em `notas/moodle-catalogo.md`: as três `core_files_*` estão
catalogadas (§3.11), `get_unused_draft_itemid` como *"gera um id de rascunho;
inofensivo"* e `delete_draft_files` como *"área de rascunho do usuário"*. E
`mod_assign_save_submission` (§3.4) recebe `plugindata` como objeto, sem a
forma dele escrita. Aqui a forma passa a importar.

## 3. O fluxo em passos, e o que existe hoje

Tudo abaixo com a forma do fonte do Moodle 5.0 (`webservice/upload.php`,
`mod/assign/submission/file/locallib.php`, `lib/filelib.php`). O que está
marcado **a medir** está no §10 com o comando. Nada disto foi chamado.

| # | passo | o que é | existe hoje? |
|---|---|---|---|
| 0 | **ler o estado** | `mod_assign_get_assignments` + `mod_assign_get_submission_status` | **sim**: `_localizar` e `montar_plano` em `entrega.py`. Faltam quatro campos (§1) |
| 1 | **ter uma área de rascunho** | um `itemid` de `filearea=draft` na conta da pessoa. Duas formas: (a) `core_files_get_unused_draft_itemid`, função WS; (b) o próprio `upload.php` com `itemid=0` cria uma e devolve o número | **não**. A função (a) não está em conjunto nenhum da política, logo a allowlist a nega. A forma (b) depende do passo 2 |
| 2 | **subir o arquivo** | `POST {MOODLE_URL}/webservice/upload.php`, `multipart/form-data`, campos `token`, `filearea=draft`, `itemid`, `filepath=/` e o arquivo. Resposta: lista JSON com um item por arquivo (`itemid`, `filename`, `filepath`, `component=user`, `filearea=draft`, `contextid`, `userid`, ...) **a medir** | **não**, em três sentidos: o projeto não monta `multipart` (só `form-urlencoded`), o cliente não tem porta para esse endereço, e a política não tem como decidir sobre ele (§4) |
| 3 | **apontar a entrega para a área** | `mod_assign_save_submission` com `plugindata[files_filemanager]=<itemid>`. O nome vem de `assign_submission_file::get_external_parameters()` no fonte: *"The id of a draft area containing files for this submission"* **a medir** | **metade**: a função está em `ESCRITA_CONFIRMADA`, `cliente.escrever` existe, e `_escrever_rascunho` monta `plugindata`, mas só a chave `onlinetext_editor` |
| 4 | **entregar para correção** | `mod_assign_submit_for_grading` | **sim, inteiro** (`entregar`). Mas em entrega **sem rascunho** este passo não existe (§5) |

**O passo 3 substitui, não acrescenta.** No fonte, salvar com uma área de
rascunho chama `file_save_draft_area_files`, que **sincroniza** a área de
destino (`submission_files`) com a de rascunho: o que não está no rascunho é
apagado do destino. Subir só `B.pdf` numa entrega que já tem `A.pdf` anexado
deixa a entrega com `B.pdf`, e `A.pdf` some. O app oficial do Moodle contorna
isso baixando e subindo de novo os arquivos que já estavam lá. Para as
entregas do dono isso é indiferente (`maxfilesubmissions = 1`: um arquivo
substitui o outro), mas o plano tem de dizer o que sai e o que entra, e é uma
das coisas que o §10 mede.

**Os passos 1 e 2 podem ser um só.** Se o `upload.php` com `itemid=0` devolve
o `itemid` novo, como o fonte sugere, o passo 1 é desnecessário e uma função a
menos entra na política. A recomendação é depender disso, e o §10 (M1) é quem
decide.

## 4. Decisão nova 1: um caminho HTTP que não é função

**O problema.** Toda a autorização do projeto é por **nome de função**:
`politica.decidir(funcao, ...)` olha `BLOQUEIO_PERMANENTE`, depois
`ESCRITA_CONFIRMADA`, depois `ALLOWLIST`, todos conjuntos de nomes, e
`cliente._requisitar` é o único lugar por onde toda função passa. O
`upload.php` não é função: não tem `wsfunction`, não vai para
`/webservice/rest/server.php`, não passa por `decidir`. Um endpoint chega ao
fio sem ninguém ter decidido nada, e isso é decisão de política, não de código.

**O precedente.** O download já resolveu problema parecido em 01/09
(`cliente.baixar`, spec de `baixar_arquivo` §6.1). Lá a frase é literal: *"A
allowlist do §2 é por nome de função de web service e não alcança este caminho,
porque o download não é uma função de web service, então esta é a allowlist do
download"*. A allowlist do download é uma checagem de **prefixo de URL**,
`_PREFIXO_ARQUIVO = "/webservice/pluginfile.php/"`, que roda **antes de qualquer
I/O**, e o motivo dela é onde o token **vai**: ele viaja no corpo, então uma
`fileurl` de outro host entregaria a credencial a esse host.

**O desenho serve aqui? Em parte, e a parte que não serve é a que importa.**

| aspecto | download (`baixar`) | upload | o precedente serve? |
|---|---|---|---|
| o token vai no corpo, e não pode ir a outro host | sim | sim | sim: mesma regra, mesmo lugar (o cliente), antes do I/O |
| de onde vem a URL | de uma **resposta** do Moodle (`fileurl`), entrada não confiável, por isso prefixo | de uma **constante**: `{self.url}/webservice/upload.php`, nunca de parâmetro | o prefixo é desnecessário; o que vale é a URL não ser montável de fora |
| lê ou escreve | lê | **escreve** na conta da pessoa | **não**: `baixar` não consulta flag nenhuma, e não pode ser copiado para um caminho de escrita |
| passa por `decidir` | não, e é aceitável porque é leitura | precisa passar pelas mesmas duas condições de `ESCRITA_CONFIRMADA`: flag ligada **e** confirmação declarada | é aqui que o precedente não alcança |
| resposta de erro | JSON com `errorcode`, mesmo com HTTP 200; `_levantar_se_erro` traduz | JSON; com `AJAX_SCRIPT` o Moodle emite `{"error": ..., "errorcode": ...}` **a medir**. `_levantar_se_erro` já lê `errorcode` e cai em `error` para a mensagem | sim, reusando a mesma função, pelo mesmo motivo de 01/09: duas traduções divergem no dia em que o token vencer |

**Três formas de autorizar o endpoint** (⏳ pendente do dono, P1):

- **A. O endpoint ganha um nome dentro da política.** Uma constante,
  `ENVIO_DE_ARQUIVO = "webservice/upload.php"`, entra em `ESCRITA_CONFIRMADA`
  ao lado das duas funções. `cliente.subir(...)` chama
  `politica.decidir(ENVIO_DE_ARQUIVO, confirmada=True)` antes de qualquer I/O,
  monta a URL da constante e nunca de parâmetro, e um `chamar("webservice/upload.php")`
  é recusado como qualquer nome fora da allowlist. **Custo:** `decidir` passa a
  ter um nome que não é função, e o teste que fixa `ESCRITA_CONFIRMADA` em
  exatamente dois nomes (`test_politica_entrega.py:210`) muda de propósito.
  **Ganho:** um conjunto só lista tudo o que escreve em nome da pessoa; as
  recusas já citam a flag pelo nome; `capacidades.py` e `diagnostico` continuam
  descrevendo a escrita a partir de um lugar.
- **B. Um método próprio no cliente, com a própria checagem**, como `baixar` é
  hoje: `subir` lê `entrega_habilitada()` e o parâmetro `confirmada` sozinho,
  sem `decidir`. **Custo:** a política passa a morar em dois lugares, que é
  exatamente o que 15/09 evitou ao fazer de `escrever` a única porta que
  declara confirmação. **Ganho:** nenhuma mudança em `politica.py`.
- **C. Uma segunda função de decisão**, `decidir_endpoint(caminho, confirmada)`,
  com um conjunto próprio `ENDPOINTS_DE_ESCRITA = {"/webservice/upload.php"}` e
  as mesmas duas condições. **Custo:** duas funções com a mesma lógica de
  flag e confirmação, que divergem no dia em que uma mudar. **Ganho:** nome de
  função e caminho de URL não se misturam num conjunto só.

**Recomendação: A.** O que se quer da política aqui é a mesma resposta de
`ESCRITA_CONFIRMADA` (flag e confirmação, com os mesmos motivos), e a
diferença "é função ou é endpoint" é do transporte, não da decisão. O
transporte fica no cliente, num método com nome próprio (`subir`), como
`escrever` e `baixar`, achável por busca, e a URL sai de uma constante. A
checagem de prefixo do download **não** se copia: não há URL de fora para
checar.

**O que este caminho compartilha com `baixar` sem discussão:** o token no
corpo (aqui, num campo do formulário), nunca na URL; a checagem antes do I/O;
o teto de bytes; e a tradução de erro por `_levantar_se_erro`.

**Sem dependência nova.** O runtime do projeto é só `mcp`. `multipart/form-data`
não tem codificador na stdlib, e montá-lo à mão (um boundary, três cabeçalhos
por parte) são umas trinta linhas. Adotar `requests` para isso seria a primeira
dependência de runtime além do `mcp`, que é decisão de §9 (o precedente é o
`pypdf` descartado em 01/09). Recomendação: à mão, com um teste que parseie o
corpo montado com `email.parser.BytesParser` da stdlib (F28).

## 5. Decisão nova 2: ler do disco da pessoa e mandar para fora

Hoje o projeto **só escreve** em disco (`deposito.py`, e só dentro de
`~/.cache/usp-mcp/moodle/`). A docstring de `arquivo.py` é explícita: *"A
ferramenta não lê o arquivo: quem lê é o agente que chamou."* Passar a ler um
arquivo do disco da pessoa e enviá-lo para fora da máquina é categoricamente
novo, e o cuidado tem de ser o mesmo que a entrega teve em 15/09.

**O que muda de natureza.** Quem escolhe o caminho é um modelo interpretando
linguagem ambígua (a mesma frase do §2.2 do `SPEC1.md`). *"Entrega o EP1"* vira
um caminho de arquivo por inferência: o PDF certo, o PDF da versão errada, um
arquivo com nome parecido, ou algo que um enunciado em PDF mandou entregar. E o
destino é a área de rascunho da conta da pessoa no e-Disciplinas: invisível a
colegas, mas fora da máquina e legível por administrador do site.

### 5.1 Que caminho é aceitável (⏳ pendente do dono, P2)

- **Só o depósito** (`~/.cache/usp-mcp/moodle/`). Não serve: o trabalho da
  pessoa não mora lá; lá mora material do professor baixado.
- **Qualquer caminho absoluto que a pessoa deu.** Serve o caso de uso inteiro
  e é o mais arriscado: `~/.ssh/id_rsa` e o próprio `.env` do servidor (com o
  `MOODLE_TOKEN` dentro) são caminhos absolutos como qualquer outro. Uma
  denylist de nomes perigosos seria a única defesa, e o Invariante 2 diz por
  que denylist não é fronteira.
- **Uma raiz declarada**, `USP_MCP_ENTREGAS_DIR`, sem valor padrão. O caminho
  pedido tem de resolver (com `resolve()`, que segue symlink) para dentro dela,
  a mesma checagem `is_relative_to` que `deposito.caminho_para` já faz no
  sentido contrário. Sem a variável, a ferramenta recusa dizendo o nome dela e
  o que pôr lá. **Custo:** uma variável a mais no `.env.example`, e a pessoa
  tem de deixar o arquivo numa pasta que ela declarou. **Ganho:** allowlist por
  diretório, o padrão do projeto; e a decisão de "o que o assistente pode
  mandar para fora" fica com quem é dono da máquina, no arquivo dela, como a
  flag.

**Recomendação: raiz declarada.** É simétrica ao depósito (uma raiz de saída
para a raiz de entrada que já existe), e é o único dos três que não obriga a
lista de exceções. Duas cercas a mais, baratas e fechadas: raiz igual a `/` ou
a `~` é recusada (seria "qualquer caminho" com outro nome), e o arquivo que
resolver para o mesmo caminho de `usp_mcp.env.achar_env()` é recusado mesmo
dentro da raiz (F27). Esta última não é denylist geral: é o único arquivo do
qual o servidor sabe, com certeza, que carrega a credencial dele.

### 5.2 O que impede "entrega essa pasta" de virar dez arquivos

Três coisas, e a primeira é de esquema:

1. **O parâmetro é `arquivo`, singular, um caminho.** Não há lista, não há
   `todos`, não há glob. O que não está no esquema não é tentado pelo modelo
   (mesmo raciocínio do M5 do spec de mensagem).
2. **Diretório é recusado**, antes de qualquer I/O. Caminho com `*`, `?` ou
   `[` também: o servidor não expande nada.
3. **O site tem `maxfilesubmissions`**, e nas fixtures é 1. O plano lê o valor e
   recusa antes de subir se a entrega não aceitar mais um arquivo além dos que
   ficarão. Vários arquivos por chamada estão fora de escopo (§12).

### 5.3 Limites de tamanho e de tipo, e a ordem deles

Todos conferidos **antes** de abrir o arquivo para envio, com `stat()`:

| limite | de onde vem | ação |
|---|---|---|
| zero bytes | `stat().st_size == 0` | recusa: é o espelho de `deposito.ja_baixado`, que não aceita zero como arquivo |
| `maxsubmissionsizebytes` da entrega | `configs` de `mod_assign_get_assignments` (10 MB nas fixtures; `0` significa "o limite do site") | recusa citando o teto **do site**, para a pessoa não procurar um limite do projeto |
| `usermaxuploadfilesize` do site | `core_webservice_get_site_info`, já na allowlist **a medir** | idem |
| teto do projeto | `TETO_ARQUIVO_BYTES` do cliente, 50 MB, o mesmo do download (⏳ P9) | recusa: o servidor lê o arquivo inteiro em memória para o hash e para o corpo |
| `filetypeslist` da entrega | `configs` (`.pdf` nas fixtures; vazio significa qualquer tipo) | recusa por extensão, antes de subir. O site recusaria depois, com o arquivo já na área de rascunho |
| plugin `file` da entrega | `configs[enabled]` e `tipos_de_envio` do status | recusa: entrega que não aceita arquivo não tem para onde apontar |

### 5.4 O que o plano mostra antes de subir

O plano de hoje mostra estado, prazo, arquivos anexados, o que muda, e a
declaração do professor. Ganha:

```
Plano de anexar arquivo — PTC3314, EC-1 - Transitórios em LT
  estado agora: já entregue para correção, editável, não travada
  prazo: 25/09/2026 23:59 (faltam 7 dias)
  arquivo que vai subir: EP1_v2.pdf (740 kB)
    caminho: /Users/joao/USP/PTC3314/EP1_v2.pdf
    modificado em: 18/09/2026 14:02
    conteúdo: sha256 3f9a…c1 (o código abaixo muda se o arquivo mudar)
  limites desta entrega: 1 arquivo, até 10 MB, tipos .pdf
  anexado hoje: EP1_PTC3314_01408154.pdf (757 kB) → SAI
  passa a ser: EP1_v2.pdf → ENTRA
  esta entrega NÃO tem etapa de rascunho: ao confirmar, o arquivo vira a
    ENTREGA na hora e o professor passa a vê-lo. Dá para substituir até o
    prazo; não dá para "desentregar".
  ao confirmar, você assina esta declaração do professor:
    <texto de submissionstatement>

Para confirmar, chame de novo com confirmacao="7b21e0". Nada foi escrito no
e-Disciplinas nem subido por esta chamada.
```

O nome, o tamanho e o caminho resolvido são o mínimo. O **carimbo de
modificação** e o **hash do conteúdo** existem porque a pessoa pode salvar uma
versão nova do PDF entre o plano e a confirmação, com o mesmo nome e quase o
mesmo tamanho: sem o conteúdo no hash, a segunda chamada subiria um arquivo
que ninguém viu no plano. **O que sai e o que entra** existe por causa da
substituição do §3. E a linha sobre a **etapa de rascunho** existe pelo §5.5.

### 5.5 `submissiondrafts = 0`: quando salvar já é entregar

Este é o achado que muda os verbos, e ele estava na fixture desde 12/09 sem
ninguém ler. `submissiondrafts` é a opção *"Exigir que os alunos cliquem no
botão enviar"*. Nas duas entregas do dono ela está **desligada** (`0`).

No fonte (`mod/assign/locallib.php`, `assign::save_submission`), com essa
opção desligada o status da submissão vai direto para `submitted` ao salvar.
Não existe etapa `draft`, o botão "entregar" não existe na tela, e
`submit_for_grading` não tem o que fazer. A fixture de status bate com isso:
`status: submitted`, `cansubmit: false`, `canedit: true`, sem nunca ter havido
um `submit_for_grading`.

Consequências, e são três:

1. **Para essas entregas, o passo 3 do §3 é a entrega.** O professor recebe
   no segundo em que `save_submission` responde. `canedit: true` até o prazo
   permite **substituir**, mas não tirar de "entregue". O plano tem de dizer
   isso em maiúsculas, e a ferramenta tem de carregar a anotação de escrita
   sem desfazer, como `entregar`.
2. **`salvar_rascunho` de hoje promete uma coisa falsa nesse caso.** A
   descrição diz *"Rascunho salvo NÃO é entrega feita: o professor não recebe
   nada até você usar `entregar`"*. Em entrega com `submissiondrafts = 0` e
   texto online, gravar o texto **é** entregá-lo. Nenhuma entrega do dono tem
   texto online, então isso nunca mordeu; mas é defeito latente da
   implementação de 15/09, e vai para o backlog com este spec. A cura é a
   mesma daqui: ler o campo e dizer o que ele muda.
3. **A implementação ganha um novo campo em `Atividade`** (`exige_botao_enviar`,
   lido de `submissiondrafts`), e ele entra no hash do plano: se o professor
   mudar a opção entre o plano e a confirmação, o significado de confirmar
   muda, e o código tem de mudar junto.

**⏳ pendente do dono (P4):** aceitar anexar em entrega sem etapa de rascunho,
com o plano dizendo que vira entrega, ou recusar essas entregas? Recomendação:
**aceitar**, porque são exatamente as entregas dele. Recusar seria repetir o
defeito do §1 com outra frase.

**E a declaração do professor.** `requiresubmissionstatement = 1` nas duas. Em
entrega com etapa de rascunho, quem assina é `submit_for_grading`, com
`acceptsubmissionstatement=1`, que o código já manda. Em entrega sem etapa,
a tela do site exige a caixa marcada no próprio formulário de envio, e a
função externa `mod_assign_save_submission` **não tem parâmetro para a
declaração**. Duas possibilidades, e só a medição separa: ou o site não exige
a declaração pelo web service (o app oficial entrega arquivos assim, o que
sugere isso), ou ele recusa com um aviso `couldnotsavesubmission` que
`_levantar_se_erro` já traduz desde 16/09. Nas duas o plano mostra a
declaração antes de pedir a confirmação, como hoje. O que não pode acontecer é
o texto ser assinado sem ter sido mostrado. Está no §10 (M4).

## 6. O que fica igual e o que muda, camada por camada

| camada (15/09) | fica | muda |
|---|---|---|
| **1. Verbos separados** | `salvar_rascunho` e `entregar` continuam duas ferramentas, sem enum | entra uma **terceira**, `anexar_arquivo` (⏳ P3). Não é parâmetro de `salvar_rascunho` porque o efeito não é o mesmo: em entrega sem etapa de rascunho, anexar é entregar (§5.5), e o nome "rascunho" mentiria |
| **2. Plano e execução em duas invocações** | a primeira chamada nunca escreve nem sobe; o código é hash do plano; código velho é recusado com o plano novo | o hash cobre também o arquivo local (caminho resolvido, tamanho, sha256 do conteúdo) e `submissiondrafts`. Continua com o verbo, que 16/09 acrescentou |
| **3. Elicitação como apresentação** | igual, inclusive "não pude perguntar" ≠ "disseram não" | a pergunta mostra o plano do §5.4, com o arquivo e o que sai |
| **4. A flag** | `USP_MCP_ENTREGA`, e só ela. Nenhuma flag nova para upload (⏳ P2 traz `USP_MCP_ENTREGAS_DIR`, que é **configuração** de onde ler, não portão de ligar; sem ela a ferramenta aparece e recusa dizendo o que falta, e isso é aceitável porque a falta é de configuração declarada, não de decisão) | `ESCRITA_CONFIRMADA` cresce (P1), e o texto de `capacidades.py` passa a dizer que a escrita inclui subir arquivo |
| **5. Recusas que a flag não abre** | ver §7 | ver §7 |

**Sem a flag, `anexar_arquivo` não existe no `tools/list`**, como as outras
duas (E14). Com a flag, a lista vai de treze para **catorze**.

**Recibo depois da escrita.** Hoje `entregar` imprime o plano como recibo, sem
reler. Para anexar isso não basta: o que importa é o que o site **tem** depois,
e a única prova é reler `mod_assign_get_submission_status` (leitura, já na
allowlist) e imprimir a lista de arquivos que voltou. Se o arquivo que subiu
não estiver nela, a saída diz isso em vez de "Feito" (F23). É também a única
forma de a primeira execução real ser uma medição e não um ato de fé (§10, M4).

## 7. Recusas que a flag não abre

**Herdadas de `_recusa_de_rascunho`**, e valem para anexar: entrega de grupo
(escreve em nome de terceiros), travada, não editável (`canedit` falso),
cronômetro não ligado (`_recusa_por_cronometro`, a que o spec de 15/09 não
previu).

**Não herdadas, de propósito:** a de "já entregue" de `_recusa_de_entrega`.
Em entrega sem etapa de rascunho o status é `submitted` desde o primeiro
salvamento, e recusar por isso impediria a substituição antes do prazo, que é
uso legítimo. O que segura o acidente aqui é o plano dizer **o que sai**
(⏳ P5: permitir a substituição com o plano explícito, ou recusar quando já há
arquivo anexado? Recomendação: permitir; recusar bloqueia a correção de um
envio errado, que é o caso em que a pessoa mais precisa da ferramenta).

**Novas**, todas antes de qualquer I/O de rede:

| recusa | por quê |
|---|---|
| `USP_MCP_ENTREGAS_DIR` ausente, ou igual a `/` ou `~` | sem raiz declarada não há de onde ler (§5.1) |
| caminho fora da raiz depois de `resolve()` | a raiz é a allowlist; symlink que aponta para fora conta como fora |
| caminho é diretório, não existe, ou não é arquivo regular | um arquivo, singular (§5.2) |
| caminho com `*`, `?`, `[` | o servidor não expande nada |
| arquivo é o `.env` que este servidor lê | é o único arquivo que se sabe carregar a credencial (§5.1) |
| zero bytes | espelho de `ja_baixado` |
| acima de `maxsubmissionsizebytes`, de `usermaxuploadfilesize` ou do teto do projeto | §5.3, e a mensagem diz **qual** dos três |
| extensão fora de `filetypeslist` | o site recusaria com o arquivo já na área de rascunho |
| entrega sem plugin `file` habilitado | não tem para onde apontar |
| `maxfilesubmissions` não comporta o resultado | com a substituição do §3 isso só recusa quando o teto é 0 |

Cada uma com mensagem própria (Invariante 6): dez recusas, dez frases.

## 8. Se a subida der certo e a entrega falhar

Cenário: o `upload.php` respondeu com o `itemid` e o arquivo está na área de
rascunho da conta; `save_submission` foi recusado pelo site, ou deu timeout.
Fica um arquivo numa área temporária da conta da pessoa. Não está anexado a
nada, ninguém além dela e de administrador do site o vê, e o cron do Moodle
apaga áreas de rascunho órfãs depois de alguns dias (`file_storage::cron`, no
fonte; o prazo exato fica **a conferir no fonte**, não ao vivo).

**⏳ pendente do dono (P6), duas opções:**

- **A. Não limpar, e dizer.** A saída diz que nada foi anexado, que o arquivo
  ficou numa área temporária da conta e que o site a limpa sozinho. Custo
  zero de política.
- **B. Limpar com `core_files_delete_draft_files`.** A função existe no token
  (§2) e apaga só da área de rascunho **do próprio usuário**, pelo `itemid` e
  pelo nome. Entra em `ESCRITA_CONFIRMADA` (é escrita, e a confirmação que a
  cobre é a mesma que autorizou a subida: limpar o que a subida falhada deixou
  é parte do que a pessoa confirmou). Melhor esforço: se a limpeza também
  falhar, a saída diz que falhou e o que ficou, nunca esconde. Nunca é chamada
  em outro contexto, e nunca sobre um `itemid` que não veio da resposta do
  passo 2 desta mesma chamada.

**Recomendação: B.** Deixar lixo que "o site limpa" é a frase que envelhece
calada, e o custo é uma função a mais, com escopo fechado (a área da própria
conta), dentro de um fluxo que já foi confirmado.

Os outros cortes são simples: se o passo 2 falhar, o passo 3 não roda e não
há o que limpar (o `upload.php` grava por arquivo, e um arquivo só); se a
resposta do passo 2 vier sem `itemid`, é erro legível e o passo 3 não roda
(F22); cada chamada usa uma área nova (`itemid=0`), então uma tentativa
falhada não contamina a seguinte.

## 9. Superfície

```
anexar_arquivo(disciplina: str, entrega: str, arquivo: str, confirmacao: str | None = None)
```

| parâmetro | o que é |
|---|---|
| `disciplina` | sigla, como nas outras duas |
| `entrega` | pedaço do nome da entrega, como nas outras duas; ambiguidade recusa e lista |
| `arquivo` | **um** caminho de arquivo, absoluto ou relativo à raiz declarada. `~` expande. Sem glob, sem lista |
| `confirmacao` | o código que o plano devolveu; sem ele, a resposta é o plano e nada sobe |

Anotações: `destructiveHint` verdadeiro (como `entregar`), porque em entrega
sem etapa de rascunho o efeito é entrega. A descrição diz, no vocabulário de
quem pergunta: "anexa um arquivo do seu computador a uma entrega", "em
entrega sem botão de enviar isto já é a entrega", "substitui o que estiver
anexado", "o arquivo tem de estar dentro da pasta declarada em
`USP_MCP_ENTREGAS_DIR`".

`salvar_rascunho` continua recusando entrega por arquivo, mas a frase passa a
apontar: *"use `anexar_arquivo`"* (F25). `entregar` não muda de esquema (F24).

## 10. O que precisa ser medido ao vivo antes de escrever código

Nenhum destes foi feito aqui. Quem decide fazer é o dono (a credencial é dele;
Invariante 4 e item 9 do `CLAUDE.md`). **M1, M2 e M9 escrevem só na área de
rascunho da conta**, que é temporária e invisível a terceiros. **M4 escreve
numa entrega real**, e por isso não é sonda: é a primeira execução, do jeito
descrito abaixo. M5, M6 e M7 são leitura pura.

Regra dos comandos: o token **nunca** vai no argv (§9 de 15/09, `ws.sh`). Os
`curl` abaixo leem a configuração pelo stdin com `-K -`, como o `ws.sh`, e a
variável `MOODLE_TOKEN` entra pelo `.env` que `usp_mcp.env.achar_env` acha.
Nunca imprimir o valor.

**M1. A forma exata do POST do `upload.php` e o que ele devolve.** Com um PDF
pequeno de teste (não a entrega), a partir da raiz do checkout:

```bash
set -a; . "$(.venv/bin/python -c 'from usp_mcp.env import achar_env; print(achar_env())')"; set +a
{
  printf 'form = "token=%s"\n' "$MOODLE_TOKEN"
  printf 'form = "filearea=draft"\n'
  printf 'form = "itemid=0"\n'
  printf 'form = "filepath=/"\n'
  printf 'form = "file_1=@%s"\n' "/caminho/para/teste.pdf"
} | curl -sS -K - "${MOODLE_URL:-https://edisciplinas.usp.br}/webservice/upload.php"
```

Registrar em `notas/`, sem o payload: o formato do topo (lista? objeto?), os
nomes de campo de cada item (`itemid`, `filename`, `filepath`, `filesize`?,
`component`, `filearea`, `contextid`, `userid`), e se `itemid=0` de fato
devolveu um `itemid` novo. Se devolveu, o passo 1 do §3 cai e
`core_files_get_unused_draft_itemid` não entra na política.

**M1b. A forma do erro do `upload.php`.** Repetir M1 **sem** a linha do
arquivo. A expectativa do fonte, com `AJAX_SCRIPT` ligado, é
`{"error": "...", "errorcode": "nofile", ...}`, com HTTP 200 ou 4xx. Registrar
o status HTTP e as chaves. É isto que decide se `_levantar_se_erro` serve sem
mudança.

**M2. `core_files_get_unused_draft_itemid`, só se M1 mostrar que é preciso:**

```bash
./scripts/ws.sh core_files_get_unused_draft_itemid
```

**M9. `core_files_delete_draft_files` sobre a área que M1 criou**, que também
apaga o lixo da sonda:

```bash
./scripts/ws.sh core_files_delete_draft_files "draftitemid=<itemid de M1>" \
  "files[0][filepath]=/" "files[0][filename]=teste.pdf"
```

Registrar a forma da resposta (o fonte diz `{"parentpaths": [...], "warnings": [...]}`)
e conferir com `core_files_get_files` (leitura) que a área ficou vazia, se se
quiser a prova.

**M5. `submissiondrafts`, `teamsubmission` e os limites de arquivo em todas as
entregas do semestre.** Leitura pura, uma chamada por disciplina, com
`capture.sh` (que imprime medida e não payload) e um `python3` sobre o cru:

```bash
./scripts/capture.sh assign_<sigla> mod_assign_get_assignments "courseids[0]=<courseid>"
python3 -c '
import json,sys
d=json.load(open("fixtures/moodle/raw/assign_<sigla>.json"))
for c in d["courses"]:
  for a in c["assignments"]:
    f={x["name"]:x["value"] for x in a.get("configs",[]) if x["plugin"]=="file"}
    print(a["name"], "grupo=",a["teamsubmission"], "botao_enviar=",a["submissiondrafts"], f)'
```

Isto responde duas perguntas de decisão: quantas entregas **individuais** por
arquivo o dono tem (P8), e quantas têm etapa de rascunho (P4).

**M6. `usermaxuploadfilesize`** vem em `core_webservice_get_site_info`, que
já está na allowlist e já foi chamada (o `uploadfiles: 1` do §2 saiu dela).
Registrar o valor.

**M7. A substituição do §3** não tem sonda sem escrita. Fica junto de M4.

**M4. `save_submission` com `plugindata[files_filemanager]=<itemid>`.** Isto
escreve numa entrega real e **não é sonda**: é a primeira execução, feita
pelo dono, numa entrega que ele **quer** entregar, pela ferramenta, com o
plano na frente, depois de M1 ter fixado a forma do upload. O código entra
com o nome do parâmetro tirado do fonte e um teste que asserta o parâmetro
**enviado** (item 11 do `CLAUDE.md`), e o recibo do §6 relê o status e mostra
o que o site tem. Se o site recusar por falta da declaração (§5.5), a resposta
virá como aviso traduzido, nada terá sido anexado, e o spec ganha um caminho a
menos; se aceitar, M7 fica medido junto (o arquivo anterior saiu?).

**M10. O prazo do cron das áreas de rascunho** se lê no fonte
(`lib/filestorage/file_storage.php`, `cron()`), não ao vivo.

## 11. Bateria

Prefixo **F** (de arquivo); `A` já é de `test_anotacoes.py` e `E` é de
15/09. Camadas `politica` e `contrato` offline, no gate; `live` atrás de
`USP_MCP_LIVE=1` **e** `USP_MCP_ENTREGA=1`, e **só leitura**: subir arquivo,
mesmo para a área de rascunho, é escrita na conta, e escrita ao vivo não entra
na suíte em fase nenhuma (15/09). A sonda M1+M9 é do dono, à mão, uma vez.

Camada `politica`:

- **F1** `decidir(ENVIO_DE_ARQUIVO)` sem flag é recusa, e o motivo cita
  `USP_MCP_ENTREGA` pelo nome.
- **F2** com a flag e sem confirmação, ainda é recusa.
- **F3** com flag e confirmação, é permitida.
- **F4** `ESCRITA_CONFIRMADA` tem exatamente os nomes decididos (três, ou
  quatro com `core_files_delete_draft_files`), nenhum na `ALLOWLIST`, nenhum
  no `BLOQUEIO_PERMANENTE`; o `BLOQUEIO_PERMANENTE` continua com 40.
- **F5** `core_files_get_unused_draft_itemid` e `core_files_get_files` **não**
  estão em conjunto nenhum, salvo decisão de M1 (o teste fixa o que foi
  decidido, para a próxima sessão não os acrescentar por conveniência).
- **F6** `cliente.chamar("webservice/upload.php")` é recusado como nome fora
  da allowlist, com a flag ligada e desligada (o análogo do T60).

Camada `contrato`, com transporte de upload dublê e `tmp_path` como raiz:

- **F7** a primeira chamada de `anexar_arquivo` não toca o transporte de
  upload nem o de escrita.
- **F8** caminho fora da raiz é recusado antes de abrir o arquivo (o dublê de
  leitura não é chamado) e a mensagem não ecoa conteúdo nenhum.
- **F9** diretório, caminho inexistente e caminho com glob: três recusas,
  três frases.
- **F10** symlink dentro da raiz apontando para fora é recusado.
- **F11** arquivo de zero bytes é recusado.
- **F12** acima de `maxsubmissionsizebytes`, de `usermaxuploadfilesize` e do
  teto do projeto: três recusas, cada uma cita o próprio teto, e nenhuma toca
  a rede.
- **F13** extensão fora de `filetypeslist` é recusada; `filetypeslist` vazio
  aceita qualquer.
- **F14** entrega sem plugin `file` é recusada.
- **F15** o código muda quando muda o conteúdo do arquivo com nome e tamanho
  iguais, quando muda o caminho, e quando muda `submissiondrafts`; e continua
  mudando com `status`, `timemodified` e o conjunto anexado (E8 preservado).
- **F16** o plano traz nome, tamanho, caminho resolvido, carimbo, hash curto,
  os limites da entrega, o que sai e o que entra.
- **F17** com `submissiondrafts = 0` o plano diz que vira entrega; com `1`, que
  vira rascunho e aponta para `entregar`.
- **F18** a ordem no fio: upload antes de `save_submission`, e o
  `plugindata[files_filemanager]` **enviado** é o `itemid` que o dublê de
  upload devolveu. Asserção sobre o parâmetro enviado, não sobre a saída.
- **F19** upload ok e `save_submission` recusado: a limpeza é chamada com o
  `itemid` e o nome (se P6 = B), a saída diz que nada foi anexado e o que
  aconteceu com a limpeza; se a limpeza também falhar, a saída diz.
- **F20** upload falha: `save_submission` não é chamado e nada é limpo.
- **F21** o token aparece no multipart **só** no campo `token`, e não aparece
  na URL, no plano, no recibo nem em nenhuma mensagem de erro (o T99 deste
  caminho).
- **F22** resposta do upload sem `itemid`, ou com `errorcode`: erro legível,
  `save_submission` não é chamado.
- **F23** depois da escrita o status é relido; o recibo lista o que o site
  devolveu; se o arquivo que subiu não estiver lá, a saída não diz "Feito".
- **F24** `entregar` não aceita `arquivo`; `additionalProperties` continua
  falso.
- **F25** `salvar_rascunho` em entrega por arquivo continua recusando, e a
  frase aponta para `anexar_arquivo`.
- **F26** o `.env` do servidor (`achar_env()`) é recusado mesmo dentro da raiz.
- **F27** raiz igual a `/` ou a `~`, e raiz ausente: recusas que citam
  `USP_MCP_ENTREGAS_DIR` pelo nome.
- **F28** o corpo multipart montado é parseável por
  `email.parser.BytesParser` e traz as partes `token`, `filearea`, `itemid`,
  `filepath` e o arquivo com o nome original como `filename`.
- **F29** a URL do upload é montada da constante e de `self.url`; um cliente
  com `url` terminando em `/` produz a mesma URL (o bug de 16/09 do prefixo
  duplo, deste lado).
- **F30** a pergunta (elicitação) mostra o plano com o arquivo e sem o pedido
  de confirmação, e só acontece depois do código conferido (E11b preservado).

Handshake:

- **F31** sem a flag, `anexar_arquivo` não aparece; com ela, aparece e são
  catorze; `disciplina`, `entrega` e `arquivo` obrigatórios no fio,
  `confirmacao` não.

Camada `live`:

- **F32** o plano de uma entrega real bate com o que o site diz, sem subir e
  sem escrever (o E13 deste caminho).

## 12. O que não entra nesta fase, declarado

- **Vários arquivos por chamada, e pastas.** `arquivo` é singular. Quem tiver
  entrega com `maxfilesubmissions > 1` sobe um por vez, e cada subida
  substitui o conjunto (§3), então na prática só o primeiro fica. Fazer certo
  exige uma área de rascunho com todos os arquivos, inclusive os que já
  estavam anexados, e isso é assunto de outro spec.
- **Preservar o que já está anexado**, baixando e subindo de novo como o app
  oficial faz. O projeto sabe baixar (`cliente.baixar`), então é possível; mas
  nas entregas medidas o teto é um arquivo, e o plano dizendo "sai X, entra Y"
  é a versão honesta do que acontece.
- **Entrega de grupo.** Continua recusada, herdada da camada 5. Ver P8.
- **`mod_assign_remove_submission`** ("desentregar"). Continua no bloqueio
  permanente, e o §9 de 15/09 já anotou que o silêncio sobre ela é só
  silêncio.
- **Ler o conteúdo do arquivo.** O servidor calcula o hash e monta o corpo;
  não interpreta PDF, não extrai texto, não valida se "é o EP1". Quem sabe o
  que está dentro é a pessoa.
- **Dependência nova.** Multipart à mão (§4).

## 13. Pendências do dono, com recomendação

| # | pergunta | opções | recomendação |
|---|---|---|---|
| P1 | como a política autoriza o `upload.php`, que não é função | A: nome constante em `ESCRITA_CONFIRMADA`; B: checagem própria no cliente; C: `decidir_endpoint` com conjunto próprio | **A** (§4) |
| P2 | de onde o servidor pode ler | só o depósito; qualquer caminho; raiz declarada `USP_MCP_ENTREGAS_DIR` | **raiz declarada**, sem padrão, recusando `/` e `~` (§5.1) |
| P3 | ferramenta nova ou parâmetro em `salvar_rascunho` | `anexar_arquivo`; `salvar_rascunho(arquivo=...)` | **ferramenta nova** (§6) |
| P4 | anexar em entrega sem etapa de rascunho, onde salvar é entregar | aceitar com plano explícito; recusar | **aceitar** (§5.5): é o caso do dono |
| P5 | substituir arquivo já anexado ou já entregue | permitir com "sai X, entra Y"; recusar quando já há arquivo | **permitir** (§7) |
| P6 | o que fazer com a área de rascunho quando a subida vinga e a entrega falha | A: nada, e dizer; B: `core_files_delete_draft_files` no mesmo fluxo | **B** (§8) |
| P7 | como obter a área de rascunho | `core_files_get_unused_draft_itemid`; `upload.php` com `itemid=0` | **`itemid=0`**, se M1 confirmar (§3) |
| P8 | entrega de grupo | manter a recusa da camada 5; reabrir | **manter agora.** Mas fica dito: as duas entregas por arquivo da fixture são de grupo, e com a recusa mantida esta ferramenta serve só às individuais. M5 mede quantas são. Reabrir é outra pergunta de §2.2, com outro spec, não um parágrafo aqui |
| P9 | teto do projeto além do do site | 50 MB (o do download); só o do site | **50 MB** (§5.3): o servidor segura o arquivo em memória |
| P10 | a sonda M1 + M1b + M9 | o dono roda uma vez; não roda e o código entra pela forma do fonte | **roda**: escreve só na área temporária da conta, e é o que separa "medido" de "suposto" |
| P11 | dependência para multipart | à mão; `requests` | **à mão** (§4) |

## 14. O que precisa ir para o §9, quando decidido e implementado

Três registros, com data:

1. que a escrita de 15/09 passou a alcançar entrega por **arquivo**, por qual
   caminho (o `upload.php` fora da rota das funções) e como a política o
   autoriza (P1), com o `ESCRITA_CONFIRMADA` no tamanho novo;
2. que o projeto passou a **ler do disco da pessoa** para enviar, de onde
   (P2) e com que cercas (§7), e que isso é a primeira vez;
3. que `submissiondrafts = 0` faz salvar ser entregar, que isso estava na
   fixture desde 12/09 sem ser lido, e o que a implementação faz com isso
   (§5.5). É o registro que mais precisa sobreviver: sem ele a próxima sessão
   lê "salvar rascunho" e acredita na palavra.

## 15. Colateral, para o backlog

Registrado em `docs/decisions/BACKLOG-correcoes.md` nesta mesma PR, sem
desvio:

- `salvar_rascunho` não lê `submissiondrafts` e promete "não é entrega feita"
  para todas as entregas; em entrega sem etapa de rascunho e com texto online
  a frase é falsa. Nenhuma entrega do dono tem texto online, então não mordeu.
- `notas/moodle-catalogo.md` (§3.4 e a tabela do fim) ainda marca
  `mod_assign_save_submission` como `bloqueada-§2.2`; ela está em
  `ESCRITA_CONFIRMADA` desde 15/09. É a mesma família de desatualização que o
  spec de mensagem achou em `core_message_*`.
