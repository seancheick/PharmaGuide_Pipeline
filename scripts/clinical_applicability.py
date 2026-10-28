"""Apply reviewed clinical scope at one boundary shared by all score consumers.

Matching a nutrient name does not transfer a lozenge trial to a capsule, or a
combination trial to one constituent. The reference registry owns restrictions;
an old enriched match cannot broaden them by carrying a stale success stamp.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from clinical_evidence_schema import is_reference_only
from constants import DELIVERY_SOURCE_STATEMENT_TYPES
from normalization import canonicalize_mass_unit, find_affirmative_label_match, normalize_text
from serving_frequency import resolve_daily_serving_range


# Milligrams per canonical mass token. Spelling is the pipeline's business:
# ``canonicalize_mass_unit`` owns every alias (DSLD's "Gram(s)", the enricher's
# "gram(s)", "Milligram(s)", "µg"...), so this module keeps no unit map of its own.
_MG_PER_CANONICAL_UNIT = {"g": 1000.0, "mg": 1.0, "mcg": 0.001}


def _mass_unit_scale(unit: Any) -> float | None:
    """Milligrams per one unit, or None for anything that is not a mass unit."""
    if not isinstance(unit, str) or not unit.strip():
        return None
    return _MG_PER_CANONICAL_UNIT.get(canonicalize_mass_unit(unit))


@lru_cache(maxsize=1)
def reviewed_entries() -> dict[str, dict]:
    payload = json.loads((Path(__file__).parent / "data/backed_clinical_studies.json").read_text())
    return {entry["id"]: entry for entry in payload["backed_clinical_studies"]}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _row_text(row: Mapping, *, source_only: bool = False, preserve_punctuation: bool = False) -> str:
    if source_only:
        label = row.get("raw_source_text") or row.get("source_label_name")
        if not isinstance(label, str) or not label.strip():
            return ""
        values = [label]
        # Only the cleaner's own source taxonomy may extend the label words: a
        # source-required scope distrusts enrichment-derived form names, so a
        # row without source taxonomy contributes its printed label text alone.
        taxonomy = row.get("raw_taxonomy")
        source_forms = taxonomy.get("forms") if isinstance(taxonomy, Mapping) else None
        forms = source_forms if isinstance(source_forms, list) else []
    else:
        values = [row.get(k) for k in ("name", "raw_source_text", "matched_form", "form_id")]
        forms = row.get("forms")
    if isinstance(forms, list):
        values.extend(f.get("name") for f in forms if isinstance(f, Mapping))
    # Parent/source notation is one linked label assertion: Zinc (as acetate)
    # is zinc acetate. Never assemble this from different ingredient rows.
    text = " ".join(str(v) for v in values if v)
    if preserve_punctuation:
        return text
    return " " + _key(text).replace(" as ", " ") + " "


def _is_exposure_row(row: Mapping) -> bool:
    """Exclude explicit non-exposures without imposing new legacy contracts."""
    if row.get("score_eligible_by_cleaner") is False:
        return False
    if _key(row.get("source_section") or row.get("source")) in {
        "inactive", "inactiveingredients", "other ingredients"
    }:
        return False
    roles = {_key(row.get(field)) for field in ("cleaner_row_role", "role_classification")}
    if roles & {"source descriptor", "inactive", "inactive non scorable", "recognized non scorable"}:
        return False
    return _key(row.get("dose_class")) != "source material mass"


def _evidence_subject_refs(product: Mapping, *, include_undosed: bool = False,
                           include_anchor_lineage: bool = False) -> set:
    """Label rows projected by the one Evidence-subject provider.

    Clinical applicability consumes the provider's decision and never rebuilds
    subject eligibility from cleaner roles or display rows.
    """
    iqd = product.get("ingredient_quality_data")
    if not isinstance(iqd, Mapping) or not isinstance(iqd.get("ingredients_scorable"), list):
        return set()
    from scoring_input_contract import get_evidence_subject_rows
    refs = set()
    for row in get_evidence_subject_rows(product):
        anchor = row.get("scoring_input_kind") == "product_level_evidence"
        if not (include_undosed or anchor):
            continue
        candidates = [row.get("raw_source_path")]
        if (include_undosed or include_anchor_lineage) and anchor:
            # The shared provider already records the exact printed lineage
            # behind an anchor. Admit those source rows for Evidence only;
            # their blend total remains unavailable as a member dose.
            candidates.extend(row.get("linked_rows") or [])
        refs.update(ref for ref in candidates if isinstance(ref, str) and ref.strip())
    return refs


def _valid_policy(policy: Any) -> bool:
    """Validate reviewed constraints before any matching or numeric comparisons."""
    if not isinstance(policy, Mapping) or not isinstance(policy.get("scope"), str):
        return False
    if "studied_population" in policy and not isinstance(policy["studied_population"], str):
        return False
    for field in ("dosage_forms", "required_form_terms", "supported_outcomes", "source_pmids",
                  "excluded_canonical_ids", "excluded_form_terms", "excluded_claim_terms"):
        if field in policy and (
            not isinstance(policy[field], list)
            or any(not isinstance(value, str) or not value.strip() for value in policy[field])
        ):
            return False
        if field in {"excluded_canonical_ids", "excluded_form_terms", "excluded_claim_terms"} and any(
            not _key(value) for value in policy.get(field, [])
        ):
            return False
    if "require_source_label_form" in policy and not isinstance(policy["require_source_label_form"], bool):
        return False
    if policy.get("require_source_label_form") and not policy.get("required_form_terms"):
        return False
    bounds = []
    for field in ("minimum_daily_dose", "maximum_daily_dose"):
        value = _number(policy[field]) if field in policy else None
        if field in policy and (value is None or value <= 0):
            return False
        bounds.append(value)
    if all(value is not None for value in bounds) and bounds[0] > bounds[1]:
        return False
    if "dose_unit" in policy or any(value is not None for value in bounds):
        if _mass_unit_scale(policy.get("dose_unit")) is None:
            return False
    return True


def _resolved_identity_by_ref(product: Mapping) -> dict:
    """Resolved form and shared Evidence identity at an exact label reference.

    The same printed row reaches this module twice: once as the label projection
    (``activeIngredients``) and once as the enriched projection, which is the only
    one carrying ``form_id``/``matched_form``. Deduplication keeps the label copy,
    so a reviewed scope that names a material ("Petadolex") could never see it.
    """
    resolved: dict = {}
    iqd = product.get("ingredient_quality_data") or {}
    if not isinstance(iqd, Mapping):
        return resolved
    for rows in (iqd.get("ingredients_scorable"), iqd.get("ingredients")):
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            ref = row.get("raw_source_path") or row.get("source_row_ref")
            if not isinstance(ref, str) or not ref.strip() or ref in resolved:
                continue
            identity = {key: row.get(key) for key in ("form_id", "matched_form") if row.get(key)}
            if identity:
                resolved[ref] = identity
    from scoring_input_contract import get_evidence_subject_rows
    subject_ids: dict[str, set[str]] = {}
    for row in get_evidence_subject_rows(product):
        ref, canonical = row.get("raw_source_path"), row.get("canonical_id")
        if isinstance(ref, str) and ref.strip() and canonical:
            subject_ids.setdefault(ref, set()).add(canonical)
    for ref, identities in subject_ids.items():
        if len(identities) == 1:
            # The subject provider already resolved this label identity. Carry
            # only identity, never its projected blend/member amount.
            resolved.setdefault(ref, {})["canonical_id"] = next(iter(identities))
    return resolved


def _rows(product: Mapping, *, source_only: bool = False, evidence_only: bool = False):
    seen = set()
    # A source-required scope distrusts enrichment-derived names, so it never
    # receives them; every other scope reads the identity enrichment resolved.
    resolved = {} if source_only else _resolved_identity_by_ref(product)
    subject_refs = _evidence_subject_refs(product, include_undosed=evidence_only)
    anchor_refs = _evidence_subject_refs(product, include_anchor_lineage=True)

    def walk(rows):
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            ref = row.get("raw_source_path") or row.get("source_row_ref")
            valid_reference = not source_only or (isinstance(ref, str) and bool(ref.strip()))
            identity = (ref, row.get("name"), str(row.get("quantity")), row.get("unit"))
            exposure = _is_exposure_row(row)
            # A projected Evidence subject is excused only from the cleaner's
            # score eligibility (a header total); its printed mass is the
            # blend's, never a member's amount, so it carries no dose here.
            source_veto = (row.get("score_eligible_by_cleaner") is False
                           and ref not in anchor_refs
                           and _key(row.get("cleaner_row_role")) != "nested display only"
                           and _is_exposure_row({**row, "score_eligible_by_cleaner": None}))
            projected = (not exposure and not source_veto and ref in subject_refs
                         and (evidence_only or _is_exposure_row(
                             {**row, "score_eligible_by_cleaner": None})))
            if valid_reference and identity not in seen and (exposure or projected):
                seen.add(identity)
                # Raw and resolved projections may use different canonical
                # namespaces for this exact row. The subject provider owns the
                # Evidence identity; label text, form and amount remain local.
                identity_fields = {key: value for key, value in (resolved.get(ref) or {}).items()
                                   if key == "canonical_id" or not row.get(key)}
                if projected:
                    identity_fields["quantity"] = None
                yield {**row, **identity_fields} if identity_fields else row
            yield from walk(row.get("nestedIngredients"))

    originals = product.get("activeIngredients") or []
    yield from walk(originals)
    # Source-required scopes cannot replace an original owner with a generated
    # row, even when the generated row has a different or missing reference.
    if source_only and any(isinstance(row, Mapping) for row in originals):
        return
    iqd = product.get("ingredient_quality_data") or {}
    yield from walk(iqd.get("ingredients_scorable") or iqd.get("ingredients"))


def _linked_rows(product: Mapping, entry: Mapping, *, source_only: bool = False, evidence_only: bool = False,
                 discriminating_terms: Any = ()):
    source_refs = entry.get("matched_source_row_refs")
    if source_refs is not None and (
        not isinstance(source_refs, list)
        or any(not isinstance(ref, str) or not ref.strip() for ref in source_refs)
    ):
        return []
    refs = set(source_refs or [])
    name = _key(entry.get("ingredient") or entry.get("matched_term"))
    canonicals = {_key(c) for c in entry.get("matched_canonical_ids") or []}
    if entry.get("matched_canonical_id"):
        canonicals.add(_key(entry["matched_canonical_id"]))
    rows = list(_rows(product, source_only=source_only, evidence_only=evidence_only))
    if refs:
        exact_refs = [r for r in rows if (r.get("raw_source_path") or r.get("source_row_ref")) in refs]
        if evidence_only:
            # A provider-owned blend anchor references its parent panel row.
            # Bind only its unique named/canonical child, never the sibling
            # materials or the parent's mass. Dose keeps exact exposure refs.
            from scoring_input_contract import get_evidence_subject_rows
            anchors = [r for r in get_evidence_subject_rows(product)
                       if r.get("raw_source_path") in refs
                       and r.get("scoring_input_kind") == "product_level_evidence"
                       and _key(r.get("canonical_id")) in canonicals
                       and name in {_key(r.get("name")), _key(r.get("raw_source_text"))}]
            if len(anchors) == 1:
                anchor = anchors[0]
                anchor_ref = anchor.get("raw_source_path")
                linked = anchor.get("linked_rows") or []
                children = [r for r in rows
                            if (r.get("raw_source_path") != anchor_ref
                                and (r.get("parent_source_path") == anchor_ref
                                     or r.get("raw_source_path") in linked))
                            and _key(r.get("canonical_id")) in canonicals
                            and name in {_key(r.get("name")), _key(r.get("raw_source_text"))}]
                if len(children) == 1:
                    return children
        return exact_refs
    exact = [r for r in rows if name and name in {_key(r.get("name")), _key(r.get("raw_source_text"))}]
    if exact:
        return exact
    if source_only:
        # Legacy source-required matches may use an exact referenced label
        # owner, but a canonical guess is not preparation/source evidence.
        return []
    # Legacy boundary only: one canonical row is unambiguous. Multiple forms of
    # the same nutrient may not lend their amount to an unmatched source form.
    candidates = [r for r in rows if _key(r.get("canonical_id")) in canonicals]
    if len(candidates) == 1:
        return candidates
    if not candidates:
        return []
    # Several owned rows: resolve only when the reviewed scope itself names the
    # material and exactly one row carries it (Petadolex beside a plain petasins
    # row). Anything the scope cannot tell apart stays unresolved.
    terms = [term for term in (discriminating_terms or []) if isinstance(term, str) and term.strip()]
    if not terms:
        return []
    discriminated = [row for row in candidates
                     if any(" " + _key(term) + " " in _row_text(row) for term in terms)]
    return discriminated if len(discriminated) == 1 else []


def _source_delivery_forms(product: Mapping, row: Mapping, excluded_terms=(), *, product_level: bool = False) -> set[str]:
    """Consume delivery-owner provenance, never infer coating from form guesses.

    Row-local evidence stays on that row. Product-level coating can bind an
    unambiguous sole active; mixed products need row-local delivery evidence.
    A stale marker must still be present in the retained label source.
    Product-level quality checks may consume a whole-product carrier claim;
    preparation-specific clinical callers retain the default sole-active scope.
    """
    result = set()
    originals = [r for r in _rows(product, source_only=True) if _is_exposure_row(r)]
    if len(originals) == 1 and originals[0].get("raw_source_path") == row.get("raw_source_path"):
        # A sole-active product's explicitly excluded delivery cannot be
        # rescued by a positive coating marker in a different source field.
        context = [product.get(key) for key in ("name", "fullName", "productName", "physicalState", "netContents")]
        context.extend(statement.get("notes") for statement in product.get("statements") or []
                       if isinstance(statement, Mapping) and statement.get("type") in DELIVERY_SOURCE_STATEMENT_TYPES)
        text = " " + _key(json.dumps(context)) + " "
        if any(" " + _key(term) + " " in text for term in excluded_terms):
            return result
    for system in (product.get("delivery_data") or {}).get("systems", []):
        if not isinstance(system, Mapping):
            continue
        marker, source = str(system.get("raw_source_text") or ""), system.get("match_source")
        if not marker or not isinstance(source, str):
            continue
        source_text = ""
        match = re.fullmatch(r"activeIngredients\[(\d+)\]", source)
        if source == row.get("raw_source_path"):
            source_text = _row_text(row, source_only=True, preserve_punctuation=True)
            if product_level:
                # Delivery extraction also retains this same label row's notes.
                # Quality can use that assertion without borrowing another row.
                source_text += " " + str(row.get("notes") or "")
        elif match:
            active = product.get("activeIngredients") or []
            index = int(match.group(1))
            if index < len(active) and isinstance(active[index], Mapping):
                original = active[index]
                if original.get("raw_source_path") == row.get("raw_source_path"):
                    source_text = _row_text(original, source_only=True, preserve_punctuation=True)
        elif product_level or (len(originals) == 1 and originals[0].get("raw_source_path") == row.get("raw_source_path")):
            match = re.fullmatch(r"statements\[(\d+)\]", source)
            if match:
                statements = product.get("statements") or []
                index = int(match.group(1))
                if (index < len(statements) and isinstance(statements[index], Mapping)
                        and statements[index].get("type") in DELIVERY_SOURCE_STATEMENT_TYPES):
                    source_text = str(statements[index].get("notes") or "")
            elif source in {"name", "fullName", "productName"}:
                source_text = str(product.get(source) or "")
            elif source == "physical_state":
                source_text = json.dumps(product.get("physicalState") or {})
            elif re.fullmatch(r"netContents\[\d+\]", source):
                source_text = json.dumps(product.get("netContents") or [])
        normalized_source = " " + _key(source_text) + " "
        if any(" " + _key(term) + " " in normalized_source for term in excluded_terms):
            continue
        marker_pattern = re.compile(r"(?<!\w)" + re.escape(marker) + r"(?!\w)", re.I)
        if not marker_pattern.search(source_text):
            continue
        # raw_source_text is the retained source field, often several clauses,
        # rather than the matched delivery token. Validate provenance above,
        # then apply the shared negation matcher to the actual delivery terms.
        from scoring_v4.modules.generic_helpers import _delivery_definitions, _delivery_patterns

        name = str(system.get("canonical_name") or system.get("name") or "").lower().strip()
        definition = _delivery_definitions().get(name)
        if not isinstance(definition, Mapping):
            continue
        patterns = _delivery_patterns([name, *(definition.get("aliases") or [])])
        if any(find_affirmative_label_match(pattern, marker)
               and find_affirmative_label_match(pattern, source_text) for pattern in patterns):
            result.add(_key(name))
    return result


def native_product_positioning_texts(product: Mapping) -> list[str]:
    """Retained native label positioning, shared by category and exact scope checks."""
    parts = [str(product.get(field) or "") for field in
             ("product_name", "brand_name", "serving_description", "suggested_use")]
    if not product.get("product_name"):
        parts.append(str(product.get("fullName") or ""))
    for statement in product.get("statements") or []:
        if isinstance(statement, Mapping) and _key(statement.get("type")) in {
            "general statements all other content", "formula re type", "formulation re other",
        }:
            parts.append(str(statement.get("notes") or statement.get("text") or ""))
    return parts



def _excluded_claim_matches(product: Mapping, policy: Mapping) -> bool:
    """Match only affirmative label positioning, never warnings or metadata."""
    excluded = {str(product.get("brand_name") or ""), str(product.get("serving_description") or "")}
    for term in policy.get("excluded_claim_terms", []):
        pattern = re.compile(r"(?<!\w)" + r"[\s_-]+".join(
            re.escape(word) for word in _key(term).split()) + r"(?!\w)", re.I)
        if any(text and text not in excluded and find_affirmative_label_match(pattern, text)
               for text in native_product_positioning_texts(product)):
            return True
    return False


def _valid_native_claim_scope(context: Mapping) -> bool:
    """The approved native extension carries exclusions, not new dose rules."""
    policy = context.get("applicability")
    sources = context.get("source_pmids")
    return bool(
        _valid_policy(policy) and policy.get("scope") == "ingredient"
        and context.get("purpose") in {"treatment", "challenge"}
        and set(policy) <= {"scope", "source_pmids", "excluded_claim_terms"}
        and policy.get("excluded_claim_terms") and policy.get("source_pmids")
        and isinstance(sources, list)
        and all(isinstance(source, str) for source in sources)
        and set(policy["source_pmids"]) <= set(sources)
    )


_CREDITABLE_CLAIM_STATES = {"absent", "aligned", "mixed"}
# The shared affirmative matcher's rule: a negation earlier in the clause
# negates what follows it ("Not for children", "free of soy").
_POSITIONING_NEGATION = re.compile(r"\b(?:no|not|without|avoid|free\s+(?:of|from))\b", re.I)


# Who a product is for is population targeting, judged against the studied
# population; it is never a claimed outcome ("Baby Probiotic", "Women's Multi").
_POPULATION_WORDS = re.compile(
    r"\b(?:infants?|bab(?:y|ies)|pediatric|child(?:ren)?|kids?|toddlers?|preterm|neonat\w*|"
    r"prenatal|pregnan\w*|maternal|postnatal|postpartum|wom[ae]n'?s?|female|men'?s?|male)\b", re.I)


def _claimed_purposes(text: str) -> set[str]:
    from evidence_resolver import evidence_indication_categories
    return evidence_indication_categories(_POPULATION_WORDS.sub(" ", text))


def native_product_positioning_categories(product: Mapping, *, purposes_only: bool = False) -> set[str]:
    """Indication categories of the label's affirmative product positioning.

    Brand and serving metadata, negated clauses and precaution blocks are not
    a marketed purpose. Generic class words ("probiotic") are not a claim.
    ``purposes_only`` drops population words, which describe targeting.
    """
    from evidence_resolver import evidence_indication_categories
    categorize = _claimed_purposes if purposes_only else evidence_indication_categories
    excluded = {str(product.get("brand_name") or ""), str(product.get("serving_description") or "")}
    categories: set[str] = set()
    for text in native_product_positioning_texts(product):
        if not text or text in excluded:
            continue
        for clause in re.split(r"[.;!?\r\n]+|\b(?:but|however)\b", text, flags=re.I):
            negation = _POSITIONING_NEGATION.search(clause)
            categories |= categorize(clause[:negation.start()] if negation else clause)
    categories.discard("probiotic")
    return categories


def assess_claim_alignment(product: Mapping, context: Mapping, canonicals=(), *, supported_outcomes=()) -> dict:
    """Compare the label's claims with one reviewed context's studied outcome.

    ``absent``: no recognized claim. ``aligned``/``mixed``: at least one claim
    shares the outcome's indication. ``unrelated``: every claim is elsewhere.
    ``ambiguous``: a recognized claim no category places. Alignment never
    earns more than absence; it only decides whether an unrelated claim
    stops this context from crediting the product. The signed credit scope
    (``supported_outcomes``) outranks a broader context condition.
    """
    from evidence_resolver import evidence_indication_categories
    from scoring_input_contract import ingredient_function_claims
    condition = _key(context.get("condition"))
    if condition:
        pattern = re.compile(r"(?<!\w)" + r"[\s_-]+".join(re.escape(word) for word in condition.split()) + r"(?!\w)", re.I)
        # Names and warnings about a condition are not a claimed product purpose.
        excluded = {str(product.get("brand_name") or ""), str(product.get("serving_description") or "")}
        if any(text and text not in excluded and find_affirmative_label_match(pattern, text)
               for text in native_product_positioning_texts(product)):
            return {"state": "aligned", "sources": ["affirmative_exact_source_condition_claim"]}
    named = [str(value) for value in supported_outcomes if _key(value) == condition]
    outcome = evidence_indication_categories(" ".join(named or map(str, supported_outcomes)))
    if not outcome:
        outcome = evidence_indication_categories(" ".join([condition, *(
            str(row.get("name") or "") for row in context.get("outcomes") or []
            if isinstance(row, Mapping) and row.get("hierarchy") == "primary")]))
    # A purpose the label attributes to this ingredient governs; unattributed
    # product positioning stands in only when the ingredient has no claim.
    claims = [(source, _claimed_purposes(text)) for canonical in sorted(set(canonicals))
              for source, text in ingredient_function_claims(product.get("statements"), canonical)]
    positioning = native_product_positioning_categories(product, purposes_only=True)
    if positioning and not claims:
        claims.append(("product_positioning", positioning))
    if not claims:
        return {"state": "absent", "sources": []}
    aligned = [source for source, categories in claims if categories & outcome]
    unclassified = [source for source, categories in claims if not categories]
    if aligned:
        return {"state": "aligned" if len(aligned) == len(claims) else "mixed",
                "sources": list(dict.fromkeys(source for source, _ in claims))}
    if unclassified:
        return {"state": "ambiguous", "sources": list(dict.fromkeys(unclassified))}
    return {"state": "unrelated", "sources": list(dict.fromkeys(source for source, _ in claims))}


def assess_native_claimed_purpose(product: Mapping, context: Mapping, canonicals=()) -> dict:
    """Decide whether a source context may credit this label's claimed purpose.

    No claim is required. An unrelated claim, or a recognized claim that cannot
    be classified, keeps the context from crediting the product. This proves
    neither a user's diagnosis nor membership in the trial population.
    """
    if "applicability" in context:
        from probiotic_measurements import context_accepted_for_scoring
        if not _valid_native_claim_scope(context) or not context_accepted_for_scoring(context):
            return {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
    alignment = assess_claim_alignment(product, context, canonicals)
    exact = alignment["sources"] == ["affirmative_exact_source_condition_claim"]
    if not exact and "applicability" in context and _excluded_claim_matches(product, context["applicability"]):
        return {"status": "not_applicable", "reason_code": "label_purpose_evidence_mismatch",
                "condition": context.get("condition"), "claim_alignment": alignment}
    if alignment["state"] in _CREDITABLE_CLAIM_STATES:
        reason = ("affirmative_exact_source_condition_claim" if exact
                  else "no_label_claim_required" if alignment["state"] == "absent"
                  else "label_claim_aligned_with_studied_outcome")
        return {"status": "applicable", "reason_code": reason,
                "condition": context.get("condition"), "claim_alignment": alignment}
    if alignment["state"] == "ambiguous":
        return {"status": "unresolved", "reason_code": "label_claim_unclassified",
                "condition": context.get("condition"), "claim_alignment": alignment}
    return {"status": "not_applicable", "reason_code": "label_purpose_evidence_mismatch",
            "condition": context.get("condition"), "claim_alignment": alignment}


_PREGNANT_SUBJECTS = re.compile(r"(?<![\w-])pregnant women\b", re.I)
_MATERNAL_SUPPLEMENTATION = re.compile(r"\b(?:pregnan\w*|maternal|postpartum)\b", re.I)
_INFANT_TARGET = re.compile(r"\b(?:infants?|bab(?:y|ies)|newborns?|neonat\w*)\b", re.I)


def _special_population(context: Mapping, description: str) -> str | None:
    """Research done only in infants, children or pregnancy (structured age first)."""
    age = context["population"].get("age_group")
    if age in {"infant", "child"}:
        # Offspring outcomes of maternal supplementation were studied by
        # supplementing pregnant women, not by giving the infant the product.
        if _MATERNAL_SUPPLEMENTATION.search(description):
            return "pregnancy"
        return "infant" if age == "infant" else "pediatric"
    if age != "mixed" and (re.search(r"pregnan|gestation", _key(context.get("condition")))
                           or _PREGNANT_SUBJECTS.search(description)):
        return "pregnancy"
    return None


def assess_context_population(product: Mapping, context: Mapping) -> str:
    """Compare a reviewed context's studied population with the label's targeting.

    Infant, pediatric and pregnancy-only research applies only to a product
    affirmatively labelled for that population (title or DSLD target groups,
    never a precaution). Any other restriction fails only on an explicit label
    conflict. This never infers an individual user's condition.
    """
    from rda_ul_calculator import label_is_for_children, label_population_members, _target_group_text
    from scoring_input_contract import _ROUTE_PRENATAL_KEYWORDS, _route_product_label_text
    population = context.get("population")
    if not isinstance(population, Mapping) or not isinstance(population.get("description"), str) or not population["description"].strip():
        return "unresolved"
    description = population["description"]
    title = _route_product_label_text(dict(product))
    groups = product.get("targetGroups") or []
    children = label_is_for_children(dict(product))
    pregnancy = ("pregnancy_lactation" in label_population_members(dict(product))
                 or bool(_ROUTE_PRENATAL_KEYWORDS.search(title)))
    special = _special_population(context, description)
    if special == "infant":
        infant = children and bool(_INFANT_TARGET.search(" ".join([title, *map(_target_group_text, groups)])))
        return "eligible" if infant else "special_targeting_absent"
    if special == "pediatric":
        return "eligible" if children else "special_targeting_absent"
    if special == "pregnancy":
        return "eligible" if pregnancy else "special_targeting_absent"
    if population.get("age_group") == "adult" and children:
        return "explicit_conflict"
    # Pregnant women are not interchangeable with a studied nonpregnant group.
    if pregnancy and not _PREGNANT_SUBJECTS.search(description):
        return "explicit_conflict"
    key = _key(description)
    men = re.compile(r"\b(?:men|male|males)\b", re.I)
    women = re.compile(r"\b(?:women|female|females)\b", re.I)
    # "Predominantly men" describes a sample, not a sex restriction.
    qualified = re.search(r"\b(?:predominantly|mostly|mainly|primarily|majority)\b", key)
    for studied, other in ((women, men), (men, women)):
        if not qualified and re.search(studied, key) and not re.search(other, key) and any(
                find_affirmative_label_match(other, _target_group_text(group))
                and not find_affirmative_label_match(studied, _target_group_text(group))
                for group in groups):
            return "explicit_conflict"
    return "eligible"


def assess_clinical_source_review(entry: Mapping) -> dict:
    """Validate contributing research at the existing clinical scope owner.

    Review flags on enriched matches cannot invent a source context or override
    the curated record. This is completion evidence, not a new dose benchmark.
    """
    from clinical_evidence_schema import validate_ingredient_context
    reference = reviewed_entries().get(str(entry.get("id") or entry.get("study_id")), {})
    contexts = reference.get("study_contexts")
    if not isinstance(contexts, list) or not contexts:
        return {"is_complete": False, "errors": ["clinical_source_contexts_missing"], "context_ids": []}
    if any(not isinstance(context, Mapping) for context in contexts):
        return {"is_complete": False, "errors": ["clinical_source_context_invalid"], "context_ids": []}
    reference_only = is_reference_only(reference)
    contributing = [context for context in contexts if isinstance(context, Mapping)
                    and context.get("scoring_eligible") is not False
                    and context.get("review_status") != "rejected_source"]
    if reference_only and not contributing:
        # Completed negative reference findings need no point-eligible arm.
        # Do not promote pending or rejected history to a completed review.
        contributing = [context for context in contexts
                        if context.get("scoring_eligible") is False
                        and context.get("review_status") == "clinician_approved"]
    from evidence_resolver import clinical_record_sources_eligible
    references = reference.get("references_structured", [])
    published = reference.get("published_studies", [])
    if (not isinstance(references, list) or any(not isinstance(ref, Mapping) for ref in references)
            or not isinstance(published, list)
            or any(not isinstance(pmid, (str, int)) or isinstance(pmid, bool) for pmid in published)):
        return {"is_complete": False, "errors": ["clinical_source_references_invalid"], "context_ids": []}
    declared_pmids = {str(ref["pmid"]) for ref in references if ref.get("pmid")}
    declared_pmids.update(str(pmid) for pmid in published
                          if re.fullmatch(r"[1-9][0-9]*", str(pmid)))
    excluded_pmids = {str(ref["pmid"]) for ref in references if ref.get("pmid")
                      and not clinical_record_sources_eligible({"references_structured": [ref]})}
    eligible_pmids = declared_pmids - excluded_pmids
    errors = []
    if reference_only and not contributing:
        # A source-transfer rejection is a completed non-affirmative decision,
        # not an affirmative trial with an invented regimen or primary outcome.
        # Every declared source must be covered by an attributable exclusion;
        # a pending sibling context or explicit record hold still blocks.
        rejected_sources = set()
        for context in contexts:
            prefix = str(context.get("context_id") or "unknown") + ":"
            sources = context.get("source_pmids")
            sources = {str(pmid) for pmid in sources} if isinstance(sources, list) else set()
            if context.get("review_status") != "rejected_source" or sources - declared_pmids:
                errors.append(prefix + "clinical_source_rejection_incomplete")
            errors.extend(prefix + error for error in validate_ingredient_context(
                context, known_component_ids={reference.get("id")}, require_complete_review=True))
            rejected_sources.update(sources)
        if not declared_pmids or declared_pmids - rejected_sources:
            errors.append("clinical_source_rejection_coverage_incomplete")
        if reference.get("scoring_eligible") is False:
            errors.append("clinical_context_eligible_source_missing")
        return {"is_complete": not errors, "errors": errors,
                "context_ids": [context.get("context_id") for context in contexts]}
    if not contributing:
        errors.append("clinical_contributing_contexts_missing")
    for context in contributing:
        context_sources = context.get("source_pmids")
        context_pmids = {str(pmid) for pmid in context_sources} if isinstance(context_sources, list) else set()
        prefix = str(context.get("context_id") or "unknown") + ":"
        if context_pmids - declared_pmids:
            errors.append(prefix + "clinical_context_source_not_in_record")
        # Excluded notices may document a trial's provenance, but cannot be
        # its sole affirmative source. Explicit exclusions also win over a
        # duplicate legacy published_studies pointer.
        # Reference-only is a reviewed non-affirmative scope, not missing
        # source review. It still needs an eligible source and full approval;
        # an explicit eligibility hold cannot be cleared by that classification.
        if ((not reference_only and not clinical_record_sources_eligible(reference))
                or reference.get("scoring_eligible") is False
                or not (context_pmids & eligible_pmids)):
            errors.append(prefix + "clinical_context_eligible_source_missing")
        if context.get("identity_scope") in {"exact_strain", "species_general"}:
            from clinical_evidence_schema import validate_frozen_context
            from studied_formulas import valid_native_study_context
            context_errors = validate_frozen_context(context, require_complete_review=True)
            if not valid_native_study_context(context, reference.get("id")):
                context_errors.append("clinical_native_context_invalid")
        else:
            context_errors = validate_ingredient_context(context, require_complete_review=True)
        errors.extend(str(context.get("context_id") or "unknown") + ":" + error
                      for error in context_errors)
    return {"is_complete": not errors, "errors": errors,
            "context_ids": [context.get("context_id") for context in contributing]}


def _accepted_condition_scopes(reference: Mapping, policy: Mapping) -> list:
    from probiotic_measurements import context_accepted_for_scoring
    source_pmids = {str(pmid) for pmid in policy.get("source_pmids") or []}
    return [
        context for context in reference.get("study_contexts") or []
        if isinstance(context, Mapping) and context_accepted_for_scoring(context)
        and (not source_pmids or source_pmids.intersection(str(pmid) for pmid in context.get("source_pmids") or []))
    ]


def condition_scope_governs(entry: Mapping) -> bool:
    """Whether this record's label-purpose decision belongs to its condition scopes."""
    reference = reviewed_entries().get(str(entry.get("id") or entry.get("study_id")), {})
    policy = reference["applicability"] if "applicability" in reference else entry.get("applicability")
    return bool(_valid_policy(policy) and policy.get("scope") == "ingredient"
                and reference.get("study_type") != "reference" and reference.get("evidence_level") != "reference"
                and _accepted_condition_scopes(reference, policy))


def _assess_condition_scopes(product: Mapping, entry: Mapping, policy: Mapping, contexts: list) -> dict:
    """Return a blocking decision, or the components a qualifying scope adds.

    Population and claim are judged per context, so one applicable context
    cannot lend its approval, population or outcome to another. Preparation
    and amount checks still follow in the caller.
    """
    canonicals = {str(row.get("canonical_id")) for row in _linked_rows(product, entry, evidence_only=True)
                  if row.get("canonical_id")}
    results = [(context, assess_context_population(product, context),
                assess_claim_alignment(product, context, canonicals,
                                       supported_outcomes=policy.get("supported_outcomes", [])))
               for context in contexts]
    qualifying = [(context, claim) for context, population, claim in results
                  if population == "eligible" and claim["state"] in _CREDITABLE_CLAIM_STATES]
    if not qualifying:
        eligible = [claim for _, population, claim in results if population == "eligible"]
        populations = {population for _, population, _ in results}
        if eligible:
            claim = next((claim for claim in eligible if claim["state"] == "ambiguous"), eligible[0])
            return {"status": "unresolved" if claim["state"] == "ambiguous" else "not_applicable",
                    "reason_code": ("label_claim_unclassified" if claim["state"] == "ambiguous"
                                    else "label_purpose_evidence_mismatch"),
                    "claim_alignment": claim, "population_applicability": {"state": "eligible"}}
        state = next(state for state in ("unresolved", "explicit_conflict", "special_targeting_absent")
                     if state in populations)
        return {"status": "unresolved" if state == "unresolved" else "not_applicable",
                "reason_code": {"unresolved": "invalid_applicability_contract",
                                "explicit_conflict": "clinical_population_mismatch",
                                "special_targeting_absent": "clinical_population_targeting_absent"}[state],
                "population_applicability": {"state": state}}
    rank = {"aligned": 0, "mixed": 1, "absent": 2}
    components = {
        "claim_alignment": min((claim for _, claim in qualifying), key=lambda claim: rank[claim["state"]]),
        "population_applicability": {"state": "eligible",
                                     "context_ids": [context.get("context_id") for context, _ in qualifying]},
    }
    if len(qualifying) < len(contexts):
        conditions = {_key(context.get("condition")) for context, _ in qualifying}
        components["supported_outcomes"] = ([value for value in policy.get("supported_outcomes", [])
                                             if _key(value) in conditions]
                                            or [context.get("condition") for context, _ in qualifying])
        components["studied_population"] = "; ".join(context["population"]["description"]
                                                     for context, _ in qualifying)
    return components


def assess_clinical_applicability(product: Mapping, entry: Mapping, *, assess_amount: bool = True) -> dict:
    reference = reviewed_entries().get(str(entry.get("id") or entry.get("study_id")), {})
    # The curated owner can retain research for context while withdrawing
    # numerical credit. An old enriched positive stamp cannot reverse that.
    if is_reference_only(reference):
        return {"status": "not_applicable", "reason_code": "reference_only_clinical_record"}
    policy = reference["applicability"] if "applicability" in reference else entry.get("applicability")
    if policy is None:
        # Legacy reviewed exclusions constrain the matched preparation only.
        # Keep their original semantics at this shared seam; ingredient names
        # can legitimately contain a generic term beside a branded preparation.
        excluded = reference.get("exclude_aliases", entry.get("exclude_aliases", []))
        if excluded:
            linked = _linked_rows(product, entry, evidence_only=True)
            if not linked:
                return {"status": "unresolved", "reason_code": "clinical_source_row_unresolved"}
            if all(any(_key(term) in _key(row.get("matched_form") or row.get("form"))
                       for term in excluded) for row in linked):
                return {"status": "not_applicable", "reason_code": "clinical_preparation_mismatch"}
        return {"status": "not_curated", "reason_code": "no_reviewed_scope_constraints"}
    if not _valid_policy(policy):
        return {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
    if policy.get("scope") == "formula_context_only":
        return {"status": "not_applicable", "reason_code": "formula_reference_not_individual_evidence"}
    if policy.get("scope") != "ingredient":
        return {"status": "unresolved", "reason_code": "unsupported_applicability_scope"}
    if _excluded_claim_matches(product, policy):
        return {"status": "not_applicable", "reason_code": "label_purpose_evidence_mismatch"}
    # Every approved, source-bound context is a condition scope: no claim is
    # required, but its population and the label's claims decide whether it
    # may credit this product (October 28, 2026 rulings).
    accepted_scopes = _accepted_condition_scopes(reference, policy)
    declared_condition_scopes = [
        context for context in reference.get("study_contexts") or []
        if isinstance(context, Mapping)
        and _key(context.get("condition")) in {_key(value) for value in policy.get("supported_outcomes", [])}
        and context.get("purpose") in {"treatment", "challenge", "prevention"}
    ]
    if ((declared_condition_scopes and not any(context in accepted_scopes for context in declared_condition_scopes))
            or (not reference.get("study_contexts")
                and isinstance(reference.get("scoring_eligible"), bool)
                and policy.get("supported_outcomes"))):
        # Losing a signed context or its source binding cannot restore the
        # legacy unscoped path. Legacy records without an explicit eligibility
        # decision retain their existing preparation-only behavior.
        return {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
    # A claim or population block is decided after preparation, so the
    # rejection still records which label rows are the studied material.
    scope = _assess_condition_scopes(product, entry, policy, accepted_scopes) if accepted_scopes else {}
    physical = product.get("physicalState") or {}
    if isinstance(physical, Mapping):
        physical = physical.get("name")
    dosage_form = _key(product.get("form_factor_canonical") or product.get("form_factor") or physical)
    allowed = {_key(f) for f in policy.get("dosage_forms") or []}

    lower, upper, frequency_defaulted = resolve_daily_serving_range(dict(product))
    reasons = []
    source_only = policy.get("require_source_label_form", False)
    if source_only:
        # A generated/stale canonical form cannot establish source-only delivery.
        # Reuse the physical-form owner on the retained label, not on its guess.
        from form_factor_normalizer import canonicalize_form_factor
        dosage_form = _key(canonicalize_form_factor(physical)) if physical else ""
    excluded_canonicals = {_key(value) for value in policy.get("excluded_canonical_ids", [])}
    exclusion_only = bool(excluded_canonicals or policy.get("excluded_form_terms")) and not any(
        policy.get(field) for field in (
            "required_form_terms", "require_source_label_form", "dosage_forms",
            "minimum_daily_dose", "maximum_daily_dose", "dose_unit",
        )
    )
    # Preparation-only judgments have no exposure prerequisite. A caller
    # asking for dose checks must still own a real reviewed amount constraint;
    # an undosed named material remains eligible for its form/literature review.
    exposure_required = assess_amount and policy.get("dose_unit") is not None
    applicable_rows = []
    for row in _linked_rows(product, entry, source_only=source_only, evidence_only=not exposure_required,
                            discriminating_terms=policy.get("required_form_terms")):
        text = _row_text(row, source_only=source_only)
        if allowed and not (allowed & ({dosage_form} | _source_delivery_forms(product, row, policy.get("excluded_form_terms", [])))):
            reasons.append("clinical_delivery_mismatch")
            continue
        if source_only and not text:
            reasons.append("clinical_source_label_unresolved")
            continue
        if _key(row.get("canonical_id")) in excluded_canonicals:
            reasons.append("clinical_identity_excluded")
            continue
        # Required terms stay source-strict, but a disqualifying preparation
        # from any form layer must still reject the row. Otherwise an
        # enrichment-derived "seed oil" can disappear when source taxonomy is
        # absent and incorrectly satisfy the broader cranberry scope.
        exclusion_text = text if not source_only else text + _row_text(row)
        if any(
            " " + _key(term) + " " in exclusion_text
            for term in policy.get("excluded_form_terms", [])
        ):
            reasons.append("clinical_form_excluded")
            continue
        forms = policy.get("required_form_terms") or []
        literal_source = normalize_text(_row_text(row, source_only=source_only, preserve_punctuation=True))
        if forms and not any(
            find_affirmative_label_match(
                re.compile(r"(?<!\w)" + re.escape(normalize_text(form)) + r"(?!\w)", re.I), literal_source
            ) if "+" in form else " " + _key(form) + " " in text
            for form in forms
        ):
            reasons.append("clinical_form_mismatch")
            continue
        amount = _number(row.get("quantity"))
        unit_scale = _mass_unit_scale(row.get("unit_normalized") or row.get("unit"))
        target_scale = _mass_unit_scale(policy.get("dose_unit"))
        if assess_amount and target_scale is not None:
            if frequency_defaulted:
                reasons.append("clinical_dose_unresolved")
                continue
            if amount is None or amount <= 0 or unit_scale is None:
                reasons.append("clinical_dose_unresolved")
                continue
            amount *= unit_scale / target_scale
            minimum, maximum = policy.get("minimum_daily_dose"), policy.get("maximum_daily_dose")
            if minimum is not None and amount * lower < float(minimum):
                reasons.append("below_applicable_clinical_dose")
                continue
            if maximum is not None and amount * upper > float(maximum):
                reasons.append("above_applicable_clinical_dose")
                continue
        if exclusion_only:
            applicable_rows.append(row)
            continue
        if scope.get("status"):
            return {**scope, "matched_source_row_refs": [ref for ref in (
                row.get("raw_source_path") or row.get("source_row_ref"),) if ref]}
        return {"status": "applicable", "reason_code": "reviewed_scope_match",
                "source_row_ref": row.get("raw_source_path") or row.get("source_row_ref"),
                "supported_outcomes": policy.get("supported_outcomes", []),
                "studied_population": policy.get("studied_population"),
                "scope": "ingredient", **scope}
    if applicable_rows and scope.get("status"):
        return {**scope, "matched_source_row_refs": list(dict.fromkeys(
            row.get("raw_source_path") or row.get("source_row_ref") for row in applicable_rows
            if row.get("raw_source_path") or row.get("source_row_ref")))}
    if applicable_rows:
        # Exclusion rejects identities/preparations, not legitimate siblings.
        # Preserve every passing row rather than making label order choose
        # the numerator later consumed by Evidence and Dose. Scoped form/dose
        # decisions above retain their existing single-source binding.
        return {"status": "applicable", "reason_code": "reviewed_scope_match",
                "matched_source_row_refs": list(dict.fromkeys(
                    row.get("raw_source_path") or row.get("source_row_ref")
                    for row in applicable_rows
                    if row.get("raw_source_path") or row.get("source_row_ref")
                )),
                "matched_canonical_ids": list(dict.fromkeys(
                    row["canonical_id"] for row in applicable_rows if row.get("canonical_id")
                )),
                "supported_outcomes": policy.get("supported_outcomes", []),
                "studied_population": policy.get("studied_population"),
                "scope": "ingredient", **scope}
    reason = reasons[0] if reasons else "clinical_source_row_unresolved"
    status = ("unresolved" if reason in {
        "clinical_source_row_unresolved", "clinical_source_label_unresolved", "clinical_dose_unresolved",
    } else "not_applicable")
    return {"status": status, "reason_code": reason}


def preparation_verified_clinical_matches(product: Mapping) -> list[dict]:
    """Matches whose identity and preparation fit the reviewed scope.

    Accepted matches, plus rejections made only by a condition scope's claim or
    population component: those prove the label carries the studied material
    without making it Evidence for this label's purpose (Formulation reads this).
    """
    evidence = product.get("evidence_data") or {}
    matches = [match for match in evidence.get("clinical_matches") or [] if isinstance(match, Mapping)]
    for rejected in evidence.get("rejected_clinical_matches") or []:
        if (isinstance(rejected, Mapping) and rejected.get("matched_source_row_refs")
                and ("claim_alignment" in rejected or "population_applicability" in rejected)):
            record = reviewed_entries().get(str(rejected.get("id")), {})
            matches.append({**record, **rejected})
    return matches


def filter_clinical_matches(product: Mapping, matches: list[dict], *, assess_amount: bool = True) -> tuple[list[dict], list[dict]]:
    accepted, rejected = [], []
    for entry in matches:
        decision = assess_clinical_applicability(product, entry, assess_amount=assess_amount)
        if decision["status"] in {"applicable", "not_curated"}:
            # Preserve legacy shape for unreviewed records; never imply that a
            # missing applicability policy is a completed scientific review.
            if decision["status"] == "not_curated":
                accepted.append(entry)
                continue
            scoped_entry = {**entry, "applicability_assessment": decision}
            if "matched_source_row_refs" in decision:
                scoped_entry["matched_source_row_refs"] = decision["matched_source_row_refs"]
                scoped_entry["matched_canonical_ids"] = decision["matched_canonical_ids"]
            elif decision.get("source_row_ref"):
                # Later dose and readiness consumers may use only the row that
                # passed, not a sibling admitted by broad identity matching.
                scoped_entry["matched_source_row_refs"] = [decision["source_row_ref"]]
            accepted.append(scoped_entry)
        else:
            rejected.append({"id": entry.get("id") or entry.get("study_id"),
                             "ingredient": entry.get("ingredient"), **decision})
    return accepted, rejected
