"""Claude Code CLI のユーティリティ関数を提供する"""

import subprocess
import sys


def run_claude(prompt: str, worktree_path: str) -> None:
    """Claude Code CLI を起動する"""
    subprocess.run(
        ["claude", "--permission-mode", "acceptEdits", prompt],
        cwd=worktree_path,
    )


def get_prompt(stdin_message: str) -> str:
    """引数または標準入力からプロンプトを取得する"""
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print(f"{stdin_message} (Ctrl+Dで終了):")
        prompt = sys.stdin.read()

    prompt = prompt.strip()

    if not prompt:
        print("エラー: プロンプトが空です。", file=sys.stderr)
        sys.exit(1)

    return prompt
