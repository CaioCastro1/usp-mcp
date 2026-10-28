"""Cliente do bean público do JupiterWeb.

Três coisas que este módulo existe para garantir, e que nenhuma outra camada
garante:

**O corpo da requisição é contrato.** O DWR responde HTTP 200 para corpo
malformado. Um erro de serialização não vira falha — vira campo vazio, com cara
de resposta. Por isso a montagem do corpo é testada byte a byte contra o §4.2
do recon.

**Nada de credencial.** O `ControlePublicoDWR` é público e stateless: sem
cookie, sem handshake, sem sessão (verificado na Fase 1 com `scriptSessionId`
inventado). O §6 do SPEC1 põe o Jupiter num servidor hospedado justamente por
isso. Este cliente não lê variável de ambiente com segredo e não manda cabeçalho
de identificação — e há teste de política que falha se alguém acrescentar.

**Gentileza com a USP** (Invariante 5). Cache com TTL colado na taxa de mudança
do dado — ementa muda por semestre, não por pergunta — e uma requisição por vez.
O rate limit do Jupiter continua sem evidência: 26 requisições sem 429 na Fase 1
**não provam** que não exista.
"""
from __future__ import annotations

import http.client
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote

from usp_mcp import AGENTE
from usp_mcp.jupiter import dwr, politica
from usp_mcp.jupiter.erros import ConsultaNegada, JupiterIndisponivel, RespostaInvalida
from usp_mcp.jupiter.politica import CONSULTAS_PERMITIDAS

__all__ = ["ClienteJupiter", "transporte_http", "transporte_get_http", "ConsultaNegada",
           "CONSULTAS_PERMITIDAS", "URL_BASE", "URL_PAGINA", "AGENTE", "TTL_PADRAO", "CODCG_POLI"]

URL_BASE = "https://uspdigital.usp.br/jupiterweb/dwr/call/plaincall"

# A segunda superfície (§9, 14/09): a página de requisitos por curso, que é a
# única que cita os currículos onde a exigência de fato mora.
URL_PAGINA = "https://uspdigital.usp.br/jupiterweb"

# A única unidade que tem módulo (varredura das 47, 26/10). Fixa, e não
# parâmetro: parâmetro que só aceita um valor é superfície à toa.
CODCG_POLI = "3"

# O User-Agent vem do pacote (`usp_mcp/__init__.py`), com a versão perguntada
# ao metadado em vez de repetida: as duas cópias à mão ficaram em `0.1` com o
# pacote em 1.0.0. Segue no `__all__` daqui porque é onde os testes o leem.

# Um semestre. O dado desta fatia é ementa, crédito e pré-requisito — muda entre
# semestres, e nunca por causa de uma pergunta repetida.
TTL_PADRAO = 60 * 60 * 24 * 120

_TEMPO_LIMITE = 20

# O que pode dar errado no fio, e por que são DUAS famílias e não uma.
#
# `urllib.error.URLError` e `TimeoutError` são subclasses de `OSError`, então um
# `except OSError` cobre timeout, conexão recusada e DNS. O que ele **não**
# cobre é `http.client.HTTPException`: `IncompleteRead` (o servidor fecha antes
# de completar o `Content-Length`) e `BadStatusLine` (a primeira linha não é uma
# linha de status) herdam só de `HTTPException`. Medido contra servidor local:
# nos dois casos a exceção subia crua até a fronteira MCP, onde o SDK a
# classifica como crash e o modelo recebe a genérica de 32 bytes.
#
# `RemoteDisconnected` é as duas coisas ao mesmo tempo (`ConnectionResetError` e
# `BadStatusLine`), e é a que mostra que listar `URLError` e `TimeoutError` à mão
# não bastava nem dentro de `OSError`.
_FALHAS_DE_TRANSPORTE = (OSError, http.client.HTTPException)

# Limite do detalhe técnico que entra na mensagem. `BadStatusLine` carrega a
# linha inteira que o servidor mandou, e ela pode ter dezenas de kB — a mensagem
# é para ser lida, não para transportar o fio de volta.
_TETO_DETALHE = 120


# --- o marcador da página de requisitos -------------------------------------
#
# O caminho do DWR valida FORMA antes de acreditar no corpo: sem `//#DWR-END#`
# o envelope não é envelope. O caminho HTML validava só o status, e HTTP 200 não
# prova nada aqui — página de manutenção, portal de login e corpo vazio vêm todos
# com 200. Sem marcador, o recorte não achava `Curso:`, devolvia lista vazia, e a
# ferramenta anunciava "nenhum currículo com exigência", que é a conclusão mais
# cara de errar nesta fatia. Com o TTL de um semestre, ela ficava.
#
# O marcador é a CONJUNÇÃO de dois, e cada metade responde uma pergunta:
# o título diz "cheguei ao JupiterWeb"; a palavra diz "e esta é a página de
# requisitos". Medido nas nove páginas HTML capturadas do JupiterWeb:
#
#   - as três capturas de `listarCursosRequisitos` trazem as duas — inclusive a
#     de zero currículo, cuja única ocorrência está na frase que ela exibe
#     ("Disciplina não tem requisitos");
#   - a sigla não serve de marcador: a de zero currículo não contém a própria;
#   - `Curso:` não serve: é justamente o que separa "tem currículo" de "não
#     tem", e exigi-lo transformaria a resposta legítima de zero currículo em
#     erro — este mesmo defeito, virado do avesso;
#   - o título sozinho não serve: as seis outras páginas capturadas o têm;
#   - a palavra sozinha é evidência fraca de ter chegado ao JupiterWeb.
#
# Limite declarado: das seis outras páginas, a conjunção rejeita cinco. A sexta
# é a ficha da disciplina, que passa só porque carrega um LINK para esta página.
# Este caminho nunca pede aquela URL, então a confusão não é alcançável — mas
# ela existe, e está escrita em vez de escondida.
_TITULO_JUPITER = re.compile(r"<title>\s*jupiterweb\s*</title>", re.I)
_PALAVRA_REQUISITO = re.compile(r"equisito", re.I)


def _e_a_pagina_de_requisitos(bruto: bytes) -> bool:
    """Se o corpo tem a forma da página de requisitos. Não lê conteúdo."""
    texto = bruto.decode("iso-8859-1", errors="replace") if isinstance(bruto, bytes) else bruto
    return bool(_TITULO_JUPITER.search(texto) and _PALAVRA_REQUISITO.search(texto))


# A lista de cursos (fatia de módulos, 26/10). Mesma lógica do marcador acima:
# o título diz "cheguei ao JupiterWeb", e o link para a grade diz "e esta é uma
# lista de cursos" — toda linha da tabela o tem, e nenhuma página de manutenção.
_LINK_GRADE = re.compile(r"listarGradeCurricular\?")


def _e_a_lista_de_cursos(bruto: bytes) -> bool:
    """Se o corpo tem a forma da lista de cursos. Não lê conteúdo."""
    texto = bruto.decode("iso-8859-1", errors="replace")
    return bool(_TITULO_JUPITER.search(texto) and _LINK_GRADE.search(texto))


def _detalhe(erro: BaseException) -> str:
    """Classe e mensagem da exceção, cortadas no teto."""
    texto = str(erro).strip()
    if len(texto) > _TETO_DETALHE:
        texto = texto[:_TETO_DETALHE] + "…"
    return f"{type(erro).__name__}: {texto}" if texto else type(erro).__name__


def _indisponivel(erro: BaseException) -> JupiterIndisponivel:
    """Traduz a falha de transporte, distinguindo os DOIS casos.

    "Não respondeu" é diagnóstico errado para um servidor que respondeu e
    respondeu mal: quem lê decide coisas diferentes nos dois. Só o caso de fato
    mudo carrega a observação sobre ambiente sem acesso à rede da USP.
    """
    if isinstance(erro, http.client.HTTPException) and not isinstance(erro, OSError):
        return JupiterIndisponivel(
            f"a resposta do JupiterWeb chegou quebrada e não dá para ler "
            f"({_detalhe(erro)}). O servidor respondeu, mas o que veio no fio não "
            "é uma resposta HTTP íntegra: corpo cortado antes do fim, ou primeira "
            "linha que não é status. Isto é transporte, não conteúdo — não "
            "conclua nada sobre a disciplina nem sobre a sigla pedida."
        )
    return JupiterIndisponivel(
        f"o JupiterWeb não respondeu ({_detalhe(erro)}). Num ambiente sem acesso "
        "à rede da USP (um sandbox em nuvem, por exemplo) a chamada não tem como "
        "sair."
    )


def transporte_http(url: str, corpo: str, cabecalhos: dict[str, str]) -> tuple[int, str]:
    """Transporte real. Injetável: nos testes entra um dublê que grava a chamada."""
    pedido = urllib.request.Request(
        url, data=corpo.encode("utf-8"), headers=cabecalhos, method="POST"
    )
    try:
        with urllib.request.urlopen(pedido, timeout=_TEMPO_LIMITE) as resposta:
            bruto = resposta.read()
            charset = resposta.headers.get_content_charset() or "ISO-8859-1"
            return resposta.status, bruto.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:  # 4xx/5xx ainda têm corpo
        try:
            corpo_do_erro = e.read()
        except _FALHAS_DE_TRANSPORTE as falha:
            # O corpo do 4xx/5xx também pode vir cortado, e aí a leitura levanta
            # de dentro do `except`. Sem isto, a exceção da leitura escapa por
            # cima da tradução que a linha de baixo faz.
            raise _indisponivel(falha) from falha
        return e.code, corpo_do_erro.decode("ISO-8859-1", errors="replace")
    except _FALHAS_DE_TRANSPORTE as e:
        raise _indisponivel(e) from e


def transporte_get_http(url: str, cabecalhos: dict[str, str]) -> tuple[int, bytes]:
    """GET da página pública. Devolve BYTES de propósito.

    O JupiterWeb serve ISO-8859-1 e nem sempre anuncia. Decodificar aqui, com o
    palpite errado, entrega "CÃ¡lculo" para o recorte — erro que atravessa a
    suíte inteira sem derrubar nada que conte linhas. Quem sabe o charset é
    quem conhece a página.
    """
    pedido = urllib.request.Request(url, headers=cabecalhos, method="GET")
    try:
        with urllib.request.urlopen(pedido, timeout=_TEMPO_LIMITE) as resposta:
            return resposta.status, resposta.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except _FALHAS_DE_TRANSPORTE as falha:
            raise _indisponivel(falha) from falha
    except _FALHAS_DE_TRANSPORTE as e:
        raise _indisponivel(e) from e


class ClienteJupiter:
    """Chamador do `ControlePublicoDWR`, com política, cache e serialização.

    `transporte` recebe `(url, corpo, cabecalhos)` e devolve `(status, texto)`.
    `relogio` é injetável para que o teste de TTL verifique a REGRA, não o valor
    da constante.
    """

    def __init__(self, transporte, *, transporte_get=transporte_get_http,
                 agente: str = AGENTE, relogio=time.monotonic,
                 ttl: int = TTL_PADRAO, permitir_escrita: bool = False):
        self._transporte = transporte
        self._transporte_get = transporte_get
        self._agente = agente
        self._relogio = relogio
        self._ttl = ttl
        self._permitir_escrita = permitir_escrita
        self._cache: dict[tuple, tuple[float, object]] = {}
        # Uma requisição por vez. Não é thread-safety por acaso: é o Invariante 5.
        self._porta = threading.Lock()

    def _chamar(self, *, metodo: str, consulta: str, params: dict):
        decisao = politica.decidir(metodo, consulta, self._permitir_escrita)
        if not decisao.permitida:
            raise ConsultaNegada(decisao.motivo)

        chave = (metodo, consulta, tuple(sorted(params.items())))
        with self._porta:
            guardado = self._cache.get(chave)
            if guardado is not None and self._relogio() - guardado[0] < self._ttl:
                return guardado[1]

            corpo = dwr.serializar(metodo=metodo, consulta=consulta, params=params)
            status, texto = self._transporte(
                f"{URL_BASE}/ControlePublicoDWR.{metodo}.dwr",
                corpo,
                {"Content-Type": "text/plain", "User-Agent": self._agente},
            )
            if status != 200:
                raise RespostaInvalida(
                    f"o JupiterWeb respondeu HTTP {status}. Atenção: o erro NORMAL "
                    "dele vem com 200 e mensagem no corpo, então um status diferente "
                    "aqui é outra coisa — indisponibilidade ou rota errada."
                )

            valor = dwr.decodificar(texto)
            self._cache[chave] = (self._relogio(), valor)
            return valor

    def obter_disciplina(self, sigla: str) -> dict:
        """Ficha da disciplina. `verdis=0` é o que a aplicação oficial manda; o
        retorno vem com a versão corrente (§8 do recon: o significado exato de
        `verdis` não foi verificado, e não se assume)."""
        return self._chamar(
            metodo="obter",
            consulta="pubObterDisciplina",
            params={"coddis": sigla, "verdis": 0},
        )

    # --- a segunda superfície: páginas HTML do mesmo host -------------------

    def _pagina(self, *, caminho: str, url: str, chave: tuple, e_a_certa, erro_forma: str,
                erro_status: str) -> bytes:
        """GET de página pública: allowlist de CAMINHO, cache, status e forma.

        A forma é validada ANTES de gravar no cache: com TTL de semestre,
        guardar uma página de manutenção responde errado pela vida do processo.
        """
        decisao = politica.decidir_caminho(caminho)
        if not decisao.permitida:
            raise ConsultaNegada(decisao.motivo)

        with self._porta:
            guardado = self._cache.get(chave)
            if guardado is not None and self._relogio() - guardado[0] < self._ttl:
                return guardado[1]

            status, bruto = self._transporte_get(url, {"User-Agent": self._agente})
            if status != 200:
                raise RespostaInvalida(erro_status.format(status=status))
            if not e_a_certa(bruto):
                raise RespostaInvalida(erro_forma)
            self._cache[chave] = (self._relogio(), bruto)
            return bruto

    def obter_requisitos(self, sigla: str) -> bytes:
        """A página crua de requisitos da disciplina, em bytes.

        Passa pela allowlist de CAMINHO, não pela de consulta: é outra
        superfície, e o filtro do DWR não alcança um GET.
        """
        # `quote` como em `dwr.serializar`, e não f-string: uma sigla com `#`
        # cortaria a URL no fragmento e a requisição sairia com meia sigla —
        # resposta de outra disciplina, com cara de certa.
        return self._pagina(
            caminho="listarCursosRequisitos",
            url=f"{URL_PAGINA}/listarCursosRequisitos?coddis={quote(sigla, safe='')}",
            chave=("pagina", "listarCursosRequisitos", sigla),
            e_a_certa=_e_a_pagina_de_requisitos,
            erro_status=(
                "o JupiterWeb respondeu HTTP {status} para a página de "
                "requisitos. Diferente do DWR, aqui um status fora de 200 é "
                "mesmo falha — a página de erro dele não vem com 200."
            ),
            erro_forma=(
                "o JupiterWeb respondeu HTTP 200, mas o que veio não é a "
                f"página de requisitos de {sigla}: faltam nela as marcas que "
                "toda resposta dessa página tem. É o que acontece com página "
                "de manutenção, tela de login e corpo vazio, que também vêm "
                "com 200. NÃO leia isto como 'a disciplina não exige nada' — "
                "nada foi lido sobre as exigências dela."
            ),
        )

    def obter_lista_cursos_poli(self, tipo: str) -> bytes:
        """A lista de cursos da Poli: `N` (ingresso, e a seção de percursos) ou
        `V` ("Cursos e Habilitações Anteriores", onde estão os 47 módulos).

        `tipo` entra na URL, então é validado contra os dois valores antes de
        qualquer coisa: um valor livre aqui é parâmetro de URL arbitrário.
        """
        if tipo not in ("N", "V"):
            raise ConsultaNegada(
                f"tipo {tipo!r} não é um dos dois da lista de cursos ('N' ou 'V')."
            )
        return self._pagina(
            caminho="jupCursoLista",
            url=f"{URL_PAGINA}/jupCursoLista?codcg={CODCG_POLI}&tipo={tipo}",
            chave=("pagina", "jupCursoLista", tipo),
            e_a_certa=_e_a_lista_de_cursos,
            erro_status=(
                "o JupiterWeb respondeu HTTP {status} para a lista de cursos da "
                "Poli. A página de erro dele não vem com 200, então isto é falha."
            ),
            erro_forma=(
                "o JupiterWeb respondeu HTTP 200, mas o que veio não é a lista de "
                "cursos da Poli: não há nela nenhum link de grade curricular. É o "
                "que acontece com página de manutenção e tela de login. NÃO leia "
                "isto como 'a Poli não tem módulo' — nada foi lido."
            ),
        )

    def grade_curricular(self, codcur: str, codhab: str, tipo: str) -> list:
        """As disciplinas de um currículo. `tipo` é o do link da lista de cursos:
        o mesmo par devolve VAZIO com o `tipo` errado (§9, 26/10)."""
        return self._chamar(
            metodo="listar",
            consulta="pubGradeCurricular",
            params={"codcur": codcur, "codhab": codhab, "tipo": tipo},
        )

    def info_curriculo(self, codcur: str, codhab: str, tipo: str) -> dict:
        """A ficha do currículo: carga exigida e regra em texto. A USP devolve
        objeto vazio (ou nada) para currículo sem ficha publicada."""
        valor = self._chamar(
            metodo="obter",
            consulta="pubObterInfoCursoWeb",
            params={"codcur": codcur, "codhab": codhab, "tipo": tipo},
        )
        return valor if isinstance(valor, dict) else {}

    def listar_colegiados(self) -> list:
        """As 47 unidades. Existe para NÃO adivinhar: `codclg` como prefixo de
        `codcur` é ambíguo (§9, 14/09), e só a lista real decide candidato."""
        return self._chamar(
            metodo="listar",
            consulta="pubListarColegiado",
            params={"pfxdisval": "XXX", "codcg": 0},
        )

    def listar_cursos_entrada(self, codclg: str) -> list:
        """Os cursos de ingresso de uma unidade."""
        return self._chamar(
            metodo="listar",
            consulta="pubListarCursoEntrada",
            params={"codclg": codclg},
        )

    def cursos_de_ingresso(self, codcur: str) -> set[str]:
        """Os `codcur` de ingresso das unidades que PODEM ser a deste curso.

        Não decide qual unidade é — isso seria chute, porque oito dos 47
        `codclg` são prefixo de outro. Decide **pertencimento**, que é tudo o
        que a marca precisa: se o código aparece na lista de ingresso de algum
        candidato, ele é curso de ingresso.
        """
        candidatos = [
            c["codclg"] for c in self.listar_colegiados()
            if codcur.startswith(c["codclg"])
        ]
        de_ingresso: set[str] = set()
        for codclg in candidatos:
            de_ingresso.update(c["codcur"] for c in self.listar_cursos_entrada(codclg))
        return de_ingresso
