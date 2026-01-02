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

  # 一時ファイルを作成
  local temp_file
  temp_file=$(mktemp /tmp/hiho_pr_comments.XXXXXX)

  # エラー時や終了時に一時ファイルを削除
  trap 'rm -f "$temp_file"' EXIT ERR

  # PRのレビューコメント一覧を取得して一時ファイルに保存
  set +e
  gh api "repos/${owner}/${repo}/pulls/${pr_number}/comments" --paginate > "$temp_file" 2>&1
  local exit_code=$?
  set -e

  if [ $exit_code -ne 0 ]; then
    echo "エラー: PRのレビューコメント取得に失敗しました。" >&2
    cat "$temp_file" >&2
    return 1
  fi

  # 指定されたコメントIDを含むスレッド全体を取得して出力
  cat "$temp_file" | jq --arg id "$comment_id" '
    # 指定されたコメントを取得
    [.[] | select(.id == ($id | tonumber))] as $matches |
    # コメントが見つからない場合はエラー
    if ($matches | length) == 0 then
      error("指定されたコメントID \($id) が見つかりません。")
    else
      $matches[0] as $target |
      # ルートIDを特定（in_reply_to_id があればそれがルート、なければ自分自身）
      ($target.in_reply_to_id // $target.id) as $root_id |
      # スレッド全体を取得
      [.[] | select(.id == $root_id or .in_reply_to_id == $root_id)]
      | sort_by(.created_at)
      | .[]
      | {id, body, user: .user.login, path, line, in_reply_to_id, created_at}
    end
  ' 2>&1 || return 1

  return 0
}
