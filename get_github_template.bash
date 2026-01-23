# GitHub の Issue テンプレートまたは PR テンプレートを取得する

function hiho_get_github_template() {
  if ! command -v gh >/dev/null; then
    echo "エラー: gh コマンドが見つかりません。gh コマンドをインストールしてください。" >&2
    return 1
  fi

  local subcommand=""
  local owner=""
  local repo=""
  local template=""

  if [ $# -eq 0 ]; then
    echo "使い方: hiho_get_github_template <issue|pr> [-o owner] [-r repo] [-t template]" >&2
    echo "  issue: Issue テンプレートを取得（-t 省略時は一覧表示）" >&2
    echo "  pr: PR テンプレートを取得" >&2
    return 1
  fi

  subcommand="$1"
  shift

  if [ "$subcommand" != "issue" ] && [ "$subcommand" != "pr" ]; then
    echo "エラー: サブコマンドは issue または pr を指定してください。" >&2
    return 1
  fi

  while [ $# -gt 0 ]; do
    case "$1" in
      -o|--owner)
        owner="$2"
        shift 2
        ;;
      -r|--repo)
        repo="$2"
        shift 2
        ;;
      -t|--template)
        template="$2"
        shift 2
        ;;
      *)
        echo "エラー: 不明なオプション: $1" >&2
        return 1
        ;;
    esac
  done

  if [ -z "$owner" ] || [ -z "$repo" ]; then
    local repo_info
    repo_info=$(gh repo view --json owner,name 2>/dev/null || true)
    if [ -z "$repo_info" ]; then
      echo "エラー: リポジトリ情報を取得できませんでした。-o と -r を指定するか、Git リポジトリ内で実行してください。" >&2
      return 1
    fi
    if [ -z "$owner" ]; then
      owner=$(echo "$repo_info" | gh api --input - --jq '.owner.login' 2>/dev/null || true)
      if [ -z "$owner" ]; then
        owner=$(echo "$repo_info" | python3 -c "import sys,json; print(json.load(sys.stdin)['owner']['login'])" 2>/dev/null || true)
      fi
    fi
    if [ -z "$repo" ]; then
      repo=$(echo "$repo_info" | gh api --input - --jq '.name' 2>/dev/null || true)
      if [ -z "$repo" ]; then
        repo=$(echo "$repo_info" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])" 2>/dev/null || true)
      fi
    fi
  fi

  if [ -z "$owner" ] || [ -z "$repo" ]; then
    echo "エラー: owner または repo を取得できませんでした。" >&2
    return 1
  fi

  case "$subcommand" in
    issue)
      _hiho_get_issue_template "$owner" "$repo" "$template"
      ;;
    pr)
      _hiho_get_pr_template "$owner" "$repo" "$template"
      ;;
  esac
}

function _hiho_gh_api_content() {
  local api_path="$1"
  local jq_filter="$2"
  local result
  if result=$(gh api "$api_path" --jq "$jq_filter" 2>/dev/null) && [ -n "$result" ]; then
    echo "$result"
    return 0
  fi
  return 1
}

function _hiho_get_issue_template() {
  local owner="$1"
  local repo="$2"
  local template="$3"

  if [ -z "$template" ]; then
    local templates
    templates=$(_hiho_gh_api_content "repos/${owner}/${repo}/contents/.github/ISSUE_TEMPLATE" '.[].name')
    if [ -n "$templates" ]; then
      echo "Issue テンプレート一覧 (${owner}/${repo}):"
      echo "$templates"
      return 0
    fi
    templates=$(_hiho_gh_api_content "repos/${owner}/.github/contents/.github/ISSUE_TEMPLATE" '.[].name')
    if [ -n "$templates" ]; then
      echo "Issue テンプレート一覧 (${owner}/.github):"
      echo "$templates"
      return 0
    fi
    echo "エラー: Issue テンプレートが見つかりませんでした。" >&2
    return 1
  fi

  local content
  content=$(_hiho_gh_api_content "repos/${owner}/${repo}/contents/.github/ISSUE_TEMPLATE/${template}" '.content')
  if [ -n "$content" ]; then
    echo "$content" | base64 -d
    return 0
  fi

  content=$(_hiho_gh_api_content "repos/${owner}/.github/contents/.github/ISSUE_TEMPLATE/${template}" '.content')
  if [ -n "$content" ]; then
    echo "$content" | base64 -d
    return 0
  fi

  echo "エラー: Issue テンプレート '${template}' が見つかりませんでした。" >&2
  return 1
}

function _hiho_get_pr_template() {
  local owner="$1"
  local repo="$2"
  local template="$3"

  if [ -n "$template" ]; then
    local content
    content=$(_hiho_gh_api_content "repos/${owner}/${repo}/contents/.github/PULL_REQUEST_TEMPLATE/${template}" '.content')
    if [ -n "$content" ]; then
      echo "$content" | base64 -d
      return 0
    fi

    content=$(_hiho_gh_api_content "repos/${owner}/.github/contents/.github/PULL_REQUEST_TEMPLATE/${template}" '.content')
    if [ -n "$content" ]; then
      echo "$content" | base64 -d
      return 0
    fi

    echo "エラー: PR テンプレート '${template}' が見つかりませんでした。" >&2
    return 1
  fi

  local pr_paths=(
    ".github/pull_request_template.md"
    ".github/PULL_REQUEST_TEMPLATE.md"
    "docs/pull_request_template.md"
    "docs/PULL_REQUEST_TEMPLATE.md"
    "pull_request_template.md"
    "PULL_REQUEST_TEMPLATE.md"
  )

  local content
  for path in "${pr_paths[@]}"; do
    content=$(_hiho_gh_api_content "repos/${owner}/${repo}/contents/${path}" '.content')
    if [ -n "$content" ]; then
      echo "$content" | base64 -d
      return 0
    fi
  done

  for path in "${pr_paths[@]}"; do
    content=$(_hiho_gh_api_content "repos/${owner}/.github/contents/${path}" '.content')
    if [ -n "$content" ]; then
      echo "$content" | base64 -d
      return 0
    fi
  done

  echo "エラー: PR テンプレートが見つかりませんでした。" >&2
  return 1
}
