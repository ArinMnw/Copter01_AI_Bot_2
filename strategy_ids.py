"""Canonical strategy identifiers, including legacy EA order/state aliases."""

import re


def normalize_sid(value):
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in ("435", "435.0", "ea2"):
        return "ea2"
    if token in ("436", "436.0", "ea2.1"):
        return "ea2.1"
    if token == "6i":
        return 7
    try:
        number = float(token)
        return int(number) if number.is_integer() else number
    except ValueError:
        return None


def sid_sort_key(value):
    sid = normalize_sid(value)
    return (1, str(sid)) if isinstance(sid, str) else (0, sid or 0)


def ea_comment_meta(comment):
    """Read new EA labels and legacy S435/S436 comments without changing orders."""
    match = re.match(
        r"^(\[[\w-]+\]|M\d+|H\d+|D\d+)_(?:S)?(ea2(?:\.1)?|435|436)(?=_|$)",
        str(comment or ""), re.IGNORECASE,
    )
    return (match.group(1), normalize_sid(match.group(2))) if match else None


def migrate_sid_metadata(value):
    """Normalize only SID fields; keep ticket keys, prices and other state intact."""
    if isinstance(value, dict):
        return {
            key: normalize_sid(item) if key in ("sid", "strategy_id", "confirmed_sid")
            else migrate_sid_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [migrate_sid_metadata(item) for item in value]
    return value
