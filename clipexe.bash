# 標準入力のテキストをWindowsクリップボードにコピーする

function hiho_clipexe() {
  if ! command -v powershell.exe >/dev/null; then
    echo "エラー: powershell.exeが見つかりません。" >&2
    return 1
  fi

  powershell.exe -NoProfile -Command '$ms = New-Object IO.MemoryStream; [Console]::OpenStandardInput().CopyTo($ms); $text = [Text.UTF8Encoding]::new($false, $true).GetString($ms.ToArray()); Set-Clipboard -Value $text'
}
