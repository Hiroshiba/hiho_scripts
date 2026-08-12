#!/usr/bin/env python3
"""GitHub の Issue テンプレートまたは PR テンプレートを取得する"""

import argparse
import base64
import sys

from base.github import (
    GitHubApiNotFoundError,
    GitHubClient,
    get_current_org_repo,
)
from base.json import require_json_list, require_json_object, require_string


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitHub の Issue テンプレートまたは PR テンプレートを取得する"
    )
    parser.add_argument(
        "subcommand",
        choices=["issue", "pr"],
        help="issue: Issue テンプレートを取得、pr: PR テンプレートを取得",
    )
    parser.add_argument("-o", "--owner", help="リポジトリのオーナー")
    parser.add_argument("-r", "--repo", help="リポジトリ名")
    parser.add_argument("-t", "--template", help="テンプレート名")

    args = parser.parse_args()

    owner = args.owner
    repo = args.repo

    if owner is None or repo is None:
        owner, repo = get_repo_info(owner, repo)

    if args.subcommand == "issue":
        handle_issue_template(owner, repo, args.template)
    elif args.subcommand == "pr":
        handle_pr_template(owner, repo, args.template)


def get_repo_info(owner: str | None, repo: str | None) -> tuple[str, str]:
    """gh コマンドでリポジトリの owner と name を取得する"""
    current_owner, current_repo = get_current_org_repo()
    if owner is None:
        owner = current_owner
    if repo is None:
        repo = current_repo

    return owner, repo


def gh_api(path: str) -> object:
    """gh api コマンドを実行して JSON 結果を返す"""
    return GitHubClient().get_json(path)


def decode_content(content: str) -> str:
    """base64 エンコードされた文字列をデコードする"""
    return base64.b64decode(content).decode("utf-8")


def handle_issue_template(owner: str, repo: str, template: str | None) -> None:
    """Issue テンプレートの取得処理を振り分ける"""
    if template is None:
        list_issue_templates(owner, repo)
        return

    get_issue_template(owner, repo, template)


def list_issue_templates(owner: str, repo: str) -> None:
    """Issue テンプレート一覧を表示する"""
    template_dirs = [
        (
            f"repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE",
            f"Issue テンプレート一覧 ({owner}/{repo}):",
        ),
        (
            f"repos/{owner}/.github/contents/.github/ISSUE_TEMPLATE",
            f"Issue テンプレート一覧 ({owner}/.github):",
        ),
    ]

    for path, heading in template_dirs:
        try:
            templates = gh_api(path)
        except GitHubApiNotFoundError:
            continue

        print_issue_template_list(templates, heading)
        return

    print("エラー: Issue テンプレートが見つかりませんでした。", file=sys.stderr)
    sys.exit(1)


def print_issue_template_list(templates: object, heading: str) -> None:
    """Issue テンプレート一覧を標準出力に表示する"""
    template_list = require_json_list(templates, "Issue テンプレート一覧")
    print(heading)
    for raw_template in template_list:
        template = require_json_object(raw_template, "Issue テンプレート")
        print(require_string(template, "name", "Issue テンプレート"))


def get_issue_template(owner: str, repo: str, template: str) -> None:
    """指定した Issue テンプレートの内容を表示する"""
    paths = [
        f"repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE/{template}",
        f"repos/{owner}/.github/contents/.github/ISSUE_TEMPLATE/{template}",
    ]
    if print_first_template_content(paths):
        return

    print(
        f"エラー: Issue テンプレート '{template}' が見つかりませんでした。",
        file=sys.stderr,
    )
    sys.exit(1)


def handle_pr_template(owner: str, repo: str, template: str | None) -> None:
    """PR テンプレートの取得処理を振り分ける"""
    if template is not None:
        get_pr_template_by_name(owner, repo, template)
        return

    get_pr_template_default(owner, repo)


def get_pr_template_by_name(owner: str, repo: str, template: str) -> None:
    """指定した PR テンプレートの内容を表示する"""
    paths = [
        f"repos/{owner}/{repo}/contents/.github/PULL_REQUEST_TEMPLATE/{template}",
        f"repos/{owner}/.github/contents/.github/PULL_REQUEST_TEMPLATE/{template}",
    ]
    if print_first_template_content(paths):
        return

    print(
        f"エラー: PR テンプレート '{template}' が見つかりませんでした。",
        file=sys.stderr,
    )
    sys.exit(1)


def get_pr_template_default(owner: str, repo: str) -> None:
    """デフォルトの PR テンプレートを検索して表示する"""
    pr_paths = [
        ".github/pull_request_template.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "docs/pull_request_template.md",
        "docs/PULL_REQUEST_TEMPLATE.md",
        "pull_request_template.md",
        "PULL_REQUEST_TEMPLATE.md",
    ]

    paths = [
        *[f"repos/{owner}/{repo}/contents/{path}" for path in pr_paths],
        *[f"repos/{owner}/.github/contents/{path}" for path in pr_paths],
    ]
    if print_first_template_content(paths):
        return

    print("エラー: PR テンプレートが見つかりませんでした。", file=sys.stderr)
    sys.exit(1)


def print_first_template_content(paths: list[str]) -> bool:
    """最初に見つかったテンプレート内容を標準出力に表示する"""
    for path in paths:
        try:
            print(get_template_content(path))
            return True
        except GitHubApiNotFoundError:
            continue

    return False


def get_template_content(path: str) -> str:
    """テンプレートファイルの本文を取得する"""
    content_data = require_json_object(gh_api(path), "テンプレートファイル")
    return decode_content(
        require_string(content_data, "content", "テンプレートファイル")
    )


if __name__ == "__main__":
    main()
