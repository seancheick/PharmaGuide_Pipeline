"""
Guard against duplicate drug_class_rules within a single rule entry.

The 2026-04-30 W/M/L/C batch renamed `mao_inhibitors` → `maois` (canonical
clinical_risk_taxonomy ID). The rename was applied post-hoc to data, after
the per-key upsert in backfill.py had already committed entries with the
old key. Result: two `maois` entries existed inside RULE_INGREDIENT_ST_JOHNS_WORT
and RULE_IQM_5HTP_SEROTONIN — same drug_class, different alert copy, both
firing for the same user, looking like a duplication bug to Flutter.

Spot-check on the multi-CYP-active stack caught the dupes; this test
locks the invariant so the same shape can't drift in again.
"""
from __future__ import annotations
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"


def test_no_duplicate_drug_class_id_within_rule():
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    dupes = []
    for r in rules:
        seen = {}
        for i, dcr in enumerate(r.get("drug_class_rules") or []):
            dcid = dcr.get("drug_class_id")
            if dcid in seen:
                dupes.append((r["id"], dcid, seen[dcid], i))
            else:
                seen[dcid] = i
    assert not dupes, (
        f"Found duplicate drug_class_id within drug_class_rules of "
        f"{len(dupes)} rule(s). Each (rule, drug_class_id) pair must "
        f"appear at most once. Drift typically comes from a rename without "
        f"re-running the upsert backfill.\n"
        + "\n".join(f"  {rid} / {dcid} at indices [{a}, {b}]"
                    for rid, dcid, a, b in dupes[:10])
    )


def test_no_duplicate_condition_id_within_rule():
    """Same invariant for condition_rules — symmetric guard."""
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    dupes = []
    for r in rules:
        seen = {}
        for i, cr in enumerate(r.get("condition_rules") or []):
            cid = cr.get("condition_id")
            if cid in seen:
                dupes.append((r["id"], cid, seen[cid], i))
            else:
                seen[cid] = i
    assert not dupes, (
        f"Found duplicate condition_id within condition_rules of "
        f"{len(dupes)} rule(s).\n"
        + "\n".join(f"  {rid} / {cid} at indices [{a}, {b}]"
                    for rid, cid, a, b in dupes[:10])
    )


# ---------------------------------------------------------------------------
# 2026-04-30 audit: latent integrity gaps
# ---------------------------------------------------------------------------


def test_pregnancy_lactation_evidence_level_is_canonical():
    """Lock the gap closed by the audit: every pregnancy_lactation.evidence_level
    value must be a member of the taxonomy evidence_levels enum.
    Previously this field was free-text — gap-fill could write 'no_data' even
    though it wasn't in the taxonomy."""
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    taxonomy_path = DATA_PATH.parent / "clinical_risk_taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    valid = {e["id"] for e in taxonomy.get("evidence_levels", [])}
    bad = []
    for r in rules:
        pl = r.get("pregnancy_lactation") or {}
        ev = pl.get("evidence_level")
        if ev is not None and ev not in valid:
            bad.append((r["id"], ev))
    assert not bad, (
        f"pregnancy_lactation.evidence_level uses {len(bad)} non-canonical "
        f"values:\n"
        + "\n".join(f"  {rid}: {ev!r}" for rid, ev in bad[:10])
        + f"\nValid set: {sorted(valid)}"
    )


def test_no_legacy_lactation_fields():
    """Lock the gap closed by the audit: legacy lactation_severity /
    lactation_evidence / lactation_notes fields must not reappear.
    They drift out of sync with the canonical lactation_category and
    evidence_level fields and shouldn't be written by any backfill."""
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    legacy_fields = ("lactation_severity", "lactation_evidence", "lactation_notes")
    bad = []
    for r in rules:
        pl = r.get("pregnancy_lactation") or {}
        for f in legacy_fields:
            if f in pl:
                bad.append((r["id"], f))
    assert not bad, (
        f"Legacy pregnancy_lactation fields present in {len(bad)} location(s); "
        f"these drift out of sync with canonical lactation_category / "
        f"evidence_level and must be removed.\n"
        + "\n".join(f"  {rid}: {f}" for rid, f in bad[:10])
    )


def test_dose_thresholds_use_canonical_severity_ids():
    """Lock the gap closed by the audit: severity_if_met / severity_if_not_met
    in dose_thresholds were missed by the info→informational rename."""
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    bad = []
    for r in rules:
        for i, dt in enumerate(r.get("dose_thresholds") or []):
            for f in ("severity_if_met", "severity_if_not_met"):
                v = dt.get(f)
                if v == "info":  # the pre-rename token
                    bad.append((r["id"], i, f))
    assert not bad, (
        f"dose_thresholds still using legacy 'info' severity in "
        f"{len(bad)} place(s) — should be 'informational' per the rename.\n"
        + "\n".join(f"  {rid}/dose_thresholds[{i}].{f}" for rid, i, f in bad[:10])
    )


def test_no_dose_thresholds_notes_typo():
    """Lock the typo fix: dose_thresholds field is `note` (singular), not `notes`."""
    rules = json.loads(DATA_PATH.read_text())["interaction_rules"]
    bad = []
    for r in rules:
        for i, dt in enumerate(r.get("dose_thresholds") or []):
            if "notes" in dt:
                bad.append((r["id"], i))
    assert not bad, (
        f"dose_thresholds[].notes typo (canonical field is `note`) in "
        f"{len(bad)} place(s):\n"
        + "\n".join(f"  {rid}/dose_thresholds[{i}]" for rid, i in bad[:10])
    )
