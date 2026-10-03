"""
Helpers for presenting chapter download failures to users.

The downloader reports chapter failures as human-readable messages. These
helpers turn those messages into short, stable categories for the GUI/CLI and
compress long lists of chapter numbers into readable ranges.
"""

from __future__ import annotations

CANCELLED = "cancelled"

# (category, short label, substrings). Checked in order against the
# lowercased message; the first match wins.
_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    (CANCELLED, "Cancelled", ("download cancelled",)),
    ("extraction", "Extraction incomplete", ("incomplete image extraction",)),
    ("partial", "Missing pages", ("incomplete download",)),
    ("no_images", "No images found", ("no images found", "failed to download any images")),
    ("cloudflare", "Blocked / challenge", ("cloudflare", "challenge", "403")),
    ("network", "Network error", ("timeout", "timed out", "connection", "ssl", "eof")),
]


def classify_failure(message: str | None) -> tuple[str, str]:
    """Return ``(category, label)`` for a chapter failure message."""
    lower = (message or "").lower()
    for category, label, needles in _RULES:
        if any(needle in lower for needle in needles):
            return category, label
    return "error", "Error"


def is_cancellation(message: str | None) -> bool:
    """True when the message represents a user cancellation, not an error."""
    return classify_failure(message)[0] == CANCELLED


def _as_int(value: str) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else None


def _sort_key(value: str) -> tuple[int, float, str]:
    try:
        return (0, float(value), value)
    except (TypeError, ValueError):
        return (1, 0.0, value)


def format_chapter_numbers(numbers, limit: int = 60) -> str:
    """
    Compress chapter numbers into a readable list.

    ``["1", "2", "3", "5", "7.5"]`` -> ``"1–3, 5, 7.5"``. Only consecutive
    integers are collapsed; decimals and non-numeric values are kept as-is.
    Duplicates are removed and output is sorted numerically. When more than
    ``limit`` tokens would be produced, the rest is summarised as ``+N more``.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for raw in numbers or []:
        text = str(raw).strip()
        if not text:
            continue
        as_int = _as_int(text)
        key = str(as_int) if as_int is not None else text
        if key not in seen:
            seen.add(key)
            unique.append(key)
    unique.sort(key=_sort_key)

    tokens: list[str] = []
    run_start: int | None = None
    run_end: int | None = None

    def flush() -> None:
        if run_start is None:
            return
        tokens.append(str(run_start) if run_start == run_end else f"{run_start}–{run_end}")

    for value in unique:
        as_int = _as_int(value)
        if as_int is not None and run_end is not None and as_int == run_end + 1:
            run_end = as_int
            continue
        flush()
        if as_int is None:
            run_start = run_end = None
            tokens.append(value)
        else:
            run_start = run_end = as_int
    flush()

    if limit > 0 and len(tokens) > limit:
        hidden = len(tokens) - limit
        return ", ".join(tokens[:limit]) + f", +{hidden} more"
    return ", ".join(tokens)
