#!/bin/bash

# プルリクエストのレビュースレッドとコメントを取得する関数
function hiho_get_pr_review_threads() {
  # 依存コマンド確認
  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  # 引数チェック
  if [ $# -ne 3 ]; then
    echo "使い方: hiho_get_pr_review_threads <owner> <repo> <pr_number>" >&2
    return 1
  fi

  # ローカル変数
  local owner="$1"
  local repo="$2"
  local pr_number="$3"

  # PR番号のバリデーション
  if ! [[ "$pr_number" =~ ^[0-9]+$ ]]; then
    echo "エラー: PR番号は数値で指定してください: $pr_number" >&2
    return 1
  fi

  # GraphQLクエリの実行
  local query
  query=$(cat <<EOF
{
  repository(owner: "${owner}", name: "${repo}") {
    pullRequest(number: ${pr_number}) {
      title
      state
      reviewDecision
      reviewThreads(first: 50) {
        nodes {
          isResolved
          isOutdated
          path
          line
          startLine
          comments(first: 30) {
            nodes {
              body
              author {
                login
              }
              createdAt
            }
          }
        }
      }
      comments(first: 30) {
        nodes {
          body
          author {
            login
          }
          createdAt
        }
      }
    }
  }
}
EOF
)

  set +e
  gh api graphql -f query="$query"
  local exit_code=$?
  set -e

  if [ $exit_code -ne 0 ]; then
    echo "エラー: GraphQLクエリの実行に失敗しました。" >&2
    return 1
  fi

  return 0
}
