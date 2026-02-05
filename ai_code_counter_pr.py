#!/usr/bin/env python3
"""
カウンタープルリクエスト（cross-fork PR）を作成するためのスクリプト
PRの送り主のfork/branchに対して変更を加え、PRを出す作業をClaude Codeに依頼する
"""

import argparse
import datetime
import json
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base.assistant import AssistantCli, run_assistant
from base.git import check_commands, fetch_remote_branch, is_git_repository
from base.github import (
    add_fork_remote,
    get_current_org_repo,
    get_current_user,
    get_pr_fork_info,
)
from base.pr_parser import parse_pr_info, validate_org_repo
from base.worktree_manager import (
    copy_local_configs,
    create_new_branch_worktree,
    get_worktree_path,
)


def main() -> None:
    assistant, prompt = parse_arguments()
    if assistant == "claude":
        check_commands(["git", "gh", "claude"])
    else:
        check_commands(["git", "gh", "codex"])

    if not prompt:
        prompt = get_prompt_from_stdin("PR URLまたはプロンプトを入力してください")

    if not is_git_repository():
        print("エラー: gitリポジトリ内で実行してください。", file=sys.stderr)
        sys.exit(1)

    pr_info = parse_pr_info(prompt)
    if not pr_info:
        print("エラー: PR URLまたはPRパスが見つかりませんでした。", file=sys.stderr)
        print("例: https://github.com/owner/repo/pull/123", file=sys.stderr)
        print("例: owner/repo/pull/123", file=sys.stderr)
        print("例: pull/123", file=sys.stderr)
        sys.exit(1)

    pr_number = pr_info["number"]

    current_org, current_repo = get_current_org_repo()
    validate_org_repo(pr_info, current_org, current_repo)

    fork_owner, fork_repo, target_branch = get_pr_fork_info(pr_number)

    remote_name = add_fork_remote(fork_owner, current_repo)
    fetch_remote_branch(remote_name, target_branch)

    branch_name = generate_branch_name()
    base_branch = f"{remote_name}/{target_branch}"

    print(f"カウンタープルリクエスト対象: {fork_owner}/{fork_repo} のブランチ '{target_branch}'")
    print(f"新規ブランチ '{branch_name}' を作成します")

    worktree_path = get_worktree_path(branch_name)

    if not create_new_branch_worktree(worktree_path, branch_name, base_branch):
        print("エラー: worktreeの作成に失敗しました。", file=sys.stderr)
        sys.exit(1)
    print(f"worktree パス: {worktree_path}")

    if assistant == "claude":
        copy_local_configs(worktree_path)

    my_user = get_current_user()
    counter_pr_prompt = build_counter_pr_prompt(
        fork_owner, fork_repo, target_branch, my_user, branch_name, prompt
    )

    run_assistant(assistant, counter_pr_prompt, str(worktree_path))


def parse_arguments() -> tuple[AssistantCli, str]:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="カウンタープルリクエスト作成用にworktreeを作り、AI コーディング CLI（Claude/Codex）を起動する"
    )
    parser.add_argument(
        "--ai",
        choices=["claude", "codex"],
        default="claude",
        help="起動するCLI（デフォルト: claude）",
    )
    parser.add_argument("prompt", nargs="*", help="PR URLまたはプロンプト")
    args = parser.parse_args()
    prompt = " ".join(args.prompt).strip()
    return args.ai, prompt


def get_prompt_from_stdin(stdin_message: str) -> str:
    """標準入力からプロンプトを取得する"""
    if not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print(f"{stdin_message} (Ctrl+Dで終了):")
        prompt = sys.stdin.read()

    prompt = prompt.strip()

    if not prompt:
        print("エラー: プロンプトが空です。", file=sys.stderr)
        sys.exit(1)

    return prompt


def generate_branch_name() -> str:
    """timestamp + random suffixでブランチ名生成する"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = secrets.token_hex(4)
    return f"ai/counter-pr/{timestamp}-{random_suffix}"


def build_counter_pr_prompt(
    fork_owner: str,
    fork_repo: str,
    target_branch: str,
    my_user: str,
    my_branch: str,
    user_prompt: str,
) -> str:
    """3行説明文付きプロンプト組み立てる"""
    return f"""これはカウンタープルリクエスト（cross-fork PR）のタスクです。{fork_owner}/{fork_repo} の {target_branch} ブランチへPRを出します。
以下の指示に従ってコーディングを行い、完了したらコミットしてプッシュし、プルリクエストを作成してください。
PRは `gh pr create --repo {fork_owner}/{fork_repo} --head {my_user}:{my_branch} --base {target_branch}` で作成してください。

以下が詳細なタスクです:
{user_prompt}"""


if __name__ == "__main__":
    main()
