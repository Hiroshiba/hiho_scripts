"""Codex CLI のユーティリティ関数を提供する"""

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from base.json import (
    get_optional_string,
    parse_json,
    require_json_object,
    require_object,
    require_string,
)


@dataclass(frozen=True)
class CodexSessionLog:
    """Codex セッション JSONL の参照情報を表す"""

    session_id: str
    jsonl_path: Path
    forked_from_id: str | None


def run_codex(prompt: str, worktree_path: str) -> None:
    """Codex CLI を起動する"""
    script = (
        f"cd {shlex.quote(worktree_path)} || exit 1; "
        f"codex --approve-for-me {shlex.quote(prompt)}; "
        f"exec bash -i"
    )
    os.execvp("bash", ["bash", "-lc", script])


def get_current_codex_session_id() -> str:
    """現在の Codex セッション ID を環境変数から取得する"""
    session_id = _require_environment_variable("CODEX_SESSION_ID")
    thread_id = _require_environment_variable("CODEX_THREAD_ID")

    if session_id != thread_id:
        raise RuntimeError(
            "環境変数 CODEX_SESSION_ID と CODEX_THREAD_ID の値が一致しません。"
        )

    _validate_session_id(session_id)
    return session_id


def get_codex_home() -> Path:
    """Codex のデータディレクトリを取得する"""
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home is None:
        return Path.home() / ".codex"
    if codex_home == "":
        raise RuntimeError("環境変数 CODEX_HOME が空です。")
    return Path(codex_home).expanduser().resolve()


def get_codex_session_log_chain(
    session_id: str, codex_home: Path
) -> list[CodexSessionLog]:
    """指定した Codex セッションからフォーク元までの JSONL を取得する"""
    _validate_session_id(session_id)
    if not codex_home.is_dir():
        raise RuntimeError(f"Codex のデータディレクトリが見つかりません: {codex_home}")

    session_logs: list[CodexSessionLog] = []
    visited_session_ids: set[str] = set()
    current_session_id = session_id

    while True:
        if current_session_id in visited_session_ids:
            raise RuntimeError(f"forked_from_id が循環しています: {current_session_id}")
        visited_session_ids.add(current_session_id)

        jsonl_path = _find_codex_session_jsonl(current_session_id, codex_home)
        session_log = _read_codex_session_log(jsonl_path, current_session_id)
        session_logs.append(session_log)

        if session_log.forked_from_id is None:
            return session_logs
        current_session_id = session_log.forked_from_id


def _require_environment_variable(name: str) -> str:
    """必須の環境変数を取得する"""
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f"環境変数 {name} が設定されていません。")
    if value == "":
        raise RuntimeError(f"環境変数 {name} が空です。")
    return value


def _validate_session_id(session_id: str) -> None:
    """Codex セッション ID が正規形の UUID か検証する"""
    try:
        normalized_session_id = str(UUID(session_id))
    except ValueError as error:
        raise RuntimeError(
            f"セッション ID が UUID ではありません: {session_id}"
        ) from error

    if normalized_session_id != session_id:
        raise RuntimeError(f"セッション ID が正規形ではありません: {session_id}")


def _find_codex_session_jsonl(session_id: str, codex_home: Path) -> Path:
    """セッション ID に対応する Codex セッション JSONL を探す"""
    search_directories = [
        codex_home / "sessions",
        codex_home / "archived_sessions",
    ]
    existing_directories = [
        directory for directory in search_directories if directory.is_dir()
    ]
    if len(existing_directories) == 0:
        raise RuntimeError(f"Codex のセッション保存先が見つかりません: {codex_home}")

    try:
        matches = sorted(
            {
                path.resolve()
                for directory in existing_directories
                for path in directory.rglob(f"*-{session_id}.jsonl")
                if path.is_file()
            }
        )
    except OSError as error:
        raise RuntimeError(
            "Codex のセッション JSONL を検索できませんでした。"
        ) from error

    if len(matches) == 0:
        raise RuntimeError(
            f"セッション ID に対応する JSONL が見つかりません: {session_id}"
        )
    if len(matches) > 1:
        match_list = "\n".join(str(path) for path in matches)
        raise RuntimeError(
            f"セッション ID に対応する JSONL が複数見つかりました:\n{match_list}"
        )
    return matches[0]


def _read_codex_session_log(
    jsonl_path: Path, expected_session_id: str
) -> CodexSessionLog:
    """Codex セッション JSONL のメタデータを読む"""
    try:
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(
            f"Codex のセッション JSONL を読み込めませんでした: {jsonl_path}"
        ) from error

    if len(lines) == 0:
        raise RuntimeError(f"Codex のセッション JSONL が空です: {jsonl_path}")

    context = f"Codex のセッション JSONL {jsonl_path} の先頭行"
    record = require_json_object(parse_json(lines[0], context), context)
    record_type = require_string(record, "type", context)
    if record_type != "session_meta":
        raise RuntimeError(f"{context}が session_meta ではありません。")

    payload = require_object(record, "payload", context)
    metadata_id = require_string(payload, "id", context)
    session_id = get_optional_string(payload, "session_id", context)
    forked_from_id = get_optional_string(payload, "forked_from_id", context)

    if session_id is not None and session_id != metadata_id:
        raise RuntimeError(f"{context}の session_id と id が一致しません。")
    if metadata_id != expected_session_id:
        raise RuntimeError(
            f"JSONL のセッション ID がファイル名と一致しません: {jsonl_path}"
        )
    if forked_from_id is not None:
        _validate_session_id(forked_from_id)

    return CodexSessionLog(
        session_id=metadata_id,
        jsonl_path=jsonl_path,
        forked_from_id=forked_from_id,
    )
