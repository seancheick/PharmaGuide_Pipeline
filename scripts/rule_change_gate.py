#!/usr/bin/env python3
"""Refuse to publish a material rule correction that has no alert.

Compares the candidate interaction DB with the one phones already hold (the DB
the app's hydration pin names). Reading the two artifacts, rather than a tracked
baseline, means there is no second copy of "what was published" to drift.

What a change requires
----------------------
needs an alert (nothing else satisfies it)
    A warning that can now reach someone it did not reach before, on a rule an
    `interaction_rule` alert can express: a medication x supplement pair, or a
    pregnancy, lactation or condition rule, at avoid or contraindicated that is
    new, was raised into that tier, or now applies to different people. An
    attestation is not a notification.

needs an alert or a reviewed attestation
    A change a person has to judge: a reworded or re-graded hard rule, a hard
    rule removed or lowered (the fast lane may only add state, so no alert can
    subtract it), a lower tier raised, or a hard rule an alert cannot express
    (medication x medication, supplement x supplement, food, and dose thresholds,
    because the feed cannot see a stack's dose).

nothing
    Everything else, including new rules below avoid, wording changes below
    avoid, and metadata such as timestamps and source lists.

Both coverage records are bound to the rule's fingerprint, so an alert or
attestation written for an earlier correction cannot cover a later one.

The emergency catalog path
--------------------------
A ban or recall reaches phones through `sync_safety_alerts.py`, which never waits
on this gate. A catalog carrying that ban may need to follow while unrelated rule
changes wait on review. `--emergency` allows that only for a catalog-only release,
with a dated override in rule_gate_emergency_overrides.json that names a ban or
recall already live, and only when no detail blob carries a held change. Blobs
carry rule text too, so a held change a blob shows, or a removal or lowering no
blob can disprove, still refuses: sign it off or hold that rule edit back. The
interaction DB pin has no emergency mode.

Usage
-----
    python3 scripts/rule_change_gate.py --candidate scripts/dist/interaction_db.sqlite \\
        --pin "$FLUTTER_REPO/tool/interaction_db.release.json"
    python3 scripts/rule_change_gate.py --fingerprint RULE_KEY --candidate DB
    python3 scripts/rule_change_gate.py --candidate DB --pin PIN --emergency \\
        --blobs-dir scripts/dist/detail_blobs --report REPORT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from safety_alerts import is_active  # noqa: E402

ALERTS_DIR = SCRIPTS / "data" / "safety_alerts"
ATTESTATIONS_FILENAME = "rule_change_attestations.json"
EMERGENCY_FILENAME = "rule_gate_emergency_overrides.json"
_EMERGENCY_EVENT_TYPES = {"ingredient_ban", "product_recall"}

_RANK = {
    "contraindicated": 4,
    "avoid": 3,
    "caution": 2,
    "monitor": 1,
    "informational": 0,
    "no_data": 0,
    "safe": 0,
}
_HARD = _RANK["avoid"]
_MEDICATION_AGENTS = {"drug", "drug_class"}

# Interaction columns that say who is warned, and what they are told. Timestamps,
# version stamps and provenance lists are deliberately absent: they change on
# every rebuild and say nothing new to a user.
_WHO_COLUMNS = (
    "agent1_type", "agent1_id", "agent1_canonical_id", "agent1_drug_class",
    "agent2_type", "agent2_id", "agent2_canonical_id", "agent2_drug_class",
    "bidirectional", "dose_dependent", "dose_threshold_json", "profile_gate_json",
    "medication_exceptions_json",
)
_WHAT_COLUMNS = (
    "severity", "effect_type", "mechanism", "management", "evidence_level",
    "alert_style", "note_body", "practical_guidance", "dose_threshold_text",
    "direction", "materiality",
)
_PROFILE_VOLATILE = {"sources", "source_urls"}


class RuleGateError(RuntimeError):
    """The comparison itself could not run. Publication stops."""


@dataclass(frozen=True)
class Rule:
    key: str
    rank: int
    who: str
    fingerprint: str
    alertable: bool
    subject: str = ""


@dataclass
class GateResult:
    errors: List[str] = field(default_factory=list)
    changes: List[str] = field(default_factory=list)
    held: List[str] = field(default_factory=list)
    record: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rank(severity: Any) -> int:
    """An unknown tier fails closed as hard: it must never pass unreviewed."""
    return _RANK.get(str(severity or "").strip().lower(), _RANK["contraindicated"])


def _interaction_rule(row: Mapping[str, Any]) -> Rule:
    who = {name: row.get(name) for name in _WHO_COLUMNS}
    what = {name: row.get(name) for name in _WHAT_COLUMNS}
    types = {row.get("agent1_type"), row.get("agent2_type")}
    return Rule(
        key=str(row["id"]),
        rank=_rank(row.get("severity")),
        who=_digest(who),
        fingerprint=_digest({"who": who, "what": what}),
        alertable="supplement" in types and bool(types & _MEDICATION_AGENTS),
    )


def _sub_rule(
    key: str, canonical_id: str, sub: Mapping[str, Any], severity: Any, *, alertable: bool
) -> Rule:
    body = {k: v for k, v in sub.items() if k not in _PROFILE_VOLATILE}
    who = {
        "canonical_id": canonical_id,
        "profile_gate": sub.get("profile_gate"),
        "applies": key.rsplit("#", 1)[-1],
    }
    return Rule(
        key=key,
        rank=_rank(severity),
        who=_digest(who),
        fingerprint=_digest({"canonical_id": canonical_id, "body": body}),
        alertable=alertable,
        subject=canonical_id,
    )


def _profile_rules(rule: Mapping[str, Any]) -> Iterable[Rule]:
    """One entry per sub-rule: a rule's severity lives on each of them."""
    rule_id = str(rule.get("id"))
    canonical_id = str((rule.get("subject_ref") or {}).get("canonical_id") or "")
    for sub in rule.get("drug_class_rules") or []:
        yield _sub_rule(
            f"{rule_id}#drug_class:{sub.get('drug_class_id')}",
            canonical_id, sub, sub.get("severity"), alertable=True,
        )
    for sub in rule.get("condition_rules") or []:
        yield _sub_rule(
            f"{rule_id}#condition:{sub.get('condition_id')}",
            canonical_id, sub, sub.get("severity"), alertable=True,
        )
    for index, sub in enumerate(rule.get("dose_thresholds") or []):
        yield _sub_rule(
            f"{rule_id}#dose:{index}",
            canonical_id, sub, sub.get("severity_if_met"), alertable=False,
        )
    life_stage = rule.get("pregnancy_lactation")
    if isinstance(life_stage, dict) and life_stage:
        # An unstated tier is absent. A stated one we can't read still fails closed.
        stated = [
            tier
            for tier in (life_stage.get("pregnancy_category"), life_stage.get("lactation_category"))
            if tier is not None
        ]
        worst = max(stated, key=_rank) if stated else "informational"
        yield _sub_rule(
            f"{rule_id}#pregnancy_lactation", canonical_id, life_stage, worst, alertable=True
        )


def load_rules(db_path: Path) -> Dict[str, Rule]:
    """Every live rule in one interaction DB, keyed for comparison."""
    rules: Dict[str, Rule] = {}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            for row in con.execute("SELECT * FROM interactions"):
                if row["retired_at"]:
                    continue
                rule = _interaction_rule(dict(row))
                rules[rule.key] = rule
            for (raw,) in con.execute("SELECT rule_json FROM profile_warning_rules"):
                for rule in _profile_rules(json.loads(raw)):
                    rules[rule.key] = rule
        finally:
            con.close()
    except (sqlite3.Error, ValueError, TypeError, AttributeError) as exc:
        raise RuleGateError(f"could not read rules from {db_path}: {exc}") from exc
    return rules


def rule_fingerprint(db_path: Path, rule_key: str) -> str:
    """The value an alert's `interaction.rule_fingerprint` must carry."""
    rule = load_rules(db_path).get(rule_key)
    if rule is None:
        raise RuleGateError(f"{rule_key} is not in {db_path}")
    return rule.fingerprint


def _load_attestations(alerts_dir: Path) -> Dict[Tuple[str, str], Mapping[str, Any]]:
    path = alerts_dir / ATTESTATIONS_FILENAME
    if not path.is_file():
        return {}
    entries = json.loads(path.read_text(encoding="utf-8")).get("attestations") or []
    return {
        (str(entry.get("rule_key")), str(entry.get("rule_fingerprint"))): entry
        for entry in entries
        if all(str(entry.get(name) or "").strip() for name in ("reason", "reviewer", "date"))
    }


def _load_alerts(alerts_dir: Path, today: str) -> Dict[Tuple[str, str], Mapping[str, Any]]:
    covering: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    for path in sorted(alerts_dir.glob("SA_*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        interaction = record.get("interaction")
        if (
            record.get("event_type") == "interaction_rule"
            and isinstance(interaction, dict)
            and is_active(record, today)
        ):
            key = (str(interaction.get("rule_id")), str(interaction.get("rule_fingerprint")))
            covering[key] = record
    return covering


def _requirement(base: Optional[Rule], new: Optional[Rule]) -> Optional[Tuple[str, str]]:
    """(what is required, why), or None when the change is not material."""
    if new is None:
        return ("review", "removed a hard rule") if base and base.rank >= _HARD else None
    if base is None:
        if new.rank < _HARD:
            return None
        why = "new hard rule"
    elif base.fingerprint == new.fingerprint:
        return None
    elif new.rank >= _HARD and base.rank < _HARD:
        why = "raised into a hard tier"
    elif new.rank >= _HARD and base.who != new.who:
        why = "hard rule now applies to different people"
    elif new.rank < base.rank and base.rank >= _HARD:
        return "review", "lowered a hard rule"
    elif new.rank > base.rank:
        return "review", "raised a lower tier"
    elif new.rank >= _HARD:
        return "review", "changed the content of a hard rule"
    else:
        return None
    return ("alert" if new.alertable else "review"), why


LiveRevisions = Union[Mapping[str, int], Callable[[], Mapping[str, int]], None]


def check_rule_changes(
    candidate_db: Path,
    baseline_db: Path,
    alerts_dir: Path = ALERTS_DIR,
    live_revisions: LiveRevisions = None,
    today: Optional[str] = None,
) -> GateResult:
    """Compare two interaction DBs. Raises RuleGateError if either can't be read.

    `live_revisions` maps alert ids to the revision in the current public feed;
    when given, a covering alert must already be live there. It may be a callable
    so the network is touched only when an alert is actually needed.
    """
    today = today or date.today().isoformat()
    baseline = load_rules(baseline_db)
    candidate = load_rules(candidate_db)
    alerts = _load_alerts(alerts_dir, today)
    attestations = _load_attestations(alerts_dir)
    result = GateResult()
    live: Optional[Mapping[str, int]] = None
    live_failed = False

    for key in sorted(baseline.keys() | candidate.keys()):
        base, new = baseline.get(key), candidate.get(key)
        requirement = _requirement(base, new)
        if requirement is None:
            continue
        needed, why = requirement
        result.changes.append(f"{key}: {why}")
        fingerprint = new.fingerprint if new else "removed"
        alert = alerts.get((key, fingerprint))
        if alert is not None and live_revisions is not None:
            if live is None and not live_failed:
                try:
                    live = live_revisions() if callable(live_revisions) else live_revisions
                except Exception as exc:  # noqa: BLE001 - any failure means unverified
                    live_failed = True
                    result.errors.append(f"could not read the live alert feed: {exc}")
            if live_failed:
                continue
            if int((live or {}).get(alert["alert_id"], 0)) < int(alert["revision"]):
                result.held.append(key)
                result.errors.append(
                    f"{key}: {why}, and alert {alert['alert_id']} revision "
                    f"{alert['revision']} is not live yet. Publish the alert first."
                )
                continue
        if alert is not None:
            continue
        if needed == "review" and (key, fingerprint) in attestations:
            continue
        result.held.append(key)
        if needed == "alert":
            result.errors.append(
                f"{key}: {why} needs a published interaction_rule alert with "
                f"rule_fingerprint {fingerprint}"
            )
        else:
            result.errors.append(
                f"{key}: {why} needs an alert or a reviewed attestation in "
                f"{ATTESTATIONS_FILENAME} for rule_fingerprint {fingerprint}"
            )
    return result


def _load_emergency_ban(
    alerts_dir: Path, live_revisions: LiveRevisions, today: str
) -> Tuple[Optional[Mapping[str, Any]], Optional[Mapping[str, Any]], List[str]]:
    """The override dated today and the live ban or recall it names, or why not."""
    path = alerts_dir / EMERGENCY_FILENAME
    entries = json.loads(path.read_text(encoding="utf-8")).get("overrides") or [] if path.is_file() else []
    todays = [entry for entry in entries if entry.get("date") == today]
    if not todays:
        return None, None, [f"no override dated {today} in {EMERGENCY_FILENAME}"]
    override = todays[-1]
    missing = [n for n in ("alert_id", "reason", "approved_by") if not str(override.get(n) or "").strip()]
    if missing:
        return None, None, [f"the override needs {', '.join(missing)}"]
    records = (json.loads(p.read_text(encoding="utf-8")) for p in sorted(alerts_dir.glob("SA_*.json")))
    alert = next((r for r in records if r.get("alert_id") == override["alert_id"]), None)
    if alert is None:
        return None, None, [f"the override names {override['alert_id']}, which does not exist"]
    if alert.get("event_type") not in _EMERGENCY_EVENT_TYPES:
        return None, None, [f"{override['alert_id']} is not a ban or recall"]
    if not is_active(alert, today):
        return None, None, [f"{override['alert_id']} is not an active alert"]
    if override.get("revision") != alert.get("revision"):
        return None, None, [f"the override is for another revision of {override['alert_id']}"]
    try:
        live = live_revisions() if callable(live_revisions) else (live_revisions or {})
    except Exception as exc:  # noqa: BLE001 - any failure means unverified
        return None, None, [f"could not read the live alert feed: {exc}"]
    if int(live.get(alert["alert_id"], 0)) < int(alert["revision"]):
        return None, None, [f"{alert['alert_id']} is not live yet. Publish the alert first."]
    return override, alert, []


def _rule_strings(rule: Optional[Mapping[str, Any]]) -> set:
    found: set = set()

    def walk(value: Any) -> None:
        if isinstance(value, str):
            found.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(rule)
    return found


def _rule_json(db_path: Path) -> Dict[str, Mapping[str, Any]]:
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return {
                str(rule.get("id")): rule
                for rule in (json.loads(raw) for (raw,) in con.execute(
                    "SELECT rule_json FROM profile_warning_rules"
                ))
            }
        finally:
            con.close()
    except (sqlite3.Error, ValueError, TypeError, AttributeError) as exc:
        raise RuleGateError(f"could not read rules from {db_path}: {exc}") from exc


def _blobs_showing_new_content(
    blobs_dir: Path,
    held_ids: Iterable[str],
    pinned: Mapping[str, Mapping[str, Any]],
    candidate: Mapping[str, Mapping[str, Any]],
) -> Dict[str, int]:
    """Warnings per held rule whose text or tier is not what phones hold now.

    Life-stage headlines and actions are derived at export, so those two fields
    count only when the candidate rule authored them. Tier and body always count.
    """
    known = {rule_id: _rule_strings(pinned.get(rule_id)) for rule_id in held_ids}
    authored = {rule_id: _rule_strings(candidate.get(rule_id)) for rule_id in held_ids}
    showing: Dict[str, int] = {}
    if not blobs_dir.is_dir():
        raise RuleGateError(f"{blobs_dir} is not a directory of detail blobs")
    with os.scandir(blobs_dir) as entries:
        for entry in entries:
            if not entry.name.endswith(".json"):
                continue
            with open(entry.path, encoding="utf-8") as handle:
                warnings = json.load(handle).get("warnings") or []
            for warning in warnings:
                rule_id = warning.get("source_rule_id")
                if rule_id not in known:
                    continue
                new = any(
                    warning.get(name) is not None and warning[name] not in known[rule_id]
                    for name in ("severity", "alert_body")
                ) or any(
                    warning.get(name) in authored[rule_id] - known[rule_id]
                    for name in ("alert_headline", "action")
                )
                if new:
                    showing[rule_id] = showing.get(rule_id, 0) + 1
    return showing


def check_emergency_catalog(
    candidate_db: Path,
    baseline_db: Path,
    blobs_dir: Path,
    alerts_dir: Path = ALERTS_DIR,
    live_revisions: LiveRevisions = None,
    today: Optional[str] = None,
) -> GateResult:
    """May this catalog go out ahead of unrelated rule review? Fails closed."""
    today = today or date.today().isoformat()
    override, alert, problems = _load_emergency_ban(alerts_dir, live_revisions, today)
    if problems:
        return GateResult(errors=[f"emergency override refused: {p}" for p in problems])
    full = check_rule_changes(
        candidate_db, baseline_db, alerts_dir=alerts_dir, live_revisions=live_revisions, today=today
    )
    if len(full.errors) != len(full.held):
        return GateResult(errors=full.errors, changes=full.changes)

    baseline, candidate = load_rules(baseline_db), load_rules(candidate_db)
    # The named ban already reaches everyone holding its ingredient, so it covers
    # that ingredient's rule being added or raised. Never its removal or lowering.
    banned = set((alert.get("scope") or {}).get("ingredient_canonical_ids") or [])
    still_held = [
        key
        for key in full.held
        if not (
            key in candidate
            and candidate[key].subject in banned
            and candidate[key].rank >= _HARD
            and (key not in baseline or candidate[key].rank >= baseline[key].rank)
        )
    ]
    result = GateResult(changes=full.changes, held=still_held)
    for key in still_held:
        if key not in candidate or candidate[key].rank < baseline.get(key, candidate[key]).rank:
            result.errors.append(
                f"{key}: a removal or lowering shows in a blob as a missing or milder "
                "warning, which no blob can disprove. Sign it off or hold that edit back."
            )
    held_ids = {key.split("#", 1)[0] for key in still_held}
    showing = _blobs_showing_new_content(
        blobs_dir, held_ids, _rule_json(baseline_db), _rule_json(candidate_db)
    )
    for key in still_held:
        rule_id = key.split("#", 1)[0]
        if rule_id in showing:
            result.errors.append(
                f"{key}: unreviewed rule content is carried by {showing[rule_id]} blob "
                "warning(s). Sign it off or hold that edit back."
            )
    result.record = {
        "alert_id": alert["alert_id"],
        "revision": alert["revision"],
        "event_type": alert["event_type"],
        "reason": override["reason"],
        "approved_by": override["approved_by"],
        "date": today,
        "held_rule_keys": still_held,
        "covered_by_alert": sorted(set(full.held) - set(still_held)),
    }
    return result


def fetch_pinned_db(pin: Mapping[str, Any], destination: Path) -> None:
    """Download the DB the app pin names and verify it against the pin's digest."""
    with urllib.request.urlopen(pin["url"], timeout=300) as response, open(destination, "wb") as out:
        shutil.copyfileobj(response, out)
    with open(destination, "rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual != pin["sha256"]:
        raise RuleGateError(f"{pin['url']} hashes to {actual}, not the pinned {pin['sha256']}")


def live_alert_revisions() -> Mapping[str, int]:
    """`latest_revisions` from the current public feed row."""
    from supabase_client import get_supabase_client

    response = (
        get_supabase_client()
        .table("safety_alert_releases")
        .select("manifest")
        .eq("is_current", True)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return (rows[0].get("manifest") or {}).get("latest_revisions") or {} if rows else {}


def enforce_against_pin(
    candidate_db: Path,
    pin: Mapping[str, Any],
    *,
    alerts_dir: Path = ALERTS_DIR,
    fetch: Callable[[Mapping[str, Any], Path], None] = fetch_pinned_db,
    live_revisions: LiveRevisions = live_alert_revisions,
) -> GateResult:
    """Compare the candidate with the DB phones hold now. Same bytes, no work."""
    with open(candidate_db, "rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() == pin.get("sha256"):
            return GateResult()
    with tempfile.TemporaryDirectory() as directory:
        baseline = Path(directory) / "pinned_interaction_db.sqlite"
        fetch(pin, baseline)
        return check_rule_changes(
            candidate_db, baseline, alerts_dir=alerts_dir, live_revisions=live_revisions
        )


def enforce_emergency_against_pin(
    candidate_db: Path,
    pin: Mapping[str, Any],
    blobs_dir: Path,
    *,
    alerts_dir: Path = ALERTS_DIR,
    fetch: Callable[[Mapping[str, Any], Path], None] = fetch_pinned_db,
    live_revisions: LiveRevisions = live_alert_revisions,
) -> GateResult:
    with tempfile.TemporaryDirectory() as directory:
        baseline = Path(directory) / "pinned_interaction_db.sqlite"
        fetch(pin, baseline)
        return check_emergency_catalog(
            candidate_db, baseline, blobs_dir, alerts_dir=alerts_dir, live_revisions=live_revisions
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="compare with this DB instead of the pin")
    parser.add_argument("--pin", type=Path, help="the app's tool/interaction_db.release.json")
    parser.add_argument("--alerts-dir", type=Path, default=ALERTS_DIR)
    parser.add_argument("--no-live-check", action="store_true",
                        help="don't require covering alerts to be in the public feed")
    parser.add_argument("--fingerprint", metavar="RULE_KEY",
                        help="print the rule_fingerprint an alert for this rule must carry")
    parser.add_argument("--emergency", action="store_true",
                        help="a catalog-only release ahead of unrelated rule review")
    parser.add_argument("--blobs-dir", type=Path, help="detail blobs, with --emergency")
    parser.add_argument("--report", type=Path, help="write the override record here, with --emergency")
    args = parser.parse_args(argv)
    if args.emergency and (args.blobs_dir is None or args.no_live_check):
        parser.error("--emergency needs --blobs-dir and the live feed check")

    try:
        if args.fingerprint:
            print(rule_fingerprint(args.candidate, args.fingerprint))
            return 0
        live = None if args.no_live_check else live_alert_revisions
        if args.emergency:
            if args.baseline:
                result = check_emergency_catalog(
                    args.candidate, args.baseline, args.blobs_dir,
                    alerts_dir=args.alerts_dir, live_revisions=live,
                )
            elif args.pin:
                result = enforce_emergency_against_pin(
                    args.candidate, json.loads(args.pin.read_text(encoding="utf-8")),
                    args.blobs_dir, alerts_dir=args.alerts_dir, live_revisions=live,
                )
            else:
                parser.error("pass --baseline or --pin")
            if result.ok:
                print(f"[rule-gate] EMERGENCY OVERRIDE: {json.dumps(result.record, sort_keys=True)}")
                if args.report:
                    args.report.write_text(json.dumps(result.record, indent=2, sort_keys=True) + "\n")
        elif args.baseline:
            result = check_rule_changes(
                args.candidate, args.baseline, alerts_dir=args.alerts_dir, live_revisions=live
            )
        elif args.pin:
            result = enforce_against_pin(
                args.candidate,
                json.loads(args.pin.read_text(encoding="utf-8")),
                alerts_dir=args.alerts_dir,
                live_revisions=live,
            )
        else:
            parser.error("pass --baseline or --pin")
    except (RuleGateError, OSError, ValueError) as exc:
        print(f"[rule-gate] REFUSED: {exc}", file=sys.stderr)
        return 1

    for message in result.errors:
        print(f"[rule-gate] REFUSED: {message}", file=sys.stderr)
    if result.ok:
        print(f"[rule-gate] passed ({len(result.changes)} material change(s), all covered)")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
