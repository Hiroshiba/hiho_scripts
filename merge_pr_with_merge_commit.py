#!/usr/bin/env python3
"""PR を一時的に通常マージ可能にし、マージ後に設定を復元する"""

from __future__ import annotations

from builtins import ExceptionGroup
import copy
import subprocess
import sys
import time
from dataclasses import dataclass
from urllib.parse import quote

from base.git import check_commands
from base.github import GitHubClient
from base.json import (
    require_boolean as _require_boolean,
    require_integer as _require_integer,
    require_json_list as _require_json_list,
    require_json_object as _require_json_object,
    require_list as _require_list,
    require_nullable_boolean as _require_nullable_boolean,
    require_nullable_string as _require_nullable_string,
    require_object as _require_object,
    require_string as _require_string,
)
from base.pr_parser import parse_pr_info


def main() -> None:
    """指定した PR を通常のマージコミットでマージする"""
    pr_argument = _parse_arguments()
    check_commands(["gh"])
    client = _MergeGitHubClient()
    reference = _parse_pr_reference(client, pr_argument)
    plan = _create_operation_plan(client, reference)

    _print_operation_plan(plan)
    if not _confirm_operation():
        print("キャンセルしました。設定変更とマージは行っていません。")
        return

    current_plan = _create_operation_plan(client, reference)
    _validate_operation_plan_unchanged(plan, current_plan)
    _merge_with_temporary_settings(client, current_plan)


@dataclass(frozen=True)
class _PullRequestReference:
    """GitHub の PR を一意に表す"""

    owner: str
    repository: str
    number: int

    @property
    def full_repository_name(self) -> str:
        """オーナー名を含むリポジトリ名を返す"""
        return f"{self.owner}/{self.repository}"


@dataclass(frozen=True)
class _PullRequest:
    """通常マージに必要な PR 情報を表す"""

    reference: _PullRequestReference
    title: str
    url: str
    state: str
    draft: bool
    base_branch: str
    head_branch: str
    head_sha: str
    mergeable: bool | None
    mergeable_state: str
    merged_at: str | None
    merge_commit_sha: str | None


@dataclass(frozen=True)
class _RepositorySettings:
    """リポジトリのマージ設定を表す"""

    full_name: str
    allow_merge_commit: bool


@dataclass(frozen=True)
class _RulesetChange:
    """ruleset の一時変更と復元内容を表す"""

    ruleset_id: int
    name: str
    source: str
    original_payload: dict[str, object]
    temporary_payload: dict[str, object]
    original_allowed_merge_methods: tuple[str, ...]
    temporary_allowed_merge_methods: tuple[str, ...]


@dataclass(frozen=True)
class _OperationPlan:
    """確認後に実行する通常マージ操作を表す"""

    pull_request: _PullRequest
    repository_settings: _RepositorySettings
    ruleset_changes: tuple[_RulesetChange, ...]
    uses_merge_queue: bool


class _MergeGitHubClient(GitHubClient):
    """GitHub API と PR の通常マージを実行する"""

    def merge_pull_request(
        self,
        reference: _PullRequestReference,
        head_sha: str,
        use_admin: bool,
    ) -> None:
        """PR を通常のマージコミットでマージする"""
        command = [
            "gh",
            "pr",
            "merge",
            str(reference.number),
            "--repo",
            reference.full_repository_name,
            "--merge",
            "--match-head-commit",
            head_sha,
        ]
        if use_admin:
            command.append("--admin")

        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"PR #{reference.number} の通常マージに失敗しました。\n"
                + _format_command_output(result)
            )


def _parse_arguments() -> str:
    """コマンドライン引数を解析する"""
    arguments = sys.argv[1:]
    if len(arguments) == 1 and arguments[0] in {"-h", "--help"}:
        _print_help()
        sys.exit(0)
    if len(arguments) != 1:
        print("エラー: PR を 1 個指定してください。", file=sys.stderr)
        print(
            "使い方: hiho_merge_pr_with_merge_commit <PR URL または PR 番号>",
            file=sys.stderr,
        )
        sys.exit(2)
    return arguments[0]


def _print_help() -> None:
    """コマンドの使い方を表示する"""
    print("PR を通常のマージコミットでマージし、変更した設定を元に戻します。")
    print("")
    print("使い方:")
    print("  hiho_merge_pr_with_merge_commit <PR URL または PR 番号>")
    print("")
    print("指定できる形式:")
    print("  https://github.com/owner/repo/pull/123")
    print("  owner/repo/pull/123")
    print("  pull/123")
    print("  123")


def _parse_pr_reference(
    client: _MergeGitHubClient, argument: str
) -> _PullRequestReference:
    """コマンドライン引数から PR を特定する"""
    pr_info = parse_pr_info(argument)
    if pr_info is None:
        raise RuntimeError(
            "PR を特定できませんでした。PR の URL または PR 番号を指定してください。"
        )

    has_org = "org" in pr_info
    has_repo = "repo" in pr_info
    if has_org != has_repo:
        raise RuntimeError("PR の org と repo は両方指定してください。")
    if has_org and has_repo:
        return _PullRequestReference(
            owner=pr_info["org"],
            repository=pr_info["repo"],
            number=pr_info["number"],
        )

    owner, repository = client.get_current_repository()
    return _PullRequestReference(
        owner=owner,
        repository=repository,
        number=pr_info["number"],
    )


def _create_operation_plan(
    client: _MergeGitHubClient, reference: _PullRequestReference
) -> _OperationPlan:
    """PR と適用ルールから通常マージの操作計画を作る"""
    pull_request = _get_pull_request(client, reference)
    _validate_open_pull_request(pull_request)
    repository_settings = _get_repository_settings(client, reference)
    applied_rules = _get_applied_rules(client, reference, pull_request.base_branch)
    ruleset_changes = _get_ruleset_changes(
        client,
        reference,
        repository_settings,
        applied_rules,
    )
    return _OperationPlan(
        pull_request=pull_request,
        repository_settings=repository_settings,
        ruleset_changes=ruleset_changes,
        uses_merge_queue=_uses_merge_queue(applied_rules),
    )


def _get_pull_request(
    client: _MergeGitHubClient, reference: _PullRequestReference
) -> _PullRequest:
    """GitHub API から PR 情報を取得する"""
    max_attempts = 3
    attempt = 1

    while True:
        data = _require_json_object(
            client.get_json(
                f"repos/{reference.full_repository_name}/pulls/{reference.number}"
            ),
            "PR 情報",
        )
        pull_request = _parse_pull_request(reference, data)
        if (
            pull_request.state != "open"
            or pull_request.merged_at is not None
            or pull_request.draft
            or pull_request.mergeable is not None
        ):
            return pull_request
        if attempt >= max_attempts:
            raise RuntimeError(
                f"PR #{reference.number} のマージ可能判定を取得できませんでした。"
            )

        print(
            f"PR #{reference.number} のマージ可能判定を待っています。",
            file=sys.stderr,
        )
        time.sleep(attempt)
        attempt += 1


def _parse_pull_request(
    reference: _PullRequestReference, data: dict[str, object]
) -> _PullRequest:
    """GitHub API の応答を PR 情報へ変換する"""
    base = _require_object(data, "base", "PR 情報")
    head = _require_object(data, "head", "PR 情報")
    return _PullRequest(
        reference=reference,
        title=_require_string(data, "title", "PR 情報"),
        url=_require_string(data, "html_url", "PR 情報"),
        state=_require_string(data, "state", "PR 情報"),
        draft=_require_boolean(data, "draft", "PR 情報"),
        base_branch=_require_string(base, "ref", "PR 情報の base"),
        head_branch=_require_string(head, "ref", "PR 情報の head"),
        head_sha=_require_string(head, "sha", "PR 情報の head"),
        mergeable=_require_nullable_boolean(data, "mergeable", "PR 情報"),
        mergeable_state=_require_string(data, "mergeable_state", "PR 情報"),
        merged_at=_require_nullable_string(data, "merged_at", "PR 情報"),
        merge_commit_sha=_require_nullable_string(data, "merge_commit_sha", "PR 情報"),
    )


def _validate_open_pull_request(pull_request: _PullRequest) -> None:
    """PR が通常マージを実行できる状態か検証する"""
    if pull_request.state != "open" or pull_request.merged_at is not None:
        raise RuntimeError(
            f"PR #{pull_request.reference.number} は open 状態ではありません。"
        )
    if pull_request.draft:
        raise RuntimeError(
            f"PR #{pull_request.reference.number} はドラフトのためマージできません。"
        )
    if pull_request.mergeable is False:
        raise RuntimeError(
            f"PR #{pull_request.reference.number} はコンフリクトしているためマージできません。"
        )


def _get_repository_settings(
    client: _MergeGitHubClient, reference: _PullRequestReference
) -> _RepositorySettings:
    """通常マージに関係するリポジトリ設定を取得する"""
    data = _require_json_object(
        client.get_json(f"repos/{reference.full_repository_name}"),
        "リポジトリ情報",
    )
    return _RepositorySettings(
        full_name=_require_string(data, "full_name", "リポジトリ情報"),
        allow_merge_commit=_require_boolean(
            data, "allow_merge_commit", "リポジトリ情報"
        ),
    )


def _get_applied_rules(
    client: _MergeGitHubClient,
    reference: _PullRequestReference,
    base_branch: str,
) -> list[dict[str, object]]:
    """PR の base branch に適用されるルールを取得する"""
    encoded_branch = quote(base_branch, safe="")
    raw_rules = _require_json_list(
        client.get_json(
            f"repos/{reference.full_repository_name}/rules/branches/{encoded_branch}"
        ),
        "適用ルール一覧",
    )
    return [_require_json_object(raw_rule, "適用ルール") for raw_rule in raw_rules]


def _get_ruleset_changes(
    client: _MergeGitHubClient,
    reference: _PullRequestReference,
    repository_settings: _RepositorySettings,
    applied_rules: list[dict[str, object]],
) -> tuple[_RulesetChange, ...]:
    """通常マージを拒む ruleset の一時変更を作る"""
    restricting_rulesets: dict[int, tuple[str, str, tuple[str, ...]]] = {}
    for rule in applied_rules:
        rule_type = _require_string(rule, "type", "適用ルール")
        if rule_type != "pull_request":
            continue

        methods = _get_allowed_merge_methods(rule, "適用中の pull_request ルール")
        if "merge" in methods:
            continue

        ruleset_id = _require_integer(rule, "ruleset_id", "適用ルール")
        source_type = _require_string(rule, "ruleset_source_type", "適用ルール")
        source = _require_string(rule, "ruleset_source", "適用ルール")
        rule_summary = (source_type, source, methods)
        if (
            ruleset_id in restricting_rulesets
            and restricting_rulesets[ruleset_id] != rule_summary
        ):
            raise RuntimeError(f"ruleset {ruleset_id} の適用ルールが一貫していません。")
        restricting_rulesets[ruleset_id] = rule_summary

    changes: list[_RulesetChange] = []
    for ruleset_id in sorted(restricting_rulesets):
        source_type, source, applied_methods = restricting_rulesets[ruleset_id]
        if source_type != "Repository":
            raise RuntimeError(
                f"ruleset {ruleset_id} は {source_type} ruleset です。"
                "複数リポジトリへ影響するため、このコマンドでは変更できません。"
            )
        if source.casefold() != repository_settings.full_name.casefold():
            raise RuntimeError(
                f"ruleset {ruleset_id} の所有元 {source} が対象リポジトリと一致しません。"
            )

        detail = _require_json_object(
            client.get_json(
                f"repos/{reference.full_repository_name}/rulesets/{ruleset_id}"
            ),
            f"ruleset {ruleset_id}",
        )
        change = _create_ruleset_change(
            ruleset_id,
            repository_settings,
            detail,
            applied_methods,
        )
        changes.append(change)

    return tuple(changes)


def _create_ruleset_change(
    ruleset_id: int,
    repository_settings: _RepositorySettings,
    detail: dict[str, object],
    applied_methods: tuple[str, ...],
) -> _RulesetChange:
    """ruleset 詳細から復元可能な一時変更を作る"""
    source_type = _require_string(detail, "source_type", f"ruleset {ruleset_id}")
    source = _require_string(detail, "source", f"ruleset {ruleset_id}")
    if source_type != "Repository":
        raise RuntimeError(
            f"ruleset {ruleset_id} はリポジトリ所有の ruleset ではありません。"
        )
    if source.casefold() != repository_settings.full_name.casefold():
        raise RuntimeError(
            f"ruleset {ruleset_id} の所有元 {source} が対象リポジトリと一致しません。"
        )

    original_payload = _extract_ruleset_update_payload(detail, ruleset_id)
    original_methods = _get_ruleset_pull_request_methods(original_payload, ruleset_id)
    if original_methods != applied_methods:
        raise RuntimeError(
            f"ruleset {ruleset_id} が情報取得中に変更されました。もう一度実行してください。"
        )
    if "merge" in original_methods:
        raise RuntimeError(
            f"ruleset {ruleset_id} の通常マージ設定が情報取得中に変更されました。"
        )

    temporary_payload = copy.deepcopy(original_payload)
    temporary_methods = ("merge", *original_methods)
    _replace_ruleset_pull_request_methods(
        temporary_payload,
        ruleset_id,
        temporary_methods,
    )
    return _RulesetChange(
        ruleset_id=ruleset_id,
        name=_require_string(detail, "name", f"ruleset {ruleset_id}"),
        source=source,
        original_payload=original_payload,
        temporary_payload=temporary_payload,
        original_allowed_merge_methods=original_methods,
        temporary_allowed_merge_methods=temporary_methods,
    )


def _extract_ruleset_update_payload(
    detail: dict[str, object], ruleset_id: int
) -> dict[str, object]:
    """ruleset 更新 API へ送る項目だけを取り出す"""
    payload: dict[str, object] = {}
    for key in [
        "name",
        "target",
        "enforcement",
        "bypass_actors",
        "conditions",
        "rules",
    ]:
        if key not in detail:
            raise RuntimeError(f"ruleset {ruleset_id} に {key} がありません。")
        payload[key] = copy.deepcopy(detail[key])
    return payload


def _get_ruleset_pull_request_methods(
    payload: dict[str, object], ruleset_id: int
) -> tuple[str, ...]:
    """ruleset の pull_request ルールから許可方式を取得する"""
    rules = _require_list(payload, "rules", f"ruleset {ruleset_id}")
    pull_request_rules: list[dict[str, object]] = []
    for raw_rule in rules:
        rule = _require_json_object(raw_rule, f"ruleset {ruleset_id} のルール")
        rule_type = _require_string(rule, "type", f"ruleset {ruleset_id} のルール")
        if rule_type == "pull_request":
            pull_request_rules.append(rule)
    if len(pull_request_rules) != 1:
        raise RuntimeError(
            f"ruleset {ruleset_id} の pull_request ルールが 1 個ではありません。"
        )
    return _get_allowed_merge_methods(
        pull_request_rules[0], f"ruleset {ruleset_id} の pull_request ルール"
    )


def _replace_ruleset_pull_request_methods(
    payload: dict[str, object],
    ruleset_id: int,
    methods: tuple[str, ...],
) -> None:
    """ruleset の pull_request ルールへ許可方式を設定する"""
    rules = _require_list(payload, "rules", f"ruleset {ruleset_id}")
    matched_rules = 0
    for raw_rule in rules:
        rule = _require_json_object(raw_rule, f"ruleset {ruleset_id} のルール")
        rule_type = _require_string(rule, "type", f"ruleset {ruleset_id} のルール")
        if rule_type != "pull_request":
            continue
        parameters = _require_object(
            rule,
            "parameters",
            f"ruleset {ruleset_id} の pull_request ルール",
        )
        parameters["allowed_merge_methods"] = list(methods)
        matched_rules += 1

    if matched_rules != 1:
        raise RuntimeError(
            f"ruleset {ruleset_id} の pull_request ルールが 1 個ではありません。"
        )


def _get_allowed_merge_methods(
    rule: dict[str, object], context: str
) -> tuple[str, ...]:
    """pull_request ルールの許可方式を検証して返す"""
    parameters = _require_object(rule, "parameters", context)
    raw_methods = _require_list(parameters, "allowed_merge_methods", context)
    methods: list[str] = []
    for raw_method in raw_methods:
        if not isinstance(raw_method, str):
            raise RuntimeError(f"{context} の許可方式が文字列ではありません。")
        methods.append(raw_method)
    if len(set(methods)) != len(methods):
        raise RuntimeError(f"{context} の許可方式が重複しています。")
    return tuple(methods)


def _uses_merge_queue(applied_rules: list[dict[str, object]]) -> bool:
    """適用ルールに merge queue があるか判定する"""
    return any(
        _require_string(rule, "type", "適用ルール") == "merge_queue"
        for rule in applied_rules
    )


def _print_operation_plan(plan: _OperationPlan) -> None:
    """対象 PR と一時変更する設定を表示する"""
    pull_request = plan.pull_request
    print("対象 PR:")
    print(f"  {pull_request.url}")
    print(f"  #{pull_request.reference.number} {pull_request.title}")
    print(f"  {pull_request.head_branch} → {pull_request.base_branch}")
    print(f"  GitHub のマージ状態: {pull_request.mergeable_state}")
    print("")
    print("対象 ruleset:")
    if len(plan.ruleset_changes) == 0:
        print("  変更対象なし")
    for change in plan.ruleset_changes:
        original_methods = ", ".join(change.original_allowed_merge_methods)
        temporary_methods = ", ".join(change.temporary_allowed_merge_methods)
        print(f"  {change.name}  ID {change.ruleset_id}")
        print(f"    所有元: {change.source}")
        print(f"    許可方式: {original_methods} → {temporary_methods}")
    print("")
    if plan.repository_settings.allow_merge_commit:
        print("リポジトリ全体の Allow merge commits: 有効のため変更なし")
    else:
        print("リポジトリ全体の Allow merge commits: 無効 → 一時的に有効")
    print("マージ方式: 通常のマージコミット")
    if plan.uses_merge_queue:
        print("merge queue: 管理者権限でバイパス")
    else:
        print("merge queue: 適用なし")


def _confirm_operation() -> bool:
    """通常マージを実行するか確認する"""
    try:
        answer = input("\n設定を一時変更して、この PR を通常マージしますか？ [y/N]: ")
    except EOFError:
        return False
    return answer.strip().lower() == "y"


def _validate_operation_plan_unchanged(
    original: _OperationPlan, current: _OperationPlan
) -> None:
    """確認中に PR と設定が変わっていないことを検証する"""
    original_pr = original.pull_request
    current_pr = current.pull_request
    pr_unchanged = (
        original_pr.reference == current_pr.reference
        and original_pr.base_branch == current_pr.base_branch
        and original_pr.head_branch == current_pr.head_branch
        and original_pr.head_sha == current_pr.head_sha
    )
    settings_unchanged = (
        original.repository_settings == current.repository_settings
        and original.ruleset_changes == current.ruleset_changes
        and original.uses_merge_queue == current.uses_merge_queue
    )
    if not pr_unchanged or not settings_unchanged:
        raise RuntimeError(
            "確認中に PR または設定が変更されました。もう一度実行してください。"
        )


def _merge_with_temporary_settings(
    client: _MergeGitHubClient, plan: _OperationPlan
) -> None:
    """設定を一時変更して PR をマージし、必ず設定を復元する"""
    repository_path = f"repos/{plan.repository_settings.full_name}"
    restore_repository = not plan.repository_settings.allow_merge_commit
    rulesets_to_restore: list[_RulesetChange] = []

    try:
        if restore_repository:
            print("リポジトリ全体で通常マージを一時的に有効化します。")
            _set_repository_allow_merge_commit(client, repository_path, True)

        for change in plan.ruleset_changes:
            rulesets_to_restore.append(change)
            print(f"ruleset {change.name} で通常マージを一時的に許可します。")
            _update_ruleset(
                client,
                repository_path,
                change,
                change.temporary_payload,
                change.temporary_allowed_merge_methods,
            )

        latest_pull_request = _get_pull_request(client, plan.pull_request.reference)
        _validate_pull_request_before_merge(plan.pull_request, latest_pull_request)
        print(f"PR #{plan.pull_request.reference.number} を通常マージします。")
        client.merge_pull_request(
            plan.pull_request.reference,
            plan.pull_request.head_sha,
            plan.uses_merge_queue,
        )
        merge_commit_sha = _verify_merge_commit(client, plan.pull_request.reference)
        print(f"二親のマージコミットを確認しました: {merge_commit_sha}")
    finally:
        restoration_errors: list[Exception] = []
        for change in reversed(rulesets_to_restore):
            try:
                print(f"ruleset {change.name} を元に戻します。")
                _update_ruleset(
                    client,
                    repository_path,
                    change,
                    change.original_payload,
                    change.original_allowed_merge_methods,
                )
            except Exception as error:
                restoration_errors.append(error)

        if restore_repository:
            try:
                print("リポジトリ全体の通常マージ設定を元に戻します。")
                _set_repository_allow_merge_commit(client, repository_path, False)
            except Exception as error:
                restoration_errors.append(error)

        if len(restoration_errors) > 0:
            raise ExceptionGroup("設定の復元に失敗しました。", restoration_errors)

    print("通常マージと設定の復元が完了しました。")


def _set_repository_allow_merge_commit(
    client: _MergeGitHubClient,
    repository_path: str,
    enabled: bool,
) -> None:
    """リポジトリ全体の通常マージ設定を変更して検証する"""
    response = _require_json_object(
        client.patch_json(repository_path, {"allow_merge_commit": enabled}),
        "リポジトリ設定の更新結果",
    )
    actual = _require_boolean(
        response, "allow_merge_commit", "リポジトリ設定の更新結果"
    )
    if actual != enabled:
        raise RuntimeError("リポジトリ全体の通常マージ設定を変更できませんでした。")


def _update_ruleset(
    client: _MergeGitHubClient,
    repository_path: str,
    change: _RulesetChange,
    payload: dict[str, object],
    expected_methods: tuple[str, ...],
) -> None:
    """ruleset を更新して許可方式を検証する"""
    response = _require_json_object(
        client.put_json(f"{repository_path}/rulesets/{change.ruleset_id}", payload),
        f"ruleset {change.ruleset_id} の更新結果",
    )
    response_payload = _extract_ruleset_update_payload(response, change.ruleset_id)
    actual_methods = _get_ruleset_pull_request_methods(
        response_payload, change.ruleset_id
    )
    if actual_methods != expected_methods:
        raise RuntimeError(
            f"ruleset {change.ruleset_id} の通常マージ設定を変更できませんでした。"
        )


def _validate_pull_request_before_merge(
    original: _PullRequest, latest: _PullRequest
) -> None:
    """設定変更中にも PR の対象と head が変わっていないことを検証する"""
    _validate_open_pull_request(latest)
    unchanged = (
        original.reference == latest.reference
        and original.base_branch == latest.base_branch
        and original.head_branch == latest.head_branch
        and original.head_sha == latest.head_sha
    )
    if not unchanged:
        raise RuntimeError(
            "設定変更中に PR のブランチまたは head が変わりました。マージを中止します。"
        )


def _verify_merge_commit(
    client: _MergeGitHubClient, reference: _PullRequestReference
) -> str:
    """PR が二親のマージコミットでマージされたことを検証する"""
    data = _require_json_object(
        client.get_json(
            f"repos/{reference.full_repository_name}/pulls/{reference.number}"
        ),
        "マージ後の PR 情報",
    )
    merged_at = _require_nullable_string(data, "merged_at", "マージ後の PR 情報")
    if merged_at is None:
        raise RuntimeError(
            f"PR #{reference.number} のマージ完了を確認できませんでした。"
        )
    merge_commit_sha = _require_nullable_string(
        data, "merge_commit_sha", "マージ後の PR 情報"
    )
    if merge_commit_sha is None:
        raise RuntimeError(
            f"PR #{reference.number} のマージコミットを取得できませんでした。"
        )

    commit = _require_json_object(
        client.get_json(
            f"repos/{reference.full_repository_name}/commits/{merge_commit_sha}"
        ),
        "マージコミット情報",
    )
    parents = _require_list(commit, "parents", "マージコミット情報")
    if len(parents) != 2:
        raise RuntimeError(
            f"PR #{reference.number} のコミットは二親のマージコミットではありません。"
        )
    for parent in parents:
        parent_data = _require_json_object(parent, "マージコミットの親")
        _require_string(parent_data, "sha", "マージコミットの親")
    return merge_commit_sha


def _format_command_output(result: subprocess.CompletedProcess[str]) -> str:
    """失敗したコマンドの出力を整形する"""
    output = result.stderr.strip()
    if output == "":
        output = result.stdout.strip()
    if output == "":
        return "コマンドから詳細なエラー出力がありませんでした。"
    return output


if __name__ == "__main__":
    main()
