"""Safety/additive-recognized rows must not pollute the unmapped *identity* report.

A label like 'Mannitol' (harmful_additives) or 'Sulbutiamine' (banned_recalled)
gets no IQM identity by design (canonical_id never comes from safety DBs), yet it
was being logged into unmapped_active/inactive_ingredients.json — a false
"add this to the identity DB" gap that inflates the triage queue.

These rows are now tagged ``recognized_non_identity`` by the normalizer and routed
by the tracker into a separate ``recognized_non_identity_ingredients.json`` bucket,
excluded from the unmapped lists. They are NOT dropped (a watchlist row could still
be a legitimate active that genuinely needs an IQM entry) — only re-categorized.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from unmapped_ingredient_tracker import UnmappedIngredientTracker


def test_tracker_routes_recognized_rows_out_of_unmapped_lists(tmp_path):
    tracker = UnmappedIngredientTracker(tmp_path)
    tracker.process_unmapped_ingredients(
        {"Mannitol": 4, "Genuinely Unknown Active": 2},
        {"Genuinely Unknown Active"},
        {
            "Mannitol": {
                "is_active": False,
                "recognized_non_identity": True,
                "recognition_standard_name": "Sugar Alcohols (Polyols)",
                "recognition_type": "harmful_additive",
            },
            "Genuinely Unknown Active": {"is_active": True},
        },
    )
    tracker.save_tracking_files()

    inactive = json.loads((tmp_path / "unmapped_inactive_ingredients.json").read_text())
    active = json.loads((tmp_path / "unmapped_active_ingredients.json").read_text())
    recognized = json.loads((tmp_path / "recognized_non_identity_ingredients.json").read_text())

    # recognized additive excluded from BOTH identity-gap lists
    assert "Mannitol" not in inactive["unmapped_ingredients"]
    assert "Mannitol" not in active["unmapped_ingredients"]
    # genuinely-unknown active is still reported as a true gap
    assert active["unmapped_ingredients"]["Genuinely Unknown Active"] == 2
    # recognized row captured separately, with audit context, not lost
    row = recognized["recognized_ingredients"]["Mannitol"]
    assert row["occurrences"] == 4
    assert row["recognition_standard_name"] == "Sugar Alcohols (Polyols)"
    assert recognized["metadata"]["total_recognized"] == 1


def test_backward_compatible_when_no_recognition_flag(tmp_path):
    """Details without the recognition flag behave exactly as before."""
    tracker = UnmappedIngredientTracker(tmp_path)
    tracker.process_unmapped_ingredients(
        {"Chopchinee": 2, "Unknown Inactive": 1},
        {"Chopchinee"},
        {"Chopchinee": {"is_active": True}, "Unknown Inactive": {"is_active": False}},
    )
    tracker.save_tracking_files()
    active = json.loads((tmp_path / "unmapped_active_ingredients.json").read_text())
    inactive = json.loads((tmp_path / "unmapped_inactive_ingredients.json").read_text())
    recognized = json.loads((tmp_path / "recognized_non_identity_ingredients.json").read_text())
    assert active["unmapped_ingredients"]["Chopchinee"] == 2
    assert inactive["unmapped_ingredients"]["Unknown Inactive"] == 1
    assert recognized["metadata"]["total_recognized"] == 0


def test_normalizer_flags_safety_recognized_rows_as_non_identity():
    n = EnhancedDSLDNormalizer()
    detail = n._build_unmapped_detail("Mannitol", [], is_active=False)
    assert detail.get("recognized_non_identity") is True
    assert detail.get("recognition_standard_name") == "Sugar Alcohols (Polyols)"


def test_normalizer_does_not_flag_true_unknown_as_recognized():
    n = EnhancedDSLDNormalizer()
    detail = n._build_unmapped_detail("Zzqx Unknown Botanical 999", [], is_active=True)
    assert not detail.get("recognized_non_identity")
