from __future__ import annotations

from datetime import datetime


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or value == "":
        return None
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def format_dashboard_datetime(
    value: datetime | str | None,
    style: str = "full",
    fallback: str = "N/A",
    include_timezone: bool = False,
) -> str:
    dt = _coerce_datetime(value)
    if dt is None:
        return fallback

    if dt.tzinfo is not None:
        dt = dt.astimezone()

    if style == "compact":
        rendered = f"{dt.strftime('%b')} {dt.day}, {dt.year} {dt.strftime('%I:%M %p').lstrip('0')}"
    else:
        rendered = (
            f"{dt.strftime('%A')}, {dt.strftime('%B')} {dt.day}, {dt.year} "
            f"at {dt.strftime('%I:%M:%S %p').lstrip('0')}"
        )

    if include_timezone and dt.tzinfo is not None:
        rendered = f"{rendered} {dt.strftime('%Z')}"
    return rendered
