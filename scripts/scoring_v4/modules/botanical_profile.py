"""V4 Phase 6 — Botanical Profile (formulation + dose adapters).

Botanicals are not vitamins. The generic A1/A2 (bio_score / premium forms) and
the RDA/UL dose proxy structurally disadvantage herbs. This profile replaces
both for botanical products:

  Formulation adapter (replaces A1/A2; reference 12), magnitudes in
  quality_score.json formulation_variant_magnitudes.botanical. V4.1 Step 4:
    recognized botanical identity        botanical_identity_neutral (neutral baseline)
    extract (not whole-herb powder)      botanical_extract
    marker standardization (tiered)      standardization_tier_full / _near / _half
    weak / unidentified botanical        -4   (replaces the identity baseline)
  Plant part and the printed amount are Transparency facts; a brand name is an
  Evidence fact (a branded studied extract still earns the full standardization
  tier, once).

  Dose adapter: source-owned reference semantics in rda_therapeutic_dosing.json
  distinguish descriptive study regimens from numerical benchmarks. The reviewed
  broad botanical records establish no general minimum/window and use the
  completed neutral for disclosed amounts. Genuinely hidden amounts retain the
  neutral; lost amounts and unresolved identity/preparation retain their holds.

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

from scoring_input_contract import dose_disclosure_status, is_lent_blend_mass, _positive_quantity
from scoring_v4.modules.generic_helpers import bio_score_of
from scoring_v4.quality_score_config import block as _cfg_block

_FVM = _cfg_block("formulation_variant_magnitudes", "botanical")["botanical"]


BOTANICAL_FORMULATION_CAP = _FVM["botanical_formulation_cap"]

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
    """name/alias -> therapeutic dosing entry (its reference_semantics decision)."""
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
def _branded_studied_entries() -> tuple:
    """(names and aliases, brand_tokens) of each clinically studied brand record."""
    try:
        raw = json.loads((_DATA_DIR / "backed_clinical_studies.json").read_text())
    except Exception:  # pragma: no cover
        return ()
    from evidence_resolver import clinical_record_sources_eligible

    out = []
    for entry in raw.get("backed_clinical_studies") or []:
        if not isinstance(entry, dict) or not clinical_record_sources_eligible(entry):
            continue
        level = _norm(entry.get("evidence_level"))
        branded = "branded" in level or _norm(entry.get("id")).startswith("brand_")
        if not branded or level == "preclinical":
            continue
        names = frozenset(k for k in (_norm(v) for v in [entry.get("standard_name"), *(entry.get("aliases") or [])]) if k)
        out.append((names, tuple(_norm(t) for t in entry.get("brand_tokens") or [] if _norm(t))))
    return tuple(out)


def _branded_studied_row(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
    """Whether ``row`` is a branded clinically-studied extract on this label.

    The enricher decides whether a label names a brand
    (``enrich_supplements_v3._brand_mentioned``: a BRAND_ entry's aliases find
    it, its ``brand_tokens`` confirm it) and records the rows each clinical
    match covers. A brand known only from animal or in-vitro work is not
    clinically studied.

    A label-level projection (a brand-named blend total such as "Sytrinol") is
    never assessed by that matcher, so the same rule reads the projection's own
    label name. Remove this branch when the enricher records brand matches for
    those rows.
    """
    from evidence_resolver import clinical_record_sources_eligible

    ref = row.get("raw_source_path")
    for match in ((product.get("evidence_data") or {}).get("clinical_matches") or []):
        if not isinstance(match, dict) or not clinical_record_sources_eligible(match):
            continue
        level = _norm(match.get("evidence_level"))
        branded = "branded" in level or _norm(match.get("id")).startswith("brand_")
        if ref and branded and level != "preclinical" and ref in (match.get("matched_source_row_refs") or []):
            return True
    if row.get("scoring_input_kind") != "product_level_evidence":
        return False
    keys = set(_ingredient_identity_keys(row))
    text = " ".join(sorted(keys))
    return any(
        keys & names and (
            not tokens
            or any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text) for t in tokens)
        )
        for names, tokens in _branded_studied_entries()
    )


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
    rows = iqd.get("ingredients_scorable") or []
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
    if unit in {"mg", "milligram", "milligrams"} or unit.startswith(("mg", "milligram")):
        return qty
    if unit in {"g", "gram", "grams"} or unit.startswith("gram"):
        return qty * 1000.0
    if (
        unit in {"mcg", "ug", "µg", "μg", "microgram", "micrograms"}
        or unit.startswith(("mcg", "ug", "µg", "μg", "microgram"))
    ):
        return qty / 1000.0
    return None


def _primary_botanical_active(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    scoring_actives = _scoring_actives(product)
    botanicals = [r for r in scoring_actives if _is_botanical_active(r)]
    if not botanicals:
        return None
    # Share the classification contract's exact aggregate-ownership boundary:
    # only a fully reconciled duplicate rollup is removed. Opaque/partial blend
    # anchors remain available as conservative fallback evidence.
    from scoring_input_contract import profile_owner_candidate_rows

    owner_candidates = profile_owner_candidate_rows(scoring_actives, product=product)
    owner_candidate_ids = {id(row) for row in owner_candidates}
    candidates = [
        row for row in botanicals if id(row) in owner_candidate_ids
    ] or botanicals
    # Highest comparable mass wins; when multiple rows share the same blend
    # total, prefer a recognized botanical anchor over the generic/unmapped
    # blend header. This keeps opaque blend headers conservative without
    # suppressing the known child identity carried by blend_anchor_mass.
    def exact_branded_preparation(row: Dict[str, Any]) -> bool:
        if not _branded_studied_row(product, row):
            return False
        text = " ".join(_ingredient_identity_keys(row))
        return any(
            any(name and name in text for name in names)
            for names, _tokens in _branded_studied_entries()
        )

    return max(candidates, key=lambda r: (
        exact_branded_preparation(r),
        _mass_mg(r) or 0.0,
        _recognized_botanical_identity(r),
        bio_score_of(r) or 0.0,
    ))


def _explicit_botanical_identity_rejection(row: Dict[str, Any]) -> bool:
    # The input owner excludes some known identities from dose-bearing rows
    # solely because the manufacturer withholds their individual quantities.
    # That exclusion cannot turn a resolved identity into an unknown botanical.
    known_without_dose = (
        row.get("identity_decision_reason") == "no_dose_evidence"
        and row.get("mapped_identity") is True
        and row.get("identity_disposition") == "clean"
        and row.get("identity_taxonomy_coherent") is True
        and row.get("cleaner_row_role") == "active_scorable"
        and row.get("score_eligible_by_cleaner") is True
        and row.get("score_exclusion_reason") == "recognized_non_scorable"
    )
    return ((row.get("scoreable_identity") is False and not known_without_dose)
            or row.get("identity_disposition") == "identity_conflict")


def _recognized_botanical_identity(
    row: Dict[str, Any], *, allow_taxonomy_fallback: bool = True,
) -> bool:
    from evidence_resolver import is_reviewed_branded_material

    if _explicit_botanical_identity_rejection(row):
        return False

    # The strict input owner has already resolved identity and botanical
    # source evidence, including a botanical form beneath a raw blend parent.
    # A broad category alone is not a verified identity or a clinical claim.
    if (row.get("scoreable_identity") is True
            and row.get("scoring_input_kind") != "product_level_evidence"
            and not is_lent_blend_mass(row)
            and (row.get("evidence_type") != "blend_anchor_mass"
                 or row.get("scoring_input_kind") == "label_active_projection")
            and bool(_norm(row.get("canonical_id")))
            and not _norm(row.get("canonical_id")).startswith("blend")
            and _classification_profile_eligible(row, "botanical") is True):
        return True
    keys = set(_ingredient_identity_keys(row))
    return bool(keys & _known_botanical_identity_set()) or is_reviewed_branded_material(
        row.get("canonical_id"), row.get("name")
    ) or (
        allow_taxonomy_fallback and bool(_norm(row.get("canonical_id"))) and _norm(
            (row.get("raw_taxonomy") or {}).get("category")) == "botanical"
        and not str(row.get("canonical_id")).startswith("blend")
    )


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


# Tiered marker-standardization credit (0-4), calibration v2. The binary
# meets_threshold gate destroyed credit for a near-threshold standardization
# (Boswellia 40% vs a 65% spec earned 0) and for a disclosed marker with an
# unparsed amount. Tiers reward genuine standardization proportionally while a
# plain powder / no-evidence ingredient still earns nothing — good products score
# higher without inflating weak ones.
# V4.1 Step 4: the earned traits (extract, standardization) fill what the
# neutral identity credit leaves of the reference; a marker word without a
# quantified amount, the plant part, the printed amount and a brand name earn
# nothing here (Transparency owns disclosure; Evidence owns branded studies).
#   full  = branded clinically-studied extract OR full threshold met
#   near  = marker disclosed and >= 75% of threshold
#   half  = marker disclosed and >= 50% of threshold
#   0     = below 50% of threshold / unquantified marker / plain powder
STANDARDIZATION_TIER_FULL = _FVM["standardization_tier_full"]
STANDARDIZATION_TIER_NEAR = _FVM["standardization_tier_near"]
STANDARDIZATION_TIER_HALF = _FVM["standardization_tier_half"]
BOTANICAL_IDENTITY_NEUTRAL = _FVM["botanical_identity_neutral"]
BOTANICAL_EXTRACT = _FVM["botanical_extract"]


def _standardization_tier_credit(product: Dict[str, Any], row: Dict[str, Any]) -> float:
    """Return the tiered marker-standardization credit for ``row``."""
    keys = set(_ingredient_identity_keys(row))
    # A branded clinically-studied extract is standardized by definition.
    if _branded_studied_row(product, row):
        return STANDARDIZATION_TIER_FULL
    sb = ((product.get("formulation_data") or {}).get("standardized_botanicals")) or []
    best = 0.0
    for item in sb:
        if not isinstance(item, dict):
            continue
        item_keys = {_norm(item.get("name")), _norm(item.get("botanical_id")),
                     _norm(item.get("standard_name"))}
        if not (keys & item_keys):
            continue
        if item.get("meets_threshold"):
            return STANDARDIZATION_TIER_FULL
        found = _as_float(item.get("percentage_found")) or 0.0
        thr = _as_float(item.get("min_threshold")) or 0.0
        if found > 0 and thr > 0:
            frac = found / thr
            if frac >= 0.75:
                best = max(best, STANDARDIZATION_TIER_NEAR)
            elif frac >= 0.50:
                best = max(best, STANDARDIZATION_TIER_HALF)
            # < 50% of the spec is genuinely under-standardized -> no credit.
    return best


def score_botanical_formulation(product: Dict[str, Any]) -> Dict[str, Any]:
    """Botanical formulation adapter (max 15). Replaces A1/A2 for botanicals."""
    row = _primary_botanical_active(product)
    components: Dict[str, float] = {}
    if row is None:
        return {"score": 0.0, "max": BOTANICAL_FORMULATION_CAP, "components": {},
                "metadata": {"reason": "no_botanical_active"}}

    recognized = _recognized_botanical_identity(row)

    if not recognized:
        components["weak_or_unidentified_botanical"] = -4.0
        score = max(0.0, min(BOTANICAL_FORMULATION_CAP, sum(components.values())))
        return {"score": round(score, 4), "max": BOTANICAL_FORMULATION_CAP,
                "components": components, "metadata": {"recognized": False}}

    forms = _forms_text(row)
    # A recognized identity is a neutral baseline, not earned quality.
    components["recognized_botanical_identity"] = BOTANICAL_IDENTITY_NEUTRAL
    if any(tok in forms for tok in _EXTRACT_TOKENS) and "powder" not in forms:
        components["extract_not_whole_herb"] = BOTANICAL_EXTRACT
    std_credit = _standardization_tier_credit(product, row)
    if std_credit > 0:
        components["marker_standardization_declared"] = std_credit

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
            entry = index[key]
            forms = _forms_text(row)
            if (
                "extract" in _norm(entry.get("standard_name"))
                and any(token in forms for token in _WHOLE_HERB_TOKENS)
                and not any(token in forms for token in _EXTRACT_TOKENS)
            ):
                # Whole-herb mass is not the extract mass studied by this
                # reference. Assess it as a disclosed amount without a
                # benchmark rather than inventing a concentration ratio or
                # treating it as an ineffective dose.
                continue
            return entry
    # Approved general Dose conclusions also live with their existing
    # clinical preparation owner. Read its exact row identity, never the
    # product title, a linked parent or an enrichment-only matched form.
    from dose_assessment import _row_names, verified_reference_citations
    from evidence_resolver import _backed_studies_index
    for key in sorted(_row_names(row, source_only=True)):
        for entry in _backed_studies_index().get(key, []):
            semantics = entry.get("reference_semantics") or {}
            if (semantics.get("reference_type") in {"no_benchmark", "discrete_studied_regimen"}
                    and semantics.get("curve") == "completed_no_benchmark_neutral"
                    and str(semantics.get("approval_status") or "").startswith("approved_existing_neutral_")
                    and semantics.get("source_ids")):
                # A broken exact owner cannot fall through to a weaker source.
                return entry if verified_reference_citations(entry) else {}
    return None


def _is_named_standardized_botanical_complex(product: Dict[str, Any], row: Dict[str, Any]) -> bool:
    """True when a parent-total row is itself the named standardized dose form.

    Curcumin phytosome / Meriva-style labels often expose a parent complex with
    nested form rows. That parent mass is the clinically studied dose form, not
    an opaque proprietary-blend total. Plain blend headers and product-level
    anchors stay conservative.
    """
    return _standardized_match(product, row) or _branded_studied_row(product, row)


# Completed no-benchmark reviews and source-confirmed hidden shares use the
# shared neutral; unresolved identity or unread source amounts remain gaps.
BOTANICAL_DOSE_NO_ACTIVE = _FVM["botanical_dose_no_active"]


def unassessed_amount_band(
    band: str, benchmark: str, label_hidden: bool = True, *,
    reviewed_label_limitation: bool = False,
) -> Dict[str, Any]:
    """Keep completed no-reference and hidden-label states distinct from gaps."""
    from scoring_v4.modules.generic_helpers import unbenchmarked_dose_credit

    # Missing capture cannot become neutral merely because no benchmark was
    # found. A valid disclosed amount with a completed no-reference conclusion,
    # or positive label-hiding evidence, takes neutral (Dose V4.1 section 2.3).
    # A recognized ingredient with a source-owned hidden share has a completed
    # label limitation, independently of a general benchmark review. Keep that
    # unresolved research fact rather than claiming an absent benchmark.
    completed_limit = (reviewed_label_limitation and label_hidden
                       and band in {"blend_total_only", "primary_no_dose"})
    neutral = (completed_limit or (benchmark != "unresolved"
               and (band == "disclosed_no_reference" or label_hidden)))
    metadata = {"benchmark": benchmark}
    if completed_limit:
        metadata.update(assessment_status="complete", reason_code="amount_not_declared")
    return {"score": unbenchmarked_dose_credit() if neutral else 0.0, "band": band,
            "metadata": metadata}


def score_botanical_dose(product: Dict[str, Any]) -> Dict[str, Any]:
    """Assess the source disposition without excluding missing primary amounts."""
    row = _primary_botanical_active(product)
    if row is None:
        return {"score": BOTANICAL_DOSE_NO_ACTIVE, "band": "no_botanical_active", "metadata": {}}
    return score_botanical_purpose_dose(product, row)


def score_botanical_purpose_dose(
    product: Dict[str, Any], row: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Assess one declared botanical purpose through the botanical Dose owner."""
    if not _is_botanical_active(row):
        return None

    benchmark = _botanical_benchmark(row)
    disclosure = dose_disclosure_status(row)
    # The strict input owner's lent-mass classification proves that the label
    # gives a total but not this child's share. A bare aggregate flag or broad
    # botanical taxonomy cannot supply that proof or establish identity.
    reviewed_hidden = (
        _recognized_botanical_identity(row, allow_taxonomy_fallback=False)
        and (is_lent_blend_mass(row) or disclosure == "not_disclosed_blend")
    )
    if row.get("is_blend_header") or row.get("blend_total_weight_only"):
        return unassessed_amount_band("blend_total_only", benchmark,
                                      reviewed_label_limitation=reviewed_hidden)
    if row.get("is_parent_total") and not _is_named_standardized_botanical_complex(product, row):
        return unassessed_amount_band("blend_total_only", benchmark,
                                      reviewed_label_limitation=reviewed_hidden)

    # P6 review (P2#3): an anchor / product-level-evidence mass is a blend/product
    # TOTAL, not a verified per-ingredient dose. It must not earn within-range
    # credit — otherwise removing the botanical-anchor CAUTION ceiling would
    # over-credit opaque blends. Score it like a blend total.
    if (row.get("scoring_input_kind") == "product_level_evidence"
            or is_lent_blend_mass(row)
            or (row.get("evidence_type") == "blend_anchor_mass"
                and row.get("scoring_input_kind") != "label_active_projection")):
        return unassessed_amount_band("blend_total_only", benchmark,
                                      reviewed_label_limitation=reviewed_hidden)

    # No numerical benchmark is being compared here. A printed volume is a
    # disclosed amount even when no mass conversion is available; the shared
    # disclosure owner also keeps missing/hidden source amounts distinct.
    if disclosure != "disclosed" or _positive_quantity(row) is None:
        return unassessed_amount_band("primary_no_dose", benchmark,
                                      label_hidden=disclosure == "not_disclosed_blend",
                                      reviewed_label_limitation=reviewed_hidden)
    # Reviewed source regimens remain descriptive. None of these broad
    # preparation records establishes an approved general minimum/window.
    return unassessed_amount_band("disclosed_no_reference", benchmark)


def _botanical_benchmark(row: Dict[str, Any]) -> str:
    """Return a completed absent general benchmark or unresolved review."""
    if _explicit_botanical_identity_rejection(row):
        return "unresolved"
    entry = _dosing_entry_for(row)
    if entry is not None:
        semantics = entry.get("reference_semantics") or {}
        if str(semantics.get("owner") or "").startswith("scripts/data/backed_clinical_studies.json::"):
            from dose_assessment import verified_reference_citations
            if not verified_reference_citations(entry):
                return "unresolved"
        if (semantics.get("curve") == "completed_no_benchmark_neutral"
                and str(semantics.get("approval_status") or "").startswith("approved_existing_neutral_")):
            return "absent"
        # A source/preparation still awaiting review is not completed neutral.
        return "unresolved"
    # A source-owned completed no-benchmark review is not an identity gap.
    # This does not promote all positive literature to botanical eligibility:
    # only the exact canonical, verified record with the approved neutral
    # disposition completes this Dose assessment. Study exposures stay
    # descriptive and an unreadable amount still fails the strict input gate.
    from evidence_resolver import _load_literature_evidence

    record = _load_literature_evidence().get(_norm(row.get("canonical_id"))) or {}
    semantics = record.get("reference_semantics") or {}
    from dose_assessment import verified_reference_citations

    if (
        verified_reference_citations(record)
        and semantics.get("reference_type") == "no_benchmark"
        and semantics.get("curve") == "completed_no_benchmark_neutral"
        and str(semantics.get("approval_status") or "").startswith("approved_existing_neutral_")
    ):
        return "absent"
    # Recognizing the ingredient completes identity, not the scientific search
    # for an applicable benchmark. Only the reviewed owners above can establish
    # a completed no-benchmark conclusion (and therefore neutral Dose credit).
    return "unresolved"
