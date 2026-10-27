"""T116-T123: a busca em linguagem natural e o texto que o modelo lê.

A tabela do T116 é a da medição de 26/10 (§9 do spec), com o caso que falhou
lá — "pré-mestrado elétrica" — agora entre os que têm de passar.
"""
import pytest

from tests.jupiter.conftest import GetPorTipo, RoteadorDWR
from usp_mcp.jupiter import cliente, indice, modulos

pytestmark = pytest.mark.contrato


@pytest.fixture(scope="module")
def ind():
    import json
    from tests.jupiter.conftest import FIXTURES, MODULOS
    respostas = json.loads((FIXTURES / MODULOS["respostas"]).read_text(encoding="utf-8"))["respostas"]
    get = GetPorTipo((FIXTURES / MODULOS["lista_N"]).read_bytes(),
                     (FIXTURES / MODULOS["lista_V"]).read_bytes())
    return indice.montar_indice(cliente.ClienteJupiter(RoteadorDWR(respostas), transporte_get=get))


@pytest.mark.parametrize("busca,esperado", [
    ("sistemas eletrônicos", {"3032/5080", "3032/5090", "3032/5100"}),
    ("telecom", {"3032/5030", "3032/5050", "3032/5130"}),
    ("biomédica", {"3032/5020"}),
    ("pré-mestrado elétrica", {"3032/5070", "3032/5100", "3032/5130"}),
    ("inteligencia artificial", {"3033/6000", "3113/6000", "3123/6000"}),
    ("energia", {"3044/5020", "3044/5030", "3032/5110", "3032/5120"}),
    ("3032/5080", {"3032/5080"}),
    ("3032 5080", {"3032/5080"}),
])
def test_t116_a_busca_casa_o_que_o_aluno_escreve(ind, busca, esperado):
    assert {m.codigo for m in modulos.filtrar(ind.modulos, busca)} == esperado


def test_t117_sigla_exata_parecida_e_ausente(ind):
    exata = modulos.responder(ind, disciplina="pmr 3508")
    assert exata.startswith("PMR3508 Aprendizado de Máquina e Reconhecimento de Padrões")
    assert "3112/5000" in exata and "Mecatrônica Avançada" in exata

    parecida = modulos.responder(ind, disciplina="PM3508")
    assert "PM3508 não aparece em nenhum módulo" in parecida
    assert "PMR3508" in parecida

    nenhuma = modulos.responder(ind, disciplina="ZZZ9999")
    assert "Nenhuma sigla parecida" in nenhuma


def test_t118_sem_argumento_vem_todos_por_curso_com_a_menor_carga_no_topo(ind):
    texto = modulos.responder(ind)
    primeira, segunda = texto.splitlines()[:2]
    assert "50" in primeira
    assert segunda == "Menor carga: 270 h — Exploração e Produção de Petróleo (3056/5000)."
    assert "Ciclo Básico - Engenharia Elétrica (3032)" in texto
    for proibida in ("extinto", "antigo"):
        assert proibida not in texto.lower()


def test_t119_um_modulo_sai_com_as_disciplinas_por_semestre(ind):
    texto = modulos.responder(ind, busca="sistemas eletronicos avancados")
    linhas = texto.splitlines()
    assert linhas[0] == ("Sistemas Eletrônicos Avançados — 3032/5080 · curso: "
                         "Ciclo Básico - Engenharia Elétrica")
    assert linhas[1] == "Carga exigida: 360 h (eletiva 360). 31 disciplinas."
    assert "9º semestre ideal" in linhas and "10º semestre ideal" in linhas
    assert "  C PSI3541 Sistemas Embarcados Distribuídos (4+0)" in linhas
    assert "⚠" not in texto, "módulo sem defeito não leva ressalva nenhuma"


def test_t120_cada_defeito_do_dado_produz_a_sua_frase(ind):
    vazio = modulos.responder(ind, busca="3052/5000")
    assert "grade vazia no Jupiter" in vazio
    percurso = modulos.responder(ind, busca="3033/6000")
    assert "nem carga publicadas no Jupiter" in percurso
    todos = modulos.responder(ind)
    linhas = todos.splitlines()
    (l_vazio,) = [l for l in linhas if l.endswith("— 3052/5000, sem grade")]
    assert "carga não publicada" not in l_vazio
    (l_perc,) = [l for l in linhas if "— 3033/6000" in l]
    assert "carga não publicada" in l_perc and l_perc.endswith(", sem grade")


def test_t121_disciplina_pelo_nome_diz_em_que_modulos_aparece(ind):
    texto = modulos.responder(ind, disciplina="sistemas embarcados")
    (linha,) = [l for l in texto.splitlines() if l.startswith("  PCS3548 ")]
    assert "3032/5080" in linha and "3032/5060" in linha
    assert any(l.startswith("  PSI3541 ") for l in texto.splitlines())


def test_t122_busca_e_disciplina_juntas_restringem_aos_modulos_da_busca(ind):
    texto = modulos.responder(ind, busca="3122/5000", disciplina="sistemas embarcados")
    assert "3032/5080" not in texto


def test_t123_varios_candidatos_vem_sem_grade_e_nenhum_vem_com_os_cursos(ind):
    varios = modulos.responder(ind, busca="telecom")
    assert varios.startswith('"telecom" casou com 3 módulos')
    assert "semestre ideal" not in varios

    nada = modulos.responder(ind, busca="astronautica")
    assert nada.startswith('Nenhum módulo casou com "astronautica"')
    assert "3032 Ciclo Básico - Engenharia Elétrica" in nada


def test_t123b_ranking_e_ressalva_de_busca_curtos(ind):
    assert "  360 h eletiva  Sistemas Eletrônicos Avançados — 3032/5080" in (
        modulos.responder(ind).splitlines())
    ultima = modulos.responder(ind, disciplina="PMR3508").splitlines()[-1]
    assert ultima == ("⚠ Fora da busca, sem grade publicada: 3022/5000, "
                      "3022/5010, 3033/6000, 3052/5000, 3052/5010, 3113/6000, 3123/6000.")


def test_t123c_modulo_que_falhou_nao_parece_dado_ausente(ind):
    """Invariante 6: um módulo que o JupiterWeb não respondeu é "não lido
    agora", nunca "carga não publicada", "sem grade" nem ausência em definitivo."""
    import dataclasses
    falho = lambda m: dataclasses.replace(
        m, falhou=True, disciplinas=(), carga_total=None, carga_obrigatoria=None,
        carga_eletiva=None, carga_livre=None)
    com_falha = indice.Indice(tuple(falho(m) if m.codigo == "3032/5080" else m
                                    for m in ind.modulos))

    ranking = modulos.responder(com_falha)
    linha = next(l for l in ranking.splitlines() if "3032/5080" in l and l.startswith("  "))
    assert linha.endswith(", não lido agora")
    assert "sem grade" not in linha
    assert "não puderam ser lidos agora" in ranking
    assert "ficaram de fora" not in ranking

    um = modulos.responder(com_falha, busca="3032/5080")
    assert "não lido agora" in um
    assert "carga não publicada" not in um

    sigla = modulos.responder(com_falha, disciplina="PSI3541")
    assert "não aparece nos 49 módulos lidos" in sigla
    assert "nenhum módulo da Poli" not in sigla
    assert "⚠ Não lidos agora (falha do JupiterWeb), a busca não os viu: 3032/5080." in sigla
    assert "Fora da busca" not in sigla.split("Não lidos agora")[0].splitlines()[-1]
