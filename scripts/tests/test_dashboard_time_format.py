from datetime import datetime, timezone

from scripts.dashboard.time_format import format_dashboard_datetime


def test_format_dashboard_datetime_humanizes_iso_timestamp():
    value = datetime(2026, 4, 9, 13, 1, 20, tzinfo=timezone.utc)
    rendered = format_dashboard_datetime(value, style="full")
    assert "Thursday, April 9, 2026" in rendered
    assert "at" in rendered


def test_format_dashboard_datetime_supports_compact_style():
    value = "2026-04-09T16:26:05.733827Z"
    rendered = format_dashboard_datetime(value, style="compact")
    assert "Apr 9, 2026" in rendered

