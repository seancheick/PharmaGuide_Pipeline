#!/usr/bin/env python3
"""Cert verification resolver — maps a product's claimed cert programs to
SKU/product-line registry matches.

Reads:
  - scripts/data/cert_registry.json (public registry snapshots)
  - scripts/data/curated_overrides/cert_verification_overrides.json (manual overrides + needs_review queue)

Returns a list of CertResolution per (brand, product) input.

Per v4 spec (docs/plans/SCORING_V4_PROPOSAL.md §10):
  - Conservative fuzzy thresholds — false positives worse than missed bonuses
  - sku ratio >= 92                 -> sku
  - sku ratio 80-91                  -> needs_review
  - product-line keyword overlap >= 85 -> product_line
  - product-line overlap 70-84        -> needs_review
  - brand match only, no product hit -> brand_only
  - no brand match                    -> claimed_only

Only scope in {sku, product_line} scores B4a points in v4. brand_only routes
to manufacturer trust D. claimed_only is display-only.

P0.1a is audit-only. This resolver is consumed by cert_audit_report.py.
No edits to score_supplements.py or enrich_supplements_v3.py in P0.1a.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    from rapidfuzz import fuzz
except ImportError as exc:
    raise SystemExit(
        "rapidfuzz is required (already in requirements-dev.txt). "
        "Install with: pip install rapidfuzz>=3.9,<4"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "scripts" / "data"
REGISTRY_PATH = DATA_DIR / "cert_registry.json"
OVERRIDES_PATH = DATA_DIR / "curated_overrides" / "cert_verification_overrides.json"


# Conservative thresholds — see docstring + v4 spec §10.
SKU_RATIO_FLOOR = 92
SKU_NEEDS_REVIEW_FLOOR = 80
PRODUCT_LINE_KEYWORD_OVERLAP_FLOOR = 85
PRODUCT_LINE_NEEDS_REVIEW_FLOOR = 70


# Recency gate — see v4 spec §10. Snapshots older than the floor cannot score
# in production scoring, only in audit. The resolver still matches them so the
# audit report stays useful, but the resolution carries `stale=True` so the
# scorer wires can refuse to grant points.
RECENCY_AUDIT_ONLY_DAYS = 180          # > 180 days = scoring_blocked (audit only)
RECENCY_NEEDS_REFRESH_WARNING_DAYS = 90  # > 90 days = warn but still score


def _parse_iso_date(value: str | None) -> "datetime | None":
    """Tolerant ISO-date parse. Accepts YYYY-MM-DD or full ISO timestamps."""
    if not value:
        return None
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _recency_status(snapshot_date: str | None) -> tuple[str, int | None]:
    """Returns (status, age_days). Status in {fresh, warn, scoring_blocked, unknown}."""
    from datetime import datetime, timezone
    parsed = _parse_iso_date(snapshot_date)
    if parsed is None:
        return ("unknown", None)
    # `parsed` is naive (strptime). Treat it as UTC for age math.
    parsed_utc = parsed.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - parsed_utc).days
    if age_days > RECENCY_AUDIT_ONLY_DAYS:
        return ("scoring_blocked", age_days)
    if age_days > RECENCY_NEEDS_REFRESH_WARNING_DAYS:
        return ("warn", age_days)
    return ("fresh", age_days)


@dataclass(frozen=True)
class CertResolution:
    """One resolved (brand, product, program) tuple."""

    program: str
    scope: str  # sku | product_line | brand_only | needs_review | claimed_only
    match_confidence: float | None = None
    record_id: str | None = None
    verified_at: str | None = None
    source_url: str | None = None
    notes: str | None = None
    matched_brand: str | None = None
    matched_product: str | None = None
    # Recency state from the registry snapshot this match came from. Production
    # scorers MUST check `scoring_blocked_reason` and skip scoring if set.
    snapshot_date: str | None = None
    snapshot_age_days: int | None = None
    recency_status: str | None = None  # fresh | warn | scoring_blocked | unknown
    scoring_blocked_reason: str | None = None  # set when the resolution cannot grant points

    def scores_points(self) -> bool:
        """v4 rule: only sku/product_line score B4a points AND recency must be fresh/warn."""
        if self.scope not in {"sku", "product_line"}:
            return False
        if self.scoring_blocked_reason:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CertRegistry:
    """In-memory view of cert_registry.json + curated overrides."""

    records_by_program: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    overrides_by_brand_product: dict[tuple[str, str], list[dict[str, Any]]] = field(
        default_factory=dict
    )
    metadata: dict[str, Any] = field(default_factory=dict)
    override_metadata: dict[str, Any] = field(default_factory=dict)
    # Per-source recency status, keyed by program name.
    recency_by_program: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        registry_path: Path = REGISTRY_PATH,
        overrides_path: Path = OVERRIDES_PATH,
    ) -> "CertRegistry":
        registry = cls()

        if registry_path.exists():
            with open(registry_path, encoding="utf-8") as f:
                payload = json.load(f)
            registry.metadata = payload.get("_metadata", {})

            # Compute per-source recency from metadata.registry_sources[*].snapshot_date
            for source in registry.metadata.get("registry_sources", []) or []:
                program = source.get("program")
                if not program:
                    continue
                status, age_days = _recency_status(source.get("snapshot_date"))
                registry.recency_by_program[program] = {
                    "snapshot_date": source.get("snapshot_date"),
                    "age_days": age_days,
                    "status": status,
                    "source_url": source.get("url"),
                }

            for record in payload.get("verified_records", []):
                program = record.get("program") or ""
                # Allow per-record snapshot_date override (rare). Default to source-level.
                rec_recency = registry.recency_by_program.get(program, {})
                record.setdefault("_snapshot_date", rec_recency.get("snapshot_date"))
                record.setdefault("_snapshot_age_days", rec_recency.get("age_days"))
                record.setdefault("_recency_status", rec_recency.get("status", "unknown"))
                registry.records_by_program.setdefault(program, []).append(record)

        if overrides_path.exists():
            with open(overrides_path, encoding="utf-8") as f:
                payload = json.load(f)
            registry.override_metadata = payload.get("_metadata", {})
            for override in payload.get("overrides", []):
                brand = normalize_brand(override.get("brand", ""))
                product = normalize_product(override.get("product", ""))
                if not brand:
                    continue
                key = (brand, product)
                registry.overrides_by_brand_product.setdefault(key, []).append(override)

        return registry

    def candidates_for(self, program: str) -> list[dict[str, Any]]:
        return self.records_by_program.get(program, [])

    def recency_for(self, program: str) -> dict[str, Any]:
        return self.recency_by_program.get(program, {"status": "unknown", "age_days": None})


# --- Normalization ----------------------------------------------------------


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


_BRAND_NOISE_PATTERN = re.compile(
    r"\b("
    r"inc|inc\.|incorporated|llc|l\.l\.c\.|ltd|ltd\.|limited|corp|corp\.|corporation|"
    r"company|co|co\.|gmbh|sa|s\.a\.|nv|n\.v\.|plc|holdings|group|brands|brand"
    r")\b\.?",
    re.IGNORECASE,
)

_PRODUCT_NOISE_PATTERN = re.compile(
    r"\b("
    r"supplement|supplements|dietary supplement|capsules?|tablets?|softgels?|"
    r"chewables?|gummies|gummy|powder|liquid|drops|sublingual|spray|"
    r"vegcaps?|vcaps?|veggie caps?|vcaps|caps|tabs|"
    r"oz|fl oz|ml|mg|mcg|g|kg|grams?|milligrams?|micrograms?|"
    r"servings?|count|ct|pack|packs"
    r")\b\.?",
    re.IGNORECASE,
)


def normalize_brand(text: str) -> str:
    if not text:
        return ""
    text = _strip_accents(text).lower().strip()
    text = re.sub(r"[®™©]", " ", text)
    text = _BRAND_NOISE_PATTERN.sub(" ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_DOSE_NUMERIC_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|kg|iu|ml|fl\s*oz|oz|billion|cfu|cfus)\b\.?",
    re.IGNORECASE,
)

_SKU_DOSE_TOKEN_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|µg|g|kg|iu|ml|fl\s*oz|oz|billion|cfu|cfus)\b\.?",
    re.IGNORECASE,
)

_SKU_FORM_TOKENS = {
    "capsule",
    "capsules",
    "caplet",
    "caplets",
    "tablet",
    "tablets",
    "softgel",
    "softgels",
    "gummy",
    "gummies",
    "chewable",
    "chewables",
    "powder",
    "liquid",
    "drops",
}

_SKU_FLAVOR_TOKENS = {
    "berry",
    "blueberry",
    "chocolate",
    "cinnamon",
    "citrus",
    "coffee",
    "fruit",
    "grape",
    "lemon",
    "lime",
    "mango",
    "mint",
    "mocha",
    "orange",
    "peach",
    "raspberry",
    "strawberry",
    "unflavored",
    "vanilla",
    "watermelon",
}


def normalize_product(text: str) -> str:
    if not text:
        return ""
    text = _strip_accents(text).lower().strip()
    text = re.sub(r"[®™©]", " ", text)
    # Strip dose-number+unit pairs first (e.g., "200 mg", "5000 IU") so the
    # leading numeric doesn't survive into the noise-stripped output.
    text = _DOSE_NUMERIC_PATTERN.sub(" ", text)
    text = _PRODUCT_NOISE_PATTERN.sub(" ", text)
    # Convert hyphens and slashes to spaces — "Multi-Vitamin" must tokenize as
    # ["multi", "vitamin"] so it aligns with "Vitamin" in matching.
    text = re.sub(r"[\-/]", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sku_dose_tokens(text: str) -> set[str]:
    """Dose tokens that materially distinguish certification SKUs."""
    if not text:
        return set()
    tokens: set[str] = set()
    normalized = _strip_accents(text).lower()
    for value, unit in _SKU_DOSE_TOKEN_PATTERN.findall(normalized):
        unit_norm = unit.replace("µ", "u").replace(" ", "")
        tokens.add(f"{value.rstrip('0').rstrip('.') if '.' in value else value}{unit_norm}")
    return tokens


def _sku_form_tokens(text: str) -> set[str]:
    if not text:
        return set()
    normalized = _strip_accents(text).lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return {token for token in normalized.split() if token in _SKU_FORM_TOKENS}


def _sku_flavor_tokens(text: str) -> set[str]:
    if not text:
        return set()
    normalized = _strip_accents(text).lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return {token for token in normalized.split() if token in _SKU_FLAVOR_TOKENS}


def _sku_stim_nonstim_conflict(product_a: str, product_b: str) -> bool:
    def has_stim(text: str) -> bool:
        normalized = _strip_accents(text or "").lower()
        normalized = re.sub(r"\bnon[-\s]?stim\b", " ", normalized)
        return bool(re.search(r"\bstim\b", normalized))

    def has_nonstim(text: str) -> bool:
        normalized = _strip_accents(text or "").lower()
        return bool(re.search(r"\bnon[-\s]?stim\b", normalized))

    return (has_stim(product_a) and has_nonstim(product_b)) or (
        has_stim(product_b) and has_nonstim(product_a)
    )


def _sku_variant_conflict(product_a: str, product_b: str) -> bool:
    """True when dose/form tokens make two high-ratio matches unsafe to auto-SKU.

    Normalization intentionally strips dose and form words for broad product
    matching, but certification verification is SKU-sensitive. A 100 mg softgel
    listing should not score a 200 mg softgel claim, and a gummies listing
    should not score a softgel claim without reviewer confirmation.
    """
    if normalize_product(product_a) == normalize_product(product_b):
        return False

    doses_a = _sku_dose_tokens(product_a)
    doses_b = _sku_dose_tokens(product_b)
    if doses_a and doses_b and doses_a != doses_b:
        return True

    forms_a = _sku_form_tokens(product_a)
    forms_b = _sku_form_tokens(product_b)
    if forms_a and forms_b and forms_a.isdisjoint(forms_b):
        return True

    if _sku_stim_nonstim_conflict(product_a, product_b):
        return True

    flavors_a = _sku_flavor_tokens(product_a)
    flavors_b = _sku_flavor_tokens(product_b)
    # If the registry record is flavor-specific, require the product claim to
    # carry the same flavor. A base registry record such as "Creatine HMB" can
    # still cover a flavored label because several cert registries list product
    # lines rather than every flavor variant.
    if flavors_b and flavors_a != flavors_b:
        return True

    return False


def normalize_program(text: str) -> str:
    """Map alternate program names to canonical IDs."""
    if not text:
        return ""
    t = _strip_accents(text).lower().strip()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # canonical mapping
    canon = {
        "nsf certified for sport": "NSF Sport",
        "nsf for sport": "NSF Sport",
        "nsf sport": "NSF Sport",
        "nsf certified": "NSF Certified",
        "nsf ansi 173": "NSF Certified",
        "nsf 173": "NSF Certified",
        "usp verified": "USP Verified",
        "usp": "USP Verified",
        "informed sport": "Informed Sport",
        "informed choice": "Informed Choice",
        "ifos": "IFOS",
        "ifos 5 star": "IFOS",
        "non gmo project": "Non-GMO Project",
        "non gmo project verified": "Non-GMO Project",
        "clean label project": "Clean Label Project",
        "friend of the sea": "Friend of the Sea",
        "msc": "MSC",
    }
    return canon.get(t, text.strip())


# --- Matching ---------------------------------------------------------------


def _keyword_overlap(a: str, b: str) -> float:
    """Returns fraction of `a`'s tokens that appear in `b`, after normalization.
    Used for product-line matching where exact name match isn't required but
    keyword overlap is."""
    a_tokens = {t for t in a.split() if len(t) >= 3}
    b_tokens = {t for t in b.split() if len(t) >= 3}
    if not a_tokens:
        return 0.0
    overlap = a_tokens & b_tokens
    return 100.0 * len(overlap) / len(a_tokens)


def _check_override(
    brand_norm: str, product_norm: str, program: str, registry: CertRegistry
) -> CertResolution | None:
    """Manual override always wins. Returns CertResolution or None."""
    program_canon = normalize_program(program)
    # Direct (brand, product) hit
    for key, overrides in registry.overrides_by_brand_product.items():
        ovr_brand, ovr_product = key
        if brand_norm != ovr_brand:
            continue
        # Product is allowed to be empty in override (brand-level override)
        if ovr_product and ovr_product != product_norm:
            continue
        for override in overrides:
            ovr_program = normalize_program(override.get("program", ""))
            if ovr_program and ovr_program != program_canon:
                continue
            status = override.get("status", "verified")
            scope = override.get("scope", "sku")
            if status == "rejected":
                return CertResolution(
                    program=program_canon,
                    scope="claimed_only",
                    notes=f"override rejected: {override.get('reason', '')}",
                )
            if status == "pending_review":
                return CertResolution(
                    program=program_canon,
                    scope="needs_review",
                    record_id=override.get("record_id"),
                    notes="override pending_review",
                )
            # verified
            return CertResolution(
                program=program_canon,
                scope=scope,
                match_confidence=1.0,
                record_id=override.get("record_id"),
                verified_at=override.get("verified_at"),
                source_url=override.get("source_url"),
                notes="curated override",
                matched_brand=override.get("brand"),
                matched_product=override.get("product"),
            )
    return None


def resolve(
    brand: str,
    product: str,
    claimed_programs: Iterable[str],
    registry: CertRegistry,
) -> list[CertResolution]:
    """Resolve every claimed program to its registry scope.

    Conservative — false positives are worse than missed bonuses.
    Returns one CertResolution per claimed program."""

    brand_norm = normalize_brand(brand)
    product_norm = normalize_product(product)
    out: list[CertResolution] = []

    for claimed in claimed_programs:
        program_canon = normalize_program(claimed)
        if not program_canon:
            continue

        # Stage 1: curated override wins
        override_resolution = _check_override(brand_norm, product_norm, program_canon, registry)
        if override_resolution is not None:
            out.append(override_resolution)
            continue

        # Stage 2: registry lookup
        candidates = registry.candidates_for(program_canon)

        # Brand match: try exact normalized first, fall back to fuzzy.
        # Use partial_ratio so "Thorne" matches "Thorne Research" (substring),
        # and require >=88 to keep brand-matching conservative.
        BRAND_FUZZY_FLOOR = 88
        brand_matches: list[dict[str, Any]] = []
        for c in candidates:
            c_brand = normalize_brand(c.get("brand_normalized", c.get("brand", "")))
            if not c_brand:
                continue
            if c_brand == brand_norm:
                brand_matches.append(c)
                continue
            # Fuzzy fallback. partial_ratio handles legal-entity suffixes
            # ("Thorne Research, Inc." → "thorne research" vs "thorne") that
            # token_set_ratio under-scores when one side is a single token.
            partial = fuzz.partial_ratio(brand_norm, c_brand)
            tokenset = fuzz.token_set_ratio(brand_norm, c_brand)
            if max(partial, tokenset) >= BRAND_FUZZY_FLOOR:
                brand_matches.append(c)
        if not brand_matches:
            out.append(CertResolution(program=program_canon, scope="claimed_only"))
            continue

        # Stage 3: product-level matching within brand-matched candidates
        best_sku: tuple[tuple[float, int, int], float, dict[str, Any], bool] | None = None
        best_line: tuple[tuple[float, int, int], float, dict[str, Any], bool] | None = None
        for c in brand_matches:
            raw_candidate_product = c.get("product", "") or c.get("product_normalized", "")
            c_product = normalize_product(c.get("product_normalized", raw_candidate_product))
            if not c_product:
                continue
            variant_conflict = _sku_variant_conflict(product, raw_candidate_product)

            # SKU exact-ish match via token_set_ratio
            ratio = fuzz.token_set_ratio(product_norm, c_product)
            token_delta = abs(len(product_norm.split()) - len(c_product.split()))
            sku_rank = (ratio, 1 if product_norm == c_product else 0, -token_delta)
            if not best_sku or sku_rank > best_sku[0]:
                best_sku = (sku_rank, ratio, c, variant_conflict)

            # Product-line keyword overlap
            overlap = _keyword_overlap(product_norm, c_product)
            line_rank = (overlap, 1 if product_norm == c_product else 0, -token_delta)
            if not best_line or line_rank > best_line[0]:
                best_line = (line_rank, overlap, c, variant_conflict)

        # Apply thresholds
        if best_sku and best_sku[1] >= SKU_RATIO_FLOOR:
            _rank, ratio, c, variant_conflict = best_sku
            if variant_conflict:
                out.append(_record_to_resolution(c, program_canon, "needs_review", ratio / 100.0))
            else:
                out.append(_record_to_resolution(c, program_canon, "sku", ratio / 100.0))
        elif best_sku and best_sku[1] >= SKU_NEEDS_REVIEW_FLOOR:
            _rank, ratio, c, _variant_conflict = best_sku
            out.append(_record_to_resolution(c, program_canon, "needs_review", ratio / 100.0))
        elif best_line and best_line[1] >= PRODUCT_LINE_KEYWORD_OVERLAP_FLOOR:
            _rank, overlap, c, variant_conflict = best_line
            if variant_conflict:
                out.append(_record_to_resolution(c, program_canon, "needs_review", overlap / 100.0))
            else:
                out.append(_record_to_resolution(c, program_canon, "product_line", overlap / 100.0))
        elif best_line and best_line[1] >= PRODUCT_LINE_NEEDS_REVIEW_FLOOR:
            _rank, overlap, c, _variant_conflict = best_line
            out.append(_record_to_resolution(c, program_canon, "needs_review", overlap / 100.0))
        else:
            # Brand was in registry but no product hit
            out.append(
                CertResolution(
                    program=program_canon,
                    scope="brand_only",
                    notes=f"brand has cert but this product not in registry",
                )
            )

    return out


def _record_to_resolution(
    record: dict[str, Any],
    program: str,
    scope: str,
    confidence: float,
) -> CertResolution:
    """Build a CertResolution from a matched registry record.

    Carries recency state from the registry snapshot. If the snapshot is
    scoring_blocked (too stale), set scoring_blocked_reason so production
    scorers refuse to grant points. Audit reports still see the match.
    """
    snapshot_date = record.get("_snapshot_date") or record.get("verified_at")
    snapshot_age_days = record.get("_snapshot_age_days")
    recency_status = record.get("_recency_status", "unknown")

    scoring_blocked_reason: str | None = None
    if recency_status == "scoring_blocked":
        scoring_blocked_reason = (
            f"snapshot is {snapshot_age_days}d old (> {RECENCY_AUDIT_ONLY_DAYS}d audit-only threshold); "
            f"refresh registry before granting B4a points"
        )
    elif recency_status == "unknown":
        scoring_blocked_reason = "snapshot date unknown; refresh registry before granting points"

    return CertResolution(
        program=program,
        scope=scope,
        match_confidence=round(confidence, 3),
        record_id=record.get("record_id"),
        verified_at=record.get("verified_at"),
        source_url=record.get("source_url"),
        matched_brand=record.get("brand") or record.get("brand_normalized"),
        matched_product=record.get("product") or record.get("product_normalized"),
        snapshot_date=snapshot_date,
        snapshot_age_days=snapshot_age_days,
        recency_status=recency_status,
        scoring_blocked_reason=scoring_blocked_reason,
    )


# --- CLI for manual probing -------------------------------------------------


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Resolve a single (brand, product, program) tuple.")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--program", action="append", required=True, help="May be repeated.")
    args = parser.parse_args()

    registry = CertRegistry.load()
    resolutions = resolve(args.brand, args.product, args.program, registry)
    for r in resolutions:
        print(json.dumps(r.to_dict(), indent=2))


if __name__ == "__main__":
    _cli()
