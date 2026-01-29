"""Codex CLI のユーティリティ関数を提供する"""

import os
import shlex


def run_codex(prompt: str, worktree_path: str) -> None:
    """Codex CLI を起動する"""
    script = (
        f'cd {shlex.quote(worktree_path)} || exit 1; '
        f'codex --ask-for-approval untrusted {shlex.quote(prompt)}; '
        f'exec bash -i'
    )
    os.execvp("bash", ["bash", "-lc", script])
