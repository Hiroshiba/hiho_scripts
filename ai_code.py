#!/usr/bin/env python3
"""
git worktreeを作成してClaude Code CLIを起動し、並列でCodexにブランチ名を提案させる
初期ブランチ名: ai/YYYYMMDD-HHMMSS-ランダム8文字
Codex提案後: ai/提案名-同じランダム8文字
"""

import argparse
import json
import secrets
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base.assistant import AssistantCli, run_assistant
from base.git import check_commands, is_git_repository
from base.worktree_manager import (
    branch_exists,
    create_new_branch_worktree,
    create_worktree,
    get_worktree_path,
    setup_claude_symlink,
    worktree_exists,
)


def main() -> None:
    CODEX_TIMEOUT = 15
    RANDOM_SUFFIX_LENGTH = 8

    base_branch, existing_branch, assistant, prompt = parse_arguments()
    if assistant == "claude":
        check_commands(["git", "codex", "claude"])
    else:
        check_commands(["git", "codex"])

    if not prompt:
        prompt = get_prompt_from_stdin()

    if not is_git_repository():
        print("エラー: gitリポジトリ内で実行してください。", file=sys.stderr)
        sys.exit(1)

    if existing_branch:
        handle_existing_branch_mode(existing_branch, assistant, prompt)
    else:
        handle_new_branch_mode(
            base_branch, assistant, prompt, RANDOM_SUFFIX_LENGTH, CODEX_TIMEOUT
        )


def parse_arguments() -> tuple[str | None, str | None, AssistantCli, str]:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="git worktreeを作成してAI コーディング CLI（Claude/Codex）を起動する"
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        help="新規ブランチ作成時のベースとなるブランチ",
    )
    parser.add_argument(
        "--branch",
        type=str,
        help="既存のブランチ名（worktreeを作成または再利用）",
    )
    parser.add_argument(
        "--ai",
        choices=["claude", "codex"],
        default="claude",
        help="起動するCLI（デフォルト: claude）",
    )
    parser.add_argument("prompt", nargs="*", help="タスクの内容")

    args = parser.parse_args()

    if args.base_branch and args.branch:
        print(
            "エラー: --base-branch と --branch は同時に指定できません。",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = " ".join(args.prompt).strip()

    return args.base_branch, args.branch, args.ai, prompt


def get_prompt_from_stdin() -> str:
    """標準入力からプロンプトを取得する"""
    if not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print("タスクの内容を入力してください (Ctrl+Dで終了):")
        prompt = sys.stdin.read()

    prompt = prompt.strip()

    if not prompt:
        print("エラー: プロンプトが空です。", file=sys.stderr)
        sys.exit(1)

    return prompt


def handle_existing_branch_mode(
    branch_name: str, assistant: AssistantCli, prompt: str
) -> None:
    """既存ブランチで worktree を作成・再利用する"""
    if not branch_exists(branch_name):
        print(
            f"エラー: ブランチ '{branch_name}' が存在しません。",
            file=sys.stderr,
        )
        sys.exit(1)

    worktree_path = get_worktree_path(branch_name)

    if worktree_exists(worktree_path):
        print(f"既存ブランチ '{branch_name}' の worktree を使用します")
        print(f"worktree パス: {worktree_path}")
    else:
        if not create_worktree(worktree_path, branch_name):
            print("エラー: worktreeの作成に失敗しました。", file=sys.stderr)
            sys.exit(1)
        print(f"ブランチ '{branch_name}' の worktree を作成しました")
        print(f"worktree パス: {worktree_path}")

    if assistant == "claude":
        setup_claude_symlink(worktree_path)

    run_assistant(assistant, prompt, str(worktree_path))


def handle_new_branch_mode(
    base_branch: str | None,
    assistant: AssistantCli,
    prompt: str,
    random_suffix_length: int,
    codex_timeout: int,
) -> None:
    """新しいブランチで worktree を作成する"""
    if base_branch is not None and not branch_exists(base_branch):
        print(
            f"エラー: ベースブランチ '{base_branch}' が存在しません。",
            file=sys.stderr,
        )
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = generate_random_suffix(random_suffix_length)
    initial_branch = f"ai/{timestamp}-{random_suffix}"

    worktree_path = get_worktree_path(initial_branch)

    if not create_new_branch_worktree(worktree_path, initial_branch, base_branch):
        print("エラー: worktreeの作成に失敗しました。", file=sys.stderr)
        sys.exit(1)

    if base_branch:
        print(f"ベースブランチ '{base_branch}' から新規ブランチ '{initial_branch}' を作成しました")
    else:
        print(f"新規ブランチ '{initial_branch}' を作成しました")
    print(f"worktree パス: {worktree_path}")

    thread = threading.Thread(
        target=suggest_branch_name,
        args=(prompt, random_suffix, str(worktree_path), codex_timeout),
        daemon=True,
    )
    thread.start()

    if assistant == "claude":
        setup_claude_symlink(worktree_path)

    run_assistant(assistant, prompt, str(worktree_path))


def generate_random_suffix(length: int) -> str:
    """指定した長さのランダムな英数字文字列を生成する"""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def suggest_branch_name(
    prompt: str, random_suffix: str, worktree_path: str, timeout: int
) -> None:
    """codex を使ってブランチ名を提案し、現在のブランチをリネームする"""
    codex_prompt = f"Generate a git branch name for this task: '{prompt}'. Use kebab-case with prefix (feature/fix/refactor/docs/test). Max 50 chars."

    with (
        tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as output_file,
        tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as schema_file,
    ):
        output_path = output_file.name
        schema_path = schema_file.name

        schema = {
            "type": "object",
            "properties": {"branchName": {"type": "string"}},
            "required": ["branchName"],
            "additionalProperties": False,
        }
        json.dump(schema, schema_file)
        schema_file.flush()

        try:
            result = subprocess.run(
                [
                    "codex",
                    "exec",
                    "--output-last-message",
                    output_path,
                    "--output-schema",
                    schema_path,
                    codex_prompt,
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                data = json.loads(Path(output_path).read_text())
                suggested_name = data.get("branchName", "")

                if suggested_name and len(suggested_name) <= 50:
                    new_branch = f"ai/{suggested_name}-{random_suffix}"
                    ok = (
                        subprocess.run(
                            ["git", "check-ref-format", "--branch", new_branch],
                            cwd=worktree_path,
                            capture_output=True,
                        ).returncode
                        == 0
                    )
                    if ok:
                        subprocess.run(
                            ["git", "branch", "-m", new_branch],
                            cwd=worktree_path,
                            capture_output=True,
                        )
        except subprocess.TimeoutExpired:
            pass
        finally:
            Path(output_path).unlink(missing_ok=True)
            Path(schema_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
