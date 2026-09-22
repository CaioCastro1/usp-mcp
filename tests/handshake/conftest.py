"""Handshake stdio compartilhado — peças comuns.

Existe porque o mesmo furo foi registrado três vezes no backlog: o adaptador
`main()` de cada servidor não tem teste, e **verde na suíte não é verde nele**.
Na trilha do Moodle isso escondeu um `main()` escrito contra a API antiga do SDK
com 99/99 testes passando; `--auto-verificar` reduziu a chance de repetir, e não
eliminou.

Quatro decisões de desenho, e nenhuma é estilo:

**Um teste, N servidores, por descoberta.** Os servidores saem de um glob em
`usp_mcp/*/server.py`, não de uma lista escrita à mão. Um quarto sistema entra
coberto no dia em que nascer, em vez de entrar com o mesmo furo pela quarta vez.
Há teste que falha se o glob não achar nada — descoberta silenciosamente vazia é
a forma mais fácil de esta suíte inteira virar decoração.

**Sem cliente MCP falso.** A docstring dos três `main()` dizia que testar isto
exigiria "um cliente MCP falso, o que testaria o SDK e não este projeto". As
duas metades estavam erradas: o cliente é JSON-RPC por um pipe (a classe abaixo),
e o que se testa não é o SDK — é se **o nosso adaptador casa com o SDK que está
instalado**, que é exatamente o que quebrou uma vez.

**Nada de rede da USP, nada de credencial.** `initialize` e `tools/list` são
respondidos pelo processo sem tocar em `chamar_ferramenta`: nos três servidores o
cliente da API só é construído na chamada da ferramenta. Por isso esta camada
roda no gate, ao lado da suíte offline, e não atrás de `USP_MCP_LIVE=1`.

**A espera com prazo é de fila, não de `select()`.** Até 21/09/2026 as duas
esperas deste cliente eram uma chamada a `select()` sobre os canos do processo
filho. Em Windows `select()` só aceita socket: um usuário rodou a suíte lá e os
dois usos viraram `WinError 10038`, derrubando os 44 testes de handshake e os 7
de `test_anotacoes` — que dependem deste mesmo cliente — sem que uma linha dos
servidores estivesse errada. A troca é uma thread por cano, cada uma lendo linha
a linha para uma `queue.Queue`, e quem espera usa o prazo da fila. O prazo é o
assunto, não o mecanismo: ele existe para servidor travado virar vermelho em
segundos em vez de pendurar a suíte para sempre, e continua inteiro. As threads
são `daemon` e o `__exit__` as espera morrer depois de encerrar o processo —
thread de leitura que sobrevive ao teste é o outro jeito de a suíte não
terminar, e ele não aparece como vermelho.
"""
from __future__ import annotations

import json
import os
import pathlib
import queue
import subprocess
import sys
import threading

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# Tempo generoso: a máquina do dono sobe um interpretador e importa o SDK. O
# limite existe para uma falha virar vermelho em segundos em vez de travar a
# suíte para sempre — que é o outro jeito de um teste deixar de verificar.
TEMPO_LIMITE_S = 30

# Espera curta do stderr. O `select()` de antes perguntava ao descritor "chegou
# byte?"; agora quem responde é a fila, e entre o byte cair no cano e a linha
# entrar na fila existe um intervalo — minúsculo, e ainda assim uma corrida.
# Zero aqui transformaria barulho real em silêncio de vez em quando, que é como
# o H3 deixaria de verificar calado. Este prazo é longo para a corrida e curto
# para a suíte: ele só é gasto por inteiro quando não há barulho nenhum.
ESPERA_STDERR_S = 0.2

MOTIVO_SEM_SDK = (
    "o SDK do MCP (pacote `mcp`) não está instalado neste ambiente, então não há "
    "adaptador stdio para exercitar. Rode `.venv/bin/python -m pip install -r "
    "requirements.txt`. Este skip NÃO é o caso normal: no ambiente do dono o SDK "
    "está presente e estes testes rodam no gate."
)


def _tem_sdk() -> bool:
    try:
        import mcp.server  # noqa: F401
    except ImportError:
        return False
    return True


com_sdk = pytest.mark.skipif(not _tem_sdk(), reason=MOTIVO_SEM_SDK)


def descobrir_servidores() -> list[str]:
    """Módulos `usp_mcp.<sistema>.server`, por descoberta e em ordem estável."""
    achados = sorted(RAIZ.glob("usp_mcp/*/server.py"))
    return [f"usp_mcp.{p.parent.name}.server" for p in achados]


def sistema_de(modulo: str) -> str:
    return modulo.split(".")[1]


class ClienteStdio:
    """Cliente MCP mínimo: JSON-RPC por linha, sobre os pipes do processo.

    Não é dublê de nada — é um cliente de verdade, pequeno. O servidor sob teste
    é o processo real, subido como o `.mcp.json` o sobe.
    """

    def __init__(
        self,
        modulo: str,
        comando: list[str] | None = None,
        cwd: pathlib.Path | str | None = None,
        env: dict[str, str] | None = None,
    ):
        # `comando`/`cwd` existem para a suíte do lançador (L1/L2), que precisa
        # subir o MESMO servidor por outro caminho e a partir de um cwd que não
        # é a raiz — que é exatamente o que esta suíte aqui nunca exercita, e
        # foi por isso que o `.mcp.json` relativo passou verde quebrado fora do
        # Claude Code. O default é o comportamento de sempre.
        self._modulo = modulo
        self._comando = comando or [sys.executable, "-m", modulo]
        self._cwd = str(cwd) if cwd is not None else str(RAIZ)
        # `env` existe para o E14, que precisa subir o MESMO servidor com
        # `USP_MCP_ENTREGA` explicitamente ligada e explicitamente desligada.
        # O default continua sendo herdar o ambiente, que é como o cliente MCP
        # de verdade sobe o processo — herdar é o comportamento sob teste em
        # todo o resto desta suíte, e não podia virar exceção por causa de um
        # teste. Passar um `env` é dizer "esta propriedade não depende de quem
        # rodou a suíte", que é exatamente o que E14 afirma.
        self._env = env
        self._proc: subprocess.Popen | None = None
        # Uma fila por cano, alimentada pela thread leitora do cano. O `None` é
        # o fim de arquivo: cano fechado é o processo que morreu, e é um caso
        # diferente de "ainda não respondeu" — os dois precisam de mensagens
        # diferentes, porque dizem coisas diferentes sobre o servidor.
        self._fila_saida: queue.Queue[str | None] = queue.Queue()
        self._fila_erro: queue.Queue[str | None] = queue.Queue()
        self._leitores: list[threading.Thread] = []
        self._id = 0
        self.info: dict = {}
        # Preenchido quando a subida falha. Quem reporta é o teste, não a
        # fixture — ver a docstring de `servidor_vivo`.
        self.falha: str | None = None

    def __enter__(self) -> ClienteStdio:
        self._proc = subprocess.Popen(
            self._comando,
            cwd=self._cwd,
            env=({**os.environ, **self._env} if self._env is not None else None),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._leitores = [
            self._drenar(self._proc.stdout, self._fila_saida, "stdout"),
            self._drenar(self._proc.stderr, self._fila_erro, "stderr"),
        ]
        return self

    def _drenar(self, cano, fila: queue.Queue, nome: str) -> threading.Thread:
        """Uma thread lendo `cano` linha a linha para `fila`, até o fim.

        O `readline()` bloqueia, e aqui isso é aceitável porque o `__exit__`
        encerra o processo e fecha o cano: o bloqueio tem sempre um fim, e
        quem espera é a thread, nunca o teste. `daemon=True` é a última rede —
        mesmo que uma leitora fique presa num cano que um neto do processo
        segurou, o interpretador ainda encerra.
        """

        def laco() -> None:
            try:
                for linha in iter(cano.readline, ""):
                    fila.put(linha)
            except (OSError, ValueError):
                # Cano fechado debaixo da leitura, no teardown. É fim de
                # arquivo com outro nome, e o `finally` já diz isso.
                pass
            finally:
                fila.put(None)

        thread = threading.Thread(
            target=laco, name=f"{self._modulo}:{nome}", daemon=True
        )
        thread.start()
        return thread

    def __exit__(self, exc_tipo, *_):
        proc = self._proc
        if proc is None:
            return
        # Fechar o stdin é o fim de linha normal de um servidor stdio; matar
        # depois é o seguro contra um servidor que não trate isso.
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        # Com o processo morto, o outro lado dos dois canos fechou e cada
        # `readline()` devolve "" — é isso, e não um sinal nosso, que faz as
        # leitoras saírem. Esperar por elas aqui é o que impede o modo de falha
        # mais caro desta troca: thread que sobrevive ao teste não fica
        # vermelha, fica pendurada.
        for leitor in self._leitores:
            leitor.join(timeout=5)
        # Segundo recurso, para o caso que o `wait()` não alcança: um neto que
        # tenha herdado o cano o mantém aberto depois de o filho morrer.
        # Fechar o arquivo aqui faz o `readline()` levantar, e a leitora sai.
        for cano in (proc.stdout, proc.stderr):
            try:
                if cano is not None and not cano.closed:
                    cano.close()
            except OSError:  # pragma: no cover — já fechado
                pass
        for leitor in self._leitores:
            leitor.join(timeout=5)
        vivas = [leitor.name for leitor in self._leitores if leitor.is_alive()]
        # Só quando NÃO há exceção subindo: levantar aqui no meio de uma falha
        # trocaria o diagnóstico do teste por este, que é o menos interessante
        # dos dois.
        if vivas and exc_tipo is None:
            raise AssertionError(
                f"leitora de cano ainda viva depois do teardown: {vivas}. A "
                "suíte continua terminando (as threads são daemon), mas alguém "
                "está segurando o cano do processo — investigue antes que isso "
                "vire uma suíte que não encerra."
            )

    # ------------------------------------------------------------------ i/o

    def _escrever(self, mensagem: dict) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(mensagem) + "\n")
        self._proc.stdin.flush()

    def _ler(self) -> dict:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            linha = self._fila_saida.get(timeout=TEMPO_LIMITE_S)
        except queue.Empty:
            raise AssertionError(
                f"{self._modulo} não respondeu em {TEMPO_LIMITE_S}s. "
                f"stderr: {self.stderr_disponivel()[:800]!r}"
            ) from None
        # `None` é o fim de arquivo posto pela leitora; linha em branco é o
        # servidor que escreveu nada e seguiu. Os dois são a mesma notícia.
        if linha is None or not linha.strip():
            raise AssertionError(
                f"{self._modulo} fechou o stdout sem responder — o processo "
                f"provavelmente morreu. stderr: {self.stderr_disponivel()[:800]!r}"
            )
        return json.loads(linha)

    def pedir(self, metodo: str, params: dict | None = None) -> dict:
        self._id += 1
        self._escrever(
            {"jsonrpc": "2.0", "id": self._id, "method": metodo, "params": params or {}}
        )
        resposta = self._ler()
        if "error" in resposta:
            raise AssertionError(
                f"{self._modulo} respondeu erro JSON-RPC em {metodo}: "
                f"{resposta['error']}"
            )
        return resposta["result"]

    def notificar(self, metodo: str, params: dict | None = None) -> None:
        self._escrever({"jsonrpc": "2.0", "method": metodo, "params": params or {}})

    # ------------------------------------------------------------- inspeção

    def stderr_disponivel(self) -> str:
        """O que o processo escreveu em stderr, sem esperar por quem não escreveu.

        Devolve no máximo uma linha, e espera `ESPERA_STDERR_S` por ela: o
        suficiente para a leitora entregar o que já chegou no cano, e curto
        demais para pendurar um teste. Silêncio é `""`.
        """
        proc = self._proc
        if proc is None or proc.stderr is None:
            return ""
        try:
            linha = self._fila_erro.get(timeout=ESPERA_STDERR_S)
        except queue.Empty:
            return ""
        return linha or ""  # `None` é o fim de arquivo, e não é barulho

    def vivo(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def apertar_mao(self) -> dict:
        """`initialize` + `notifications/initialized`, como um cliente real faz."""
        resultado = self.pedir(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tests.handshake", "version": "0"},
            },
        )
        self.notificar("notifications/initialized")
        self.info = resultado
        return resultado


@pytest.fixture(scope="session", params=descobrir_servidores())
def servidor_vivo(request):
    """Um processo por servidor, com a mão já apertada, para a sessão inteira.

    Escopo de sessão por medida, não por gosto: um processo por teste custava
    67 s no gate (26 subidas de interpretador com o SDK), e 3 subidas custam ~8 s.
    O que cada teste exercita continua sendo o processo REAL — o que se
    compartilha é a subida, não a asserção.

    A subida a frio continua coberta: `initialize` acontece uma vez por
    processo, e H1 assere sobre o resultado guardado dessa subida.
    """
    if not _tem_sdk():
        pytest.skip(MOTIVO_SEM_SDK)
    modulo = request.param
    with ClienteStdio(modulo) as cliente:
        # A falha de subida é CAPTURADA e guardada, nunca levantada aqui: uma
        # fixture que levanta transforma `FAILED` em `ERROR`, e o §4 do
        # CONVENTIONS.md registra que erro de setup não é vermelho honesto — é
        # justamente o caso mais importante desta suíte (o servidor não sobe)
        # que ficaria com a cara errada.
        try:
            cliente.apertar_mao()
        except Exception as exc:  # noqa: BLE001 — o diagnóstico vai para o teste
            cliente.falha = f"{modulo} não completou o handshake: {exc}"
        yield modulo, cliente
