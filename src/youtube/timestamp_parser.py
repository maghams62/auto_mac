from __future__ import annotations

import re
from typing import Optional


_COLON_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))\b")
_ALT_COLON_PATTERN = re.compile(r"\b(\d{1,2}):(\d{1,2})\b")
_MINUTE_PATTERN = re.compile(
    r"(?:around|about|at)?\s*(?:the\s+)?(\d+)\s*(?:minutes?|mins?|min|m)\s*(?:in|mark)?",
    re.IGNORECASE,
)
_SECOND_PATTERN = re.compile(
    r"(?:around|about|at)?\s*(?:the\s+)?(\d+)\s*(?:seconds?|secs?|sec|s)\s*(?:in|mark)?",
    re.IGNORECASE,
)
_HOUR_PATTERN = re.compile(
    r"(?:around|about|at)?\s*(?:the\s+)?(\d+)\s*(?:hours?|hrs?|hr|h)\s*(?:in|mark)?",
    re.IGNORECASE,
)

_WORD_NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _parts_to_seconds(parts: list[int]) -> int:
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        hours = 0
        minutes = 0
        seconds = parts[0]
    return hours * 3600 + minutes * 60 + seconds


def parse_timestamp_hint(text: str) -> Optional[int]:
    """
    Parse human-friendly timestamp hints into raw seconds.

    Supports:
        - hh:mm:ss / mm:ss / m:s
        - "around 5 minutes", "30 seconds in", "at the 2h mark"
    """

    if not text:
        return None

    if not text:
        return None

    normalized = _replace_word_numbers(text.lower().replace("-", " "))

    colon_match = _COLON_PATTERN.search(normalized)
    if colon_match:
        parts = [int(value) if value is not None else 0 for value in colon_match.groups()]
        return _parts_to_seconds(parts)

    simple_match = _ALT_COLON_PATTERN.search(normalized)
    if simple_match:
        minutes = int(simple_match.group(1))
        seconds = int(simple_match.group(2))
        return minutes * 60 + seconds

    hour_match = _HOUR_PATTERN.search(normalized)
    minute_match = _MINUTE_PATTERN.search(normalized)
    second_match = _SECOND_PATTERN.search(normalized)

    # Support combined expressions like "1 hour 5 minutes"
    total_seconds = 0
    if hour_match:
        total_seconds += int(hour_match.group(1)) * 3600
    if minute_match:
        total_seconds += int(minute_match.group(1)) * 60
    if second_match:
        total_seconds += int(second_match.group(1))

    if total_seconds > 0:
        return total_seconds

    return None


def _replace_word_numbers(text: str) -> str:
    tokens = text.split()
    result = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        value = _WORD_NUMBERS.get(token)
        if value is None:
            result.append(token)
            i += 1
            continue

        total = value
        j = i + 1
        while j < len(tokens):
            next_value = _WORD_NUMBERS.get(tokens[j])
            if next_value is None:
                break
            total += next_value
            j += 1
        result.append(str(total))
        i = j

    return " ".join(result)

