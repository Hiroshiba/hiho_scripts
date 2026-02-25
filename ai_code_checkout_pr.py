#!/usr/bin/env python3
"""
PR のブランチを worktree にチェックアウトして AI CLI を起動する
対応形式: https://github.com/org/repo/pull/123, org/repo/pull/123, pull/123
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base.assistant import AssistantCli, run_assistant
from base.git import check_commands, is_git_repository
from base.github import (
    add_fork_remote,
    get_current_org_repo,
    get_current_user,
    get_pr_fork_info,
)
from base.pr_parser import parse_pr_info, validate_org_repo
from base.worktree_manager import (
    copy_local_configs,
    create_worktree,
    get_worktree_path,
    worktree_exists,
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

    pr_author = get_pr_author(pr_number)
    current_user = get_current_user()

    fork_owner, fork_repo, branch_name = get_pr_fork_info(pr_number)

    print(f"PR #{pr_number} のブランチ '{branch_name}' をチェックアウトします")
    print(f"PR 作者: {pr_author}")

    is_from_origin = fork_owner == current_org
    if not is_from_origin:
        print(f"fork: {fork_owner}/{fork_repo}")
    if pr_author != current_user:
        print(f"(現在のユーザー: {current_user})")

    if is_from_origin:
        remote_name = "origin"
    else:
        remote_name = add_fork_remote(fork_owner, current_repo)

    local_branch = find_local_branch_for_remote(remote_name, branch_name)

    if not local_branch:
        if not fetch_and_create_local_branch(remote_name, branch_name):
            print(
                f"エラー: ブランチ '{branch_name}' のfetchに失敗しました。",
                file=sys.stderr,
            )
            sys.exit(1)
        local_branch = branch_name

    worktree_path = get_worktree_path(local_branch)

    if worktree_exists(worktree_path):
        print(f"既存のworktreeを使用します: {worktree_path}")
    else:
        if not create_worktree(worktree_path, local_branch):
            print("エラー: worktreeの作成に失敗しました。", file=sys.stderr)
            sys.exit(1)
        print(f"worktreeを作成しました: {worktree_path}")

    if assistant == "claude":
        copy_local_configs(worktree_path)

    checkout_pr_prompt = build_checkout_pr_prompt(
        pr_number,
        current_org,
        current_repo,
        pr_author,
        fork_owner,
        fork_repo,
        branch_name,
        local_branch,
        remote_name,
        is_from_origin,
        prompt,
    )
    run_assistant(assistant, checkout_pr_prompt, str(worktree_path))


def parse_arguments() -> tuple[AssistantCli, str]:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="PR 続行用にworktreeを作り、AI コーディング CLI（Claude/Codex）を起動する"
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


def get_pr_author(pr_number: int) -> str:
    """PR の作者を取得する"""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "author"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(f"PR #{pr_number} の情報を取得できませんでした")

    data = json.loads(result.stdout)
    return data["author"]["login"]


def find_local_branch_for_remote(remote_name: str, remote_branch: str) -> str | None:
    """リモートブランチに対応するローカルブランチを検索する"""
    result = subprocess.run(
        ["git", "branch", "-vv"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None

    pattern = re.compile(rf"^\*?\s+(\S+)\s+\w+\s+\[{remote_name}/([^:\]]+)")

    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            local_branch = match.group(1)
            tracking_branch = match.group(2)
            if tracking_branch == remote_branch:
                return local_branch

    return None


def build_checkout_pr_prompt(
    pr_number: int,
    current_org: str,
    current_repo: str,
    pr_author: str,
    fork_owner: str,
    fork_repo: str,
    branch_name: str,
    local_branch: str,
    remote_name: str,
    is_from_origin: bool,
    user_prompt: str,
) -> str:
    """PR のブランチ由来情報を文脈として含むプロンプトを組み立てる"""
    fork_info = (
        ""
        if is_from_origin
        else f"このPRは {fork_owner}/{fork_repo} のforkから出されています。\n"
    )
    return f"""このworktreeは PR #{pr_number} ({current_org}/{current_repo}) のブランチをチェックアウトしたものです。
PR作者: {pr_author}
ブランチ: {local_branch} (リモート: {remote_name}/{branch_name})
{fork_info}プッシュは `git push -u {remote_name} {local_branch}:{branch_name}` で行ってください。

以下がタスクの詳細です:
{user_prompt}"""


def fetch_and_create_local_branch(remote_name: str, branch_name: str) -> bool:
    """リモートブランチを fetch してローカルブランチを作成または更新する"""
    check_result = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True,
    )
    if check_result.returncode == 0:
        update_result = subprocess.run(
            ["git", "fetch", remote_name, f"{branch_name}:{branch_name}"],
            capture_output=True,
        )
        return update_result.returncode == 0

    fetch_result = subprocess.run(
        ["git", "fetch", remote_name, f"{branch_name}:{branch_name}"],
        capture_output=True,
    )
    return fetch_result.returncode == 0


if __name__ == "__main__":
    main()
