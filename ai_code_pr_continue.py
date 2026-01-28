#!/usr/bin/env python3
"""
PRの実装を続けるためのスクリプト
PR URLまたはPR番号からリモートブランチを特定し、worktreeを作成してClaude Code CLIを起動する
対応形式: https://github.com/org/repo/pull/123, org/repo/pull/123, pull/123
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base.claude import get_prompt, run_claude
from base.git import check_commands, is_git_repository
from base.github import get_current_org_repo, get_current_user
from base.pr_parser import parse_pr_info, validate_org_repo
from base.worktree_manager import (
    create_worktree,
    get_worktree_path,
    setup_claude_symlink,
    worktree_exists,
)


def main() -> None:
    check_commands(["git", "gh", "claude"])

    prompt = get_prompt("PR URLまたはプロンプトを入力してください")

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

    if pr_author != current_user:
        print(
            f"エラー: PR #{pr_number} の作者 '{pr_author}' が現在のユーザー '{current_user}' と一致しません。",
            file=sys.stderr,
        )
        sys.exit(1)

    branch_name = get_pr_branch(pr_number)
    if not branch_name:
        print(
            f"エラー: PR #{pr_number} のブランチが見つかりませんでした。",
            file=sys.stderr,
        )
        sys.exit(1)

    local_branch = find_local_branch_for_remote(branch_name)

    if not local_branch:
        if not fetch_and_create_local_branch(branch_name):
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

    setup_claude_symlink(worktree_path)

    run_claude(prompt, str(worktree_path))


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


def get_pr_branch(pr_number: int) -> str | None:
    """PR のブランチ名を取得する"""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "headRefName"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    data = json.loads(result.stdout)
    return data.get("headRefName")


def find_local_branch_for_remote(remote_branch: str) -> str | None:
    """リモートブランチに対応するローカルブランチを検索する"""
    result = subprocess.run(
        ["git", "branch", "-vv"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None

    pattern = re.compile(r"^\*?\s+(\S+)\s+\w+\s+\[origin/([^:\]]+)")

    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            local_branch = match.group(1)
            tracking_branch = match.group(2)
            if tracking_branch == remote_branch:
                return local_branch

    return None


def fetch_and_create_local_branch(branch_name: str) -> bool:
    """リモートブランチを fetch してローカルブランチを作成または更新する"""
    check_result = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True,
    )
    if check_result.returncode == 0:
        update_result = subprocess.run(
            ["git", "fetch", "origin", f"{branch_name}:{branch_name}"],
            capture_output=True,
        )
        return update_result.returncode == 0

    fetch_result = subprocess.run(
        ["git", "fetch", "origin", f"{branch_name}:{branch_name}"],
        capture_output=True,
    )
    return fetch_result.returncode == 0


if __name__ == "__main__":
    main()
