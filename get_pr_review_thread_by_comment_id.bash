#!/bin/bash

# プルリクエストのレビューコメントIDからスレッド全体を取得する関数
function hiho_get_pr_review_thread_by_comment_id() {
  # 依存コマンド確認
  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  if ! command -v jq >/dev/null; then
    echo "エラー: jqコマンドが見つかりません。jqコマンドをインストールしてください。" >&2
    return 1
  fi

  # ローカル変数
  local owner=""
  local repo=""
  local pr_number=""
  local comment_id=""

  # 引数の数に応じて処理を分岐
  if [ $# -eq 2 ]; then
    # pr_numberとcomment_idのみ指定された場合、owner/repoは自動取得
    pr_number="$1"
    comment_id="$2"
    owner=$(gh repo view --json owner -q '.owner.login' 2>/dev/null || true)
    repo=$(gh repo view --json name -q '.name' 2>/dev/null || true)
    if [ -z "$owner" ] || [ -z "$repo" ]; then
      echo "エラー: リポジトリ情報を取得できませんでした。owner/repoを明示的に指定するか、Gitリポジトリ内で実行してください。" >&2
      return 1
    fi
  elif [ $# -eq 4 ]; then
    # owner, repo, pr_number, comment_idが全て指定された場合
    owner="$1"
    repo="$2"
    pr_number="$3"
    comment_id="$4"
  else
    echo "使い方: hiho_get_pr_review_thread_by_comment_id [<owner> <repo>] <pr_number> <comment_id>" >&2
    echo "  owner/repoを省略した場合、現在のリポジトリから自動取得します。" >&2
    return 1
  fi

  # PR番号のバリデーション
  if ! [[ "$pr_number" =~ ^[0-9]+$ ]]; then
    echo "エラー: PR番号は数値で指定してください: $pr_number" >&2
    return 1
  fi

  # コメントIDのバリデーション
  if ! [[ "$comment_id" =~ ^[0-9]+$ ]]; then
    echo "エラー: コメントIDは数値で指定してください: $comment_id" >&2
    return 1
  fi

  # PRのレビューコメント一覧を取得
  local all_comments
  set +e
  all_comments=$(gh api "repos/${owner}/${repo}/pulls/${pr_number}/comments" --paginate 2>&1)
  local exit_code=$?
  set -e

  if [ $exit_code -ne 0 ]; then
    echo "エラー: PRのレビューコメント取得に失敗しました。" >&2
    echo "$all_comments" >&2
    return 1
  fi

  # 指定されたコメントIDのコメントを取得
  local target_comment
  target_comment=$(echo "$all_comments" | jq --arg id "$comment_id" '.[] | select(.id == ($id | tonumber))')

  if [ -z "$target_comment" ]; then
    echo "エラー: 指定されたコメントID ${comment_id} が見つかりません。" >&2
    return 1
  fi

  # スレッドのルートIDを特定
  # - in_reply_to_id があればそれがルート
  # - なければ自分自身がルート
  local root_id
  root_id=$(echo "$target_comment" | jq -r '.in_reply_to_id // empty')

  if [ -z "$root_id" ]; then
    root_id="$comment_id"
  fi

  # スレッド全体を取得（ルートID自体 または in_reply_to_id がルートIDのコメント）
  echo "$all_comments" | jq --arg root_id "$root_id" '
    [.[] | select(.id == ($root_id | tonumber) or .in_reply_to_id == ($root_id | tonumber))]
    | sort_by(.created_at)
    | .[]
    | {id, body, user: .user.login, path, line, in_reply_to_id, created_at}
  '

  return 0
}
