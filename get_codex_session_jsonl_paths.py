#!/usr/bin/env python3
"""Codex セッションとフォーク元の JSONL パスを列挙する"""

import argparse
import json
import sys

from base.codex import (
    get_codex_home,
    get_codex_session_log_chain,
    get_current_codex_session_id,
)


def main() -> None:
    """Codex セッション JSONL の一覧を JSON で出力する"""
    try:
        session_id_argument = parse_session_id_argument()
        if session_id_argument is None:
            session_id = get_current_codex_session_id()
        else:
            session_id = session_id_argument

        session_logs = get_codex_session_log_chain(session_id, get_codex_home())
    except RuntimeError as error:
        print(f"エラー: {error}", file=sys.stderr)
        sys.exit(1)

    output = [
        {
            "session_id": session_log.session_id,
            "jsonl_path": str(session_log.jsonl_path),
            "forked_from_id": session_log.forked_from_id,
        }
        for session_log in session_logs
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))


def parse_session_id_argument() -> str | None:
    """任意のセッション ID 引数を解析する"""
    parser = argparse.ArgumentParser(
        description="Codex セッションとフォーク元の JSONL パスを列挙する"
    )
    parser.add_argument(
        "session_id",
        nargs="?",
        help="起点とする Codex セッション ID。省略時は環境変数から取得する",
    )
    session_id = parser.parse_args().session_id
    if session_id is not None and not isinstance(session_id, str):
        raise RuntimeError("セッション ID 引数が文字列ではありません。")
    return session_id


if __name__ == "__main__":
    main()
