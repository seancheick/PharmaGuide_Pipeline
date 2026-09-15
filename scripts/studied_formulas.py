"""Probiotic clinical identity and whole-formula applicability.

No product ID exceptions, per-strain allocations, or AFU/CFU conversions. A
caller stamp is never authoritative: each consumer proves the label contract.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from clinical_applicability import reviewed_entries
from identity_integrity import has_nonlive_microbial_derivative_evidence
from normalization import normalize_text
from serving_frequency import resolve_daily_serving_range
from probiotic_measurements import (
    strain_cfu_tier, clinical_strain_research_scope, normalized_cfu_count,
    effective_strain_evidence, identity_review_accepted, context_accepted_for_scoring,
    classify_dose_applicability, dose_applicability_credit, DOSE_MEASUREMENT_UNITS,
    clinical_review_provenance_valid, effective_clinical_dose_basis,
)


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


def clinical_strain_identity_key(identity: str) -> str:
    """Shared exact-name key for the cleaner index and downstream identity checks."""
    return _key(normalize_text(identity))


def clinical_strain_identity_matches(identity: object, reference: Mapping) -> bool:
    """Exact registry identity, ignoring punctuation but not species or codes."""
    if not isinstance(identity, str) or not identity.strip():
        return False
    allowed_names = {
        clinical_strain_identity_key(name)
        for name in [reference.get("standard_name"), *reference.get("aliases", [])]
        if isinstance(name, str) and name.strip()
    }
    return clinical_strain_identity_key(identity) in allowed_names


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


def clinical_strain_group_designation(row: Mapping) -> str | None:
    """Read the source row's code-shaped group field, excluding taxonomy/prose."""
    group = row.get("ingredientGroup")
    group_words = re.findall(r"[A-Za-z0-9-]+", group) if isinstance(group, str) else []
    if group_words and all(
        _key(word) in _clinical_strain_code_tokens()
        or word.isdigit()
        or (re.search(r"[A-Za-z]", word) and re.search(r"[0-9]", word))
        for word in group_words
    ):
        return group
    return None


def _clinical_strain_label_forms(row: Mapping) -> set[str] | None:
    """Read only well-shaped source form names; malformed members fail closed."""
    raw_forms = row.get("forms")
    if raw_forms is not None and not isinstance(raw_forms, list):
        return None
    forms = set()
    for form in raw_forms or []:
        value = form.get("name") if isinstance(form, Mapping) else form
        if not isinstance(value, str) or not value.strip():
            return None
        forms.add(value.strip())
    group_code = clinical_strain_group_designation(row)
    if group_code:
        forms.add(group_code)
    return forms


def clinical_strain_identity_from_label(row: Mapping, reference: Mapping) -> str | None:
    """Resolve an exact identity from this label row, never surrounding prose.

    A structured form may complete its owner's species/code or name a full
    strain. Parent tokens must still be an exact prefix of a registry alias;
    a different species or explicit code cannot borrow the form's identity.
    Multiple distinct forms remain unresolved rather than inheriting one dose.
    """
    label = row.get("raw_source_text") or row.get("name")
    forms = _clinical_strain_label_forms(row)
    if forms is None:
        return None
    # DSLD may put the explicit strain code in this same row's structured
    # group field. Taxonomy, categories and notes cannot select a strain.
    group_code = clinical_strain_group_designation(row)
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


def _source_row_representations(owners, ref):
    if not isinstance(ref, str) or not ref:
        return []
    return [owner for owner in owners if owner.get("raw_source_path") == ref]


def probiotic_source_live_eligible(product: Mapping, row: Mapping) -> bool:
    """No representation of this source may contradict live-organism use.

    Keep nonlive representations in the source set: a live-looking duplicate
    must not rescue their identity, denominator membership, or CFU disclosure.
    """
    owners = list(_clinical_label_rows(product.get("activeIngredients")))
    representations = _source_row_representations(owners, row.get("raw_source_path")) or [row]
    return not any(has_nonlive_microbial_derivative_evidence(owner) for owner in representations)


def _source_rows_all_match(owners, ref, predicate):
    """Every actual representation must remain live-eligible and agree."""
    matched = _source_row_representations(owners, ref)
    return bool(matched) and all(
        not has_nonlive_microbial_derivative_evidence(owner) and predicate(owner)
        for owner in matched
    )


def _legacy_label_owner_unique(owners, identity):
    owner_refs = set()
    for owner in owners:
        if clinical_strain_identity_key(str(owner.get("name") or "")) != identity:
            continue
        if has_nonlive_microbial_derivative_evidence(owner):
            return False
        ref = owner.get("raw_source_path")
        if ref is not None and (not isinstance(ref, str) or not ref):
            return False
        owner_refs.add(ref if ref is not None else id(owner))
    return len(owner_refs) == 1


def _label_strain_identity_candidates(row: Mapping) -> list[tuple[str, str, str | None]]:
    """Enumerate printed biological members using the single-strain resolver.

    A one-form view proves physical identity only: it must never be passed to
    the individual-dose gate in place of the original multi-form source row.
    """
    from form_vocab import matches_postbiotic, matches_probiotic_delivery
    from probiotic_measurements import _label_designation_tokens, label_strain_identity_resolution

    registry = _clinical_strain_registry()
    label = row.get("name")
    if not isinstance(label, str) or not clinical_strain_identity_key(label):
        return []

    def resolved(view):
        matches = {cid: identity for cid, reference in registry.items()
                   if (identity := clinical_strain_identity_from_label(view, reference))}
        if len(matches) == 1:
            cid, identity = next(iter(matches.items()))
            return (f"strain:{cid}", identity, cid)
        return None

    whole = resolved(row)
    if whole:
        return [whole]
    forms = _clinical_strain_label_forms(row)
    if forms is None:
        return [(f"label:{clinical_strain_identity_key(label)}", label, None)]
    form_names = {
        clinical_strain_identity_key(value): value
        for value in sorted(forms) if clinical_strain_identity_key(value)
    }
    label_key = clinical_strain_identity_key(label)
    if len(form_names) > 1:
        alternatives = {}
        for form_key, form_name in form_names.items():
            candidate = resolved({**row, "forms": [{"name": form_name}]})
            state = label_strain_identity_resolution(form_name, None, registry)
            if candidate:
                key = candidate[0]
            elif (state["resolution"] == "unresolved_label_text"
                  and not any(clinical_strain_group_designation({"ingredientGroup": code})
                              for code in _label_designation_tokens(form_name)[1])
                  and (matches_probiotic_delivery(form_name) or matches_postbiotic(form_name))):
                continue
            else:
                key = f"label:{label_key}|{form_key}"
                candidate = (key, form_name, None)
            alternatives[key] = candidate
        if alternatives:
            return list(alternatives.values())
    key = "|".join([label_key, *sorted(form_names)])
    return [(f"label:{key}", label, None)]


def label_owned_strain_identities(product: Mapping) -> list[tuple[Mapping, list[tuple[str, str, str | None]]]]:
    """Source rows and identity-only keys, independent of clinical projections.

    This proves identity only, never an individual amount or clinical support.
    A registry ID is returned only when every representation of that source
    proves the same biological member set. Unknown names retain their keys.
    """
    from constants import BLOCKED_PROBIOTIC_STRAINS, HOLD_PROBIOTIC_STRAINS

    owners = list(_clinical_label_rows(product.get("activeIngredients")))
    blocked = BLOCKED_PROBIOTIC_STRAINS | HOLD_PROBIOTIC_STRAINS
    registry = _clinical_strain_registry()

    def permitted(label, cid):
        # A printed alias cannot bypass the policy on its canonical identity.
        names = [label, registry.get(cid, {}).get("standard_name", "")]
        return not any(token in name.lower() for name in names for token in blocked)

    candidates = {id(owner): _label_strain_identity_candidates(owner) for owner in owners}
    result = []
    for owner in owners:
        identities = candidates[id(owner)]
        expected = {key for key, _, _ in identities}
        source_proved = _source_rows_all_match(
            owners, owner.get("raw_source_path"),
            lambda other: {key for key, _, _ in candidates[id(other)]} == expected,
        )
        if owner.get("raw_source_path") is None:
            # Preserve the existing unambiguous exact-name legacy owner path.
            # Forms cannot complete a species without their required source ref.
            source_proved = _legacy_label_owner_unique(
                owners, clinical_strain_identity_key(str(owner.get("name") or "")))
        result.append((owner, [
            (key, label, cid if source_proved and permitted(label, cid) else None)
            for key, label, cid in identities
        ]))
    return result


def clinical_strain_matches_source_row(product: Mapping, clinical: Mapping, row: Mapping) -> bool:
    """Use an actual source owner, or one unambiguous exact legacy label name."""
    owners = list(_clinical_label_rows(product.get("activeIngredients")))
    if "source_row_ref" in clinical:
        ref = clinical["source_row_ref"]
        if not isinstance(ref, str) or not ref or ref != row.get("raw_source_path"):
            return False
        reference = _clinical_strain_registry().get(clinical.get("clinical_id"))
        return bool(reference) and clinical_strain_identity_matches(
            clinical.get("strain"), reference
        ) and _source_rows_all_match(owners, ref, lambda owner:
            clinical_strain_identity_from_label(owner, reference)
            and (not clinical.get("label_name")
                 or _key(clinical["label_name"]) == _key(owner.get("name")))
        )
    identity = _key(normalize_text(str(clinical.get("strain") or "")))
    if not identity or identity != _key(normalize_text(str(row.get("name") or ""))):
        return False
    return _legacy_label_owner_unique(owners, identity)


def consolidated_native_strains(product: Mapping) -> list[dict]:
    """One projection per source/identity, including rejected diagnostic rows.

    Duplicate projections are not independent reviews. Keep agreed fields;
    disputed review metadata fails closed, while physical exclusion flags and
    their explanations survive. Never select a review by input order.
    """
    pdata = product.get("probiotic_data") or product.get("probiotic_detail") or {}
    rows = pdata.get("clinical_strains") if isinstance(pdata, Mapping) else None
    if not isinstance(rows, list):
        return []
    groups = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        cid, ref = row.get("clinical_id"), row.get("source_row_ref")
        if isinstance(cid, str) and cid and (ref is None or isinstance(ref, str)):
            key = (cid, ref, None if ref else _key(row.get("strain")))
        else:
            key = (index,)
        groups.setdefault(key, []).append(row)
    review_fields = {
        "dr_pham_signoff", "review_status", "research_match_status",
        "evidence_scope", "human_evidence", "clinical_support_level",
        "evidence_level", "indication_primary", "source_urls", "source_count",
    }
    result = []
    for group in groups.values():
        first = group[0]
        if all(row == first for row in group):
            result.append(first)
            continue
        fields = set().union(*(row.keys() for row in group))
        conflicts = sorted(k for k in fields if any(
            k not in row or k not in first or row[k] != first[k] for row in group))
        merged = {k: first[k] for k in sorted(fields - set(conflicts))}
        merged["projection_conflict_fields"] = conflicts
        for flag in ("is_blocked", "is_inactivated", "is_postbiotic"):
            if any(row.get(flag) for row in group):
                merged[flag] = True
        for note in ("block_reason", "postbiotic_note"):
            values = sorted({row[note] for row in group
                             if isinstance(row.get(note), str) and row[note]})
            if values:
                merged[note] = "; ".join(values)
        if review_fields.intersection(conflicts) or merged.get("is_blocked"):
            merged.update(review_status="pending_review", dr_pham_signoff=False,
                          research_match_status="rejected" if merged.get("is_blocked") else "pending_review",
                          clinical_support_level=None)
        result.append(merged)
    return result


def label_owned_native_strains(product: Mapping) -> list[dict]:
    """Prove label identities once, independently of clinical-source review.

    An evidence hold does not erase a strain printed on the label. Conversely,
    a registry ID alone cannot supply an identity, an owner or a dose.
    """
    registry = _clinical_strain_registry()
    matched = []
    for row in consolidated_native_strains(product):
        if not isinstance(row.get("clinical_id"), str):
            continue
        reference = registry.get(row["clinical_id"])
        if not reference or row.get("is_blocked"):
            continue
        if not clinical_strain_identity_matches(row.get("strain"), reference):
            continue
        if not clinical_strain_matches_source_row(product, row, {
            "raw_source_path": row.get("source_row_ref"), "name": row.get("strain")
        }):
            continue
        matched.append(row)
    return matched


def independent_clinical_strains(product: Mapping) -> list[dict]:
    """Admit only label identities backed by current independent review."""
    registry = _clinical_strain_registry()
    independent = []
    for row in label_owned_native_strains(product):
        reference = registry[row["clinical_id"]]
        thresholds = reference.get("cfu_thresholds") or {}
        evidence = effective_strain_evidence(reference) or {}
        validation = evidence.get("clinical_validation") or {}
        # Specificity is not review completion or strength. Preserve previously
        # reviewed contextual research while its scope is being curated, without
        # accepting a caller's unknown-scope stamp against a resolved reference.
        allowed_match_statuses = {"exact_strain", "species_level"}
        if clinical_strain_research_scope(reference)["evidence_scope"] == "scope_unresolved":
            allowed_match_statuses.add("scope_unresolved")
        if (not identity_review_accepted(reference)
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
    pdata = product.get("probiotic_data")
    if isinstance(pdata, Mapping):
        product = {**product, "probiotic_data": {
            **pdata, "clinical_strains": consolidated_native_strains(product)}}
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
        evidence = effective_strain_evidence(reference) or {}
        support = evidence.get("clinical_support_level") or evidence.get("evidence_strength") or "weak"
        support = {"strong": "high", "medium": "moderate"}.get(support, support)
        result = {"clinical_id": row.get("clinical_id"), "strain": row.get("strain"),
                  "source_row_ref": row.get("source_row_ref"), "dose_applicable": False,
                  "cfu_per_day": _owned_daily_cfu(product, row),
                  "support_level": support, "research_accepted": id(row) in accepted,
                  "indication_primary": thresholds.get("indication_primary"),
                  "indication_secondary": thresholds.get("indication_secondary"),
                  "effect_direction": evidence.get("effect_direction"),
                  "source_pmids": [p for p in [evidence.get("pmid"), *evidence.get("additional_pmids", [])] if p],
                  "supported_outcomes": [], "studied_population": None}
        result.update(clinical_strain_research_scope(reference))
        # Point-producing reference provenance is distinct from the inventory
        # of known research. Newly found sources do not inherit its approval.
        result["scoring_source_pmids"] = list(result["source_pmids"])
        result["study_contexts"] = _assess_native_study_contexts(product, row, reference)
        result["source_pmids"] = sorted(set(result["source_pmids"]) | {
            pmid for context in result["study_contexts"]
            if context.get("status") == "source_context_recorded"
            for pmid in context["source_pmids"]})
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
        elif any(c.get("clinical_applicability") == "established" for c in result["study_contexts"]):
            # The bridge: an approved exact-strain context, the label's owned
            # daily dose on a tested arm, a positive primary patient-important
            # outcome. Identity review (above) is still required first.
            status = "strain_dose_applicable"
        elif any(context_accepted_for_scoring(c) and c.get("status") == "source_context_recorded"
                 for c in result["study_contexts"]):
            status = "strain_context_not_applicable"
        elif result["study_contexts"] or "study_contexts" in reference:
            # Pending or held contexts are not clinician-approved scoring
            # policies. A legacy universal range cannot bypass their review.
            status = "strain_context_review_pending"
        else:
            # Retired universal min/max blocks cannot establish an outcome,
            # regimen or combination policy. The source-context model is the
            # only native path; no approved outcome policy is authored yet.
            status = "strain_dose_reference_unreviewed"
        result["status"] = status
        result["industry_adequacy_tier"] = strain_cfu_tier(
            result["cfu_per_day"], thresholds.get("tiers_cfu_per_day"))
        result["dose_applicable"] = status == "strain_dose_applicable"
        result["dose_applicability_credit"] = max(
            [float(c.get("dose_applicability_credit") or 0.0) for c in result["study_contexts"]
             if c.get("clinical_applicability") == "established"], default=0.0)
        results.append(result)
    context_ids = sorted({context["context_id"] for row in results
        for context in row["study_contexts"]
        if context.get("status") == "source_context_recorded"
        and context.get("dose_comparison") not in {
            "identity_owner_unresolved", "organism_preparation_mismatch"}})
    return {"formula_assessment": formula, "strain_assessments": results,
            "native_context_review": {
                "status": "pending_clinical_review" if context_ids else "not_curated",
                "context_ids": context_ids}}


NATIVE_CONTEXT_REVIEW_STATUSES = frozenset({
    "source_verified_pending_clinical_review",  # authored, PMIDs verified, no approval
    "clinician_approved",                        # the only status that can score
    "adjudication_required",                     # conflicting sources; held
    "rejected_source",                           # excluded from research entirely
})
NATIVE_CONTEXT_QUALITY_ENUMS = {
    "study_design": frozenset({"rct", "crossover_rct", "cluster_rct", "open_label",
                               "observational", "meta_analysis", "systematic_review",
                               "guideline", "case_series"}),
    "blinding": frozenset({"double", "triple", "single", "open", "unreported"}),
    "funding": frozenset({"industry", "independent", "mixed", "unreported"}),
    "source_tier": frozenset({"A", "B", "C", "D", "E"}),
}


def valid_native_study_context(context: Mapping, reference_id: str) -> bool:
    """Validate a registry context and any claimed clinical approval."""
    if not isinstance(context, Mapping):
        return False

    def text_list(value, *, allow_empty=False):
        return isinstance(value, list) and (allow_empty or bool(value)) and all(
            isinstance(item, str) and item.strip() for item in value)

    if (not all(isinstance(context.get(key), str) and context[key].strip()
                for key in ("context_id", "condition", "trial_family"))
            or context.get("review_status") not in NATIVE_CONTEXT_REVIEW_STATUSES
            or not text_list(context.get("source_pmids"))
            or not text_list(context.get("components"))
            or reference_id not in context["components"]
            or not set(context["components"]) <= set(_clinical_strain_registry())
            or context.get("identity_scope") not in ("exact_strain", "species_general", "combination")
            or context.get("purpose") not in ("prevention", "treatment", "challenge", "physiology")
            or not text_list(context.get("limitations"))):
        return False
    # New curation batches opt into the single frozen evidence contract.  Keep
    # legacy contexts readable while making every newly stamped context pass
    # the stricter vocabulary and semantic checks in one shared module. The
    # shape checks above run first so a malformed record fails closed here
    # instead of raising inside those checks.
    if context.get("context_schema_version") is not None:
        from clinical_evidence_schema import validate_frozen_context

        if validate_frozen_context(
            context,
            known_component_ids=set(_clinical_strain_registry()),
        ):
            return False
    eligible = context.get("scoring_eligible")
    if eligible is not None and not isinstance(eligible, bool):
        return False
    if (context.get("review_status") == "clinician_approved"
            and not clinical_review_provenance_valid(context)):
        return False
    components = context["components"]
    if (len(set(components)) != len(components)
            or (len(components) > 1) != (context["identity_scope"] == "combination")):
        return False
    # Optional study-quality descriptors: validated when present, never scored.
    for key, allowed in NATIVE_CONTEXT_QUALITY_ENUMS.items():
        if key in context and context[key] is not None and context[key] not in allowed:
            return False
    if "sample_size" in context and context["sample_size"] is not None and (
            isinstance(context["sample_size"], bool) or not isinstance(context["sample_size"], int)
            or context["sample_size"] <= 0):
        return False
    for key in ("trial_registration", "comparator"):
        if key in context and context[key] is not None and not (
                isinstance(context[key], str) and context[key].strip()):
            return False
    population, dose, outcomes = (context.get(k) for k in ("population", "dose", "outcomes"))
    if (not isinstance(population, Mapping)
            or population.get("age_group") not in ("adult", "child", "infant", "mixed", "unknown")
            or not isinstance(population.get("description"), str) or not population["description"].strip()
            or not isinstance(dose, Mapping)
            or effective_clinical_dose_basis(dose) not in (
                "discrete_daily_arms", "measured_viability", "single_challenge",
                "unresolved", "not_applicable", "combination_total_daily")
            or (dose.get("measurement_type") or "viable_count") not in DOSE_MEASUREMENT_UNITS
            or dose.get("unit") not in DOSE_MEASUREMENT_UNITS[dose.get("measurement_type") or "viable_count"]
            or not isinstance(dose.get("values"), list)
            or any(_number(v) is None or _number(v) <= 0 for v in dose["values"])
            or (effective_clinical_dose_basis(dose) == "discrete_daily_arms"
                and context.get("identity_scope") != "combination"
                and not dose["values"]
                and dose.get("dose_status") != "extraction_pending")
            or (effective_clinical_dose_basis(dose) == "unresolved" and dose["values"])
            or not text_list(dose.get("dosage_forms"), allow_empty=True)
            or not text_list(dose.get("co_therapies"), allow_empty=True)):
        return False
    duration = dose.get("duration_days")
    if duration is not None and (_number(duration) is None or _number(duration) <= 0):
        return False
    if not isinstance(outcomes, list) or not outcomes:
        return False
    return all(isinstance(outcome, Mapping)
        and isinstance(outcome.get("name"), str) and outcome["name"].strip()
        and outcome.get("hierarchy") in ("primary", "secondary", "post_hoc", "guideline", "unresolved")
        and outcome.get("kind") in ("patient_important", "surrogate", "evidence_ranking")
        and outcome.get("direction") in ("positive", "mixed", "null", "negative", "unresolved")
        for outcome in outcomes)


def _native_study_contexts(reference: Mapping) -> list:
    """One authored record per study context; combinations join by explicit IDs."""
    contexts = reference.get("study_contexts", [])
    if not isinstance(contexts, list):
        return [None]
    contexts = list(contexts)
    reference_id = reference.get("id")
    if not reference_id:
        return contexts
    for other in _clinical_strain_registry().values():
        if other.get("id") == reference_id:
            continue
        others = other.get("study_contexts", [])
        if not isinstance(others, list):
            continue
        for context in others:
            if (isinstance(context, Mapping)
                    and isinstance(context.get("components"), list)
                    and reference_id in context["components"]):
                contexts.append(context)
    return contexts


def _assess_native_study_contexts(product: Mapping, row: Mapping, reference: Mapping) -> list[dict]:
    """Compare label facts to studies through the existing identity/dose owner.

    Keep findings per outcome/trial. Marketing cannot establish a diagnosis,
    treatment duration, antibiotic co-therapy or lactose challenge. A matching
    amount therefore does not imply outcome applicability or patient benefit.
    """
    contexts = _native_study_contexts(reference)
    result = []
    for context in contexts:
        if not valid_native_study_context(context, reference.get("id")):
            result.append({"status": "invalid_context", "clinical_applicability": "not_established"})
            continue
        if context["review_status"] == "rejected_source":
            # A rejected source is not research; its PMIDs never join the inventory.
            result.append({"context_id": context["context_id"], "status": "rejected_source",
                           "review_status": "rejected_source",
                           "clinical_applicability": "not_established"})
            continue
        dose = context["dose"]
        owned = clinical_strain_matches_source_row(product, row, {
            "raw_source_path": row.get("source_row_ref"), "name": row.get("strain")})
        amount = _owned_daily_cfu(product, row) if owned else None
        if not owned:
            comparison = "identity_owner_unresolved"
        elif row.get("is_inactivated") or row.get("is_postbiotic"):
            comparison = "organism_preparation_mismatch"
        elif context["identity_scope"] == "combination":
            comparison = "combination_not_individual_dose"
        elif context["identity_scope"] == "species_general":
            comparison = "species_not_exact_strain"
        elif (context["dose"].get("measurement_type") or "viable_count") != "viable_count":
            # Spore counts and other non-CFU measurements are not interchangeable
            # with a label-owned CFU dose. Keep the source context visible, but
            # never let a numeric coincidence establish applicability.
            comparison = "study_dose_not_viable_count"
        elif effective_clinical_dose_basis(dose) != "discrete_daily_arms":
            comparison = "study_daily_dose_unresolved"
        elif not dose.get("values"):
            # A canonical per-strain dose can be explicitly pending extraction;
            # an empty arm list is unresolved, not evidence that the label is
            # outside the studied range.
            comparison = "study_daily_dose_unresolved"
        elif amount is None:
            comparison = "label_dose_unknown"
        else:
            # The same classifier that awards credit decides the wording, so a
            # float-rounded label amount cannot read "outside" while scoring EXACT.
            comparison = classify_dose_applicability(amount, dose)[1]
        population = _key(product.get("target_population"))
        study_population = context["population"]["age_group"]
        population_comparison = (
            "label_population_unknown" if not population or study_population in {"unknown", "mixed"}
            else "same_broad_age_group" if population == _key(study_population)
            else "different_label_population")
        form = _key(product.get("form_factor_canonical") or product.get("form_factor"))
        delivery_comparison = (
            "delivery_unknown" if not form or not dose["dosage_forms"]
            else "same_delivery_form" if form in {_key(f) for f in dose["dosage_forms"]}
            else "different_delivery_form")
        if owned and not (row.get("is_inactivated") or row.get("is_postbiotic")) \
                and context["identity_scope"] == "exact_strain":
            applicability_class, class_reason = classify_dose_applicability(amount, dose)
        else:
            applicability_class, class_reason = "DOSE_UNKNOWN", comparison
        applicability, reason, credit = _accepted_context_applicability(
            context, applicability_class, class_reason)
        result.append({**deepcopy(context), "status": "source_context_recorded",
            "dose_comparison": comparison, "label_daily_cfu": amount,
            "dose_applicability_class": applicability_class,
            "dose_applicability_credit": credit,
            "source_row_ref": row.get("source_row_ref"),
            "population_comparison": population_comparison,
            "delivery_comparison": delivery_comparison,
            "clinical_applicability": applicability,
            "applicability_reason": reason})
    return result


def _accepted_context_applicability(context: Mapping, applicability_class: str,
                                    class_reason: str) -> tuple[str, str, float]:
    """Only an attributable clinician-approved exact-strain context whose tested arm
    exactly matches the label's owned daily dose and that
    has a positive primary patient-important outcome establishes applicability.
    Everything else is recorded with the reason it does not."""
    if not context_accepted_for_scoring(context):
        return "not_established", "context_not_clinician_approved", 0.0
    if context["identity_scope"] != "exact_strain":
        return "not_established", "not_individual_strain_scope", 0.0
    credit = dose_applicability_credit(applicability_class)
    if credit <= 0.0:
        return "not_established", class_reason, 0.0
    if not any(o["hierarchy"] == "primary" and o["kind"] == "patient_important"
               and o["direction"] == "positive" for o in context["outcomes"]):
        return "not_established", "no_positive_primary_patient_important_outcome", 0.0
    return "established", "clinician_approved_context_dose_and_outcome_match", credit


def measured_native_strain_doses(product: Mapping) -> list[dict]:
    """Label-owned daily potency, not clinical applicability or source approval."""
    registry = _clinical_strain_registry()
    measured = []
    for row in label_owned_native_strains(product):
        daily_range = _owned_daily_cfu_range(product, row)
        cfu = daily_range[0] if daily_range is not None else None
        thresholds = registry[row["clinical_id"]].get("cfu_thresholds") or {}
        measured.append({"clinical_id": row["clinical_id"], "strain": row["strain"],
            "source_row_ref": row.get("source_row_ref"), "cfu_per_day": cfu,
            "maximum_cfu_per_day": daily_range[1] if daily_range is not None else None,
            "adequacy_tier": strain_cfu_tier(cfu, thresholds.get("tiers_cfu_per_day")),
            "is_inactivated": bool(row.get("is_inactivated")),
            "is_postbiotic": bool(row.get("is_postbiotic"))})
    return measured


def _owned_daily_cfu(product: Mapping, row: Mapping) -> float | None:
    """A discrete daily dose for trial applicability; a range is not one dose."""
    daily_range = _owned_daily_cfu_range(product, row)
    if daily_range is None or daily_range[0] != daily_range[1]:
        return None
    return daily_range[0]


def _owned_daily_cfu_range(product: Mapping, row: Mapping) -> tuple[float, float] | None:
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
    measures = set()
    for blend in blends:
        if not isinstance(blend, Mapping) or blend.get("raw_source_path") != ref:
            continue
        measure = blend.get("cfu_data") or {}
        if (len(blend.get("strains") or []) != 1 or not isinstance(measure, Mapping)
                or _key(normalize_text(str(blend["strains"][0]))) != _key(normalize_text(
                    str(row.get("label_name") or row.get("strain") or "")))
                or measure.get("raw_source_path") != ref
                or measure.get("evidence_scope") != "row_level"):
            return None
        measures.add(normalized_cfu_count(measure) if measure.get("has_cfu") is True else None)
    basis = product.get("serving_basis") or {}
    lower, upper, _ = resolve_daily_serving_range(dict(product))
    if (len(measures) != 1 or None in measures
            or not isinstance(basis, Mapping) or not basis.get("servings_per_day_source")
            or lower <= 0):
        return None
    amount = next(iter(measures))
    minimum, maximum = _number(amount * lower), _number(amount * upper)
    return (minimum, maximum) if minimum is not None and maximum is not None else None


def strain_assessments_for_match(entry: Mapping, assessment: Mapping) -> list[dict]:
    """Join a generic clinical record to already-reviewed native identities."""
    registry = _clinical_strain_registry()
    return [row for row in assessment["strain_assessments"]
            if row["research_accepted"] and row["status"] not in {
                "strain_context_mismatch", "strain_context_unresolved", "strain_dose_incompatible"}
            and (entry.get("id") == row["clinical_id"] or any(
                clinical_strain_identity_matches(entry.get(field), registry[row["clinical_id"]])
                for field in ("standard_name", "ingredient")))]
