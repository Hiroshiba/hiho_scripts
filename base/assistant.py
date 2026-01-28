"""AI コーディング CLI の起動を抽象化する"""

from typing import Literal

from base.claude import run_claude
from base.codex import run_codex

AssistantCli = Literal["claude", "codex"]


def run_assistant(assistant: AssistantCli, prompt: str, worktree_path: str) -> None:
    """指定されたアシスタント CLI を起動する"""
    if assistant == "claude":
        run_claude(prompt, worktree_path)
        return
    if assistant == "codex":
        run_codex(prompt, worktree_path)
        return
    raise ValueError(f"Unknown assistant: {assistant}")

