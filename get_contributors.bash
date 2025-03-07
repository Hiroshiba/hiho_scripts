# commit Aからcommit Bまでの貢献者リストを取得する

function hiho_get_contributors() {
  # 必要なコマンドがあるか確認
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
    return 1
  fi

  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  if ! command -v jq >/dev/null; then
    echo "エラー: jqコマンドが見つかりません。jqコマンドをインストールしてください。" >&2
    return 1
  fi

  # 引数処理
  usage() {
    echo "使い方: get_contributors <commit-or-branch-A> [<commit-or-branch-B>]"
    echo "  commitBが省略された場合、upstream/mainまたはupstream/masterの存在する方をデフォルトとします。"
  }

  if [ $# -eq 0 ]; then
    usage
    return 1
  fi

  local COMMIT_A
  local COMMIT_B
  if [ $# -eq 1 ]; then
    COMMIT_A="$1"
    if git rev-parse --verify upstream/main >/dev/null 2>&1; then
      COMMIT_B="upstream/main"
    elif git rev-parse --verify upstream/master >/dev/null 2>&1; then
      COMMIT_B="upstream/master"
    else
      echo "エラー: upstream/main も upstream/master も存在しません。初期点を指定してください。" >&2
      return 1
    fi
  else
    COMMIT_A="$1"
    COMMIT_B="$2"
  fi

  # 準備ログ
  echo "A側の指定: ${COMMIT_A}"
  echo "B側の指定: ${COMMIT_B}"
  echo "コミット範囲を取得中..."

  # コミット範囲チェック
  if ! git rev-parse --verify "${COMMIT_A}" >/dev/null 2>&1; then
    echo "エラー: 指定されたA側(${COMMIT_A})が存在しません。" >&2
    return 1
  fi

  if ! git rev-parse --verify "${COMMIT_B}" >/dev/null 2>&1; then
    echo "エラー: 指定されたB側(${COMMIT_B})が存在しません。" >&2
    return 1
  fi

  # リポジトリ情報取得
  echo "リポジトリ情報を取得します..."
  local REPO_JSON
  REPO_JSON=$(gh repo view --json name,owner 2>/dev/null || true)
  if [ -z "$REPO_JSON" ]; then
    echo "エラー: ghコマンドでリポジトリ情報を取得できませんでした。" >&2
    return 1
  fi
  local REPO_OWNER
  local REPO_NAME
  REPO_OWNER=$(echo "$REPO_JSON" | jq -r '.owner.login')
  REPO_NAME=$(echo "$REPO_JSON" | jq -r '.name')
  if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    echo "エラー: リポジトリオーナーまたは名前が取得できませんでした。" >&2
    return 1
  fi

  echo "対象リポジトリ: ${REPO_OWNER}/${REPO_NAME}"

  # コミット一覧取得
  local COMMITS
  COMMITS=$(git rev-list "${COMMIT_A}..${COMMIT_B}" || true)
  if [ -z "$COMMITS" ]; then
    echo "指定範囲にコミットがありません。"
    return 0
  fi

  echo "コミット数: $(echo "$COMMITS" | wc -l)"

  # コミットごとにGitHub上のauthor.loginを取得
  declare -A AUTHORS
  local i=0
  echo "GitHub APIからコミットごとの著者(login)を取得します..."
  while IFS= read -r COMMIT_SHA; do
    i=$((i + 1))
    echo "${i}件目のコミット(${COMMIT_SHA})の著者情報を取得中..."
    local LOGIN
    LOGIN=$(gh api "repos/${REPO_OWNER}/${REPO_NAME}/commits/${COMMIT_SHA}" --jq '.author.login' 2>/dev/null || true)
    echo "  -> ログイン名: ${LOGIN}"
    if [ "$LOGIN" = "null" ] || [ -z "$LOGIN" ]; then
      echo "警告: このコミットにはGitHubユーザーが紐付いていないようです。スキップします。"
      continue
    fi
    if [ "$LOGIN" = "github-actions[bot]" ]; then
      echo "github-actions[bot]は除外します。"
      continue
    fi
    AUTHORS["$LOGIN"]=1
  done <<<"$COMMITS"

  # 結果表示
  echo "コミッター一覧:"
  for AUTHOR in $(printf "%s\n" "${!AUTHORS[@]}" | sort); do
    echo "$AUTHOR"
  done
}
