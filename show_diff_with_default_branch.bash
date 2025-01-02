# 現在のコミットとupstreamデフォルトブランチとの差分を表示する。
# 共通の枝分かれcommitを探して、そのcommitからHEADまでの差分を表示する。

function show_diff_with_default_branch() {
  # 必要なコマンドがあるか確認
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
    return 1
  fi

  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  # リモート名を取得
  local remote="upstream"
  if ! git remote get-url upstream &>/dev/null; then
    remote="origin"
  fi

  # デフォルトブランチの確認
  local default_branch
  default_branch=$(gh repo view --json defaultBranchRef -q ".defaultBranchRef.name" 2>/dev/null || true)

  if [ -z "$default_branch" ]; then
    if git ls-remote --heads "$remote" main &>/dev/null; then
      default_branch="main"
    elif git ls-remote --heads "$remote" master &>/dev/null; then
      default_branch="master"
    else
      echo "エラー: リモートのデフォルトブランチ(mainまたはmaster)が見つかりません。" >&2
      return 1
    fi
  fi

  echo "リモート: $remote"
  echo "デフォルトブランチ: $default_branch"

  # デフォルトブランチをフェッチ
  echo "デフォルトブランチをフェッチします..."
  if ! git fetch "$remote" "$default_branch"; then
    echo "エラー: リモートブランチのフェッチに失敗しました。" >&2
    return 1
  fi

  # 比較対象を設定
  local target
  target="$remote/$default_branch"

  # 現在のcommit(HEAD) とターゲット($target)の共通の枝分かれcommitを探す
  local merge_base
  merge_base=$(git merge-base HEAD "$target" 2>/dev/null)
  if [ -z "$merge_base" ]; then
    echo "エラー: 現在のブランチと${target}に共通のコミットが見つかりません。" >&2
    return 1
  fi

  # 差分を表示
  echo "現在のコミット(HEAD) と ${target} の共通の枝分かれ (${merge_base}) との差分を表示します:"
  if ! git diff -w --color-moved=dimmed-zebra --color-moved-ws=ignore-all-space "$merge_base" HEAD; then
    echo "エラー: 差分の取得に失敗しました。" >&2
    return 1
  fi

  return 0
}
