#!/usr/bin/env python3
"""GitHub の Issue テンプレートまたは PR テンプレートを取得する"""

import argparse
import base64
import json
import subprocess
import sys
from typing import Literal


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


class GitHubApiError(Exception):
    """GitHub API の実行失敗を表す"""


class GitHubApiNotFoundError(GitHubApiError):
    """GitHub API の 404 応答を表す"""


HTTP_STATUS_MISSING = "http_status_missing"
HttpStatus = int | Literal["http_status_missing"]


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


def gh_api(path: str) -> dict | list:
    """gh api コマンドを実行して JSON 結果を返す"""
    result = subprocess.run(
        ["gh", "api", "--include", path],
        capture_output=True,
        text=True,
    )
    status_code = parse_http_status_code(result.stdout)

    if result.returncode != 0:
        if status_code == 404:
            raise GitHubApiNotFoundError(path)
        raise GitHubApiError(format_gh_api_error(path, result, status_code))

    body = parse_response_body(path, result.stdout)

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise GitHubApiError(
            f"GitHub API の JSON 応答を解析できませんでした: {path}"
        ) from error


def parse_http_status_code(output: str) -> HttpStatus:
    """gh api --include の出力から HTTP ステータスを取得する"""
    status_lines = [
        line
        for line in normalize_line_endings(output).splitlines()
        if line.startswith("HTTP/")
    ]
    if len(status_lines) == 0:
        return HTTP_STATUS_MISSING

    status_line = status_lines[-1]
    parts = status_line.split(" ", 2)
    if len(parts) < 2:
        raise GitHubApiError("GitHub API の HTTP ステータス行を解析できませんでした。")

    try:
        return int(parts[1])
    except ValueError as error:
        raise GitHubApiError(
            "GitHub API の HTTP ステータスコードを解析できませんでした。"
        ) from error


def parse_response_body(path: str, output: str) -> str:
    """gh api --include の出力から JSON 本文を取得する"""
    parts = normalize_line_endings(output).rsplit("\n\n", 1)
    if len(parts) != 2:
        raise GitHubApiError(f"GitHub API の応答本文を取得できませんでした: {path}")

    return parts[1]


def normalize_line_endings(text: str) -> str:
    """改行コードを LF に揃える"""
    return text.replace("\r\n", "\n")


def format_gh_api_error(
    path: str,
    result: subprocess.CompletedProcess[str],
    status_code: HttpStatus,
) -> str:
    """gh api の失敗情報をエラーメッセージに整形する"""
    message_lines = [f"GitHub API の実行に失敗しました: {path}"]
    if status_code != HTTP_STATUS_MISSING:
        message_lines.append(f"HTTP ステータス: {status_code}")

    stderr = result.stderr.strip()
    if stderr != "":
        message_lines.append(stderr)

    return "\n".join(message_lines)


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


def print_issue_template_list(templates: dict | list, heading: str) -> None:
    """Issue テンプレート一覧を標準出力に表示する"""
    if not isinstance(templates, list):
        raise GitHubApiError("Issue テンプレート一覧の応答形式が想定と異なります。")

    print(heading)
    for template in templates:
        if not isinstance(template, dict):
            raise GitHubApiError("Issue テンプレートの応答形式が想定と異なります。")
        if "name" not in template or not isinstance(template["name"], str):
            raise GitHubApiError("Issue テンプレート名の応答形式が想定と異なります。")
        print(template["name"])


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
    if template:
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
    content_data = gh_api(path)
    if not isinstance(content_data, dict):
        raise GitHubApiError("テンプレートファイルの応答形式が想定と異なります。")
    if "content" not in content_data or not isinstance(content_data["content"], str):
        raise GitHubApiError("テンプレートファイル本文の応答形式が想定と異なります。")

    return decode_content(content_data["content"])


if __name__ == "__main__":
    main()
