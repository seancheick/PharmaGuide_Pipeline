"""Sprint C (2026-05-13) — banned_substance_detail must forward the
additional context fields the warning dict already carries.

Background
==========
``build_banned_substance_detail`` previously returned only three fields:
``safety_warning_one_liner``, ``safety_warning``, ``substance_name``.
But the source warning dict for the same product carries 12 more,
including the regulatory date, mechanism paragraph, and real citation
URLs. The Flutter blocked-product view read ``source_url`` (singular)
that never existed and always fell back to the generic FDA CDER index.

Sprint C widens the function to also forward:
    - ``ban_context``           (enum: substance/adulterant/watchlist/...)
    - ``detail``                (paragraph mechanism / FDA story)
    - ``regulatory_date_label`` ("FDA ban effective")
    - ``date``                  ("2016-09-07")
    - ``source_urls``           (list[str])

The three legacy fields remain MANDATORY (locked in by
``_validate_banned_preflight_propagation``). The new fields are OPTIONAL
on the blob — forwarded when the warning has them populated, omitted
otherwise. Flutter must tolerate any subset being absent.

These tests pin the new contract so future emitter refactors can't
silently drop the context fields.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Synthetic helpers — keep tests fast and decoupled from the live build.
# ---------------------------------------------------------------------------


def _enriched_with_banned() -> dict:
    """Return an enriched-product payload that ``has_banned_substance``
    will accept. Uses the inactive-resolver path (Brominated Vegetable
    Oil is a known banned inactive in banned_recalled_ingredients.json),
    matching the shape expected by build_final_db's helpers."""
    return {
        "dsld_id": "9999999",
        "id": "9999999",
        "full_name": "Synthetic test product containing Brominated Vegetable Oil",
        "brand_name": "Synthetic Test Brand",
        "contaminant_data": {
            "banned_substances": {"found": False, "substances": []},
            "harmful_additives": {"found": False, "additives": []},
        },
        "activeIngredients": [],
        "inactiveIngredients": [
            {
                "name": "Brominated Vegetable Oil",
                "raw_source_text": "Brominated Vegetable Oil",
                "standardName": "Brominated Vegetable Oil",
            },
        ],
        "ingredient_summary": {"active_ingredients": []},
        "warnings": [],
        "allergen_hits": [],
        "harmful_additives": [],
    }


def _full_warning() -> dict:
    """A banned_substance warning with every field populated, matching the
    real shape emitted by build_warnings_list for a Vinpocetine product."""
    return {
        "type": "banned_substance",
        "severity": "critical",
        "clinical_risk": "critical",
        "display_mode_default": "critical",
        "title": "Banned substance: Vinpocetine",
        "safety_warning_one_liner": "Not a lawful US supplement with pregnancy risk. Stop.",
        "safety_warning": (
            "An FDA statement in 2019 concluded vinpocetine is not a lawful "
            "supplement ingredient, and it is associated with miscarriage risk "
            "in pregnancy. Stop using and consult a clinician."
        ),
        "ban_context": "substance",
        "detail": (
            "Vinpocetine is a synthetic derivative of the alkaloid vincamine, "
            "used as a prescription drug in Europe and Japan. In 2019 the FDA "
            "concluded it does not meet the statutory definition of a dietary "
            "ingredient."
        ),
        "regulatory_date_label": "FDA ban effective",
        "date": "2016-09-07",
        "source_urls": [
            "https://www.fda.gov/food/cfsan-constituent-updates/fda-determines-vinpocetine-not-dietary-ingredient"
        ],
        "source": "banned_recalled_ingredients",
        "condition_ids": [],
        "drug_class_ids": [],
        "identifiers": None,
    }


# ---------------------------------------------------------------------------
# Tests — context fields forwarded when warning carries them
# ---------------------------------------------------------------------------


def test_bsd_forwards_ban_context_when_present() -> None:
    from scripts.build_final_db import build_banned_substance_detail
    bsd = build_banned_substance_detail(_enriched_with_banned(), [_full_warning()])
    assert bsd is not None
    assert bsd["ban_context"] == "substance", (
        "ban_context must be forwarded verbatim from the warning dict so "
        "Flutter can branch user-facing copy (substance vs adulterant vs "
        "watchlist vs export_restricted). The 2026-04-16 lesson — status "
        "overload — is exactly why this enum matters."
    )


def test_bsd_forwards_detail_paragraph_when_present() -> None:
    from scripts.build_final_db import build_banned_substance_detail
    bsd = build_banned_substance_detail(_enriched_with_banned(), [_full_warning()])
    assert bsd is not None
    assert "detail" in bsd
    assert "Vinpocetine is a synthetic derivative" in bsd["detail"]


def test_bsd_forwards_regulatory_date_label_and_date_when_present() -> None:
    from scripts.build_final_db import build_banned_substance_detail
    bsd = build_banned_substance_detail(_enriched_with_banned(), [_full_warning()])
    assert bsd is not None
    assert bsd["regulatory_date_label"] == "FDA ban effective"
    assert bsd["date"] == "2016-09-07"


def test_bsd_forwards_source_urls_list_when_present() -> None:
    from scripts.build_final_db import build_banned_substance_detail
    bsd = build_banned_substance_detail(_enriched_with_banned(), [_full_warning()])
    assert bsd is not None
    assert isinstance(bsd["source_urls"], list)
    assert len(bsd["source_urls"]) == 1
    assert bsd["source_urls"][0].startswith("https://www.fda.gov/")


def test_bsd_full_shape_matches_widened_contract() -> None:
    """End-to-end shape: the full widened bsd has exactly the legacy 3
    fields PLUS the 5 new fields when the warning carries them all."""
    from scripts.build_final_db import build_banned_substance_detail
    bsd = build_banned_substance_detail(_enriched_with_banned(), [_full_warning()])
    assert bsd is not None
    assert set(bsd.keys()) == {
        "safety_warning_one_liner",
        "safety_warning",
        "substance_name",
        "ban_context",
        "detail",
        "regulatory_date_label",
        "date",
        "source_urls",
    }


# ---------------------------------------------------------------------------
# Tests — new fields are OPTIONAL (no regression on minimal warnings)
# ---------------------------------------------------------------------------


def test_bsd_omits_optional_fields_when_warning_lacks_them() -> None:
    """When the warning carries only the legacy 3 fields (e.g. an older
    emitter site that hasn't been updated yet, or a banned ingredient whose
    authoring doesn't include ban_context/date), the bsd must still be
    populated with the 3 legacy fields and OMIT the optional keys.

    Crucially: must NOT emit empty strings/lists for missing fields.
    Empty values are a Flutter footgun (UI renders "FDA ban effective"
    with no date next to it). Absent keys are the contract."""
    from scripts.build_final_db import build_banned_substance_detail
    minimal_warning = {
        "type": "banned_substance",
        "severity": "critical",
        "title": "Banned substance: Test",
        "safety_warning_one_liner": "One-liner.",
        "safety_warning": "Body warning text.",
    }
    bsd = build_banned_substance_detail(_enriched_with_banned(), [minimal_warning])
    assert bsd is not None
    assert set(bsd.keys()) == {
        "safety_warning_one_liner",
        "safety_warning",
        "substance_name",
    }


def test_bsd_omits_optional_field_when_warning_value_is_empty_string() -> None:
    """Warning carries the optional field but it's an empty/whitespace
    string. Must omit the key from bsd, not forward the empty value."""
    from scripts.build_final_db import build_banned_substance_detail
    w = _full_warning()
    w["ban_context"] = "   "
    w["regulatory_date_label"] = ""
    bsd = build_banned_substance_detail(_enriched_with_banned(), [w])
    assert bsd is not None
    assert "ban_context" not in bsd
    assert "regulatory_date_label" not in bsd
    # Other context fields still present
    assert "detail" in bsd
    assert "date" in bsd
    assert "source_urls" in bsd


def test_bsd_omits_source_urls_when_list_is_all_empty_strings() -> None:
    """source_urls is a list[str]; if every entry is empty/whitespace,
    omit the key entirely. Don't forward a [] either — absence beats
    empty list for Flutter's "do we have citations?" check."""
    from scripts.build_final_db import build_banned_substance_detail
    w = _full_warning()
    w["source_urls"] = ["", "  ", None]
    bsd = build_banned_substance_detail(_enriched_with_banned(), [w])
    assert bsd is not None
    assert "source_urls" not in bsd


def test_bsd_filters_empty_strings_from_source_urls() -> None:
    """Mixed list — keep the populated entries, drop the empties."""
    from scripts.build_final_db import build_banned_substance_detail
    w = _full_warning()
    w["source_urls"] = ["https://example.com/a", "", "https://example.com/b", "   "]
    bsd = build_banned_substance_detail(_enriched_with_banned(), [w])
    assert bsd is not None
    assert bsd["source_urls"] == ["https://example.com/a", "https://example.com/b"]


# ---------------------------------------------------------------------------
# Tests — legacy contract preserved (regression guard for the 3-field core)
# ---------------------------------------------------------------------------


def test_bsd_returns_none_when_no_banned_substance() -> None:
    from scripts.build_final_db import build_banned_substance_detail
    clean = {
        "dsld_id": "1234",
        "contaminant_data": {"has_contaminants": False, "contaminants_found": []},
        "ingredients_active": [],
        "ingredients_inactive": [],
    }
    assert build_banned_substance_detail(clean, [_full_warning()]) is None


def test_bsd_returns_none_when_warning_lacks_authored_copy() -> None:
    """The mandatory-3 gate must still fire — a warning with empty
    safety_warning_one_liner cannot produce a bsd even if the context
    fields are richly populated. This is the contract the E1.1.4
    validator relies on (a non-None bsd guarantees the legacy fields)."""
    from scripts.build_final_db import build_banned_substance_detail
    w = _full_warning()
    w["safety_warning_one_liner"] = ""
    assert build_banned_substance_detail(_enriched_with_banned(), [w]) is None


def test_bsd_substance_name_extracted_from_title() -> None:
    """Title format 'Banned substance: <Name>' yields substance_name=<Name>.
    Regression guard for the existing parsing rule."""
    from scripts.build_final_db import build_banned_substance_detail
    bsd = build_banned_substance_detail(_enriched_with_banned(), [_full_warning()])
    assert bsd is not None
    assert bsd["substance_name"] == "Vinpocetine"
