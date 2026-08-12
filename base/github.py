"""GitHub API 操作のユーティリティ関数を提供する"""

import json
import re
import subprocess
import sys
import time
from typing import TypedDict

from base.json import (
    parse_json,
    require_boolean,
    require_json_object,
    require_object,
    require_string,
)


class GitHubApiError(RuntimeError):
    """GitHub API の実行失敗を表す"""


class GitHubApiNotFoundError(GitHubApiError):
    """GitHub API の 404 応答を表す"""


class GitHubClient:
    """gh コマンドを使って GitHub API を操作する"""

    def get_json(self, path: str) -> object:
        """GitHub API の JSON を取得する"""
        return self._request_json("GET", path, None)

    def patch_json(self, path: str, payload: dict[str, object]) -> object:
        """GitHub API を PATCH して JSON を返す"""
        return self._request_json("PATCH", path, payload)

    def put_json(self, path: str, payload: dict[str, object]) -> object:
        """GitHub API を PUT して JSON を返す"""
        return self._request_json("PUT", path, payload)

    def get_current_repository(self) -> tuple[str, str]:
        """現在のリポジトリを取得する"""
        return get_current_org_repo()

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
    ) -> object:
        """一時的な失敗を再試行して GitHub API を実行する"""
        max_attempts = 3
        attempt = 1

        while True:
            command = ["gh", "api", "--include", "--method", method, path]
            input_text = None
            if payload is not None:
                command.extend(["--input", "-"])
                input_text = json.dumps(payload, ensure_ascii=False)

            result = subprocess.run(
                command,
                input=input_text,
                capture_output=True,
                text=True,
            )
            status_code, response_body = _parse_http_response(result.stdout)
            succeeded = (
                result.returncode == 0
                and status_code is not None
                and 200 <= status_code < 300
            )
            if succeeded:
                return parse_json(response_body, f"GitHub API の応答 {path}")

            retryable = _is_retryable_status(status_code)
            if retryable and attempt < max_attempts:
                print(
                    f"GitHub API が一時的に失敗しました。{attempt + 1} 回目を試します。",
                    file=sys.stderr,
                )
                time.sleep(attempt)
                attempt += 1
                continue

            message = _format_api_error(
                method,
                path,
                status_code,
                response_body,
                result,
            )
            if status_code == 404:
                raise GitHubApiNotFoundError(message)
            raise GitHubApiError(message)


class PRDetail(TypedDict):
    """PR の詳細情報を表す型"""

    author: str
    fork_owner: str
    fork_repo: str
    branch: str
    maintainer_can_modify: bool


def get_current_org_repo() -> tuple[str, str]:
    """現在のリポジトリの org と repo を取得する"""
    data = _run_gh_json(
        ["gh", "repo", "view", "--json", "owner,name"],
        "現在のリポジトリ情報",
    )
    owner = require_object(data, "owner", "現在のリポジトリ情報")
    return (
        require_string(owner, "login", "現在のリポジトリ情報"),
        require_string(data, "name", "現在のリポジトリ情報"),
    )


def get_current_user() -> str:
    """現在の GitHub ユーザー名を取得する"""
    data = require_json_object(GitHubClient().get_json("user"), "GitHub ユーザー情報")
    return require_string(data, "login", "GitHub ユーザー情報")


def get_pr_fork_info(pr_number: int) -> tuple[str, str, str]:
    """PR の fork owner、repo、branch を取得する"""
    data = _run_gh_json(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "headRepositoryOwner,headRepository,headRefName",
        ],
        f"PR #{pr_number} の情報",
    )
    owner = require_object(data, "headRepositoryOwner", f"PR #{pr_number} の情報")
    repository = require_object(data, "headRepository", f"PR #{pr_number} の情報")
    return (
        require_string(owner, "login", f"PR #{pr_number} の情報"),
        require_string(repository, "name", f"PR #{pr_number} の情報"),
        require_string(data, "headRefName", f"PR #{pr_number} の情報"),
    )


def get_pr_detail(pr_number: int) -> PRDetail:
    """PR の author、fork 情報、maintainerCanModify を一括取得する"""
    data = _run_gh_json(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "author,headRepositoryOwner,headRepository,headRefName,maintainerCanModify",
        ],
        f"PR #{pr_number} の情報",
    )
    author = require_object(data, "author", f"PR #{pr_number} の情報")
    owner = require_object(data, "headRepositoryOwner", f"PR #{pr_number} の情報")
    repository = require_object(data, "headRepository", f"PR #{pr_number} の情報")
    return PRDetail(
        author=require_string(author, "login", f"PR #{pr_number} の情報"),
        fork_owner=require_string(owner, "login", f"PR #{pr_number} の情報"),
        fork_repo=require_string(repository, "name", f"PR #{pr_number} の情報"),
        branch=require_string(data, "headRefName", f"PR #{pr_number} の情報"),
        maintainer_can_modify=require_boolean(
            data,
            "maintainerCanModify",
            f"PR #{pr_number} の情報",
        ),
    )


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
        raise RuntimeError(f"リモート '{remote_name}' の追加に失敗しました")

    print(f"リモート '{remote_name}' を追加しました")
    return remote_name


def _run_gh_json(command: list[str], context: str) -> dict[str, object]:
    """gh コマンドを実行して JSON オブジェクトを返す"""
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{context}を取得できませんでした。\n{_format_command_output(result)}"
        )
    return require_json_object(parse_json(result.stdout, context), context)


def _parse_http_response(output: str) -> tuple[int | None, str]:
    """gh api --include の出力からステータスと本文を取得する"""
    normalized = output.replace("\r\n", "\n")
    status_matches = re.findall(r"^HTTP/\S+\s+(\d{3})", normalized, re.MULTILINE)
    status_code = int(status_matches[-1]) if len(status_matches) > 0 else None
    response_parts = normalized.rsplit("\n\n", 1)
    if len(response_parts) != 2:
        return status_code, ""
    return status_code, response_parts[1]


def _is_retryable_status(status_code: int | None) -> bool:
    """HTTP ステータスから安全に再試行できるか判定する"""
    if status_code is None:
        return True
    return status_code in {408, 429, 500, 502, 503, 504}


def _format_api_error(
    method: str,
    path: str,
    status_code: int | None,
    response_body: str,
    result: subprocess.CompletedProcess[str],
) -> str:
    """GitHub API の失敗を日本語のエラーへ整形する"""
    lines = [f"GitHub API の実行に失敗しました: {method} {path}"]
    if status_code is not None:
        lines.append(f"HTTP ステータス: {status_code}")
    stderr = result.stderr.strip()
    if stderr != "":
        lines.append(stderr)
    body = response_body.strip()
    if body != "":
        lines.append(body)
    return "\n".join(lines)


def _format_command_output(result: subprocess.CompletedProcess[str]) -> str:
    """失敗したコマンドの出力を整形する"""
    output = result.stderr.strip()
    if output == "":
        output = result.stdout.strip()
    if output == "":
        return "コマンドから詳細なエラー出力がありませんでした。"
    return output
