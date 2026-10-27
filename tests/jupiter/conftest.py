"""Peças compartilhadas da suíte do Jupiter.

Nenhum caminho absoluto de máquina: tudo sai da posição deste arquivo.
Nenhuma fixture crua é impressa — só lida (§0 do CONVENTIONS.md).
"""
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "fixtures" / "jupiter"

# As três fixtures da fatia vertical (§4.1 do spec). Uma quarta aqui é
# alargar o escopo, e o teste da allowlist vai reclamar.
FATIA = {
    "psi3323": "dwr-pubObterDisciplina-PSI3323.txt",
    "ptc3314": "dwr-pubObterDisciplina-PTC3314.txt",
    "erro": "dwr-pubObterDisciplina-ERRO-sigla-inexistente.txt",
}

SENTINELA_ESQUELETO = "ESQUELETO-FASE2"


def caminho(chave):
    return FIXTURES / FATIA[chave]


def texto(chave):
    return caminho(chave).read_text(encoding="utf-8")


def fonte_de(modulo):
    """Fonte de um módulo, recusando-se a ler esqueleto.

    Três testes provam uma AUSÊNCIA no fonte (nada de eval, nada de token,
    nada de choke point). Contra o esqueleto praticamente vazio os três
    ficariam verdes verificando nada — medido. Este guarda transforma esse
    falso-verde em vermelho honesto.
    """
    fonte = pathlib.Path(modulo.__file__).read_text(encoding="utf-8")
    assert SENTINELA_ESQUELETO not in fonte, (
        f"{modulo.__name__} ainda é esqueleto. Uma varredura de fonte aqui "
        "passaria espuriamente: só significa algo depois da Fase 2."
    )
    return fonte


class Gravador:
    """Transporte falso: devolve fixture e guarda a requisição que teria saído.

    É o que torna os testes de corpo de requisição possíveis. Sem ele, corpo
    DWR malformado passa despercebido — o Jupiter responde 200 de qualquer
    jeito, e o erro aparece como campo vazio em vez de falha.
    """

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = []

    def __call__(self, url, corpo, cabecalhos):
        self.chamadas.append({"url": url, "corpo": corpo, "cabecalhos": dict(cabecalhos)})
        if len(self._respostas) > 1:
            return 200, self._respostas.pop(0)
        return 200, self._respostas[0]


@pytest.fixture
def psi3323():
    return texto("psi3323")


@pytest.fixture
def ptc3314():
    return texto("ptc3314")


@pytest.fixture
def erro():
    return texto("erro")


@pytest.fixture
def gravador():
    return Gravador


# --- A fatia de requisitos (14/09). HTML, não DWR: outra superfície, outro
# transporte, e por isso fixtures próprias. Todas de dado público — o §5 do
# design mediu 0 ocorrência de nome de docente nas três.
REQUISITOS = {
    "psi3323_html": "html-listarCursosRequisitos-PSI3323.html",
    "mat2455_html": "html-listarCursosRequisitos-MAT2455.html",
    "ptc3313_html": "html-listarCursosRequisitos-PTC3313.html",
    "ingresso_poli": "dwr-pubListarCursoEntrada-codclg3.txt",
    "colegiados": "dwr-pubListarColegiado.txt",
    # `pubListarRequisitoDisciplina` saiu da FATIA (allowlist) em 14/09 (§9),
    # mas o arquivo fica no disco: evidência pública do formato DWR de array
    # de um elemento, citada em notas/jupiter-recon.md e usada só pelo T5.
    "requisito_disciplina": "dwr-pubListarRequisitoDisciplina-MAT2454.txt",
}


def html(chave):
    """O JupiterWeb serve ISO-8859-1, e ler como UTF-8 estoura no primeiro
    acento. A decodificação é responsabilidade de quem lê o fio, então o teste
    passa BYTES adiante — é o que o transporte real entrega."""
    return (FIXTURES / REQUISITOS[chave]).read_bytes()


@pytest.fixture
def psi3323_html():
    return html("psi3323_html")


@pytest.fixture
def mat2455_html():
    return html("mat2455_html")


@pytest.fixture
def ptc3313_html():
    return html("ptc3313_html")


@pytest.fixture
def ingresso_poli():
    return (FIXTURES / REQUISITOS["ingresso_poli"]).read_text(encoding="utf-8")


@pytest.fixture
def colegiados():
    """As 47 unidades. Sem elas, decidir a unidade a partir do codcur seria
    chute: oito codclg são prefixo de outro (§9, 14/09)."""
    return (FIXTURES / REQUISITOS["colegiados"]).read_text(encoding="utf-8")


@pytest.fixture
def requisito_disciplina():
    return (FIXTURES / REQUISITOS["requisito_disciplina"]).read_text(encoding="utf-8")


# --- A fatia de módulos (26/10). Dado público: as duas listas de curso da Poli
# e os envelopes DWR crus de grade e ficha dos 50 pares de módulo/percurso. Um
# arquivo só para os 100 envelopes porque eles só fazem sentido juntos: o
# índice é a soma deles, e o teste de custo precisa do índice inteiro.
import json
import re
from urllib.parse import unquote

MODULOS = {
    "lista_N": "html-jupCursoLista-codcg3-N.html",
    "lista_V": "html-jupCursoLista-codcg3-V.html",
    "respostas": "dwr-modulos-poli.json",
}


@pytest.fixture
def lista_n():
    return (FIXTURES / MODULOS["lista_N"]).read_bytes()


@pytest.fixture
def lista_v():
    return (FIXTURES / MODULOS["lista_V"]).read_bytes()


@pytest.fixture
def respostas_modulos():
    dados = json.loads((FIXTURES / MODULOS["respostas"]).read_text(encoding="utf-8"))
    return dados["respostas"]


class RoteadorDWR:
    """Transporte DWR falso que responde pela CONSULTA e pelos PARÂMETROS que
    saíram no corpo — não pela ordem das chamadas.

    É o que permite asserir o parâmetro ENVIADO (regra 11 do CLAUDE.md): a
    chave `consulta|codcur|codhab|tipo` só existe na fixture se o `tipo` que
    saiu for o certo, e uma chave sem resposta derruba o teste em vez de
    devolver qualquer coisa.
    """

    def __init__(self, respostas):
        self.respostas = dict(respostas)
        self.enviados = []

    def __call__(self, url, corpo, cabecalhos):
        campos = dict(l.split("=", 1) for l in corpo.splitlines() if "=" in l)
        consulta = campos["c0-param0"].split(":", 1)[1]
        refs = sorted((k for k in campos if re.fullmatch(r"c0-e\d+", k)), key=lambda k: int(k[4:]))
        valores = [unquote(campos[k].split(":", 1)[1]) for k in refs]
        chave = "|".join([consulta, *valores])
        self.enviados.append(chave)
        if chave not in self.respostas:
            raise AssertionError(f"chamada sem fixture: {chave}")
        return 200, self.respostas[chave]


class GetPorTipo:
    """Transporte GET falso das duas listas de curso, escolhidas pelo `tipo=`
    da URL pedida."""

    def __init__(self, lista_n, lista_v, status=200):
        self._por_tipo = {"N": lista_n, "V": lista_v}
        self.status = status
        self.urls = []

    def __call__(self, url, cabecalhos):
        self.urls.append(url)
        tipo = re.search(r"[?&]tipo=([A-Z])", url).group(1)
        return self.status, self._por_tipo[tipo]
