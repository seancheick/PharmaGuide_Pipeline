"""Versioned anomaly rules evaluated over the dashboard index at refresh time.

A finding is a contradiction, an integrity defect, an incomplete state shown as
final, or an unexplained change. Audit states (Evidence 0, Dose neutral,
Verification neutral 6, Formula checks below 10) are NOT findings: they are
Product Explorer saved views. Every rule cites the policy that makes it a defect.

Bump a rule's ``version`` whenever its meaning changes: the finding id includes it,
so an accepted exception for the old meaning does not silence the new one.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow.dataset as pds

from scripts.dashboard.score_index import CANARY_FILE, PILLARS, QUALITY_CONFIG, REPO_ROOT, TABLES, pillar_maxima
from scripts.dashboard import run_compare
from scoring_v4.penalty_registry import PENALTY_ALIASES, PENALTY_REGISTRY
from scoring_v4.quality_score import (
    _ROUNDING_BOUND,
    EVIDENCE_APPLICABILITY_STATES,
    EVIDENCE_COVERAGE_GAP_STATES,
)

TOL = _ROUNDING_BOUND  # the scorer's own reconciliation bound
# realized = score − score-without-deductions; both sit on the 0.1 grid, so two residues can stack.
REALIZED_TOL = 2 * _ROUNDING_BOUND
SEVERITY_ORDER = ["critical", "high", "medium", "info"]
FINDING_COLUMNS = [
    "finding_id", "rule_id", "rule_version", "severity", "category", "pillar", "plane", "run_key",
    "dsld_id", "product_name", "brand_name", "subject", "message", "current_value", "expected",
    "receipt_entry_id", "policy",
]
CALIBRATION_STALE_DAYS = 365
PEER_MIN_N = 30
PEER_Z = 3.5
PSI_LIMIT = 0.2


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: int
    severity: str
    category: str
    message: str
    expected: str
    policy: str
    scope: str  # product | compare | calibration | run
    check: Callable[["Context"], pd.DataFrame]
    pillar: str | None = None


@dataclass
class Context:
    products: dict[str, pd.DataFrame]       # plane -> latest products
    ledgers: dict[str, pd.DataFrame]
    receipts: dict[str, pd.DataFrame]
    explanations: dict[str, pd.DataFrame]
    dose_flags: dict[str, pd.DataFrame]
    runs: dict[str, dict]                   # plane -> latest run meta
    deltas: dict[str, pd.DataFrame]         # "candidate_vs_previous", "release_vs_candidate"
    pillar_drift: list[dict]
    calibration: list[dict]
    pillar_max: dict[str, float]
    plane: str = "candidate"
    golden: list[dict] | None = None  # golden_set_results rows for the latest candidate

    def p(self) -> pd.DataFrame:
        return self.products.get(self.plane, pd.DataFrame())

    def frame(self, name: str) -> pd.DataFrame:
        return getattr(self, name).get(self.plane, pd.DataFrame())


def _rows(frame: pd.DataFrame, value: Any = None, **extra: Any) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    out = pd.DataFrame({"dsld_id": frame["dsld_id"].astype(str).values})
    if value is not None:
        out["current_value"] = frame[value].astype(str).values if isinstance(value, str) else value
    for key, val in extra.items():
        out[key] = frame[val].values if isinstance(val, str) and val in frame else val
    return out


def _scored(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["quality_score_status"] == "scored"] if not frame.empty else frame


# ---------------------------------------------------------------- product rules

def _receipt_reconcile(ctx):
    p = ctx.p()
    return _rows(p[p["receipt_mismatch_max"].fillna(0) > TOL], "receipt_mismatch_max")


def _pillar_sum(ctx):
    p = ctx.p()
    return _rows(p[p["pillar_sum_mismatch"].fillna(0) > TOL], "pillar_sum_mismatch")


def _out_of_range(ctx):
    led = ctx.frame("ledgers")
    if led.empty:
        return pd.DataFrame()
    maxima = led["pillar"].map(ctx.pillar_max)
    bad = led[(led["score"] < -TOL) | (led["score"] > maxima + TOL)]
    p = ctx.p()
    totals = p[(p["total"] < -TOL) | (p["total"] > 100 + TOL)]
    a = _rows(bad, "score", pillar="pillar")
    b = _rows(totals, "total")
    return pd.concat([a, b], ignore_index=True)


def _negative_unawarded(ctx):
    led = ctx.frame("ledgers")
    return _rows(led[led["unawarded"].fillna(0) < -TOL], "unawarded", pillar="pillar") if not led.empty else pd.DataFrame()


def _realized_exceeds_nominal(ctx):
    led = ctx.frame("ledgers")
    if led.empty:
        return pd.DataFrame()
    bad = led[led["realized_deductions"] < led["nominal_deductions"] - REALIZED_TOL]
    return _rows(bad, "realized_deductions", pillar="pillar")


def _missing_receipt(ctx):
    p = _scored(ctx.p())
    return _rows(p[p["pillars_missing_receipt"] > 0], "pillars_missing_receipt") if not p.empty else pd.DataFrame()


def _unscored_visible(ctx):
    p = ctx.p()
    if p.empty:
        return pd.DataFrame()
    bad = p[p["quality_score_status"].isin(["not_scored", "suppressed_safety"]) & (p["total"].notna() | p["tier"].notna())]
    return _rows(bad, "quality_score_status")


def _blocked_without_reason(ctx):
    p = ctx.p()
    if p.empty:
        return pd.DataFrame()
    blocked = (p["quality_score_status"] == "suppressed_safety") | (p["product_safety_status"] == "blocked")
    no_reason = p["blocking_reason"].isna() & p["suppressed_reason"].isna() & p["safety_signal_reason"].isna()
    return _rows(p[blocked & no_reason], "product_safety_status")


def _config_missing(ctx):
    p = _scored(ctx.p())
    return _rows(p[p["config_fingerprint"].isna()], "quality_score_status") if not p.empty else pd.DataFrame()


def _verification_zero(ctx):
    # Verification fails open to a neutral baseline, so 0 needs a recorded deduction or cap to explain it.
    p = _scored(ctx.p())
    rec = ctx.frame("receipts")
    if p.empty:
        return pd.DataFrame()
    zero = p[p["pillar_verification"].fillna(-1).abs() < TOL]
    if zero.empty:
        return pd.DataFrame()
    explained = set()
    if not rec.empty:
        explained = set(rec[(rec["pillar"] == "verification") & rec["kind"].isin(["deduction", "cap"])]["dsld_id"])
    return _rows(zero[~zero["dsld_id"].isin(explained)], "pillar_verification", pillar="verification")


def _penalty_wrong_pillar(ctx):
    rec = ctx.frame("receipts")
    if rec.empty:
        return pd.DataFrame()
    canonical = rec["entry_id"].map(lambda value: PENALTY_ALIASES.get(value, value))
    owner = canonical.map(lambda value: PENALTY_REGISTRY[value].primary_dimension if value in PENALTY_REGISTRY else None)
    bad = rec[owner.notna() & (owner != rec["pillar"])]
    return _rows(bad, "pillar", pillar="pillar", receipt_entry_id="entry_id")


def _double_dose_ceiling(ctx):
    rec = ctx.frame("receipts")
    flags = ctx.frame("dose_flags")
    ids = set()
    if not rec.empty:
        counts = rec[rec["entry_id"] == "dose_safety_ceiling"].groupby("dsld_id").size()
        ids |= set(counts[counts > 1].index)
    if not flags.empty:
        counts = flags[flags["is_ceiling"]].groupby("dsld_id").size()
        ids |= set(counts[counts > 1].index)
    return pd.DataFrame({"dsld_id": sorted(ids), "current_value": "multiple dose ceilings"}) if ids else pd.DataFrame()


def _evidence_state_display(ctx):
    p = ctx.p()
    if p.empty:
        return pd.DataFrame()
    gap = p["evidence_state"].isin(EVIDENCE_COVERAGE_GAP_STATES | EVIDENCE_APPLICABILITY_STATES)
    bad = p[gap & (p["evidence_display_state"] == "assessed")]
    return _rows(bad, "evidence_state", pillar="evidence")


def _strength_pillars(ctx, pillar: str) -> set[str]:
    ex = ctx.frame("explanations")
    if ex.empty:
        return set()
    return set(ex[(ex["role"] == "strength") & (ex["pillar"] == pillar)]["dsld_id"].astype(str))


def _evidence_strength_contradiction(ctx):
    p = ctx.p()
    ids = _strength_pillars(ctx, "evidence")
    if p.empty or not ids:
        return pd.DataFrame()
    bad = p[p["dsld_id"].isin(ids) & ((p["pillar_evidence"].fillna(0) == 0) | (p["evidence_display_state"].fillna("assessed") != "assessed"))]
    return _rows(bad, "evidence_display_state", pillar="evidence")


def _verification_neutral_claimed(ctx):
    p = ctx.p()
    if p.empty:
        return pd.DataFrame()
    ids = _strength_pillars(ctx, "verification")
    fail_open = p["verification_fail_open"].fillna(False).astype(bool)
    claims = p["dsld_id"].isin(ids) | p["has_third_party_testing"].fillna(False).astype(bool)
    return _rows(p[fail_open & claims], "verification_tier", pillar="verification")


def _dose_neutral_strength(ctx):
    p = ctx.p()
    ids = _strength_pillars(ctx, "dose")
    if p.empty or not ids:
        return pd.DataFrame()
    neutral = p["neutral_only_pillars"].map(lambda value: "dose" in list(value if value is not None else []))
    return _rows(p[neutral & p["dsld_id"].isin(ids)], "dose_basis", pillar="dose")


def _peer_outlier(ctx):
    p = ctx.p()
    if p.empty:
        return pd.DataFrame()
    pool = p[(p["quality_score_status"] == "scored") & (p["quality_assessment_status"] == "complete") & p["total"].notna()]
    out = []
    for category, group in pool.groupby("category"):
        if len(group) < PEER_MIN_N:
            continue
        median = group["total"].median()
        mad = (group["total"] - median).abs().median() * 1.4826
        if not mad:
            continue
        z = (group["total"] - median) / mad
        hit = group[z.abs() > PEER_Z]
        for (_, row), score in zip(hit.iterrows(), z[z.abs() > PEER_Z]):
            out.append({"dsld_id": str(row["dsld_id"]),
                        "current_value": f"{row['total']} vs median {median:.1f} of n={len(group)} {category} (z={score:.1f})"})
    return pd.DataFrame(out)


def _low_route_ranked(ctx):
    p = ctx.p()
    if p.empty:
        return pd.DataFrame()
    bad = p[(p["route_confidence"] == "low") & (p["quality_score_status"] == "scored") & (p["quality_assessment_status"] == "complete")]
    return _rows(bad, "module")


def golden_set_results(doc: dict, records: dict[str, dict], release_ids: set[str]) -> list[dict]:
    """The golden set's own evaluator over full scored records (owner: the golden-set packet)."""
    from audits.golden_set_v4_20261019.proposal import evaluate
    if not doc.get("canaries"):
        return []
    tiers = json.loads(QUALITY_CONFIG.read_text(encoding="utf-8"))["tiers"]
    return evaluate(doc, records, tiers, release_ids)


def _canary_expectations(ctx):
    if ctx.plane != "candidate" or not ctx.golden:
        return pd.DataFrame()
    out = [{"dsld_id": row["dsld_id"], "subject": name, "current_value": str(got)[:200]}
           for row in ctx.golden for name, ok, got in row["checks"] if not ok]
    return pd.DataFrame(out)


# ---------------------------------------------------------------- compare rules

def _compare_rows(ctx, key: str, mask: Callable[[pd.DataFrame], pd.Series], value: Callable[[dict], str]):
    deltas = ctx.deltas.get(key)
    if deltas is None or deltas.empty:
        return pd.DataFrame()
    hit = deltas[(deltas["presence"] == "both") & mask(deltas).fillna(False).astype(bool)]
    records = hit.to_dict("records")
    return pd.DataFrame({"dsld_id": [str(r["dsld_id"]) for r in records],
                         "current_value": [value(r) for r in records], "subject": key})


def _unexplained_mover(key):
    no_run_change = lambda d: d["run_causes"].map(len) == 0  # noqa: E731
    return lambda ctx: _compare_rows(ctx, key, lambda d: ~d["explained"].astype(bool) & no_run_change(d),
                                     lambda r: f"{r['total_before']} → {r['total_after']}")


def _unattributed_under_run_change(key):
    return lambda ctx: _compare_rows(
        ctx, key, lambda d: ~d["explained"].astype(bool) & (d["run_causes"].map(len) > 0),
        lambda r: f"{r['total_before']} → {r['total_after']} (run change: {', '.join(r['run_causes'])})")


def _safety_unexplained(key):
    return lambda ctx: _compare_rows(
        ctx, key, lambda d: d["safety_changed"].astype(bool) & (d["safety_causes"].map(len) == 0),
        lambda r: f"{r['product_safety_status_before']} → {r['product_safety_status_after']}")


def _safety_explained(key):
    return lambda ctx: _compare_rows(
        ctx, key, lambda d: d["safety_changed"].astype(bool) & (d["safety_causes"].map(len) > 0),
        lambda r: f"{r['product_safety_status_before']} → {r['product_safety_status_after']} "
                  f"({', '.join(r['safety_causes'])})")


def _large_or_tier_move(key):
    return lambda ctx: _compare_rows(
        ctx, key, lambda d: d["explained"].astype(bool) & (d["tier_crossed"].astype(bool) | (d["delta"].abs() >= 5)),
        lambda r: f"{r['tier_before']} → {r['tier_after']} (Δ {r['delta']})")


# ---------------------------------------------------------------- calibration / run rules

def _calibration_incomplete(ctx):
    out = []
    today = date.today()
    for record in ctx.calibration:
        problems = []
        if not str(record.get("approval_status") or "").startswith("approved"):
            problems.append(f"approval_status={record.get('approval_status')!r}")
        for field in ("source_ids", "owner", "rationale", "review_date"):
            if not record.get(field):
                problems.append(f"missing {field}")
        try:
            age = (today - date.fromisoformat(str(record.get("review_date"))[:10])).days
            if age > CALIBRATION_STALE_DAYS:
                problems.append(f"review {age} days old")
        except ValueError:
            pass
        if problems:
            out.append({"subject": record["path"], "current_value": "; ".join(problems)})
    return pd.DataFrame(out)


def owner_symbol_exists(owner: str) -> bool:
    if "::" not in owner:
        return False
    path, symbol = owner.split("::", 1)
    target = REPO_ROOT / path
    if not target.is_file():
        return False
    head = symbol.split(".")[0]
    text = target.read_text(encoding="utf-8")
    return re.search(rf"^\s*(def|class)\s+{re.escape(head)}\b|^\s*{re.escape(head)}\s*[:=]", text, re.M) is not None


def _calibration_owner(ctx):
    out = [{"subject": record["path"], "current_value": str(record.get("owner"))}
           for record in ctx.calibration if record.get("owner") and not owner_symbol_exists(str(record["owner"]))]
    return pd.DataFrame(out)


def _pillar_drift(ctx):
    return pd.DataFrame([{"subject": f"{d['pillar']} ({d['base']} → {d['cand']})", "current_value": f"PSI {d['psi']:.3f}",
                          "pillar": d["pillar"]} for d in ctx.pillar_drift if d["psi"] > PSI_LIMIT])


RULES: list[Rule] = [
    Rule("receipt_reconcile", 1, "critical", "accounting", "Receipt entries do not sum to the pillar score",
         "sum(entries) = pillar ± 0.05", "quality_score.py::_finish_receipt", "product", _receipt_reconcile),
    Rule("pillar_sum", 1, "critical", "accounting", "Six pillars do not sum to the total",
         "sum(pillars) = quality_score_v4_100", "quality_score.py::assemble_quality_score (total is the pillar sum)",
         "product", _pillar_sum),
    Rule("score_out_of_range", 1, "critical", "accounting", "Score or pillar outside its allowed range",
         "0 ≤ pillar ≤ max; 0 ≤ total ≤ 100", "quality_score.json pillars", "product", _out_of_range),
    Rule("negative_unawarded", 1, "critical", "accounting", "Pillar has negative unawarded capacity",
         "unawarded ≥ 0", "quality_score.py::_finish_receipt", "product", _negative_unawarded),
    Rule("realized_exceeds_nominal", 1, "critical", "accounting", "Realized deduction larger than the nominal charge",
         "|realized| ≤ |nominal|", "quality_score.py::_finish_receipt", "product", _realized_exceeds_nominal),
    Rule("scored_pillar_without_receipt", 1, "critical", "accounting", "Scored pillar has no receipt",
         "every scored pillar carries a receipt", "quality_score.py receipts", "product", _missing_receipt),
    Rule("unscored_has_score", 1, "critical", "status", "Not-scored or suppressed product carries a score or tier",
         "no public score when quality_score_status ≠ scored", "quality_score.json suppression", "product", _unscored_visible),
    Rule("blocked_without_reason", 1, "critical", "safety", "Blocked or suppressed product has no recorded reason",
         "banned/recalled products ship with their reason", "AGENTS.md data rules (BLOCKED keeps reason)",
         "product", _blocked_without_reason),
    Rule("config_fingerprint_missing", 1, "critical", "provenance", "Scored product has no config fingerprint",
         "every score names its config", "config_registry.all_config_provenance", "product", _config_missing),
    Rule("unexplained_mover", 2, "critical", "drift", "Score moved with no pillar or run-level cause",
         "every movement has a reason code or run cause", "replay.reason_codes", "compare",
         _unexplained_mover("candidate_vs_previous")),
    Rule("unattributed_mover_under_run_change", 1, "high", "drift",
         "Pillar moved with no pillar-level cause while code, config or reference data changed",
         "a component, penalty, reference or formula cause", "replay.reason_codes", "compare",
         _unattributed_under_run_change("candidate_vs_previous")),
    Rule("safety_change_unexplained", 1, "critical", "safety", "Safety status changed with no recorded cause",
         "a safety change follows a signal, reason or reference-data change", "scoring.md (never hide a safety finding)",
         "compare", _safety_unexplained("candidate_vs_previous")),
    Rule("safety_change_unexplained_vs_release", 1, "critical", "safety",
         "Safety status differs from release with no recorded cause", "a safety change follows a recorded cause",
         "scoring.md", "compare", _safety_unexplained("release_vs_candidate")),
    Rule("safety_change_review", 1, "high", "safety", "Safety status changed (cause recorded) — mandatory review",
         "reviewed and accepted", "scoring.md", "compare", _safety_explained("candidate_vs_previous")),
    Rule("safety_change_review_vs_release", 1, "high", "safety", "Safety status differs from release (cause recorded)",
         "reviewed before publication", "scoring.md", "compare", _safety_explained("release_vs_candidate")),
    Rule("verification_zero_unexplained", 1, "high", "accounting",
         "Verification is 0 with no recorded deduction or cap", "fail-open neutral baseline unless a penalty applies",
         "scoring.md (Verification fails open to verification_subscale.neutral_baseline)", "product",
         _verification_zero, pillar="verification"),
    Rule("penalty_wrong_pillar", 1, "high", "ownership", "Penalty charged outside its registered pillar",
         "penalty pillar = PENALTY_REGISTRY.primary_dimension", "penalty_registry.py::PENALTY_REGISTRY",
         "product", _penalty_wrong_pillar),
    Rule("dose_ceiling_repeated", 1, "high", "ownership", "More than one Dose safety ceiling on one product",
         "one product-level Dose ceiling", "quality_score.json dose_safety_ceiling (one product-level ceiling)",
         "product", _double_dose_ceiling, pillar="dose"),
    Rule("evidence_gap_shown_assessed", 1, "high", "semantics", "Evidence coverage gap displayed as assessed",
         "coverage-gap/applicability states never display as assessed",
         "quality_score.py EVIDENCE_COVERAGE_GAP_STATES / EVIDENCE_APPLICABILITY_STATES", "product",
         _evidence_state_display, pillar="evidence"),
    Rule("evidence_strength_contradiction", 1, "high", "semantics",
         "Evidence listed as a strength while 0 or not assessed", "strengths only from assessed, earned Evidence",
         "build_final_db.py::_build_v4_score_explanation", "product", _evidence_strength_contradiction, pillar="evidence"),
    Rule("verification_neutral_claimed", 1, "high", "semantics",
         "Verification is the neutral unknown but a strength/flag claims verification",
         "fail-open neutral never reads as verified", "scoring.md (Verification fails open)", "product",
         _verification_neutral_claimed, pillar="verification"),
    Rule("dose_neutral_strength", 1, "high", "semantics", "Dose is a neutral disposition but listed as a strength",
         "neutral Dose is not described as adequate", "quality_score.json dose neutral policy", "product",
         _dose_neutral_strength, pillar="dose"),
    Rule("calibration_incomplete", 1, "high", "calibration", "Calibration record provisional, incomplete or stale",
         "approved, sourced, owned, reasoned, reviewed ≤ 365 days", "schemas/dose_reference_semantics.schema.json",
         "calibration", _calibration_incomplete),
    Rule("calibration_owner_missing", 1, "high", "calibration", "Calibration owner symbol not found in code",
         "owner path::symbol exists", "quality_score.json reference_semantics.owner", "calibration", _calibration_owner),
    Rule("tier_or_large_move", 1, "medium", "drift", "Tier crossing or ≥5-point movement (cause recorded)",
         "reviewed by shared cause", "AGENTS.md development workflow", "compare", _large_or_tier_move("candidate_vs_previous")),
    Rule("pillar_drift", 1, "medium", "drift", "Pillar distribution shifted between runs", f"PSI ≤ {PSI_LIMIT}",
         "Evidently-style PSI over 10 bins", "run", _pillar_drift),
    Rule("peer_outlier", 1, "medium", "distribution", "Score extreme versus its category peers",
         f"|robust z| ≤ {PEER_Z} (complete products, n ≥ {PEER_MIN_N})", "peer percentile is context, not a score",
         "product", _peer_outlier),
    Rule("low_route_confidence_ranked", 1, "medium", "routing", "Complete scored product with low route confidence",
         "route confidence ≥ moderate for ranked products", "route_decision.confidence", "product", _low_route_ranked),
    Rule("canary_expectation_broken", 1, "medium", "golden_set", "Golden-set canary breaks an approved expectation",
         "fix at the owner or record an allowed movement reason; never edit the expectation to the score",
         "scripts/data/canary_products.json _metadata.golden_set", "product", _canary_expectations),
]


# ---------------------------------------------------------------- evaluation

def finding_id(rule: Rule, plane: str, dsld_id: Any, pillar: Any, subject: Any) -> str:
    key = json.dumps([rule.rule_id, rule.version, plane, dsld_id, pillar, subject], default=str)
    return hashlib.sha256(key.encode()).hexdigest()[:20]


def calibration_records() -> list[dict[str, Any]]:
    config = json.loads(QUALITY_CONFIG.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []

    def walk(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            if "rationale" in node or "approval_status" in node:
                out.append({"path": ".".join(path), **{k: v for k, v in node.items() if not k.startswith("_")}})
            for key, value in node.items():
                walk(value, [*path, key])

    walk(config, [])
    return out


def golden_doc() -> dict[str, Any]:
    try:
        return json.loads(CANARY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}



def psi(before: pd.Series, after: pd.Series, bins: int = 10, cap: float = 20.0) -> float:
    before, after = before.dropna(), after.dropna()
    if before.empty or after.empty:
        return 0.0
    edges = [cap * i / bins for i in range(bins + 1)]
    edges[-1] = float("inf")
    b = pd.cut(before, [-float("inf"), *edges[1:]]).value_counts(normalize=True, sort=False) + 1e-4
    a = pd.cut(after, [-float("inf"), *edges[1:]]).value_counts(normalize=True, sort=False) + 1e-4
    import math
    return float(sum((x - y) * math.log(x / y) for x, y in zip(a, b)))


def evaluate(ctx: Context, *, run_keys: dict[str, str | None]) -> pd.DataFrame:
    products = {plane: frame.drop_duplicates("dsld_id").set_index("dsld_id") if not frame.empty else frame
                for plane, frame in ctx.products.items()}
    rows = []
    for rule in RULES:
        planes = ["candidate", "release"] if rule.scope == "product" else ["candidate"]
        for plane in planes:
            if rule.scope == "product" and ctx.products.get(plane, pd.DataFrame()).empty:
                continue
            ctx.plane = plane
            hits = rule.check(ctx)
            if hits is None or hits.empty:
                continue
            for hit in hits.to_dict("records"):
                pid = hit.get("dsld_id")
                pillar = hit.get("pillar") or rule.pillar
                subject = hit.get("subject")
                lookup = products.get(plane)
                name = brand = None
                if pid is not None and lookup is not None and not lookup.empty and pid in lookup.index:
                    name, brand = lookup.loc[pid, "product_name"], lookup.loc[pid, "brand_name"]
                rows.append({
                    "finding_id": finding_id(rule, plane, pid, pillar, (subject, hit.get("receipt_entry_id"))),
                    "rule_id": rule.rule_id, "rule_version": rule.version, "severity": rule.severity,
                    "category": rule.category, "pillar": pillar, "plane": plane, "run_key": run_keys.get(plane),
                    "dsld_id": pid, "product_name": name, "brand_name": brand, "subject": subject,
                    "message": rule.message, "current_value": hit.get("current_value"),
                    "expected": hit.get("expected") or rule.expected,
                    "receipt_entry_id": hit.get("receipt_entry_id"), "policy": rule.policy,
                })
    frame = pd.DataFrame(rows, columns=FINDING_COLUMNS)
    return frame.astype({"rule_version": "int64"}) if not frame.empty else frame


def evaluate_build(build: Path, meta: dict[str, Any], previous: Path | None) -> dict[str, int]:
    """Called by score_index.refresh on the staged build; writes findings + deltas."""

    def read(run_key: str, table: str, columns: list[str] | None = None) -> pd.DataFrame:
        directory = build / "runs" / run_key / table
        if not directory.exists():
            return pd.DataFrame(columns=columns or TABLES[table].names)
        return pds.dataset(str(directory), format="parquet", schema=TABLES[table]).to_table(columns=columns).to_pandas()

    runs = {run["run_key"]: run for run in meta["runs"]}
    latest = {plane: runs.get(key) for plane, key in (meta.get("latest") or {}).items() if key}
    candidates = sorted((r for r in meta["runs"] if r["plane"] == "candidate"), key=lambda r: r.get("run_time") or "")
    prev_candidate = next((r for r in reversed(candidates) if latest.get("candidate") and r["run_key"] != latest["candidate"]["run_key"]), None)

    frames: dict[str, dict[str, pd.DataFrame]] = {name: {} for name in ("products", "ledgers", "receipts", "explanations", "dose_flags")}
    for plane, run in latest.items():
        for name in frames:
            frames[name][plane] = read(run["run_key"], name)

    deltas: dict[str, pd.DataFrame] = {}
    pairs = {"candidate_vs_previous": (prev_candidate, latest.get("candidate")),
             "release_vs_candidate": (latest.get("release"), latest.get("candidate"))}
    delta_dir = build / "deltas"
    delta_dir.mkdir(exist_ok=True)
    drift = []
    for key, (base, cand) in pairs.items():
        if not base or not cand:
            continue
        frame = run_compare.compare(read, base, cand)
        deltas[key] = frame
        frame.to_parquet(delta_dir / f"{base['run_key']}__{cand['run_key']}__v{run_compare.DELTA_VERSION}.parquet", index=False)
        left = read(base["run_key"], "products")
        right = read(cand["run_key"], "products")
        maxima = pillar_maxima()
        for name in PILLARS:
            drift.append({"pillar": name, "base": base["plane"], "cand": cand["plane"],
                          "psi": psi(left[f"pillar_{name}"], right[f"pillar_{name}"], cap=maxima[name])})

    golden = None
    if latest.get("candidate"):
        records = read(latest["candidate"]["run_key"], "canary_records")
        release_ids = set(frames["products"].get("release", pd.DataFrame(columns=["dsld_id"]))["dsld_id"].astype(str))
        golden = golden_set_results(golden_doc(), {pid: json.loads(text) for pid, text in
                                                   zip(records["dsld_id"], records["record_json"])}, release_ids)
    ctx = Context(products=frames["products"], ledgers=frames["ledgers"], receipts=frames["receipts"],
                  explanations=frames["explanations"], dose_flags=frames["dose_flags"], runs=latest,
                  deltas=deltas, pillar_drift=drift, calibration=calibration_records(),
                  pillar_max=pillar_maxima(), golden=golden)
    findings = evaluate(ctx, run_keys={plane: run["run_key"] for plane, run in latest.items()})
    findings.to_parquet(build / "findings.parquet", index=False)

    # first/last seen follows run chronology, carried forward across builds
    seen_path = build / "finding_seen.parquet"
    history = pd.read_parquet(previous / "finding_seen.parquet") if previous and (previous / "finding_seen.parquet").exists() \
        else pd.DataFrame(columns=["finding_id", "run_key", "run_time"])
    current = pd.DataFrame({
        "finding_id": findings["finding_id"],
        "run_key": findings["run_key"],
        "run_time": findings["run_key"].map(lambda key: (runs.get(key) or {}).get("run_time")),
    }) if not findings.empty else pd.DataFrame(columns=["finding_id", "run_key", "run_time"])
    pd.concat([history, current], ignore_index=True).drop_duplicates(["finding_id", "run_key"]).to_parquet(seen_path, index=False)
    counts = findings["severity"].value_counts().to_dict() if not findings.empty else {}
    return {severity: int(counts.get(severity, 0)) for severity in SEVERITY_ORDER}


def with_seen(findings: pd.DataFrame, build: Path, runs: list[dict[str, Any]]) -> pd.DataFrame:
    """Attach first/last seen run times (chronological) to the current findings."""
    path = build / "finding_seen.parquet"
    if findings.empty or not path.exists():
        return findings
    seen = pd.read_parquet(path).groupby("finding_id")["run_time"].agg(first_seen="min", last_seen="max").reset_index()
    return findings.merge(seen, on="finding_id", how="left")
