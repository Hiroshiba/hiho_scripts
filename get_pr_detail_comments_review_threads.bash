#!/bin/bash

# プルリクエストの詳細とコメントとレビュースレッドを取得する関数
function hiho_get_pr_detail_comments_review_threads() {
  # 依存コマンド確認
  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  # ローカル変数
  local owner=""
  local repo=""
  local pr_number=""

  # 引数の数に応じて処理を分岐
  if [ $# -eq 1 ]; then
    # pr_numberのみ指定された場合、owner/repoは自動取得
    pr_number="$1"
    owner=$(gh repo view --json owner -q '.owner.login' 2>/dev/null || true)
    repo=$(gh repo view --json name -q '.name' 2>/dev/null || true)
    if [ -z "$owner" ] || [ -z "$repo" ]; then
      echo "エラー: リポジトリ情報を取得できませんでした。owner/repoを明示的に指定するか、Gitリポジトリ内で実行してください。" >&2
      return 1
    fi
  elif [ $# -eq 3 ]; then
    # owner, repo, pr_numberが全て指定された場合
    owner="$1"
    repo="$2"
    pr_number="$3"
  else
    echo "使い方: hiho_get_pr_detail_comments_review_threads [<owner> <repo>] <pr_number>" >&2
    echo "  owner/repoを省略した場合、現在のリポジトリから自動取得します。" >&2
    return 1
  fi

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
      author {
        login
      }
      createdAt
      state
      body
      reviewThreads(first: 100) {
        nodes {
          isResolved
          isOutdated
          path
          line
          startLine
          comments(first: 100) {
            nodes {
              databaseId
              body
              author {
                login
              }
              createdAt
            }
          }
        }
      }
      comments(first: 100) {
        nodes {
          databaseId
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
