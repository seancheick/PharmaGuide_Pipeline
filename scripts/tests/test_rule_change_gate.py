"""Publication refuses a material rule correction with no alert.

The alert feed is the only thing that reaches a phone between releases, so a
rule that newly warns someone must not leave without one. Fixtures are fake.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import build_interaction_db as bid  # noqa: E402
import rule_change_gate as gate  # noqa: E402

KEY = "DSI_FAKE_TESTOPRILEX_FAKEROOT"
PROFILE_RULE = "RULE_FAKE_FAKEROOT"
DRUG_KEY = f"{PROFILE_RULE}#drug_class:fake_class"


def _row(**overrides):
    row = {
        "id": KEY,
        "agent1_type": "drug_class",
        "agent1_name": "Testoprilex (fictional)",
        "agent1_id": "class:fake_test_medications",
        "agent2_type": "supplement",
        "agent2_name": "Fakeroot (fictional)",
        "agent2_id": "C0000000",
        "agent2_canonical_id": "fake_fakeroot",
        "severity": "caution",
        "mechanism": "Fictional mechanism.",
        "management": "Fictional management.",
        "evidence_level": "established",
        "last_updated": "2026-11-01",
    }
    row.update(overrides)
    return row


def _rule(*, severity="caution", gate_ids=("fake_class",), mechanism="Fictional."):
    return {
        "id": PROFILE_RULE,
        "subject_ref": {"db": "fake", "canonical_id": "fake_fakeroot"},
        "condition_rules": [],
        "dose_thresholds": [],
        "pregnancy_lactation": None,
        "last_reviewed": "2026-11-01",
        "review_owner": "fake",
        "drug_class_rules": [
            {
                "drug_class_id": "fake_class",
                "severity": severity,
                "evidence_level": "established",
                "mechanism": mechanism,
                "profile_gate": {"requires": {"drug_classes_any": list(gate_ids)}},
            }
        ],
    }


def _db(path: Path, rows=(), rules=(), classes=None) -> Path:
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(bid.SCHEMA_SQL)
    for class_id, rxcuis in (classes or {}).items():
        con.execute(
            "INSERT INTO drug_class_map VALUES (?, ?, ?, ?, ?, ?)",
            (class_id, class_id, json.dumps(rxcuis), "[]", "fake", "2026-11-01"),
        )
    columns = {c[1]: c for c in con.execute("PRAGMA table_info(interactions)")}
    for row in rows:
        filled = {
            name: "" for name, c in columns.items() if c[3] and c[4] is None
        } | row
        names = ", ".join(filled)
        marks = ", ".join("?" for _ in filled)
        con.execute(
            f"INSERT INTO interactions ({names}) VALUES ({marks})",
            list(filled.values()),
        )
    for rule in rules:
        con.execute(
            "INSERT INTO profile_warning_rules VALUES (?, ?, ?, ?)",
            (rule["id"], rule["subject_ref"]["canonical_id"], "6", json.dumps(rule)),
        )
    con.commit()
    con.close()
    return path


def _alert(fingerprint, *, rule_id=KEY, status="published", revision=1, **overrides):
    record = {
        "alert_id": "SA_9999_0001",
        "revision": revision,
        "event_type": "interaction_rule",
        "status": status,
        "retracted": status == "retracted",
        "effective_date": "2026-11-01",
        "interaction": {
            "rule_id": rule_id,
            "rule_fingerprint": fingerprint,
            "severity": "contraindicated",
        },
    }
    record.update(overrides)
    return record


def _alerts_dir(tmp_path, *records, attestations=()):
    directory = tmp_path / "alerts"
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir()
    for index, record in enumerate(records):
        (directory / f"SA_9999_{index:04d}.json").write_text(json.dumps(record))
    if attestations:
        (directory / gate.ATTESTATIONS_FILENAME).write_text(
            json.dumps({"attestations": list(attestations)})
        )
    return directory


def _check(tmp_path, base_rows=(), cand_rows=(), base_rules=(), cand_rules=(), records=(),
           attestations=(), live_revisions=None, base_classes=None, cand_classes=None):
    (tmp_path / "b").mkdir(exist_ok=True)
    (tmp_path / "c").mkdir(exist_ok=True)
    baseline = _db(tmp_path / "b" / "db.sqlite", base_rows, base_rules, base_classes)
    candidate = _db(tmp_path / "c" / "db.sqlite", cand_rows, cand_rules, cand_classes)
    return gate.check_rule_changes(
        candidate,
        baseline,
        alerts_dir=_alerts_dir(tmp_path, *records, attestations=attestations),
        live_revisions=live_revisions,
    )


def _fp(tmp_path, rows=(), rules=(), key=KEY, classes=None):
    name = hashlib.sha256(repr((rows, rules, classes)).encode()).hexdigest()[:8]
    db = _db(tmp_path / f"fp_{name}.sqlite", rows, rules, classes)
    return gate.rule_fingerprint(db, key)


def test_no_change_passes(tmp_path):
    result = _check(tmp_path, [_row()], [_row()])
    assert result.ok and not result.changes


@pytest.mark.parametrize("severity", ["contraindicated", "avoid"])
def test_new_hard_rule_with_no_alert_refuses(tmp_path, severity):
    result = _check(tmp_path, [], [_row(severity=severity)])
    assert not result.ok
    assert KEY in result.errors[0]
    assert "needs a published interaction_rule alert" in result.errors[0]


def test_new_hard_rule_with_its_alert_passes(tmp_path):
    row = _row(severity="contraindicated")
    result = _check(tmp_path, [], [row], records=[_alert(_fp(tmp_path, [row]))])
    assert result.ok, result.errors


def test_severity_raised_into_hard_refuses(tmp_path):
    result = _check(tmp_path, [_row()], [_row(severity="avoid")])
    assert not result.ok


def test_new_medication_scope_on_a_hard_rule_refuses(tmp_path):
    base = _row(severity="avoid")
    result = _check(tmp_path, [base], [_row(severity="avoid", agent1_id="class:wider")])
    assert not result.ok
    assert "needs a published" in result.errors[0]


def test_alert_for_an_earlier_correction_does_not_cover_this_one(tmp_path):
    old = _row(severity="avoid", mechanism="Old.")
    new = _row(severity="contraindicated")
    result = _check(tmp_path, [_row()], [new], records=[_alert(_fp(tmp_path, [old]))])
    assert not result.ok


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "draft"},
        {"status": "retracted"},
        {"event_type": "ingredient_ban"},
        {"expires_at": "2020-01-01"},
        {"effective_date": "2999-01-01"},
    ],
)
def test_alert_that_is_not_live_does_not_cover(tmp_path, overrides):
    row = _row(severity="contraindicated")
    record = _alert(_fp(tmp_path, [row]))
    record.update(overrides)
    result = _check(tmp_path, [], [row], records=[record])
    assert not result.ok


def test_a_retracted_alert_no_longer_covers_the_rule(tmp_path):
    """Revision 1 is still on disk. Revision 2 withdrew it."""
    rule = _row(severity="avoid")
    fingerprint = _fp(tmp_path, [rule])
    result = _check(
        tmp_path, [], [rule],
        records=[_alert(fingerprint), _alert(fingerprint, status="retracted", revision=2)],
        live_revisions={"SA_9999_0001": 2},
    )
    assert not result.ok


def test_an_older_revision_does_not_cover_what_the_latest_stopped_saying(tmp_path):
    rule = _row(severity="avoid")
    fingerprint = _fp(tmp_path, [rule])
    other = _fp(tmp_path, [_row(severity="avoid", mechanism="Other words.")])
    result = _check(
        tmp_path, [], [rule],
        records=[_alert(fingerprint), _alert(other, revision=2)],
        live_revisions={"SA_9999_0001": 2},
    )
    assert not result.ok


def test_a_draft_revision_does_not_hide_the_published_alert(tmp_path):
    rule = _row(severity="avoid")
    fingerprint = _fp(tmp_path, [rule])
    result = _check(
        tmp_path, [], [rule],
        records=[_alert(fingerprint), _alert(fingerprint, status="draft", revision=2)],
        live_revisions={"SA_9999_0001": 1},
    )
    assert result.ok, result.errors


def test_attestation_cannot_replace_a_required_alert(tmp_path):
    row = _row(severity="contraindicated")
    result = _check(
        tmp_path, [], [row],
        attestations=[{"rule_key": KEY, "rule_fingerprint": _fp(tmp_path, [row]),
                       "reason": "x", "reviewer": "y", "date": "2026-11-03"}],
    )
    assert not result.ok


def test_reworded_hard_rule_needs_alert_or_attestation(tmp_path):
    base = _row(severity="avoid")
    new = _row(severity="avoid", mechanism="Different words.")
    refused = _check(tmp_path, [base], [new])
    assert not refused.ok
    assert "alert or a reviewed attestation" in refused.errors[0]

    attested = _check(
        tmp_path, [base], [new],
        attestations=[{"rule_key": KEY, "rule_fingerprint": _fp(tmp_path, [new]),
                       "reason": "Typo.", "reviewer": "fake", "date": "2026-11-03"}],
    )
    assert attested.ok, attested.errors


@pytest.mark.parametrize("missing", ["reason", "reviewer", "date"])
def test_attestation_must_be_complete(tmp_path, missing):
    base = _row(severity="avoid")
    new = _row(severity="avoid", mechanism="Different words.")
    entry = {"rule_key": KEY, "rule_fingerprint": _fp(tmp_path, [new]),
             "reason": "Typo.", "reviewer": "fake", "date": "2026-11-03"}
    entry[missing] = " "
    assert not _check(tmp_path, [base], [new], attestations=[entry]).ok


def test_attestation_is_bound_to_the_exact_rule_text(tmp_path):
    base = _row(severity="avoid")
    new = _row(severity="avoid", mechanism="Different words.")
    other = _row(severity="avoid", mechanism="Other words.")
    result = _check(
        tmp_path, [base], [new],
        attestations=[{"rule_key": KEY, "rule_fingerprint": _fp(tmp_path, [other]),
                       "reason": "Typo.", "reviewer": "fake", "date": "2026-11-03"}],
    )
    assert not result.ok


@pytest.mark.parametrize("bad_date", ["soon", "2026-13-40", "2999-01-01"])
def test_attestation_needs_a_real_date_that_has_passed(tmp_path, bad_date):
    base = _row(severity="avoid")
    new = _row(severity="avoid", mechanism="Different words.")
    entry = {"rule_key": KEY, "rule_fingerprint": _fp(tmp_path, [new]),
             "reason": "Typo.", "reviewer": "fake", "date": bad_date}
    assert not _check(tmp_path, [base], [new], attestations=[entry]).ok


def test_removal_attestation_covers_only_the_rule_it_saw_removed(tmp_path):
    """A rule that came back and was removed again is a new decision."""
    first = _row(severity="contraindicated")
    second = _row(severity="contraindicated", mechanism="Came back reworded.")
    entry = {"rule_key": KEY, "rule_fingerprint": f"removed:{_fp(tmp_path, [first])}",
             "reason": "Withdrawn.", "reviewer": "fake", "date": "2026-11-03"}
    assert _check(tmp_path, [first], [], attestations=[entry]).ok
    assert not _check(tmp_path, [second], [], attestations=[entry]).ok


@pytest.mark.parametrize(
    "candidate",
    [[], [_row(severity="caution")]],
    ids=["removed", "lowered"],
)
def test_weakening_a_hard_rule_is_a_reviewed_decision(tmp_path, candidate):
    """The fast lane can't subtract, so no alert fixes it: a person signs it."""
    result = _check(tmp_path, [_row(severity="contraindicated")], candidate)
    assert not result.ok
    assert "alert or a reviewed attestation" in result.errors[0]


def test_retired_hard_rule_counts_as_removed(tmp_path):
    result = _check(
        tmp_path,
        [_row(severity="contraindicated")],
        [_row(severity="contraindicated", retired_at="2026-11-01")],
    )
    assert not result.ok


@pytest.mark.parametrize(
    "base, new",
    [
        ([], [_row(severity="monitor")]),
        ([_row()], [_row(mechanism="Reworded caution.")]),
        ([_row()], []),
        ([_row()], [_row(severity="monitor")]),
        ([_row(severity="avoid")], [_row(severity="avoid", last_updated="2027-01-01")]),
        ([_row(severity="avoid")], [_row(severity="avoid", source_urls_json='["https://x.test"]')]),
    ],
    ids=["new-monitor", "caution-reworded", "caution-removed", "caution-lowered",
         "timestamp-only", "source-list-only"],
)
def test_not_material(tmp_path, base, new):
    result = _check(tmp_path, base, new)
    assert result.ok, result.errors


def test_raising_a_lower_tier_needs_review(tmp_path):
    result = _check(tmp_path, [_row(severity="monitor")], [_row()])
    assert not result.ok
    assert "alert or a reviewed attestation" in result.errors[0]


@pytest.mark.parametrize(
    "agent",
    [
        {"agent1_type": "drug", "agent2_type": "drug"},
        {"agent1_type": "supplement", "agent2_type": "supplement"},
        {"agent2_type": "food"},
    ],
    ids=["med-med", "sup-sup", "food"],
)
def test_pair_an_alert_cannot_express_needs_attestation(tmp_path, agent):
    row = _row(severity="contraindicated", **agent)
    result = _check(tmp_path, [], [row])
    assert not result.ok
    assert "alert or a reviewed attestation" in result.errors[0]


def test_profile_drug_class_rule_is_compared_per_sub_rule(tmp_path):
    result = _check(
        tmp_path, base_rules=[_rule()], cand_rules=[_rule(severity="contraindicated")],
    )
    assert not result.ok
    assert DRUG_KEY in result.errors[0]
    assert "needs a published" in result.errors[0]

    rule = _rule(severity="contraindicated")
    covered = _check(
        tmp_path, base_rules=[_rule()], cand_rules=[rule],
        records=[_alert(_fp(tmp_path, rules=[rule], key=DRUG_KEY), rule_id=DRUG_KEY)],
    )
    assert covered.ok, covered.errors


GROWN = {"class:fake_class": ["111", "222"], "class:fake_test_medications": ["333", "444"]}
SAME = {"class:fake_class": ["111"], "class:fake_test_medications": ["333"]}


def test_class_membership_growth_widens_a_hard_profile_rule(tmp_path):
    """A medicine added to a class the gate names now gets the warning: same rule, different people."""
    rule = _rule(severity="avoid")
    result = _check(tmp_path, base_rules=[rule], cand_rules=[rule], base_classes=SAME, cand_classes=GROWN)
    assert not result.ok
    assert DRUG_KEY in result.errors[0] and "applies to different people" in result.errors[0]

    covered = _check(
        tmp_path, base_rules=[rule], cand_rules=[rule], base_classes=SAME, cand_classes=GROWN,
        records=[_alert(_fp(tmp_path, rules=[rule], key=DRUG_KEY, classes=GROWN), rule_id=DRUG_KEY)],
    )
    assert covered.ok, covered.errors


def test_class_membership_growth_widens_a_hard_class_pair(tmp_path):
    row = _row(severity="contraindicated", agent1_id="class:fake_test_medications")
    result = _check(tmp_path, [row], [row], base_classes=SAME, cand_classes=GROWN)
    assert not result.ok
    assert KEY in result.errors[0] and "applies to different people" in result.errors[0]


def test_class_membership_changes_the_rule_does_not_name_or_below_hard_are_not_material(tmp_path):
    other = {**SAME, "class:unrelated": ["999"]}
    hard = _rule(severity="avoid")
    assert _check(tmp_path, base_rules=[hard], cand_rules=[hard], base_classes=SAME, cand_classes=other).ok
    soft = _rule(severity="caution")
    assert _check(tmp_path, base_rules=[soft], cand_rules=[soft], base_classes=SAME, cand_classes=GROWN).ok


def test_rules_without_class_references_keep_their_fingerprint(tmp_path):
    """Existing attestations on condition, dose and life-stage rules stay bound to the same fingerprint."""
    rule = _rule(severity="avoid", gate_ids=())
    rule["drug_class_rules"][0]["drug_class_id"] = "not_in_the_map"
    assert _fp(tmp_path, rules=[rule], key=f"{PROFILE_RULE}#drug_class:not_in_the_map") == _fp(
        tmp_path, rules=[rule], key=f"{PROFILE_RULE}#drug_class:not_in_the_map", classes=GROWN)


def test_profile_class_ids_follow_the_app_crosswalk(tmp_path):
    """The app maps class:antiplatelet_agents to profile id `antiplatelets`; membership follows it."""
    rule = _rule(severity="avoid", gate_ids=("antiplatelets",))
    rule["drug_class_rules"][0]["drug_class_id"] = "antiplatelets"
    key = f"{PROFILE_RULE}#drug_class:antiplatelets"
    result = _check(tmp_path, base_rules=[rule], cand_rules=[rule],
                    base_classes={"class:antiplatelet_agents": ["1"]},
                    cand_classes={"class:antiplatelet_agents": ["1", "2"]})
    assert not result.ok and key in result.errors[0]


def test_profile_review_metadata_alone_is_not_a_change(tmp_path):
    rule = _rule(severity="avoid")
    result = _check(
        tmp_path, base_rules=[rule], cand_rules=[{**rule, "last_reviewed": "2027-01-01"}],
    )
    assert result.ok, result.errors


def test_new_pregnancy_contraindication_needs_an_alert(tmp_path):
    """An attestation is not a notification: the device can match this locally."""
    base = {**_rule(), "drug_class_rules": [], "condition_rules": []}
    new = {**base, "condition_rules": [
        {"condition_id": "pregnancy", "severity": "contraindicated", "mechanism": "Fake."}
    ]}
    key = f"{PROFILE_RULE}#condition:pregnancy"
    result = _check(tmp_path, base_rules=[base], cand_rules=[new])
    assert not result.ok
    assert key in result.errors[0]
    assert "needs a published" in result.errors[0]

    fingerprint = _fp(tmp_path, rules=[new], key=key)
    attested = _check(
        tmp_path, base_rules=[base], cand_rules=[new],
        attestations=[{"rule_key": key, "rule_fingerprint": fingerprint, "reason": "r",
                       "reviewer": "fake", "date": "2026-11-03"}],
    )
    assert not attested.ok
    covered = _check(
        tmp_path, base_rules=[base], cand_rules=[new],
        records=[_alert(fingerprint, rule_id=key)],
    )
    assert covered.ok, covered.errors


def test_new_life_stage_contraindication_needs_an_alert(tmp_path):
    base = {**_rule(), "drug_class_rules": []}
    new = {**base, "pregnancy_lactation": {"pregnancy_category": "contraindicated"}}
    result = _check(tmp_path, base_rules=[base], cand_rules=[new])
    assert not result.ok
    assert "needs a published" in result.errors[0]


def test_absent_life_stage_tier_is_absent_not_contraindicated(tmp_path):
    """Only wording changed, on a block whose other tier is simply not stated."""
    base = {**_rule(), "drug_class_rules": [], "pregnancy_lactation": {
        "pregnancy_category": "caution", "lactation_category": None, "notes": "Old."}}
    new = {**base, "pregnancy_lactation": {**base["pregnancy_lactation"], "notes": "New."}}
    result = _check(tmp_path, base_rules=[base], cand_rules=[new])
    assert result.ok, result.errors


def test_life_stage_block_with_no_tier_at_all_is_not_hard(tmp_path):
    base = {**_rule(), "drug_class_rules": [], "pregnancy_lactation": {"notes": "Old."}}
    new = {**base, "pregnancy_lactation": {"notes": "New."}}
    assert _check(tmp_path, base_rules=[base], cand_rules=[new]).ok


def test_invalid_life_stage_tier_still_fails_closed(tmp_path):
    base = {**_rule(), "drug_class_rules": [], "pregnancy_lactation": {
        "pregnancy_category": "caution", "lactation_category": None}}
    new = {**base, "pregnancy_lactation": {
        "pregnancy_category": "caution", "lactation_category": "bogus"}}
    assert not _check(tmp_path, base_rules=[base], cand_rules=[new]).ok


@pytest.mark.parametrize(
    "block_field", ["pregnancy_category", "lactation_category"]
)
def test_life_stage_block_tiers_are_read(tmp_path, block_field):
    base = {**_rule(), "drug_class_rules": [], "pregnancy_lactation": {block_field: "caution"}}
    new = {**base, "pregnancy_lactation": {block_field: "contraindicated"}}
    result = _check(tmp_path, base_rules=[base], cand_rules=[new])
    assert not result.ok


def test_unknown_tier_fails_closed_as_hard(tmp_path):
    result = _check(tmp_path, [], [_row(severity="severe_future_tier")])
    assert not result.ok


def test_when_live_revisions_are_known_the_alert_must_already_be_live(tmp_path):
    row = _row(severity="contraindicated")
    record = _alert(_fp(tmp_path, [row]), revision=2)
    assert not _check(tmp_path, [], [row], records=[record], live_revisions={}).ok
    assert not _check(
        tmp_path, [], [row], records=[record], live_revisions={"SA_9999_0001": 1}
    ).ok
    assert _check(
        tmp_path, [], [row], records=[record], live_revisions={"SA_9999_0001": 2}
    ).ok


def test_live_revisions_are_only_asked_for_when_an_alert_is_needed(tmp_path):
    def unreachable():
        raise AssertionError("no material change, so no network")

    result = _check(tmp_path, [_row()], [_row()], live_revisions=unreachable)
    assert result.ok


def test_unreachable_live_feed_fails_closed(tmp_path):
    def down():
        raise OSError("offline")

    row = _row(severity="contraindicated")
    result = _check(tmp_path, [], [row], records=[_alert(_fp(tmp_path, [row]))], live_revisions=down)
    assert not result.ok
    assert "could not read the live alert feed" in result.errors[0]


def test_a_damaged_candidate_fails_closed(tmp_path):
    bad = tmp_path / "bad.sqlite"
    bad.write_text("not a database")
    good = _db(tmp_path / "good.sqlite")
    with pytest.raises(gate.RuleGateError):
        gate.check_rule_changes(bad, good, alerts_dir=_alerts_dir(tmp_path))


def test_cli_exit_codes(tmp_path, capsys):
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    baseline = _db(tmp_path / "b" / "db.sqlite", [_row()])
    candidate = _db(tmp_path / "c" / "db.sqlite", [_row(severity="contraindicated")])
    alerts = _alerts_dir(tmp_path)
    args = ["--candidate", str(candidate), "--baseline", str(baseline),
            "--alerts-dir", str(alerts), "--no-live-check"]
    assert gate.main(args) == 1
    assert KEY in capsys.readouterr().err
    assert gate.main(["--candidate", str(baseline), "--baseline", str(baseline),
                      "--alerts-dir", str(alerts), "--no-live-check"]) == 0


def test_cli_prints_a_fingerprint_for_the_alert_author(tmp_path, capsys):
    db = _db(tmp_path / "db.sqlite", [_row()])
    assert gate.main(["--fingerprint", KEY, "--candidate", str(db)]) == 0
    assert capsys.readouterr().out.strip() == gate.rule_fingerprint(db, KEY)


def test_release_full_runs_the_gate_before_anything_publishes():
    source = (Path(gate.__file__).parent / "release_full.sh").read_text()
    position = source.index("scripts/rule_change_gate.py")
    assert position < source.index("--publish-flutter-pin \"$FLUTTER_REPO\"")
    assert position < source.index("# Step 5: Sync to Supabase")


# --- the emergency path: a catalog carrying a ban must not wait on unrelated review

BAN = {
    "alert_id": "SA_9999_0002",
    "revision": 1,
    "event_type": "ingredient_ban",
    "status": "published",
    "retracted": False,
    "effective_date": "2026-11-01",
    "scope": {"ingredient_canonical_ids": ["fake_bannedroot"], "dsld_ids": []},
}
OVERRIDE = {
    "alert_id": "SA_9999_0002",
    "revision": 1,
    "reason": "Fictional ban must reach the catalog tonight.",
    "approved_by": "fake",
    "date": "2026-11-03",
}
HELD = {
    "id": PROFILE_RULE,
    "subject_ref": {"db": "fake", "canonical_id": "fake_fakeroot"},
    "drug_class_rules": [{
        "drug_class_id": "fake_class", "severity": "contraindicated",
        "alert_headline": "Pinned.", "alert_body": "Pinned body.",
    }],
}
HELD_NEW = {
    **HELD,
    "drug_class_rules": [{**HELD["drug_class_rules"][0], "alert_body": "Reworded, unreviewed."}],
}


def _emergency(tmp_path, *, blobs=(), overrides=(OVERRIDE,), records=(BAN,), base=(HELD,),
               cand=(HELD_NEW,), live=None, blob_fields=None):
    (tmp_path / "b").mkdir(exist_ok=True)
    (tmp_path / "c").mkdir(exist_ok=True)
    baseline = _db(tmp_path / "b" / "db.sqlite", (), base)
    candidate = _db(tmp_path / "c" / "db.sqlite", (), cand)
    alerts = _alerts_dir(tmp_path, *records)
    (alerts / gate.EMERGENCY_FILENAME).write_text(json.dumps({"overrides": list(overrides)}))
    blob_dir = tmp_path / "blobs"
    shutil.rmtree(blob_dir, ignore_errors=True)
    blob_dir.mkdir()
    for index, warnings in enumerate(blobs):
        (blob_dir / f"{index}.json").write_text(
            json.dumps({"warnings": warnings, **(blob_fields or {})})
        )
    return gate.check_emergency_catalog(
        candidate, baseline, blob_dir, alerts_dir=alerts,
        live_revisions={"SA_9999_0002": 1} if live is None else live, today="2026-11-03",
    )


def _warning(body):
    return {"source_rule_id": PROFILE_RULE, "severity": "contraindicated",
            "condition_ids": [], "drug_class_ids": ["fake_class"],
            "alert_headline": "Pinned.", "alert_body": body}


def test_emergency_passes_an_unrelated_hold_the_catalog_does_not_carry(tmp_path):
    result = _emergency(tmp_path, blobs=[[_warning("Pinned body.")], []])
    assert result.ok, result.errors
    assert result.record["alert_id"] == "SA_9999_0002"
    assert result.record["approved_by"] == "fake"
    assert result.record["held_rule_keys"] == [DRUG_KEY]


def test_emergency_refuses_when_a_blob_carries_the_held_change(tmp_path):
    result = _emergency(tmp_path, blobs=[[_warning("Reworded, unreviewed.")]])
    assert not result.ok
    assert DRUG_KEY in result.errors[0]
    assert "carried by" in result.errors[0]


@pytest.mark.parametrize("field", ["warnings", "warnings_profile_gated"])
def test_emergency_reads_every_list_a_blob_carries_rules_in(tmp_path, field):
    result = _emergency(
        tmp_path,
        blobs=[[]],
        blob_fields={field: [_warning("Reworded, unreviewed.")]},
    )
    assert not result.ok
    assert "carried by" in result.errors[0]


def test_emergency_counts_the_detail_field_too(tmp_path):
    warning = {**_warning("Pinned body."), "detail": "Reworded, unreviewed."}
    assert not _emergency(tmp_path, blobs=[[warning]]).ok


RAISED_BASE = {
    **HELD,
    "drug_class_rules": [{"drug_class_id": "fake_class", "severity": "caution"}],
    "condition_rules": [{"condition_id": "fake_condition", "severity": "avoid"}],
}
RAISED_CAND = {
    **RAISED_BASE,
    "drug_class_rules": [{"drug_class_id": "fake_class", "severity": "avoid"}],
}


def _target_warning(severity, *, condition_ids=(), drug_class_ids=()):
    return {"source_rule_id": PROFILE_RULE, "severity": severity,
            "condition_ids": list(condition_ids), "drug_class_ids": list(drug_class_ids)}


def test_emergency_sees_a_raised_tier_the_rule_already_uses_elsewhere(tmp_path):
    """Avoid is in the pinned rule, but not for this drug class."""
    result = _emergency(
        tmp_path, base=(RAISED_BASE,), cand=(RAISED_CAND,),
        blobs=[[_target_warning("avoid", drug_class_ids=["fake_class"])]],
    )
    assert not result.ok
    assert "carried by" in result.errors[0]


def test_emergency_passes_the_same_tier_on_the_target_that_always_had_it(tmp_path):
    result = _emergency(
        tmp_path, base=(RAISED_BASE,), cand=(RAISED_CAND,),
        blobs=[[_target_warning("avoid", condition_ids=["fake_condition"])]],
    )
    assert result.ok, result.errors


def test_emergency_refuses_a_tier_on_a_target_the_pinned_rule_lacks(tmp_path):
    result = _emergency(
        tmp_path, base=(RAISED_BASE,), cand=(RAISED_CAND,),
        blobs=[[_target_warning("avoid", condition_ids=["fake_other"])]],
    )
    assert not result.ok


def _summary(bucket_field, target, *, severity="avoid", rule_ids=(PROFILE_RULE,), actions=()):
    return {"interaction_summary": {
        "highest_severity": severity,
        bucket_field: {target: {"label": target, "highest_severity": severity,
                                "rule_ids": list(rule_ids), "actions": list(actions)}},
    }}


def test_emergency_sees_a_raised_tier_in_the_blob_summary(tmp_path):
    """The Fit score and the core hint read this. Its tier names no single rule."""
    result = _emergency(
        tmp_path, base=(RAISED_BASE,), cand=(RAISED_CAND,), blobs=[[]],
        blob_fields=_summary("drug_class_summary", "fake_class"),
    )
    assert not result.ok
    assert "carried by" in result.errors[0]


def test_emergency_sees_a_new_action_in_the_blob_summary(tmp_path):
    cand = {**HELD, "drug_class_rules": [{**HELD["drug_class_rules"][0], "action": "Reworded, unreviewed."}]}
    result = _emergency(
        tmp_path, cand=(cand,), blobs=[[]],
        blob_fields=_summary("drug_class_summary", "fake_class", severity="contraindicated",
                             actions=["Reworded, unreviewed."]),
    )
    assert not result.ok


@pytest.mark.parametrize(
    "fields",
    [
        _summary("drug_class_summary", "fake_class", rule_ids=("RULE_FAKE_OTHER",)),
        _summary("condition_summary", "fake_condition"),
    ],
    ids=["another rule's bucket", "the target whose tier did not change"],
)
def test_emergency_summary_check_stays_on_the_held_change(tmp_path, fields):
    result = _emergency(
        tmp_path, base=(RAISED_BASE,), cand=(RAISED_CAND,), blobs=[[]], blob_fields=fields,
    )
    assert result.ok, result.errors


def test_tiers_by_target_hold_every_tier_export_can_derive():
    """So the check doesn't refuse an unchanged rule."""
    rule = {
        **HELD,
        "drug_class_rules": [{"drug_class_id": "fake_class", "severity": "caution"}],
        "condition_rules": [{"condition_id": "pregnancy", "severity": "avoid"}],
        "dose_thresholds": [
            {"scope": "condition", "target_id": "fake_condition",
             "severity_if_met": "avoid", "severity_if_not_met": "monitor"},
            {"scope": None, "severity_if_met": "caution"},
        ],
        "pregnancy_lactation": {"pregnancy_category": "avoid", "lactation_category": "caution"},
    }
    tiers = gate._tiers_by_target(rule)
    assert tiers[("drug_class", "fake_class")] == {"caution"}
    assert tiers[("condition", "pregnancy")] == {"avoid"}
    assert tiers[("condition", "lactation")] == {"caution"}
    assert tiers[("condition", "fake_condition")] == {"avoid", "monitor"}
    assert tiers[("dose", "")] == {"caution", "informational"}


def test_emergency_uses_the_alerts_latest_revision(tmp_path):
    """Revision 1 was withdrawn by revision 2: it can't justify going early."""
    withdrawn = {**BAN, "revision": 2, "status": "retracted", "retracted": True}
    assert not _emergency(tmp_path, records=(BAN, withdrawn)).ok


def test_a_rule_an_alert_cannot_express_can_still_be_attested(tmp_path):
    """A gate with a form or a dose needs a product in hand, so no alert can carry it."""
    empty = {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": []}
    gate = {
        "gate_type": "condition",
        "requires": {**empty, "conditions_any": ["pregnancy"]},
        "excludes": {**empty, "product_forms_any": ["topical"], "nutrient_forms_any": []},
        "dose": None,
    }
    base = {**_rule(), "drug_class_rules": [], "condition_rules": []}
    new = {**base, "condition_rules": [{
        "condition_id": "pregnancy", "severity": "contraindicated", "profile_gate": gate,
    }]}
    key = f"{PROFILE_RULE}#condition:pregnancy"
    fingerprint = _fp(tmp_path, rules=[new], key=key)
    assert _check(
        tmp_path, base_rules=[base], cand_rules=[new],
        attestations=[{"rule_key": key, "rule_fingerprint": fingerprint, "reason": "r",
                       "reviewer": "fake", "date": "2026-11-03"}],
    ).ok


def test_emergency_refuses_a_held_removal_it_cannot_prove_absent(tmp_path):
    result = _emergency(tmp_path, cand=())
    assert not result.ok


@pytest.mark.parametrize(
    "overrides",
    [
        (),
        ({**OVERRIDE, "date": "2026-11-01"},),
        ({**OVERRIDE, "revision": 2},),
        ({**OVERRIDE, "reason": " "},),
        ({**OVERRIDE, "approved_by": ""},),
    ],
    ids=["none", "stale", "other-revision", "no-reason", "no-approver"],
)
def test_emergency_needs_a_complete_override_for_today(tmp_path, overrides):
    assert not _emergency(tmp_path, overrides=overrides).ok


@pytest.mark.parametrize(
    "records",
    [
        (),
        ({**BAN, "event_type": "interaction_rule"},),
        ({**BAN, "status": "draft"},),
        ({**BAN, "status": "retracted", "retracted": True},),
    ],
    ids=["missing", "not-a-ban", "draft", "retracted"],
)
def test_emergency_needs_a_real_ban_or_recall(tmp_path, records):
    assert not _emergency(tmp_path, records=records).ok


def test_emergency_alert_must_already_be_live(tmp_path):
    assert not _emergency(tmp_path, live={}).ok


def test_emergency_exempts_only_the_named_bans_own_rule(tmp_path):
    ban_rule = {
        "id": "RULE_FAKE_BANNEDROOT",
        "subject_ref": {"db": "fake", "canonical_id": "fake_bannedroot"},
        "condition_rules": [{"condition_id": "pregnancy", "severity": "contraindicated",
                             "alert_headline": "Banned.", "alert_body": "Banned body."}],
    }
    result = _emergency(
        tmp_path, base=(), cand=(ban_rule,),
        blobs=[[{"source_rule_id": "RULE_FAKE_BANNEDROOT", "severity": "contraindicated",
                 "alert_headline": "Banned.", "alert_body": "Banned body."}]],
    )
    assert result.ok, result.errors
    assert result.record["held_rule_keys"] == []


def test_emergency_cli_writes_its_record(tmp_path, monkeypatch, capsys):
    today = gate.date.today().isoformat()
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    baseline = _db(tmp_path / "b" / "db.sqlite", (), (HELD,))
    candidate = _db(tmp_path / "c" / "db.sqlite", (), (HELD_NEW,))
    alerts = _alerts_dir(tmp_path, BAN)
    (alerts / gate.EMERGENCY_FILENAME).write_text(json.dumps({"overrides": [{**OVERRIDE, "date": today}]}))
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "1.json").write_text(json.dumps({"warnings": []}))
    report = tmp_path / "report.json"
    monkeypatch.setattr(gate, "live_alert_revisions", lambda: {"SA_9999_0002": 1})

    code = gate.main([
        "--candidate", str(candidate), "--baseline", str(baseline), "--alerts-dir", str(alerts),
        "--emergency", "--blobs-dir", str(blobs), "--report", str(report),
    ])

    assert code == 0
    assert "EMERGENCY OVERRIDE" in capsys.readouterr().out
    assert json.loads(report.read_text())["held_rule_keys"] == [DRUG_KEY]


def test_the_normal_gate_ignores_an_emergency_override(tmp_path):
    """The artifact gate and the app pin have no emergency mode."""
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    baseline = _db(tmp_path / "b" / "db.sqlite", (), (HELD,))
    candidate = _db(tmp_path / "c" / "db.sqlite", (), (HELD_NEW,))
    alerts = _alerts_dir(tmp_path, BAN)
    (alerts / gate.EMERGENCY_FILENAME).write_text(json.dumps({"overrides": [OVERRIDE]}))
    assert not gate.check_rule_changes(
        candidate, baseline, alerts_dir=alerts, live_revisions={"SA_9999_0002": 1},
        today="2026-11-03",
    ).ok


def test_release_full_emergency_path_never_moves_the_pin():
    source = (Path(gate.__file__).parent / "release_full.sh").read_text()
    assert '(( SKIP_FLUTTER == 1 )) || { err "--emergency-catalog needs --skip-flutter"' in source
    assert "--emergency --blobs-dir" in source


def test_the_fast_lane_never_waits_on_the_rule_gate():
    """A ban or recall reaches phones through its own script, whatever is held."""
    source = (Path(gate.__file__).parent / "sync_safety_alerts.py").read_text()
    assert "rule_change_gate" not in source
    assert "supabase_client" in source
