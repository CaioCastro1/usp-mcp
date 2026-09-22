"""Quando uma ressalva invariável ainda serve, e quando ela é só repetição.

**O problema, medido em 22/09/2026** (`notas/custo-em-token.md`): 801 tokens
saíam idênticos a toda chamada em sete ferramentas deste servidor — e a descrição
de cada uma, que o cliente carrega a sessão inteira, já os continha. Sobreposição
de vocabulário medida entre o bloco `⚠` e a descrição: 92% em `ja_entreguei`, 85%
em `atrasadas`, 71% em `o_que_mudou`. Em `atrasadas`, 215 dos 325 tokens da
resposta eram texto que a descrição de 279 tokens já dizia, quase palavra por
palavra. Não era troca de custo-por-chamada por custo-por-sessão: era a mesma
frase duas vezes na mesma sessão.

**A regra:** uma ressalva invariável só sai quando a resposta *desta* chamada
pode ser lida errado sem ela. Duas classes, e elas são complementares por
construção — nunca saem juntas:

- **`ausencia`** — desmente a leitura "não tem nada" de uma lista vazia. É a
  classe que protege o caso do Invariante 6: `atrasadas` sem nenhum item parece
  "não devo nada", e o que ela não vê (questionário) muda essa leitura.
- **`presenca`** — desmente a leitura "isto é tudo, e é fato" de uma lista cheia.
  `atrasadas` COM itens é onde o modelo acusaria alguém de não ter entregue, e é
  ali que "isto é o que o e-Disciplinas REGISTRA" precisa sair.

**Uma terceira classe não existe aqui de propósito.** Ressalva de *roteamento*
("para X, use a ferramenta Y") e de *contrato* ("'Em andamento' sai das datas do
espaço") não chegam a este módulo: elas foram para a descrição da ferramenta, que
é onde o cliente já as lê. Deixá-las existir como dado convidaria a próxima
sessão a emiti-las "só nesse caso", que é como a regra volta a ser sempre.

**Isto não afrouxa o Invariante 6.** O que o Invariante 6 proíbe é o silêncio que
engana — a lista vazia que parece "não tem nada", o erro cru engolido. A regra
acima preserva a ressalva exatamente onde essa leitura é possível. O que sai de
cena é repetição, não aviso. E ressalva que depende do DADO ("2 atividades não
puderam ser lidas com esta credencial") não passa por aqui: ela varia com a
resposta, é o Invariante 7 funcionando, e continua saindo sempre.

**Por que um módulo e não um `if` em cada ferramenta.** A mesma regra escrita em
sete lugares é sete lugares para divergir, e este repositório já pagou por isso
duas vezes: `texto.py` existe porque duas semânticas de casamento por nome
nasceram em módulos diferentes e custaram o T83.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# As duas únicas classes. Ver a docstring do módulo para por que `roteamento` e
# `contrato` não estão aqui.
AUSENCIA = "ausencia"
PRESENCA = "presenca"
CLASSES = (AUSENCIA, PRESENCA)


@dataclass(frozen=True)
class Ressalva:
    """Uma frase invariável, com a leitura errada que ela existe para desmentir.

    `frozen=True` porque estas nascem como constante de módulo, compartilhada
    entre chamadas: uma ressalva mutável faria a segunda resposta diferir da
    primeira sem que nada no dado tivesse mudado.
    """

    texto: str
    quando: str


def emitir(ressalvas: Sequence[Ressalva], *, vazio: bool) -> list[str]:
    """As ressalvas que esta resposta ainda precisa dizer, na ordem declarada.

    `vazio` é a forma da resposta: verdadeiro quando a ferramenta não achou item
    nenhum. A ordem é a da declaração, e não uma ordenação nossa — quem lê a
    resposta lê na ordem em que a ferramenta escreveu.
    """
    escolhida = AUSENCIA if vazio else PRESENCA

    saida = []
    for ressalva in ressalvas:
        if ressalva.quando not in CLASSES:
            # Erro e não silêncio: `quando="presença"`, com acento, nunca casaria
            # com nada e a ressalva sumiria sem ninguém notar. Um aviso perdido
            # em silêncio é o que o Invariante 6 proíbe, aplicado a este módulo.
            raise ValueError(
                f"classe de ressalva desconhecida: {ressalva.quando!r}. "
                f"As classes são {CLASSES}. Ressalva de roteamento não vem para "
                "cá — ela mora na descrição da ferramenta."
            )
        if ressalva.quando == escolhida:
            saida.append(ressalva.texto)
    return saida
