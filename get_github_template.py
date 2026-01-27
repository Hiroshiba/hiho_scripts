#!/usr/bin/env python3
"""GitHub の Issue テンプレートまたは PR テンプレートを取得する"""

import argparse
import base64
import json
import subprocess
import sys


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

    if not owner or not repo:
        owner, repo = get_repo_info(owner, repo)

    if args.subcommand == "issue":
        handle_issue_template(owner, repo, args.template)
    elif args.subcommand == "pr":
        handle_pr_template(owner, repo, args.template)


def get_repo_info(owner: str | None, repo: str | None) -> tuple[str, str]:
    """gh コマンドでリポジトリの owner と name を取得する"""
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 or not result.stdout:
        print(
            "エラー: リポジトリ情報を取得できませんでした。-o と -r を指定するか、Git リポジトリ内で実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    repo_info = json.loads(result.stdout)

    if not owner:
        owner = repo_info["owner"]["login"]
    if not repo:
        repo = repo_info["name"]

    if not owner or not repo:
        print("エラー: owner または repo を取得できませんでした。", file=sys.stderr)
        sys.exit(1)

    return owner, repo


def gh_api(path: str) -> dict | list | None:
    """gh api コマンドを実行して JSON 結果を返す"""
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    return json.loads(result.stdout)


def decode_content(content: str) -> str:
    """base64 エンコードされた文字列をデコードする"""
    return base64.b64decode(content).decode("utf-8")


def handle_issue_template(owner: str, repo: str, template: str | None) -> None:
    """Issue テンプレートの取得処理を振り分ける"""
    if not template:
        list_issue_templates(owner, repo)
        return

    get_issue_template(owner, repo, template)


def list_issue_templates(owner: str, repo: str) -> None:
    """Issue テンプレート一覧を表示する"""
    templates = gh_api(f"repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE")
    if templates and isinstance(templates, list):
        print(f"Issue テンプレート一覧 ({owner}/{repo}):")
        for template in templates:
            print(template["name"])
        return

    templates = gh_api(f"repos/{owner}/.github/contents/.github/ISSUE_TEMPLATE")
    if templates and isinstance(templates, list):
        print(f"Issue テンプレート一覧 ({owner}/.github):")
        for template in templates:
            print(template["name"])
        return

    print("エラー: Issue テンプレートが見つかりませんでした。", file=sys.stderr)
    sys.exit(1)


def get_issue_template(owner: str, repo: str, template: str) -> None:
    """指定した Issue テンプレートの内容を表示する"""
    content_data = gh_api(
        f"repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE/{template}"
    )
    if content_data and isinstance(content_data, dict) and "content" in content_data:
        print(decode_content(content_data["content"]))
        return

    content_data = gh_api(
        f"repos/{owner}/.github/contents/.github/ISSUE_TEMPLATE/{template}"
    )
    if content_data and isinstance(content_data, dict) and "content" in content_data:
        print(decode_content(content_data["content"]))
        return

    print(f"エラー: Issue テンプレート '{template}' が見つかりませんでした。", file=sys.stderr)
    sys.exit(1)


def handle_pr_template(owner: str, repo: str, template: str | None) -> None:
    """PR テンプレートの取得処理を振り分ける"""
    if template:
        get_pr_template_by_name(owner, repo, template)
        return

    get_pr_template_default(owner, repo)


def get_pr_template_by_name(owner: str, repo: str, template: str) -> None:
    """指定した PR テンプレートの内容を表示する"""
    content_data = gh_api(
        f"repos/{owner}/{repo}/contents/.github/PULL_REQUEST_TEMPLATE/{template}"
    )
    if content_data and isinstance(content_data, dict) and "content" in content_data:
        print(decode_content(content_data["content"]))
        return

    content_data = gh_api(
        f"repos/{owner}/.github/contents/.github/PULL_REQUEST_TEMPLATE/{template}"
    )
    if content_data and isinstance(content_data, dict) and "content" in content_data:
        print(decode_content(content_data["content"]))
        return

    print(f"エラー: PR テンプレート '{template}' が見つかりませんでした。", file=sys.stderr)
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

    for path in pr_paths:
        content_data = gh_api(f"repos/{owner}/{repo}/contents/{path}")
        if content_data and isinstance(content_data, dict) and "content" in content_data:
            print(decode_content(content_data["content"]))
            return

    for path in pr_paths:
        content_data = gh_api(f"repos/{owner}/.github/contents/{path}")
        if content_data and isinstance(content_data, dict) and "content" in content_data:
            print(decode_content(content_data["content"]))
            return

    print("エラー: PR テンプレートが見つかりませんでした。", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
