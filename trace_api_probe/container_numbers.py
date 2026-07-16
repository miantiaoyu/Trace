from __future__ import annotations

import re
import string


_CONTAINER_PATTERN = re.compile(r"[A-Z]{3}U[0-9]{7}")
_LETTER_VALUES = dict(
    zip(
        string.ascii_uppercase,
        (10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38),
        strict=True,
    )
)


def normalize_container_number(value: str) -> str:
    """Return a canonical ISO 6346 freight-container number."""
    container = "".join(str(value).upper().split())
    if not _CONTAINER_PATTERN.fullmatch(container):
        raise ValueError(f"柜号 {container or '(空)'} 不符合 ISO 6346 格式")

    weighted_sum = sum(_character_value(character) * (2**position) for position, character in enumerate(container[:10]))
    expected_check_digit = weighted_sum % 11 % 10
    if int(container[-1]) != expected_check_digit:
        raise ValueError(f"柜号 {container} 的 ISO 6346 校验位无效")
    return container


def _character_value(character: str) -> int:
    return int(character) if character.isdigit() else _LETTER_VALUES[character]
