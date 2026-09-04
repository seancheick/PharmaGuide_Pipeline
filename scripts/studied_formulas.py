"""Probiotic clinical identity and whole-formula applicability.

No product ID exceptions, per-strain allocations, or AFU/CFU conversions. A
caller stamp is never authoritative: each consumer proves the label contract.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from clinical_applicability import reviewed_entries
from normalization import normalize_text
from serving_frequency import resolve_daily_serving_range
from probiotic_measurements import strain_cfu_tier, clinical_strain_research_scope


def _key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _failure(reason):
    return {"status": "unresolved_reference", "reason_code": reason}


def assess_studied_formula(product: Mapping) -> dict:
    """Prove exact species/strain set, native potency, prebiotic and daily dose."""
    brand = _key(product.get("brandName") or product.get("brand_name"))
    name = _key(product.get("fullName") or product.get("product_name"))
    for entry in reviewed_entries().values():
        contract = entry.get("formula_contract")
        if not isinstance(contract, dict):
            continue
        if brand == _key(contract["brand"]) and name == _key(contract["product_name"]):
            return _assess(product, entry, contract)
    return _failure("no_reviewed_formula_reference")


def _assess(product, entry, contract):
    basis = product.get("serving_basis") or {}
    if not isinstance(basis, Mapping):
        return _failure("formula_daily_serving_mismatch")
    lower, upper, _ = resolve_daily_serving_range(dict(product))
    if (_key(product.get("form_factor_canonical")) != _key(contract["dosage_form"])
            or _key(basis.get("basis_unit")) not in {"capsule", "capsules"}
            or _number(basis.get("basis_count")) != contract["capsules_per_serving"]
            or not basis.get("servings_per_day_source")
            or lower != contract["daily_servings"] or upper != lower):
        return _failure("formula_daily_serving_mismatch")
    rows = product.get("activeIngredients") or []
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return _failure("formula_label_rows_missing")
    headers = [r for r in rows if r.get("nestedIngredients")]
    others = [r for r in rows if not r.get("nestedIngredients")]
    if not headers or len(others) != 1:
        return _failure("formula_active_composition_mismatch")
    refs = [r.get("raw_source_path") for r in rows]
    if any(not isinstance(r, str) or not r for r in refs) or len(set(refs)) != len(refs):
        return _failure("formula_source_ownership_invalid")
    names = { _key(name): i for i, aliases in enumerate(contract["strain_names"]) for name in aliases }
    identities, strain_refs, group_doses = [], [], {}
    for header in headers:
        group = []
        for row in header["nestedIngredients"]:
            if not isinstance(row, dict) or row.get("nestedIngredients"):
                return _failure("formula_strain_structure_mismatch")
            ref = row.get("raw_source_path")
            identity = names.get(_key(row.get("name")))
            if identity is None or not isinstance(ref, str) or not ref.startswith(header["raw_source_path"] + ".nestedRows["):
                return _failure("formula_strain_identity_mismatch")
            identities.append(identity)
            group.append(identity)
            strain_refs.append(ref)
        matched_group = next((g for g in contract["blend_composition"] if sorted(group) == g["strain_indices"]), None)
        if not matched_group:
            return _failure("formula_blend_composition_mismatch")
        group_doses[header["raw_source_path"]] = matched_group["daily_afu"]
    if (sorted(identities) != list(range(len(contract["strain_names"])))
            or len(set(strain_refs + refs)) != len(strain_refs + refs)):
        return _failure("formula_strain_set_mismatch")

    prebiotic = others[0]
    if not isinstance(prebiotic.get("forms"), list):
        return _failure("formula_prebiotic_mismatch")
    text = " ".join(str(prebiotic.get(k) or "") for k in ("name", "raw_source_text", "notes"))
    text += " " + " ".join(str(f.get("name") or "") for f in prebiotic.get("forms", []) if isinstance(f, dict))
    if (prebiotic.get("canonical_id") != contract["prebiotic_canonical_id"]
            or _key(contract["prebiotic_brand_token"]) not in _key(prebiotic.get("name"))
            or "indianpomegranate" not in _key(text) or "fruit" not in _key(text)
            or not re.search(r"(?:greater\s+than|>)\s*40\s*%\s*polyphenol", text, re.I)
            or _number(prebiotic.get("quantity")) != contract["prebiotic_mass_mg"]
            or _key(prebiotic.get("unit")) != "mg"):
        return _failure("formula_prebiotic_mismatch")
    pdata = product.get("probiotic_data") or {}
    if not isinstance(pdata, Mapping):
        return _failure("formula_afu_ownership_mismatch")
    measures = pdata.get("afu_measurements") or []
    header_refs = {r["raw_source_path"] for r in headers}
    if (not isinstance(measures, list) or len(measures) != len(headers)
            or any(not isinstance(m, dict) for m in measures)
            or {m.get("source_row_ref") for m in measures} != header_refs):
        return _failure("formula_afu_ownership_mismatch")
    total = 0.0
    for m in measures:
        value = _number(m.get("normalized_value"))
        source = _number(m.get("source_value"))
        scale = {"afu": 1, "millionafu": 1e6, "billionafu": 1e9}.get(_key(m.get("source_unit")))
        if (m.get("normalized_unit") != "AFU" or value is None or value <= 0
                or source is None or scale is None or not math.isclose(source * scale, value, rel_tol=1e-12)
                or any(m.get(k) is not None for k in ("serving_size_order", "serving_size_quantity", "serving_size_unit"))):
            return _failure("formula_afu_measurement_mismatch")
        total += value
        if not math.isclose(value * lower, group_doses[m["source_row_ref"]], rel_tol=1e-12):
            return _failure("formula_blend_afu_mismatch")
    if not math.isclose(total * lower, contract["daily_afu"], rel_tol=1e-12):
        return _failure("formula_afu_dose_mismatch")
    return {"status": "assessed_studied_formula", "reason_code": "reviewed_commercial_formula_and_reported_total_dose",
            "evidence_id": entry["id"], "scope": "formula_specific",
            "daily_dose": {"value": contract["daily_afu"], "unit": "AFU"},
            "afu_source_row_refs": sorted(header_refs), "strain_source_row_refs": sorted(strain_refs),
            "prebiotic_source_row_ref": prebiotic["raw_source_path"],
            "source_pmids": contract["source_pmids"], "supported_outcomes": contract["supported_outcomes"],
            "studied_population": contract["studied_population"], "limitations": entry["notes"],
            "delivery_basis": contract["delivery_basis"], "reviewed_at": contract["reviewed_at"]}


def formula_clinical_match(product: Mapping) -> dict | None:
    assessment = assess_studied_formula(product)
    if assessment["status"] != "assessed_studied_formula":
        return None
    entry = reviewed_entries()[assessment["evidence_id"]]
    return {**{k: entry[k] for k in ("id", "standard_name", "evidence_level", "evidence_scope",
                                   "study_type", "effect_direction", "total_enrollment", "references_structured")},
            "evidence_origin": "verified_formula_contract", "applicability_assessment": assessment,
            "matched_source_row_refs": assessment["strain_source_row_refs"] + assessment["afu_source_row_refs"] + [assessment["prebiotic_source_row_ref"]]}


@lru_cache(maxsize=1)
def _clinical_strain_registry() -> dict[str, dict]:
    payload = json.loads(
        (Path(__file__).parent / "data/clinically_relevant_strains.json").read_text()
    )
    return {entry["id"]: entry for entry in payload["clinically_relevant_strains"]}


def clinical_strain_identity_matches(identity: object, reference: Mapping) -> bool:
    """Exact registry identity, ignoring punctuation but not species or codes."""
    if not isinstance(identity, str) or not identity.strip():
        return False
    allowed_names = {
        _key(normalize_text(name))
        for name in [reference.get("standard_name"), *reference.get("aliases", [])]
        if isinstance(name, str) and name.strip()
    }
    return _key(normalize_text(identity)) in allowed_names


@lru_cache(maxsize=1)
def _clinical_strain_code_tokens() -> frozenset[str]:
    return frozenset(
        _key(token)
        for entry in _clinical_strain_registry().values()
        for name in [entry["standard_name"], *(
            alias for alias in entry.get("aliases", []) if not re.search(r"\s", alias)
        )]
        for token in re.findall(r"[A-Za-z0-9-]+", name)
        if token.isupper() and len(token) > 1
    )


def clinical_strain_identity_from_label(row: Mapping, reference: Mapping) -> str | None:
    """Resolve an exact identity from this label row, never surrounding prose.

    A structured form may complete its owner's species/code or name a full
    strain. Parent tokens must still be an exact prefix of a registry alias;
    a different species or explicit code cannot borrow the form's identity.
    Multiple distinct forms remain unresolved rather than inheriting one dose.
    """
    label = row.get("raw_source_text") or row.get("name")
    forms = {
        str(form.get("name") if isinstance(form, Mapping) else form).strip()
        for form in row.get("forms") or []
        if (form.get("name") if isinstance(form, Mapping) else form)
    }
    # DSLD may put the explicit strain code in this same row's structured
    # group field. Only code-shaped values join the exact form proof; ordinary
    # taxonomy, categories and notes cannot select a representative strain.
    group = row.get("ingredientGroup")
    group_code = None
    group_words = re.findall(r"[A-Za-z0-9-]+", group) if isinstance(group, str) else []
    if group_words and all(
        _key(word) in _clinical_strain_code_tokens()
        or word.isdigit()
        or (re.search(r"[A-Za-z]", word) and re.search(r"[0-9]", word))
        for word in group_words
    ):
        forms.add(group)
        group_code = group
    def tokens(value):
        return tuple(re.findall(r"[a-z0-9]+", normalize_text(str(value or "")).lower()))

    aliases = [reference.get("standard_name"), *reference.get("aliases", [])]
    alias_tokens = [tokens(alias) for alias in aliases if alias]

    def compatible_parent(value):
        parent = tokens(value)
        return bool(parent) and any(alias[:len(parent)] == parent for alias in alias_tokens)

    # Redundant full names, punctuation variants and the same species/code
    # descriptor are one identity, not multiple strains. A genuinely different
    # form cannot lend the entire owner's CFU to a direct-name match either.
    conflicting_forms = [form for form in forms if not (
        compatible_parent(form)
        or any(alias[-len(tokens(form)):] == tokens(form) for alias in alias_tokens)
        or clinical_strain_identity_matches(f"{label} {form}", reference)
    )]
    if clinical_strain_identity_matches(label, reference):
        # A lone generic species descriptor cannot erase an exact label strain.
        # Explicit codes (including unknown alphanumeric codes) still veto a
        # conflicting form; they never authorize a new identity.
        explicit_conflict = any(
            _key(token) in _clinical_strain_code_tokens()
            or (re.search(r"[A-Za-z]", token) and re.search(r"[0-9]", token))
            for form in conflicting_forms
            for token in re.findall(r"[A-Za-z0-9-]+", form)
        )
        if explicit_conflict or (len(forms) > 1 and conflicting_forms):
            return None
        return str(label)
    if conflicting_forms:
        return None
    if not forms or not row.get("raw_source_path"):
        return None
    if not compatible_parent(label):
        return None
    for field in ("name", "standardName", "standard_name", "ingredientGroup"):
        value = row.get(field)
        # Single-word taxonomy groups (e.g. Bifidobacteria) are not strain
        # identities. Multi-word scientific parents must agree with the form.
        is_genus = value and any(
            tokens(entry["standard_name"])[:1] == tokens(value)
            for entry in _clinical_strain_registry().values()
        )
        if value and (len(tokens(value)) > 1 or is_genus) and not compatible_parent(value):
            return None
    for form in sorted(forms):
        # A group code must complete the label species, never stand alone.
        candidates = (f"{label} {form}",) if form == group_code else (form, f"{label} {form}")
        for candidate in candidates:
            if clinical_strain_identity_matches(candidate, reference):
                return str(reference["standard_name"])
    return None


def _clinical_label_rows(rows):
    for row in rows or []:
        if isinstance(row, Mapping):
            yield row
            yield from _clinical_label_rows(row.get("nestedIngredients"))


def clinical_strain_matches_source_row(product: Mapping, clinical: Mapping, row: Mapping) -> bool:
    """Use an actual source owner, or one unambiguous exact legacy label name."""
    owners = list(_clinical_label_rows(product.get("activeIngredients")))
    if "source_row_ref" in clinical:
        ref = clinical["source_row_ref"]
        if not isinstance(ref, str) or not ref or ref != row.get("raw_source_path"):
            return False
        reference = _clinical_strain_registry().get(clinical.get("clinical_id"))
        matched = [owner for owner in owners if owner.get("raw_source_path") == ref]
        return bool(reference and matched) and clinical_strain_identity_matches(
            clinical.get("strain"), reference
        ) and all(
            clinical_strain_identity_from_label(owner, reference)
            and (not clinical.get("label_name")
                 or _key(clinical["label_name"]) == _key(owner.get("name")))
            for owner in matched
        )
    identity = _key(normalize_text(str(clinical.get("strain") or "")))
    if not identity or identity != _key(normalize_text(str(row.get("name") or ""))):
        return False
    owner_refs = {
        owner.get("raw_source_path") or id(owner)
        for owner in owners
        if _key(normalize_text(str(owner.get("name") or ""))) == identity
    }
    return len(owner_refs) == 1


def independent_clinical_strains(product: Mapping) -> list[dict]:
    """Admit only enrichment identities backed by current independent review."""
    pdata = product.get("probiotic_data") or product.get("probiotic_detail") or {}
    if not isinstance(pdata, Mapping) or not isinstance(pdata.get("clinical_strains"), list):
        return []
    registry = _clinical_strain_registry()
    independent = []
    for row in pdata["clinical_strains"]:
        if not isinstance(row, dict) or not isinstance(row.get("clinical_id"), str):
            continue
        reference = registry.get(row["clinical_id"])
        if not reference:
            continue
        identity = row.get("strain") or row.get("standard_name") or row.get("name")
        if not clinical_strain_identity_matches(identity, reference):
            continue
        if "source_row_ref" in row:
            if not clinical_strain_matches_source_row(
                product, row, {"raw_source_path": row["source_row_ref"]}
            ):
                continue
        thresholds = reference.get("cfu_thresholds") or {}
        evidence = thresholds.get("evidence") or {}
        validation = evidence.get("clinical_validation") or {}
        # Specificity is not review completion or strength. Preserve previously
        # reviewed contextual research while its scope is being curated, without
        # accepting a caller's unknown-scope stamp against a resolved reference.
        allowed_match_statuses = {"exact_strain", "species_level"}
        if clinical_strain_research_scope(reference)["evidence_scope"] == "scope_unresolved":
            allowed_match_statuses.add("scope_unresolved")
        if (thresholds.get("dr_pham_signoff") is not True
                or evidence.get("type") == "product_formula_rct"
                or validation.get("q1_strain_explicit") == "FORMULA_LEVEL"
                or any(source.get("evidence_scope") in {"formula_specific", "formula_only"}
                       for source in (reference, thresholds, row))
                or row.get("dr_pham_signoff") is False
                or row.get("review_status") in {"pending_review", "rejected", "needs_revision"}
                or ("research_match_status" in row
                    and row["research_match_status"] not in allowed_match_statuses)):
            continue
        independent.append(row)
    return independent


def assess_probiotic_evidence(product: Mapping) -> dict:
    """Normalize existing identity decisions; never promote industry dose tiers.

    Exact strain research remains contextual evidence when dose or reviewed
    clinical scope is unknown. A whole-formula assessment owns its own dose;
    it does not manufacture quantities or research approvals for its members.
    """
    if not product.get("probiotic_data") and isinstance(product.get("probiotic_detail"), Mapping):
        product = {**product, "probiotic_data": product["probiotic_detail"]}
    formula = assess_studied_formula(product)
    registry = _clinical_strain_registry()
    accepted = {id(row) for row in independent_clinical_strains(product)
                if "source_row_ref" in row or clinical_strain_matches_source_row(
                    product, row, {"name": row.get("strain")})}
    pdata = product.get("probiotic_data") or {}
    raw_rows = pdata.get("clinical_strains", []) if isinstance(pdata, Mapping) else []
    results = []
    for row in raw_rows if isinstance(raw_rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        reference = registry.get(str(row.get("clinical_id") or ""), {})
        thresholds = reference.get("cfu_thresholds") or {}
        evidence = thresholds.get("evidence") or {}
        support = evidence.get("clinical_support_level") or evidence.get("evidence_strength") or "weak"
        support = {"strong": "high", "medium": "moderate"}.get(support, support)
        scope = reference.get("applicability")
        result = {"clinical_id": row.get("clinical_id"), "strain": row.get("strain"),
                  "source_row_ref": row.get("source_row_ref"), "dose_applicable": False,
                  "cfu_per_day": _owned_daily_cfu(product, row),
                  "support_level": support, "research_accepted": id(row) in accepted,
                  "effect_direction": evidence.get("effect_direction"),
                  "source_pmids": [p for p in [evidence.get("pmid"), *evidence.get("additional_pmids", [])] if p],
                  "supported_outcomes": [], "studied_population": None}
        result.update(clinical_strain_research_scope(reference))
        if not reference:
            status = "strain_reference_unreviewed"
        elif not clinical_strain_identity_matches(row.get("strain"), reference):
            status = "strain_identity_mismatch"
        elif id(row) not in accepted:
            status = "strain_identity_or_review_unresolved"
        elif row.get("is_inactivated") or row.get("is_postbiotic"):
            status = "strain_context_mismatch"
        elif result["cfu_per_day"] is None or result["cfu_per_day"] <= 0:
            status = "strain_dose_unknown"
        elif not isinstance(scope, Mapping):
            status = "strain_dose_reference_unreviewed"
        else:
            status = _assess_strain_scope(product, result, scope)
            result.update(source_pmids=scope.get("source_pmids", []),
                          supported_outcomes=scope.get("supported_outcomes", []),
                          studied_population=scope.get("studied_population"))
        result["status"] = status
        result["industry_adequacy_tier"] = strain_cfu_tier(
            result["cfu_per_day"], thresholds.get("tiers_cfu_per_day"))
        result["dose_applicable"] = status == "strain_dose_applicable"
        results.append(result)
    return {"formula_assessment": formula, "strain_assessments": results}


def assessed_native_strain_doses(product: Mapping) -> list[dict]:
    """Project the shared assessment to the existing Dose arithmetic interface."""
    assessment = assess_probiotic_evidence(product)
    by_owner = {(r["clinical_id"], r["source_row_ref"]): r
                for r in assessment["strain_assessments"] if r["research_accepted"]}
    return [{**row, "cfu_per_day": assessed["cfu_per_day"],
             "adequacy_tier": assessed["industry_adequacy_tier"],
             "clinical_support_level": assessed["support_level"]}
            for row in independent_clinical_strains(product)
            if (assessed := by_owner.get((row.get("clinical_id"), row.get("source_row_ref"))))]


def _owned_daily_cfu(product: Mapping, row: Mapping) -> float | None:
    """Use the existing CFU producer's unique row-level measure, never its total.

    The legacy clinical row's cfu_per_day is actually a per-serving stamp. Join
    back to its source-owned measurement and apply explicit serving frequency.
    Missing provenance is unknown, not zero, and AFU never enters this path.
    """
    ref = row.get("source_row_ref")
    if not isinstance(ref, str) or not ref or not clinical_strain_matches_source_row(
            product, row, {"raw_source_path": ref}):
        return None
    blends = (product.get("probiotic_data") or {}).get("probiotic_blends") or []
    measures = []
    for blend in blends:
        if not isinstance(blend, Mapping) or blend.get("raw_source_path") != ref:
            continue
        measure = blend.get("cfu_data") or {}
        if (len(blend.get("strains") or []) != 1 or not isinstance(measure, Mapping)
                or measure.get("raw_source_path") != ref
                or measure.get("evidence_scope") != "row_level"):
            return None
        measures.append(_number(measure.get("cfu_count")))
    basis = product.get("serving_basis") or {}
    lower, upper, _ = resolve_daily_serving_range(dict(product))
    if (len(measures) != 1 or measures[0] is None or measures[0] <= 0
            or not isinstance(basis, Mapping) or not basis.get("servings_per_day_source")
            or lower != upper or lower <= 0):
        return None
    return measures[0] * lower


def strain_assessments_for_match(entry: Mapping, assessment: Mapping) -> list[dict]:
    """Join a generic clinical record to already-reviewed native identities."""
    registry = _clinical_strain_registry()
    return [row for row in assessment["strain_assessments"]
            if row["research_accepted"] and row["status"] not in {
                "strain_context_mismatch", "strain_context_unresolved", "strain_dose_incompatible"}
            and (entry.get("id") == row["clinical_id"] or any(
                clinical_strain_identity_matches(entry.get(field), registry[row["clinical_id"]])
                for field in ("standard_name", "ingredient")))]


def _assess_strain_scope(product: Mapping, row: Mapping, scope: Mapping) -> str:
    """Require a finite, source-backed native-CFU range and explicit label scope.

    This consumes curated applicability in the existing strain registry. A
    caller's adequacy_tier/dose_basis stamp cannot create a reviewed reference.
    Population is label scope, not inferred from marketing or a user's profile.
    """
    low, high = (_number(scope.get(k)) for k in ("minimum_daily_dose", "maximum_daily_dose"))
    def has_text_list(key):
        value = scope.get(key)
        return (isinstance(value, list) and bool(value)
                and all(isinstance(item, str) and item.strip() for item in value))

    if (scope.get("dose_unit") != "CFU" or low is None or high is None
            or low <= 0 or high < low
            or not all(has_text_list(key) for key in (
                "source_pmids", "supported_outcomes", "dosage_forms"))
            or not all(isinstance(scope.get(key), str) and scope[key].strip()
                       for key in ("studied_population", "target_population"))):
        return "strain_dose_reference_unreviewed"
    form = product.get("form_factor_canonical") or product.get("form_factor")
    population = product.get("target_population")
    if not form or not population:
        return "strain_context_unresolved"
    if (_key(form) not in {_key(f) for f in scope["dosage_forms"]}
            or _key(population) != _key(scope["target_population"])):
        return "strain_context_mismatch"
    if not row.get("source_row_ref") or not clinical_strain_matches_source_row(
            product, row, {"raw_source_path": row["source_row_ref"]}):
        return "strain_context_unresolved"
    return "strain_dose_applicable" if low <= _number(row.get("cfu_per_day")) <= high else "strain_dose_incompatible"
