"""Fronteira MCP do Moodle. Entrypoint local stdio (§6 do SPEC1).

Este pacote não tem servidor na raiz de propósito: o servidor público
(RUCard/Jupiter) é outro processo, sem credencial pessoal. Este módulo é o
entrypoint LOCAL — dado autenticado do dono nunca sai desta máquina
(Invariante 4). É por isso que ele fala stdio, não HTTP hospedado.

A suíte (`tests/moodle/test_server_mcp.py`) tem só 3 testes de propósito: o
valor real está na projeção (`projecao.py`) e na política (`politica.py`),
que não têm nada a ver com protocolo MCP. Esta camada expõe duas funções
puras — `listar_ferramentas` e `chamar_ferramenta` — que qualquer adaptador
de protocolo pode chamar sem precisar do SDK instalado; `main()` é a casca
stdio por cima, e só ela importa o SDK (import de topo quebraria a suíte,
que roda sem o SDK presente).
"""
from __future__ import annotations

import os

from ..anotacoes import (
    ENTREGA_SEM_DESFAZER,
    ESCREVE_NO_DEPOSITO,
    ESCREVE_RASCUNHO,
    SO_LEITURA,
    para_o_sdk,
)
from ..env import carregar_env
from . import capacidades
from . import entrega as entrega_mod
from . import politica
from .arquivo import baixar_arquivo
from .atrasadas import atrasadas
from .avisos import avisos
from .cliente import ClienteMoodle
from .diagnostico import diagnostico
from .disciplinas import minhas_disciplinas
from .erros import ErroMoodle
from .ja_entreguei import ja_entreguei
from .material import material
from .notas import notas
from .o_que_mudou import o_que_mudou
from .o_que_vence import o_que_vence
from .questionarios import questionarios

# URL default: mesma do §8 do SPEC1 e de scripts/ws.sh. MOODLE_URL sobrescreve
# para quem precisa apontar para outro ambiente (não há esse caso hoje, mas
# não custa não fixar o valor).
_URL_PADRAO = "https://edisciplinas.usp.br"

# Onze ferramentas (§5: crescer é decisão de §9 — a segunda entrou em 31/08, a
# terceira em 01/09, da quarta à décima em 14/09, e a décima primeira em
# 17/09). Os nomes vêm das perguntas do dono, não das funções do Moodle por
# trás.
_NOME_FERRAMENTA = "o_que_vence"
_NOME_MATERIAL = "material"
_NOME_ARQUIVO = "baixar_arquivo"
_NOME_DIAGNOSTICO = "diagnostico"
_NOME_JA_ENTREGUEI = "ja_entreguei"
_NOME_NOTAS = "notas"
_NOME_AVISOS = "avisos"
_NOME_MUDOU = "o_que_mudou"
_NOME_DISCIPLINAS = "disciplinas"
_NOME_ATRASADAS = "atrasadas"
_NOME_QUESTIONARIOS = "questionarios"

# As duas de 15/09/2026, e as únicas que escrevem. Só aparecem com
# `USP_MCP_ENTREGA=1` — ver `_ferramentas_de_entrega`.
_NOME_RASCUNHO = "salvar_rascunho"
_NOME_ENTREGAR = "entregar"


def _ferramentas_de_entrega() -> list[dict]:
    """As duas de escrita, ou lista vazia quando a flag está desligada.

    **Desaparecer é melhor do que recusar.** Uma ferramenta que aparece no
    `tools/list` e sempre responde "não posso" ensina o modelo a tentar: ele a
    vê na lista, escolhe, gasta uma chamada, lê a negativa e tenta contornar.
    Com ela fora da lista o padrão continua sendo negar, e nada no que o modelo
    lê sugere que existe um caminho de escrita para procurar.
    """
    if not politica.entrega_habilitada():
        return []
    return [
        {
            "name": _NOME_RASCUNHO,
            "description": (
                "Salva o TEXTO do rascunho de uma entrega no e-Disciplinas "
                "(Moodle da USP), sem enviar para correção. Use para 'salva "
                "isso como rascunho no EP1', 'guarda esse texto na entrega'. "
                "Rascunho salvo NÃO é entrega feita: o professor não recebe "
                "nada até você usar `entregar`. Funciona em DUAS chamadas: a "
                "primeira não escreve nada e devolve um plano do que mudaria "
                "com um código; a segunda, repetindo o código, é que grava. Se "
                "alguma coisa mudar no e-Disciplinas entre uma e outra, o "
                "código não confere e a resposta traz o plano novo. Só entrega "
                "de TEXTO online: entrega por arquivo é recusada com esse "
                "motivo, porque este servidor não sobe arquivo. Entrega de "
                "grupo também é recusada."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam."
                        ),
                    },
                    "entrega": {
                        "type": "string",
                        "description": (
                            "Pedaço do nome da entrega — 'EP1', 'EC-2'. Se "
                            "casar com mais de uma, a resposta lista os "
                            "candidatos em vez de escolher por você."
                        ),
                    },
                    "texto": {
                        "type": "string",
                        "description": (
                            "O texto do rascunho. Ele SUBSTITUI o que estiver "
                            "lá — o conteúdo anterior não volta."
                        ),
                    },
                    "confirmacao": {
                        "type": "string",
                        "description": (
                            "O código que o plano devolveu na chamada anterior. "
                            "Sem ele nada é escrito: a resposta é o plano."
                        ),
                    },
                },
                "required": ["disciplina", "entrega", "texto"],
                "additionalProperties": False,
            },
            "annotations": ESCREVE_RASCUNHO,
        },
        {
            "name": _NOME_ENTREGAR,
            "description": (
                "ENVIA uma entrega para correção no e-Disciplinas (Moodle da "
                "USP) — o botão de entregar, com tudo o que ele significa. Use "
                "para 'entrega o EP1', 'manda o EC-1 para correção'. Isto NÃO "
                "tem como ser desfeito por este servidor: depois de enviada, a "
                "entrega está com o professor. Funciona em DUAS chamadas: a "
                "primeira não escreve nada e devolve um plano — estado atual, "
                "prazo, arquivos anexados, o que muda — com um código; a "
                "segunda, repetindo o código, é que envia. Se alguma coisa "
                "mudar no e-Disciplinas entre uma e outra (arquivo novo, prazo "
                "prorrogado, entrega já enviada), o código não confere e a "
                "resposta traz o plano novo em vez de enviar. Recusa, e diz por "
                "quê: entrega de grupo, entrega travada, entrega já enviada, "
                "envio não permitido pelo site, e entrega sem nenhum arquivo "
                "anexado. NÃO anexa arquivo — para ver o que já está anexado, "
                "use `ja_entreguei`."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam."
                        ),
                    },
                    "entrega": {
                        "type": "string",
                        "description": (
                            "Pedaço do nome da entrega — 'EP1', 'EC-2'. Se "
                            "casar com mais de uma, a resposta lista os "
                            "candidatos em vez de escolher por você: enviar a "
                            "errada não tem desfazer."
                        ),
                    },
                    "confirmacao": {
                        "type": "string",
                        "description": (
                            "O código que o plano devolveu na chamada anterior. "
                            "Sem ele nada é enviado: a resposta é o plano."
                        ),
                    },
                },
                "required": ["disciplina", "entrega"],
                "additionalProperties": False,
            },
            "annotations": ENTREGA_SEM_DESFAZER,
        },
    ]


def listar_ferramentas() -> list[dict]:
    """Descreve a ferramenta como o MODELO a vê: nome, descrição, parâmetros.

    A descrição usa o vocabulário de quem pergunta ("entrega", "prazo",
    "vence"), não o nome da função do Moodle por trás (T43) — é isso que faz
    o modelo escolher a ferramenta certa diante de uma pergunta em português.

    **Depende do ambiente desde 15/09/2026**, e é a única função deste projeto
    que depende: com `USP_MCP_ENTREGA=1` a lista tem treze itens, sem ela tem
    onze. Continua pura (lê `os.environ`, não escreve em lugar nenhum) e
    continua não exigindo o SDK. Quem carrega o `.env` antes de perguntar é
    `main()`, no começo do processo — aqui dentro um `carregar_env()` seria
    efeito colateral numa função que a suíte inteira chama.
    """
    return [
        {
            "name": _NOME_FERRAMENTA,
            "description": (
                "Lista o que tem prazo de entrega em breve nas disciplinas do "
                "e-Disciplinas (Moodle da USP): tarefas e questionários que "
                "vencem dentro de uma janela de dias a partir de agora. Use "
                "para responder perguntas como 'o que eu tenho para entregar', "
                "'o que vence essa semana' ou 'tem alguma tarefa vencendo'. Diz "
                "o que vence e quando, não se já foi feito: para isso, "
                "`ja_entreguei` (tarefa) e `questionarios` (questionário)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dias": {
                        "type": "integer",
                        "description": (
                            "Tamanho da janela, em dias, a partir de agora. "
                            "Padrão 14."
                        ),
                        "default": 14,
                    },
                    "limite": {
                        "type": "integer",
                        "description": (
                            "Número máximo de vencimentos no texto de saída. "
                            "Sem padrão: se omitido, todos os vencimentos "
                            "encontrados na janela entram na resposta."
                        ),
                    },
                },
                "additionalProperties": False,
            },
            # Consulta e nada mais, como em todas as `SO_LEITURA` abaixo: as
            # cinco funções da allowlist são de leitura, e a lista de bloqueio
            # permanente não é aberta por flag. A razão de cada campo do bloco
            # mora ao lado dele em `usp_mcp/anotacoes.py`, uma vez só — nove
            # cópias desta explicação seriam oito que envelhecem caladas.
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_MATERIAL,
            "description": (
                "Lista os arquivos publicados no espaço de uma disciplina no "
                "e-Disciplinas (Moodle da USP): PDFs de regras e programação da "
                "matéria, listas de exercícios, roteiros, apostilas, provas de "
                "semestres anteriores, **os arquivos de enunciado anexados às "
                "entregas e exercícios computacionais**, os links externos "
                "que o professor postou e **os links que ele deixou no meio do "
                "texto da página da disciplina** (slides no Google Drive, vídeo "
                "no YouTube, site de referência). Use para 'que arquivos tem em "
                "PSI3323', 'cadê as regras da disciplina', 'tem prova antiga em "
                "PTC3314', 'onde está a lista de exercícios', 'me dá o enunciado "
                "do EC-1', 'onde estão os slides'. "
                "NÃO devolve o link de download do arquivo "
                "interno — um endereço sem a credencial não abre, e um com ela "
                "exporia o token — mas diz o nome, o tipo e o tamanho de cada "
                "um. Para baixar de fato um destes arquivos, use `baixar_arquivo`."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PSI3323 ou PTC3314. Espaço e caixa não "
                            "importam. Aceita também o RÓTULO inteiro "
                            "(PSI3323-2026), que é o que distingue duas "
                            "matrículas da mesma sigla, e casa com pedaço do "
                            "nome."
                        ),
                    },
                    "busca": {
                        "type": "string",
                        "description": (
                            "Filtra por pedaço do nome do arquivo — 'prova', "
                            "'lista', 'regras'. Opcional: sem ele vem tudo, e "
                            "a saída diz quantos itens ficaram de fora quando "
                            "o filtro é usado."
                        ),
                    },
                },
                "required": ["disciplina"],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_ARQUIVO,
            "description": (
                "Baixa um arquivo publicado no espaço da disciplina no "
                "e-Disciplinas (Moodle da USP) e devolve o CAMINHO dele no disco "
                "desta máquina, para que você mesmo o abra com a sua ferramenta "
                "de leitura de arquivos. Use para 'me dá a lista 2 de PSI3323', "
                "'abre a apostila de amp op', 'pega a prova anterior', 'baixa o "
                "enunciado do EC-1'. Para saber "
                "que arquivos existem antes de escolher, use `material`."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PSI3323. Espaço e caixa não importam. "
                            "Aceita também o RÓTULO inteiro (PSI3323-2026), "
                            "que é o que distingue duas matrículas da mesma "
                            "sigla, e casa com pedaço do nome."
                        ),
                    },
                    "nome": {
                        "type": "string",
                        "description": (
                            "Pedaço do nome do arquivo, como aparece em "
                            "`material` — 'lista 2', 'apostila', 'regras'. "
                            "Acento e caixa não importam. Se casar com mais de "
                            "um, a resposta lista os candidatos em vez de "
                            "escolher por você."
                        ),
                    },
                    "todos": {
                        "type": "boolean",
                        "description": (
                            "Baixa TODOS os arquivos que casarem, em vez de "
                            "recusar a ambiguidade. Padrão falso. Há teto por "
                            "chamada, e o que ficar de fora é nomeado na saída."
                        ),
                    },
                },
                "required": ["disciplina", "nome"],
                "additionalProperties": False,
            },
            # A única das dez de leitura que não é read-only no sentido do
            # protocolo (as duas de escrita, quando existem, também não são):
            # ela grava o arquivo baixado no disco desta máquina. O campo
            # pergunta "modifica o seu ambiente?", e o disco de quem chama é
            # ambiente — a decisão inteira, e o que os outros três campos
            # compensam, está escrita em `usp_mcp/anotacoes.py`.
            "annotations": ESCREVE_NO_DEPOSITO,
        },
        {
            "name": _NOME_DIAGNOSTICO,
            "description": (
                "Diz se este servidor funciona no Moodle configurado, e o que "
                "ele alcança por lá: nome do site, versão do Moodle, quantas "
                "funções o seu token atinge e qual das ferramentas daqui está "
                "disponível. Diz também em que estado está a capacidade de "
                "escrita deste servidor — ligada ou desligada — e de quem é a "
                "decisão de mudá-lo. Use quando alguma ferramenta falhar sem motivo "
                "claro, ao configurar o servidor pela primeira vez, para "
                "responder 'isso funciona no Moodle da minha faculdade?', ou "
                "para 'o que dá para fazer por aqui?'. "
                "Custa UMA chamada ao Moodle e não lê disciplina nem entrega "
                "nenhuma. Exige token já configurado: para checar um site ANTES "
                "de ter token, o caminho é `scripts/compatibilidade.sh`, que não "
                "usa credencial."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_JA_ENTREGUEI,
            "description": (
                "Diz o que já foi entregue e o que ainda não foi nas tarefas de "
                "uma disciplina do e-Disciplinas (Moodle da USP), e distingue "
                "RASCUNHO SALVO de ENTREGA ENVIADA — que na tela do Moodle "
                "parecem a mesma coisa. Use para 'já entreguei o EP1?', 'o que "
                "falta entregar em PTC3314', 'minha entrega foi mesmo enviada', "
                "'entreguei dentro do prazo?'. Diz também a data do envio, o "
                "nome do arquivo enviado, se já foi corrigida e se houve "
                "prorrogação de prazo para você. Cobre só TAREFA: questionário "
                "não passa por aqui — para saber se já fez um questionário, se "
                "ainda dá e quantas tentativas sobram, use `questionarios`; "
                "para o que TEM prazo, inclusive questionário, `o_que_vence`. "
                "Prova presencial que o professor não lançou não existe em "
                "lugar nenhum. Não traz a nota. "
                "Custa uma chamada ao Moodle por entrega consultada, então "
                "pergunte por uma disciplina de cada vez."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam. "
                            "Aceita também o RÓTULO inteiro (PTC3314-2026), "
                            "que é o que distingue duas matrículas da mesma "
                            "sigla, e casa com pedaço do nome."
                        ),
                    },
                    "entrega": {
                        "type": "string",
                        "description": (
                            "Pedaço do nome da entrega — 'EP1', 'EC-2', "
                            "'relatório'. Opcional: sem ele vêm todas as "
                            "entregas da disciplina, e a saída diz se alguma "
                            "ficou de fora por teto de consultas."
                        ),
                    },
                },
                "required": ["disciplina"],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_NOTAS,
            "description": (
                "Mostra as suas notas no e-Disciplinas (Moodle da USP). Sem "
                "disciplina, dá a nota final de cada uma. Com disciplina, abre "
                "item a item: cada prova, lista e exercício com a nota e quanto "
                "ela pesa na final. Use para 'como estou de "
                "nota', 'quanto tirei no EP1', 'minhas notas em PTC3314', 'qual "
                "minha média'. Diz quando o professor lançou e ocultou a nota, "
                "em vez de fingir que não existe. Não diz de quanto era a nota: "
                "o e-Disciplinas não manda o máximo do item, só o valor tirado. "
                "Não traz o comentário escrito "
                "do professor, e não sabe de nota que ficou no papel e nunca "
                "foi lançada no sistema. Custa UMA chamada ao Moodle."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam. "
                            "Opcional: sem ela vem a nota final de todas as "
                            "disciplinas, que é a visão mais barata."
                        ),
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_AVISOS,
            "description": (
                "Mostra o que o professor e a turma escreveram nos fóruns de "
                "uma disciplina do e-Disciplinas (Moodle da USP): o mural de "
                "avisos primeiro, com o assunto, a data e o começo do texto de "
                "cada tópico. Use para 'o professor avisou alguma coisa?', 'tem "
                "recado novo em PTC3314', 'mudou alguma coisa sobre a prova', "
                "'o que foi dito no fórum'. É aqui que aparece o que o "
                "calendário não sabe — prova presencial adiada, sala trocada, "
                "lista que vai sair —, porque isso não vira prazo de atividade. "
                "Não diz QUEM escreveu: o fórum traz nome de outras pessoas e "
                "eles não saem daqui. Tópico longo sai cortado, e a resposta "
                "avisa quando cortou. Custa uma chamada ao Moodle para listar "
                "os fóruns e mais uma por fórum lido."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam. "
                            "Aceita também o RÓTULO inteiro (PTC3314-2026), "
                            "que é o que distingue duas matrículas da mesma "
                            "sigla, e casa com pedaço do nome."
                        ),
                    },
                },
                "required": ["disciplina"],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_MUDOU,
            "description": (
                "Diz o que mexeu numa disciplina do e-Disciplinas (Moodle da "
                "USP) nos últimos dias: arquivo novo ou trocado, tópico novo no "
                "fórum, atividade com configuração ou prazo alterado, nota "
                "lançada. Use para 'mudou alguma coisa em PTC3314?', 'tem "
                "novidade desde ontem', 'o professor postou algo novo essa "
                "semana', 'vale a pena eu abrir a página da disciplina'. É uma "
                "chamada barata, feita para ser o PRIMEIRO passo: ela diz QUE "
                "mudou e nunca O QUE mudou — para ver o arquivo use `material`, "
                "para ler o que foi escrito no fórum use `avisos`, e para o que "
                "tem prazo use `o_que_vence`. A janela é em dias e a resposta "
                "repete desde quando ela olhou."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam. "
                            "Aceita também o RÓTULO inteiro (PTC3314-2026), "
                            "que é o que distingue duas matrículas da mesma "
                            "sigla, e casa com pedaço do nome."
                        ),
                    },
                    "dias": {
                        "type": "integer",
                        "description": (
                            "Tamanho da janela, em dias para trás a partir de "
                            "agora. Padrão 7. Precisa ser pelo menos 1: com "
                            "zero a resposta seria 'nada mudou' por construção."
                        ),
                        "default": 7,
                    },
                },
                "required": ["disciplina"],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_DISCIPLINAS,
            "description": (
                "Lista as disciplinas em que você está matriculado no "
                "e-Disciplinas (Moodle da USP), com a SIGLA de cada uma — que é "
                "o que todas as outras ferramentas deste servidor pedem. Use "
                "para 'quais matérias eu tenho', 'que disciplinas estou "
                "cursando', 'qual a sigla de eletrônica', 'me lembra o que eu "
                "fiz em 2024'. As do semestre em andamento vêm primeiro e "
                "completas, com nome e período; as de semestres já encerrados "
                "saem como CONTAGEM por ano — nenhuma fica de fora da conta, e "
                "`todas` traz os rótulos e o período de cada uma, o que vale a "
                "pena quando a pergunta é sobre um ano antigo. 'Em andamento' "
                "sai das datas que o e-Disciplinas declara para o espaço da "
                "disciplina, e não da sua matrícula oficial: trancamento e "
                "cancelamento não chegam até aqui, e uma disciplina que o "
                "professor não datou cai num bloco à parte, sem período. A "
                "matrícula oficial é o JupiterWeb, que este servidor não "
                "alcança com dado pessoal. É a ferramenta mais barata daqui: a "
                "lista já é buscada para traduzir sigla, então a resposta "
                "costuma sair sem nenhuma chamada nova."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "todas": {
                        "type": "boolean",
                        "description": (
                            "Mostra também o nome e o período de cada "
                            "disciplina já encerrada, em vez de só a sigla "
                            "agrupada por ano. Padrão falso."
                        ),
                        "default": False,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_ATRASADAS,
            "description": (
                "Diz o que já venceu e o e-Disciplinas (Moodle da USP) NÃO "
                "registra como entregue — inclusive o rascunho que ficou salvo "
                "e nunca foi enviado, que na tela parece entrega feita. Use "
                "para 'tem alguma coisa atrasada?', 'perdi algum prazo?', 'o "
                "que eu devo?', 'esqueci de entregar alguma coisa em "
                "PTC3314?'. Sem disciplina, olha as do semestre em andamento; "
                "com disciplina, só ela, inclusive de semestre passado. "
                "IMPORTANTE ao relatar o resultado: esta ferramenta sabe o que "
                "está REGISTRADO no e-Disciplinas, e não o que a pessoa fez — "
                "entrega no papel, por e-mail ou que o professor não lançou no "
                "site não aparece como enviada, então não afirme que alguém "
                "não entregou; diga que não há registro e sugira confirmar. "
                "Entrega já corrigida sem envio registrado a própria resposta "
                "separa, e não conta como falta. Custa uma chamada ao Moodle "
                "para listar as entregas e mais uma por entrega vencida. Não vê "
                "QUESTIONÁRIO: para questionário que fechou sem você fazer, use "
                "`questionarios` com a disciplina. Para ver TODAS as entregas "
                "de uma disciplina, vencidas ou não, use `ja_entreguei`; para o "
                "que ainda vai vencer, `o_que_vence`."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam. "
                            "Opcional: sem ela, a consulta cobre as "
                            "disciplinas do semestre em andamento, com teto "
                            "declarado na resposta."
                        ),
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            "annotations": SO_LEITURA,
        },
        {
            "name": _NOME_QUESTIONARIOS,
            "description": (
                "Diz, para cada questionário de uma disciplina do e-Disciplinas "
                "(Moodle da USP), se você já FEZ — isto é, se tem tentativa "
                "finalizada —, se ainda está no prazo ou já fechou, e quantas "
                "tentativas você usou e ainda pode usar. Use para 'já fiz o "
                "teste 12?', 'ainda dá para fazer o questionário de PTC3314?', "
                "'quantas tentativas eu tenho?', 'perdi algum questionário?'. É "
                "o par de `ja_entreguei` para questionário: aquela cobre "
                "tarefa, esta cobre questionário, e nenhuma cobre a outra. Só "
                "LÊ: não abre, não responde e não finaliza questionário, e não "
                "há configuração que a faça fazer isso. Tentativa em andamento "
                "não conta como feita. Não traz a nota — ela sai em `notas`. "
                "Custa uma chamada ao Moodle para listar os questionários e "
                "mais uma por questionário consultado, com teto declarado na "
                "resposta; pergunte pelo nome (`questionario`) para gastar só "
                "duas."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "disciplina": {
                        "type": "string",
                        "description": (
                            "Sigla da disciplina como no e-Disciplinas, por "
                            "exemplo PTC3314. Espaço e caixa não importam. "
                            "Aceita também o RÓTULO inteiro (PTC3314-2026), "
                            "que é o que distingue duas matrículas da mesma "
                            "sigla, e casa com pedaço do nome."
                        ),
                    },
                    "questionario": {
                        "type": "string",
                        "description": (
                            "Pedaço do nome do questionário — 'Teste 12', "
                            "'semanal 3'. Opcional: sem ele vêm todos os "
                            "questionários da disciplina, e a saída diz se "
                            "algum ficou sem estado por teto de consultas."
                        ),
                    },
                },
                "required": ["disciplina"],
                "additionalProperties": False,
            },
            # Nenhum identificador de tentativa ou de questionário entra por
            # aqui, e é regra e não estilo: o único caminho natural para
            # descobrir um id de tentativa é a função que fabrica um, e ela
            # está no bloqueio permanente. Sem o id no vocabulário da
            # ferramenta, não existe pergunta cujo próximo passo encoste nela.
            "annotations": SO_LEITURA,
        },
        *_ferramentas_de_entrega(),
    ]


def chamar_ferramenta(
    nome: str, argumentos: dict, *, cliente=None, perguntar=None
) -> str:
    """Despacha para a ferramenta pedida pelo nome, ou levanta erro legível.

    Nome desconhecido é a fronteira do Invariante 6 (T44): não devolve lista
    vazia nem `None` silencioso — levanta `ErroMoodle` citando o nome pedido,
    porque "ferramenta não existe" e "ferramenta existe mas não achou nada"
    têm curas diferentes para quem lê o erro. Com `USP_MCP_ENTREGA` desligada é
    por aqui que `salvar_rascunho` e `entregar` também deixam de existir: elas
    não estão em `listar_ferramentas()`, e este `if` é a mesma porta.

    `perguntar` é a função que abre a pergunta de confirmação no cliente, e só
    as duas de escrita a usam. `None` — o default, e o que toda chamada de
    leitura passa — significa "não há como perguntar", que a saída distingue de
    "perguntei e disseram não".
    """
    conhecidas = tuple(f["name"] for f in listar_ferramentas())
    if nome not in conhecidas:
        raise ErroMoodle(
            f"Ferramenta desconhecida: {nome!r}. As ferramentas expostas por "
            f"este servidor são {', '.join(repr(n) for n in conhecidas)}."
        )

    if cliente is None:
        # O `.env` é a única casa do token (§8, gitignorado) — decisão de
        # 31/08/2026. `carregar_env` usa `setdefault`, então o bloco `env` de um
        # cliente MCP, se existir, ganha do arquivo. Chamado aqui e não no import
        # do módulo para que importar `server` continue sendo livre de efeito
        # colateral (é o que os testes de contrato fazem).
        carregar_env()

        # Credencial só é lida aqui, na hora de montar o cliente — nunca logada
        # nem exposta (Invariante 3).
        cliente = ClienteMoodle(
            token=os.environ.get("MOODLE_TOKEN", ""),
            url=os.environ.get("MOODLE_URL", _URL_PADRAO),
        )

    if nome in (_NOME_RASCUNHO, _NOME_ENTREGAR):
        # `asyncio.run` aqui, e não `async def chamar_ferramenta`: esta função é
        # a fronteira síncrona que a suíte inteira e os outros nove caminhos
        # usam, e torná-la corrotina obrigaria todos eles a mudar por causa de
        # duas ferramentas. Na produção quem chama as corrotinas de
        # `entrega.py` é `main()`, que já está num laço de eventos e as aguarda
        # direto — as duas portas terminam na MESMA corrotina.
        import asyncio

        if nome == _NOME_ENTREGAR:
            corrotina = entrega_mod.entregar(
                cliente,
                argumentos["disciplina"],
                argumentos["entrega"],
                confirmacao=argumentos.get("confirmacao"),
                perguntar=perguntar,
            )
        else:
            corrotina = entrega_mod.salvar_rascunho(
                cliente,
                argumentos["disciplina"],
                argumentos["entrega"],
                argumentos["texto"],
                confirmacao=argumentos.get("confirmacao"),
                perguntar=perguntar,
            )
        return asyncio.run(corrotina).texto

    if nome == _NOME_DIAGNOSTICO:
        return diagnostico(cliente)

    if nome == _NOME_ATRASADAS:
        return atrasadas(cliente, argumentos.get("disciplina")).texto

    if nome == _NOME_QUESTIONARIOS:
        return questionarios(
            cliente,
            argumentos["disciplina"],
            questionario=argumentos.get("questionario"),
        ).texto

    if nome == _NOME_DISCIPLINAS:
        return minhas_disciplinas(
            cliente, todas=bool(argumentos.get("todas"))
        ).texto

    if nome == _NOME_NOTAS:
        return notas(cliente, disciplina=argumentos.get("disciplina")).texto

    if nome == _NOME_AVISOS:
        return avisos(cliente, argumentos["disciplina"]).texto

    if nome == _NOME_MUDOU:
        return o_que_mudou(
            cliente,
            argumentos["disciplina"],
            dias=argumentos.get("dias", 7),
        ).texto

    if nome == _NOME_JA_ENTREGUEI:
        return ja_entreguei(
            cliente,
            argumentos["disciplina"],
            entrega=argumentos.get("entrega"),
        ).texto

    if nome == _NOME_MATERIAL:
        return material(
            cliente,
            argumentos["disciplina"],
            busca=argumentos.get("busca"),
        ).texto

    if nome == _NOME_ARQUIVO:
        return baixar_arquivo(
            cliente,
            argumentos["disciplina"],
            argumentos["nome"],
            todos=bool(argumentos.get("todos")),
            raiz=argumentos.get("raiz"),
        ).texto

    return o_que_vence(
        cliente,
        dias=argumentos.get("dias", 14),
        limite=argumentos.get("limite"),
    ).texto


def main() -> None:  # pragma: no cover — casca stdio; ver nota abaixo.
    """Adaptador stdio real. Import do SDK fica AQUI dentro, não no topo do
    módulo: os testes de contrato importam `usp_mcp.moodle.server` sem o SDK
    do MCP instalado, e um import de topo quebraria a coleta inteira da
    suíte por causa de uma dependência que as funções puras nem chegam a usar.

    **Tem teste, por dois caminhos que não se substituem.** T78-T81
    (`tests/moodle/test_server_stdio.py`) rodam isto em processo, substituindo só
    `run()`, e alcançam o que o processo esconde: o dicionário montado para
    `chamar_ferramenta` e a mensagem de SDK ausente. `tests/handshake/` sobe o
    processo de verdade e compara o que sai NO FIO com o declarado — foi lá que
    apareceu o schema mais pobre que o `inputSchema`. Antes de 31/08/2026 esta
    docstring dizia "sem teste automático de propósito", com a justificativa de
    que exercitá-lo testaria o SDK; as duas metades estavam erradas, e foi este
    buraco que escondeu um `main()` falando a API antiga com a suíte 99/99 verde.

    **E por um terceiro desde 10/09/2026.** E1-E4
    (`tests/moodle/test_erro_no_fio.py`) olham a MENSAGEM DE ERRO no fio, que
    nenhum dos dois alcançava — os dois exercitam o caminho feliz e o handshake,
    e a fronteira ficou muda por uma versão inteira do SDK sem ninguém ver.
    """
    # O `.env` é lido AQUI, antes de perguntar quais ferramentas existem. Desde
    # 15/09/2026 `listar_ferramentas()` depende do ambiente (`USP_MCP_ENTREGA`),
    # e a flag mora no mesmo arquivo que o token — sem esta linha, ligá-la no
    # `.env` produziria o pior defeito possível: a ferramenta chamável e fora do
    # `tools/list`, ou o contrário, conforme a ordem em que as coisas
    # acontecessem. `carregar_env` usa `setdefault`, então quem já está no
    # ambiente continua ganhando do arquivo.
    carregar_env()

    try:
        from mcp.server import MCPServer
        # `ToolError` existe no 2.0.0 e no 2.2.0, e entra no MESMO try: sem o
        # SDK, quem responde é a mensagem legível abaixo, não um traceback.
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError as exc:
        raise SystemExit(
            "O SDK do MCP (pacote `mcp`) não está instalado. Rode "
            "`.venv/bin/python -m pip install -r requirements.txt`. As funções "
            "`listar_ferramentas` e `chamar_ferramenta` funcionam sem ele."
        ) from exc

    from usp_mcp.adaptador import anotar

    # Indexado por NOME, e não desempacotado por posição. O desempacotamento
    # posicional já matou este servidor uma vez: em 14/09 `main()` abria três
    # descritores, `listar_ferramentas` passou a devolver quatro, e o processo
    # morreu antes do handshake com a suíte verde em tudo que não fosse o T78.
    # Um dicionário não tem essa forma de falhar — ferramenta nova só precisa
    # ser registrada, nunca contada.
    portas = {f["name"]: f for f in listar_ferramentas()}
    porta_material = portas[_NOME_MATERIAL]
    porta_arquivo = portas[_NOME_ARQUIVO]
    porta_diagnostico = portas[_NOME_DIAGNOSTICO]
    porta_ja_entreguei = portas[_NOME_JA_ENTREGUEI]
    porta_notas = portas[_NOME_NOTAS]
    porta_avisos = portas[_NOME_AVISOS]
    porta_mudou = portas[_NOME_MUDOU]
    porta_disciplinas = portas[_NOME_DISCIPLINAS]
    porta_atrasadas = portas[_NOME_ATRASADAS]
    porta_questionarios = portas[_NOME_QUESTIONARIOS]
    descritor = portas[_NOME_FERRAMENTA]
    # `instructions` viaja no `initialize`, uma vez por conexão, e é o canal de
    # INFORMAÇÃO que o `tools/list` não é: nada ali é chamável. É por ele que o
    # assistente fica sabendo que existe uma capacidade de escrita desligada,
    # sem que exista um item de lista para escolher, gastar e contornar — a
    # razão inteira está em `capacidades.py`. Lido depois do `carregar_env()`
    # acima, porque o texto depende da flag, que mora no mesmo arquivo do token.
    servidor = MCPServer(
        name="usp-mcp-moodle",
        version="1.1.0",
        instructions=capacidades.instrucoes(),
    )

    def _chamar(nome: str, argumentos: dict) -> str:
        """A tradução do erro do domínio para o canal que o modelo lê.

        Um ponto só para as três ferramentas: repetir o `try` em cada closure
        seria a terceira cópia da mesma regra, e a que alguém esquece de pôr na
        quarta ferramenta. `ToolError` é o canal que o SDK define para "falha
        prevista, a mensagem é para o modelo ler" — sem isto, o 2.2.0 classifica
        `ErroMoodle` como crash e entrega 32 bytes de `Error executing tool
        o_que_vence`, com a cura ("configure o MOODLE_TOKEN no .env") presa no
        stderr (medido em 10/09/2026).

        Só `ErroMoodle` é traduzido. `except Exception` aqui seria pior do que o
        silêncio: este é o entrypoint com credencial pessoal (Invariante 4), e o
        texto de uma exceção imprevista deste processo não tem por que viajar.
        """
        try:
            return chamar_ferramenta(nome, argumentos)
        except ErroMoodle as exc:
            raise ToolError(str(exc)) from exc

    def _registrar(porta: dict, funcao) -> None:
        """Um ponto só de registro, pelo mesmo motivo do `_chamar` acima.

        São dez chamadas a `servidor.tool()` neste `main()`, e cada campo novo
        do protocolo é a décima primeira chance de esquecer uma. `annotations`
        acabou de ser esse campo: com a chamada repetida dez vezes, registrar
        nove anotadas e uma muda não quebraria nada visível — a ferramenta
        continuaria funcionando, só chegaria ao cliente sem a dica de que é de
        leitura, que é a forma de defeito mais fácil de não ver.

        O bloco sai do descritor, e não é escrito aqui: a razão de cada campo
        está ao lado da declaração, e a segunda cópia é a que envelhece calada.
        Quem obriga descritor e fio a concordarem é o A6.

        `porta` é o descritor inteiro, sempre obtido do dicionário por NOME.
        Nada aqui é contado nem desempacotado por posição — foi assim que este
        `main()` morreu antes do handshake quando a quarta ferramenta entrou.
        """
        servidor.tool(
            name=porta["name"],
            description=porta["description"],
            annotations=para_o_sdk(porta),
        )(funcao)

    def _o_que_vence(dias=14, limite=None) -> str:
        # Assinatura explícita em vez de `**kwargs`: o SDK deriva o schema que
        # o modelo vê a partir dela, e um `**kwargs` produziria uma ferramenta
        # sem parâmetro nenhum. Mantida em sincronia com o `inputSchema` de
        # `listar_ferramentas` — `_auto_verificar` compara os dois.
        return _chamar(descritor["name"], {"dias": dias, "limite": limite})

    # O SDK lê a ASSINATURA, não o inputSchema declarado (§9, 31/08/2026). Sem
    # isto, "Padrão 14" e a explicação de `limite` não chegam ao modelo.
    anotar(_o_que_vence, descritor["inputSchema"], {"dias": int, "limite": int | None})
    _registrar(descritor, _o_que_vence)

    def _material(disciplina, busca=None) -> str:
        # `disciplina` SEM default de propósito: no SDK é a ausência de default
        # que torna o parâmetro obrigatório no fio, e o `inputSchema` a declara
        # em `required`. Com `=None` os dois divergiam e o modelo via uma
        # ferramenta que aceita ser chamada sem disciplina — H6 pegou.
        return _chamar(
            porta_material["name"], {"disciplina": disciplina, "busca": busca}
        )

    # Mesmo motivo: sem `anotar`, "Espaço e caixa não importam" e a explicação de
    # `busca` não chegam ao modelo — ele veria só {"title": "Disciplina"}.
    anotar(_material, porta_material["inputSchema"], {"disciplina": str, "busca": str | None})
    _registrar(porta_material, _material)

    def _baixar_arquivo(disciplina, nome, todos=False) -> str:
        # `disciplina` e `nome` SEM default: no SDK é a ausência de default que
        # torna o parâmetro obrigatório no fio, e o `inputSchema` os declara em
        # `required`. Com `=None` os dois divergiriam — foi assim que H6 pegou
        # `material` em 31/08.
        return _chamar(
            porta_arquivo["name"],
            {"disciplina": disciplina, "nome": nome, "todos": todos},
        )

    anotar(
        _baixar_arquivo,
        porta_arquivo["inputSchema"],
        {"disciplina": str, "nome": str, "todos": bool},
    )
    _registrar(porta_arquivo, _baixar_arquivo)

    def _diagnostico() -> str:
        # Sem parâmetro nenhum, e é de propósito: a pergunta é sobre o site
        # inteiro. `anotar` ainda é chamado para manter uma porta só de entrada
        # do schema declarado — com `properties` vazio ele só fixa o retorno.
        try:
            return chamar_ferramenta(porta_diagnostico["name"], {})
        except ErroMoodle as exc:
            raise ToolError(str(exc)) from exc

    anotar(_diagnostico, porta_diagnostico["inputSchema"], {})
    _registrar(porta_diagnostico, _diagnostico)

    def _ja_entreguei(disciplina, entrega=None) -> str:
        # `disciplina` SEM default: é a ausência de default que torna o
        # parâmetro obrigatório no fio, e o `inputSchema` a declara em
        # `required`. Com `=None` os dois divergiriam (H6, 31/08).
        return _chamar(
            porta_ja_entreguei["name"],
            {"disciplina": disciplina, "entrega": entrega},
        )

    anotar(
        _ja_entreguei,
        porta_ja_entreguei["inputSchema"],
        {"disciplina": str, "entrega": str | None},
    )
    _registrar(porta_ja_entreguei, _ja_entreguei)

    def _notas(disciplina=None) -> str:
        # `disciplina` COM default, ao contrário das outras três: aqui ela é
        # opcional de verdade, e o `inputSchema` a declara fora de `required`.
        # É a mesma regra de H6 lida ao contrário — o que não pode é divergir.
        return _chamar(porta_notas["name"], {"disciplina": disciplina})

    anotar(_notas, porta_notas["inputSchema"], {"disciplina": str | None})
    _registrar(porta_notas, _notas)

    def _avisos(disciplina) -> str:
        # `disciplina` SEM default, como em `material` e `ja_entreguei`: é a
        # ausência de default que torna o parâmetro obrigatório no fio, e o
        # `inputSchema` a declara em `required` (H6, 31/08). Aqui ela é mesmo
        # obrigatória — sem escopo, `courseids` vazio traria as 74 matrículas.
        return _chamar(porta_avisos["name"], {"disciplina": disciplina})

    anotar(_avisos, porta_avisos["inputSchema"], {"disciplina": str})
    _registrar(porta_avisos, _avisos)

    def _o_que_mudou(disciplina, dias=7) -> str:
        # `disciplina` SEM default e `dias` COM: é a assinatura que o SDK lê para
        # decidir o que é obrigatório no fio, e o `inputSchema` declara os dois
        # do mesmo jeito. O default 7 aparece nos dois lugares de propósito —
        # divergir é o que H6 pegou em 31/08.
        return _chamar(porta_mudou["name"], {"disciplina": disciplina, "dias": dias})

    anotar(
        _o_que_mudou, porta_mudou["inputSchema"], {"disciplina": str, "dias": int}
    )
    _registrar(porta_mudou, _o_que_mudou)

    def _disciplinas(todas=False) -> str:
        # `todas` COM default, como o `disciplina` de `notas`: o parâmetro é
        # opcional de verdade, e o `inputSchema` o declara fora de `required`.
        # A pergunta comum ("quais matérias eu tenho") não passa parâmetro
        # nenhum, e é por isso que ela não pode ser obrigatória.
        return _chamar(porta_disciplinas["name"], {"todas": todas})

    anotar(_disciplinas, porta_disciplinas["inputSchema"], {"todas": bool})
    _registrar(porta_disciplinas, _disciplinas)

    def _atrasadas(disciplina=None) -> str:
        # `disciplina` COM default, como em `notas`: a pergunta comum ("tem
        # alguma coisa atrasada?") não tem escopo, e obrigá-lo faria o modelo
        # inventar uma disciplina para poder chamar.
        return _chamar(porta_atrasadas["name"], {"disciplina": disciplina})

    anotar(_atrasadas, porta_atrasadas["inputSchema"], {"disciplina": str | None})
    _registrar(porta_atrasadas, _atrasadas)

    def _questionarios(disciplina, questionario=None) -> str:
        # `disciplina` SEM default e `questionario` COM, como em `ja_entreguei`:
        # é a assinatura que o SDK lê para decidir o que é obrigatório no fio,
        # e o `inputSchema` declara os dois do mesmo jeito (H6, 31/08).
        return _chamar(
            porta_questionarios["name"],
            {"disciplina": disciplina, "questionario": questionario},
        )

    anotar(
        _questionarios,
        porta_questionarios["inputSchema"],
        {"disciplina": str, "questionario": str | None},
    )
    _registrar(porta_questionarios, _questionarios)

    # ------------------------------------------------- as duas de escrita
    #
    # Registradas só quando existem: `portas` vem de `listar_ferramentas()`, que
    # devolve dez sem `USP_MCP_ENTREGA=1`. Indexar por nome sem checar mataria o
    # servidor antes do handshake com a flag desligada — que é exatamente a
    # forma de falha que o desempacotamento posicional já produziu uma vez.
    if _NOME_ENTREGAR in portas:
        from mcp.server.mcpserver import Context

        from pydantic import BaseModel, Field as CampoPydantic

        class _Confirmacao(BaseModel):
            """O esquema de um campo só que a pergunta usa.

            Um booleano, e não texto livre: o protocolo só aceita tipo
            primitivo aqui, e a pergunta que importa tem duas respostas.
            """

            confirmo: bool = CampoPydantic(
                description="Confirma esta escrita no e-Disciplinas?"
            )

        async def _perguntar(ctx, mensagem: str) -> bool:
            """`Context.elicit`, e o que fazer quando ele não existe do outro lado.

            Cliente que não suporta elicitação levanta daqui uma
            `ElicitacaoIndisponivel`, que o fluxo trata como "não pude
            perguntar" — nunca como "disseram não". Os dois casos saem escritos
            com palavras diferentes na resposta, e é essa distinção que impede
            um cliente sem elicitação de ver toda entrega cancelada sem motivo.

            `except Exception` aqui é deliberado e estreito no efeito: a lista
            de erros que um cliente pode devolver ao recusar uma capacidade não
            é fechada, e o pior caso desta captura é perguntar menos — nunca
            escrever mais.
            """
            if ctx is None:
                raise entrega_mod.ElicitacaoIndisponivel
            try:
                resultado = await ctx.elicit(mensagem, _Confirmacao)
            except Exception as exc:  # noqa: BLE001 — ver docstring
                raise entrega_mod.ElicitacaoIndisponivel from exc
            if resultado.action != "accept":
                return False
            return bool(getattr(resultado.data, "confirmo", False))

        def _cliente_com_credencial():
            """O mesmo cliente que `chamar_ferramenta` monta quando não recebe um.

            Montado aqui porque estas duas não passam por `chamar_ferramenta`:
            elas precisam aguardar a pergunta, e `chamar_ferramenta` é síncrona.
            """
            carregar_env()
            return ClienteMoodle(
                token=os.environ.get("MOODLE_TOKEN", ""),
                url=os.environ.get("MOODLE_URL", _URL_PADRAO),
            )

        porta_entregar = portas[_NOME_ENTREGAR]
        porta_rascunho = portas[_NOME_RASCUNHO]

        async def _entregar(disciplina, entrega, confirmacao=None, ctx=None) -> str:
            try:
                resposta = await entrega_mod.entregar(
                    _cliente_com_credencial(),
                    disciplina,
                    entrega,
                    confirmacao=confirmacao,
                    perguntar=lambda mensagem: _perguntar(ctx, mensagem),
                )
            except ErroMoodle as exc:
                raise ToolError(str(exc)) from exc
            return resposta.texto

        anotar(
            _entregar,
            porta_entregar["inputSchema"],
            {"disciplina": str, "entrega": str, "confirmacao": str | None},
        )
        # `anotar` substitui `__annotations__` inteiro, e o `ctx` não é
        # parâmetro do modelo: o SDK o injeta por tipo e o deixa fora do schema.
        # Reposto aqui, depois, para que as duas coisas valham ao mesmo tempo.
        _entregar.__annotations__["ctx"] = Context
        _registrar(porta_entregar, _entregar)

        async def _salvar_rascunho(
            disciplina, entrega, texto, confirmacao=None, ctx=None
        ) -> str:
            try:
                resposta = await entrega_mod.salvar_rascunho(
                    _cliente_com_credencial(),
                    disciplina,
                    entrega,
                    texto,
                    confirmacao=confirmacao,
                    perguntar=lambda mensagem: _perguntar(ctx, mensagem),
                )
            except ErroMoodle as exc:
                raise ToolError(str(exc)) from exc
            return resposta.texto

        anotar(
            _salvar_rascunho,
            porta_rascunho["inputSchema"],
            {
                "disciplina": str,
                "entrega": str,
                "texto": str,
                "confirmacao": str | None,
            },
        )
        _salvar_rascunho.__annotations__["ctx"] = Context
        _registrar(porta_rascunho, _salvar_rascunho)

    servidor.run(transport="stdio")


def _auto_verificar() -> int:  # pragma: no cover — utilitário de linha de comando
    """`python -m usp_mcp.moodle.server --auto-verificar`: o que dá para
    checar sem tocar a rede da USP nem gastar uma chamada da conta.

    Nasceu porque `main()` não tinha teste. Desde 31/08/2026 tem
    (`tests/handshake/`), e isto continua útil por outro motivo: roda em um
    comando, imprime o diagnóstico de configuração (`.env`, token, SDK) que um
    teste não imprime, e responde "por que o servidor não sobe aqui" mais rápido
    do que uma suíte.
    """
    from .. import env as _env

    print("ferramentas expostas :", [f["name"] for f in listar_ferramentas()])

    arquivo = _env.achar_env()
    print(".env encontrado      :", arquivo or "NÃO — copie .env.example")
    _env.carregar_env()
    # Forma, nunca valor (Invariante 3).
    token = os.environ.get("MOODLE_TOKEN") or ""
    print(
        "MOODLE_TOKEN         :",
        f"presente, {len(token)} chars" if token else "AUSENTE",
    )
    print("MOODLE_URL           :", os.environ.get("MOODLE_URL", _URL_PADRAO))

    try:
        from mcp.server import MCPServer  # noqa: F401
    except ImportError:
        print("SDK do MCP           : AUSENTE — pip install -r requirements.txt")
        return 1
    print("SDK do MCP           : presente")

    # O schema que o modelo vê tem de casar com a assinatura que o adaptador
    # registra. Isto checava a PRIMEIRA ferramenta e imprimia "OK" como se
    # falasse pelas duas — meia checagem com cara de checagem inteira, que é o
    # Invariante 7 quebrado dentro da própria ferramenta de verificação.
    # Corrigido em 31/08; a cobertura de verdade está em T79.
    import inspect

    from mcp.server import MCPServer as _M

    servidor = _M(name="verificacao", version="0.0.0")

    @servidor.tool(name="o_que_vence", description="verificação")
    def _sonda_vence(dias: int = 14, limite: int | None = None) -> str:
        return ""

    @servidor.tool(name="material", description="verificação")
    def _sonda_material(disciplina: str, busca: str | None = None) -> str:
        return ""

    @servidor.tool(name="baixar_arquivo", description="verificação")
    def _sonda_arquivo(disciplina: str, nome: str, todos: bool = False) -> str:
        return ""

    @servidor.tool(name="diagnostico", description="verificação")
    def _sonda_diagnostico() -> str:
        return ""

    @servidor.tool(name="ja_entreguei", description="verificação")
    def _sonda_ja_entreguei(disciplina: str, entrega: str | None = None) -> str:
        return ""

    @servidor.tool(name="notas", description="verificação")
    def _sonda_notas(disciplina: str | None = None) -> str:
        return ""

    @servidor.tool(name="avisos", description="verificação")
    def _sonda_avisos(disciplina: str) -> str:
        return ""

    @servidor.tool(name="o_que_mudou", description="verificação")
    def _sonda_mudou(disciplina: str, dias: int = 7) -> str:
        return ""

    @servidor.tool(name="disciplinas", description="verificação")
    def _sonda_disciplinas(todas: bool = False) -> str:
        return ""

    @servidor.tool(name="atrasadas", description="verificação")
    def _sonda_atrasadas(disciplina: str | None = None) -> str:
        return ""

    @servidor.tool(name="questionarios", description="verificação")
    def _sonda_questionarios(disciplina: str, questionario: str | None = None) -> str:
        return ""

    # As duas de escrita só entram na conta quando existem. `listar_ferramentas`
    # não as devolve com a flag desligada, e o laço abaixo só cobra sonda do que
    # ela devolveu — registrá-las sempre criaria duas ferramentas de verificação
    # que o servidor de verdade não tem.
    @servidor.tool(name="entregar", description="verificação")
    def _sonda_entregar(disciplina: str, entrega: str, confirmacao: str | None = None) -> str:
        return ""

    @servidor.tool(name="salvar_rascunho", description="verificação")
    def _sonda_rascunho(
        disciplina: str, entrega: str, texto: str, confirmacao: str | None = None
    ) -> str:
        return ""

    sondas = {
        "o_que_vence": _sonda_vence,
        "material": _sonda_material,
        "baixar_arquivo": _sonda_arquivo,
        "diagnostico": _sonda_diagnostico,
        "ja_entreguei": _sonda_ja_entreguei,
        "notas": _sonda_notas,
        "avisos": _sonda_avisos,
        "o_que_mudou": _sonda_mudou,
        "disciplinas": _sonda_disciplinas,
        "atrasadas": _sonda_atrasadas,
        "questionarios": _sonda_questionarios,
        "entregar": _sonda_entregar,
        "salvar_rascunho": _sonda_rascunho,
    }
    divergiu = False
    for ferramenta in listar_ferramentas():
        nome = ferramenta["name"]
        declarados = set(ferramenta["inputSchema"]["properties"])
        sonda = sondas.get(nome)
        if sonda is None:
            print(f"schema x assinatura  : {nome}: SEM SONDA — acrescente uma aqui")
            divergiu = True
            continue
        reais = set(inspect.signature(sonda).parameters)
        estado = "OK" if declarados == reais else f"DIVERGEM {declarados ^ reais}"
        print(f"schema x assinatura  : {nome}: {estado}")
        divergiu = divergiu or declarados != reais
    if divergiu:
        return 1

    print()
    print("Nada acima tocou a rede da USP. A suíte já cobre a fronteira MCP")
    print("offline (T78-T81); o que falta é a rede — plugar e perguntar.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    if "--auto-verificar" in sys.argv:
        raise SystemExit(_auto_verificar())
    main()
