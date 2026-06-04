"""V4 Phase 6 — Botanical Profile (formulation + dose adapters).

Botanicals are not vitamins. The generic A1/A2 (bio_score / premium forms) and
the RDA/UL dose proxy structurally disadvantage herbs. This profile replaces
both for botanical products:

  Formulation adapter (replaces A1/A2, max 15):
    recognized botanical identity        +6
    plant part disclosed                 +2
    quantified dose present              +2
    extract (not whole-herb powder)      +2
    marker standardization declared      +4
    branded clinically-studied extract   +3
    weak / unidentified botanical        -4   (replaces the +6 identity credit)

  Dose adapter (replaces RDA/UL proxy), via rda_therapeutic_dosing.json:
    within studied range   -> 21
    near studied range     -> 16
    below studied range    -> 10
    disclosed, no reference-> 10
    blend total only       -> 7
    primary, no dose       -> 0  (NOT denominator exclusion)

The A5b standardized-botanical bonus is DISABLED inside the profile (marker
standardization is now core formulation, not a duplicate +1 bonus). Botanical
safety cautions are surfaced via confidence; they never override the safety gate.

Spec: docs/superpowers/specs/2026-06-01-v4-botanical-profile-design.md
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

BOTANICAL_FORMULATION_CAP = 15.0

# Roles that mark an active as the product's marketed hero (Phase 2 classifier).
# Used by the route-drift fix so a mass-heavy botanical *adjunct* can't hijack a
# product whose primary/claim-prominent active is non-botanical.
_PRIMARY_ROLES = frozenset({"primary", "claim_prominent"})
_ROLE_STRENGTH = {
    "primary": 3,
    "claim_prominent": 3,
    "major": 2,
    "adjunct": 1,
}

# A title-prominent botanical can promote a mixed product into the botanical
# profile only when it is still a material component. This prevents "Papaya
# Enzyme" style products from scoring off a trace botanical theme while larger
# enzyme/mineral/vitamin actives carry the dose.
_BOTANICAL_PROMOTION_MATERIALITY_FRACTION = 0.5
_ENZYME_TITLE_RE = re.compile(r"\b(enzyme|enzymes|digestive)\b", re.IGNORECASE)
_ENZYME_CANONICALS = frozenset({
    "digestive_enzymes",
    "alpha_amylase",
    "amylase",
    "bromelain",
    "papain",
    "protease",
    "lipase",
    "cellulase",
    "lactase",
})
_NON_BOTANICAL_ACTIVE_CATEGORIES = frozenset({
    "amino_acids",
    "fatty_acids",
    "omega_fatty_acids",
    "enzymes",
    "enzyme",
    "digestive_enzyme",
})
_NON_BOTANICAL_RAW_CATEGORIES = frozenset({
    "amino acid",
    "fat",
    "enzyme",
})
_BOTANICAL_SOURCE_FORM_CATEGORIES = frozenset({"botanical", "herb"})

_PLANT_PARTS = (
    "root", "leaf", "leaves", "bark", "flower", "seed", "fruit", "berry",
    "rhizome", "aerial", "bulb", "stem", "rind", "peel", "whole herb", "herb",
    "needle", "resin", "gum", "hull", "shell", "pod",
)
_EXTRACT_TOKENS = ("extract", "extracted", "concentrate", "standardized")
_WHOLE_HERB_TOKENS = ("powder", "whole herb", "whole-herb", "dried herb", "cut")


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _primary_type(product: Dict[str, Any]) -> str:
    ptype = (product or {}).get("primary_type")
    if not (isinstance(ptype, str) and ptype.strip()):
        tax = (product or {}).get("supplement_taxonomy")
        ptype = tax.get("primary_type") if isinstance(tax, dict) else None
    return _norm(ptype)


# --- reference data (loaded + indexed once) --------------------------------

@lru_cache(maxsize=1)
def _dosing_index() -> Dict[str, Dict[str, Any]]:
    """name/alias -> therapeutic dosing entry (typical_dosing_range etc.)."""
    try:
        raw = json.loads((_DATA_DIR / "rda_therapeutic_dosing.json").read_text())
    except Exception:  # pragma: no cover
        return {}
    index: Dict[str, Dict[str, Any]] = {}
    for entry in raw.get("therapeutic_dosing", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                index.setdefault(k, entry)
    return index


@lru_cache(maxsize=1)
def _botanical_identity_set() -> frozenset:
    try:
        raw = json.loads((_DATA_DIR / "botanical_ingredients.json").read_text())
    except Exception:  # pragma: no cover
        return frozenset()
    names = set()
    for entry in raw.get("botanical_ingredients", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                names.add(k)
    return frozenset(names)


@lru_cache(maxsize=1)
def _standardized_botanical_identity_set() -> frozenset:
    """Canonical ids/names/aliases for standardized botanical extracts.

    These entries often represent marker compounds or branded extracts
    (curcumin, Meriva, BCM-95) that are botanical-derived but may arrive from
    enrichment with a chemical/non-botanical taxonomy category. They still need
    the botanical formulation and therapeutic-dose adapters.
    """
    try:
        raw = json.loads((_DATA_DIR / "standardized_botanicals.json").read_text())
    except Exception:  # pragma: no cover
        return frozenset()
    names = set()
    for entry in raw.get("standardized_botanicals", []):
        if not isinstance(entry, dict):
            continue
        for key in [entry.get("id"), entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                names.add(k)
    return frozenset(names)


def _known_botanical_identity_set() -> frozenset:
    return _botanical_identity_set() | _standardized_botanical_identity_set()


@lru_cache(maxsize=1)
def _branded_studied_set() -> frozenset:
    """Normalised names/aliases of branded clinically-studied extracts
    (backed_clinical_studies entries flagged branded / id BRAND_*)."""
    try:
        raw = json.loads((_DATA_DIR / "backed_clinical_studies.json").read_text())
    except Exception:  # pragma: no cover
        return frozenset()
    entries = raw if isinstance(raw, list) else [v for k, v in raw.items() if k != "_metadata"]
    if len(entries) == 1 and isinstance(entries[0], list):
        entries = entries[0]
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        is_branded = (
            "branded" in _norm(entry.get("evidence_level"))
            or _norm(entry.get("id")).startswith("brand_")
        )
        if not is_branded:
            continue
        for key in [entry.get("standard_name")] + list(entry.get("aliases") or []):
            k = _norm(key)
            if k:
                names.add(k)
    return frozenset(names)


# --- ingredient helpers ----------------------------------------------------

def _scoring_actives(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        from scoring_input_contract import build_scoring_classification, get_scoring_ingredients
        result = get_scoring_ingredients(product, strict=True)
        if result.rows:
            rows = [dict(r) for r in result.rows if isinstance(r, dict)]
            try:
                contract = build_scoring_classification(product)
                contracts_by_key: Dict[tuple, Dict[str, Any]] = {}
                contracts_by_unique_ref: Dict[str, Dict[str, Any]] = {}
                duplicate_refs = set()
                for item in contract.get("ingredients", []):
                    if not isinstance(item, dict):
                        continue
                    row_ref = str(item.get("row_ref") or "")
                    key = (
                        row_ref,
                        _norm(item.get("canonical_id")),
                        _norm(item.get("name")),
                    )
                    contracts_by_key[key] = item
                    if row_ref in contracts_by_unique_ref:
                        duplicate_refs.add(row_ref)
                    else:
                        contracts_by_unique_ref[row_ref] = item
                for row_ref in duplicate_refs:
                    contracts_by_unique_ref.pop(row_ref, None)
                for index, row in enumerate(rows):
                    row_ref = str(row.get("raw_source_path") or row.get("source") or f"scoring_row:{index}")
                    row_contract = contracts_by_key.get((
                        row_ref,
                        _norm(row.get("canonical_id")),
                        _norm(row.get("name")),
                    ))
                    if row_contract is None:
                        row_contract = contracts_by_unique_ref.get(row_ref)
                    if isinstance(row_contract, dict):
                        row["_scoring_classification"] = row_contract
            except Exception:  # pragma: no cover - profile scoring still has legacy fallback
                pass
            return rows
    except Exception:  # pragma: no cover - legacy fixture fallback
        pass
    iqd = (product or {}).get("ingredient_quality_data") or {}
    rows = iqd.get("ingredients_scorable") or iqd.get("ingredients") or []
    return [r for r in rows if isinstance(r, dict)]


def _classification_profile_eligible(row: Dict[str, Any], profile: str) -> Optional[bool]:
    row_contract = row.get("_scoring_classification")
    if not isinstance(row_contract, dict):
        return None
    profiles = row_contract.get("profile_eligibility")
    if not isinstance(profiles, dict):
        return None
    payload = profiles.get(profile)
    if not isinstance(payload, dict):
        return None
    return payload.get("eligible") is True


def _classification_product_profile_eligible(product: Dict[str, Any], profile: str) -> Optional[bool]:
    try:
        from scoring_input_contract import build_scoring_classification
        contract = build_scoring_classification(product)
    except Exception:  # pragma: no cover - legacy fallback below owns failures
        return None
    profiles = contract.get("profile_eligibility")
    if not isinstance(profiles, dict):
        return None
    payload = profiles.get(profile)
    if not isinstance(payload, dict):
        return None
    return payload.get("eligible") is True


def _is_botanical_active(row: Dict[str, Any]) -> bool:
    contract_eligible = _classification_profile_eligible(row, "botanical")
    if contract_eligible is not None:
        return contract_eligible
    tax = row.get("raw_taxonomy") if isinstance(row.get("raw_taxonomy"), dict) else {}
    category = _norm(row.get("category"))
    category_key = category.replace("-", "_").replace(" ", "_")
    raw_category = _norm(tax.get("category"))
    if category_key in _NON_BOTANICAL_ACTIVE_CATEGORIES or raw_category in _NON_BOTANICAL_RAW_CATEGORIES:
        return False
    raw_forms = tax.get("forms") if isinstance(tax.get("forms"), list) else []
    has_botanical_source_form = any(
        isinstance(form, dict) and _norm(form.get("category")) in _BOTANICAL_SOURCE_FORM_CATEGORIES
        for form in raw_forms
    )
    if category_key == "antioxidants" and raw_category != "botanical" and not has_botanical_source_form:
        return False
    if _norm(tax.get("category")) == "botanical" or _norm(row.get("category")) == "botanical":
        return True
    names = {_norm(row.get("canonical_id")), _norm(row.get("standard_name")), _norm(row.get("name"))}
    return bool(names & _known_botanical_identity_set())


def _forms_text(row: Dict[str, Any]) -> str:
    tax = row.get("raw_taxonomy") if isinstance(row.get("raw_taxonomy"), dict) else {}
    pieces = [row.get("matched_form"), row.get("name"), row.get("standard_name")]
    for form in (tax.get("forms") or []) + (row.get("forms") or []):
        if isinstance(form, dict):
            pieces.append(form.get("name"))
        else:
            pieces.append(form)
    return " ".join(_norm(p) for p in pieces if p)


def _ingredient_identity_keys(row: Dict[str, Any]) -> List[str]:
    return [k for k in (_norm(row.get("canonical_id")), _norm(row.get("standard_name")),
                        _norm(row.get("name")), _norm(row.get("matched_form"))) if k]


def _mass_mg(row: Dict[str, Any]) -> Optional[float]:
    qty = _as_float(row.get("quantity"))
    if qty is None or qty <= 0:
        return None
    # Normalize the unit: lowercase, drop spaces and the "(s)" plural marker DSLD
    # uses ("Gram(s)" is the catalog's standard gram spelling — 1906 rows — and
    # must convert to mg, not fall through to the assume-mg branch).
    unit = _norm(row.get("unit") or row.get("unit_normalized")).replace(" ", "")
    unit = unit.replace("(s)", "s")
    if not unit:
        return qty  # botanicals often omit units; default those to mg.
    if unit in {"mg", "milligram", "milligrams"}:
        return qty
    if unit in {"g", "gram", "grams"}:
        return qty * 1000.0
    if unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms"}:
        return qty / 1000.0
    return None


def _primary_botanical_active(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    botanicals = [r for r in _scoring_actives(product) if _is_botanical_active(r)]
    if not botanicals:
        return None
    # highest comparable mass wins; fall back to first
    return max(botanicals, key=lambda r: (_mass_mg(r) or 0.0))


def _role_by_identity(product: Dict[str, Any]) -> Dict[str, str]:
    """Map each scoring active's identity (canonical_id, then name) -> role.

    Lazy import keeps the dependency one-directional at load time (the Phase 2
    role classifier lazy-imports router constants itself); a classifier failure
    degrades gracefully to "no roles" so the legacy mass rule still applies.
    """
    try:
        from scoring_input_contract import classify_ingredient_roles
        roles = classify_ingredient_roles(product)
    except Exception:  # pragma: no cover - defensive: fall back to mass rule
        return {}
    out: Dict[str, str] = {}

    def keep_strongest(key: str, role: Any) -> None:
        if not key or not isinstance(role, str):
            return
        current = out.get(key)
        if current is None or _ROLE_STRENGTH.get(role, 0) > _ROLE_STRENGTH.get(current, 0):
            out[key] = role

    for r in roles:
        if not isinstance(r, dict):
            continue
        role = r.get("role")
        cid = _norm(r.get("canonical_id"))
        name = _norm(r.get("name"))
        keep_strongest(cid, role)
        keep_strongest(name, role)
    return out


def _role_of(row: Dict[str, Any], role_map: Dict[str, str]) -> Optional[str]:
    return role_map.get(_norm(row.get("canonical_id"))) or role_map.get(_norm(row.get("name")))


# Title separators that split a compound product name into head ("the product")
# and tail ("with X"). The head segment names the active the product is selling.
_TITLE_SEPARATORS = (" with ", " plus ", " and ", " featuring ", " + ", " & ", "+", "&")


def _title_head_boundary(title: str) -> int:
    """Char index where the title head ends (first separator), or len(title)."""
    boundary = len(title)
    for sep in _TITLE_SEPARATORS:
        i = title.find(sep)
        if i != -1:
            boundary = min(boundary, i)
    return boundary


def _row_title_pos(row: Dict[str, Any], title: str) -> Optional[int]:
    """Earliest char index at which a recognizable token of ``row`` appears in
    ``title`` (normalised), or None. Tries name / standard_name / canonical_id
    (underscores as spaces) / matched_form."""
    positions = []
    for key in _ingredient_identity_keys(row):
        for cand in (key, key.replace("_", " ")):
            i = title.find(cand)
            if i != -1:
                positions.append(i)
    return min(positions) if positions else None


def _botanical_is_title_head(
    product: Dict[str, Any],
    botanical: Dict[str, Any],
    non_botanical_heroes: List[Dict[str, Any]],
) -> bool:
    """Tie-breaker for products that name BOTH a botanical and a non-botanical as
    title-prominent. Grammar-aware (user policy): the title HEAD owns the dose path.

      Elderberry with Zinc   -> botanical (elderberry is the head)
      Iron with Eleuthero    -> non-botanical (iron is the head)
      Sambucus Elderberry Zinc (no separator) -> earliest-named wins
      ambiguous              -> False (safer generic path; botanical profile would
                                erase the mineral/vitamin RDA/UL logic)
    """
    title = _norm(product.get("product_name") or product.get("fullName"))
    if not title:
        return False
    boundary = _title_head_boundary(title)
    bot_pos = _row_title_pos(botanical, title)
    nonbot_positions = [p for p in (_row_title_pos(r, title) for r in non_botanical_heroes)
                        if p is not None]

    bot_in_head = bot_pos is not None and bot_pos < boundary
    nonbot_in_head = any(p < boundary for p in nonbot_positions)
    if bot_in_head and not nonbot_in_head:
        return True
    if nonbot_in_head and not bot_in_head:
        return False
    # both (or neither) in the head segment -> earliest-named ingredient wins
    if bot_pos is not None and nonbot_positions:
        return bot_pos < min(nonbot_positions)
    # unresolved -> non-botanical / generic path (safer)
    return False


def _botanical_is_material(botanical_mass_mg: float, non_botanical: List[Dict[str, Any]]) -> bool:
    """Return True when the botanical is material enough to own a mixed profile."""
    max_non_botanical_mass = max((_mass_mg(r) or 0.0 for r in non_botanical), default=0.0)
    if max_non_botanical_mass <= 0:
        return True
    return botanical_mass_mg >= (
        _BOTANICAL_PROMOTION_MATERIALITY_FRACTION * max_non_botanical_mass
    )


def _is_nonbotanical_enzyme_active(row: Dict[str, Any]) -> bool:
    canonical = _norm(row.get("canonical_id"))
    tax = row.get("raw_taxonomy") if isinstance(row.get("raw_taxonomy"), dict) else {}
    return bool(
        canonical in _ENZYME_CANONICALS
        or _norm(tax.get("category")) == "enzyme"
        or _norm(row.get("category")) == "enzyme"
        or _norm(row.get("dose_class")) == "enzyme_activity"
    )


def _has_enzyme_product_intent(product: Dict[str, Any], non_botanical: List[Dict[str, Any]]) -> bool:
    """True for products whose marketed class is enzymes, not botanical herbs."""
    title = str(product.get("product_name") or product.get("fullName") or "")
    primary_type = _primary_type(product)
    if primary_type not in {"fiber_digestive", "digestive_enzyme"} and not _ENZYME_TITLE_RE.search(title):
        return False
    return any(_is_nonbotanical_enzyme_active(r) for r in non_botanical)


# --- public API ------------------------------------------------------------

def is_botanical_product(product: Dict[str, Any]) -> bool:
    """A product the botanical profile can actually score: it must have a
    recognizable botanical ACTIVE (taxonomy category 'botanical' or a known
    botanical identity) that is *mass-dominant* over the product's actives.

    Taxonomy primary_type alone is NOT enough — routing a product to the profile
    when the adapters can't find a botanical active would zero its
    formulation/dose (regression). So detection is anchored on the same
    `_primary_botanical_active` the adapters use, keeping router and adapters
    consistent.

    Role-aware selector (route-drift fix): mass-dominance alone let a mass-heavy
    botanical *adjunct* hijack a product whose marketed active is non-botanical
    (melatonin 3 mg hijacked by passion flower 200 mg; zinc by elderberry; iron by
    eleuthero). The Phase 2 role classifier resolves this:
      - botanical is the role hero AND material                     -> botanical path
      - a non-botanical active is the role hero, botanical is not    -> NOT botanical
      - both are role heroes                                         -> title-head + material
      - roles absent                                                 -> legacy mass rule

    The legacy mass-dominance gate (P6 review) is retained as the fallback: a
    generic-routed product with a non-botanical active that out-masses the botanical
    (e.g. Magnesium 400 mg + Ginger 50 mg) must NOT flip wholesale to the botanical
    path. The botanical routes only when it is at least as massive as the heaviest
    non-botanical active (comparable mg units; missing masses treated as 0, so
    pure-botanical / anchor-only products still route)."""
    if not isinstance(product, dict):
        return False
    contract_eligible = _classification_product_profile_eligible(product, "botanical")
    if contract_eligible is not None:
        return contract_eligible
    primary = _primary_botanical_active(product)
    if primary is None:
        return False

    actives = _scoring_actives(product)
    non_botanical = [r for r in actives if not _is_botanical_active(r)]
    botanical_mass = _mass_mg(primary) or 0.0
    mass_says_botanical = (
        max((_mass_mg(r) or 0.0 for r in non_botanical), default=0.0) <= botanical_mass
    )
    botanical_is_material = _botanical_is_material(botanical_mass, non_botanical)

    role_map = _role_by_identity(product)
    if role_map:
        botanical_is_hero = _role_of(primary, role_map) in _PRIMARY_ROLES
        non_botanical_heroes = [r for r in non_botanical if _role_of(r, role_map) in _PRIMARY_ROLES]
        if botanical_is_hero and _has_enzyme_product_intent(product, non_botanical):
            return False  # enzyme products keep generic/enzyme dose logic
        if botanical_is_hero and not non_botanical_heroes:
            # Title/theme alone is not enough. A trace botanical in an enzyme or
            # vitamin product should not erase the larger non-botanical dose path.
            return botanical_is_material
        if non_botanical_heroes and not botanical_is_hero:
            return False  # non-botanical hero -> don't let a botanical adjunct hijack
        if botanical_is_hero and non_botanical_heroes:
            # both named in title -> grammar (title head) owns the dose path,
            # but only when the botanical is material enough for that ownership.
            return (
                botanical_is_material
                and _botanical_is_title_head(product, primary, non_botanical_heroes)
            )

    # roles absent / no role hero -> legacy mass-dominance rule
    return mass_says_botanical


def _standardized_match(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
    sb = ((product.get("formulation_data") or {}).get("standardized_botanicals")) or []
    keys = set(_ingredient_identity_keys(row))
    for item in sb:
        if not isinstance(item, dict) or not item.get("meets_threshold"):
            continue
        item_keys = {_norm(item.get("name")), _norm(item.get("botanical_id")),
                     _norm(item.get("standard_name"))}
        if keys & item_keys:
            return True
    return False


def score_botanical_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Botanical formulation adapter (max 15). Replaces A1/A2 for botanicals."""
    row = _primary_botanical_active(product)
    components: Dict[str, float] = {}
    if row is None:
        return {"score": 0.0, "max": BOTANICAL_FORMULATION_CAP, "components": {},
                "metadata": {"reason": "no_botanical_active"}}

    keys = set(_ingredient_identity_keys(row))
    recognized = bool(keys & _known_botanical_identity_set()) or (
        bool(_norm(row.get("canonical_id"))) and _norm(
            (row.get("raw_taxonomy") or {}).get("category")) == "botanical"
        and not str(row.get("canonical_id")).startswith("blend")
    )

    if not recognized:
        components["weak_or_unidentified_botanical"] = -4.0
        score = max(0.0, min(BOTANICAL_FORMULATION_CAP, sum(components.values())))
        return {"score": round(score, 4), "max": BOTANICAL_FORMULATION_CAP,
                "components": components, "metadata": {"recognized": False}}

    forms = _forms_text(row)
    components["recognized_botanical_identity"] = 6.0
    if any(re.search(r"\b" + re.escape(pp) + r"\b", forms) for pp in _PLANT_PARTS):
        components["plant_part_disclosed"] = 2.0
    if _mass_mg(row) is not None:
        components["quantified_dose_present"] = 2.0
    if any(tok in forms for tok in _EXTRACT_TOKENS) and "powder" not in forms:
        components["extract_not_whole_herb"] = 2.0
    if _standardized_match(product, row):
        components["marker_standardization_declared"] = 4.0
    if keys & _branded_studied_set():
        components["branded_clinically_studied_extract"] = 3.0

    raw = sum(components.values())
    return {"score": round(min(BOTANICAL_FORMULATION_CAP, max(0.0, raw)), 4),
            "max": BOTANICAL_FORMULATION_CAP,
            "components": components,
            "metadata": {"recognized": True, "raw": round(raw, 4),
                         "cap_applied": raw > BOTANICAL_FORMULATION_CAP}}


def _dosing_entry_for(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    index = _dosing_index()
    for key in _ingredient_identity_keys(row):
        if key in index:
            return index[key]
    return None


def _is_named_standardized_botanical_complex(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
    """True when a parent-total row is itself the named standardized dose form.

    Curcumin phytosome / Meriva-style labels often expose a parent complex with
    nested form rows. That parent mass is the clinically studied dose form, not
    an opaque proprietary-blend total. Plain blend headers and product-level
    anchors stay conservative.
    """
    keys = set(_ingredient_identity_keys(row))
    return _standardized_match(product, row) or bool(keys & _branded_studied_set())


def _parse_dose_range(entry: Dict[str, Any]) -> Optional[tuple]:
    rng = _norm(entry.get("typical_dosing_range"))
    m = re.match(r"^\s*([0-9.]+)\s*[-–]\s*([0-9.]+)", rng)
    if not m:
        exact = re.match(r"^\s*([0-9.]+)\s*$", rng)
        if exact:
            v = float(exact.group(1))
            return v, v
        return None
    return float(m.group(1)), float(m.group(2))


def _range_mg(entry: Dict[str, Any]) -> Optional[tuple]:
    """Parsed therapeutic dose range converted to mg for _mass_mg comparison."""
    rng = _parse_dose_range(entry)
    if rng is None:
        return None
    unit = _norm(entry.get("unit"))
    if unit in {"g", "gram", "grams"}:
        return rng[0] * 1000.0, rng[1] * 1000.0
    if unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms"}:
        return rng[0] / 1000.0, rng[1] / 1000.0
    if unit in {"mg", "milligram", "milligrams"}:
        return rng
    # Non-mass units (CFU, activity units) are not comparable to _mass_mg.
    return None


def score_botanical_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Botanical dose adapter via clinical therapeutic ranges. Never returns
    None (a primary botanical with no dose is 0, not denominator-excluded)."""
    row = _primary_botanical_active(product)
    if row is None:
        return {"score": 0.0, "band": "no_botanical_active", "metadata": {}}

    if row.get("is_blend_header") or row.get("blend_total_weight_only"):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}
    if row.get("is_parent_total") and not _is_named_standardized_botanical_complex(product, row):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}

    # P6 review (P2#3): an anchor / product-level-evidence mass is a blend/product
    # TOTAL, not a verified per-ingredient dose. It must not earn within-range
    # credit — otherwise removing the botanical-anchor CAUTION ceiling would
    # over-credit opaque blends. Score it like a blend total.
    if (row.get("scoring_input_kind") == "product_level_evidence"
            or row.get("evidence_type") == "blend_anchor_mass"):
        return {"score": 7.0, "band": "blend_total_only", "metadata": {}}

    mass = _mass_mg(row)
    if mass is None:
        return {"score": 0.0, "band": "primary_no_dose", "metadata": {}}

    entry = _dosing_entry_for(row)
    if entry is None:
        return {"score": 10.0, "band": "disclosed_no_reference", "metadata": {}}

    rng = _range_mg(entry)
    if rng is None:
        return {"score": 10.0, "band": "disclosed_no_reference", "metadata": {}}

    lo, hi = rng
    meta = {"dose_mg": mass, "range_mg": [lo, hi]}
    if lo <= mass <= hi:
        return {"score": 21.0, "band": "within_studied_range", "metadata": meta}
    if 0.8 * lo <= mass < lo or hi < mass <= 1.2 * hi:
        return {"score": 16.0, "band": "near_studied_range", "metadata": meta}
    if mass < 0.8 * lo:
        return {"score": 10.0, "band": "below_studied_range", "metadata": meta}
    # Well above the studied range (P6 review P2#2): a megadose is not evidence-
    # backed and B7 cannot fire for botanicals (no RDA/UL safety flags), so it
    # must NOT earn the same near-range credit as a dose just outside the window.
    # True toxicity is still caught by the Layer-1 safety gate; this is fairness.
    return {"score": 12.0, "band": "above_studied_range", "metadata": meta}
