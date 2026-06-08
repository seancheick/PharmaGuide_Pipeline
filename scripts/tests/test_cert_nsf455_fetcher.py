"""NSF/ANSI 455-2 GMP facility-registration fetcher (parser) tests.

Tests the pure ``parse_nsf_455_listing`` against a fixture shaped like the live
info.nsf.org/Certified/455GMP listing — no network. Locks: facility scope, empty
product, company-id extraction from the logo path, the verifiable per-company
source URL, NSF header-block skipping, and schema parity.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from api_audit.verify_certifications import parse_nsf_455_listing  # noqa: E402

SNAPSHOT = "2026-06-07"

# Two real company blocks + an NSF header block (must be skipped), separated by
# <hr noshade> exactly like the live page.
NSF_455_SAMPLE_HTML = """
<table><tr><td><font size='+2'>NSF GMP Registration Program</font></td></tr></table>
NSF/ANSI 455-2 program description boilerplate.
<hr noshade>
<table><tr><td><font size='+2'>Pure Encapsulations&nbsp;</font></td>
<td><a href="http://www.purecaps.com"><img src='http://info.nsf.org/certified/common/logo/C0006061.gif'></a></td></tr>
<tr><td>490 Boston Post Road</td></tr><tr><td>Sudbury, MA 01776</td></tr></table>
<strong>Manufacturing Facility</strong>
<hr noshade>
<table><tr><td><font size='+2'>Nutricost Manufacturing, LLC&nbsp;</font></td>
<td><img src='http://info.nsf.org/certified/common/logo/C0912345.gif'></td></tr>
<tr><td>Vineyard, UT</td></tr></table>
"""


def test_parse_nsf_455_extracts_facility_records() -> None:
    records = parse_nsf_455_listing(NSF_455_SAMPLE_HTML, SNAPSHOT)
    brands = {r["brand"] for r in records}
    # NSF header block skipped; two real companies kept.
    assert brands == {"Pure Encapsulations", "Nutricost Manufacturing, LLC"}


def test_parse_nsf_455_records_are_facility_scope_empty_product() -> None:
    records = parse_nsf_455_listing(NSF_455_SAMPLE_HTML, SNAPSHOT)
    for r in records:
        assert r["scope"] == "facility"
        assert r["product"] == ""
        assert r["product_normalized"] == ""
        assert r["program"] == "NSF/ANSI 455"
        assert r["standard"] == "NSF/ANSI 455-2"
        assert r["verified_at"] == SNAPSHOT


def test_parse_nsf_455_builds_verifiable_per_company_url() -> None:
    records = parse_nsf_455_listing(NSF_455_SAMPLE_HTML, SNAPSHOT)
    pure = next(r for r in records if r["brand"] == "Pure Encapsulations")
    assert pure["company_id"] == "C0006061"
    assert pure["source_url"] == (
        "https://info.nsf.org/Certified/455GMP/Listings.asp"
        "?Company=C0006061&Standard=455-2GMP"
    )


def test_parse_nsf_455_record_has_required_registry_fields() -> None:
    records = parse_nsf_455_listing(NSF_455_SAMPLE_HTML, SNAPSHOT)
    required = {
        "record_id", "program", "brand", "product", "brand_normalized",
        "product_normalized", "scope", "lot_numbers_tested", "verified_at",
        "source_url", "evidence_band",
    }
    for r in records:
        assert required <= set(r), f"missing: {required - set(r)}"
        assert r["record_id"].startswith("NSF_ANSI")
