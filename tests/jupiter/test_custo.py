"""T34-T37: custo.

Uma asserção de razão de redução foi desenhada e DESCARTADA por medição
(§4.6 do spec): a razão do Jupiter é ~1,8x, não os 11,5x do recon — esses
comparam DWR com HTML, não DWR com a projeção. Contra o próprio DWR quase
não há o que reduzir, porque o payload É a resposta.

O que sobrou: teto absoluto, o núcleo estruturado (spread de 9%) e uma
trava CATEGÓRICA, que é o que de fato impede regressão.
"""
import json

import pytest

from tests.jupiter.conftest import FIXTURES, MODULOS, GetPorTipo, RoteadorDWR
from usp_mcp.jupiter import cliente, dwr, ferramentas, server
from usp_mcp.jupiter import indice as _indice
from usp_mcp.jupiter import modulos as _modulos

pytestmark = pytest.mark.contrato

# Medido em 31/08: 2.148 B (PSI3323) e 3.615 B (PTC3314). Folga de ~38%
# sobre a maior das duas amostras — duas, não uma: a maior é quase o dobro
# da menor com a MESMA forma.
TETO_SAIDA_B = 5000

# Medido: 179 B e 164 B, spread de 9%. É a parte que a ferramenta controla;
# o texto livre varia 77% e é a resposta em si.
NUCLEO = (
    "sigla",
    "nome",
    "creditos_aula",
    "creditos_trabalho",
    "carga_horaria_total",
    "tipo",
    "ativacao",
)
NUCLEO_MIN_B, NUCLEO_MAX_B = 140, 210


def tamanho(o):
    return len(json.dumps(o, ensure_ascii=False).encode())


def saida(gravador, bruto, sigla, secoes=ferramentas.SECOES):
    return ferramentas.disciplina(
        sigla, cliente=cliente.ClienteJupiter(gravador([bruto])), secoes=secoes
    )


@pytest.mark.parametrize("qual,sigla", [("psi", "PSI3323"), ("ptc", "PTC3314")])
def test_t34_teto_absoluto_com_folga_declarada(gravador, psi3323, ptc3314, qual, sigla):
    d = saida(gravador, psi3323 if qual == "psi" else ptc3314, sigla)
    assert tamanho(d) <= TETO_SAIDA_B, f"{sigla}: {tamanho(d)} B > {TETO_SAIDA_B} B"


@pytest.mark.parametrize("qual,sigla", [("psi", "PSI3323"), ("ptc", "PTC3314")])
def test_t35_nucleo_estruturado_e_estavel(gravador, psi3323, ptc3314, qual, sigla):
    d = saida(gravador, psi3323 if qual == "psi" else ptc3314, sigla)
    n = {k: d[k] for k in NUCLEO}
    assert NUCLEO_MIN_B <= tamanho(n) <= NUCLEO_MAX_B, f"núcleo de {sigla}: {tamanho(n)} B"


@pytest.mark.parametrize("qual,sigla", [("psi", "PSI3323"), ("ptc", "PTC3314")])
def test_t36_conjunto_de_chaves_e_exatamente_o_declarado(
    gravador, psi3323, ptc3314, qual, sigla
):
    # A trava que não envelhece. T34 e T35 são numéricos; esta é categórica,
    # e é a única forma de o custo explodir de novo (campo a mais sobrevivendo).
    d = saida(gravador, psi3323 if qual == "psi" else ptc3314, sigla)

    desconhecidas = set(d) - set(ferramentas.CAMPOS_SAIDA)
    assert not desconhecidas, f"campos fora do declarado: {sorted(desconhecidas)}"

    despejo = json.dumps(d, ensure_ascii=False)
    for vazamento in ("stackTrace", "javaClassName", "nomdisepa", "pgmrsudisepa"):
        assert vazamento not in despejo
    assert not [k for k in d if k.endswith(("_es", "epa"))]


def test_t37_erro_nunca_custa_mais_que_sucesso(gravador, psi3323, erro):
    sucesso = tamanho(saida(gravador, psi3323, "PSI3323"))

    c = cliente.ClienteJupiter(gravador([erro]))
    with pytest.raises(dwr.JupiterErro) as exc:
        ferramentas.disciplina("ZZZ9999", cliente=c)
    projetado = tamanho({"erro": exc.value.mensagem})

    assert projetado < sucesso, (
        f"erro projetado {projetado} B >= sucesso {sucesso} B. O erro cru são "
        "~1.978 tokens contra ~17 da mensagem: 116x, e é a resposta ERRADA."
    )


# O que o modelo lê é o TEXTO, não o dicionário. Medido em 14/09/2026 (PTC3314):
# padrão ~700 B, `todas` 3.880 B, `todas` + inglês ~6.700 B. Folga de ~30%.
TETO_TEXTO_PADRAO_B = 1_200
TETO_TEXTO_TODAS_B = 5_000
TETO_TEXTO_TODAS_INGLES_B = 8_500


def test_t34b_o_texto_padrao_responde_quantos_creditos_por_menos_de_1200_bytes(gravador, ptc3314):
    ficha = saida(gravador, ptc3314, "PTC3314", secoes=ferramentas.SECOES_PADRAO)
    texto = server.formatar(ficha)
    assert len(texto.encode()) <= TETO_TEXTO_PADRAO_B, f"padrão: {len(texto.encode())} B"
    assert "Créditos: 4 aula" in texto


def test_t34c_o_texto_com_todas_as_secoes_tem_teto(gravador, ptc3314):
    texto = server.formatar(saida(gravador, ptc3314, "PTC3314"))
    assert len(texto.encode()) <= TETO_TEXTO_TODAS_B, f"todas: {len(texto.encode())} B"


def test_t34d_o_texto_com_ingles_tem_teto(gravador, ptc3314):
    ficha = ferramentas.disciplina(
        "PTC3314", cliente=cliente.ClienteJupiter(gravador([ptc3314])),
        secoes=ferramentas.SECOES, idiomas=("pt", "en"),
    )
    texto = server.formatar(ficha)
    assert len(texto.encode()) <= TETO_TEXTO_TODAS_INGLES_B, f"inglês: {len(texto.encode())} B"
    assert "Ementa (inglês):" in texto


# --- T126-T127: a ferramenta `modulos` (26/10) -------------------------------
#
# Medido em 27/10 com as fixtures da fatia. Teto = medido × 1,15; piso =
# medido × 0,85. Quem cortar bytes baixa os dois no mesmo commit; quem crescer
# diz por quê. O cru que estas respostas substituem são ~104 mil tokens.
MEDIDO_MODULOS = {
    "ranking": ({}, 4751),
    "um_modulo": ({"busca": "3032/5080"}, 1861),
    "candidatos": ({"busca": "telecom"}, 377),
    "nenhum": ({"busca": "astronautica"}, 814),
    "sigla": ({"disciplina": "PMR3508"}, 256),
    "nome": ({"disciplina": "aprendizado de maquina"}, 389),
    "parecida": ({"disciplina": "PM3508"}, 258),
}
MEDIDO_ESTATICO_JUPITER = 4066


@pytest.fixture(scope="module")
def indice_modulos():
    respostas = json.loads(
        (FIXTURES / MODULOS["respostas"]).read_text(encoding="utf-8"))["respostas"]
    get = GetPorTipo((FIXTURES / MODULOS["lista_N"]).read_bytes(),
                     (FIXTURES / MODULOS["lista_V"]).read_bytes())
    return _indice.montar_indice(
        cliente.ClienteJupiter(RoteadorDWR(respostas), transporte_get=get))


@pytest.mark.parametrize("forma", sorted(MEDIDO_MODULOS))
def test_t126_cada_forma_de_resposta_de_modulos_tem_teto_e_piso(indice_modulos, forma):
    argumentos, medido = MEDIDO_MODULOS[forma]
    tamanho = len(_modulos.responder(indice_modulos, **argumentos).encode())
    assert tamanho <= medido * 1.15, f"{forma}: {tamanho} B > teto {medido * 1.15:.0f} B"
    assert tamanho >= medido * 0.85, (
        f"{forma}: {tamanho} B < piso {medido * 0.85:.0f} B — cortou e não baixou "
        "o teto. Atualize MEDIDO_MODULOS no mesmo commit."
    )


def test_t127_a_descricao_do_jupiter_tem_teto_e_piso():
    """O custo que se paga em TODA sessão, perguntada ou não. O Moodle cresceu
    24% entre 22/09 e 27/10 sem nada ficar vermelho — este é o guarda do
    Jupiter."""
    tamanho = len(json.dumps(server.listar_ferramentas(), ensure_ascii=False).encode())
    assert MEDIDO_ESTATICO_JUPITER * 0.85 <= tamanho <= MEDIDO_ESTATICO_JUPITER * 1.15, (
        f"tools/list do Jupiter: {tamanho} B (medido {MEDIDO_ESTATICO_JUPITER} B)"
    )
