"""W1-W7: o scripts/novo-worktree.sh, e a única coisa que ele não pode errar.

O script existe por uma medição de 21/09/2026: a `main` local desta máquina
estava 324 commits atrás do `origin/main`, com histórico divergente desde 31/08,
e todo worktree aberto dali nascia dois dias no passado — `git worktree add -b x`
ramifica do HEAD local, que ninguém garantiu estar em dia.

**W1 é o teste que justifica o arquivo**, e os outros seis existem para ele não
ficar sozinho: um repositório dublê onde o remoto tem um commit que o local não
tem, e a asserção é sobre em qual dos dois o worktree nasceu. Um script que
ramifique do local passa em tudo o mais e falha só aqui.

Nada aqui toca a rede: o "remoto" é um bare local, e o `git fetch` do script
resolve um caminho de arquivo. O venv é pulado com `USP_MCP_WORKTREE_SEM_VENV=1`
— pagar uma instalação de verdade por teste custaria minutos, e a escolha do
gerenciador é exercitada em W5/W6 pelo **argv enviado**, que é o que a regra 11
do CLAUDE.md manda assertar: o dublê devolve o que o teste mandou, então a saída
dele não prova nada.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "novo-worktree.sh"

MOTIVO_SEM_GIT = (
    "`git` não está no PATH deste ambiente, e todo teste daqui precisa de um "
    "repositório de verdade. Este skip NÃO é o caso normal: no ambiente do dono "
    "o git existe e estes testes rodam no gate."
)

sem_git = pytest.mark.skipif(shutil.which("git") is None, reason=MOTIVO_SEM_GIT)


def _git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _duble(tmp: pathlib.Path) -> tuple[pathlib.Path, str]:
    """Um checkout com `origin`, onde o REMOTO tem um commit que o local não tem.

    É a situação medida em 21/09: a main local parada enquanto o remoto andou.
    O commit extra é criado com `commit-tree`, que não toca a árvore de trabalho
    — assim o dublê fica atrasado sem que nenhum arquivo do teste desapareça.

    Devolve o checkout e o sha que existe SÓ no remoto.
    """
    local = tmp / "checkout"
    local.mkdir()
    _git(local.parent, "init", "--quiet", str(local))
    _git(local, "config", "user.email", "teste@exemplo.invalido")
    _git(local, "config", "user.name", "Teste")
    _git(local, "symbolic-ref", "HEAD", "refs/heads/main")

    (local / "scripts").mkdir()
    shutil.copy2(SCRIPT, local / "scripts" / SCRIPT.name)
    (local / "pyproject.toml").write_text("# dublê\n", encoding="utf-8")
    _git(local, "add", "-A")
    _git(local, "commit", "--quiet", "-m", "base comum")

    bare = tmp / "origem.git"
    _git(local.parent, "init", "--bare", "--quiet", str(bare))
    _git(local, "remote", "add", "origin", str(bare))
    _git(local, "push", "--quiet", "origin", "main")

    # O commit que só o remoto tem. Mesma árvore, pai no HEAD: o conteúdo não
    # importa, a ancestralidade sim.
    tree = _git(local, "rev-parse", "HEAD^{tree}")
    so_no_remoto = _git(
        local, "commit-tree", tree, "-p", "HEAD", "-m", "commit que so existe no remoto"
    )
    _git(local, "push", "--quiet", "origin", f"{so_no_remoto}:refs/heads/main")
    return local, so_no_remoto


def _rodar(local: pathlib.Path, *args: str, path_extra: str | None = None) -> subprocess.CompletedProcess:
    ambiente = dict(os.environ)
    ambiente["USP_MCP_WORKTREE_SEM_VENV"] = "1"
    if path_extra is not None:
        ambiente["PATH"] = path_extra
    return subprocess.run(
        ["./scripts/novo-worktree.sh", *args],
        cwd=local, env=ambiente, capture_output=True, text=True, timeout=120,
    )


# --------------------------------------------------------------------------
# W1 — a base é o remoto, e não o HEAD local
# --------------------------------------------------------------------------


@sem_git
def test_w1_o_worktree_nasce_do_origin_main_e_nao_do_head_local(tmp_path):
    """O defeito que o script existe para não ter. Se ele ramificar do HEAD
    local — que é o que `git worktree add -b` faz sozinho —, o worktree nasce no
    commit da base comum, e não no que só o remoto tem."""
    local, so_no_remoto = _duble(tmp_path)
    head_local_antes = _git(local, "rev-parse", "HEAD")
    assert head_local_antes != so_no_remoto, "dublê mal montado: local e remoto iguais"

    r = _rodar(local, "fix/teste")
    assert r.returncode == 0, f"script falhou:\n{r.stdout}\n{r.stderr}"

    criado = local / ".claude" / "worktrees" / "fix-teste"
    assert criado.is_dir(), f"worktree não foi criado. Saída:\n{r.stdout}\n{r.stderr}"
    assert _git(criado, "rev-parse", "HEAD") == so_no_remoto, (
        "o worktree nasceu do HEAD local, não do origin/main — é exatamente o "
        "defeito de 21/09/2026 que este script existe para não repetir"
    )


# --------------------------------------------------------------------------
# W2 — o que ele NÃO faz
# --------------------------------------------------------------------------


@sem_git
def test_w2_nao_cria_env_no_worktree(tmp_path):
    """Um `.env` próprio no worktree sombreia o do checkout — o defeito que o
    token.sh teve em 11/09/2026 (§9) e a checagem 0 do gate teve antes dele."""
    local, _ = _duble(tmp_path)
    r = _rodar(local, "fix/teste")
    assert r.returncode == 0

    criado = local / ".claude" / "worktrees" / "fix-teste"
    assert not (criado / ".env").exists(), "criou .env no worktree, sombreando o do checkout"
    assert ".env" in r.stdout, "não disse que o worktree fica sem .env, e por quê"


# --------------------------------------------------------------------------
# W3-W4 — recusa com cura, em vez de estrago
# --------------------------------------------------------------------------


@sem_git
def test_w3_recusa_caminho_ocupado_citando_a_cura(tmp_path):
    local, _ = _duble(tmp_path)
    ocupado = local / "ja-existe"
    ocupado.mkdir()

    r = _rodar(local, "fix/teste", "ja-existe")
    assert r.returncode == 1
    assert "git worktree remove" in r.stderr, (
        f"recusou sem dizer o que fazer. stderr:\n{r.stderr}"
    )


@sem_git
def test_w4_recusa_branch_existente_apontando_o_git_direto(tmp_path):
    """Este script abre branch NOVA. Continuar trabalho já começado é outro
    comando, e dizer qual vale mais do que o erro cru do git."""
    local, _ = _duble(tmp_path)
    _git(local, "branch", "ja/existe")

    r = _rodar(local, "ja/existe")
    assert r.returncode == 1
    assert "git worktree add" in r.stderr and "ja/existe" in r.stderr


# --------------------------------------------------------------------------
# W5-W6 — qual gerenciador, medido pelo argv ENVIADO
# --------------------------------------------------------------------------


def _duble_de_comando(dir_bin: pathlib.Path, nome: str, registro: pathlib.Path, corpo: str = "") -> None:
    """Um executável que anota como foi chamado e sai 0. O que interessa é o
    argv que chegou nele, não o que ele devolve (regra 11 do CLAUDE.md)."""
    dir_bin.mkdir(parents=True, exist_ok=True)
    alvo = dir_bin / nome
    alvo.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "{nome} $*" >> "{registro}"\n'
        f"{corpo}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    alvo.chmod(0o755)


@sem_git
def test_w5_com_uv_no_path_instala_editavel_com_os_extras(tmp_path):
    local, _ = _duble(tmp_path)
    binario = tmp_path / "bin"
    registro = tmp_path / "chamadas.txt"
    _duble_de_comando(binario, "uv", registro)

    ambiente = dict(os.environ)
    ambiente.pop("USP_MCP_WORKTREE_SEM_VENV", None)
    r = subprocess.run(
        ["./scripts/novo-worktree.sh", "fix/teste"],
        cwd=local,
        env={**ambiente, "PATH": f"{binario}:{os.environ['PATH']}"},
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    chamadas = registro.read_text(encoding="utf-8")
    assert "uv venv" in chamadas, f"não criou venv com uv. Chamadas:\n{chamadas}"
    assert "uv pip install -e .[dev]" in chamadas, (
        "instalou sem `-e` ou sem os extras de dev: sem o `-e` não existem os "
        f"entry points em .venv/bin/ e o test_pacote.py (P6) PULA. Chamadas:\n{chamadas}"
    )


@sem_git
def test_w6_sem_uv_cai_para_o_venv_do_python_com_a_mesma_cura(tmp_path):
    """Sem uv o script não pode desistir: cai para `python3 -m venv`, que é a
    cura que o scripts/servidor.sh e o gate já citam. Duas curas para a mesma
    falta é a divergência que este repositório já pagou três vezes."""
    local, _ = _duble(tmp_path)
    binario = tmp_path / "bin"
    registro = tmp_path / "chamadas.txt"
    # O python3 dublê cria o .venv/bin/python que o próprio script vai chamar em
    # seguida — senão o passo do pip morreria com ENOENT e o teste mediria isso.
    _duble_de_comando(
        binario, "python3", registro,
        corpo=(
            'if [ "${2:-}" = "venv" ]; then\n'
            '  mkdir -p .venv/bin\n'
            f'  printf "#!/usr/bin/env bash\\necho \\"venv-python \\$*\\" >> {registro}\\nexit 0\\n" > .venv/bin/python\n'
            "  chmod +x .venv/bin/python\n"
            "fi"
        ),
    )

    ambiente = dict(os.environ)
    ambiente.pop("USP_MCP_WORKTREE_SEM_VENV", None)
    # PATH sem uv, e com o git de verdade: o dublê substitui só o python3.
    caminho_git = pathlib.Path(shutil.which("git")).parent
    r = subprocess.run(
        ["./scripts/novo-worktree.sh", "fix/teste"],
        cwd=local,
        env={**ambiente, "PATH": f"{binario}:{caminho_git}:/usr/bin:/bin"},
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, f"{r.stdout}\n{r.stderr}"

    chamadas = registro.read_text(encoding="utf-8")
    assert "python3 -m venv .venv" in chamadas, f"não criou o venv. Chamadas:\n{chamadas}"
    assert "venv-python -m pip install -e .[dev]" in chamadas, (
        f"instalou sem `-e` ou sem os extras de dev. Chamadas:\n{chamadas}"
    )


# --------------------------------------------------------------------------
# W7 — o fetch que falha não vira worktree velho em silêncio
# --------------------------------------------------------------------------


@sem_git
def test_w7_fetch_que_falha_para_o_script_em_vez_de_usar_o_ref_antigo(tmp_path):
    """Cair para o `refs/remotes/origin/main` antigo devolveria exatamente o
    worktree desatualizado que o script existe para não criar. Então ele para."""
    local, _ = _duble(tmp_path)
    _git(local, "remote", "set-url", "origin", str(tmp_path / "remoto-que-nao-existe"))

    r = _rodar(local, "fix/teste")
    assert r.returncode == 1, f"deixou passar com o fetch quebrado:\n{r.stdout}\n{r.stderr}"
    assert not (local / ".claude" / "worktrees" / "fix-teste").exists(), (
        "criou o worktree mesmo sem conseguir saber onde o origin/main está"
    )
    assert "fetch falhou" in r.stderr
