# JupiterWeb — reconhecimento (31/08/2026)

> Fase 1, linha que faltava. Executado do terminal do Caio (o §1.1 do SPEC vale: o sandbox
> não alcança `uspdigital.usp.br`). **26 requisições HTTP no total**, teto era ~30.
> Nenhuma tentativa de login, nenhuma credencial, nenhum acesso ao `.env`.
> Nenhum laço, nenhuma enumeração de id, nenhum catálogo baixado.

Fixtures em `fixtures/jupiter/`. Nada aqui edita `SPEC1.md`.

---

## 0. Veredito, antes do detalhe

**Existe JSON — mais precisamente, existe RPC estruturado, público e sem autenticação.**
Não é REST e não é `application/json`, mas é um endpoint que devolve **objeto com campos
nomeados**, não HTML. Scraping de tabela aninhada **não é necessário** para a parte que mais
importa (ementa, créditos, pré-requisito, grade curricular).

A tecnologia é **DWR (Direct Web Remoting)**, framework de RPC Java sobre HTTP. O JupiterWeb
expõe um bean chamado literalmente `ControlePublicoDWR` — *público* no nome e no
comportamento: a chamada funciona **sem cookie, sem sessão e sem handshake** (verificado,
§4.4).

**Vale a pena?** Sim, para catálogo de disciplina, pré-requisito e grade curricular — com a
ressalva do §7. **Não** para horário de aula: essa parte continua sendo scraping de HTML
frágil, e é a única que eu recomendaria não prometer.

Correção de expectativa que o SPEC pedia: o §1.4 dizia "não prometa Jupiter antes de mapear
se existe JSON ou se é só HTML". A resposta medida é **"os dois, e a fronteira entre eles
não é onde se esperaria"** — o dado *estático* (ementa) tem API; o dado *do semestre*
(turma, horário, vaga) só tem HTML.

---

## 1. Contagem de requisições

| # | Requisição | Status |
|---|---|---|
| 1 | `GET /robots.txt` | 302 |
| 2 | idem com `-L` (2 saltos) | 200 (redirect p/ `/wsusuario/`) |
| 3 | `GET /jupiterweb/` | 200 |
| 4 | `GET /jupiterweb/jupDisciplinaBusca?tipo=D` | 200 |
| 5 | `GET /jupiterweb/obterDisciplina?sgldis=PSI3323` | 200 |
| 6 | `GET /jupiterweb/obterTurma?sgldis=PSI3323` | 200 |
| 7 | `GET /jupiterweb/listarCursosRequisitos?coddis=PSI3323` | 200 |
| 8 | `GET /jupiterweb/dwr/index.html` | **404** |
| 9 | `GET /jupiterweb/javascript/jupiterweb.js` | 200 |
| 10 | `GET /jupiterweb/servicos` (hipótese: backend móvel, paralelo ao RUCard) | **404** |
| 11 | `GET /jupiterweb/jupCarreira.jsp` | 200 |
| 12–13 | `GET /jupiterweb/dwr/interface/{ControlePublicoDWR,CursoControlePublicoDWR}.js` | 200 |
| 14 | `GET /jupiterweb/javascript/carreira/jupCarreira.js` | 200 |
| 15 | `POST /jupiterweb/dwr/call/plaincall/__System.generateId.dwr` | 200 |
| 16 | `GET /jupiterweb/dwr/engine.js` (para acertar o formato do corpo) | 200 |
| 17 | `POST …/ControlePublicoDWR.obter.dwr` → `pubObterDisciplina` PSI3323 | 200 |
| 18 | idem → `pubListarColegiado` | 200 |
| 19 | idem → `pubListarCursoEntrada` `{codclg:3}` | 200 |
| 20 | idem → `pubGradeCurricular` `{codcur:3033,codhab:0,tipo:N}` | 200 |
| 21 | `GET /jupiterweb/jupDisciplinaBusca?tipo=T` | 200 |
| 22 | `POST …obter.dwr` → `pubObterDisciplina` PTC3314 | 200 |
| 23 | idem com sigla inexistente `ZZZ9999` | 200 + `handleException` |
| 24 | `GET /jupiterweb/creditos.jsp` | 200 |
| 25 | `POST …obter.dwr` **sem cookie, `scriptSessionId` inventado** → PME3344 | 200 |
| 26 | `POST …listar.dwr` → `pubListarRequisitoDisciplina` MAT2454 | 200 |

**Total: 26.** Nenhuma requisição repetida por tentativa-e-erro além do que está na tabela.

---

## 2. Pergunta 2 — o que é público sem login

Tudo abaixo respondeu **HTTP 200 sem cookie de sessão autenticada**. O menu público está
declarado no próprio HTML da home (`fixtures/jupiter/html-index.html`), num array
`nomgrpweb=Público`:

| Rótulo no menu | URL |
|---|---|
| Busca por Disciplinas | `jupDisciplinaBusca?tipo=D&codmnu=6755` |
| Busca por Turmas | `jupDisciplinaBusca?tipo=T&codmnu=6756` |
| Cursos de ingresso | `jupCarreira.jsp?codmnu=8275` |
| Calendário Escolar 2025/2026 | `jupArquivosPublicos.jsp?tiparq=8&anoprg=2025` / `tiparq=9&anoprg=2026` |
| Fale conosco | `jupColegiadoEmailLista` |

**Não verificado:** `jupArquivosPublicos.jsp` e `jupColegiadoEmailLista` — não foram
requisitados (ver §8).

Área autenticada é `webLogin.jsp` / Senha Única. **Não tocada**, conforme a restrição.

Evidência de que o servidor é Tomcat/Struts atrás de balanceador:

```
HTTP/1.1 200
Set-Cookie: JSESSIONID=…; Path=/jupiterweb; HttpOnly
Content-Type: text/html;charset=ISO-8859-1
X-Backend-Server: xxx.xxx.206.91
X-Frame-Options: SAMEORIGIN
```

Charset é **ISO-8859-1** em todo o HTML — importa para qualquer parser.

---

## 3. Pergunta 3 — a forma de uma página de disciplina (caminho HTML)

### 3.1 Como se chega lá

O formulário de busca **não faz POST**. O JS da página (`html-buscaDisciplina-form.html`) é
literalmente:

```js
document.location.href='obterDisciplina?nomdis='+nomdis+'&sgldis='+sgldis;
```

Ou seja: **GET direto, só com a sigla. Sem código de unidade, sem id interno, sem sessão.**

```
GET https://uspdigital.usp.br/jupiterweb/obterDisciplina?nomdis=&sgldis=PSI3323
→ 200  text/html;charset=ISO-8859-1  42.769 B
```

A própria página de disciplina revela mais dois endpoints, no HTML:

```html
<A HREF="listarCursosRequisitos?coddis=PSI3323" class="link_gray">…requisitos…</A>
<A HREF="obterTurma?sgldis=PSI3323" class="link_gray">…oferecimento…</A>
```

Três endpoints, **um único parâmetro cada, e o parâmetro é a sigla que o aluno já sabe.**
Isso é o melhor da superfície HTML.

### 3.2 O que a página de PSI3323 traz (verificado)

Escola Politécnica / Eng de Sistemas Eletrônicos; `PSI3323 - Laboratório de Eletrônica I`;
Créditos Aula 3, Créditos Trabalho 0, Carga Horária Total 45 h, Tipo Semestral, Ativação
01/01/2025. Seções: Ementa (pt + en), Objetivos (pt + en), Conteúdo Programático (pt + en),
Método/Critério de Avaliação, Norma de Recuperação, Bibliografia, Docentes Responsáveis.

`listarCursosRequisitos?coddis=PSI3323` devolve, em texto:
`Curso: 3032 Engenharia — Habilitação: Ciclo Básico - Engenharia Elétrica (integral) —
Período ideal: 6 → PSI3322 - Eletrônica II`.

### 3.3 `obterTurma` — o horário existe, e é público

```
GET https://uspdigital.usp.br/jupiterweb/obterTurma?sgldis=PSI3323
→ 200  text/html;charset=ISO-8859-1  110.847 B
```

**9 turmas** (2026201…2026210). Cada uma traz, verificado no texto extraído:

```
Código da Turma: 2026201   Início: 03/08/2026   Fim: 12/12/2026
Tipo da Turma: Prática     Observações: Sala C1-01 Mezanino
Horário | Prof(a).:  seg  15:00  17:40  Eduardo Coelho Marques da Costa / Sergio Takeo Kofuji
Atividades Didáticas: João Antonio Martino (R) — Coordenação de Turmas da Disciplina — 30
Vagas | Inscritos | Pendentes | Matriculados: Obrigatória 15 15 0 15
```

Isso é **dia da semana, hora de início e fim, sala, professor, vagas e matriculados** — sem
login. É o dado que o Moodle não tem.

---

## 4. Pergunta 1 — a resposta: DWR, RPC público

### 4.1 Como foi achado

`jupCarreira.jsp` (Cursos de ingresso) carrega duas interfaces DWR que as outras páginas
públicas não carregam:

```html
<script src="dwr/interface/ControlePublicoDWR.js"></script>
<script src="dwr/interface/CursoControlePublicoDWR.js"></script>
<script src="javascript/carreira/jupCarreira.js"></script>
```

`/jupiterweb/dwr/index.html` (console de debug do DWR) responde **404** — está desligado, que
é o correto em produção. Mas as interfaces `dwr/interface/*.js` são servidas (200,
`text/javascript`) e listam os métodos remotos:

```js
// ControlePublicoDWR.js
p.executarBatch / p.executar / p.obterArquivo / p.listar / p.obter
p.obterRelatorio / p.obterCsv / p.obterPdf / p.obterZip / p.obterWebdoc / p.obterProgresso
// CursoControlePublicoDWR.js
p.recuperarProjetoPedagogico
```

`listar` e `obter` são genéricos: o primeiro parâmetro é o **nome da consulta**. Os nomes
usados pela aplicação estão em `js-jupCarreira.js` (fixture salva) e são estes oito:

| consulta | método | parâmetros | devolve |
|---|---|---|---|
| `pubListarColegiado` | `listar` | `{pfxdisval, codcg}` | unidades (codclg/nomclg) |
| `pubListarCursoEntrada` | `listar` | `{codclg}` | cursos (codcur, codhab, nomhab, nomcur, perhab) |
| `pubObterInfoCurso` | `obter` | `{codcur, codhab}` | ficha do curso |
| `pubObterInfoCursoWeb` | `obter` | `{codcur, codhab, tipo}` | ficha do curso (web) |
| `pubGradeCurricular` | `listar` | `{codcur, codhab, tipo:"N"}` | grade curricular inteira |
| `pubListarRequisitoDisciplina` | `listar` | `{codcur, codhab, coddis}` | pré-requisitos |
| `pubObterDisciplina` | `obter` | `{coddis, verdis}` | **a disciplina inteira, estruturada** |
| `pubListarDiscipResp` | `listar` | `{coddis}` | docentes responsáveis |

**Não verificado:** `pubObterInfoCurso`, `pubListarDiscipResp` e
`recuperarProjetoPedagogico` — os nomes e a assinatura vêm do JS oficial da aplicação, mas
eu **não os chamei** (ver §8). Estão listados como *lidos no código do Jupiter*, não como
*testados*.

`pubObterInfoCursoWeb` foi chamado em 22/10/2026 (§9 de 26/10): ~900 B com carga exigida,
duração e a regra em HTML.

### 4.2 O protocolo, para quem for implementar

`POST https://uspdigital.usp.br/jupiterweb/dwr/call/plaincall/ControlePublicoDWR.obter.dwr`
com `Content-Type: text/plain` e corpo de linhas `chave=valor`:

```
callCount=1
windowName=
c0-scriptName=ControlePublicoDWR
c0-methodName=obter
c0-id=0
c0-param0=string:pubObterDisciplina
c0-e1=string:PSI3323
c0-e2=number:0
c0-param1=Object_Object:{coddis:reference:c0-e1, verdis:reference:c0-e2}
batchId=0
instanceId=0
page=%2Fjupiterweb%2FjupCarreira.jsp
scriptSessionId=0000000000000000
```

Objetos são serializados por referência (`prop:reference:c0-eN`), com cada `c0-eN` numa
linha própria — formato lido em `dwr/engine.js` (`serialize.convertObject`, linha ~1391),
não adivinhado. Valores string são `encodeURIComponent`-ados.

### 4.3 A resposta

`Content-Type: text/javascript;charset=ISO-8859-1`. Corpo:

```js
throw 'allowScriptTagRemoting is false.';
//#DWR-REPLY
//#DWR-START#
(function(){
if(!window.dwr)return;
var dwr=window.dwr._[0];
dwr.engine.remote.handleCallback("0","0",{coddis:"PSI3323",nomdis:"Laboratório de Eletrônica I",creaul:"3",cretrb:"0",…});
})();
//#DWR-END#
```

**Não é JSON válido** (chaves sem aspas, `\/` escapado, envelope JS). Mas é um único objeto
literal, extraível com um regex sobre `handleCallback("0","0",(…));` e parseável com um
leitor de JS-object tolerante. É estrutura, não apresentação.

Os **26 campos** de `pubObterDisciplina` (PSI3323, verificado):

```
coddis nomdis creaul cretrb cgahoreto dtaatvdis dtadtvdis
objdis pgmdis pgmrsudis tipdis verdis
crtavl dscnorrcp dscmtdavl dscbbgdis
cgahorlcn cgaacdciecul
nomdisepa objdisepa pgmdisepa pgmrsudisepa          (espanhol — vazios nesta disciplina)
nomdisigl objdisigl pgmdisigl pgmrsudisigl          (inglês — preenchidos)
```

Mapeamento verificado contra o HTML da mesma disciplina: `pgmrsudis` = Ementa,
`pgmdis` = Conteúdo Programático, `dscbbgdis` = Bibliografia, `dscmtdavl` = Método de
Avaliação, `crtavl` = Critério, `dscnorrcp` = Norma de Recuperação, `tipdis="S"` = Semestral.
**Carga horária total não é campo**: o JS oficial calcula `creaul*15 + cretrb*30`
(confere com os 45 h que o HTML mostra para 3+0).

### 4.4 O endpoint é stateless — verificado

Requisição 25: **sem cookie jar, sem handshake `__System.generateId`, com
`scriptSessionId=0000000000000000` inventado**, para `PME3344`:

```
status=200  ctype=text/javascript;charset=ISO-8859-1  size=2448
… handleCallback("0","0",{coddis:"PME3344",nomdis:"Termodinâmica Aplicada",creaul:"2",…})
```

Consequência de desenho: um servidor HTTP hospedado (§6 do SPEC) pode chamar isso
diretamente, sem gerenciar sessão. Encaixa no "dado público e cacheável" sem ressalva.

### 4.5 Erro é legível (bom para o Invariante 6)

Sigla inexistente `ZZZ9999` → HTTP **200**, mas `handleException` em vez de `handleCallback`:

```js
dwr.engine.remote.handleException("0","0",{cause:null,errorCode:0,
  javaClassName:"usp.erro.USPException",
  localizedMessage:"Disciplina inválida ou ainda não ativada !",
  message:"Disciplina inválida ou ainda não ativada !",
  stackTrace:[…46 frames…]})
```

Mensagem em português, pronta para repassar ao usuário. **Cuidado de implementação:** o
status é 200 nos dois casos — quem checar só o código HTTP produz exatamente o silêncio que
o Invariante 6 proíbe. Discriminar por `handleException` vs `handleCallback`.
Custo colateral: o stack trace de 46 frames faz a resposta de erro (7.176 B) ser **quase o
dobro** da resposta de sucesso (3.707 B). Descartar o `stackTrace` antes de logar.

### 4.6 Nada de REST/JSON convencional

- `/jupiterweb/dwr/index.html` → **404**
- `/jupiterweb/servicos` (hipótese de backend móvel, por paralelo ao `rucard/servicos` do
  §1.2 do SPEC) → **404**
- Nenhum `$.ajax`, `fetch(`, `getJSON` ou `XMLHttpRequest` em `jupiterweb.js` (8.697 B, 16
  funções, todas de UI: `bloquearTela`, `preencheCombo`, `validaData`…). As duas únicas
  menções a `dwr` no arquivo são `dwr.engine._timeout` em comentário de timeout.
- As páginas de **disciplina** e de **turma** carregam `dwr/engine.js` e `dwr/util.js` mas
  **nenhuma interface DWR** — o conteúdo delas é 100% renderizado no servidor.

**Não verificado, e não vou afirmar:** se existe uma API JSON da USP fora do JupiterWeb
(algo como um `api.usp.br`). Eu não sondei nenhum host além de `uspdigital.usp.br`, porque
isso viraria adivinhação de nome de domínio, que é o laço que o Invariante 5 proíbe.

---

## 5. Pergunta 5 — grade curricular, horário e vínculo do aluno

### 5.1 Grade curricular — **estruturada, pública, uma chamada**

Cadeia verificada, três chamadas:

1. `pubListarColegiado {pfxdisval:"XXX", codcg:"0"}` → **47 unidades**.
   Ex.: `{codclg:"3",nomclg:"Escola Politécnica - ( EP )"}`, `{codclg:"43",…"Instituto de Física"}`.
2. `pubListarCursoEntrada {codclg:"3"}` → **11 cursos de ingresso da Poli**, campos
   `codcur, codhab, nomhab, nomcur, perhab`. Ex.:
   `{codcur:"3033",codhab:"0",nomhab:"Ciclo Básico - Engenharia Elétrica",nomcur:"Engenharia",perhab:"integral"}`
3. `pubGradeCurricular {codcur:"3033", codhab:"0", tipo:"N"}` → **67 registros, 17.356 B**,
   campos `coddis verdis nomdis creaul cretrb tipobg numsemidl tipdis obscur cgahoreto
   cgahorlcn cgaacdciecul temce temcp temaaca codcurcom codhabcom`.
   `tipobg`: 31 `O` (obrigatória) e 36 `L` (optativa livre); `numsemidl` (semestre ideal)
   vai de 1 a 5 neste currículo. Ex.:
   `{coddis:"MAT2453",verdis:"4",nomdis:"Cálculo Diferencial e Integral I",creaul:"6",cretrb:"0",tipobg:"O",numsemidl:"1",tipdis:"S",…}`

Nota: o `codcur` do Ciclo Básico Elétrica aparece como **3033** em `pubListarCursoEntrada` e
como **3032** no HTML de `listarCursosRequisitos?coddis=PSI3323`. São códigos diferentes na
mesma família; **não investiguei por quê** e não vou inventar explicação. Quem implementar
precisa resolver isso antes de assumir que um único `codcur` serve.

**`tipo=V`** (26/10): para os currículos da lista de anteriores (`jupCursoLista?tipo=V`),
`pubGradeCurricular` só responde com `tipo:"V"`; com `N` vem vazio. É isso, e não a falta
de dado, que a discrepância 3033 × 3032 escondia.

### 5.2 Pré-requisito — **estruturado**

`pubListarRequisitoDisciplina {codcur:"3033", codhab:"0", coddis:"MAT2454"}` → 307 B:

```
{coddisreq:"MAT2453",tipreq:"PR",numgrpreq:"1",
 nomdisreq:"Cálculo Diferencial e Integral I",stamtrrcp:"S"}
```

`tipreq:"PR"` = pré-requisito. `numgrpreq` é o "grupo" que o HTML chama de *Indicação de
Conjunto* (pré-requisitos alternativos). **Não verificado:** o conjunto completo de valores
de `tipreq` e o significado exato de `stamtrrcp` — uma amostra só mostra `PR` e `S`.

Pré-requisito **depende do curso**, não só da disciplina: os parâmetros exigem
`codcur`+`codhab`. Isso responde metade da pergunta candidata do §5 do SPEC ("Essa
disciplina tem quantos créditos e qual o pré-requisito?") — os créditos são
incondicionais (`pubObterDisciplina`), o pré-requisito **não é**.

### 5.3 Horário de aula — existe, mas **só em HTML**

`jupDisciplinaBusca?tipo=T` (Busca por Turmas) foi requisitada de propósito para checar isto:
**a página não carrega nenhuma interface DWR** (lista de `<script src>` verificada, zero
`dwr/interface/*`), e seu JS faz o mesmo `document.location.href='obterTurma?…'`.

Não há consulta `pub*` de turma em nenhum JS que eu li. Portanto:

> **Horário, sala, vagas e professor da turma são acessíveis apenas por scraping do HTML de
> `obterTurma?sgldis=…`.** Não achei caminho estruturado.

Isso é a fronteira do projeto: o Jupiter dá API para o que muda por semestre-ementa
(estável) e HTML para o que muda por semestre-oferecimento (volátil) — exatamente o
contrário do que seria conveniente.

### 5.4 Vínculo do aluno — **não existe sem login**

Nada de "minhas disciplinas", nota, histórico ou matrícula na superfície pública. Tudo isso
está atrás de `webLogin.jsp` / Senha Única, que por restrição desta tarefa **não foi tocado**.
Registro como achado: o Jupiter público é **catálogo institucional**, não perfil de aluno.
O que o dono cursa continua vindo do Moodle (§1.3 do SPEC).

---

## 6. Pergunta 4 — quão estável é o HTML

Ruim. Medido, não impressão:

| página | bytes HTML | bytes de texto útil | sobra |
|---|---:|---:|---:|
| `obterDisciplina?sgldis=PSI3323` | 42.769 | 4.032 | 9,4% |
| `obterTurma?sgldis=PSI3323` (9 turmas) | 110.847 | 4.967 | 4,5% |
| `listarCursosRequisitos?coddis=PSI3323` | 30.230 | 782 | 2,6% |
| `/jupiterweb/` (só o menu) | 26.498 | 539 | 2,0% |

Cerca de 26 kB de todas elas é o mesmo *chrome* de menu público, repetido.
Isso reproduz o padrão que o §9 do SPEC (31/08) já registrou para o Moodle: **quanto mais
comprime, menos estava respondendo.**

Sobre âncoras — este é o ponto que decide manutenibilidade:

- `obterDisciplina`: **20 `<table>`, 64 `<tr>`, e os únicos `id=` da página são de layout**
  (`layout_conteudo`, `listMenuRoot`, `my_web_cabecalho`, `fsmenu-fallback`…).
  Zero id no conteúdo.
- `obterTurma`: **48 `<table>`, 148 `<tr>`**, mesmos ids de layout e nada mais.
- As classes disponíveis são **puramente tipográficas**: `txt_arial_10pt_black`,
  `txt_verdana_8pt_gray`, `txt_arial_7pt_black`, `link_gray`… Um redesenho que troque
  Verdana 8pt por outra coisa quebra qualquer seletor baseado nelas, sem trocar uma vírgula
  do dado.
- O markup é HTML 4.01 Transitional com `<font face="Verdana, Arial, Helvetica, sans-serif"
  size="1" color="#666666">` em cada célula, e ainda tem `<!-- hidden -->` e `<!-- acoes -->`
  comentados no meio.

**Veredito sobre scraping:** um parser teria que ancorar em *rótulos de texto*
("Créditos Aula:", "Código da Turma:", "Horário") e caminhar pela árvore a partir deles.
É factível — os rótulos são estáveis porque são o que o usuário lê — mas é frágil a
qualquer reforma de layout, e o SPEC já exige, nesse caso, "manutenção semestral explícita
ou não prometer".

---

## 7. Recomendação

**Fazer, com DWR (`ControlePublicoDWR`):** ementa, objetivos, programa, bibliografia,
créditos, tipo, ativação, versões em inglês/espanhol; grade curricular de um curso;
pré-requisito por curso; lista de unidades e cursos. Custo medido:

| chamada | bytes | ~tokens |
|---|---:|---:|
| `pubObterDisciplina` (1 disciplina) | 3.707 | ~930 |
| `pubListarRequisitoDisciplina` (1 disciplina/curso) | 307 | ~80 |
| `pubGradeCurricular` (67 disciplinas) | 17.356 | ~4.340 |
| `pubListarColegiado` (47 unidades) | 4.033 | ~1.010 |
| `pubListarCursoEntrada` (11 cursos) | 1.576 | ~390 |

Contra 42.769 B de HTML para a mesma disciplina: **11,5× menor**, e sem parser de tabela.
Depois de projetar (descartar `stackTrace`, os campos `*epa` vazios e as versões em inglês
quando não pedidas), `pubObterDisciplina` cai bem abaixo disso — não medi o número
projetado, então não vou citar um.

**Não prometer, ou prometer com aviso explícito:** horário de aula, sala, vagas e professor
da turma. É scraping de 48 tabelas aninhadas sem uma única âncora semântica. Se entrar,
entra com a manutenção semestral declarada que o §4 do SPEC exige, e com o Invariante 7
(dizer que a fonte é frágil) na própria saída.

**Argumento de valor, honesto:** o Jupiter é o único lugar onde estão ementa, créditos,
pré-requisito e horário — o Moodle não tem nada disso. A pergunta candidata "Essa disciplina
tem quantos créditos e qual o pré-requisito?" (§5 do SPEC) é respondível hoje em **duas
chamadas DWR e ~1.010 tokens**, sem credencial nenhuma. Isso é barato o suficiente para ser
um servidor HTTP hospedado e cacheado (§6 do SPEC), com TTL semestral — ementa muda por
semestre, e o Invariante 5 aponta exatamente para esse TTL.

---

## 8. O que ficou por testar

Parei em 26 requisições. Não testado, em ordem de utilidade:

1. **`obterTurma` de outra disciplina.** Só tenho PSI3323. Não sei se 9 turmas é típico nem
   se a estrutura do bloco de horário varia quando há turma teórica + prática, turma sem
   horário publicado, ou disciplina anual. **Isso é o maior buraco** — é justamente a parte
   frágil, e tem uma amostra só.
2. **`pubObterInfoCurso` / `pubObterInfoCursoWeb` / `pubListarDiscipResp` /
   `recuperarProjetoPedagogico`.** Nomes e assinaturas lidos no JS oficial, nunca chamados.
3. **`jupArquivosPublicos.jsp?tiparq=9&anoprg=2026`** — calendário escolar. Provavelmente um
   PDF; não abri.
4. **`jupColegiadoEmailLista`** — contatos de colegiado.
5. **Rate limit.** Zero evidência. 26 requisições espaçadas não produziram 429, 403 nem
   throttling observável, e isso **não é prova de que não exista**.
6. **Cache.** Todas as páginas trazem `<meta HTTP-EQUIV="CACHE-CONTROL" CONTENT="NO-CACHE">`;
   não inspecionei headers `Cache-Control`/`ETag` reais das respostas DWR.
7. **Discrepância `codcur` 3032 vs 3033** (§5.1).
8. **Estabilidade do `verdis`.** `pubObterDisciplina` aceita `verdis` (versão da disciplina);
   passei `0` e o retorno veio com `verdis:"2"`. Não testei o que `verdis:1` devolve, nem se
   `0` significa "corrente". Não assuma.
9. **Se a mesma sigla pode existir em mais de uma unidade.** `obterDisciplina` só recebe
   sigla; presumo unicidade, mas **não verifiquei**.

---

## 9. Invariante 8 — termos de uso, robots.txt

- **Não existe `robots.txt` em `uspdigital.usp.br`.** `GET /robots.txt` → **302** com
  `Location: /wsusuario/`, e o destino é a tela de login (200, 17.538 B). Qualquer caminho
  desconhecido no host cai nesse redirect, então isso é o comportamento padrão de 404 do
  balanceador, não uma diretiva. **Não há permissão nem proibição declarada por esse canal.**
- **`creditos.jsp` não tem termo de uso, licença ou aviso legal** — é só a lista nominal de
  Reitoria, Pró-Reitoria de Graduação, GRS e STI. O único texto jurídico do rodapé, em todas
  as páginas, é: `© 1999 - 2026 - Superintendência de Tecnologia da Informação/USP`.
- Consequência para o Invariante 8: **"está público" continua não equivalendo a "liberado
  para redistribuir"**, e aqui não há sequer um documento a citar. O `ControlePublicoDWR` é
  nominalmente público, o que é um sinal forte de intenção — mas é sinal, não permissão
  escrita. Antes de divulgar amplamente, o caminho é perguntar à STI/Pró-G, não deduzir do
  nome da classe. O README precisa da declaração de não-vínculo de qualquer forma.
- Higiene mínima recomendada se isso virar servidor: User-Agent identificável com contato,
  cache com TTL semestral e concorrência 1. Nada disso está implementado — é recomendação.

---

## 10. Fixtures salvas

`fixtures/jupiter/` — cruas, como vieram (HTML em ISO-8859-1, DWR com escapes `\uXXXX`).

| arquivo | o que é |
|---|---|
| `html-index.html` | home pública, com o array do menu `nomgrpweb=Público` |
| `html-buscaDisciplina-form.html` | form `tipo=D` + o JS que monta `obterDisciplina?…` |
| `html-buscaTurma-form.html` | form `tipo=T`; **prova de que não há DWR aqui** |
| `html-jupCarreira.html` | a única página pública que carrega interfaces DWR |
| `html-obterDisciplina-PSI3323.html` | página de disciplina (42.769 B) |
| `html-obterTurma-PSI3323.html` | 9 turmas com horário/sala/vagas (110.847 B) |
| `html-listarCursosRequisitos-PSI3323.html` | requisitos por curso, em HTML |
| `html-creditos.html` | evidência de que não há termo de uso |
| `js-jupCarreira.js` | **o mapa da API** — todas as chamadas `pub*` e os campos |
| `dwr-ControlePublicoDWR.js`, `dwr-CursoControlePublicoDWR.js` | assinaturas dos métodos remotos |
| `dwr-handshake-generateId.txt` | handshake (que se descobriu dispensável) |
| `dwr-pubObterDisciplina-PSI3323.txt` | 26 campos, 3.707 B |
| `dwr-pubObterDisciplina-PTC3314.txt` | segunda amostra, mesma forma |
| `dwr-pubObterDisciplina-PME3344-sem-sessao.txt` | **prova de que é stateless** |
| `dwr-pubObterDisciplina-ERRO-sigla-inexistente.txt` | forma do erro (`handleException`) |
| `dwr-pubGradeCurricular-3033-0.txt` | 67 disciplinas, 17 campos cada |
| `dwr-pubListarColegiado.txt` | 47 unidades |
| `dwr-pubListarCursoEntrada-codclg3.txt` | 11 cursos da Poli |
| `dwr-pubListarRequisitoDisciplina-MAT2454.txt` | pré-requisito estruturado |

**Sobre dado pessoal:** nenhuma fixture contém dado do dono do projeto — não houve login e
nenhuma requisição foi feita em nome dele. O `html-obterTurma-PSI3323.html` contém **nomes de
professores e contagens de vagas/matriculados** de páginas públicas do catálogo; é o conteúdo
em si, não um vazamento, mas fica o registro para quem for decidir sobre commit.
O `cookies.txt` da sessão de captura foi **apagado** (Invariante 3).

## 14/09/2026 — o JupiterWeb entrega DOIS cookies, não um

Medido sem credencial, contra `webLogin.jsp` e `jupCarreira.jsp`. O §2 desta nota
registrava só o `JSESSIONID`.

```
JSESSIONID=…;      Path=/jupiterweb;  HttpOnly            (sem Secure)
UD_jupiterweb=…;   path=/;            secure;  httponly   (80 hex)
```

O segundo é entregue a visitante **anônimo**, então não é prova de sessão autenticada —
pode ser identificador de dispositivo, pré-auth ou anti-CSRF. O que ele é de fato só se
sabe com uma sessão logada, e está na Fase 1a do plano.

**Por que isso importa antes de qualquer código:** eu havia afirmado, na conversa de
14/09, que o cookie do Jupiter é `Path=/jupiterweb` e portanto não alcança outros sistemas
do USP Digital. O `UD_jupiterweb` tem **`path=/`** — escopo de host. Nome e path discordam,
e a afirmação tranquilizadora não se sustenta enquanto a discordância não for medida.

**Nenhum dos dois traz `Max-Age` nem `Expires`**: morrem com o navegador. O timeout de
inatividade do servidor continua **não medido** — 30 min é default do Tomcat, não fato
deste deployment, e a distinção entre as duas coisas é o assunto do item 9 do `CLAUDE.md`.
