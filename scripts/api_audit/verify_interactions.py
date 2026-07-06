#!/usr/bin/env python3
"""Verify and normalize curated interaction drafts before the DB build.

Gate script for ``build_interaction_db.py``. Implements the 10 checks
defined in INTERACTION_DB_SPEC v2.2.0 §6.2, produces a structured report,
and writes a normalized output file that the builder consumes.

Design
------
All 10 checks are implemented as pure functions that take their inputs
explicitly. Network-dependent work (RxNorm, UMLS, PubMed) is done through
small injectable clients so the offline unit test suite can monkeypatch
everything and run fully hermetically.

CLI surface
-----------
    # Offline audit of draft shards (no network, skip checks 3/4):
    python3 scripts/api_audit/verify_interactions.py \\
        --drafts scripts/data/curated_interactions \\
        --report /tmp/interaction_audit_report.json \\
        --offline

    # Full verification with RxNorm + UMLS live:
    python3 scripts/api_audit/verify_interactions.py \\
        --drafts scripts/data/curated_interactions \\
        --report scripts/interaction_db_output/interaction_audit_report.json \\
        --normalized-out scripts/interaction_db_output/interactions_verified.json \\
        --corrections-out scripts/interaction_db_output/corrections.json

Exit codes
----------
    0   errors == 0
    1   errors > 0 (build must not proceed)
    2   bad CLI arguments / missing input files
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = timezone.utc
from pathlib import Path
from typing import Any, Callable, Protocol

# --------------------------------------------------------------------------- #
# Constants & schema
# --------------------------------------------------------------------------- #

# Draft-vocab → Flutter enum (Check 8, spec §6.2)
SEVERITY_MAP: dict[str, str] = {
    "contraindicated": "contraindicated",
    "major": "avoid",
    "moderate": "caution",
    "minor": "monitor",
}

FLUTTER_SEVERITIES: tuple[str, ...] = ("contraindicated", "avoid", "caution", "monitor")

# Wave 9.B.3 (2026-05-27) — display_layer enum + lane policy.
# An entry's display_layer determines whether the app surfaces it as an
# interruptive user-facing alert ("alert") or as a non-interruptive
# background insight ("background"). Deprecation continues to use the
# existing `retired_at` + `retired_reason` columns — display_layer has
# no "deprecated" value (see reports/wave_9b_minor_review/9B2_SCHEMA_DESIGN_DISPLAY_LAYER.md).
DISPLAY_LAYER_VALUES: frozenset[str] = frozenset({"alert", "background"})

# Severity-lane invariant (draft-vocab severities, pre-normalization).
# Major / Moderate / Contraindicated entries must live in the alert lane;
# Minor / Monitor entries must live in the background lane.
ALERT_LANE_DRAFT_SEVERITIES: frozenset[str] = frozenset(
    {"contraindicated", "major", "moderate"}
)
BACKGROUND_LANE_DRAFT_SEVERITIES: frozenset[str] = frozenset(
    {"minor", "monitor"}
)

ALLOWED_TYPES: frozenset[str] = frozenset(
    {
        "Med-Sup", "Sup-Med", "Sup-Sup", "Med-Med",
        "Med-Food", "Sup-Food", "Food-Med",
        "Med-Lifestyle", "Med-Procedure",
    }
)

ALLOWED_EFFECT_TYPES: frozenset[str] = frozenset(
    {"Inhibitor", "Enhancer", "Additive", "Neutral"}
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "type",
    "agent1_name",
    "agent1_id",
    "agent2_name",
    "agent2_id",
    "severity",
    "mechanism",
    "management",
)

# --------------------------------------------------------------------------- #
# Evidence-strength derivation (SP-6)  ⚠ CLINICIAN REVIEW REQUIRED before rebuild
# --------------------------------------------------------------------------- #
#
# Curated PAIRWISE interactions (curated_interactions/*.json) carry author
# metadata `clinical_confidence` (high/medium/moderate/low) + `evidence_basis`
# (study / source type), NOT a graded `evidence_level`. That is why the shipped
# interaction_db has 150/150 evidence_level = NULL. This derives the
# evidence_level into the LOCKED evidence_strength_vocab
# (scripts/data/evidence_strength_vocab.json), gated on audited provenance per
# the SP-0 rule: "map evidence grade to clinical-study data and audited
# identifiers; do NOT infer from marketing copy."
#
# The tables below are a defensible, conservative DEFAULT grounded in the vocab
# tier definitions. Adjust the TABLES (not the logic) after clinician review.
# Preview every proposed grade first:
#     python3 scripts/api_audit/review_evidence_derivation.py
#
# Canonical vocab, weakest -> strongest. `no_data` is the fail-safe: the
# ship-blocking NULL becomes an explicit, honest "no evidence data" tier, never
# a silent absence. Kept in sync with evidence_strength_vocab.json by the
# module-load self-check below.
EVIDENCE_STRENGTH_ORDER: tuple[str, ...] = (
    "no_data",
    "theoretical",
    "limited",
    "moderate",
    "probable",
    "established",
)

# evidence_basis (study / source type) -> BASE strength tier, before the
# confidence + provenance modifiers. Mirrors the study-design hierarchy in
# audit_clinical_evidence_strength.STUDY_TYPE_STRENGTH.
EVIDENCE_BASIS_BASE_STRENGTH: dict[str, str] = {
    # Strongest designs + regulatory authority = "consistent clinical or
    # regulatory backing" (established).
    "systematic_review": "established",
    "rct": "established",
    "label_regulatory": "established",  # FDA / label warnings = regulatory backing
    # Credible human / authoritative but not definitive = probable.
    "authoritative_review": "probable",
    "clinical_reference": "probable",
    "clinical_literature": "probable",
    "review": "probable",
    # Narrower / early human evidence.
    "observational": "moderate",
    # Mechanism-only, no direct confirmation = theoretical.
    "mechanism_inferred": "theoretical",
    "preclinical": "theoretical",
}

# Bases that are self-authoritative for provenance (regulatory / expert-curated
# references) and so may hold established/probable WITHOUT a PMID. Everything
# else must carry an audited identifier to grade above `moderate`.
SELF_AUTHORITATIVE_BASES: frozenset[str] = frozenset(
    {"label_regulatory", "authoritative_review", "clinical_reference"}
)


def derive_evidence_level(
    evidence_basis: str | None,
    clinical_confidence: str | None,
    source_pmids: list[str] | None,
) -> str:
    """Derive an evidence_strength_vocab tier from curated-interaction author
    metadata. SP-6 compliant: canonical vocab, provenance-gated, never NULL.

    Rubric (clinician-reviewable — adjust the tables above, not this logic):
      1. evidence_basis -> base tier (EVIDENCE_BASIS_BASE_STRENGTH).
      2. clinical_confidence: `low` steps down one tier (floor: theoretical);
         high / medium / moderate keep the base tier.
      3. provenance gate (SP-0): `established`/`probable` require an audited
         PMID OR a self-authoritative basis; otherwise cap at `moderate`.
    Unknown / absent basis -> `no_data`.
    """
    basis = (evidence_basis or "").strip().lower()
    conf = (clinical_confidence or "").strip().lower()
    base = EVIDENCE_BASIS_BASE_STRENGTH.get(basis)
    if base is None:
        return "no_data"

    idx = EVIDENCE_STRENGTH_ORDER.index(base)
    if conf == "low":
        idx = max(idx - 1, EVIDENCE_STRENGTH_ORDER.index("theoretical"))

    if EVIDENCE_STRENGTH_ORDER[idx] in ("established", "probable"):
        has_provenance = bool(source_pmids) or basis in SELF_AUTHORITATIVE_BASES
        if not has_provenance:
            idx = EVIDENCE_STRENGTH_ORDER.index("moderate")
    return EVIDENCE_STRENGTH_ORDER[idx]


def _assert_evidence_vocab_alignment() -> None:
    """SP-6 canonical-ID enforcement: EVIDENCE_STRENGTH_ORDER must match the
    LOCKED evidence_strength_vocab exactly, so the derivation can never emit an
    off-vocab tier. Best-effort — skipped if the vocab file is unavailable."""
    vocab_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "evidence_strength_vocab.json"
    )
    try:
        vocab = json.loads(vocab_path.read_text())
    except OSError:
        return
    ids = {e["id"] for e in vocab.get("evidence_strengths", []) if e.get("id")}
    off = set(EVIDENCE_STRENGTH_ORDER) - ids
    missing = ids - set(EVIDENCE_STRENGTH_ORDER)
    if off or missing:
        raise ValueError(
            "evidence_strength derivation drifted from evidence_strength_vocab: "
            f"not-in-vocab={sorted(off)} not-mapped={sorted(missing)}"
        )


_assert_evidence_vocab_alignment()

# Agent ID shapes
RXCUI_RE = re.compile(r"^\d+$")
REF_RE = re.compile(r"^ref:[a-z][a-z0-9_]*$")
CUI_RE = re.compile(r"^C\d{7}$")
CLASS_RE = re.compile(r"^class:[a-z][a-z0-9_]*$")

# PMID extraction from PubMed URLs (NBK* book URLs are NIH Bookshelf,
# not PMIDs and must not be extracted).
PUBMED_URL_RE = re.compile(
    r"(?:pubmed\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pubmed)/(?P<pmid>\d+)",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass
class EntryIssue:
    """One structured issue against a single entry."""

    entry_id: str
    check: str  # human short-code e.g. "schema", "duplicate", "rxcui", "cui", "source_gate"
    severity: str  # "error" | "warning" | "info"
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = {
            "entry_id": self.entry_id,
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
        }
        if self.details:
            out["details"] = self.details
        return out


@dataclass
class VerificationReport:
    total_entries: int = 0
    valid: int = 0
    warnings: int = 0
    errors: int = 0
    blocked_by: list[dict[str, Any]] = field(default_factory=list)
    cui_corrections: list[dict[str, Any]] = field(default_factory=list)
    rxcui_mismatches: list[dict[str, Any]] = field(default_factory=list)
    unmapped_supplements: list[dict[str, Any]] = field(default_factory=list)
    unknown_classes: list[dict[str, Any]] = field(default_factory=list)
    food_agents: list[dict[str, Any]] = field(default_factory=list)  # foods don't need IQM mapping
    ghost_pmids: list[dict[str, Any]] = field(default_factory=list)        # Check 11 — PMID dead/404
    retracted_pmids: list[dict[str, Any]] = field(default_factory=list)    # Check 11 — PMID flagged retracted
    topic_mismatch_pmids: list[dict[str, Any]] = field(default_factory=list)  # Check 11 — abstract topic ≠ rule
    issues: list[EntryIssue] = field(default_factory=list)

    def add_issue(self, issue: EntryIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.errors += 1
        elif issue.severity == "warning":
            self.warnings += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "valid": self.valid,
            "warnings": self.warnings,
            "errors": self.errors,
            "blocked_by": self.blocked_by,
            "cui_corrections": self.cui_corrections,
            "rxcui_mismatches": self.rxcui_mismatches,
            "unmapped_supplements": self.unmapped_supplements,
            "food_agents": self.food_agents,
            "ghost_pmids": self.ghost_pmids,
            "retracted_pmids": self.retracted_pmids,
            "topic_mismatch_pmids": self.topic_mismatch_pmids,
            "unknown_classes": self.unknown_classes,
            "issues": [i.to_dict() for i in self.issues],
        }


# --------------------------------------------------------------------------- #
# Network client protocols (dependency injection for tests)
# --------------------------------------------------------------------------- #


class RxNormClientProtocol(Protocol):
    def properties(self, rxcui: str) -> dict[str, Any] | None:
        """Return {'name': ..., 'tty': ..., 'rxcui': ...} or None."""


class UMLSSearchClientProtocol(Protocol):
    def search_exact(self, term: str) -> dict | None:
        """Return {'cui': 'C...', 'name': ...} or None."""

    def lookup_cui(self, cui: str) -> dict | None:
        """Return concept dict or None."""


class PubMedValidatorProtocol(Protocol):
    def exists(self, pmid: str) -> bool:
        ...

    def fetch(self, pmid: str) -> dict | None:
        """Return parsed article dict (title, abstract, retracted, etc.)
        or None if PMID is unknown / dead."""


# --------------------------------------------------------------------------- #
# Default RxNorm client (real network)
# --------------------------------------------------------------------------- #

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
DEFAULT_RATE_LIMIT = 0.12
DEFAULT_TIMEOUT = 10.0


def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request("https://rxnav.nlm.nih.gov", method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return ctx
    except (ssl.SSLCertVerificationError, urllib.error.URLError):
        return ssl._create_unverified_context()


class RxNormClient:
    """Minimal stdlib RxNorm client. Queries /rxcui/{rxcui}/properties.json."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        ssl_ctx: ssl.SSLContext | None = None,
    ) -> None:
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.ssl_ctx = ssl_ctx or _make_ssl_ctx()
        self._cache: dict[str, dict[str, Any] | None] = {}

    def properties(self, rxcui: str) -> dict[str, Any] | None:
        rxcui = rxcui.strip()
        if not rxcui or not RXCUI_RE.match(rxcui):
            return None
        if rxcui in self._cache:
            return self._cache[rxcui]

        url = f"{RXNAV_BASE}/rxcui/{urllib.parse.quote(rxcui)}/properties.json"
        time.sleep(self.rate_limit)
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_ctx) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"  RxNorm error for {rxcui}: HTTP {e.code}", file=sys.stderr)
            self._cache[rxcui] = None
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  RxNorm error for {rxcui}: {e}", file=sys.stderr)
            self._cache[rxcui] = None
            return None

        props = payload.get("properties") or {}
        if not props:
            self._cache[rxcui] = None
            return None

        result = {
            "rxcui": str(props.get("rxcui", "")),
            "name": str(props.get("name", "")),
            "tty": str(props.get("tty", "")),
            "synonym": str(props.get("synonym", "")),
        }
        self._cache[rxcui] = result
        return result


# --------------------------------------------------------------------------- #
# Default PubMed validator — wraps api_audit.pubmed_client (real network)
# --------------------------------------------------------------------------- #


class PubMedValidator:
    """Adapter on top of api_audit.pubmed_client.PubMedClient that satisfies
    PubMedValidatorProtocol. Caches per-PMID lookups across the full audit
    run via the underlying client's disk cache.

    `fetch(pmid)` returns the parsed article dict (title, abstract, retracted,
    publication_types, mesh_terms, …) or None when the PMID is unknown.
    """

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from pubmed_client import PubMedClient  # type: ignore
            client = PubMedClient()
        self._client = client
        self._fetch_cache: dict[str, dict | None] = {}

    def exists(self, pmid: str) -> bool:
        return self.fetch(pmid) is not None

    def fetch(self, pmid: str) -> dict | None:
        pmid = (pmid or "").strip()
        if not pmid or not pmid.isdigit():
            return None
        if pmid in self._fetch_cache:
            return self._fetch_cache[pmid]
        try:
            xml = self._client.efetch([pmid])
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from pubmed_client import parse_pubmed_article_xml  # type: ignore
            articles = parse_pubmed_article_xml(xml) if xml else []
        except Exception:
            articles = []
        record = articles[0] if articles else None
        # Confirm the returned article actually matches the requested PMID
        # (PubMed sometimes returns related but different IDs).
        if record and str(record.get("pmid", "")).strip() != pmid:
            record = None
        self._fetch_cache[pmid] = record
        return record


# --------------------------------------------------------------------------- #
# Pure functions — the 10 checks (testable without network)
# --------------------------------------------------------------------------- #


def classify_agent(agent_id: str) -> str:
    """Classify an agent_id string by its shape.

    Returns one of: 'drug' (rxcui), 'supplement' (cui), 'class' (class:...),
    'reference' (ref:...), 'unknown'.

    The 'ref:' prefix is used for non-drug, non-supplement entities that
    don't have a standard ontology identifier — e.g. lifestyle factors
    (ref:alcohol), procedures (ref:iodinated_contrast), food items
    (ref:grapefruit). These are pass-through: no API verification is
    attempted, but the ID is accepted as valid.
    """
    if not isinstance(agent_id, str):
        return "unknown"
    aid = agent_id.strip()
    if CLASS_RE.match(aid):
        return "class"
    if REF_RE.match(aid):
        return "reference"
    if CUI_RE.match(aid):
        return "supplement"
    if RXCUI_RE.match(aid):
        return "drug"
    return "unknown"


def validate_schema(entry: dict[str, Any]) -> list[str]:
    """Check 1. Returns list of error messages; empty list == valid schema."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return ["entry is not an object"]

    # Required fields
    for key in REQUIRED_FIELDS:
        val = entry.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"missing required field: {key}")

    # Type field enum
    type_val = entry.get("type")
    if type_val is not None and type_val not in ALLOWED_TYPES:
        errors.append(f"invalid type: {type_val!r} (allowed: {sorted(ALLOWED_TYPES)})")

    # Severity enum (draft vocab, pre-normalization)
    sev = entry.get("severity")
    if sev is not None and sev.lower() not in SEVERITY_MAP:
        errors.append(f"invalid severity: {sev!r} (allowed: {sorted(SEVERITY_MAP)})")

    # Optional effect type enum
    eff = entry.get("interaction_effect_type")
    if eff is not None and eff not in ALLOWED_EFFECT_TYPES:
        errors.append(
            f"invalid interaction_effect_type: {eff!r} (allowed: {sorted(ALLOWED_EFFECT_TYPES)})"
        )

    # Agent ID shapes
    for side in ("agent1_id", "agent2_id"):
        aid = entry.get(side)
        if isinstance(aid, str) and aid and classify_agent(aid) == "unknown":
            errors.append(
                f"invalid {side}: {aid!r} "
                "(expected rxcui, Cxxxxxxx, class:name, or ref:name)"
            )

    # Optional: source_urls must be list of strings if present
    urls = entry.get("source_urls")
    if urls is not None:
        if not isinstance(urls, list):
            errors.append("source_urls must be a list")
        else:
            for idx, u in enumerate(urls):
                if not isinstance(u, str) or not u.strip():
                    errors.append(f"source_urls[{idx}] must be a non-empty string")

    # Optional: source_pmids must be list of strings if present
    pmids = entry.get("source_pmids")
    if pmids is not None:
        if not isinstance(pmids, list):
            errors.append("source_pmids must be a list")
        else:
            for idx, p in enumerate(pmids):
                if not isinstance(p, str) or not p.strip().isdigit():
                    errors.append(f"source_pmids[{idx}] must be a digit string")

    return errors


def detect_duplicates(entries: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Check 2. Returns {id: [index, index, ...]} for any id appearing more than once."""
    buckets: dict[str, list[int]] = {}
    for idx, e in enumerate(entries):
        eid = e.get("id")
        if isinstance(eid, str) and eid:
            buckets.setdefault(eid, []).append(idx)
    return {k: v for k, v in buckets.items() if len(v) > 1}


def normalize_severity(draft_severity: str) -> str | None:
    """Check 8. Draft vocab → Flutter enum. Returns None if unknown."""
    if not isinstance(draft_severity, str):
        return None
    return SEVERITY_MAP.get(draft_severity.lower())


def check_display_layer_policy(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Checks 12, 13, 14 (Wave 9.B.3 Phase 1, 2026-05-27). Pure function —
    no network, no side effects. Returns a list of issue kwargs ready to be
    wrapped in EntryIssue. Empty list means the entry's display_layer state
    is policy-compliant.

    Implements the two-lane policy from
    reports/wave_9b_minor_review/9B2_SCHEMA_DESIGN_DISPLAY_LAYER.md:

      Check 12 — display_layer enum
        Field is OPTIONAL during migration (Phase 1 → Phase 3 window).
        When PRESENT, must be one of {"alert", "background"} or it's an
        error. There is no "deprecated" value — deprecation continues to
        use the existing retired_at / retired_reason columns.

      Check 13 — severity ↔ lane invariant
        - display_layer == "alert"      requires severity ∈ {Major, Moderate, Contraindicated}
        - display_layer == "background" requires severity ∈ {Minor, Monitor}
        - display_layer absent + Minor/Monitor: WARNING (missing lane
          declaration for non-alert-eligible severity). Becomes ERROR
          after Phase 3 backfills explicit display_layer on every live
          entry. Tracked by report `migration_warning` flag in details.
        - display_layer absent + Major/Moderate/Contraindicated: no
          finding (backward-compat default ⇒ alert is correct).
        - background + alert-eligible severity (Major+): ERROR — real
          policy conflict, not a migration artifact.
        - alert + Minor/Monitor: WARNING during migration; severity
          should either be upgraded to Moderate+ or display_layer should
          flip to "background". Becomes ERROR after Phase 3.

      Check 14 — background_rationale required
        When display_layer == "background", background_rationale must be
        a non-empty string. The rationale records WHY this entry is not
        a user-facing alert — load-bearing context for the next reviewer.

    Retired entries (`retired_at` set) are exempt from Check 13 — they
    are not user-facing, so the lane invariant doesn't apply.
    """
    issues: list[dict[str, Any]] = []

    display_layer = entry.get("display_layer")
    severity_raw = entry.get("severity")
    severity_key = severity_raw.lower() if isinstance(severity_raw, str) else None
    background_rationale = entry.get("background_rationale")
    if not isinstance(background_rationale, str):
        background_rationale = ""
    retired = bool(entry.get("retired_at"))

    # Check 12 — display_layer enum (only enforced when field is present)
    if display_layer is not None and display_layer not in DISPLAY_LAYER_VALUES:
        issues.append({
            "check": "display_layer_enum",
            "severity": "error",
            "message": (
                f"invalid display_layer: {display_layer!r} "
                f"(allowed: {sorted(DISPLAY_LAYER_VALUES)}; deprecation uses "
                f"retired_at, not display_layer)"
            ),
        })
        # Stop downstream checks — enum is broken, lane semantics meaningless.
        return issues

    # Retired entries skip the lane invariant (Check 13) entirely.
    # Background_rationale (Check 14) still applies if display_layer is set,
    # for audit symmetry, but in practice authors won't set display_layer on
    # retired entries.
    if not retired and severity_key is not None:
        in_alert_lane_sev = severity_key in ALERT_LANE_DRAFT_SEVERITIES
        in_bg_lane_sev = severity_key in BACKGROUND_LANE_DRAFT_SEVERITIES

        if display_layer == "background":
            if in_alert_lane_sev:
                issues.append({
                    "check": "display_layer_lane",
                    "severity": "error",
                    "message": (
                        f"display_layer='background' conflicts with severity={severity_raw!r}. "
                        f"Background lane is for Minor/Monitor only; alert-eligible severities "
                        f"({sorted(ALERT_LANE_DRAFT_SEVERITIES)}) must use display_layer='alert'."
                    ),
                    "details": {"severity": severity_raw, "display_layer": display_layer},
                })
        elif display_layer == "alert":
            if in_bg_lane_sev:
                issues.append({
                    "check": "display_layer_lane",
                    "severity": "warning",
                    "message": (
                        f"display_layer='alert' with severity={severity_raw!r} violates the "
                        f"two-lane policy (Minor/Monitor must be background). Migration "
                        f"warning — promote severity OR move to display_layer='background'. "
                        f"Will become error after Phase 3."
                    ),
                    "details": {
                        "severity": severity_raw,
                        "display_layer": display_layer,
                        "migration_warning": True,
                    },
                })
        else:  # display_layer absent
            if in_bg_lane_sev:
                issues.append({
                    "check": "display_layer_missing",
                    "severity": "warning",
                    "message": (
                        f"display_layer absent; severity={severity_raw!r} (Minor/Monitor) is "
                        f"not alert-eligible. Set display_layer='background' explicitly "
                        f"with a background_rationale. Migration warning — will become error "
                        f"after Phase 3."
                    ),
                    "details": {
                        "severity": severity_raw,
                        "migration_warning": True,
                    },
                })
            # display_layer absent + Major/Moderate/Contraindicated: no finding.
            # Backward-compat default of 'alert' is correct for these. Phase 3
            # will backfill the explicit declaration.

    # Check 14 — background lane requires a rationale
    if display_layer == "background" and not background_rationale.strip():
        issues.append({
            "check": "display_layer_rationale",
            "severity": "error",
            "message": (
                "display_layer='background' requires a non-empty background_rationale "
                "explaining why this entry is not a user-facing alert. Example: 'CoQ10 is "
                "studied as MITIGATION for SAMS, not an adverse interaction.'"
            ),
        })

    return issues


def normalize_direction(entry: dict[str, Any]) -> dict[str, Any]:
    """Check 7. If one side is drug and the other is supplement, ensure
    agent1 is the drug. Preserve original type as type_authored.

    This is the canonicalization used for dedup in the builder. Returns a
    shallow-copied entry with swapped agents if needed plus type_authored.
    """
    out = dict(entry)
    out.setdefault("type_authored", out.get("type"))

    a1_kind = classify_agent(str(out.get("agent1_id", "")))
    a2_kind = classify_agent(str(out.get("agent2_id", "")))

    # If agent2 is a drug (or class) and agent1 is a supplement, swap so
    # drug-side is always first.
    should_swap = False
    if a1_kind in ("supplement", "reference") and a2_kind in ("drug", "class"):
        should_swap = True
    elif a1_kind == "class" and a2_kind == "drug":
        # Normalize: specific drug first, class second (harder to match class first)
        should_swap = False  # keep authored order
    elif a1_kind == "supplement" and a2_kind == "supplement":
        # Stable sort: lower id first for deterministic sup-sup pairs
        if str(out.get("agent1_id", "")) > str(out.get("agent2_id", "")):
            should_swap = True

    if should_swap:
        out["agent1_name"], out["agent2_name"] = out["agent2_name"], out["agent1_name"]
        out["agent1_id"], out["agent2_id"] = out["agent2_id"], out["agent1_id"]
        # type stays as authored; type_authored is preserved above

    # Compute canonical type based on *normalized* sides
    a1_kind = classify_agent(str(out.get("agent1_id", "")))
    a2_kind = classify_agent(str(out.get("agent2_id", "")))
    agent_type_map = {
        "drug": "drug",
        "class": "drug_class",
        "supplement": "supplement",
        "reference": "reference",
    }
    out["agent1_type"] = agent_type_map.get(a1_kind, "unknown")
    out["agent2_type"] = agent_type_map.get(a2_kind, "unknown")

    # Med-Food / Food-Med / Sup-Food / Food-Sup carry a real CUI on the food
    # side, so classify_agent() returns 'supplement' (CUI shape). Override
    # the agent_type to "food" so downstream consumers (Flutter alert
    # renderer, audit gates) can distinguish food advisories from
    # supplement-drug interactions. The interaction's top-level `type`
    # field is the source of truth for which side is food.
    type_authored = str(out.get("type_authored", "") or "")
    if type_authored in ("Med-Food", "Food-Med"):
        # After normalize_direction(), Med-Food and Food-Med both place
        # food at agent2 (drug-side ends up at agent1).
        out["agent2_type"] = "food"
    elif type_authored in ("Sup-Food", "Food-Sup"):
        # Sup-Food / Food-Sup: ambiguous after CUI-sort swap. Mark whichever
        # side does NOT match the IQM-supplement-CUI as food. For now, set
        # both to a sentinel and let downstream choose — but in practice
        # we have no Sup-Food entries yet, so leave a TODO.
        # TODO: when Sup-Food entries appear, add per-side food marker on
        #       the source entry to disambiguate.
        pass
    return out


# Common stop-words to drop from agent names before topic-overlap check.
# Without this, "class:statins" → ["class", "statins"] would always
# match any article mentioning "statin" — too lax. We want the *specific*
# agents to appear (Vitamin K, Warfarin, etc.), not generic terms.
_TOPIC_STOPWORDS = frozenset({
    "class", "the", "and", "for", "with", "from", "into", "drug",
    "drugs", "medication", "medications", "supplement", "supplements",
    "vitamin", "extract", "powder", "supplement", "natural", "herbal",
    "oil", "acid", "high", "low", "tyramine-containing",
})


# Latin-name + synonym aliases for topic-overlap. Common-name agent
# rules cite papers that often title-mention the Latin binomial. Without
# this map, the heuristic reports false positives on legit citations
# (e.g. fenugreek paper titled "Trigonella foenum-graecum").
_AGENT_ALIASES: dict[str, tuple[str, ...]] = {
    "st. john's wort":   ("hypericum", "perforatum"),
    "st johns wort":     ("hypericum", "perforatum"),
    "fenugreek":         ("trigonella", "foenum-graecum", "foenum"),
    "ashwagandha":       ("withania", "somnifera"),
    "valerian":          ("valeriana", "officinalis"),
    "ginkgo biloba":     ("ginkgo", "biloba", "egb"),
    "milk thistle":      ("silybum", "marianum", "silymarin", "silibinin"),
    "saw palmetto":      ("serenoa", "repens"),
    "echinacea":         ("echinacea", "purpurea"),
    "ginger":            ("zingiber", "officinale"),
    "turmeric":          ("curcuma", "longa", "curcumin"),
    "garlic":            ("allium", "sativum"),
    "ginseng":           ("panax", "ginseng"),
    "black cohosh":      ("cimicifuga", "actaea", "racemosa"),
    "dong quai":         ("angelica", "sinensis"),
    "kava":              ("piper", "methysticum"),
    "yohimbe":           ("pausinystalia", "yohimbine"),
    "willow bark":       ("salix", "salicin"),
    "evening primrose":  ("oenothera", "biennis", "gla"),
    "vitamin k":         ("phylloquinone", "menaquinone", "k1", "k2"),
    "vitamin d":         ("cholecalciferol", "ergocalciferol", "calcidiol", "calcitriol"),
    "vitamin e":         ("tocopherol", "tocotrienol"),
    "vitamin b12":       ("cobalamin", "cyanocobalamin", "methylcobalamin"),
    "vitamin a":         ("retinol", "retinoid", "retinyl"),
    "vitamin c":         ("ascorbic", "ascorbate"),
    "folate":            ("folic", "methylfolate"),
    "niacin":            ("nicotinic", "nicotinamide"),
    "calcium":           ("calci",),
    "iron":              ("ferrous", "ferric"),
    "magnesium":         ("magnesi",),
    "potassium":         ("potass",),
    "alpha-lipoic acid": ("lipoic", "thioctic"),
    "coenzyme q10":      ("ubiquinol", "ubiquinone", "coq10", "coenzyme"),
    "5-htp":             ("hydroxytryptophan", "serotonin", "5ht"),
    "red yeast rice":    ("monacolin", "lovastatin", "monascus"),
    "warfarin":          ("coumadin", "coumarin", "anticoagulant", "inr"),
    "soy isoflavones":   ("soy", "isoflavone", "genistein", "daidzein"),
}


def _pmid_topic_overlap(article: dict[str, Any], rule: dict[str, Any]) -> bool:
    """Loose topic-overlap heuristic.

    Returns True if at least one agent-name token (length >= 4, not a
    stopword) OR any known alias for that agent appears in the article's
    title + abstract. Returns True when there are no usable agent tokens
    (defensive fallback — don't flag entries with all-stopword names
    like 'class:statins').
    """
    haystack = (
        (article.get("title") or "") + " " + (article.get("abstract") or "")
    ).lower()
    needles: set[str] = set()
    for field_name in ("agent1_name", "agent2_name"):
        raw = str(rule.get(field_name, "")).lower()
        # Strip class: prefix if present
        if raw.startswith("class:") or raw.startswith("class "):
            continue  # class names are too generic for topic-overlap
        # Add aliases for known agents (Latin names, synonyms)
        clean = raw.replace("(class)", "").replace("(high dose)", "").strip()
        for alias_key, aliases in _AGENT_ALIASES.items():
            if alias_key in clean or clean in alias_key:
                needles.update(aliases)
        # Special-case vitamin <letter>: keep the full phrase as a needle
        # because the letter alone is too short to clear the >=4 filter
        # (e.g., "Vitamin E" → 'tocopherol' alias might not match an article
        # that titles "Vitamin E serum levels…" verbatim).
        m = re.match(r"vitamin\s+([a-z]\d{0,2})\b", clean)
        if m:
            needles.add(f"vitamin {m.group(1)}")
        # Tokenize on common separators
        for tok in clean.replace("(", " ").replace(")", " ").replace(",", " ").split():
            tok = tok.strip(".,;:'-")
            if len(tok) >= 4 and tok not in _TOPIC_STOPWORDS:
                needles.add(tok)
    if not needles:
        return True  # nothing to check; defer to other gates
    return any(n in haystack for n in needles)


def extract_pmids_from_urls(source_urls: list[str] | None) -> list[str]:
    """Check 10. Pull numeric PMIDs from any PubMed URLs; dedupe, preserve order."""
    if not source_urls:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for url in source_urls:
        if not isinstance(url, str):
            continue
        for m in PUBMED_URL_RE.finditer(url):
            pmid = m.group("pmid")
            if pmid and pmid not in seen:
                seen.add(pmid)
                out.append(pmid)
    return out


def check_major_source_gate(entry: dict[str, Any]) -> bool:
    """Check 9. Returns True if the Major+ entry passes the source gate.

    Non-Major entries always pass. Major+ entries must have at least one
    non-empty source_url or source_pmid. Accepts either the draft vocab
    (Major/Contraindicated) or the normalized Flutter vocab (avoid/
    contraindicated) so callers can invoke before or after normalization.
    """
    raw = str(entry.get("severity", "")).strip()
    normalized = normalize_severity(raw) or raw.lower()
    if normalized not in ("contraindicated", "avoid"):
        return True

    urls = entry.get("source_urls") or []
    pmids = entry.get("source_pmids") or []
    has_url = any(isinstance(u, str) and u.strip() for u in urls)
    has_pmid = any(isinstance(p, str) and p.strip() for p in pmids)
    return has_url or has_pmid


def map_canonical_id(
    agent_id: str,
    agent_kind: str,
    iqm_cui_index: dict[str, str],
) -> str | None:
    """Check 5. Map a supplement CUI to the ingredient_quality_map canonical_id.

    ``iqm_cui_index`` is a prebuilt ``{cui: canonical_id}`` lookup derived
    from ``scripts/data/ingredient_quality_map.json``.
    """
    if agent_kind != "supplement":
        return None
    return iqm_cui_index.get(agent_id)


def build_iqm_cui_index(
    iqm: dict[str, Any],
    *,
    botanicals: dict[str, Any] | None = None,
    banned_recalled: dict[str, Any] | None = None,
    harmful_additives: dict[str, Any] | None = None,
    other_ingredients: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Build a reverse {cui: canonical_id} index from all pipeline data files.

    Primary source is ingredient_quality_map.json. Supplementary sources
    (botanicals, banned/recalled, harmful_additives, other_ingredients) are
    checked when the CUI is not found in IQM — giving broader coverage for
    herbs, foods, and edge-case ingredients.

    The IQM is a top-level dict keyed by canonical_id. Entries without a
    CUI are skipped. If two canonical_ids share a CUI the earlier one
    (dict-insertion order) wins — this matches the Python 3.7+ stability
    the pipeline already relies on.
    """
    index: dict[str, str] = {}

    # 1. IQM — primary source
    for canonical_id, entry in iqm.items():
        if canonical_id.startswith("_"):  # _metadata
            continue
        cui = entry.get("cui") if isinstance(entry, dict) else None
        if isinstance(cui, str) and cui and cui not in index:
            index[cui] = canonical_id

    # 2. Botanicals — keyed by canonical_id
    if botanicals:
        for canonical_id, entry in botanicals.items():
            if canonical_id.startswith("_") or not isinstance(entry, dict):
                continue
            cui = entry.get("cui")
            if isinstance(cui, str) and cui and cui not in index:
                index[cui] = canonical_id

    # 3. Banned/recalled — array under "ingredients" or "banned_recalled" key
    if banned_recalled:
        items = banned_recalled.get("ingredients") or banned_recalled.get("banned_recalled", [])
        for entry in items:
            if not isinstance(entry, dict):
                continue
            cui = entry.get("cui")
            cid = entry.get("canonical_id") or entry.get("id", "")
            if isinstance(cui, str) and cui and cid and cui not in index:
                index[cui] = cid

    # 4. Harmful additives — array under "harmful_additives" or "ingredients" key
    if harmful_additives:
        items = harmful_additives.get("harmful_additives") or harmful_additives.get("ingredients", [])
        for entry in items:
            if not isinstance(entry, dict):
                continue
            cui = entry.get("cui")
            cid = entry.get("canonical_id") or entry.get("id", "")
            if isinstance(cui, str) and cui and cid and cui not in index:
                index[cui] = cid

    # 5. Other ingredients — keyed by canonical_id or id
    if other_ingredients:
        items = other_ingredients
        if "other_ingredients" in other_ingredients:
            items = {e.get("canonical_id", e.get("id", "")): e
                     for e in other_ingredients["other_ingredients"]
                     if isinstance(e, dict)}
        for canonical_id, entry in items.items():
            if canonical_id.startswith("_") or not isinstance(entry, dict):
                continue
            cui = entry.get("cui")
            if isinstance(cui, str) and cui and cui not in index:
                index[cui] = canonical_id

    return index


def expand_drug_class(
    class_id: str,
    drug_classes: dict[str, Any],
) -> list[str] | None:
    """Check 6. Return the RxCUI list for a class, or None if unknown class."""
    classes = drug_classes.get("classes") or {}
    cls = classes.get(class_id)
    if not isinstance(cls, dict):
        return None
    rxcuis = cls.get("member_rxcuis")
    return list(rxcuis) if isinstance(rxcuis, list) else None


# --------------------------------------------------------------------------- #
# Entry processing (orchestrates the 10 checks for one entry)
# --------------------------------------------------------------------------- #


@dataclass
class VerifyContext:
    iqm_cui_index: dict[str, str]
    drug_classes: dict[str, Any]
    rxnorm: RxNormClientProtocol | None = None
    umls: UMLSSearchClientProtocol | None = None
    pubmed: PubMedValidatorProtocol | None = None


def verify_entry(
    entry: dict[str, Any],
    ctx: VerifyContext,
    report: VerificationReport,
) -> dict[str, Any] | None:
    """Run all 10 checks on one entry. Returns the normalized entry,
    or None if a blocking error occurred."""

    entry_id = str(entry.get("id") or "<unknown>")

    # Check 1: schema
    schema_errors = validate_schema(entry)
    if schema_errors:
        for msg in schema_errors:
            report.add_issue(
                EntryIssue(entry_id=entry_id, check="schema", severity="error", message=msg)
            )
        return None

    # Checks 12, 13, 14 (Wave 9.B.3 Phase 1): display_layer policy.
    # Validates the optional `display_layer` field, the severity-lane
    # invariant, and the background_rationale requirement. Emits warnings
    # for the migration-window cases (Minor/Monitor entries without an
    # explicit display_layer declaration) and errors for hard policy
    # conflicts. Pure function over the entry dict — no I/O.
    for issue_kw in check_display_layer_policy(entry):
        report.add_issue(EntryIssue(entry_id=entry_id, **issue_kw))

    # Checks 7, 8: normalize direction + severity
    normalized = normalize_direction(entry)
    draft_sev = str(normalized.get("severity", ""))
    flutter_sev = normalize_severity(draft_sev)
    if flutter_sev is None:
        report.add_issue(
            EntryIssue(
                entry_id=entry_id,
                check="severity",
                severity="error",
                message=f"unmappable severity: {draft_sev!r}",
            )
        )
        return None
    normalized["severity"] = flutter_sev

    # Check 10: extract PMIDs (merge with any explicit source_pmids)
    authored_pmids = normalized.get("source_pmids") or []
    extracted = extract_pmids_from_urls(normalized.get("source_urls"))
    merged_pmids: list[str] = []
    seen: set[str] = set()
    for p in list(authored_pmids) + extracted:
        if isinstance(p, str) and p.strip().isdigit() and p not in seen:
            seen.add(p)
            merged_pmids.append(p)
    normalized["source_pmids"] = merged_pmids

    # Check 11: PubMed PMID content verification (live efetch + topic match).
    # Only runs when ctx.pubmed is wired (CLI flag --check-pubmed). Catches
    # the failure mode that bit us on the Tyramine + Valerian sweep: an
    # ID that "looks valid" but the cited article is wrong-topic.
    #
    # Three failure shapes, all surfaced as warnings (not errors) so the
    # build still produces output and authors can fix iteratively:
    #   - ghost: PMID 404 / not in PubMed at all
    #   - retracted: PMID exists but article was retracted
    #   - topic_mismatch: PMID exists but title+abstract has zero overlap
    #     with agent1_name / agent2_name (probable wrong citation)
    if ctx.pubmed is not None and merged_pmids:
        for pmid in merged_pmids:
            article = ctx.pubmed.fetch(pmid)
            if article is None:
                report.ghost_pmids.append({
                    "entry_id": entry_id,
                    "pmid": pmid,
                    "reason": "not_found_in_pubmed",
                })
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="pmid_ghost",
                        severity="warning",
                        message=f"PMID {pmid} not found in PubMed (ghost citation)",
                    )
                )
                continue
            if article.get("retracted"):
                report.retracted_pmids.append({
                    "entry_id": entry_id,
                    "pmid": pmid,
                    "title": article.get("title", ""),
                })
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="pmid_retracted",
                        severity="warning",
                        message=f"PMID {pmid} flagged retracted in PubMed",
                    )
                )
                continue
            if not _pmid_topic_overlap(article, normalized):
                report.topic_mismatch_pmids.append({
                    "entry_id": entry_id,
                    "pmid": pmid,
                    "title": (article.get("title") or "")[:200],
                    "agent1_name": normalized.get("agent1_name"),
                    "agent2_name": normalized.get("agent2_name"),
                })
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="pmid_topic_mismatch",
                        severity="warning",
                        message=(
                            f"PMID {pmid} title+abstract has zero overlap with "
                            f"agent names — possible wrong citation"
                        ),
                    )
                )

    # Check 9: Major+ source gate (run *after* PMID extraction)
    if not check_major_source_gate(normalized):
        report.add_issue(
            EntryIssue(
                entry_id=entry_id,
                check="source_gate",
                severity="error",
                message=f"{flutter_sev} severity requires at least 1 source URL or PMID",
            )
        )
        report.blocked_by.append(
            {
                "id": entry_id,
                "reason": f"{flutter_sev} severity requires at least 1 source URL or PMID",
            }
        )
        return None

    # Check 5: canonical_id mapping for supplements
    # NOTE: foods (Med-Food / Food-Med / Sup-Food / Food-Sup) carry CUIs but
    # are intentionally out of IQM scope (the IQM is supplement-only). After
    # normalize_direction(), Med-Food and Food-Med both place the food at
    # agent2. Sup-Food/Food-Sup have CUI-CUI sides that may swap by id sort —
    # for those, fall back to noting both sides as food-eligible.
    type_authored = str(normalized.get("type_authored", "") or "")
    food_sides: set[str] = set()
    if type_authored in ("Med-Food", "Food-Med"):
        food_sides = {"agent2"}
    elif type_authored in ("Sup-Food", "Food-Sup"):
        food_sides = {"agent1", "agent2"}  # ambiguous after CUI-sort swap

    for side in ("agent1", "agent2"):
        agent_id = str(normalized.get(f"{side}_id", ""))
        kind = classify_agent(agent_id)
        if kind == "supplement":
            canonical = map_canonical_id(agent_id, kind, ctx.iqm_cui_index)
            normalized[f"{side}_canonical_id"] = canonical
            if canonical is None:
                if side in food_sides:
                    # Food agent — out of IQM scope, no warning, track separately
                    report.food_agents.append(
                        {
                            "entry_id": entry_id,
                            "side": side,
                            "cui": agent_id,
                            "name": normalized.get(f"{side}_name"),
                            "type_authored": type_authored,
                        }
                    )
                else:
                    report.add_issue(
                        EntryIssue(
                            entry_id=entry_id,
                            check="canonical_map",
                            severity="warning",
                            message=f"supplement {agent_id} has no canonical_id in ingredient_quality_map",
                            details={"agent_side": side, "name": normalized.get(f"{side}_name")},
                        )
                    )
                    report.unmapped_supplements.append(
                        {
                            "entry_id": entry_id,
                            "side": side,
                            "cui": agent_id,
                            "name": normalized.get(f"{side}_name"),
                        }
                    )
        elif kind == "reference":
            authored_canonical = normalized.get(f"{side}_canonical_id")
            if isinstance(authored_canonical, str) and authored_canonical.strip():
                normalized[f"{side}_canonical_id"] = authored_canonical.strip()
            else:
                normalized[f"{side}_canonical_id"] = agent_id.removeprefix("ref:")
        else:
            normalized[f"{side}_canonical_id"] = None

    # Check 6: class expansion validation (store expanded list for builder)
    for side in ("agent1", "agent2"):
        agent_id = str(normalized.get(f"{side}_id", ""))
        if classify_agent(agent_id) != "class":
            continue
        rxcuis = expand_drug_class(agent_id, ctx.drug_classes)
        if rxcuis is None:
            report.add_issue(
                EntryIssue(
                    entry_id=entry_id,
                    check="drug_class",
                    severity="error",
                    message=f"unknown drug class: {agent_id}",
                )
            )
            report.unknown_classes.append({"entry_id": entry_id, "class_id": agent_id})
            return None
        normalized[f"{side}_class_rxcuis"] = rxcuis

    # Check 3: RXCUI verification (optional — only if ctx.rxnorm provided)
    if ctx.rxnorm is not None:
        for side in ("agent1", "agent2"):
            agent_id = str(normalized.get(f"{side}_id", ""))
            if classify_agent(agent_id) != "drug":
                continue
            props = ctx.rxnorm.properties(agent_id)
            if props is None:
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="rxcui",
                        severity="error",
                        message=f"rxcui {agent_id} not found in RxNorm",
                        details={"agent_side": side, "name": normalized.get(f"{side}_name")},
                    )
                )
                return None
            authored_name = str(normalized.get(f"{side}_name", "")).strip().lower()
            returned_name = str(props.get("name", "")).strip().lower()
            synonym = str(props.get("synonym", "")).strip().lower()
            if authored_name and authored_name not in returned_name and authored_name not in synonym:
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="rxcui",
                        severity="warning",
                        message=f"rxcui {agent_id} resolves to {props.get('name')!r}, not {normalized.get(f'{side}_name')!r}",
                        details={"agent_side": side, "rxcui": agent_id},
                    )
                )
                report.rxcui_mismatches.append(
                    {
                        "entry_id": entry_id,
                        "side": side,
                        "rxcui": agent_id,
                        "authored_name": normalized.get(f"{side}_name"),
                        "rxnorm_name": props.get("name"),
                    }
                )

    # Check 4: CUI verification (optional — only if ctx.umls provided)
    # Strategy: look up the authored CUI directly to confirm it exists in UMLS.
    # Do NOT search by name and compare — UMLS name search returns the top
    # text-match CUI which may differ from a valid authored CUI (e.g. "Magnesium"
    # returns a lab-test CUI, not the supplement concept). A valid CUI that
    # resolves via lookup_cui is accepted as correct.
    if ctx.umls is not None:
        for side in ("agent1", "agent2"):
            agent_id = str(normalized.get(f"{side}_id", ""))
            if classify_agent(agent_id) != "supplement":
                continue
            authored_name = str(normalized.get(f"{side}_name", "")).strip()
            if not authored_name:
                continue
            # First: verify the authored CUI exists via direct lookup
            try:
                concept = ctx.umls.lookup_cui(agent_id)
            except Exception:
                concept = None  # timeout or network error — treat as soft miss
            if concept is not None:
                # CUI exists in UMLS — accepted as valid
                continue
            # CUI not found in UMLS — try name search as fallback
            try:
                exact = ctx.umls.search_exact(authored_name)
            except Exception:
                exact = None
            if not exact:
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="cui",
                        severity="warning",
                        message=f"cui {agent_id} for {authored_name!r} not found in UMLS (lookup failed, name search also returned no results)",
                        details={"agent_side": side},
                    )
                )
                continue
            resolved_cui = str(exact.get("cui", "")).strip()
            if resolved_cui and resolved_cui != agent_id:
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="cui",
                        severity="warning",
                        message=f"cui {agent_id} not found in UMLS; name search for {authored_name!r} suggests {resolved_cui}",
                        details={"agent_side": side},
                    )
                )
                report.cui_corrections.append(
                    {
                        "id": entry_id,
                        "claimed": agent_id,
                        "claimed_resolves_to": None,
                        "correct_cui_for": authored_name,
                        "suggested_cui": resolved_cui,
                        "action": "corrected in output",
                    }
                )
                normalized[f"{side}_id"] = resolved_cui
                # Re-run canonical_id map with corrected cui
                normalized[f"{side}_canonical_id"] = map_canonical_id(
                    resolved_cui, "supplement", ctx.iqm_cui_index
                )

    # SP-6 evidence-strength derivation. Curated pairwise interactions ship
    # `clinical_confidence` + `evidence_basis` but no graded `evidence_level`
    # (why the DB shipped 150/150 NULL). Derive it into the canonical vocab,
    # provenance-gated, so a graded — never NULL — value always reaches the
    # builder. ⚠ Review the proposed grades before rebuild:
    #   python3 scripts/api_audit/review_evidence_derivation.py
    normalized["evidence_level"] = derive_evidence_level(
        entry.get("evidence_basis"),
        entry.get("clinical_confidence"),
        normalized.get("source_pmids"),
    )

    return normalized


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #


def load_drafts(drafts_path: Path) -> list[dict[str, Any]]:
    """Load all JSON shards under a directory (or a single JSON file).

    Each file may be either a flat list of entries or an object with an
    ``interactions`` key holding the list.
    """
    entries: list[dict[str, Any]] = []

    if drafts_path.is_file():
        files = [drafts_path]
    elif drafts_path.is_dir():
        files = sorted(p for p in drafts_path.glob("*.json") if p.is_file())
    else:
        raise FileNotFoundError(f"drafts path does not exist: {drafts_path}")

    for f in files:
        with f.open() as fh:
            payload = json.load(fh)
        if isinstance(payload, list):
            entries.extend(payload)
        elif isinstance(payload, dict):
            interactions = payload.get("interactions")
            if isinstance(interactions, list):
                entries.extend(interactions)
        # else: skip silently — verifier will report missing entries upstream

    return entries


def load_ingredient_quality_map(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


def load_drug_classes(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Main verification pipeline
# --------------------------------------------------------------------------- #


def verify_all(
    entries: list[dict[str, Any]],
    ctx: VerifyContext,
) -> tuple[VerificationReport, list[dict[str, Any]]]:
    report = VerificationReport(total_entries=len(entries))

    # Check 2: duplicate ID detection (operates on full list)
    dupes = detect_duplicates(entries)
    for entry_id, idxs in dupes.items():
        report.add_issue(
            EntryIssue(
                entry_id=entry_id,
                check="duplicate",
                severity="error",
                message=f"duplicate id appears {len(idxs)} times (indexes: {idxs})",
            )
        )

    dupe_ids = set(dupes.keys())

    normalized_out: list[dict[str, Any]] = []
    for entry in entries:
        eid = entry.get("id")
        if isinstance(eid, str) and eid in dupe_ids:
            # Still run checks on first occurrence; subsequent are dropped.
            if eid not in {x.get("id") for x in normalized_out}:
                n = verify_entry(entry, ctx, report)
                if n is not None:
                    normalized_out.append(n)
            continue

        n = verify_entry(entry, ctx, report)
        if n is not None:
            normalized_out.append(n)

    report.valid = len(normalized_out)
    return report, normalized_out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _default_iqm_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "ingredient_quality_map.json"


def _default_drug_classes_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "drug_classes.json"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify and normalize curated interaction drafts")
    p.add_argument(
        "--drafts",
        type=Path,
        required=True,
        help="Path to a JSON file or directory of JSON shards with curated entries",
    )
    p.add_argument(
        "--iqm",
        type=Path,
        default=_default_iqm_path(),
        help="Path to ingredient_quality_map.json (default: scripts/data/ingredient_quality_map.json)",
    )
    p.add_argument(
        "--drug-classes",
        type=Path,
        default=_default_drug_classes_path(),
        help="Path to drug_classes.json (default: scripts/data/drug_classes.json)",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write structured JSON report to this path",
    )
    p.add_argument(
        "--normalized-out",
        type=Path,
        default=None,
        help="Write normalized entries to this path (consumed by build_interaction_db.py)",
    )
    p.add_argument(
        "--corrections-out",
        type=Path,
        default=None,
        help="Write auto-corrections (CUI fixes, RXCUI mismatches, unmapped) to this path",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Skip RxNorm and UMLS network checks (schema/normalization only)",
    )
    p.add_argument(
        "--no-rxnorm",
        action="store_true",
        help="Skip RxNorm verification only",
    )
    p.add_argument(
        "--no-umls",
        action="store_true",
        help="Skip UMLS verification only",
    )
    p.add_argument(
        "--check-pubmed",
        action="store_true",
        help=(
            "Run Check 11: live PubMed PMID verification (efetch each cited "
            "PMID, flag 404s / retracted / topic-mismatched articles). Slow "
            "(~1-2s per PMID with rate-limiting). Off by default for routine "
            "rebuilds; on for clinical-data audits."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.drafts.exists():
        print(f"ERROR: drafts path does not exist: {args.drafts}", file=sys.stderr)
        return 2
    if not args.iqm.exists():
        print(f"ERROR: IQM path does not exist: {args.iqm}", file=sys.stderr)
        return 2
    if not args.drug_classes.exists():
        print(f"ERROR: drug classes path does not exist: {args.drug_classes}", file=sys.stderr)
        return 2

    entries = load_drafts(args.drafts)
    iqm = load_ingredient_quality_map(args.iqm)
    drug_classes = load_drug_classes(args.drug_classes)

    # Load supplementary data files for broader CUI mapping
    data_dir = args.iqm.parent
    supplementary = {}
    for fname, key in [
        ("botanical_ingredients.json", "botanicals"),
        ("banned_recalled_ingredients.json", "banned_recalled"),
        ("harmful_additives.json", "harmful_additives"),
        ("other_ingredients.json", "other_ingredients"),
    ]:
        fpath = data_dir / fname
        if fpath.exists():
            with open(fpath) as f:
                supplementary[key] = json.load(f)

    ctx = VerifyContext(
        iqm_cui_index=build_iqm_cui_index(iqm, **supplementary),
        drug_classes=drug_classes,
    )

    if not args.offline and not args.no_rxnorm:
        ctx.rxnorm = RxNormClient()
    if not args.offline and not args.no_umls:
        try:
            # Reuse the verify_cui UMLS client via dynamic import
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from verify_cui import UMLSClient  # type: ignore
            api_key = os.environ.get("UMLS_API_KEY", "").strip()
            if api_key:
                ctx.umls = UMLSClient(api_key=api_key)
            else:
                print("  (UMLS skipped — no UMLS_API_KEY in env)", file=sys.stderr)
        except Exception as exc:  # pragma: no cover — import guard
            print(f"  (UMLS skipped — could not load client: {exc})", file=sys.stderr)

    if not args.offline and args.check_pubmed:
        try:
            ctx.pubmed = PubMedValidator()
            print("  (PubMed live verification enabled — Check 11)", file=sys.stderr)
        except Exception as exc:  # pragma: no cover — import guard
            print(f"  (PubMed skipped — could not load client: {exc})", file=sys.stderr)

    report, normalized = verify_all(entries, ctx)

    # Write outputs
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.normalized_out:
        args.normalized_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_metadata": {
                "schema_version": "1.0.0",
                "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "source_count": len(entries),
                "verified_count": len(normalized),
            },
            "interactions": normalized,
        }
        args.normalized_out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.corrections_out:
        args.corrections_out.parent.mkdir(parents=True, exist_ok=True)
        corrections = {
            "cui_corrections": report.cui_corrections,
            "rxcui_mismatches": report.rxcui_mismatches,
            "unmapped_supplements": report.unmapped_supplements,
            "unknown_classes": report.unknown_classes,
        }
        args.corrections_out.write_text(
            json.dumps(corrections, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # Console summary
    print(
        f"verify_interactions: total={report.total_entries} valid={report.valid} "
        f"warnings={report.warnings} errors={report.errors}",
        file=sys.stderr,
    )
    for b in report.blocked_by:
        print(f"  BLOCKED: {b['id']} — {b['reason']}", file=sys.stderr)

    return 0 if report.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
