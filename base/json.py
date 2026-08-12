"""JSON 値を厳密に検証する関数を提供する"""

import json


def parse_json(text: str, context: str) -> object:
    """JSON 文字列を解析する"""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{context}を JSON として解析できませんでした。") from error


def require_json_object(value: object, context: str) -> dict[str, object]:
    """値が文字列キーの JSON オブジェクトであることを検証する"""
    if not isinstance(value, dict):
        raise RuntimeError(f"{context}が JSON オブジェクトではありません。")
    for key in value:
        if not isinstance(key, str):
            raise RuntimeError(f"{context}に文字列ではないキーがあります。")
    return value


def require_json_list(value: object, context: str) -> list[object]:
    """値が JSON 配列であることを検証する"""
    if not isinstance(value, list):
        raise RuntimeError(f"{context}が JSON 配列ではありません。")
    return value


def require_string(data: dict[str, object], key: str, context: str) -> str:
    """必須項目を文字列として取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    value = data[key]
    if not isinstance(value, str):
        raise RuntimeError(f"{context}の {key} が文字列ではありません。")
    return value


def require_nullable_string(
    data: dict[str, object], key: str, context: str
) -> str | None:
    """必須項目を null 許容文字列として取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    value = data[key]
    if value is not None and not isinstance(value, str):
        raise RuntimeError(f"{context}の {key} が文字列または null ではありません。")
    return value


def require_boolean(data: dict[str, object], key: str, context: str) -> bool:
    """必須項目を boolean として取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    value = data[key]
    if not isinstance(value, bool):
        raise RuntimeError(f"{context}の {key} が boolean ではありません。")
    return value


def require_nullable_boolean(
    data: dict[str, object], key: str, context: str
) -> bool | None:
    """必須項目を null 許容 boolean として取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    value = data[key]
    if value is not None and not isinstance(value, bool):
        raise RuntimeError(f"{context}の {key} が boolean または null ではありません。")
    return value


def require_integer(data: dict[str, object], key: str, context: str) -> int:
    """必須項目を整数として取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    value = data[key]
    if type(value) is not int:
        raise RuntimeError(f"{context}の {key} が整数ではありません。")
    return value


def require_object(
    data: dict[str, object], key: str, context: str
) -> dict[str, object]:
    """必須項目を JSON オブジェクトとして取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    return require_json_object(data[key], f"{context}の {key}")


def require_list(data: dict[str, object], key: str, context: str) -> list[object]:
    """必須項目を JSON 配列として取得する"""
    if key not in data:
        raise RuntimeError(f"{context}に {key} がありません。")
    return require_json_list(data[key], f"{context}の {key}")
