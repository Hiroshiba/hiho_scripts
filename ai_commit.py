#!/usr/bin/env python3
"""staged 変更からコミットメッセージを生成してコミットする。"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

Provider = Literal["codex", "claude"]

MAX_CHUNK_CHARACTERS = 30_000
MAX_SUMMARY_CHARACTERS = 2_000

COMMIT_MESSAGE_INSTRUCTIONS = """1. **言語**  
   - コミットメッセージは**日本語**で記述すること。

2. **Conventional Commits 準拠**  
   - コミットメッセージは以下の形式に従って記述すること。  
     ```
     <type>(<scope>): <description>
     ```
   - ただし、**scope**は英単語で記述すること（例: `api`, `ui`, `db` など）。

3. **タイプの区分と各プロンプト例**  
   - **feat**: 新機能の追加  
     *例: 「新しいユーザー認証機能を実装」*  
   - **fix**: バグ修正  
     *例: 「ログイン時のエラーを修正」*  
   - **docs**: ドキュメントの変更  
     *例: 「README の更新」*  
   - **style**: コードのフォーマットやスタイルの調整（機能に影響しない変更）  
     *例: 「インデントの修正」*  
   - **refactor**: リファクタリング（機能追加やバグ修正を伴わないコード改善）  
     *例: 「変数名のリファクタリング」*  
   - **test**: テストコードの追加や修正  
     *例: 「ユニットテストの追加」*  
   - **chore**: その他の補助的な変更（ビルドツールの更新、ライブラリのアップデートなど）  
     *例: 「パッケージのバージョン更新」*

4. **スコープの記述**  
   - 変更箇所や影響範囲を示す**scope**は英単語で記述し、必要に応じて指定すること。  
     *例: `feat(api): 新しいエンドポイントの追加`*
   - scopeが不要な場合は必ず省略すること。
     *例: `fix: ログイン時のエラーを修正`*"""


def main() -> None:
    """staged 変更のコミットメッセージを AI で生成してコミットする。"""
    commit_staged_changes()


def commit_staged_changes() -> None:
    """コミットメッセージの生成とコミットを実行する。"""
    provider = parse_provider_argument()

    repository_root = get_repository_root(Path.cwd())
    if has_staged_changes(repository_root) is False:
        raise RuntimeError(
            "staged 変更がありません。先に必要な変更を git add してください"
        )

    staged_state = get_staged_state(repository_root)
    metadata = get_staged_metadata(repository_root)
    staged_diff = get_staged_diff(repository_root)
    commit_message = generate_commit_message(provider, metadata, staged_diff)

    if get_staged_state(repository_root) != staged_state:
        raise RuntimeError(
            "コミットメッセージの生成中に staged 変更が変わりました。再度実行してください"
        )

    commit_output = run_git(
        repository_root,
        ["commit", "-m", commit_message],
    )
    if commit_output != "":
        print(commit_output, end="" if commit_output.endswith("\n") else "\n")


def parse_provider_argument() -> Provider:
    """コマンドライン引数から利用する AI を取得する。"""
    parser = argparse.ArgumentParser(
        description="staged 変更からコミットメッセージを生成してコミットします"
    )
    parser.add_argument(
        "--ai",
        choices=["codex", "claude"],
        default="codex",
        help="利用する AI。デフォルトは codex",
    )
    arguments = parser.parse_args()
    provider = arguments.ai
    if provider == "codex" or provider == "claude":
        return provider
    raise ValueError(f"未対応の AI が指定されました: {provider}")


def get_repository_root(current_directory: Path) -> Path:
    """Git リポジトリのルートを取得する。"""
    root = run_git(
        current_directory,
        ["rev-parse", "--show-toplevel"],
    ).strip()
    if root == "":
        raise RuntimeError("Git リポジトリのルートを取得できませんでした")
    return Path(root)


def has_staged_changes(repository_root: Path) -> bool:
    """staged 変更の有無を返す。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--exit-code"],
        cwd=repository_root,
    )
    if result.returncode != 0 and result.returncode != 1:
        result.check_returncode()
    return result.returncode == 1


def get_staged_state(repository_root: Path) -> str:
    """staged 変更を表す blob ID の一覧を取得する。"""
    return run_git(
        repository_root,
        [
            "diff",
            "--cached",
            "--raw",
            "--no-abbrev",
            "--no-renames",
            "-z",
            "--no-ext-diff",
        ],
    )


def get_staged_metadata(repository_root: Path) -> str:
    """staged 変更のファイル情報と変更量を取得する。"""
    short_stat = run_git(
        repository_root,
        ["diff", "--cached", "--shortstat", "--no-color", "--no-ext-diff"],
    )
    name_status = run_git(
        repository_root,
        [
            "diff",
            "--cached",
            "--name-status",
            "--find-renames",
            "--no-color",
            "--no-ext-diff",
        ],
    )
    num_stat = run_git(
        repository_root,
        [
            "diff",
            "--cached",
            "--numstat",
            "--find-renames",
            "--no-color",
            "--no-ext-diff",
        ],
    )
    metadata = (
        "変更統計\n"
        f"{short_stat}\n"
        "変更ファイル\n"
        f"{name_status}\n"
        "ファイル別の追加行数と削除行数\n"
        f"{num_stat}"
    )
    return limit_metadata(metadata)


def get_staged_diff(repository_root: Path) -> str:
    """コミット対象となる staged diff を取得する。"""
    return run_git(
        repository_root,
        [
            "diff",
            "--cached",
            "--find-renames",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
        ],
    )


def run_git(repository_root: Path, arguments: list[str]) -> str:
    """Git コマンドを実行して標準出力を返す。"""
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=True,
    )
    return result.stdout


def format_model_command_failure(error: subprocess.CalledProcessError) -> str:
    """AI コマンドの失敗を再試行ログ向けに整形する。"""
    details = error.stderr.strip()
    if details == "":
        details = error.stdout.strip()
    if details == "":
        return f"AI コマンドに失敗しました。終了コード: {error.returncode}"
    return f"AI コマンドに失敗しました\n{details}"


def limit_metadata(metadata: str) -> str:
    """メタデータを全体から均等に抽出して上限内へ収める。"""
    if len(metadata) <= MAX_CHUNK_CHARACTERS:
        return metadata

    lines = metadata.splitlines(keepends=True)
    selected_count = min(len(lines), 200)
    while True:
        selected_lines = select_evenly(lines, selected_count)
        notice = f"メタデータ全 {len(lines)} 行から {selected_count} 行を均等抽出しています\n"
        limited_metadata = notice + "".join(selected_lines)
        if len(limited_metadata) <= MAX_CHUNK_CHARACTERS:
            return limited_metadata
        if selected_count == 1:
            raise RuntimeError("staged 変更のメタデータ一行が上限を超えています")
        selected_count //= 2


def generate_commit_message(
    provider: Provider,
    metadata: str,
    staged_diff: str,
) -> str:
    """変更量に応じた経路でコミットメッセージを生成する。"""
    maximum_selected_chunks = 8
    if len(staged_diff) <= MAX_CHUNK_CHARACTERS:
        prompt = build_direct_commit_prompt(metadata, staged_diff)
        return generate_valid_commit_message(provider, prompt)

    chunks = split_diff_chunks(staged_diff)
    selected_chunks = select_evenly(
        chunks,
        min(len(chunks), maximum_selected_chunks),
    )
    print(
        f"大きな staged diff を {len(chunks)} チャンクに分割し、"
        f"{len(selected_chunks)} チャンクを要約します",
        file=sys.stderr,
    )
    summaries = generate_summaries(provider, selected_chunks, len(chunks))
    prompt = build_aggregated_commit_prompt(
        metadata,
        summaries,
        len(chunks),
        len(selected_chunks),
    )
    return generate_valid_commit_message(provider, prompt)


def build_direct_commit_prompt(metadata: str, staged_diff: str) -> str:
    """全 staged diff から直接生成するプロンプトを作る。"""
    return f"""以下の staged 変更だけを根拠にコミットメッセージを一つ生成してください。
コマンドを実行せず、ファイルも読み込まず、提供した情報だけを使用してください。
出力は一行だけにしてください。説明、引用符、Markdown のコードフェンスは不要です。

{COMMIT_MESSAGE_INSTRUCTIONS}

変更情報
{metadata}

staged diff
{staged_diff}"""


def build_aggregated_commit_prompt(
    metadata: str,
    summaries: list[str],
    total_chunk_count: int,
    selected_chunk_count: int,
) -> str:
    """部分要約から最終生成するプロンプトを作る。"""
    summaries_text = "\n\n".join(
        f"部分要約 {index}\n{summary}"
        for index, summary in enumerate(summaries, start=1)
    )
    sampling_note = (
        f"diff 全 {total_chunk_count} チャンクのうち "
        f"{selected_chunk_count} チャンクを均等抽出して要約しました。"
    )
    return f"""以下の staged 変更のメタデータと部分要約だけを根拠に、変更全体を表すコミットメッセージを一つ生成してください。
部分要約を単純に連結せず、変更全体の主目的を一つにまとめてください。
コマンドを実行せず、ファイルも読み込まず、提供した情報だけを使用してください。
出力は一行だけにしてください。説明、引用符、Markdown のコードフェンスは不要です。

{COMMIT_MESSAGE_INSTRUCTIONS}

抽出情報
{sampling_note}

変更情報
{metadata}

部分要約
{summaries_text}"""


def generate_summaries(
    provider: Provider,
    selected_chunks: list[str],
    total_chunk_count: int,
) -> list[str]:
    """選択した diff チャンクを並列で要約する。"""
    maximum_parallel_calls = 3
    worker_count = min(len(selected_chunks), maximum_parallel_calls)
    if worker_count < 1:
        raise RuntimeError("要約対象の diff チャンクがありません")

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                generate_summary,
                provider,
                chunk,
                index,
                len(selected_chunks),
                total_chunk_count,
            )
            for index, chunk in enumerate(selected_chunks, start=1)
        ]
        return [future.result() for future in futures]


def generate_summary(
    provider: Provider,
    chunk: str,
    chunk_index: int,
    selected_chunk_count: int,
    total_chunk_count: int,
) -> str:
    """一つの diff チャンクから変更事実を要約する。"""
    prompt = f"""staged diff の一部から、変更事実を簡潔な日本語で要約してください。
コミットメッセージは作らず、変更した対象、内容、目的を可能な範囲で抽出してください。
推測で目的を補わず、コマンドを実行せず、ファイルも読み込まず、提供した diff だけを使用してください。
これは全 {total_chunk_count} チャンクから均等抽出した {selected_chunk_count} 件のうち {chunk_index} 件目です。

staged diff の一部
{chunk}"""
    schema = build_text_schema("summary", MAX_SUMMARY_CHARACTERS)
    return generate_structured_text(
        provider,
        prompt,
        "summary",
        schema,
        validate_summary,
    )


def generate_valid_commit_message(provider: Provider, prompt: str) -> str:
    """形式を検証しながらコミットメッセージを生成する。"""
    schema = build_text_schema("message", 200)
    return generate_structured_text(
        provider,
        prompt,
        "message",
        schema,
        validate_commit_message,
    )


def build_text_schema(field_name: str, maximum_length: int) -> dict[str, object]:
    """一つの文字列フィールドを持つ JSON Schema を作る。"""
    return {
        "type": "object",
        "properties": {
            field_name: {
                "type": "string",
                "minLength": 1,
                "maxLength": maximum_length,
            }
        },
        "required": [field_name],
        "additionalProperties": False,
    }


def generate_structured_text(
    provider: Provider,
    prompt: str,
    field_name: str,
    schema: dict[str, object],
    validator: Callable[[str], None],
) -> str:
    """構造化出力を検証し、失敗時は AI 呼び出しだけを再試行する。"""
    maximum_attempts = 2
    attempt = 1
    while True:
        try:
            output = invoke_model(provider, prompt, schema)
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            UnicodeDecodeError,
        ) as error:
            if should_retry_generation(attempt, maximum_attempts, error):
                attempt += 1
                continue
            raise

        try:
            value = extract_structured_text(provider, output, field_name)
            validator(value)
            return value
        except ValueError as error:
            if should_retry_generation(attempt, maximum_attempts, error):
                attempt += 1
                continue
            raise


def should_retry_generation(
    attempt: int,
    maximum_attempts: int,
    error: (
        subprocess.TimeoutExpired
        | subprocess.CalledProcessError
        | UnicodeDecodeError
        | ValueError
    ),
) -> bool:
    """生成失敗を通知して再試行できるかを返す。"""
    if attempt >= maximum_attempts:
        return False

    if isinstance(error, subprocess.CalledProcessError):
        message = format_model_command_failure(error)
    elif isinstance(error, subprocess.TimeoutExpired):
        message = "AI コマンドが制限時間内に完了しませんでした"
    elif isinstance(error, UnicodeDecodeError):
        message = "AI コマンドの出力が UTF-8 ではありません"
    else:
        message = str(error)

    print(
        f"AI による生成に失敗したため再試行します: {message}",
        file=sys.stderr,
    )
    return True


def invoke_model(
    provider: Provider,
    prompt: str,
    schema: dict[str, object],
) -> str:
    """指定した AI CLI を隔離した一時ディレクトリで実行する。"""
    schema_json = json.dumps(schema, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix="ai-commit-") as temporary_directory:
        working_directory = Path(temporary_directory)

        if provider == "codex":
            schema_path = working_directory / "schema.json"
            output_path = working_directory / "output.json"
            schema_path.write_text(schema_json, encoding="utf-8")
            command = [
                "codex",
                "exec",
                "--model",
                "gpt-5.6-luna",
                "--config",
                'model_reasoning_effort="medium"',
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ]
            run_model_command(command, prompt, working_directory)
            return output_path.read_text(encoding="utf-8")

        if provider == "claude":
            command = [
                "claude",
                "--print",
                "--model",
                "sonnet",
                "--effort",
                "medium",
                "--safe-mode",
                "--tools",
                "",
                "--no-session-persistence",
                "--output-format",
                "json",
                "--json-schema",
                schema_json,
            ]
            return run_model_command(command, prompt, working_directory)

        raise ValueError(f"未対応の AI が指定されました: {provider}")


def run_model_command(
    command: list[str],
    prompt: str,
    working_directory: Path,
) -> str:
    """AI CLI を実行して標準出力を返す。"""
    timeout_seconds = 300
    result = subprocess.run(
        command,
        cwd=working_directory,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=timeout_seconds,
        check=True,
    )
    return result.stdout


def extract_structured_text(
    provider: Provider,
    output: str,
    field_name: str,
) -> str:
    """AI CLI の JSON から指定した文字列フィールドを取得する。"""
    payload: object = json.loads(output)

    if not isinstance(payload, dict):
        raise ValueError("AI の出力が JSON オブジェクトではありません")

    if provider == "codex":
        structured_output = payload
    elif provider == "claude":
        if "structured_output" not in payload:
            raise ValueError("Claude の出力に structured_output がありません")
        structured_output = payload["structured_output"]
        if not isinstance(structured_output, dict):
            raise ValueError("Claude の structured_output が不正です")
    else:
        raise ValueError(f"未対応の AI が指定されました: {provider}")

    if field_name not in structured_output:
        raise ValueError(f"AI の出力に {field_name} がありません")
    value = structured_output[field_name]
    if not isinstance(value, str):
        raise ValueError(f"AI の {field_name} が文字列ではありません")
    return value


def validate_summary(summary: str) -> None:
    """部分要約の空白と長さを検証する。"""
    if summary == "":
        raise ValueError("AI の部分要約が空です")
    if summary != summary.strip():
        raise ValueError("AI の部分要約に不要な前後空白があります")
    if len(summary) > MAX_SUMMARY_CHARACTERS:
        raise ValueError("AI の部分要約が長すぎます")


def validate_commit_message(commit_message: str) -> None:
    """コミットメッセージの形式と言語を検証する。"""
    commit_message_pattern = re.compile(
        r"^(?:feat|fix|docs|style|refactor|test|chore)"
        r"(?:\([a-z][a-z0-9-]*\))?: (?P<description>[^\r\n]+)$"
    )
    japanese_character_pattern = re.compile(r"[ぁ-んァ-ヶ一-龯々]")
    if commit_message != commit_message.strip():
        raise ValueError("コミットメッセージに不要な前後空白があります")
    match = commit_message_pattern.fullmatch(commit_message)
    if match is None:
        raise ValueError(
            "コミットメッセージが Conventional Commits の一行形式ではありません"
        )
    description = match.group("description")
    if japanese_character_pattern.search(description) is None:
        raise ValueError("コミットメッセージの説明が日本語ではありません")


def split_diff_chunks(staged_diff: str) -> list[str]:
    """staged diff を構造を保ったチャンクへ分割する。"""
    lockfile_names = frozenset(
        {
            "Cargo.lock",
            "Gemfile.lock",
            "composer.lock",
            "package-lock.json",
            "pnpm-lock.yaml",
            "poetry.lock",
            "uv.lock",
            "yarn.lock",
        }
    )
    sections = [
        condense_lockfile_section(section, lockfile_names)
        for section in split_file_sections(staged_diff)
    ]
    fragments: list[str] = []
    for section in sections:
        fragments.extend(split_file_section(section))
    return pack_fragments(fragments)


def split_file_sections(staged_diff: str) -> list[str]:
    """diff をファイル境界で分割する。"""
    sections: list[str] = []
    current_lines: list[str] = []
    for line in staged_diff.splitlines(keepends=True):
        if line.startswith("diff --git ") and len(current_lines) > 0:
            sections.append("".join(current_lines))
            current_lines = []
        current_lines.append(line)
    if len(current_lines) > 0:
        sections.append("".join(current_lines))
    if len(sections) == 0:
        raise RuntimeError("staged diff をファイル単位に分割できませんでした")
    return sections


def condense_lockfile_section(
    section: str,
    lockfile_names: frozenset[str],
) -> str:
    """指定された lockfile の本文を省略して差分メタデータだけを残す。"""
    first_line = section.partition("\n")[0]
    is_lockfile = any(f"/{name}" in first_line for name in lockfile_names)
    if is_lockfile is False:
        return section

    metadata_prefixes = (
        "diff --git ",
        "index ",
        "new file mode ",
        "deleted file mode ",
        "old mode ",
        "new mode ",
        "similarity index ",
        "rename from ",
        "rename to ",
        "--- ",
        "+++ ",
        "Binary files ",
    )
    metadata_lines = [
        line
        for line in section.splitlines(keepends=True)
        if line.startswith(metadata_prefixes)
    ]
    return "".join(metadata_lines) + "lockfile の差分本文は省略しました\n"


def split_file_section(section: str) -> list[str]:
    """一つのファイル差分を hunk と行の境界で分割する。"""
    if len(section) <= MAX_CHUNK_CHARACTERS:
        return [section]

    lines = section.splitlines(keepends=True)
    hunk_indexes = [index for index, line in enumerate(lines) if line.startswith("@@ ")]
    if len(hunk_indexes) == 0:
        return split_lines_with_prefix(lines[0], lines[1:])

    header = "".join(lines[: hunk_indexes[0]])
    fragments: list[str] = []
    for position, hunk_index in enumerate(hunk_indexes):
        if position + 1 < len(hunk_indexes):
            next_hunk_index = hunk_indexes[position + 1]
        else:
            next_hunk_index = len(lines)
        hunk_lines = lines[hunk_index:next_hunk_index]
        prefix = header + hunk_lines[0]
        hunk_length = len(prefix) + sum(len(line) for line in hunk_lines[1:])
        if hunk_length <= MAX_CHUNK_CHARACTERS:
            fragments.append(prefix + "".join(hunk_lines[1:]))
        else:
            fragments.extend(split_lines_with_prefix(prefix, hunk_lines[1:]))
    return fragments


def split_lines_with_prefix(prefix: str, lines: list[str]) -> list[str]:
    """長い hunk をヘッダー付きの行境界で分割する。"""
    capacity = MAX_CHUNK_CHARACTERS - len(prefix)
    if capacity < 1:
        raise RuntimeError("diff のファイルヘッダーまたは hunk ヘッダーが長すぎます")
    if len(lines) == 0:
        return [prefix]

    fragments: list[str] = []
    current = ""
    for line in lines:
        if len(line) > capacity:
            if current != "":
                fragments.append(prefix + current)
                current = ""
            fragments.extend(split_long_line_with_prefix(prefix, line))
            continue
        if len(current) + len(line) > capacity:
            fragments.append(prefix + current)
            current = ""
        current += line
    if current != "":
        fragments.append(prefix + current)
    return fragments


def split_long_line_with_prefix(prefix: str, line: str) -> list[str]:
    """一行で上限を超える差分をヘッダー付きの文字境界で分割する。"""
    capacity = MAX_CHUNK_CHARACTERS - len(prefix)
    if capacity < 1:
        raise RuntimeError("diff のファイルヘッダーまたは hunk ヘッダーが長すぎます")
    if len(line) <= capacity:
        raise ValueError("文字分割の対象行がチャンク上限を超えていません")
    return [
        prefix + line[start : start + capacity]
        for start in range(0, len(line), capacity)
    ]


def pack_fragments(fragments: list[str]) -> list[str]:
    """小さい差分断片を上限まで同じチャンクへまとめる。"""
    chunks: list[str] = []
    current = ""
    for fragment in fragments:
        if len(fragment) > MAX_CHUNK_CHARACTERS:
            raise RuntimeError("分割後の diff がチャンク上限を超えています")
        separator = "\n" if current != "" else ""
        candidate = current + separator + fragment
        if len(candidate) <= MAX_CHUNK_CHARACTERS:
            current = candidate
            continue
        chunks.append(current)
        current = fragment
    if current != "":
        chunks.append(current)
    if len(chunks) == 0:
        raise RuntimeError("staged diff のチャンクを作成できませんでした")
    return chunks


def select_evenly(values: list[str], selected_count: int) -> list[str]:
    """リスト全体から指定件数を均等に抽出する。"""
    if selected_count < 1:
        raise ValueError("抽出件数は一件以上である必要があります")
    if selected_count > len(values):
        raise ValueError("抽出件数が対象件数を超えています")
    if selected_count == len(values):
        return list(values)
    if selected_count == 1:
        return [values[len(values) // 2]]
    indexes = [
        index * (len(values) - 1) // (selected_count - 1)
        for index in range(selected_count)
    ]
    return [values[index] for index in indexes]


if __name__ == "__main__":
    main()
