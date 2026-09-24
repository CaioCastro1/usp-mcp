# O texto da página da disciplina, sob demanda — Plano de Implementação

> **Para quem executa:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recomendado) ou superpowers:executing-plans, tarefa por tarefa, na ordem. Os passos
> usam checkbox (`- [ ]`).

**Objetivo:** `material` passa a (a) dizer no rodapé quais seções da página têm texto
escrito que a lista não mostra e (b) devolver esse texto quando chamado com
`texto="<seção>"` ou `texto="tudo"`.

**Arquitetura:** `Secao` ganha o campo `texto` (prosa em texto puro do `summary` da
seção + `description` dos `label` dela), preenchido em `projetar_material`. O rodapé
troca o aviso "bloco(s) de texto sem link" por um que nomeia as seções com texto. Um
ramo novo em `material()` responde o modo texto com UMA chamada
(`core_course_get_contents`). O `server.py` expõe o parâmetro.

**Stack:** Python 3.13, pytest, offline. Rodar com `.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-24-texto-da-pagina-design.md` — leia antes.

## Restrições globais

- **Antes de começar:** `git fetch origin && git merge --ff-only origin/main` (ou
  `sync_with_base_branch` se for worktree do app). Worktree velha já deu diagnóstico
  errado neste projeto.
- Nenhuma chamada nova ao Moodle. O modo `texto` faz exatamente UMA:
  `core_course_get_contents`, com o `courseid` resolvido. Nunca `mod_assign_get_assignments`.
- Nenhuma string que sai do processo cita `§`, `Invariante`, `SPEC1`, `label` ou
  `summary` (`tests/test_jargao.py` e L3 vigiam). Docstring e comentário podem.
- Todo corte é declarado na saída. Nada de lista vazia muda.
- Escreva em português, no tom dos comentários vizinhos (o porquê, não o quê).
- Não rode a camada `live` (`USP_MCP_LIVE=1`): é decisão do dono.
- Gate final: `./scripts/gate.sh` verde.

---

### Tarefa 1: `Secao.texto` preenchido na projeção

**Arquivos:**
- Modificar: `usp_mcp/moodle/material.py` (import de `.texto`, `Secao`, `projetar_material`, `_com_anexos`)
- Criar: `tests/moodle/test_texto_da_pagina.py`

**Interfaces:**
- Produz: `Secao(nome: str, itens: tuple[Item, ...], texto: str = "")`. `texto` é
  `"\n".join` das partes não vazias, na ordem da página: `sem_html(summary)` da seção,
  depois `sem_html(description)` de cada módulo `label`. Vazio quando não há prosa.

- [ ] **Passo 1: teste que falha**

Crie `tests/moodle/test_texto_da_pagina.py`:

```python
"""TP1-TP9: o texto escrito na página da disciplina, sob demanda.

O achado do dono (24/09/2026): a regra de avaliação de PTC3314 mora no texto da
seção do topo, `material` não o mostrava nem dizia que existia, e o assistente
chutou a regra pelo livro de notas. A fixture de PTC3314 é a mesma disciplina — a
seção "Ondas e Linhas" tem 5.414 B de texto (higienizado, com o tamanho real).
"""
from __future__ import annotations

import json

import pytest

from tests.moodle.conftest import FIXTURE_CONTEUDO_PTC3314
from tests.moodle.test_links_no_texto import DRIVE, _cliente, _label, _secao
from usp_mcp.moodle import disciplinas as disc
from usp_mcp.moodle import material as mat
from usp_mcp.moodle.erros import ErroMoodle
from usp_mcp.moodle.texto import sem_html

COURSEID_PTC3314 = 142036


@pytest.fixture(autouse=True)
def _cache_limpo():
    disc.limpar_cache()
    yield
    disc.limpar_cache()


@pytest.mark.contrato
def test_TP1_o_texto_da_secao_junta_resumo_e_blocos_de_texto_em_ordem():
    modulo_assign = {"id": 8001, "name": "EC-1", "modname": "assign",
                     "description": "<p>Aberto: 1 set. Vencimento: 8 set.</p>", "contents": []}
    conteudo = [_secao("Geral", [
        _label(7101, "Avaliação", "<p>MF = (8P + 2T)/10</p>"),
        modulo_assign,
        _label(7102, "Slides", f'<p>Os <a href="{DRIVE}">slides</a> ficam aqui.</p>'),
    ], summary="<p>Haverá 2 provas.</p>")]

    (secao,) = mat.projetar_material(conteudo).secoes

    assert secao.texto == "Haverá 2 provas.\nMF = (8P + 2T)/10\nOs slides ficam aqui."
    assert "Vencimento" not in secao.texto, "description de atividade não é texto da página"


@pytest.mark.contrato
def test_TP1b_secao_sem_prosa_tem_texto_vazio_e_os_anexos_nao_o_apagam():
    bruto = json.loads(FIXTURE_CONTEUDO_PTC3314.read_text(encoding="utf-8"))
    c = mat.projetar_material(bruto)
    topo = c.secoes[0]
    assert topo.nome == "Ondas e Linhas"
    assert topo.texto == sem_html(bruto[0]["summary"])
    assert c.secoes[-1].texto == "", "a última seção de PTC3314 tem summary vazio"

    # `_com_anexos` reconstrói as seções; o texto tem de sobreviver.
    anexos = mat.AnexosDeEntrega(itens=(mat.Item(
        nome="EP1.pdf", tipo="PDF", tamanho=None, modificado=None,
        url_externa=None, secao="Ondas e Linhas"),))
    assert mat._com_anexos(c, anexos).secoes[0].texto == topo.texto
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/moodle/test_texto_da_pagina.py -v`
Expected: FAIL com `AttributeError: 'Secao' object has no attribute 'texto'`.

- [ ] **Passo 3: implementar**

Em `usp_mcp/moodle/material.py`:

1. Import: `from .texto import casa, links, normalizar, sem_html`.
2. `Secao`:

```python
@dataclass(frozen=True)
class Secao:
    nome: str
    itens: tuple[Item, ...]
    # A prosa que o professor escreveu na página, em texto puro: o resumo da
    # seção e os blocos de texto dela, na ordem da página. Não sai na lista — sai
    # quando `material` é chamado com `texto`, e o rodapé diz que ela existe.
    # Medido em 24/09/2026: a regra de avaliação de PTC3314 mora aqui (5.414 B).
    texto: str = ""
```

3. Em `projetar_material`, dentro do `for secao in bruto or ():`, logo depois de
   `nome_secao = ...`:

```python
        prosa = [t for t in (sem_html(secao.get("summary") or ""),) if t]
```

   No ramo `if modname == _MODULO_DE_TEXTO:`, antes do `continue`:

```python
                if (t := sem_html(modulo.get("description") or "")):
                    prosa.append(t)
```

   E troque `secoes.append(Secao(nome=nome_secao, itens=tuple(itens)))` por:

```python
        secoes.append(Secao(nome=nome_secao, itens=tuple(itens), texto="\n".join(prosa)))
```

4. Em `_com_anexos`, a list comprehension passa a levar o texto:

```python
    secoes = [
        Secao(nome=s.nome, itens=s.itens + tuple(por_secao.pop(s.nome, ())), texto=s.texto)
        for s in conteudo.secoes
    ]
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/moodle/test_texto_da_pagina.py tests/moodle/test_material.py tests/moodle/test_links_no_texto.py -v`
Expected: PASS em tudo (nada na saída mudou ainda).

- [ ] **Passo 5: commit**

```bash
git add usp_mcp/moodle/material.py tests/moodle/test_texto_da_pagina.py
git commit -m "material: guarda o texto da página por seção, sem emiti-lo ainda"
```

---

### Tarefa 2: o rodapé nomeia as seções com texto

**Arquivos:**
- Modificar: `usp_mcp/moodle/material.py` (`_avisos_do_texto`)
- Modificar: `tests/moodle/test_links_no_texto.py` (L9)
- Modificar: `tests/moodle/test_custo.py` (`TETO["material"]`)
- Testar: `tests/moodle/test_texto_da_pagina.py`

**Interfaces:**
- Consome: `Secao.texto` (Tarefa 1), `_TETO_NOMES_NO_RODAPE` (já existe, = 3).
- Produz: `_secoes_com_texto(conteudo: Conteudo) -> list[str]` — nomes das seções com
  `texto` não vazio, `"(sem seção)"` para nome vazio, na ordem da página. A Tarefa 3 usa.

- [ ] **Passo 1: testes que falham**

Acrescente a `tests/moodle/test_texto_da_pagina.py`:

```python
@pytest.mark.contrato
def test_TP2_o_rodape_diz_que_ha_texto_e_como_pedir(disciplinas_brutas, conteudo_ptc3314):
    """O defeito que causou o chute: o resumo de seção sumia calado."""
    r = mat.material(_cliente(disciplinas_brutas, conteudo_ptc3314), "PTC3314", agora=lambda: 0.0)

    assert "19 seções têm texto escrito na página" in r.texto
    assert "Ondas e Linhas" in r.texto
    assert "e mais 16" in r.texto
    assert "`texto`" in r.texto and "`tudo`" in r.texto
    assert "summary" not in r.texto and "label" not in r.texto


@pytest.mark.contrato
def test_TP3_uma_secao_so_fica_no_singular(disciplinas_brutas):
    conteudo = [_secao("Geral", [], summary="<p>Tragam calculadora.</p>")]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323", agora=lambda: 0.0)

    assert r.vazio_por == "sem_material", "texto não é arquivo: o vazio continua vazio"
    assert "1 seção tem texto escrito na página" in r.texto
    assert "Geral" in r.texto
```

Em `tests/moodle/test_links_no_texto.py`, L9: o aviso antigo ("2 bloco(s) de texto…")
some, porque o texto dos dois `label` agora é texto da seção "Geral". Troque a linha
`assert "2 bloco" in r.texto` por:

```python
    assert "1 seção tem texto escrito na página" in r.texto and "Geral" in r.texto
```

e ajuste a docstring de L9: o rodapé passa a nomear a SEÇÃO que tem texto, não a contar
blocos.

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/moodle/test_texto_da_pagina.py tests/moodle/test_links_no_texto.py -v`
Expected: FAIL em TP2, TP3 e L9.

- [ ] **Passo 3: implementar**

Em `usp_mcp/moodle/material.py`, acima de `_avisos_do_texto`:

```python
def _secoes_com_texto(conteudo: Conteudo) -> list[str]:
    """Os nomes das seções que têm prosa na página, na ordem da página."""
    return [s.nome or "(sem seção)" for s in conteudo.secoes if s.texto]
```

Em `_avisos_do_texto`, **substitua** o bloco `if conteudo.textos_sem_link: ...` por:

```python
    # Substitui a contagem de "blocos de texto sem link", que só via `label`: o
    # resumo de seção sumia calado, e foi ali que a regra de avaliação de
    # PTC3314 se escondeu (24/09/2026). O texto do `label` agora é texto da seção,
    # então os dois avisos diriam a mesma coisa. Nomear a seção é o que deixa o
    # modelo pedir a certa; dizer para que serve é o que o faz ligar a pergunta
    # "como é a avaliação" a este parâmetro.
    if com_texto := _secoes_com_texto(conteudo):
        nomeadas = ", ".join(com_texto[:_TETO_NOMES_NO_RODAPE])
        if (sobra := len(com_texto) - _TETO_NOMES_NO_RODAPE) > 0:
            nomeadas += f", e mais {sobra}"
        quantas = "1 seção tem" if len(com_texto) == 1 else f"{len(com_texto)} seções têm"
        avisos.append(
            f"{quantas} texto escrito na página da disciplina, fora de arquivo e "
            f"de link, que esta lista não reproduz: {nomeadas}. É onde o professor "
            "costuma pôr critério de avaliação, pré-requisitos e bibliografia — "
            "para ler, chame de novo com `texto` igual ao nome da seção, ou `tudo`."
        )
```

Atualize a docstring de `_avisos_do_texto`: a terceira contagem agora é "quais seções
têm texto", não "quantos blocos sem link". O campo `Conteudo.textos_sem_link` **fica**
(L1 o usa como fato das capturas); só deixa de virar linha no rodapé — diga isso no
comentário do campo.

- [ ] **Passo 4: rodar e ver passar; ajustar o teto medido**

Run: `.venv/bin/python -m pytest tests/moodle -v`
Expected: TP2, TP3 e L9 passam. **Espere** OR2 vermelho para `material`: a saída de
PTC3314 cresceu (~+330 B). Leia o tamanho real na mensagem do OR2 e troque o teto em
`tests/moodle/test_custo.py` por um valor entre `tamanho` e `tamanho / 0.85`
(arredonde para dezena), com o motivo no comentário:

```python
    "material": <novo>,  # 6.410 → aqui: o rodapé nomeia as seções com texto na
    # página (24/09/2026), e é o que impede o chute sobre critério de avaliação
```

Se algum outro teste de `test_material.py` quebrar por contar linhas `⚠`, corrija a
contagem com o motivo — não apague a asserção.

- [ ] **Passo 5: commit**

```bash
git add usp_mcp/moodle/material.py tests/moodle/test_texto_da_pagina.py tests/moodle/test_links_no_texto.py tests/moodle/test_custo.py
git commit -m "material: o rodapé nomeia as seções que têm texto na página"
```

---

### Tarefa 3: o modo `texto` em `material()`

**Arquivos:**
- Modificar: `usp_mcp/moodle/material.py` (`material`, nova `_texto_da_pagina`, constante `_TETO_TEXTO`)
- Testar: `tests/moodle/test_texto_da_pagina.py`

**Interfaces:**
- Consome: `Secao.texto`, `_secoes_com_texto` não é necessário aqui (filtre `s.texto`).
- Produz: `material(cliente, disciplina, busca=None, agora=None, texto=None) -> RespostaMaterial`.
  `texto` vai por ÚLTIMO para não deslocar `agora`. No modo texto, `total` = seções com
  texto, `mostrados` = seções impressas, `vazio_por` ∈ {`None`, `"sem_texto"`,
  `"secao_sem_texto"`}.

- [ ] **Passo 1: testes que falham**

Acrescente a `tests/moodle/test_texto_da_pagina.py`:

```python
@pytest.mark.contrato
def test_TP4_texto_da_secao_do_topo_sai_inteiro_com_uma_chamada_so(disciplinas_brutas, conteudo_ptc3314):
    """A pergunta do dono. Asserção sobre o parâmetro ENVIADO, não só a saída."""
    cliente = _cliente(disciplinas_brutas, conteudo_ptc3314)
    r = mat.material(cliente, "PTC3314", agora=lambda: 0.0, texto="ondas e linhas")

    assert sem_html(conteudo_ptc3314[0]["summary"]) in r.texto
    assert r.texto.startswith("PTC3314 (")
    assert r.mostrados == 1 and r.total == 19 and r.vazio_por is None
    assert cliente.params_de("core_course_get_contents")["courseid"] == COURSEID_PTC3314
    nomes = [f for f, _ in cliente.chamadas]
    assert nomes.count("core_course_get_contents") == 1
    assert "mod_assign_get_assignments" not in nomes, "os anexos não servem ao texto"


@pytest.mark.contrato
def test_TP5_tudo_traz_todas_as_secoes_com_texto(disciplinas_brutas, conteudo_ptc3314):
    r = mat.material(_cliente(disciplinas_brutas, conteudo_ptc3314), "PTC3314",
                     agora=lambda: 0.0, texto="TUDO")
    assert r.mostrados == 19
    assert 9_000 < len(r.texto.encode()) < mat._TETO_TEXTO
    assert "⚠" not in r.texto, "nada cortado, nada a declarar"


@pytest.mark.contrato
def test_TP6_secao_que_nao_existe_lista_as_que_existem(disciplinas_brutas, conteudo_ptc3314):
    r = mat.material(_cliente(disciplinas_brutas, conteudo_ptc3314), "PTC3314",
                     agora=lambda: 0.0, texto="bibliografia")
    assert r.vazio_por == "secao_sem_texto" and r.mostrados == 0
    assert "'bibliografia'" in r.texto
    assert "Ondas e Linhas" in r.texto and "30 novembro - 6 dezembro" in r.texto
    assert "`tudo`" in r.texto


@pytest.mark.contrato
def test_TP7_busca_e_texto_juntos_e_erro_antes_de_qualquer_chamada(disciplinas_brutas, conteudo_ptc3314):
    cliente = _cliente(disciplinas_brutas, conteudo_ptc3314)
    with pytest.raises(ErroMoodle, match="um de cada vez"):
        mat.material(cliente, "PTC3314", busca="lista", texto="tudo", agora=lambda: 0.0)
    assert cliente.chamadas == []


@pytest.mark.contrato
def test_TP8_corte_por_tamanho_e_declarado(disciplinas_brutas):
    longo = "<p>" + ("x" * 9_000) + "</p>"
    conteudo = [_secao(f"S{i}", [], summary=longo) for i in range(3)]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323",
                     agora=lambda: 0.0, texto="tudo")
    assert len(r.texto.encode()) <= mat._TETO_TEXTO + 400, "teto + a linha do aviso"
    assert r.mostrados == 2
    assert "S2" in r.texto.split("⚠", 1)[1], "a seção que ficou de fora é nomeada"

    enorme = [_secao("Única", [], summary="<p>" + ("y" * 30_000) + "</p>")]
    disc.limpar_cache()
    r = mat.material(_cliente(disciplinas_brutas, enorme), "PSI3323",
                     agora=lambda: 0.0, texto="única")
    assert r.mostrados == 1 and "foi cortado" in r.texto


@pytest.mark.contrato
def test_TP9_pagina_sem_texto_diz_isso(disciplinas_brutas):
    conteudo = [_secao("Aula 1", [])]
    r = mat.material(_cliente(disciplinas_brutas, conteudo), "PSI3323",
                     agora=lambda: 0.0, texto="tudo")
    assert r.vazio_por == "sem_texto" and r.total == 0
    assert "não tem texto escrito" in r.texto
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/moodle/test_texto_da_pagina.py -v`
Expected: FAIL em TP4–TP9 com `TypeError: material() got an unexpected keyword argument 'texto'`.

- [ ] **Passo 3: implementar**

Em `usp_mcp/moodle/material.py`, perto de `_TETO_NOMES_NO_RODAPE`:

```python
# Teto do modo `texto`, em bytes. A maior amostra (`tudo` em PSI3323) dá ~14,3 kB;
# o teto corta por seção inteira e declara o que ficou de fora.
_TETO_TEXTO = 20_000
```

Nova função, acima de `material`:

```python
def _texto_da_pagina(cliente, alvo, pedido: str) -> RespostaMaterial:
    """O que o professor escreveu na página, por seção. UMA chamada.

    Só `core_course_get_contents`: os anexos de entrega (a segunda chamada de
    `acervo`) são arquivo, não texto, e pedi-los aqui seria martelar a USP por
    uma resposta que esta pergunta não usa.
    """
    conteudo = projetar_material(
        cliente.chamar("core_course_get_contents", courseid=alvo.courseid)
    )
    cabecalho = f"{alvo.sigla} ({alvo.rotulo}) — texto da página da disciplina"
    com_texto = [s for s in conteudo.secoes if s.texto]

    if not com_texto:
        return RespostaMaterial(
            texto=(
                f"{cabecalho}\n\nA página não tem texto escrito fora dos arquivos "
                "e links: tudo o que ela publica sai em `material` sem `texto`."
            ),
            total=0, mostrados=0, vazio_por="sem_texto",
        )

    escolhidas = (
        com_texto if normalizar(pedido) == "TUDO"
        else [s for s in com_texto if casa(pedido, s.nome)]
    )
    if not escolhidas:
        nomes = ", ".join(s.nome or "(sem seção)" for s in com_texto)
        return RespostaMaterial(
            texto=(
                f"{cabecalho}\n\nNenhuma seção com texto tem {pedido!r} no nome. "
                f"As {len(com_texto)} que têm: {nomes}. Repita com uma delas, "
                "ou com `tudo`."
            ),
            total=len(com_texto), mostrados=0, vazio_por="secao_sem_texto",
        )

    linhas = [cabecalho]
    usados = len(cabecalho.encode())
    mostradas = 0
    for s in escolhidas:
        nome = s.nome or "(sem seção)"
        bloco = f"\n{nome}:\n{s.texto}"
        tamanho = len(bloco.encode())
        if usados + tamanho > _TETO_TEXTO:
            if mostradas == 0:
                # Uma seção sozinha maior que o teto: sai até o teto, e o corte
                # é dito — nunca uma resposta vazia por ser grande demais.
                linhas.append(bloco.encode()[: _TETO_TEXTO - usados].decode("utf-8", "ignore"))
                linhas.append(f"\n⚠ O texto de {nome!r} é maior que o limite desta resposta e foi cortado aqui.")
                mostradas = 1
            break
        linhas.append(bloco)
        usados += tamanho
        mostradas += 1

    if fora := escolhidas[mostradas:]:
        nomes = ", ".join(s.nome or "(sem seção)" for s in fora)
        linhas.append(
            f"\n⚠ {len(fora)} seção(ões) ficaram de fora para caber no limite "
            f"desta resposta: {nomes}. Peça cada uma pelo nome."
        )

    return RespostaMaterial(texto="\n".join(linhas), total=len(com_texto), mostrados=mostradas)
```

Em `material`, mude a assinatura e o começo:

```python
def material(
    cliente, disciplina: str, busca: str | None = None, agora=None, texto: str | None = None
) -> RespostaMaterial:
    """...(docstring atual)...

    Com `texto`, responde outra pergunta sobre o mesmo espaço: o que o professor
    ESCREVEU na página, e não o que publicou como arquivo. Ver `_texto_da_pagina`.
    """
    pedido_texto = (texto or "").strip()
    if pedido_texto and (busca or "").strip():
        # Antes de qualquer chamada, como sigla inválida: combinar os dois calado
        # faria um deles ser ignorado.
        raise ErroMoodle(
            "`busca` procura pelo nome de arquivo e `texto` pelo nome de seção; "
            "juntos, um deles seria ignorado. Chame com um de cada vez."
        )

    lista = carregar(cliente, agora=agora)
    resolucao = resolver(lista, disciplina)
    if resolucao.disciplina is None:
        raise ErroMoodle(resolucao.motivo)

    alvo = resolucao.disciplina
    if pedido_texto:
        return _texto_da_pagina(cliente, alvo, pedido_texto)

    conteudo = acervo(cliente, alvo.courseid)
    # ... resto inalterado
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/moodle -v`
Expected: PASS em tudo. Se TP8 falhar no `+ 400`, meça a linha do aviso e ajuste — não
afrouxe o teto.

- [ ] **Passo 5: commit**

```bash
git add usp_mcp/moodle/material.py tests/moodle/test_texto_da_pagina.py
git commit -m "material: com \`texto\`, devolve o que o professor escreveu na página"
```

---

### Tarefa 4: expor `texto` no servidor

**Arquivos:**
- Modificar: `usp_mcp/moodle/server.py` — descrição e `inputSchema` de `_NOME_MATERIAL`
  (~linha 248), despacho em `chamar_ferramenta` (~757), `_material` + `anotar` (~909),
  `_sonda_material` em `_auto_verificar` (~1199)
- Testar: `tests/moodle/test_texto_da_pagina.py`

**Interfaces:**
- Consome: `material(..., texto=...)` (Tarefa 3).
- Produz: parâmetro `texto` (string, opcional) no `tools/list` de `material`.

- [ ] **Passo 1: testes que falham**

```python
from usp_mcp.moodle.server import chamar_ferramenta, listar_ferramentas


@pytest.mark.contrato
def test_TP10_o_schema_de_material_tem_texto_opcional():
    (porta,) = [f for f in listar_ferramentas() if f["name"] == "material"]
    props = porta["inputSchema"]["properties"]
    assert props["texto"]["type"] == "string"
    assert "texto" not in porta["inputSchema"]["required"]
    assert "avaliação" in porta["description"] or "avaliada" in porta["description"]


@pytest.mark.contrato
def test_TP11_o_despacho_repassa_texto(disciplinas_brutas, conteudo_ptc3314):
    cliente = _cliente(disciplinas_brutas, conteudo_ptc3314)
    saida = chamar_ferramenta(
        "material", {"disciplina": "PTC3314", "texto": "Ondas e Linhas"}, cliente=cliente
    )
    assert "texto da página da disciplina" in saida
    assert "mod_assign_get_assignments" not in [f for f, _ in cliente.chamadas]
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/moodle/test_texto_da_pagina.py -k "TP10 or TP11" -v`
Expected: FAIL com `KeyError: 'texto'`.

- [ ] **Passo 3: implementar**

1. Na `description` de `material`, depois da frase "...'onde estão os slides'. ", acrescente:

```python
                "Com `texto`, devolve em vez da lista o que o professor ESCREVEU "
                "na própria página — como a disciplina é avaliada, o que ela "
                "exige antes, que livros usa: 'como é a avaliação de PTC3314', "
                "'quantos testes posso perder'. "
```

2. No `inputSchema.properties`, depois de `busca`:

```python
                    "texto": {
                        "type": "string",
                        "description": (
                            "Nome ou pedaço do nome de uma seção da página, ou "
                            "'tudo'. Troca a lista de arquivos pelo texto escrito "
                            "nessas seções. Não combina com `busca`."
                        ),
                    },
```

3. Despacho (`if nome == _NOME_MATERIAL:`): acrescente `texto=argumentos.get("texto"),`.
4. `_material`:

```python
    def _material(disciplina, busca=None, texto=None) -> str:
        # (comentário atual sobre `disciplina` sem default)
        return _chamar(
            porta_material["name"],
            {"disciplina": disciplina, "busca": busca, "texto": texto},
        )

    anotar(
        _material, porta_material["inputSchema"],
        {"disciplina": str, "busca": str | None, "texto": str | None},
    )
```

5. `_sonda_material(disciplina: str, busca: str | None = None, texto: str | None = None)`.

- [ ] **Passo 4: rodar tudo**

Run: `.venv/bin/python -m pytest tests/moodle tests/handshake tests/test_jargao.py -v`
Expected: PASS. **Atenção ao OR3** (`test_custo.py`: a resposta não repete a
descrição): se ele apontar a frase do rodapé da Tarefa 2 como cópia da descrição,
reescreva a frase do **rodapé** (mantenha os nomes das seções e a instrução
`texto`/`tudo`; tire o que a descrição já diz) e reajuste o teto do OR2 no mesmo commit.

Run: `.venv/bin/python -m usp_mcp.moodle.server --auto-verificar`
Expected: a verificação de schema × assinatura diz OK para `material`.

- [ ] **Passo 5: commit**

```bash
git add usp_mcp/moodle/server.py tests/moodle/test_texto_da_pagina.py tests/moodle/test_custo.py usp_mcp/moodle/material.py
git commit -m "server: material aceita \`texto\` para ler a página da disciplina"
```

---

### Tarefa 5: registrar o dado (Definição de Pronto)

**Arquivos:**
- Modificar: `SPEC1.md` (entrada nova no fim do §9)
- Modificar: `usp_mcp/moodle/material.py` (docstring do módulo: um parágrafo novo)
- Modificar: `README.md` (linha 31, a tabela de perguntas)

- [ ] **Passo 1: §9 do SPEC1.md**

Entrada nova, depois da última, com o título
`### 24/09/2026 — o resumo de seção tinha a regra de avaliação, e a decisão de 03/09 julgou o corpo pelo título`.
Conteúdo, em prosa no estilo das vizinhas:

- o achado (sessão de uso: PTC3314, faltas nos testes, chute pelo livro de notas,
  print da página);
- o dado: tabela da spec (19 seções com texto, 9.893 B; topo 5.414 B; PSI3323
  14.278 B), e que a amostra já tinha o caso;
- o que se revê da entrada de 03/09 ("Descartado junto: os `summary` de seção") e o
  que continua certo nela (o custo);
- a decisão (sob demanda, parâmetro, rodapé, uma chamada) e o descartado (emitir
  sempre; ferramenta nova), com os números;
- a lição: **o livro de notas do Moodle não é a regra da disciplina** — o peso
  configurado em `notas` divergiu do texto do professor, e o texto vence;
- o novo teto do OR2 de `material` e o `_TETO_TEXTO`.

- [ ] **Passo 2: docstring de `material.py`**

Acrescente ao fim da docstring do módulo um parágrafo
`**O texto da página, sob demanda (24/09/2026).**` resumindo: o rodapé nomeia as seções
com texto, `texto=` devolve a prosa com uma chamada só, e por que não sai sempre
(+150%/+220%). Aponte para a spec.

- [ ] **Passo 3: README**

Na tabela de perguntas (linha ~31), acrescente abaixo da linha de "Que arquivos tem em
PTC3314?":

```markdown
| "Como é a avaliação de PTC3314?" | Lê o texto que o professor escreveu na página da disciplina |
```

- [ ] **Passo 4: gate**

Run: `./scripts/gate.sh`
Expected: verde.

- [ ] **Passo 5: commit**

```bash
git add SPEC1.md usp_mcp/moodle/material.py README.md
git commit -m "SPEC1 §9: o texto da página sob demanda, e o dado que reabriu 03/09"
```
