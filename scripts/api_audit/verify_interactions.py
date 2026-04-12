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

ALLOWED_TYPES: frozenset[str] = frozenset(
    {"Med-Sup", "Sup-Med", "Sup-Sup", "Med-Med", "Med-Food", "Sup-Food", "Food-Med"}
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

# Agent ID shapes
RXCUI_RE = re.compile(r"^\d+$")
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
# Pure functions — the 10 checks (testable without network)
# --------------------------------------------------------------------------- #


def classify_agent(agent_id: str) -> str:
    """Classify an agent_id string by its shape.

    Returns one of: 'drug' (rxcui), 'supplement' (cui), 'class' (class:...),
    'unknown'.
    """
    if not isinstance(agent_id, str):
        return "unknown"
    aid = agent_id.strip()
    if CLASS_RE.match(aid):
        return "class"
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
            errors.append(f"invalid {side}: {aid!r} (expected rxcui, Cxxxxxxx, or class:name)")

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
    if a1_kind == "supplement" and a2_kind in ("drug", "class"):
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
    out["agent1_type"] = {"drug": "drug", "class": "drug_class", "supplement": "supplement"}.get(
        a1_kind, "unknown"
    )
    out["agent2_type"] = {"drug": "drug", "class": "drug_class", "supplement": "supplement"}.get(
        a2_kind, "unknown"
    )
    return out


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


def build_iqm_cui_index(iqm: dict[str, Any]) -> dict[str, str]:
    """Build a reverse {cui: canonical_id} index from ingredient_quality_map.json.

    The IQM is a top-level dict keyed by canonical_id. Entries without a
    CUI are skipped. If two canonical_ids share a CUI the earlier one
    (dict-insertion order) wins — this matches the Python 3.7+ stability
    the pipeline already relies on.
    """
    index: dict[str, str] = {}
    for canonical_id, entry in iqm.items():
        if canonical_id.startswith("_"):  # _metadata
            continue
        cui = entry.get("cui") if isinstance(entry, dict) else None
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
    for side in ("agent1", "agent2"):
        agent_id = str(normalized.get(f"{side}_id", ""))
        kind = classify_agent(agent_id)
        if kind == "supplement":
            canonical = map_canonical_id(agent_id, kind, ctx.iqm_cui_index)
            normalized[f"{side}_canonical_id"] = canonical
            if canonical is None:
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
    if ctx.umls is not None:
        for side in ("agent1", "agent2"):
            agent_id = str(normalized.get(f"{side}_id", ""))
            if classify_agent(agent_id) != "supplement":
                continue
            authored_name = str(normalized.get(f"{side}_name", "")).strip()
            if not authored_name:
                continue
            exact = ctx.umls.search_exact(authored_name)
            if not exact:
                continue  # no hit is a soft miss, not an error
            resolved_cui = str(exact.get("cui", "")).strip()
            if resolved_cui and resolved_cui != agent_id:
                report.add_issue(
                    EntryIssue(
                        entry_id=entry_id,
                        check="cui",
                        severity="warning",
                        message=f"cui mismatch: authored {agent_id} for {authored_name!r}, UMLS returned {resolved_cui}",
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

    ctx = VerifyContext(
        iqm_cui_index=build_iqm_cui_index(iqm),
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
