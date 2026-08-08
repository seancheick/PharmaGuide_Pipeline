"""FDA sync -> draft safety alert: identity is checked, never guessed."""
from __future__ import annotations

import os
import sys

import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(SCRIPTS, "api_audit"))

from fda_alert_drafts import (  # noqa: E402
    candidate_ids_for,
    draft_from_record,
    index_banned_entries,
    next_alert_id,
    parse_fda_class,
    propose_drafts,
    resolvable_ids,
    warrants_user_alert,
)
from safety_alerts import validate_feed  # noqa: E402

TODAY = "2026-08-08"

# Only NOOTROPIC_VINPOCETINE is a real catalog identity here — mirroring the
# measured reality that 11 of 168 banned-DB ids double as catalog canonical ids.
CATALOG_INDEX = {
    "NOOTROPIC_VINPOCETINE": {"204468"},
    "red_yeast_rice": {"206443", "213840"},
    "ashwagandha": {"306237"},
}

BANNED_ENTRIES = [
    {
        "id": "NOOTROPIC_VINPOCETINE",
        "standard_name": "Vinpocetine",
        "aliases": ["vinpocetine", "cavinton"],
    },
    {
        # The borax shape: tracked, but no id the catalog uses.
        "id": "BANNED_SODIUM_TETRABORATE",
        "standard_name": "Sodium Tetraborate (Borax)",
        "aliases": ["borax", "sodium tetraborate"],
    },
]
BANNED_INDEX = index_banned_entries(BANNED_ENTRIES)


def _record(**overrides):
    record = {
        "recall_number": "F-1234-2026",
        "classification": "Class II",
        "recalling_firm": "Example Labs",
        "product_description": "Example Brain Support Capsules",
        "reason_for_recall": "Product contains vinpocetine, not a lawful dietary ingredient.",
        "recall_initiation_date": "2026-07-15",
        "extracted_substances": ["vinpocetine"],
        "substances_already_tracked": ["Vinpocetine"],
        "fda_source_url": "https://www.accessdata.fda.gov/example",
        "_source_type": "dea_federal_register",
    }
    record.update(overrides)
    return record


class TestSelection:
    def test_class_i_always_warrants_an_alert(self):
        assert warrants_user_alert(_record(classification="Class I", substances_already_tracked=[]))

    def test_a_tracked_substance_warrants_an_alert(self):
        assert warrants_user_alert(_record(classification="Class III"))

    def test_routine_untracked_recall_does_not(self):
        """A feed that fires on everything teaches people to ignore it."""
        assert not warrants_user_alert(
            _record(classification="Class III", substances_already_tracked=[])
        )


class TestIdentityIsCheckedNotGuessed:
    def test_only_ids_present_in_the_catalog_survive(self):
        assert resolvable_ids(["NOOTROPIC_VINPOCETINE", "vinpocetine"], CATALOG_INDEX) == [
            "NOOTROPIC_VINPOCETINE"
        ]

    def test_no_substring_or_fuzzy_match(self):
        assert resolvable_ids(["vinpocetine_hcl", "RED_YEAST", "ashwagandha_extract"], CATALOG_INDEX) == []

    def test_case_differences_are_not_identity(self):
        """Exact equality only — a case-folded hit is not proof of identity."""
        assert resolvable_ids(["nootropic_vinpocetine", "Ashwagandha"], CATALOG_INDEX) == []

    def test_candidates_include_id_then_aliases(self):
        assert candidate_ids_for(BANNED_ENTRIES[0]) == [
            "NOOTROPIC_VINPOCETINE",
            "vinpocetine",
            "cavinton",
        ]


class TestDrafting:
    def test_resolvable_substance_produces_a_draft(self):
        draft, candidate = draft_from_record(
            _record(), CATALOG_INDEX, BANNED_INDEX, alert_id="SA_2026_0001", today=TODAY
        )
        assert candidate is None
        assert draft["scope"]["ingredient_canonical_ids"] == ["NOOTROPIC_VINPOCETINE"]
        assert draft["status"] == "draft"

    def test_unresolvable_substance_yields_a_candidate_not_a_draft(self):
        """The borax case. An unresolvable scope would apply to zero products
        while looking complete — worse than surfacing it for a human."""
        record = _record(
            extracted_substances=["borax"],
            substances_already_tracked=["Sodium Tetraborate (Borax)"],
        )
        draft, candidate = draft_from_record(
            record, CATALOG_INDEX, BANNED_INDEX, alert_id="SA_2026_0001", today=TODAY
        )
        assert draft is None
        assert candidate["identity_candidates_considered"]
        assert "canonical id" in candidate["what_a_curator_must_supply"]

    def test_draft_never_carries_a_resolution(self):
        """Resolution is pinned to a catalog snapshot at publication."""
        draft, _ = draft_from_record(
            _record(), CATALOG_INDEX, BANNED_INDEX, alert_id="SA_2026_0001", today=TODAY
        )
        assert draft["resolved_dsld_ids"] == []
        assert draft["catalog_snapshot_version"] is None
        assert draft["published_at"] is None


class TestDisposition:
    def test_ingredient_ban_blocks(self):
        draft, _ = draft_from_record(
            _record(), CATALOG_INDEX, BANNED_INDEX, alert_id="SA_2026_0001", today=TODAY
        )
        assert draft["consumer_disposition"] == "block"

    def test_class_i_is_recorded_as_the_bare_numeral(self):
        """FDA prints "Class I"; the schema stores "I"."""
        draft, _ = draft_from_record(
            _record(classification="Class I"),
            CATALOG_INDEX, BANNED_INDEX, alert_id="SA_2026_0001", today=TODAY,
        )
        assert draft["fda_class"] == "I"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Class I", "I"),
            ("Class II", "II"),
            ("Class III", "III"),
            ("class iii", "III"),
            # Unclassified events are real — DEA scheduling actions and import
            # alerts carry no recall class. Never invent one.
            ("", None),
            (None, None),
            ("Not Classified", None),
        ],
    )
    def test_class_parsing_distinguishes_i_from_ii_and_iii(self, raw, expected):
        """`startswith("class i")` is TRUE for Class II and Class III, which
        silently escalated every classified recall to the highest urgency band.
        """
        assert parse_fda_class(raw) == expected

    def test_class_ii_recall_of_a_tracked_substance_still_blocks_via_ban(self):
        """Disposition follows the event type, not the recall class: a
        prohibited substance is in every unit, so there is nothing to check."""
        draft, _ = draft_from_record(
            _record(classification="Class III"),
            CATALOG_INDEX, BANNED_INDEX, alert_id="SA_2026_0001", today=TODAY,
        )
        assert draft["consumer_disposition"] == "block"

    def test_product_recall_never_becomes_an_ingredient_wide_ban(self):
        """A recall applies to a product/batch, not every product sharing an
        ingredient. Without an exact affected product identity, it must remain
        a curator candidate even when the ingredient is catalog-resolvable.
        """
        draft, candidate = draft_from_record(
            _record(_source_type="openfda_enforcement"),
            CATALOG_INDEX,
            BANNED_INDEX,
            alert_id="SA_2026_0001",
            today=TODAY,
        )
        assert draft is None
        assert candidate["reason"] == "product recall has no verified affected product identity"


class TestDraftsAreNeverPublishable:
    def test_status_is_always_draft(self):
        out = propose_drafts(
            [_record(), _record(classification="Class I")],
            CATALOG_INDEX, BANNED_INDEX,
            existing_alert_ids=[], today=TODAY, year=2026,
        )
        assert out["drafts"]
        assert all(d["status"] == "draft" for d in out["drafts"])

    def test_a_generated_draft_passes_the_schema_but_is_not_publishable(self):
        """It must be a VALID draft — an invalid one would block the curator —
        and it must still fail the published-alert requirements."""
        out = propose_drafts(
            [_record()], CATALOG_INDEX, BANNED_INDEX,
            existing_alert_ids=[], today=TODAY, year=2026,
        )
        draft = {k: v for k, v in out["drafts"][0].items() if not k.startswith("_")}
        assert validate_feed([draft])["ok"], validate_feed([draft])["errors"]

        promoted = dict(draft, status="published", published_at="2026-08-08T00:00:00Z")
        result = validate_feed([promoted])
        assert not result["ok"]
        assert any("resolved_dsld_ids" in e for e in result["errors"])


class TestAlertIds:
    def test_continues_the_existing_sequence(self):
        assert next_alert_id(["SA_2026_0001", "SA_2026_0007"], 2026) == "SA_2026_0008"

    def test_ignores_other_years(self):
        assert next_alert_id(["SA_2025_0042"], 2026) == "SA_2026_0001"

    def test_generated_drafts_do_not_collide(self):
        out = propose_drafts(
            [_record(), _record(recall_number="F-9999-2026")],
            CATALOG_INDEX, BANNED_INDEX,
            existing_alert_ids=["SA_2026_0001"], today=TODAY, year=2026,
        )
        ids = [d["alert_id"] for d in out["drafts"]]
        assert ids == ["SA_2026_0002", "SA_2026_0003"]
        assert len(set(ids)) == len(ids)


def test_substance_index_maps_names_to_entries():
    assert BANNED_INDEX["vinpocetine"]["id"] == "NOOTROPIC_VINPOCETINE"
    assert BANNED_INDEX["borax"]["id"] == "BANNED_SODIUM_TETRABORATE"
