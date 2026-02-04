"""Git 操作のユーティリティ関数を提供する"""

import shutil
import subprocess
import sys


def is_git_repository() -> bool:
    """カレントディレクトリが git リポジトリ内かどうかを判定する"""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
    )
    return result.returncode == 0


def check_commands(commands: list[str]) -> None:
    """必要なコマンドの存在を確認する"""
    for cmd in commands:
        if not shutil.which(cmd):
            print(f"エラー: {cmd}コマンドが見つかりません。", file=sys.stderr)
            sys.exit(1)


def fetch_remote_branch(remote_name: str, branch_name: str) -> None:
    """リモートブランチを fetch する"""
    result = subprocess.run(
        ["git", "fetch", remote_name, branch_name],
        capture_output=True,
    )

    if result.returncode != 0:
        raise Exception(
            f"リモート '{remote_name}' のブランチ '{branch_name}' のfetchに失敗しました"
        )

    print(f"ブランチ '{remote_name}/{branch_name}' をfetchしました")
