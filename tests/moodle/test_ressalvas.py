"""A regra de quando uma ressalva invariável sai (RS1-RS6).

Medido em 22/09/2026 (`notas/custo-em-token.md`): 801 tokens saem idênticos a
toda chamada em sete ferramentas, e a descrição de cada uma — que o cliente
carrega a sessão inteira — já os contém. O que este módulo decide é **quando**
essa frase ainda serve: quando a resposta desta chamada pode ser lida errado sem
ela.

Duas classes, e elas são complementares por construção: `ausencia` desmente a
leitura "não tem nada" de uma lista vazia; `presenca` desmente a leitura "isto é
tudo o que existe" de uma lista cheia. Nunca saem juntas — hoje as duas saem
sempre, e é esse o desperdício.
"""
from __future__ import annotations

import pytest

from usp_mcp.moodle.ressalvas import Ressalva, emitir

SO_QUANDO_VAZIO = Ressalva(texto="não cobre questionário", quando="ausencia")
SO_QUANDO_TEM = Ressalva(texto="isto é registro, não é fato", quando="presenca")


def test_rs1_lista_vazia_emite_a_de_ausencia_e_so_ela():
    assert emitir([SO_QUANDO_VAZIO, SO_QUANDO_TEM], vazio=True) == [
        "não cobre questionário"
    ]


def test_rs2_lista_com_item_emite_a_de_presenca_e_so_ela():
    assert emitir([SO_QUANDO_VAZIO, SO_QUANDO_TEM], vazio=False) == [
        "isto é registro, não é fato"
    ]


def test_rs3_a_ordem_de_declaracao_e_preservada():
    """Quem lê a resposta lê na ordem em que a ferramenta declarou. Ordenar por
    outra coisa (classe, tamanho) faria a saída mudar sem ninguém pedir."""
    primeira = Ressalva(texto="primeira", quando="presenca")
    segunda = Ressalva(texto="segunda", quando="presenca")
    assert emitir([primeira, segunda], vazio=False) == ["primeira", "segunda"]


def test_rs4_sem_ressalva_declarada_a_saida_e_vazia():
    assert emitir([], vazio=True) == []
    assert emitir([], vazio=False) == []


def test_rs5_classe_desconhecida_levanta_em_vez_de_calar():
    """O modo de falha que este `raise` existe para impedir: alguém escreve
    `quando="presença"`, com acento, e a ressalva simplesmente nunca sai. Seria
    um aviso perdido em silêncio — o Invariante 6 aplicado a este módulo."""
    with pytest.raises(ValueError, match="presença"):
        emitir([Ressalva(texto="x", quando="presença")], vazio=False)


def test_rs6_a_ressalva_e_imutavel():
    """Constante de módulo compartilhada entre chamadas: se `emitir` ou uma
    ferramenta puder mudar o texto, a segunda chamada responde diferente da
    primeira sem que nada no dado tenha mudado."""
    with pytest.raises(Exception):
        SO_QUANDO_TEM.texto = "outro"
