"""Shared probiotic measurement and registry-scope adapters.

This is a measurement adapter, not a clinical benchmark. No universal AFU/CFU
conversion or AFU adequacy range is authored. CFU potency bands and research
scope retain the registry's meaning; neither invents clinical dose applicability.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from clinical_evidence_schema import DOSE_MEASUREMENT_UNITS  # noqa: F401  (re-exported)

_AFU_UNIT = re.compile(
    r"(?:(million|billion)\s+)?(?:afu|active fluorescent units?)(?:\(s\))?",
    re.IGNORECASE,
)
AFU_REVIEW_REASON = "probiotic_afu_reference_unavailable"


def normalized_cfu_count(measure: Mapping) -> float | None:
    """Read one normalized CFU measurement; reject invalid or conflicting twins.

    CFU and billion-CFU are the same unit at a known scale, unlike AFU or mass.
    An explicitly invalid count is not rescued by a second redundant field.
    """
    values = []
    for field, scale in (("cfu_count", 1.0), ("billion_count", 1e9)):
        if field not in measure:
            continue
        value = measure[field]
        if isinstance(value, bool):
            return None
        try:
            number = float(value) * scale
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number) or number <= 0:
            return None
        values.append(number)
    if not values or any(not math.isclose(values[0], v, rel_tol=1e-9) for v in values[1:]):
        return None
    return values[0]


def declared_total_cfu(pdata: Mapping) -> float:
    """Consume enrichment's ownership-reconciled total, never re-sum projections."""
    measure = {target: pdata[source] for source, target in (
        ("total_cfu", "cfu_count"), ("total_billion_count", "billion_count")
    ) if source in pdata}
    return normalized_cfu_count(measure) or 0.0


def probiotic_label_identity_summary(product: Mapping) -> dict:
    """Count distinct label identities after proving each source row's forms.

    ``total_strain_count`` is a derived projection, never a declared denominator.
    Actual label rows may complete a missing blend projection. Neither clinical
    projection availability nor clinical review controls physical identity.
    """
    from studied_formulas import (
        _clinical_strain_registry,
        clinical_strain_identity_key, clinical_strain_identity_matches,
        label_owned_strain_identities,
    )

    product = product if isinstance(product, Mapping) else {}
    pdata = product.get("probiotic_data") or product.get("probiotic_detail") or {}
    pdata = pdata if isinstance(pdata, Mapping) else {}
    registry = _clinical_strain_registry()
    owned = label_owned_strain_identities(product)
    owners = [owner for owner, _ in owned]
    owner_identities = {id(owner): identities for owner, identities in owned}
    owner_registry_ids = {
        id(owner): {key.removeprefix("strain:") for key, _, _ in identities if key.startswith("strain:")}
        for owner, identities in owned
    }
    keys, exact_keys, disclosed_keys = set(), set(), set()
    blend_resolutions = []

    def valid_name(value):
        return isinstance(value, str) and bool(value.strip()) and bool(clinical_strain_identity_key(value))

    def identities(name, owner=None):
        if owner is not None:
            result = []
            for key, label, cid in owner_identities[id(owner)]:
                # Ownership already proved the printed alias. Use the registry
                # spelling to assess specificity, not the label's typography.
                identity = registry[cid]["standard_name"] if cid else label
                state = label_strain_identity_resolution(identity, cid, registry)
                result.append((key, state, state["resolution"] in {
                    "exact_strain_reviewed", "exact_strain_unreviewed"}))
            return result
        registered = {
            cid for cid, reference in registry.items()
            if clinical_strain_identity_matches(name, reference)
        }
        if len(registered) == 1:
            cid = next(iter(registered))
            return [(f"strain:{cid}", label_strain_identity_resolution(name, None, registry), False)]
        return [(f"label:{clinical_strain_identity_key(name)}",
                 label_strain_identity_resolution(name, None, registry), False)]

    blends = pdata.get("probiotic_blends")
    for blend in blends if isinstance(blends, list) else []:
        if not isinstance(blend, Mapping):
            blend_resolutions.append([])
            continue
        names = blend.get("strains")
        names = [name.strip() for name in names if valid_name(name)] if isinstance(names, list) else []
        ref = blend.get("raw_source_path")
        resolutions, blend_keys = [], set()
        source_names_proved = True
        for name in names:
            source_rows = [owner for owner in owners if (
                valid_name(owner.get("name"))
                and (clinical_strain_identity_key(owner["name"]) == clinical_strain_identity_key(name)
                     or any(clinical_strain_identity_matches(name, registry[cid])
                            for cid in owner_registry_ids[id(owner)]))
                and (not ref or owner.get("raw_source_path") == ref
                     or (isinstance(owner.get("raw_source_path"), str)
                         and owner["raw_source_path"].startswith(f"{ref}.nestedRows[")))
            )]
            if ref and not source_rows:
                source_names_proved = False
            for owner in source_rows or [None]:
                for key, state, exact in identities(name, owner):
                    keys.add(key)
                    blend_keys.add(key)
                    if exact:
                        exact_keys.add(key)
                    resolutions.append(state)
        blend_resolutions.append(resolutions)
        measure = blend.get("cfu_data") or {}
        if (names and len(blend_keys) == 1 and source_names_proved
                and isinstance(measure, Mapping)
                and measure.get("has_cfu") is True
                and measure.get("evidence_scope") in {None, "row_level"}
                and (measure.get("raw_source_path") is None or measure["raw_source_path"] == ref)
                and normalized_cfu_count(measure) is not None):
            disclosed_keys.update(blend_keys)

    # Actual registry-resolved label sources survive missing blend projections;
    # detached clinical IDs never manufacture a source row or an identity.
    for owner, members in owned:
        if not any(cid for _, _, cid in members):
            continue
        for key, _, exact in identities(owner["name"], owner):
            keys.add(key)
            if exact:
                exact_keys.add(key)

    return {
        "total_strain_count": len(keys),
        "identified_strain_count": len(exact_keys),
        "per_strain_cfu_disclosed_count": len(disclosed_keys & keys),
        "blend_identity_resolutions": blend_resolutions,
    }


def strain_cfu_tier(cfu_per_day, tiers_cfu_per_day) -> str | None:
    """Map a per-strain CFU count to the registry's potency band.

    These bands do not establish trial-dose applicability or clinical efficacy.

    Returns one of ``"low" | "adequate" | "good" | "excellent"`` or
    ``None`` when the dose is zero/missing or the bands dict is empty.
    Tolerates band-key order and missing ``upper_exclusive`` (treats it
    as +infinity) / missing ``lower_inclusive`` (treats it as 0).
    """
    if (isinstance(cfu_per_day, bool) or not isinstance(cfu_per_day, (int, float))
            or not math.isfinite(cfu_per_day) or cfu_per_day <= 0):
        return None
    if not isinstance(tiers_cfu_per_day, dict) or not tiers_cfu_per_day:
        return None

    for tier_name in ("low", "adequate", "good", "excellent"):
        band = tiers_cfu_per_day.get(tier_name)
        if not isinstance(band, dict):
            continue
        lower = band.get("lower_inclusive", 0)
        upper = band.get("upper_exclusive")
        lower_ok = cfu_per_day >= (lower if isinstance(lower, (int, float)) else 0)
        upper_ok = (
            upper is None
            or (isinstance(upper, (int, float)) and cfu_per_day < upper)
        )
        if lower_ok and upper_ok:
            return tier_name
    return None


def collect_afu_measurements(product: Mapping) -> list[dict]:
    """Read cleaned row quantities plus the lossless label-display projection.

    A row can occur in the nested and flattened cleaner projections. Its source
    reference and amount identify one measurement. Different serving amounts
    are retained, never summed into an invented product or per-strain dose.
    """
    found: dict[tuple, dict] = {}

    def add(ref, value, unit, serving=None):
        match = _AFU_UNIT.fullmatch(str(unit or "").strip())
        if not match:
            return
        scale = {"million": 1_000_000, "billion": 1_000_000_000}.get((match[1] or "").lower(), 1)
        try:
            decimal_source = Decimal(str(value).replace(",", ""))
            source = float(decimal_source)
            normalized = float(decimal_source * scale)
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            source = normalized = float("nan")
        valid = math.isfinite(normalized) and normalized > 0 and not isinstance(value, bool)
        source_value = source if math.isfinite(source) else str(value)
        normalized = normalized if valid else None
        serving = serving or {}
        basis = tuple(serving.get(k) or None for k in (
            "serving_size_order", "serving_size_quantity", "serving_size_unit",
        ))
        key = (ref, normalized, basis) if valid else (ref, str(value), str(unit), basis)
        found.setdefault(key, {
            "source_row_ref": ref,
            "source_value": source_value,
            "source_unit": str(unit).strip(),
            "normalized_value": normalized,
            "normalized_unit": "AFU",
            "serving_size_order": basis[0],
            "serving_size_quantity": basis[1],
            "serving_size_unit": basis[2],
            "assessment_status": "unresolved_reference" if valid else "invalid_amount",
        })

    def visit(rows, prefix):
        for index, row in enumerate(rows or []):
            if not isinstance(row, Mapping):
                continue
            ref = row.get("raw_source_path") or f"{prefix}[{index}]"
            variants = row.get("quantityVariants") or []
            if variants:
                for variant in variants:
                    if isinstance(variant, Mapping):
                        add(ref, variant.get("quantity"), variant.get("unit"), variant)
            else:
                add(ref, row.get("quantity"), row.get("unit"))
            visit(row.get("nestedIngredients"), f"{ref}.nestedRows")

    visit(product.get("activeIngredients"), "activeIngredients")
    for row in product.get("display_ingredients") or []:
        if not isinstance(row, Mapping) or row.get("source_section") != "activeIngredients":
            continue
        ref = row.get("raw_source_path")
        if not ref:
            continue
        values = [{"exact_dose_text": row.get("exact_dose_text")}]
        values.extend(row.get("serving_variants") or [])
        for value in values:
            if not isinstance(value, Mapping):
                continue
            parts = str(value.get("exact_dose_text") or "").split(maxsplit=1)
            if len(parts) == 2:
                add(ref, parts[0], parts[1], value)
    return list(found.values())


def pending_afu_measurements(product: Mapping) -> list[dict]:
    """Consume the enrichment-owned measurement contract, including blob alias."""
    pdata = product.get("probiotic_data") or product.get("probiotic_detail") or {}
    if not isinstance(pdata, Mapping):
        return []
    rows = pdata.get("afu_measurements")
    if rows is None:
        return []
    # Only the current, exact formula contract can settle an AFU exposure. Never
    # trust an enriched/caller-supplied success stamp or convert AFU into CFU.
    from studied_formulas import assess_studied_formula
    if assess_studied_formula(product)["status"] == "assessed_studied_formula":
        return []
    if not isinstance(rows, list):
        rows = [rows]
    return [
        row if (
            isinstance(row, dict)
            and isinstance(row.get("source_row_ref"), str)
            and row["source_row_ref"].strip()
        ) else {
            "source_row_ref": f"probiotic_data.afu_measurements[{index}]",
            "assessment_status": "invalid_measurement_payload",
        }
        for index, row in enumerate(rows)
    ]


@lru_cache(maxsize=1)
def _probiotic_evidence_policy() -> dict:
    """The owner's native-context policy lives with the scoring config (one brain)."""
    from scoring_v4.quality_score_config import block as config_block
    block = config_block("evidence_magnitudes", "probiotic")["probiotic"]
    return {"review_policy": block.get("native_context_review_policy", "clinician_only"),
            "dose": dict(block.get("dose_applicability_policy") or {})}


def native_context_review_policy() -> str:
    return _probiotic_evidence_policy()["review_policy"]


IDENTITY_CONFIDENCE_ACCEPTED = frozenset({
    "clinical_identity_reviewed", "deposit_crosswalk_verified", "canonical_identity_verified"})
def clinical_review_provenance_valid(context) -> bool:
    """Require an attributable, dated clinical approval with an explicit scope."""
    if not isinstance(context, Mapping):
        return False
    review = context.get("clinical_review")
    if not isinstance(review, Mapping):
        return False
    if review.get("scope") != "identity_dose_outcome_applicability":
        return False
    reviewer = review.get("reviewer")
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewer, str) or not reviewer.strip() or reviewer.strip().lower() in {
        "unknown", "pending", "placeholder", "tbd",
    }:
        return False
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        return False
    try:
        parsed = datetime.fromisoformat(reviewed_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    # Permit ordinary host clock skew, but never let a future-dated record
    # pre-authorize clinical scoring work that has not happened yet.
    return parsed <= datetime.now(parsed.tzinfo) + timedelta(minutes=5)


def context_accepted_for_scoring(context) -> bool:
    """Only an attributable clinician approval can authorize clinical scoring."""
    if not isinstance(context, Mapping):
        return False
    # A clinician approval records review provenance; it does not override an
    # explicit scope decision that this context is not eligible for scoring
    # (for example, a class-level or ranking-only record). Only an absent flag
    # or the boolean True is eligibility; 0, "false" and "no" are not.
    eligible = context.get("scoring_eligible")
    return (
        context.get("review_status") == "clinician_approved"
        and (eligible is None or eligible is True)
        and clinical_review_provenance_valid(context)
    )


def effective_clinical_dose_basis(dose: Mapping) -> str | None:
    """Resolve the canonical frozen dose basis to the runtime vocabulary.

    New contexts store ``dose.dose_basis``.  Older contexts store
    ``dose.basis``.  The frozen field wins when present; an unknown value
    fails closed instead of silently falling back to a potentially conflicting
    legacy value.  This keeps one owner for the meaning of a clinical dose
    while preserving compatibility with legacy registry records.
    """
    if not isinstance(dose, Mapping):
        return None
    if "dose_basis" in dose:
        return {
            "per_strain_daily": "discrete_daily_arms",
            "nominal_assigned_arm": "discrete_daily_arms",
            "combination_total_daily": "combination_total_daily",
            "measured_viability": "measured_viability",
            "single_challenge": "single_challenge",
            "not_applicable": "not_applicable",
        }.get(dose.get("dose_basis"))
    return dose.get("basis") if isinstance(dose.get("basis"), str) else None


def identity_confidence(entry) -> str:
    """What the registry actually knows about an identity, from strongest to weakest.

    clinical_identity_reviewed (clinician sign-off) > deposit_crosswalk_verified
    (designation named in literature with a culture-collection deposit) >
    canonical_identity_verified (designation and species named in literature, or a
    legacy curated identity awaiting sign-off) > label_designation_recognized
    (printed designation; species unconfirmed or no literature hit). None of these
    means efficacy, a known dose or laboratory authenticity of the product.
    """
    entry = entry if isinstance(entry, Mapping) else {}
    thresholds = entry.get("cfu_thresholds") or {}
    if isinstance(thresholds, Mapping) and thresholds.get("dr_pham_signoff") is True:
        return "clinical_identity_reviewed"
    verification = entry.get("identity_verification")
    if isinstance(verification, Mapping):
        if verification.get("status") == "designation_verified":
            return "deposit_crosswalk_verified" if verification.get("deposit_ids") else "canonical_identity_verified"
        return "label_designation_recognized"
    # Legacy clinician-authored entries predate this explicit identity block.
    # New bare entries fail closed instead of becoming verified by omission.
    if _legacy_evidence_block(entry) is not None:
        return "canonical_identity_verified"
    return "label_designation_recognized"


def _primary_patient_important(context: Mapping) -> list:
    return [o for o in (context.get("outcomes") or []) if isinstance(o, Mapping)
            and o.get("hierarchy") == "primary" and o.get("kind") == "patient_important"]


def derived_context_evidence(entry) -> dict | None:
    """Summarize the identity's accepted exact-strain contexts in the legacy evidence shape.

    Strength: pooled human evidence (meta-analysis, systematic review, guideline) or
    two or more RCTs with a positive primary patient-important outcome -> strong;
    one such RCT -> medium; otherwise weak. Direction: negative-only evidence is
    negative; positive evidence with null, mixed, or negative company is mixed;
    positives only are positive; null-only or surrogate-only evidence is null.
    Combination and species contexts never contribute.
    """
    entry = entry if isinstance(entry, Mapping) else {}
    contexts = [c for c in (entry.get("study_contexts") or []) if isinstance(c, Mapping)
                and c.get("identity_scope") == "exact_strain" and context_accepted_for_scoring(c)]
    if not contexts:
        return None
    # An approved context only counts for this identity when it is a valid
    # record OF this identity: the runtime validator owns that rule (owner in
    # components, exact-strain means one component, unit matches measurement).
    # studied_formulas imports this module, so resolve it at call time.
    from studied_formulas import valid_native_study_context
    contexts = [c for c in contexts if valid_native_study_context(c, entry.get("id"))]
    if not contexts:
        return None
    # Several papers can report the same trial. Evidence strength counts independent
    # trial families, never publication rows.
    families: dict[str, list[Mapping]] = {}
    for context in contexts:
        family = str(context.get("trial_family") or context.get("context_id") or "").strip()
        families.setdefault(family, []).append(context)
    positives, mixed, nulls, negatives = [], [], [], []
    for family_contexts in families.values():
        directions = {
            outcome.get("direction")
            for context in family_contexts
            for outcome in _primary_patient_important(context)
        }
        representative = family_contexts[0]
        if directions == {"negative"}:
            negatives.append(representative)
        elif directions & {"positive", "negative"} and len(directions) > 1:
            mixed.append(representative)
        elif "positive" in directions:
            positives.append(representative)
        elif "mixed" in directions:
            mixed.append(representative)
        elif "null" in directions:
            nulls.append(representative)
    pooled = [c for c in positives if c.get("study_design") in ("meta_analysis", "systematic_review", "guideline")]
    rcts = [c for c in positives if c.get("study_design") in ("rct", "crossover_rct", "cluster_rct")]
    strength = "strong" if pooled or len(rcts) >= 2 else "medium" if rcts else "weak"
    if negatives and not positives:
        direction = "negative"
    elif positives and (nulls or negatives or mixed):
        direction = "mixed"
    elif positives:
        direction = "positive_strong" if strength == "strong" else "positive_weak"
    elif mixed:
        direction = "mixed"
    else:
        direction = "null"
    pmids: list = []
    for c in (positives + mixed + nulls + negatives) or contexts:
        for pmid in c.get("source_pmids") or []:
            if pmid not in pmids:
                pmids.append(pmid)
    return {
        "type": "study_contexts_derived",
        "evidence_strength": strength,
        "effect_direction": direction,
        "pmid": pmids[0] if pmids else None,
        "additional_pmids": pmids[1:],
        "clinical_validation": {"q1_strain_explicit": "YES", "q3_human_clinical": "YES"},
        "derived_from_contexts": [c.get("context_id") for c in contexts],
        "review_basis": native_context_review_policy(),
        "context_counts": {"positive": len(positives), "mixed": len(mixed), "null": len(nulls), "negative": len(negatives)},
    }


def _legacy_evidence_block(entry: Mapping) -> dict | None:
    thresholds = entry.get("cfu_thresholds") or {}
    legacy = thresholds.get("evidence") if isinstance(thresholds, Mapping) else None
    return dict(legacy) if isinstance(legacy, Mapping) and legacy else None


def effective_strain_evidence(entry) -> dict | None:
    """A clinician-authored summary always summarizes its identity (signed or
    suspended); only an identity without one is described by its accepted contexts."""
    entry = entry if isinstance(entry, Mapping) else {}
    legacy = _legacy_evidence_block(entry)
    if legacy is not None:
        return legacy
    if identity_confidence(entry) not in IDENTITY_CONFIDENCE_ACCEPTED:
        return None
    return derived_context_evidence(entry)


def identity_review_accepted(entry) -> bool:
    """Clinician sign-off, or an attributable approved context on a verified identity.

    An identity with a clinician-authored summary stays under the clinician gate:
    a suspended sign-off is a hold, and the owner policy cannot lift it.
    """
    entry = entry if isinstance(entry, Mapping) else {}
    thresholds = entry.get("cfu_thresholds") or {}
    if isinstance(thresholds, Mapping) and thresholds.get("dr_pham_signoff") is True:
        return True
    if _legacy_evidence_block(entry) is not None:
        return False
    return identity_confidence(entry) in IDENTITY_CONFIDENCE_ACCEPTED and derived_context_evidence(entry) is not None


def classify_dose_applicability(amount, dose: Mapping) -> tuple[str, str]:
    """Classify a label's owned daily dose against a study's tested exposure.

    Discrete trial arms are points, not a continuous efficacy range. Measured
    start/end viability describes product stability and cannot establish a tested
    daily efficacy dose.
    """
    dose = dose if isinstance(dose, Mapping) else {}
    if (dose.get("measurement_type") or "viable_count") != "viable_count":
        return "DOSE_UNKNOWN", "study_dose_not_viable_count"
    try:
        values = [float(v) for v in (dose.get("values") or [])]
    except (TypeError, ValueError):
        return "DOSE_UNKNOWN", "study_daily_dose_unresolved"
    if effective_clinical_dose_basis(dose) != "discrete_daily_arms" or not values:
        return "DOSE_UNKNOWN", "study_daily_dose_unresolved"
    if amount is None:
        return "DOSE_UNKNOWN", "label_dose_unknown"
    if any(math.isclose(float(amount), value, rel_tol=1e-9) for value in values):
        return "EXACT_TESTED_DOSE", "matches_tested_daily_dose"
    return "OUTSIDE_TESTED_RANGE", "outside_tested_daily_doses"


def dose_applicability_credit(applicability_class: str) -> float:
    credit = _probiotic_evidence_policy()["dose"].get("credit") or {}
    try:
        return float(credit.get(applicability_class, 0.0))
    except (TypeError, ValueError):
        return 0.0


def clinical_strain_research_scope(entry: dict) -> dict:
    """One registry-owned scope decision for presentation and scored evidence."""
    entry = entry if isinstance(entry, dict) else {}
    evidence = effective_strain_evidence(entry) or {}
    validation = evidence.get("clinical_validation") or {}
    validation = validation if isinstance(validation, dict) else {}
    evidence_type = str(evidence.get("type") or "").strip().lower()
    explicit = str(validation.get("q1_strain_explicit") or "").strip().upper()
    human = str(validation.get("q3_human_clinical") or "").strip().upper()
    human_evidence = human == "YES" if human else any(
        token in evidence_type for token in ("rct", "meta_analysis", "clinical", "guideline", "human"))
    if explicit == "FORMULA_LEVEL" or evidence_type == "product_formula_rct":
        scope = "formula_specific"
    elif explicit == "YES" or "strain_specific" in evidence_type:
        scope = "strain_specific"
    elif explicit == "NO":
        scope = "species_general"
    else:
        scope = "scope_unresolved"
    return {"evidence_scope": scope, "human_evidence": human_evidence}


_PROBIOTIC_GENERA = frozenset({
    "lactobacillus", "bifidobacterium", "streptococcus", "bacillus", "saccharomyces",
    "lactococcus", "enterococcus", "pediococcus", "leuconostoc", "akkermansia",
    "clostridium", "escherichia", "lacticaseibacillus", "lactiplantibacillus",
    "limosilactobacillus", "ligilactobacillus", "lentilactobacillus", "levilactobacillus",
    "bacteroides", "propionibacterium", "weissella", "kluyveromyces", "heyndrickxia",
    "weizmannia", "faecalibacterium", "lacticaseibacillus", "latilactobacillus",
})
_TAXON_NOISE = frozenset({"subsp", "ssp", "spp", "sp", "var", "strain", "subspecies"})


def _label_designation_tokens(label: str) -> tuple[list[str], list[str]]:
    """Split a label strain into taxon words and strain-designation codes."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\.]*", str(label or ""))
    taxon, codes = [], []
    for index, word in enumerate(words):
        bare = word.rstrip(".")
        # Uppercase label typography is not an uppercase strain designation.
        # Preserve the scientific binomial before interpreting later codes.
        if bare.lower() in _PROBIOTIC_GENERA or (
            index == 1 and taxon and
            (taxon[0] in _PROBIOTIC_GENERA or len(taxon[0]) == 1) and bare.isalpha()
        ):
            taxon.append(bare.lower())
            continue
        if re.fullmatch(r"[A-Za-z]", bare):
            taxon.append(bare.lower())  # genus abbreviation such as "L."
            continue
        if bare.lower() in _TAXON_NOISE:
            continue
        if re.search(r"\d", bare) or (bare.isupper() and len(bare) >= 2):
            codes.append(bare)
        else:
            taxon.append(bare.lower())
    return taxon, codes


def label_strain_identity_resolution(label: str, clinical_id, registry: Mapping) -> dict:
    """One honest identity state per label strain; never invents a strain.

    States: exact_strain_reviewed, exact_strain_unreviewed (registry identity
    without clinician sign-off), strain_designation_unregistered (a code is
    printed but no registry identity exists yet), species_only, genus_only,
    unresolved_label_text, rejected_by_clinician. A species-only label can
    never own a strain identity, whatever the caller passes.
    """
    text = str(label or "").strip()
    if clinical_id == "BLOCKED_OR_HOLD":
        return {"strain": text, "resolution": "rejected_by_clinician", "clinical_id": clinical_id}
    taxon, codes = _label_designation_tokens(text)
    has_genus = bool(taxon) and (taxon[0] in _PROBIOTIC_GENERA or len(taxon[0]) == 1)
    reference = registry.get(clinical_id) if isinstance(clinical_id, str) and isinstance(registry, Mapping) else None
    from studied_formulas import clinical_strain_identity_matches
    if codes and isinstance(reference, Mapping) and clinical_strain_identity_matches(text, reference):
        signoff = (reference.get("cfu_thresholds") or {}).get("dr_pham_signoff") is True
        state = "exact_strain_reviewed" if signoff else "exact_strain_unreviewed"
        return {"strain": text, "resolution": state, "clinical_id": clinical_id}
    if codes and has_genus:
        return {"strain": text, "resolution": "strain_designation_unregistered", "clinical_id": None}
    if has_genus and len(taxon) >= 2:
        return {"strain": text, "resolution": "species_only", "clinical_id": None}
    if has_genus and len(taxon) == 1 and len(taxon[0]) > 1:
        return {"strain": text, "resolution": "genus_only", "clinical_id": None}
    return {"strain": text, "resolution": "unresolved_label_text", "clinical_id": None}
