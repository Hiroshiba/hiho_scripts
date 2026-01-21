# 指定されたglobパターンに一致するファイル内容をクリップボードにコピーする

function hiho_pbcopy_files() {
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
    return 1
  fi

  if [ $# -eq 0 ]; then
    echo "使い方: hiho_pbcopy_files <パターン> [パターン2 ...]"
    echo "例: hiho_pbcopy_files '*.ts'"
    echo "例: hiho_pbcopy_files 'hoge*.ts' '*test*'"
    return 1
  fi

  local output=""
  local -a files=()

  for pattern in "$@"; do
    local has_files=false

    while IFS= read -r -d '' file; do
      has_files=true
      output+="========\n"
      output+="File: $file\n"
      output+="========\n\n"
      output+="$(cat "$file")\n\n"
      files+=("$file")
    done < <(git ls-files -z "$pattern")

    if [ "$has_files" = false ]; then
      echo "エラー: パターン '${pattern}' に一致するファイルがgitリポジトリに見つかりません" >&2
    fi
  done

  if [ -z "$output" ]; then
    echo "エラー: 指定されたパターンに一致するファイルが見つかりませんでした" >&2
    return 1
  fi

  function to_clipboard() {
    if command -v pbcopy >/dev/null; then
      pbcopy
    elif command -v clip.exe >/dev/null; then
      iconv -f UTF-8 -t UTF-16LE | clip.exe
    else
      echo "エラー: クリップボードコマンドが見つかりません。" >&2
      return 1
    fi
  }

  if ! echo -e "$output" | to_clipboard; then
    return 1
  fi

  echo "${#files[@]}個のファイルをクリップボードにコピーしました:"
  for file in "${files[@]}"; do
    echo "  - $file"
  done
}
