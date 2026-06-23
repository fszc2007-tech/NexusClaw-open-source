from __future__ import annotations

from typing import Any

try:
    from opencc import OpenCC
except Exception:  # noqa: BLE001
    OpenCC = None


_traditional_converter = OpenCC("s2t") if OpenCC else None


def to_traditional_text(text: str | None) -> str | None:
    if not text:
        return text
    if _traditional_converter is None:
        return text
    return _traditional_converter.convert(text)


def to_traditional_data(value: Any) -> Any:
    if isinstance(value, str):
        return to_traditional_text(value)
    if isinstance(value, list):
        return [to_traditional_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(to_traditional_data(item) for item in value)
    if isinstance(value, dict):
        return {key: to_traditional_data(item) for key, item in value.items()}
    return value


def format_reply_text(text: str, reply_locale: str = "zh-Hant") -> str:
    if reply_locale != "zh-Hant" or not text:
        return text
    normalized = to_traditional_text(text)
    return normalized if normalized is not None else text
