"""Erros legíveis (Invariante 6).

Estas classes são contrato, não implementação: a suíte distingue quatro modos de
falha porque cada um exige uma ação diferente de quem lê. Um `Exception` genérico
faria "token venceu" e "a USP caiu" parecerem o mesmo problema.
"""
from __future__ import annotations


class ErroMoodle(Exception):
    """Base. Toda mensagem daqui deve dizer o que fazer, não só o que houve."""


class TokenInvalido(ErroMoodle):
    """Token vencido, revogado ou ausente. A mensagem aponta o §8 do SPEC1."""


class FuncaoBloqueada(ErroMoodle):
    """Função fora da allowlist ou na lista de bloqueio permanente (§2.2)."""


class MoodleIndisponivel(ErroMoodle):
    """Timeout, conexão recusada, 5xx. O serviço não respondeu."""


class CertificadoNaoVerificado(MoodleIndisponivel):
    """O servidor respondeu, mas a cadeia TLS dele não fecha (§9, 04/11/2026).

    Subclasse de `MoodleIndisponivel` para não quebrar quem já trata esse erro;
    classe própria porque a ação é outra: não adianta "tentar mais tarde" nem
    trocar o token — é atualizar o projeto ou avisar a USP. Até 04/11 esta
    falha chegava ao modelo como "timeout", e enganou o diagnóstico.
    """


class RespostaIlegivel(ErroMoodle):
    """HTTP 200 que não é o JSON esperado — página de manutenção, HTML de erro."""
