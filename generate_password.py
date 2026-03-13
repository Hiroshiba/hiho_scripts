#!/usr/bin/env python3
"""パスワードを生成して stdout に出力するスクリプト"""

import argparse
import secrets
import string
import sys

_DEFAULT_CHARSET = "default"
_ALNUM_CHARSET = "alnum"
_SYMBOLS_CHARSET = "symbols"

_EXTRA_SYMBOLS = "!@#$%^&*()+=[]{}|;:,.<>?/~"


def main() -> None:
    length, mode = parse_arguments()

    if length < 1:
        print("エラー: 文字数は1以上を指定してください。", file=sys.stderr)
        sys.exit(1)

    charset = build_charset(mode)
    password = generate_password(length, charset)
    print(password)


def parse_arguments() -> tuple[int, str]:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description="パスワードを生成して stdout に出力する")
    parser.add_argument("-l", "--length", type=int, default=16, help="パスワードの文字数（デフォルト: 16）")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-a", "--alnum", action="store_true", help="英数字のみ（A-Za-z0-9）")
    group.add_argument("-s", "--symbols", action="store_true", help="記号を含める")

    args = parser.parse_args()

    if args.alnum:
        mode = _ALNUM_CHARSET
    elif args.symbols:
        mode = _SYMBOLS_CHARSET
    else:
        mode = _DEFAULT_CHARSET

    return args.length, mode


def build_charset(mode: str) -> str:
    """モードに応じた文字セットを構築する"""
    base = string.ascii_letters + string.digits
    if mode == _ALNUM_CHARSET:
        return base
    if mode == _DEFAULT_CHARSET:
        return base + "-_"
    if mode == _SYMBOLS_CHARSET:
        return base + "-_" + _EXTRA_SYMBOLS
    raise ValueError(f"不明なモード: {mode}")


def generate_password(length: int, charset: str) -> str:
    """指定された文字セットからパスワードを生成する"""
    return "".join(secrets.choice(charset) for _ in range(length))


if __name__ == "__main__":
    main()
