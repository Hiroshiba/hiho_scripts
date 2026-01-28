"""Codex CLI のユーティリティ関数を提供する"""

import subprocess
import sys


def run_codex(prompt: str, worktree_path: str) -> None:
    """Codex CLI を起動する"""
    # FIXME: 日本語入力したあとエンターが効かない
    subprocess.run(
        ["codex", "--ask-for-approval", "untrusted", "--disable", "shell_snapshot", "--no-alt-screen", prompt],
        cwd=worktree_path,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
