"""AI コーディング CLI の起動を抽象化する"""

from typing import Literal

from base.claude import run_claude
from base.codex import run_codex

AssistantCli = Literal["claude", "codex"]


def run_assistant(assistant: AssistantCli, prompt: str, worktree_path: str) -> None:
    """指定されたアシスタント CLI を起動する"""
    worktree_context = """このタスクはgit worktree上で実行されています。ブランチは作成済みで、チェックアウトも完了しています。新しいブランチの作成やチェックアウトは不要です。"""
    full_prompt = f"{prompt}\n\n{worktree_context}"

    if assistant == "claude":
        run_claude(full_prompt, worktree_path)
        return
    if assistant == "codex":
        run_codex(full_prompt, worktree_path)
        return
    raise ValueError(f"Unknown assistant: {assistant}")

