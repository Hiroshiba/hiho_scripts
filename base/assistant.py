"""AI コーディング CLI の起動を抽象化する"""

import os
import sys
from typing import Literal

from base.claude import run_claude
from base.codex import run_codex

AssistantCli = Literal["claude", "codex"]


def run_assistant(assistant: AssistantCli, prompt: str, worktree_path: str) -> None:
    """指定されたアシスタント CLI を起動する"""
    _restore_tty_stdin()

    worktree_context = """このタスクはgit worktree上で実行されています。ブランチは作成済みで、チェックアウトも完了しています。新しいブランチの作成やチェックアウトは不要です。"""
    full_prompt = f"{prompt}\n\n{worktree_context}"

    if assistant == "claude":
        run_claude(full_prompt, worktree_path)
        return
    if assistant == "codex":
        run_codex(full_prompt, worktree_path)
        return
    raise ValueError(f"Unknown assistant: {assistant}")


def _restore_tty_stdin() -> None:
    """パイプから stdin を消費した後でも対話 CLI が使えるよう /dev/tty を fd 0 に繋ぎ直す"""
    if sys.stdin.isatty():
        return
    try:
        tty_fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError as e:
        print(
            f"エラー: 制御端末 /dev/tty を開けませんでした: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    os.dup2(tty_fd, 0)
    os.close(tty_fd)

