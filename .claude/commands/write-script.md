---
name: write-script
description: bash・Python スクリプトの作成・修正
---

## タスク

```
$ARGUMENTS
```

## 準備

以下の既存ファイルを読んでパターンを把握すること:

### Bash

- get_contributors.bash
- get_pr_detail_comments_review_threads.bash
- new_branch.bash
- pbcopy_files.bash
- stash_and_pr.bash

### Python

- ai_code.py
- ai_code_pr_continue.py
- get_github_template.py
- base/worktree_manager.py
- base/pr_parser.py

## 規約

### 共通

- 配置: メインスクリプトは直下、共通モジュールは `base/`
- エラー出力: 日本語で stderr に出力

### Bash 規約

#### ファイル構成

- 拡張子: `.bash`
- 1ファイル1関数

#### フォーマット

```bash
# 関数の説明（日本語、1-2行）

function hiho_関数名() {
  # 1. 依存コマンド確認
  # 2. 引数処理 + バリデーション
  # 3. ローカル変数初期化
  # 4. メイン処理
}
```

#### コーディング規則

- 関数名: `hiho_` プレフィックス + スネークケース
- ローカル変数: 必ず `local` を付ける、スネークケース小文字
- エラー出力: `>&2` に出力
- 戻り値: エラー時 `return 1`、正常時 `return 0` または `return`
- 依存コマンド確認: `if ! command -v xxx >/dev/null; then`
- 一時ファイル使用時: `mktemp` + `trap` でクリーンアップ
- 引数バリデーション: `$#` で個数チェック
- 外部コマンド実行: `set +e` / `set -e` でエラーハンドリング
- ヘルプ: `usage()` 関数を定義

### Python 規約

#### ファイル構成

- 拡張子: `.py`
- shebang: `#!/usr/bin/env python3`
- メインスクリプトは直下、共通モジュールは `base/`

#### フォーマット

```python
#!/usr/bin/env python3
"""モジュールの説明（日本語、1-3行）"""

import ...  # 標準ライブラリ → サードパーティ → ローカルの順


def main() -> None:
    # メイン処理
    ...


def helper_function() -> None:
    """関数の説明"""
    ...


if __name__ == "__main__":
    main()
```

#### コーディング規則

- `def main() -> None:` を最上部に配置
- `if __name__ == "__main__":` を最下部に配置
- 型アノテーション: すべての関数引数と返り値に型を付与
- パス操作: `from pathlib import Path`（`os.path` は使わない）
- ファイル読み書き: `Path.read_text()` / `Path.read_bytes()`
- エラー出力: `print(..., file=sys.stderr)` + `sys.exit(1)`
- 依存コマンド確認: `shutil.which(cmd)` で存在チェック
- subprocess: `subprocess.run(..., capture_output=True, text=True)`

## .bashrc への追記

Bash スクリプト新規作成時は `.bashrc` に source 行を追加すること。
既存ファイルと同じ形式で追加: `source "${script_dir}/ファイル名.bash"`
