# 指定された拡張子のファイル内容をクリップボードにコピーする

function hiho_pbcopy_files() {
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
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
    local has_files=false

    while IFS= read -r -d '' file; do
      has_files=true
      output+="========\n"
      output+="File: $file\n"
      output+="========\n\n"
      output+="$(cat "$file")\n\n"
      file_count=$((file_count + 1))
    done < <(git ls-files -z "*.${ext}")

    if [ "$has_files" = false ]; then
      echo "エラー: 拡張子 '.${ext}' のファイルがgitリポジトリに見つかりません" >&2
    fi
  done

  if [ -z "$output" ]; then
    echo "エラー: 指定された拡張子のファイルが見つかりませんでした" >&2
    return 1
  fi
  
  function to_clipboard() {
    # クリップボードコマンドを検出
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
  echo "${file_count}個のファイルをクリップボードにコピーしました"
}
