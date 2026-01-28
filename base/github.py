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
