"""Contract tests for the safety-alert fast lane.

These encode the acceptance criteria agreed before implementation. The recurring
theme: an alert is a *claim about a verified regulatory event*, and every way of
weakening that claim — an unresolved scope, a fuzzy match, an edited record, a
retraction reaching across lanes — has to be impossible rather than discouraged.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from safety_alerts import (  # noqa: E402
    INTERACTION_EVIDENCE_LEVELS,
    applies_to,
    is_active,
    latest_revisions,
    validate_alert,
    validate_feed,
)


def _alert(**overrides):
    """A valid published ingredient_ban. Override one field per test."""
    record = {
        "alert_id": "SA_2026_0001",
        "revision": 1,
        "event_type": "ingredient_ban",
        "status": "published",
        "authority": "FDA",
        "source_url": "https://www.fda.gov/example-advisory",
        "evidence_verified_at": "2026-08-08",
        "fda_class": None,
        "jurisdiction": "US",
        "effective_date": "2026-08-01",
        "published_at": "2026-08-08T14:00:00Z",
        "scope": {"ingredient_canonical_ids": ["tianeptine"], "dsld_ids": []},
        "resolved_dsld_ids": ["306237"],
        "catalog_snapshot_version": "2026.08.07.192916",
        "lots": None,
        "headline": "Tianeptine is prohibited in dietary supplements",
        "body": "FDA has determined tianeptine is not a lawful dietary ingredient.",
        "action": "Stop taking this product and contact your clinician.",
        "consumer_disposition": "block",
        "expires_at": None,
        "retracted": False,
    }
    record.update(overrides)
    return record


def test_the_template_record_is_valid():
    outcome = validate_alert(_alert())
    assert outcome["ok"], outcome["errors"]
    assert outcome["warnings"] == []


@pytest.mark.parametrize("field", [
    "alert_id", "revision", "event_type", "status", "authority", "source_url",
    "evidence_verified_at", "jurisdiction", "effective_date", "scope",
    "resolved_dsld_ids", "catalog_snapshot_version", "headline", "body", "action",
    "consumer_disposition",
])
def test_every_required_field_is_actually_required(field):
    record = _alert()
    del record[field]
    assert not validate_alert(record)["ok"], f"{field} was droppable"


def test_publication_authority_is_never_optional():
    """An alert without a verifiable official source is not an alert."""
    assert not validate_alert(_alert(source_url="fda.gov/thing"))["ok"], "non-https accepted"
    assert not validate_alert(_alert(source_url=""))["ok"]
    assert not validate_alert(_alert(authority=""))["ok"]


def test_fda_class_is_conditional_not_required():
    """Bans (DEA scheduling, import alerts, warning letters) carry no recall class.

    Requiring it would force curators to invent one, which is worse than absent.
    """
    assert validate_alert(_alert(fda_class=None))["ok"]

    recall = _alert(
        event_type="product_recall",
        fda_class="I",
        scope={"ingredient_canonical_ids": [], "dsld_ids": ["306237"]},
    )
    assert validate_alert(recall)["ok"], validate_alert(recall)["errors"]

    assert not validate_alert(_alert(fda_class="IV"))["ok"], "bogus class accepted"

    # Allowed but suspicious: a class on a ban asks the curator to double-check.
    flagged = validate_alert(_alert(fda_class="II"))
    assert flagged["ok"]
    assert any("ingredient_ban" in w for w in flagged["warnings"])


def test_human_approval_must_choose_the_consumer_disposition():
    assert not validate_alert(_alert(consumer_disposition=""))["ok"]
    assert not validate_alert(_alert(consumer_disposition="good_to_know"))["ok"]
    assert validate_alert(_alert(consumer_disposition="review"))["ok"]


def test_brand_scope_is_rejected_in_v1():
    """Brand without an exact normalized identity invites runtime fuzzy matching."""
    record = _alert(scope={"brand": "Some Brand", "ingredient_canonical_ids": ["tianeptine"], "dsld_ids": []})
    outcome = validate_alert(record)
    assert not outcome["ok"]
    assert any("brand" in e for e in outcome["errors"])


def test_scope_must_be_exactly_one_dimension():
    both = _alert(scope={"ingredient_canonical_ids": ["tianeptine"], "dsld_ids": ["306237"]})
    assert not validate_alert(both)["ok"], "ambiguous dual scope accepted"

    neither = _alert(scope={"ingredient_canonical_ids": [], "dsld_ids": []})
    assert not validate_alert(neither)["ok"], "scopeless alert accepted"


def test_event_type_and_scope_must_agree():
    mismatched = _alert(event_type="product_recall")  # still ingredient-scoped
    assert not validate_alert(mismatched)["ok"]


def test_published_alert_must_carry_a_resolved_applicability_set():
    """An unresolved published alert matches nothing and notifies nobody."""
    assert not validate_alert(_alert(resolved_dsld_ids=[]))["ok"]
    # A draft may legitimately be unresolved — resolution happens at publication.
    assert validate_alert(_alert(status="draft", resolved_dsld_ids=[]))["ok"]


def test_records_are_immutable_per_alert_id_and_revision():
    feed = [_alert(), _alert(headline="edited in place")]
    outcome = validate_feed(feed)
    assert not outcome["ok"]
    assert any("duplicate" in e for e in outcome["errors"])

    # The correct move is a higher revision, not an edit.
    assert validate_feed([_alert(), _alert(revision=2, headline="corrected")])["ok"]


def test_latest_revision_wins_regardless_of_file_order():
    records = [_alert(revision=3), _alert(revision=1), _alert(revision=2)]
    assert latest_revisions(records)["SA_2026_0001"]["revision"] == 3


def test_retraction_requires_the_retracted_status():
    assert not validate_alert(_alert(retracted=True))["ok"], "retracted=true with status=published"
    assert validate_alert(_alert(retracted=True, status="retracted"))["ok"]


def test_lots_are_display_only_and_never_a_matching_input():
    """We do not know the user's lot. A lot-scoped alert says 'check your lot'."""
    recall = _alert(
        event_type="product_recall",
        scope={"ingredient_canonical_ids": [], "dsld_ids": ["306237"]},
        lots=["ABC123", "ABC124"],
    )
    assert validate_alert(recall)["ok"]
    # applies_to resolves on identity only — lots are never consulted.
    assert applies_to(recall, dsld_id="306237")
    assert not applies_to(recall, dsld_id="999999")


class TestIsActive:
    """is_active answers 'raise THIS alert's signal', never 'is the product safe'."""

    def test_published_and_in_window(self):
        assert is_active(_alert(), "2026-08-08")

    def test_draft_never_fires(self):
        assert not is_active(_alert(status="draft"), "2026-08-08")

    def test_retracted_never_fires(self):
        assert not is_active(_alert(status="retracted", retracted=True), "2026-08-08")

    def test_not_yet_effective(self):
        assert not is_active(_alert(effective_date="2026-09-01"), "2026-08-08")

    def test_expired(self):
        assert not is_active(_alert(expires_at="2026-08-01"), "2026-08-08")


class TestAppliesTo:
    def test_resolved_set_applies_on_a_device_whose_catalog_predates_the_alert(self):
        """The case that makes the fast lane work.

        A device on an older catalog cannot resolve the newly banned substance
        locally, so canonical matching finds nothing. The publication-time
        resolved set still applies — this is why it is signed and shipped.
        """
        record = _alert()
        assert applies_to(record, dsld_id="306237", ingredient_canonical_ids=[])

    def test_canonical_ingredient_match_is_the_second_confirmation(self):
        """A product absent from the resolved set still matches on identity.

        Covers a product catalogued after the alert was published.
        """
        record = _alert(resolved_dsld_ids=["111111"])
        assert applies_to(record, dsld_id="999999", ingredient_canonical_ids=["tianeptine"])

    def test_never_matches_on_name_similarity(self):
        record = _alert()
        assert not applies_to(record, dsld_id="999999", ingredient_canonical_ids=["tianeptine sodium"])
        assert not applies_to(record, dsld_id="999999", ingredient_canonical_ids=["Tianeptine"])

    def test_unrelated_product_never_matches(self):
        assert not applies_to(_alert(), dsld_id="999999", ingredient_canonical_ids=["ashwagandha"])


# --- interaction_rule: a rule correction, matched only on the device ---------


def _interaction_alert(**interaction_overrides):
    interaction = {
        "rule_id": "DSI_FAKE_TESTOPRILEX_FAKEROOT",
        "rule_fingerprint": "sha256:" + "0" * 64,
        "ingredient_name": "Fakeroot (fictional)",
        "medication_name": "Testoprilex (fictional)",
        "medication_ids": ["class:fake_test_medications", "0000001"],
        "severity": "contraindicated",
        "evidence_level": "established",
    }
    interaction.update(interaction_overrides)
    return _alert(
        event_type="interaction_rule",
        scope={"ingredient_canonical_ids": ["fake_fakeroot"], "dsld_ids": []},
        resolved_dsld_ids=["9990001"],
        consumer_disposition="block",
        interaction=interaction,
    )


def test_a_complete_interaction_rule_alert_is_valid():
    outcome = validate_alert(_interaction_alert())
    assert outcome["ok"], outcome["errors"]


@pytest.mark.parametrize(
    "field", ["rule_id", "ingredient_name", "medication_name", "evidence_level"]
)
def test_interaction_rule_needs_its_text_fields(field):
    assert not validate_alert(_interaction_alert(**{field: ""}))["ok"]
    assert not validate_alert(_interaction_alert(**{field: None}))["ok"]


def test_interaction_rule_without_a_block_is_refused():
    record = _interaction_alert()
    del record["interaction"]
    assert not validate_alert(record)["ok"]


@pytest.mark.parametrize("value", [None, [], "class:x", [""], [7]])
def test_interaction_rule_needs_real_medication_ids(value):
    assert not validate_alert(_interaction_alert(medication_ids=value))["ok"]


@pytest.mark.parametrize("value", ["Warfarin", "Blood thinners", "class:Has Spaces"])
def test_medication_ids_are_identities_never_display_names(value):
    """The device matches ids exactly. A name would silently match nobody."""
    assert not validate_alert(_interaction_alert(medication_ids=[value]))["ok"]


@pytest.mark.parametrize("value", ["", "abc", "sha256:xyz", None])
def test_interaction_rule_needs_a_rule_fingerprint(value):
    assert not validate_alert(_interaction_alert(rule_fingerprint=value))["ok"]


@pytest.mark.parametrize("value", ["informational", "safe", "severe", None])
def test_interaction_rule_severity_is_one_of_the_four_warning_tiers(value):
    assert not validate_alert(_interaction_alert(severity=value))["ok"]


@pytest.mark.parametrize(
    "value",
    ["established", "probable", "moderate", "limited", "theoretical", "no_data"],
)
def test_evidence_level_uses_the_locked_vocabulary(value):
    assert validate_alert(_interaction_alert(evidence_level=value))["ok"]


def test_evidence_level_refuses_a_value_outside_the_vocabulary():
    assert not validate_alert(_interaction_alert(evidence_level="strong"))["ok"]


def test_disposition_follows_severity_the_way_the_app_does():
    """Same mapping as the app's disposition fallback: only contraindicated blocks."""
    good = _interaction_alert(severity="avoid")
    good["consumer_disposition"] = "review"
    assert validate_alert(good)["ok"]

    assert not validate_alert(_interaction_alert(severity="avoid"))["ok"]
    bad = _interaction_alert()
    bad["consumer_disposition"] = "review"
    assert not validate_alert(bad)["ok"]


def test_interaction_rule_scopes_on_ingredients_not_products():
    record = _interaction_alert()
    record["scope"] = {"ingredient_canonical_ids": [], "dsld_ids": ["9990001"]}
    assert not validate_alert(record)["ok"]


def test_only_an_interaction_rule_may_carry_the_block():
    record = _alert(interaction={"rule_id": "x"})
    assert not validate_alert(record)["ok"]


def test_the_server_side_matcher_never_claims_an_interaction_rule_match():
    """Only the device knows the medications. Publication-time code must not guess."""
    record = _interaction_alert()
    assert not applies_to(record, dsld_id="9990001")
    assert not applies_to(record, ingredient_canonical_ids=["fake_fakeroot"])


def test_evidence_levels_stay_equal_to_the_locked_vocabulary():
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "evidence_strength_vocab.json"
    )
    with open(path, encoding="utf-8") as handle:
        vocab = json.load(handle)["evidence_strengths"]
    assert {entry["id"] for entry in vocab} == INTERACTION_EVIDENCE_LEVELS
