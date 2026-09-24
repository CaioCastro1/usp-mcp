# O texto da página da disciplina, sob demanda — design

> 24/09/2026. Fecha um achado do dono em uso real, e reabre a parte da decisão de
> 03/09/2026 (§9, "a busca semântica é do modelo") que descartou os `summary` de
> seção.

## O que aconteceu

Numa sessão de uso, a pergunta era sobre o critério de avaliação de uma
disciplina. O critério estava escrito no texto da seção do topo da página, junto
com objetivos, pré-requisitos e bibliografia. `material` não mostra esse texto, e
**não diz que ele existe**, então o assistente respondeu sem ele.

São dois defeitos, e o segundo é o que levou à resposta sem base:

1. **Não há como ler o texto.** `projetar_material` lê o `summary` de cada seção
   e o `description` de cada `label` só para extrair links (`_links_do_texto`); a
   prosa é descartada.
2. **O descarte é calado para o `summary`** (Invariante 7). O rodapé conta
   "bloco(s) de texto da página sem link" — mas só para módulo `label`
   (`material.py`, `textos_sem_link`). Seção com texto e sem link some sem aviso.
   Um modelo que visse "a seção X tem texto que esta lista não mostra" teria
   pedido esse texto antes de responder.

## O que foi medido

Sem rede, sobre as capturas versionadas (a higienização troca as palavras por
sílabas sintéticas mas preserva o tamanho — `scripts/higienizar.py`,
`SUFIXOS_TEXTO`):

| | PSI3323 | PTC3314 |
|---|---:|---:|
| seções com `summary` não vazio | 11 | 19 |
| `summary` em texto puro (`sem_html`), total | 14.278 B | 9.893 B |
| seção do topo, texto puro | 1.795 B | **5.414 B** |
| `material` hoje (saída inteira) | ~6.400 B | 6.410 B de teto (OR2) |

A seção do topo é a que concentra o texto — é o lugar típico de objetivos,
critério de avaliação e bibliografia. Não é preciso capturar nada novo para
medir: o custo real está na amostra.

A decisão de 03/09 disse que os `summary` "são o campo que menos promete", a
partir dos títulos medidos (`AULA 1`, `Geral`, datas). O título não é o texto: uma
seção de título genérico pode ter, no corpo, as regras da disciplina.
O custo medido naquela data continua certo — o erro foi concluir, do título, o
valor do corpo.

## Decisões, com a razão de cada uma

### 1. Sob demanda, nunca junto da lista

Emitir o texto em toda chamada de `material` custaria de +150% (PTC3314) a +220%
(PSI3323) em toda pergunta "cadê a lista 3", em que ele não serve. Sob demanda,
quem paga é só a pergunta que precisa dele. É o mesmo desenho do `secoes` do
Jupiter (`ementa` por padrão, `avaliacao` quando pedida).

### 2. Parâmetro de `material`, não ferramenta nova

§5: a pergunta é sobre o espaço da disciplina, que é o que `material` já cobre, e
a descoberta ("tem texto nesta página?") sai no rodapé dele. Uma ferramenta à
parte obrigaria o modelo a saber de antemão que o texto existe — exatamente o que
falhou. O parâmetro se chama `texto` e recebe o nome (ou pedaço) de uma seção, ou
`tudo`.

### 3. O rodapé passa a contar e nomear as seções com texto

Substitui o aviso de "bloco(s) de texto sem link": o texto do `label` passa a
fazer parte do texto da seção, então os dois avisos diriam a mesma coisa. Nomeia
até 3 seções e diz "e mais N" — o mesmo teto e a mesma forma das entregas sem
anexo (`_TETO_NOMES_NO_RODAPE`). O rodapé diz para que serve ("critério de
avaliação, pré-requisitos, bibliografia") porque é isso que faz o modelo ligar a
pergunta ao parâmetro.

### 4. Uma chamada só, e nenhuma a mais do que hoje

`texto` usa só `core_course_get_contents` — a mesma resposta que `material` já
pede. Não faz a segunda chamada (`mod_assign_get_assignments`), que só serve aos
anexos. Invariante 5 intacto.

### 5. O que entra no texto de uma seção

`sem_html(summary)` da seção, seguido de `sem_html(description)` de cada `label`
dela, na ordem da página. **Não** entra o `description` dos outros módulos:
medido em PTC3314, o de `assign` são 529 B de datas, que `o_que_vence` responde
melhor.

### 6. `busca` e `texto` juntos é erro legível, antes de qualquer chamada

Filtram coisas diferentes (nome de arquivo × nome de seção); combiná-los calado
faria um deles ser ignorado. Erro antes de gastar chamada, como sigla inválida.

### 7. Teto de 20.000 B no modo texto, declarado

A maior amostra (`tudo` em PSI3323) dá ~14,3 kB. O teto corta por seção inteira;
seção que sozinha passa do teto é cortada no teto. Nos dois casos a saída diz o
que ficou de fora e como pedir (Invariante 7).

## O que isto não resolve

- **Texto em `page`, `book` ou PDF** não é coberto; nenhum dos dois aparece na
  amostra (0 `page`, medido em 17/09).
- O texto é de terceiro (o professor) e sai inteiro, como o corpo de post em
  `avisos`. Não é instrução para o modelo; é dado.
