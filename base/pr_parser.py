"""PR URL/パスのパース処理を提供する"""

import re
import sys
from typing import Required, TypedDict


class PRInfo(TypedDict, total=False):
    """PR 情報を表す型"""
    number: Required[int]
    org: str
    repo: str


def parse_pr_info(text: str) -> PRInfo | None:
    """テキストから PR 番号・org・repo を抽出する"""
    text = text.strip()

    patterns = [
        r"https?://github\.com/(?P<org>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)",
        r"(?P<org>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)",
        r"pull/(?P<number>\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            result: PRInfo = {"number": int(match.group("number"))}
            org = match.group("org") if "org" in match.groupdict() else None
            repo = match.group("repo") if "repo" in match.groupdict() else None
            if org:
                result["org"] = org
            if repo:
                result["repo"] = repo
            return result

    return None


def validate_org_repo(pr_info: PRInfo, current_org: str, current_repo: str) -> None:
    """PR 情報の org/repo が現在のリポジトリと一致するか検証する"""
    if "org" in pr_info and pr_info["org"] != current_org:
        print(f"エラー: PRのorg '{pr_info['org']}' が現在のorg '{current_org}' と一致しません。", file=sys.stderr)
        sys.exit(1)

    if "repo" in pr_info and pr_info["repo"] != current_repo:
        print(f"エラー: PRのrepo '{pr_info['repo']}' が現在のrepo '{current_repo}' と一致しません。", file=sys.stderr)
        sys.exit(1)
