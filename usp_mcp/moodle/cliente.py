"""Camada 2 — o cliente: transporte, política na fronteira, e erro legível.

A política (Invariante 2) é aplicada AQUI, dentro de `chamar`, de propósito: se
a checagem morasse só na camada de ferramenta (o wrapper MCP), qualquer código
novo que instanciasse `ClienteMoodle` direto — um script de depuração, uma
segunda ferramenta — contornaria a allowlist sem perceber. O cliente é o único
lugar por onde toda chamada ao web service passa, então é o único lugar onde a
política pode ser garantida e não apenas convencionada.

Este módulo é deliberadamente incapaz de iterar sobre funções do Moodle: não
existe `chamar_varias`, `sweep`, nem nada parecido. Um laço sobre as 447
funções habilitadas neste token passaria por `mod_quiz_start_attempt` e
`mod_assign_submit_for_grading` com a credencial do dono (Regra de Ouro, §3.1)
— a defesa mais confiável contra isso é a ausência do método, não uma checagem
em tempo de execução que alguém pode esquecer de manter.
"""
from __future__ import annotations

import functools
import http.client
import importlib.resources
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import politica
from .erros import (
    CertificadoNaoVerificado,
    ErroMoodle,
    FuncaoBloqueada,
    MoodleIndisponivel,
    RespostaIlegivel,
    TokenInvalido,
)

_URL_SUFIXO_WEBSERVICE = "/webservice/rest/server.php"

# As três chaves do envelope REST que `_requisitar` preenche sozinho. Nenhuma
# pode vir em `params`: a política decide sobre `funcao`, e um `wsfunction`
# vindo de fora venceria essa decisão no fio (`**params` era o último a
# escrever no dicionário). Medido em 14/09/2026 com transporte falso: a política
# aprovou `core_course_get_contents` e o fio recebeu
# `mod_assign_submit_for_grading`. Não é alcançável pelos inputs MCP de hoje —
# os call sites usam chaves literais —, e é exatamente por isso que a recusa
# fica aqui e não em cada ferramenta: o dia em que uma repassar `**kwargs` do
# modelo não pode ser o dia em que isto passa a valer.
_CHAVES_RESERVADAS = frozenset({"wstoken", "wsfunction", "moodlewsrestformat"})

# O que o transporte pode levantar sem que seja culpa do JSON: `OSError` cobre
# timeout, recusa de conexão e `urllib.error.URLError`; `http.client.HTTPException`
# cobre `IncompleteRead` (resposta truncada) e `BadStatusLine` (status line
# inválida), que NÃO são `OSError` e escapavam cruas até 16/09/2026 — chegavam
# ao modelo como "Error executing tool X", de 32 bytes.
_FALHAS_DE_TRANSPORTE = (OSError, http.client.HTTPException)

# Caminho que caracteriza arquivo servido pelo webservice — a allowlist do
# download. Não é o mesmo endpoint das funções (`/webservice/rest/server.php`).
_PREFIXO_ARQUIVO = "/webservice/pluginfile.php/"

# Timeout do download. Maior arquivo medido em 01/09: 6,3 MB. Mais generoso que o
# das funções porque aqui o custo é banda, não processamento do Moodle.
_TIMEOUT_DOWNLOAD_SEGUNDOS = 120

# Teto por arquivo. Maior medido: 6,3 MB — folga deliberada de ~8x.
TETO_ARQUIVO_BYTES = 50 * 1024 * 1024

# Timeout do transporte HTTP padrão. Não é configurável por parâmetro porque
# nenhum teste exercita esse caminho (só tests/moodle/test_live.py, pulado) —
# um valor fixo e conservador é suficiente até haver dado medido que peça algo
# diferente (decisão de §9, não conveniência de código).
# Medido ao vivo em 31/08/2026: `core_enrol_get_users_courses` levou **14,7 s**
# para devolver as 74 matrículas (104 kB). Com o teto anterior de 15 s, a chamada
# mais pesada da ferramenta `material` rodava a 2% de margem — e estourou na
# primeira execução real, com a suíte inteira verde. Não baixe este valor sem
# remedir: a suíte não alcança este caminho (§9, 31/08).
_TIMEOUT_PADRAO_SEGUNDOS = 60


class _TokenOculto:
    """Guarda o token sem deixar `repr`/`str` (nem o despejo de `vars()` de
    quem o contém) imprimirem o valor por acidente (Invariante 3).

    `__slots__` é o que faz isso valer também para `vars(cliente)`: o atributo
    do cliente aponta para um objeto deste tipo, e `str()` de um dicionário
    chama `repr()` em cada valor — nunca o valor bruto. `get()` é a única
    porta de saída, usada só na hora de montar o payload da requisição.
    """

    __slots__ = ("_valor",)

    def __init__(self, valor: str) -> None:
        self._valor = valor

    def get(self) -> str:
        return self._valor

    def __repr__(self) -> str:  # pragma: no cover — exercitado via vars(c)
        return "TokenOculto(***)"

    def __str__(self) -> str:  # pragma: no cover
        return "***"


@functools.lru_cache(maxsize=1)
def _contexto_tls() -> ssl.SSLContext:
    """Raízes do sistema + o intermediário que o e-Disciplinas deixa de mandar.

    Desde o certificado de 26/10/2026 o servidor envia a folha assinada por
    "RNP ICPEdu GR46 OV TLS CA 2025" junto com um intermediário que não tem
    nada a ver com ela (GlobalSign RSA OV SSL CA 2018). Navegador e curl do
    macOS completam a cadeia pela URL de AIA; o OpenSSL do Python não faz isso
    e recusa com CERTIFICATE_VERIFY_FAILED (§9, 04/11/2026).

    A verificação continua inteira — hostname, validade e assinatura. O PEM
    só ACRESCENTA o elo que falta; não substitui as raízes do sistema e não
    desliga nada. Quando a USP corrigir a cadeia, este arquivo vira redundante
    e inofensivo; ele vence em 19/11/2030.

    `VERIFY_X509_PARTIAL_CHAIN` deixa o intermediário embutido ser o ponto de
    confiança, sem exigir que a raiz dele (GlobalSign Root R46) esteja no
    repositório da máquina. Sem a flag, só o Python 3.13+ funcionava — ele a
    liga por padrão; no 3.11 e no 3.12 o `/etc/ssl/cert.pem` do macOS não traz
    a R46 e a cadeia parava em "unable to get issuer certificate" (§9,
    04/11/2026). A flag não afrouxa nada para os outros sites: as raízes do
    sistema já são pontos de confiança, e a única âncora nova é o PEM acima.
    """
    ctx = ssl.create_default_context()
    pem = importlib.resources.files(__package__).joinpath("cadeia_extra.pem")
    # `cadata` exige ASCII: por isso o cabeçalho do PEM não tem acento.
    ctx.load_verify_locations(cadata=pem.read_text(encoding="ascii"))
    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return ctx


def _e_falha_de_certificado(exc: BaseException) -> bool:
    """`urlopen` embrulha o erro de TLS em `URLError.reason`; o transporte
    injetado pode levantá-lo cru. Os dois caminhos contam."""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(
        exc.reason, ssl.SSLCertVerificationError
    )


_MENSAGEM_CERTIFICADO = (
    "o e-Disciplinas respondeu, mas o certificado HTTPS dele não pôde ser "
    "verificado (a cadeia que o servidor manda está incompleta ou mudou). Não é "
    "o seu token e não adianta repetir: atualize o usp-mcp e, se persistir, "
    "abra uma issue em https://github.com/CaioCastro1/usp-mcp/issues."
)


def _transporte_padrao(*, url: str, dados: dict) -> dict:
    """Transporte HTTP real, só stdlib (sem dependência nova).

    POST form-urlencoded — é o que o web service REST do Moodle espera. Erro
    de rede e JSON inválido não são tratados aqui: sobem como `OSError` e
    `ValueError` (ou subclasses, como `json.JSONDecodeError` e
    `urllib.error.URLError`) para `chamar` traduzir num erro legível, exigindo
    só um lugar de tradução em vez de duplicá-la no transporte injetável.
    """
    corpo = urllib.parse.urlencode(dados).encode("utf-8")
    requisicao = urllib.request.Request(url, data=corpo, method="POST")
    with urllib.request.urlopen(
        requisicao, timeout=_TIMEOUT_PADRAO_SEGUNDOS, context=_contexto_tls()
    ) as resp:
        bruto = resp.read()
    return json.loads(bruto)


def _e_lista_de_warnings(resposta) -> bool:
    """A forma `external_warnings` do core: lista de itens com `warningcode`.

    O critério é a forma do ITEM, não o tipo do topo: `core_enrol_get_users_courses`
    e `core_course_get_contents` também devolvem lista no topo, de cursos e de
    seções, e nenhum item deles tem `warningcode`. Lista vazia não é warning —
    é o sucesso documentado das funções que devolvem `external_warnings`.
    """
    return (
        isinstance(resposta, list)
        and len(resposta) > 0
        and all(isinstance(item, dict) and "warningcode" in item for item in resposta)
    )


def _levantar_se_erro(rotulo: str, resposta) -> None:
    """Traduz o erro do Moodle, e é chamada pelos DOIS caminhos.

    Existe como função e não embutida em `chamar` porque o download
    (`baixar`) recebe o mesmo formato de erro por outro transporte. Duplicar a
    tradução criaria duas mensagens diferentes para `invalidtoken`, e a
    divergência só apareceria no dia em que o token expirasse.

    Dois formatos de recusa, e os dois chegam com HTTP 200:

    - `dict` com `errorcode` — a exceção do Moodle, em qualquer função;
    - `list` de itens com `warningcode` — o retorno `external_warnings` que
      `mod_assign_submit_for_grading` e `mod_assign_save_submission` declaram
      no core. Sucesso é `[]`; recusa é `[{"warningcode":
      "couldnotsubmitforgrading", ...}]`, e há `submissionsclosed` e
      `couldnotsavesubmission`. Até 16/09/2026 este formato passava por
      sucesso, e `entregar` dizia "Feito" sobre uma recusa — no verbo que não
      tem desfazer.
    """
    if _e_lista_de_warnings(resposta):
        detalhes = "; ".join(
            f"{item.get('warningcode')} — {item.get('message', '') or ''}".rstrip(" —")
            for item in resposta
        )
        raise ErroMoodle(
            f"Moodle recusou {rotulo}: {detalhes}. A resposta veio como lista de "
            "avisos (HTTP 200), que é como o Moodle diz não para esta função."
        )
    if not (isinstance(resposta, dict) and "errorcode" in resposta):
        return
    errorcode = resposta["errorcode"]
    if errorcode == "invalidtoken":
        raise TokenInvalido(
            "Token do Moodle inválido ou expirado — rode ./scripts/token.sh para "
            "gerar um novo e gravar MOODLE_TOKEN no .env."
        )
    mensagem = resposta.get("message", "") or resposta.get("error", "")
    raise ErroMoodle(f"Moodle recusou {rotulo}: {errorcode} — {mensagem}")


def _transporte_download_padrao(*, url: str, dados: dict, teto_bytes: int):
    """POST form-urlencoded que devolve (content_type, bytes). Só stdlib.

    Lê no máximo `teto_bytes + 1` de propósito: é assim que um arquivo sem
    `filesize` utilizável ainda respeita o teto, e o byte extra é o que permite
    detectar que o teto foi ultrapassado em vez de truncar calado.
    """
    corpo = urllib.parse.urlencode(dados).encode("utf-8")
    requisicao = urllib.request.Request(url, data=corpo, method="POST")
    with urllib.request.urlopen(
        requisicao, timeout=_TIMEOUT_DOWNLOAD_SEGUNDOS, context=_contexto_tls()
    ) as resp:
        return resp.headers.get("Content-Type", ""), resp.read(teto_bytes + 1)


class ClienteMoodle:
    """Uma função por invocação, escolhida à mão (Regra de Ouro, §3.1).

    Deliberadamente SEM método que itere sobre funções: um sweep sobre as 447
    passa por `start_attempt` e `submit_for_grading` com o token do dono.
    """

    def __init__(
        self,
        *,
        token: str,
        url: str,
        transporte=None,
        transporte_download=None,
        permitir_escrita: bool = False,
    ) -> None:
        # Falhar cedo (Invariante 6): token vazio nunca deveria chegar a uma
        # requisição. A instrução de correção vai na mensagem, não só o fato.
        if not token:
            raise ErroMoodle(
                "MOODLE_TOKEN ausente ou vazio — configure-o no .env "
                "(ver .env.example) antes de usar o cliente."
            )
        self._token = _TokenOculto(token)
        # Sem barra final, sempre. `https://edisciplinas.usp.br/` é a forma que
        # se copia do navegador, e com ela o prefixo esperado do download virava
        # `...usp.br//webservice/pluginfile.php/`, que nenhuma `fileurl` real
        # tem: TODO `baixar` era recusado, e no modo singular a recusa subia
        # crua. Normalizar aqui, uma vez, é o que faz os dois sufixos abaixo
        # valerem para as duas grafias.
        self.url = url.rstrip("/")
        self.transporte = transporte if transporte is not None else _transporte_padrao
        self.transporte_download = (
            transporte_download
            if transporte_download is not None
            else _transporte_download_padrao
        )
        self.permitir_escrita = permitir_escrita

    def chamar(self, funcao: str, **params) -> dict:
        """Aplica a política, emite EXATAMENTE UMA requisição, traduz o erro.

        A política roda antes de qualquer I/O: uma função negada nunca chega
        a tocar o transporte (T21), nem mesmo com `permitir_escrita=True`
        (T22 — essa flag não abre o bloqueio permanente do §2.2).

        **Este caminho nunca declara confirmação.** Uma função de
        `ESCRITA_CONFIRMADA` chamada por aqui é recusada pela política como
        qualquer outra — a porta da escrita é `escrever`, e ela tem nome
        próprio justamente para não ser aberta por engano por código que só
        queria ler. Quem trava esta frase é o T60, com a flag ligada: até
        16/09/2026 nenhum teste a alcançava, e `confirmada=True` aqui dentro
        passava por 460 testes verdes.
        """
        return self._requisitar(funcao, params, confirmada=False)

    def escrever(self, funcao: str, **params) -> dict:
        """A ÚNICA porta que declara confirmação à política (15/09/2026).

        Verbo separado, e não um parâmetro de `chamar`, pelo mesmo motivo que
        `salvar_rascunho` e `entregar` são duas ferramentas e não um enum: um
        booleano põe as duas intenções a uma letra de distância na cabeça de
        quem gera a chamada, e a segunda não tem volta. Com um método próprio,
        todo código que escreve é achável por uma busca pelo nome, e nenhum
        caminho de leitura consegue escrever mesmo se quiser.

        Quem chama isto é `entrega.py`, depois de ter mostrado um plano e
        conferido que ele não mudou. Chamar daqui sem essa conferência é
        contornar a camada que o desenho inteiro existe para ter.
        """
        return self._requisitar(funcao, params, confirmada=True)

    def _requisitar(self, funcao: str, params: dict, *, confirmada: bool) -> dict:
        """O transporte e a tradução de erro, um lugar só para os dois verbos.

        Duplicar isto criaria duas mensagens diferentes para `invalidtoken`, e a
        divergência só apareceria no dia em que o token expirasse — que é o
        mesmo motivo pelo qual `_levantar_se_erro` já é função e não bloco.
        """
        decisao = politica.decidir(
            funcao, permitir_escrita=self.permitir_escrita, confirmada=confirmada
        )
        if not decisao.permitida:
            raise FuncaoBloqueada(decisao.motivo)

        if reservadas := _CHAVES_RESERVADAS & set(params):
            # Antes do transporte, e como recusa de política e não como erro de
            # parâmetro: a política acabou de decidir sobre `funcao`, e uma
            # destas chaves em `params` é uma tentativa de mandar outra coisa no
            # fio com a decisão dela na mão.
            raise FuncaoBloqueada(
                f"{funcao}: os parâmetros trazem {sorted(reservadas)}, que são "
                "do envelope da requisição e não da função. A política decidiu "
                f"sobre {funcao!r}, e é esse nome que vai no fio — nenhum outro."
            )

        url = f"{self.url}{_URL_SUFIXO_WEBSERVICE}"
        # O envelope entra DEPOIS de `params`, de propósito: mesmo que a recusa
        # acima um dia deixe passar uma grafia nova, o último a escrever
        # `wsfunction` é o nome que a política aprovou.
        dados = {
            **params,
            "wstoken": self._token.get(),
            "wsfunction": funcao,
            "moodlewsrestformat": "json",
        }

        try:
            resposta = self.transporte(url=url, dados=dados)
        except ValueError as exc:
            # JSON inválido com HTTP 200 — o caso real mais comum é página de
            # manutenção em HTML. Não deixar isso virar KeyError/JSONDecodeError
            # cru mais adiante (Invariante 6).
            raise RespostaIlegivel(
                f"{funcao}: a resposta do e-Disciplinas não é um JSON válido "
                "(provável página de manutenção ou erro HTML com HTTP 200)."
            ) from exc
        except _FALHAS_DE_TRANSPORTE as exc:
            if _e_falha_de_certificado(exc):
                raise CertificadoNaoVerificado(
                    f"{funcao}: {_MENSAGEM_CERTIFICADO}"
                ) from exc
            # TimeoutError é subclasse de OSError, assim como ConnectionError e
            # urllib.error.URLError — cobre timeout e recusa de conexão. A
            # segunda família é a que não é OSError: resposta truncada e status
            # line inválida (ver `_FALHAS_DE_TRANSPORTE`).
            raise MoodleIndisponivel(
                f"{funcao}: o Moodle/e-Disciplinas não respondeu ou a resposta "
                "veio truncada (timeout, conexão recusada ou interrompida). "
                "Tente de novo mais tarde."
            ) from exc

        _levantar_se_erro(funcao, resposta)

        return resposta

    def baixar(
        self,
        fileurl: str,
        *,
        tamanho_esperado: int | None = None,
        teto_bytes: int = TETO_ARQUIVO_BYTES,
    ) -> bytes:
        """Baixa UM arquivo do webservice do Moodle. O token vai no CORPO.

        Medido em 01/09/2026 (§9): o corpo do POST autentica igual à query
        string, e por isso a credencial nunca precisa entrar numa URL. Também
        medido: erro de credencial chega com **HTTP 200** e `Content-Type:
        application/json` — checar status não serve de nada aqui.

        A restrição de origem é a allowlist deste caminho. Ela roda antes de
        qualquer I/O: como o token viaja no corpo, uma URL de outro host
        entregaria a credencial do dono a esse host.
        """
        esperado = f"{self.url}{_PREFIXO_ARQUIVO}"
        if not fileurl.startswith(esperado):
            raise FuncaoBloqueada(
                f"Download recusado: {fileurl!r} não começa com {esperado!r}. "
                "O token vai no corpo da requisição, então baixar de outro "
                "endereço entregaria a sua credencial a ele."
            )

        try:
            content_type, corpo = self.transporte_download(
                url=fileurl,
                dados={"token": self._token.get()},
                teto_bytes=teto_bytes,
            )
        except _FALHAS_DE_TRANSPORTE as exc:
            if _e_falha_de_certificado(exc):
                raise CertificadoNaoVerificado(
                    f"Download: {_MENSAGEM_CERTIFICADO}"
                ) from exc
            raise MoodleIndisponivel(
                "O e-Disciplinas não respondeu ao download ou ele veio "
                "interrompido (timeout, conexão recusada ou truncada). Tente de "
                "novo mais tarde."
            ) from exc

        if "json" in (content_type or "").lower():
            try:
                _levantar_se_erro("o download do arquivo", json.loads(corpo))
            except ValueError as exc:
                raise RespostaIlegivel(
                    "O e-Disciplinas devolveu algo que não é o arquivo nem um "
                    "erro compreensível no lugar do download."
                ) from exc
            raise RespostaIlegivel(
                "O e-Disciplinas devolveu JSON no lugar do arquivo, sem "
                "`errorcode` para explicar o motivo."
            )

        if len(corpo) > teto_bytes:
            raise ErroMoodle(
                f"O arquivo passa do teto de {teto_bytes} bytes e não foi "
                "gravado. Baixe pelo e-Disciplinas."
            )

        if tamanho_esperado is not None and len(corpo) != tamanho_esperado:
            raise ErroMoodle(
                f"O download veio incompleto: esperava {tamanho_esperado} bytes "
                f"e recebeu {len(corpo)}. Nada foi gravado."
            )

        return corpo
