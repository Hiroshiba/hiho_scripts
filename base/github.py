"""GitHub API 操作のユーティリティ関数を提供する"""

import json
import subprocess


def get_current_org_repo() -> tuple[str, str]:
    """現在のリポジトリの org と repo を取得する"""
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception("現在のリポジトリ情報を取得できませんでした")

    data = json.loads(result.stdout)
    return data["owner"]["login"], data["name"]


def get_current_user() -> str:
    """現在の GitHub ユーザー名を取得する"""
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception("現在のGitHubユーザーを取得できませんでした")

    return result.stdout.strip()


def get_pr_fork_info(pr_number: int) -> tuple[str, str, str]:
    """PR の fork owner/repo/branch を取得する"""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "headRepositoryOwner,headRepository,headRefName",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(f"PR #{pr_number} の情報を取得できませんでした")

    data = json.loads(result.stdout)
    fork_owner = data["headRepositoryOwner"]["login"]
    fork_repo = data["headRepository"]["name"]
    branch_name = data["headRefName"]

    return fork_owner, fork_repo, branch_name


def add_fork_remote(fork_owner: str, repo_name: str) -> str:
    """fork リモートを追加する"""
    remote_name = fork_owner

    check_result = subprocess.run(
        ["git", "remote", "get-url", remote_name],
        capture_output=True,
    )

    if check_result.returncode == 0:
        print(f"リモート '{remote_name}' は既に存在します")
        return remote_name

    result = subprocess.run(
        [
            "git",
            "remote",
            "add",
            remote_name,
            f"git@github.com:{fork_owner}/{repo_name}.git",
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        raise Exception(f"リモート '{remote_name}' の追加に失敗しました")

    print(f"リモート '{remote_name}' を追加しました")
    return remote_name
