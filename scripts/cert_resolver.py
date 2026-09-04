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
from dataclasses import asdict, dataclass, field, replace
from functools import lru_cache
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


@lru_cache(maxsize=65_536)
def normalize_brand(text: str) -> str:
    if not text:
        return ""
    text = _strip_accents(text).lower().strip()
    text = re.sub(r"[®™©]", " ", text)
    text = _BRAND_NOISE_PATTERN.sub(" ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _brand_tokens(brand_norm: str) -> set[str]:
    """Meaningful normalized brand tokens for registry matching.

    Short substring matches are unsafe for cert registries: e.g. ``LTH`` can
    appear inside ``Health`` and ``VITAL`` can partially match ``vitafusion``.
    Token-set subset matching keeps accepted aliases like ``Thorne`` →
    ``Thorne Research`` without letting unrelated brands inherit SKU certs.
    """
    return {token for token in (brand_norm or "").split() if len(token) >= 2}


def _brands_likely_same(product_brand_norm: str, registry_brand_norm: str) -> bool:
    if not product_brand_norm or not registry_brand_norm:
        return False
    if product_brand_norm == registry_brand_norm:
        return True

    product_tokens = _brand_tokens(product_brand_norm)
    registry_tokens = _brand_tokens(registry_brand_norm)
    if not product_tokens or not registry_tokens:
        return False

    return product_tokens.issubset(registry_tokens) or registry_tokens.issubset(product_tokens)


_SKU_DOSE_TOKEN_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|µg|g|kg|iu|ml|fl\s*oz|oz|"
    r"(?:billion|b)(?:\s*(?:cfus?|afu))?|cfus?|afu)\b\.?",
    re.IGNORECASE,
)

_SKU_FORM_TOKENS = {
    "capsule": "capsule", "capsules": "capsule",
    "caplet": "caplet", "caplets": "caplet",
    "tablet": "tablet", "tablets": "tablet",
    "softgel": "softgel", "softgels": "softgel",
    "gummy": "gummy", "gummies": "gummy",
    "chewable": "chewable", "chewables": "chewable",
    "powder": "powder", "liquid": "liquid", "drops": "drops",
}
_SKU_NET_CONTENTS_FORM_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?\s+)?(?:once\s+daily\s+)?"
    r"(?:(?P<material>vegetarian|vegan|gelatin)\s+)?"
    r"(?P<form>" + "|".join(_SKU_FORM_TOKENS) + r")(?:\(s\))?",
    re.IGNORECASE,
)

_SKU_SEX_TOKENS = {
    "men": "male", "mens": "male", "man": "male", "male": "male", "him": "male",
    "women": "female", "womens": "female", "woman": "female", "female": "female", "her": "female",
    "boy": "male", "boys": "male", "girl": "female", "girls": "female",
}
_SKU_LIFE_STAGE_TOKENS = {
    "prenatal": "prenatal", "pregnancy": "prenatal", "pregnant": "prenatal",
    "postnatal": "postnatal", "postpartum": "postnatal",
    "kid": "child", "kids": "child", "child": "child", "children": "child",
    "teen": "teen", "teens": "teen", "teenager": "teen", "adolescent": "teen",
    "adult": "adult", "adults": "adult",
    "baby": "infant", "babies": "infant", "infant": "infant", "infants": "infant",
    "toddler": "toddler", "toddlers": "toddler",
    "senior": "senior", "seniors": "senior",
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

_MARINE_CERT_PROGRAMS = {"IFOS", "IKOS", "IAOS"}
_MARINE_PRODUCT_RE = re.compile(
    r"\b("
    r"omega\s*3|omega[-\s]?3|fish\s*oil|krill\s*oil|algae\s*oil|algal\s*oil|"
    r"epa|dha|docosahexaenoic|eicosapentaenoic|marine\s*oil"
    r")\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=65_536)
def normalize_product(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[®™©]", " ", text)
    text = re.sub(r"(?<=\w)['’]s\b", "", text, flags=re.IGNORECASE)
    text = _strip_accents(text).lower().strip()
    # Strip dose-number+unit pairs first (e.g., "200 mg", "5000 IU") so the
    # leading numeric doesn't survive into the noise-stripped output.
    text = _SKU_DOSE_TOKEN_PATTERN.sub(" ", text)
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
        # Registry shorthand 50B and label 50 billion CFU identify the same
        # strength. AFU remains a distinct measurement; never infer CFU from it.
        if unit_norm in {"b", "billion", "bcfu", "bcfus", "billioncfu", "billioncfus"}:
            unit_norm = "billioncfu"
        elif unit_norm in {"bafu", "billionafu"}:
            unit_norm = "billionafu"
        elif unit_norm == "cfus":
            unit_norm = "cfu"
        tokens.add(f"{value.rstrip('0').rstrip('.') if '.' in value else value}{unit_norm}")
    return tokens


def _sku_form_tokens(text: str) -> set[str]:
    if not text:
        return set()
    normalized = _strip_accents(text).lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return {_SKU_FORM_TOKENS[token] for token in normalized.split() if token in _SKU_FORM_TOKENS}


def _with_label_form_context(product: str, context: dict[str, Any] | None) -> str:
    """Add only explicit form evidence, never marketing or serving instructions.

    A narrowly parsed net-contents unit may carry a material qualifier such as
    Vegetarian Capsule(s). Counts and the printed Once Daily prefix are not
    product identity. Unsupported descriptors stay unresolved, not guessed.
    """
    context = context if isinstance(context, dict) else {}
    parts = [product]
    form = context.get("form_factor_canonical") or context.get("form_factor")
    if isinstance(form, str) and form.lower().strip() in _SKU_FORM_TOKENS:
        parts.append(_SKU_FORM_TOKENS[form.lower().strip()])
    contents = context.get("netContents")
    for row in contents if isinstance(contents, list) else []:
        unit = row.get("unit") if isinstance(row, dict) else None
        if not isinstance(unit, str):
            continue
        # DSLD prints both of these plural templates on gummy package units.
        # Still require the entire resulting unit to match the narrow grammar.
        unit = re.sub(r"\bgumm(?:ie\(s\)|y\(ies\))$", "gummies", unit.strip(), flags=re.IGNORECASE)
        match = _SKU_NET_CONTENTS_FORM_PATTERN.fullmatch(unit)
        if match:
            if match["material"]:
                parts.append(match["material"].lower())
            parts.append(_SKU_FORM_TOKENS[match["form"].lower()])
    return " ".join(parts)


@lru_cache(maxsize=65_536)
def _sku_population_tokens(text: str) -> tuple[frozenset[str], ...]:
    """Explicit label population qualifiers, kept separate from fuzzy name text.

    Age labels identify formulations, not overlapping patient eligibility:
    an 18+ listing does not certify a different 50+ formulation.
    """
    normalized = _strip_accents(text or "").lower()
    words = set(re.findall(r"[a-z]+", normalized))
    sexes = frozenset(_SKU_SEX_TOKENS[w] for w in words if w in _SKU_SEX_TOKENS)
    stages = frozenset(_SKU_LIFE_STAGE_TOKENS[w] for w in words if w in _SKU_LIFE_STAGE_TOKENS)
    ages = set()
    for lower in re.findall(r"\b(\d{1,2})\s*(?:\+|plus\b|(?:and\s+)?(?:older|over|up)\b)", normalized):
        ages.add(f"{int(lower)}+")
    for lower, upper in re.findall(r"\bages?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\b", normalized):
        ages.add(f"{int(lower)}-{int(upper)}")
    return sexes, stages, frozenset(ages)


def _sku_population_conflict(product: str, candidate: str) -> bool:
    for requested, certified in zip(_sku_population_tokens(product), _sku_population_tokens(candidate)):
        # A population-specific registry row cannot establish identity for an
        # unspecified label. A generic row may cover a more specific member;
        # explicit combined lines (prenatal + postnatal) can cover either member.
        if certified and (not requested or not requested.issubset(certified)):
            return True
    return False


def _sku_identity_tokens(text: str, brand_tokens: set[str]) -> frozenset[str]:
    """Name identity after the existing population/strength/form guards.

    Only descriptors and already-validated population language are removed.
    Material qualifiers (immune, herbal, named additions) remain required.
    """
    normalized = normalize_product(text)
    tokens = set(normalized.split()) - brand_tokens
    # Form identity is checked separately before these name tokens qualify.
    # In particular, caplet/caplets must not become different name qualifiers;
    # keep normalize_product unchanged because it also indexes reviewed overrides.
    tokens -= _SKU_FORM_TOKENS.keys()
    tokens -= {"for", "and", "with", "formula", "multivitamin"}
    tokens -= _SKU_SEX_TOKENS.keys()
    tokens -= _SKU_LIFE_STAGE_TOKENS.keys()
    _, _, ages = _sku_population_tokens(text)
    if ages:
        tokens -= {"age", "ages", "up", "older", "over", "plus"}
        tokens -= {number for age in ages for number in re.findall(r"\d+", age)}
    if any(re.fullmatch(r"[abcdek]\d*", token) for token in tokens):
        tokens.discard("vitamin")
    return frozenset(tokens)


def _literal_product_name(text: str, registry_brand: str) -> str:
    """Keep the whole normalized name, removing only a leading registry brand.

    Population and descriptor words can comprise the literal product name.
    Do not turn their removal from broad identity tokens into an empty match.
    Raw strength/form/population guards remain required at the call site.
    """
    name = normalize_product(text)
    brand = normalize_product(normalize_brand(registry_brand))
    if name == brand:
        return ""
    if brand and name.startswith(brand + " "):
        name = name[len(brand) + 1:]
    return name


def _sku_flavor_tokens(text: str) -> set[str]:
    if not text:
        return set()
    normalized = _strip_accents(text).lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return {token for token in normalized.split() if token in _SKU_FLAVOR_TOKENS}


def _sku_query_flavor_tokens(text: str) -> set[str]:
    """Existing flavor refinements, not arbitrary named product editions."""
    tokens = _sku_flavor_tokens(text)
    if not tokens:
        return tokens
    tokens.update({"flavor", "flavored", "flavour", "flavoured", "flavors", "flavours"})
    normalized = normalize_product(text)
    for phrase in ("strawberry lemonade", "chocolate fudge", "berry fresh"):
        if re.search(rf"\b{phrase}\b", normalized):
            tokens.update(phrase.split())
    return tokens


def _sku_flavor_only_match(product: str, candidate: str, brand_tokens: set[str]) -> bool:
    """A named flavor is not evidence for the underlying certified product.

    For example, fruit powder must not inherit a flavored creatine listing.
    Only explicit flavor descriptions trigger this guard: fruit names can
    also identify actual ingredients, not merely flavors.
    """
    normalized = _strip_accents(candidate).lower()
    if not re.search(r"\bflavou?r(?:ed)?\b", normalized):
        return False
    descriptors = brand_tokens | {"flavor", "flavored", "flavour", "flavoured"}
    product_tokens = set(normalize_product(product).split()) - descriptors
    candidate_tokens = set(normalize_product(candidate).split()) - descriptors
    if product_tokens == candidate_tokens:
        return False
    flavor_tokens = _sku_flavor_tokens(candidate)
    # Preserve multi-word descriptions when a delivery-form word separates
    # them from the product identity ("powder sour green apple flavored").
    forms = "|".join(_SKU_FORM_TOKENS)
    for description in re.findall(rf"\b(?:{forms})\b\s+(.+?)\s+flavou?r(?:ed)?\b", normalized):
        flavor_tokens.update(normalize_product(description).split())
    # Registry names may omit the form: "creatine pear flavored".
    flavor_tokens.update(re.findall(r"\b([a-z]+)\s+flavou?r(?:ed)?\b", normalized))
    return bool(flavor_tokens) and (product_tokens & candidate_tokens).issubset(flavor_tokens)


def _sku_named_addition_conflict(product: str, candidate: str, brand_tokens: set[str]) -> bool:
    """Keep explicit additions/editions such as B12 + Folate or CBD+ Focus.

    The '+' need not appear on the queried label, but the named addition must.
    Age suffixes such as 50+ are handled by the population guard instead.
    """
    product_tokens = set(normalize_product(product).split()) - brand_tokens
    for plus in re.finditer(r"\+", candidate):
        if re.search(r"\b\d{1,2}\s*$", candidate[:plus.start()]):
            continue
        # Strip trademarks before Unicode folding can turn ™ into the letters
        # "TM"; that annotation is not a named ingredient or product edition.
        suffix = re.sub(r"[®™©]", " ", candidate[plus.end():])
        addition = {
            token for token in normalize_product(suffix).split()
            if any(char.isalpha() for char in token)
        } - brand_tokens
        if addition and not addition.issubset(product_tokens):
            return True
    return False


def _program_requires_marine_context(program: str) -> bool:
    return normalize_program(program) in _MARINE_CERT_PROGRAMS


def _has_marine_product_context(text: str) -> bool:
    return bool(_MARINE_PRODUCT_RE.search(text or ""))


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


def _sku_variant_conflict(
    product_a: str,
    product_b: str,
    *,
    brand_a: str = "",
    brand_b: str = "",
) -> bool:
    """True when identity qualifiers make a high-ratio match unsafe to auto-SKU.

    Normalization intentionally strips dose and form words for broad product
    matching, but certification verification is SKU-sensitive. A 100 mg softgel
    listing should not score a 200 mg softgel claim, and a gummies listing
    should not score a softgel claim without reviewer confirmation.
    """
    # Never short-circuit on normalize_product equality: that deliberately
    # erases strength and form, which are certification identity constraints.
    # Population qualifiers may live in a label's sub-brand (Kids First,
    # Garden of Life Baby). Use that context only for population, not flavor
    # or strength, which must come from the product itself.
    if _sku_population_conflict(f"{brand_a} {product_a}", f"{brand_b} {product_b}"):
        return True
    brand_tokens = set(normalize_product(f"{brand_a} {brand_b}").split())
    if _sku_flavor_only_match(product_a, product_b, brand_tokens):
        return True
    if _sku_named_addition_conflict(product_a, product_b, brand_tokens):
        return True

    doses_a = _sku_dose_tokens(product_a)
    doses_b = _sku_dose_tokens(product_b)
    if doses_b and doses_a != doses_b:
        return True

    forms_a = _sku_form_tokens(product_a)
    forms_b = _sku_form_tokens(product_b)
    if forms_b and (not forms_a or not forms_a.issubset(forms_b)):
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


@lru_cache(maxsize=1_024)
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
        "nsf contents certified": "NSF Certified",
        "nsf certified": "NSF Certified",
        "nsf ansi 173": "NSF Certified",
        "nsf 173": "NSF Certified",
        "nsf ansi 455": "NSF/ANSI 455",
        "nsf ansi 455 2": "NSF/ANSI 455",
        "nsf 455": "NSF/ANSI 455",
        "nsf gmp": "NSF/ANSI 455",
        "nsf gmp registered": "NSF/ANSI 455",
        "usp verified": "USP Verified",
        "usp": "USP Verified",
        "informed sport": "Informed Sport",
        "informed choice": "Informed Choice",
        "ifos": "IFOS",
        "ifos 5 star": "IFOS",
        "consumerlab": "ConsumerLab",
        "consumerlab approved": "ConsumerLab",
        "consumerlab tested": "ConsumerLab",
        "consumerlab com approved": "ConsumerLab",
        "consumer lab": "ConsumerLab",
        "consumer lab approved": "ConsumerLab",
        "cl approved": "ConsumerLab",
        "bscg": "BSCG",
        "bscg certified drug free": "BSCG",
        "certified drug free": "BSCG",
        "banned substances control group": "BSCG",
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
    brand_norm: str,
    product_norm: str,
    program: str,
    registry: CertRegistry,
    dsld_id: str | None = None,
    *,
    product: str,
) -> CertResolution | None:
    """Apply a curated override only to its reviewed raw product identity."""
    program_canon = normalize_program(program)
    request_dsld_id = str(dsld_id or "").strip()
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
            override_dsld_id = str(override.get("dsld_id") or "").strip()
            if override_dsld_id and override_dsld_id != request_dsld_id:
                continue
            # An override reviews one raw product (or an explicit whole brand),
            # not every strength/form collapsed into its normalized index key.
            # Compare to the reviewed product, not matched_product: a reviewed
            # product-line mapping may legitimately carry extra dose detail.
            if override.get("product") and _sku_variant_conflict(
                product, override["product"], brand_a=brand_norm, brand_b=override.get("brand", "")
            ):
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
            if scope in {"sku", "product_line"} and override.get("matched_product"):
                if _sku_population_conflict(
                    f"{brand_norm} {product}",
                    f"{override.get('matched_brand', '')} {override['matched_product']}",
                ):
                    return CertResolution(
                        program=program_canon,
                        scope="needs_review",
                        record_id=override.get("record_id"),
                        notes="curated override population conflict",
                        matched_brand=override.get("matched_brand"),
                        matched_product=override["matched_product"],
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
                matched_brand=override.get("matched_brand") or override.get("brand"),
                matched_product=override.get("matched_product") or override.get("product"),
            )
    return None


def resolve(
    brand: str,
    product: str,
    claimed_programs: Iterable[str],
    registry: CertRegistry,
    dsld_id: str | None = None,
    *,
    label_context: dict[str, Any] | None = None,
) -> list[CertResolution]:
    """Resolve every claimed program to its registry scope.

    Conservative — false positives are worse than missed bonuses.
    Returns one CertResolution per claimed program."""

    brand_norm = normalize_brand(brand)
    reviewed_product_norm = normalize_product(product)
    identity_product = _with_label_form_context(product, label_context)
    product_norm = normalize_product(identity_product)
    query_flavor_tokens = _sku_query_flavor_tokens(product)
    out: list[CertResolution] = []

    for claimed in claimed_programs:
        program_canon = normalize_program(claimed)
        if not program_canon:
            continue

        # Stage 1: curated override wins
        override_resolution = _check_override(
            brand_norm,
            reviewed_product_norm,
            program_canon,
            registry,
            dsld_id=dsld_id,
            product=identity_product,
        )
        if override_resolution is not None:
            out.append(override_resolution)
            continue

        # Stage 2: registry lookup
        candidates = registry.candidates_for(program_canon)

        # Brand match is token-subset conservative. Do not use fuzzy substring
        # matching here: false-positive registry certs are worse than missed
        # bonuses, and short brands like LTH/VITAL collide with unrelated names.
        brand_matches: list[dict[str, Any]] = []
        for c in candidates:
            c_brand = normalize_brand(c.get("brand_normalized", c.get("brand", "")))
            if _brands_likely_same(brand_norm, c_brand):
                brand_matches.append(c)
        if not brand_matches:
            out.append(CertResolution(program=program_canon, scope="claimed_only"))
            continue

        if _program_requires_marine_context(program_canon) and not _has_marine_product_context(product):
            out.append(
                CertResolution(
                    program=program_canon,
                    scope="claimed_only",
                    notes="marine certification requires omega/fatty-acid product context",
                )
            )
            continue

        # Stage 3: product-level matching within brand-matched candidates
        best_sku: tuple[tuple[bool, float, int, int], float, dict[str, Any], bool] | None = None
        best_line: tuple[tuple[bool, float, int, int], float, dict[str, Any], bool] | None = None
        qualifying_identities: set[tuple[frozenset[str], ...]] = set()
        exact_identities: set[tuple[frozenset[str], ...]] = set()
        qualifying_records = []
        for c in brand_matches:
            raw_candidate_product = c.get("product", "") or c.get("product_normalized", "")
            raw_candidate_product = _with_label_form_context(
                raw_candidate_product, {"form_factor": c.get("product_form")}
            )
            c_product = normalize_product(c.get("product_normalized", raw_candidate_product))
            if not c_product:
                continue
            variant_conflict = _sku_variant_conflict(
                identity_product, raw_candidate_product, brand_a=brand,
                brand_b=c.get("brand", c.get("brand_normalized", "")),
            )
            brand_tokens = set(normalize_product(
                f"{brand} {c.get('brand', c.get('brand_normalized', ''))}"
            ).split())
            product_tokens = _sku_identity_tokens(identity_product, brand_tokens)
            candidate_tokens = _sku_identity_tokens(raw_candidate_product, brand_tokens)
            registry_brand = c.get("brand", c.get("brand_normalized", ""))
            literal_product = _literal_product_name(product, registry_brand)
            literal_candidate = _literal_product_name(raw_candidate_product, registry_brand)
            literal_identity = bool(literal_product) and literal_product == literal_candidate
            exact_identity = literal_identity or (bool(product_tokens) and product_tokens == candidate_tokens)
            # A registry-specific qualifier may not disappear just because
            # token_set_ratio calls a subset 100 (Daily Probiotics -> Daily
            # Immune Probiotics). Extra query detail may refine a listed line;
            # a missing registry qualifier requires an explicit reviewed alias.
            insufficient_identity = not exact_identity and (
                not candidate_tokens.issubset(product_tokens)
                or len(product_tokens & candidate_tokens) < 2
            )
            # Query-side named additions also identify distinct SKUs. Use the
            # raw title, not appended form evidence, and remove only registry
            # brand tokens so a query sub-brand cannot hide its own edition.
            registry_brand_tokens = set(normalize_product(registry_brand).split())
            query_additions = (
                _sku_identity_tokens(product, registry_brand_tokens)
                - _sku_identity_tokens(raw_candidate_product, registry_brand_tokens)
                - query_flavor_tokens
            )
            unsupported_edition = bool(query_additions) and c.get("scope") != "product_line"
            variant_conflict = variant_conflict or insufficient_identity or unsupported_edition

            # SKU exact-ish match via token_set_ratio
            ratio = fuzz.token_set_ratio(product_norm, c_product)
            token_delta = abs(len(product_norm.split()) - len(c_product.split()))
            if not variant_conflict:
                # Once all registry qualifiers are present and the raw
                # strength/form/population guards pass, compare the validated
                # product identity. Embedded registry brand text and extra
                # source-backed form detail must not dilute that match.
                ratio = 100.0 if literal_identity else fuzz.token_set_ratio(
                    " ".join(sorted(product_tokens)), " ".join(sorted(candidate_tokens))
                )
                token_delta = abs(len(product_tokens) - len(candidate_tokens))
            # A compatible qualifying record must win over a conflicting row
            # whose strength/form disappeared during normalization. If none
            # qualifies, retain the best fuzzy candidate for review as before.
            sku_rank = (
                not variant_conflict and ratio >= SKU_RATIO_FLOOR,
                ratio, int(exact_identity), -token_delta,
            )
            if not best_sku or sku_rank > best_sku[0]:
                best_sku = (sku_rank, ratio, c, variant_conflict)

            # Product-line keyword overlap
            overlap = _keyword_overlap(product_norm, c_product)
            line_rank = (
                not variant_conflict and overlap >= PRODUCT_LINE_KEYWORD_OVERLAP_FLOOR,
                overlap, int(exact_identity), -token_delta,
            )
            if not best_line or line_rank > best_line[0]:
                best_line = (line_rank, overlap, c, variant_conflict)
            if not variant_conflict and (
                ratio >= SKU_RATIO_FLOOR or overlap >= PRODUCT_LINE_KEYWORD_OVERLAP_FLOOR
            ):
                identity = (
                    candidate_tokens,
                    frozenset(_sku_dose_tokens(raw_candidate_product)),
                    frozenset(_sku_form_tokens(raw_candidate_product)),
                    *_sku_population_tokens(raw_candidate_product),
                )
                qualifying_identities.add(identity)
                qualifying_records.append(c)
                if exact_identity:
                    exact_identities.add(identity)

        # Duplicate registry rows for one identity are harmless; distinct
        # plausible variants require review, not a choice based on row order.
        if len(exact_identities or qualifying_identities) > 1:
            # Keep a deterministic representative plus the candidate IDs for
            # existing review tooling; no candidate receives scoring authority.
            candidates = sorted(qualifying_records, key=lambda row: (str(row.get("record_id") or ""), str(row.get("product") or "")))
            resolution = _record_to_resolution(candidates[0], program_canon, "needs_review", 0.0)
            out.append(replace(resolution, notes="ambiguous registry product variants: " + ", ".join(
                str(row.get("record_id") or row.get("product")) for row in candidates)))
            continue

        # Apply thresholds
        if best_sku and best_sku[1] >= SKU_RATIO_FLOOR:
            _rank, ratio, c, variant_conflict = best_sku
            if variant_conflict:
                out.append(_record_to_resolution(c, program_canon, "needs_review", ratio / 100.0))
            else:
                scope = "product_line" if c.get("scope") == "product_line" else "sku"
                out.append(_record_to_resolution(c, program_canon, scope, ratio / 100.0))
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


def discover_verified_programs(
    brand: str,
    product: str,
    registry: CertRegistry,
    dsld_id: str | None = None,
    *,
    label_context: dict[str, Any] | None = None,
) -> list[CertResolution]:
    """Discover direct SKU/product-line certs from loaded registries.

    `resolve()` is claim-driven: it answers "does this claimed program match
    the registry?" For scoring reachability we also need the inverse when a
    public registry lists the product but the label text does not repeat the
    program name. Only SKU/product-line matches are returned; brand-only,
    claimed-only, and needs-review results remain non-scoring.
    """
    discovered: list[CertResolution] = []
    for program in sorted(registry.records_by_program):
        for resolution in resolve(brand, product, [program], registry, dsld_id=dsld_id,
                                  label_context=label_context):
            if resolution.scope not in {"sku", "product_line"}:
                continue
            note = "registry_discovered_product_match"
            if resolution.notes:
                note = f"{resolution.notes}; {note}"
            discovered.append(replace(resolution, notes=note))
    return discovered


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
