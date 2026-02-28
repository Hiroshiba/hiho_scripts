#!/usr/bin/env python3
"""VOICEVOX PR のスナップショットを更新する"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import subprocess

from base.git import check_commands, fetch_remote_branch
from base.github import add_fork_remote, get_current_user, get_pr_detail
from base.pr_parser import PRInfo, parse_pr_info


def main() -> None:
    """VOICEVOX PR のスナップショットを更新する"""
    pr_url = parse_arguments()
    check_commands(["git", "gh"])

    pr_info = parse_pr_info(pr_url)
    if not pr_info:
        if pr_url.strip().isdigit():
            pr_info = PRInfo(number=int(pr_url.strip()))
        else:
            print("エラー: PR URLまたはPR番号をパースできませんでした。", file=sys.stderr)
            print("例: https://github.com/VOICEVOX/voicevox/pull/123", file=sys.stderr)
            print("例: 123", file=sys.stderr)
            sys.exit(1)

    pr_number = pr_info["number"]
    detail = get_pr_detail(pr_number)
    current_user = get_current_user()

    is_own_pr = detail["author"] == current_user

    print(f"PR #{pr_number} のスナップショットを更新します")
    print(f"PR 作者: {detail['author']}, ブランチ: {detail['branch']}")

    if not is_own_pr:
        if not detail["maintainer_can_modify"]:
            print(
                "エラー: PRのmaintainerCanModifyがfalseのため、ブランチにpushできません。",
                file=sys.stderr,
            )
            print(
                "PR作者に「Maintainers are allowed to edit this pull request」を有効化してもらってください。",
                file=sys.stderr,
            )
            sys.exit(1)
        run_others_pr_flow(
            current_user, detail["author"], detail["fork_repo"], detail["branch"]
        )
    else:
        run_own_pr_flow(detail["fork_owner"], detail["fork_repo"], detail["branch"])

    print("スナップショットの更新が完了しました")


def parse_arguments() -> str:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description="VOICEVOX PR のスナップショットを更新する"
    )
    parser.add_argument(
        "pr_url",
        help="PR URL または PR 番号 (例: https://github.com/VOICEVOX/voicevox/pull/123, 123)",
    )
    args = parser.parse_args()
    return args.pr_url


def run_own_pr_flow(fork_owner: str, fork_repo: str, branch: str) -> None:
    """自分の PR のスナップショットを更新する"""
    print("自分のPRです。ワークフローをディスパッチします...")
    old_head_sha = get_branch_head_sha(fork_owner, fork_repo, branch)

    dispatch_time = datetime.now(timezone.utc).isoformat()
    dispatch_workflow(fork_owner, fork_repo, branch)

    run_id = find_workflow_run(fork_owner, fork_repo, branch, dispatch_time)
    wait_for_workflow_completion(fork_owner, fork_repo, run_id)

    validate_commit_advanced(fork_owner, fork_repo, branch, old_head_sha)


def run_others_pr_flow(
    current_user: str, pr_author: str, fork_repo: str, branch: str
) -> None:
    """他人の PR のスナップショットを更新する"""
    print(f"PR作者 ({pr_author}) のブランチをフェッチします...")
    add_fork_remote(pr_author, fork_repo)
    fetch_remote_branch(pr_author, branch)

    print(f"自分のフォーク ({current_user}) にpushします...")
    add_fork_remote(current_user, fork_repo)
    git_push(current_user, f"{pr_author}/{branch}:refs/heads/{branch}")

    old_head_sha = get_branch_head_sha(current_user, fork_repo, branch)

    print("ワークフローをディスパッチします...")
    dispatch_time = datetime.now(timezone.utc).isoformat()
    dispatch_workflow(current_user, fork_repo, branch)

    run_id = find_workflow_run(current_user, fork_repo, branch, dispatch_time)
    wait_for_workflow_completion(current_user, fork_repo, run_id)

    no_changes = validate_commit_advanced(current_user, fork_repo, branch, old_head_sha)
    if no_changes:
        delete_remote_branch(current_user, fork_repo, branch)
        return

    print("更新されたブランチをフェッチします...")
    fetch_remote_branch(current_user, branch)

    print(f"PR作者 ({pr_author}) のブランチにpushします...")
    git_push(pr_author, f"{current_user}/{branch}:{branch}")

    print("自分のフォーク上の一時ブランチを削除します...")
    delete_remote_branch(current_user, fork_repo, branch)


def dispatch_workflow(repo_owner: str, repo_name: str, branch: str) -> None:
    """test.yml ワークフローをディスパッチする"""
    result = subprocess.run(
        [
            "gh",
            "workflow",
            "run",
            "test.yml",
            "--repo",
            f"{repo_owner}/{repo_name}",
            "--ref",
            branch,
            "-f",
            "update_snapshots=true",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(
            f"ワークフローのディスパッチに失敗しました: {result.stderr.strip()}"
        )
    print("ワークフローをディスパッチしました")


def find_workflow_run(
    repo_owner: str, repo_name: str, branch: str, after_time: str
) -> int:
    """ディスパッチ後のワークフロー実行を検索する"""
    print("ワークフロー実行を検索中...")
    deadline = time.time() + 120
    after_dt = datetime.fromisoformat(after_time)

    while time.time() < deadline:
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow=test.yml",
                f"--branch={branch}",
                "--repo",
                f"{repo_owner}/{repo_name}",
                "--json",
                "databaseId,status,event,createdAt",
                "--limit",
                "5",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Exception(
                f"ワークフロー実行一覧の取得に失敗しました: {result.stderr.strip()}"
            )

        runs = json.loads(result.stdout)
        for run in runs:
            if run["event"] != "workflow_dispatch":
                continue
            created_at = datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))
            if created_at >= after_dt:
                run_id = run["databaseId"]
                print(f"ワークフロー実行を発見しました (run ID: {run_id})")
                return run_id

        print("ワークフロー実行を待機中... (5秒後に再試行)")
        time.sleep(5)

    raise Exception("ワークフロー実行が120秒以内に見つかりませんでした")


def wait_for_workflow_completion(repo_owner: str, repo_name: str, run_id: int) -> None:
    """ワークフローの完了を待機する"""
    print("ワークフローの完了を待機しています...")
    result = subprocess.run(
        [
            "gh",
            "run",
            "watch",
            str(run_id),
            "--repo",
            f"{repo_owner}/{repo_name}",
            "--exit-status",
        ],
    )
    if result.returncode != 0:
        print(
            f"エラー: ワークフロー (run ID: {run_id}) が失敗しました。",
            file=sys.stderr,
        )
        sys.exit(1)


def get_branch_head_sha(repo_owner: str, repo_name: str, branch: str) -> str:
    """リモートブランチの HEAD SHA を取得する"""
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo_owner}/{repo_name}/git/ref/heads/{branch}",
            "--jq",
            ".object.sha",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(
            f"ブランチ '{branch}' のHEAD SHAの取得に失敗しました: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def validate_commit_advanced(
    repo_owner: str, repo_name: str, branch: str, old_head_sha: str
) -> bool:
    """ブランチの HEAD が1コミット進んだことを検証する。変更なしの場合は True を返す"""
    new_head_sha = get_branch_head_sha(repo_owner, repo_name, branch)

    if new_head_sha == old_head_sha:
        print(
            "スナップショットの変更がありませんでした（コミットは追加されていません）"
        )
        return True

    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo_owner}/{repo_name}/commits/{new_head_sha}",
            "--jq",
            ".parents[0].sha",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(f"コミット情報の取得に失敗しました: {result.stderr.strip()}")

    parent_sha = result.stdout.strip()
    if parent_sha != old_head_sha:
        print(
            f"エラー: 新しいコミット ({new_head_sha[:7]}) の親が期待するSHA ({old_head_sha[:7]}) と一致しません。",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"コミットの追加を確認しました ({new_head_sha[:7]})")
    return False


def git_push(remote: str, refspec: str) -> None:
    """git push を実行する"""
    result = subprocess.run(
        ["git", "push", remote, refspec],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(
            f"git push {remote} {refspec} に失敗しました: {result.stderr.strip()}"
        )
    print(f"git push {remote} {refspec} 完了")


def delete_remote_branch(repo_owner: str, repo_name: str, branch: str) -> None:
    """リモートブランチを削除する"""
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "DELETE",
            f"repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception(
            f"ブランチ '{branch}' の削除に失敗しました: {result.stderr.strip()}"
        )
    print(f"ブランチ '{branch}' を削除しました ({repo_owner}/{repo_name})")


if __name__ == "__main__":
    main()
