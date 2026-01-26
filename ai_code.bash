# git worktreeを作成してClaude Code CLIを起動し、並列でCodexにブランチ名を提案させる
# 初期ブランチ名: ai/YYYYMMDD-HHMMSS-ランダム8文字
# Codex提案後: ai/提案名-同じランダム8文字

function hiho_ai_code() {
  local CODEX_TIMEOUT=15
  local RANDOM_SUFFIX_LENGTH=8

  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。" >&2
    return 1
  fi
  if ! command -v codex >/dev/null; then
    echo "エラー: codexコマンドが見つかりません。" >&2
    return 1
  fi
  if ! command -v claude >/dev/null; then
    echo "エラー: claudeコマンドが見つかりません。" >&2
    return 1
  fi
  if ! command -v jq >/dev/null; then
    echo "エラー: jqコマンドが見つかりません。" >&2
    return 1
  fi

  local prompt=""

  if [ $# -gt 0 ]; then
    prompt="$*"
  elif [ ! -t 0 ]; then
    prompt=$(cat)
  else
    echo "タスクの内容を入力してください (Ctrl+Dで終了):"
    prompt=$(cat)
  fi

  if [ -z "$prompt" ]; then
    echo "エラー: プロンプトが空です。" >&2
    return 1
  fi

  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "エラー: gitリポジトリ内で実行してください。" >&2
    return 1
  fi

  local repo_root
  repo_root=$(git rev-parse --show-toplevel)
  local timestamp
  timestamp=$(date +'%Y%m%d-%H%M%S')
  local random_suffix
  random_suffix=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c "$RANDOM_SUFFIX_LENGTH")
  local initial_branch="ai/${timestamp}-${random_suffix}"

  local worktrees_dir="${repo_root}.worktrees"
  local worktree_path="${worktrees_dir}/${initial_branch}"

  mkdir -p "$worktrees_dir"

  if ! git worktree add "$worktree_path" -b "$initial_branch" 2>/dev/null; then
    echo "エラー: worktreeの作成に失敗しました。" >&2
    return 1
  fi

  local codex_output_file
  codex_output_file=$(mktemp)
  local codex_schema_file
  codex_schema_file=$(mktemp)
  trap 'rm -f "$codex_output_file" "$codex_schema_file"' EXIT

  cat > "$codex_schema_file" <<'EOF'
{
  "type": "object",
  "properties": {
    "branchName": {
      "type": "string"
    }
  },
  "required": ["branchName"],
  "additionalProperties": false
}
EOF

  (
    local codex_prompt="Generate a git branch name for this task: '${prompt}'. Use kebab-case with prefix (feature/fix/refactor/docs/test). Max 50 chars."

    if timeout "${CODEX_TIMEOUT}s" codex exec --output-last-message "$codex_output_file" --output-schema "$codex_schema_file" "$codex_prompt" 2>/dev/null; then
      local suggested_name
      suggested_name=$(jq -r '.branchName' "$codex_output_file" 2>/dev/null)

      if [ -n "$suggested_name" ] && [[ "$suggested_name" =~ ^[a-z0-9/_-]+$ ]] && [ ${#suggested_name} -le 50 ]; then
        local new_branch="ai/${suggested_name}-${random_suffix}"

        cd "$worktree_path" || exit
        git branch -m "$new_branch" 2>/dev/null
      fi
    fi
  ) &

  cd "$worktree_path" || return 1

  if [ -d "${repo_root}/.claude" ] && [ ! -e ".claude" ]; then
    ln -s "${repo_root}/.claude" .claude
  fi

  claude --permission-mode acceptEdits "$prompt"

  return 0
}
