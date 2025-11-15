# 指定された拡張子のファイル内容をクリップボードにコピーする

function hiho_pbcopy_files() {
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
    return 1
  fi

  if ! command -v pbcopy >/dev/null; then
    echo "エラー: pbcopyコマンドが見つかりません。pbcopyコマンドをインストールしてください。" >&2
    return 1
  fi

  if [ $# -eq 0 ]; then
    echo "使い方: hiho_pbcopy_files <拡張子> [拡張子2 ...]"
    echo "例: hiho_pbcopy_files py"
    echo "例: hiho_pbcopy_files py yaml"
    return 1
  fi

  local output=""
  local file_count=0

  for ext in "$@"; do
    local files
    files=$(git ls-files "*.${ext}")

    if [ -z "$files" ]; then
      echo "エラー: 拡張子 '.${ext}' のファイルがgitリポジトリに見つかりません" >&2
      continue
    fi

    while IFS= read -r file; do
      output+="========\n"
      output+="File: $file\n"
      output+="========\n\n"
      output+="$(cat "$file")\n\n"
      file_count=$((file_count + 1))
    done <<< "$files"
  done

  if [ -z "$output" ]; then
    echo "エラー: 指定された拡張子のファイルが見つかりませんでした" >&2
    return 1
  fi

  echo -e "$output" | pbcopy
  echo "${file_count}個のファイルをクリップボードにコピーしました"
}
