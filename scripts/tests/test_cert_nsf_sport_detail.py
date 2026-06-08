"""NSF Sport listing-detail parser tests (lot-number extraction).

Regression for the silently-broken `--with-lots` path: the detail page is a
``<th>Field</th><td>value<br>value…</td>`` table, so lots live in the cell
adjacent to the ``Lot #`` header, not on a ``Lot #: …`` text line. The old
same-line regex required a separator the live page never emits and captured
zero lots. This locks the table-aware parser.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.verify_certifications import parse_nsf_sport_detail_html  # noqa: E402

# Shaped like the live nsfsport-prod listing-detail table.
NSF_SPORT_DETAIL_HTML = """
<table>
  <tr><th>Free of Claims</th><td>Sugar<br/>Caffeine</td></tr>
  <tr><th>Lot #</th><td>48715<br/>49759<br/>49038<br/>51019B<br/>51447A</td></tr>
  <tr><th>Product Form</th><td>Liquid</td></tr>
  <tr><th>Facility</th><td>Acme Mfg, Salt Lake City, UT</td></tr>
</table>
"""

NSF_SPORT_DETAIL_NO_LOTS = """
<table>
  <tr><th>Product Form</th><td>Capsule</td></tr>
  <tr><th>Flavor</th><td>Unflavored</td></tr>
</table>
"""


def test_parse_detail_extracts_br_separated_lots() -> None:
    out = parse_nsf_sport_detail_html(NSF_SPORT_DETAIL_HTML)
    assert out["lot_numbers"] == ["48715", "49759", "49038", "51019B", "51447A"]


def test_parse_detail_captures_facility() -> None:
    out = parse_nsf_sport_detail_html(NSF_SPORT_DETAIL_HTML)
    assert out.get("facility") == "Acme Mfg, Salt Lake City, UT"


def test_parse_detail_no_lots_is_empty() -> None:
    out = parse_nsf_sport_detail_html(NSF_SPORT_DETAIL_NO_LOTS)
    assert "lot_numbers" not in out
