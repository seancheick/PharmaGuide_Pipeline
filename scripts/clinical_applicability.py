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
                 discriminating_terms: Any = (), source_preparation: bool = False):
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
                    # Preparation may be printed on this exact provider-owned
                    # heading. Keep its retained source separate from the child
                    # that owns exclusions, delivery and exposure; no sibling or
                    # product-wide text can establish this lineage.
                    if source_preparation:
                        return exact_refs
                    return children
                if len(exact_refs) == 1:
                    # Several provider identities may share a blend reference.
                    # This match names one exact anchor; use that identity, not
                    # another member at the same heading or a raw missing ID.
                    return [{**exact_refs[0], "canonical_id": anchor["canonical_id"]}]
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



# A signed exclusion names a claim. In label statements a single word counts
# only as a claimed object ("supports cellular energy"), not in a mechanism
# sentence ("the heart's energy producing system"); a title keeps the exact
# signed word. Precautions never count.
_CLAIM_VERB = r"(?:supports?|promotes?|boosts?|helps?|enhances?|increases?|improves?|maintains?|for)"
_CLAIM_NOUN = r"(?:support|formula|booster|boost|health)"
_PRECAUTION_CLAUSE = re.compile(
    r"\b(?:consult|ask (?:your|a)|talk (?:to|with)|if you (?:are|have)|warning|caution|keep out of reach)\b", re.I)


def _excluded_claim_matches(product: Mapping, policy: Mapping) -> bool:
    """Match only affirmative label claims, never warnings, precautions or metadata."""
    excluded = {str(product.get("brand_name") or ""), str(product.get("serving_description") or "")}
    titles = {str(product.get(field) or "") for field in ("product_name", "fullName")} - {""}
    clauses = [(text in titles, clause) for text in native_product_positioning_texts(product)
               if text and text not in excluded
               for clause in re.split(r"[.;!?\r\n]+", text) if not _PRECAUTION_CLAUSE.search(clause)]
    for term in policy.get("excluded_claim_terms", []):
        words = _key(term).split()
        exact = r"[\s_-]+".join(re.escape(word) for word in words)
        claimed = (rf"(?:{_CLAIM_VERB}\b.*?(?<!\w){exact}|{exact}[\s_-]+{_CLAIM_NOUN})"
                   if len(words) == 1 else exact)
        patterns = {True: re.compile(r"(?<!\w)" + exact + r"(?!\w)", re.I),
                    False: re.compile(r"(?<!\w)" + claimed + r"(?!\w)", re.I)}
        if any(find_affirmative_label_match(patterns[title], clause) for title, clause in clauses):
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
_POSITIONING_NEGATION = re.compile(
    r"\b(?:no|not|without|avoid|never|won'?t|don'?t|doesn'?t|free\s+(?:of|from))\b", re.I)


# Who a product is for is population targeting, judged against the studied
# population; it is never a claimed outcome ("Baby Probiotic", "Women's Multi").
_POPULATION_WORDS = re.compile(
    r"\b(?:infants?|bab(?:y|ies)|pediatric|child(?:ren)?|kids?|toddlers?|preterm|neonat\w*|"
    r"prenatal|pregnan\w*|maternal|postnatal|postpartum|wom[ae]n'?s?|female|men'?s?|male)\b", re.I)


# A product-level function sentence ("Supports normal enzyme activity"). A
# general wellness phrase names no specific purpose, so it is no such claim.
_POSITIONING_FUNCTION = re.compile(r"\b(?:supports?|promotes?|helps?|maintains?)\s+[a-z]", re.I)
_GENERAL_WELLNESS = re.compile(
    r"\b(?:(?:overall|general|daily|good|optimal|total|everyday)\s+(?:health|wellness|well[- ]?being|nutrition)"
    r"|well[- ]?being|wellness|nutritional support)\b", re.I)


def _claimed_purposes(text: str) -> set[str]:
    from evidence_resolver import evidence_indication_categories
    return evidence_indication_categories(_POPULATION_WORDS.sub(" ", text))


def native_product_positioning_categories(product: Mapping, *, purposes_only: bool = False) -> set[str]:
    """Indication categories of the label's affirmative product positioning."""
    return _positioning_claims(product, purposes_only=purposes_only)[0]


def _positioning_claims(product: Mapping, *, purposes_only: bool = False) -> tuple[set[str], bool]:
    """Positioning categories, and whether a function sentence no category places exists.

    Brand and serving metadata, negated clauses and precaution blocks are not
    a marketed purpose. Generic class words ("probiotic") are not a claim.
    ``purposes_only`` drops population words, which describe targeting, and
    the directions for use, which are not a marketed purpose.
    """
    from evidence_resolver import evidence_indication_categories
    categorize = _claimed_purposes if purposes_only else evidence_indication_categories
    excluded = {str(product.get("brand_name") or ""), str(product.get("serving_description") or "")}
    if purposes_only:
        excluded.add(str(product.get("suggested_use") or ""))
    categories: set[str] = set()
    unclassified = False
    for text in native_product_positioning_texts(product):
        if not text or text in excluded:
            continue
        for clause in re.split(r"[.;!?\r\n]+|\b(?:but|however)\b", text, flags=re.I):
            if _PRECAUTION_CLAUSE.search(clause):
                continue
            negation = _POSITIONING_NEGATION.search(clause)
            affirmative = clause[:negation.start()] if negation else clause
            found = categorize(affirmative)
            categories |= found
            unclassified |= (not found and bool(_POSITIONING_FUNCTION.search(affirmative))
                             and not _GENERAL_WELLNESS.search(affirmative))
    categories.discard("probiotic")
    return categories, unclassified


# Outcomes that report no comparative efficacy for the product's user.
NON_EFFICACY_OUTCOME_ROLES = {
    "within_group_change", "post_hoc_subgroup",
    "companion_reported_context", "network_ranking",
}


def qualifying_purpose_outcomes(context: Mapping, *, include_nonpositive: bool = False) -> tuple[list, bool]:
    """Outcomes that may name a purpose, and whether an unresolved one holds it.

    Sean, October 28, 2026 (PR #278): a positive primary or approved unranked
    (hierarchy not_reported) outcome qualifies; a surrogate names only itself.
    A direct trial's known or unresolved primary cannot be bypassed by an
    unranked positive endpoint. A pooled result may remain unranked.
    Null, mixed or unfavorable results, secondaries, post-hoc, within-group,
    companion and ranking-only outcomes never name a purpose.
    Evidence consistency consumers may include the corresponding nonpositive
    findings so that a null result remains a contradiction, never credit.
    """
    if context.get("outcome_role") in NON_EFFICACY_OUTCOME_ROLES:
        return [], False
    outcomes = [row for row in context.get("outcomes") or [] if isinstance(row, Mapping)
                and row.get("outcome_role") not in NON_EFFICACY_OUTCOME_ROLES]
    reported = [row for row in outcomes if row.get("hierarchy") in {"primary", "not_reported"}]
    unresolved_candidates = outcomes
    if context.get("evidence_role") == "direct_rct":
        primary = [row for row in outcomes if row.get("hierarchy") == "primary"]
        if primary:
            # An unranked positive cannot outrank a reported primary. Retain
            # nonpositive findings for the consistency consumer.
            reported = [row for row in reported
                        if row.get("hierarchy") == "primary" or row.get("direction") != "positive"]
            unresolved_candidates = primary
        elif any(row.get("hierarchy") == "unresolved" for row in outcomes):
            # Registered-primary uncertainty is stronger than an absent rank.
            # 299v/32365981 records unranked positive vigor while the registered
            # exercise endpoint still has no exact primary measurement mapping.
            return [], True
    directions = {"positive", "null", "mixed", "negative"} if include_nonpositive else {"positive"}
    qualifying = [row for row in reported if row.get("direction") in directions]
    held = not qualifying and any(row.get("hierarchy") == "unresolved" or row.get("direction") == "unresolved"
                                  for row in unresolved_candidates)
    return qualifying, held


def evaluated_purpose_outcomes(context: Mapping) -> list:
    """Null, mixed or unfavorable primary findings of a context with no positive one.

    They say what the research evaluated, so a matching claim reaches the
    preserved finding (an evaluated null, never credit). Beside a positive
    outcome they name nothing: a null sleep result cannot widen stress credit.
    """
    qualifying, held = qualifying_purpose_outcomes(context)
    if qualifying or held or context.get("outcome_role") in NON_EFFICACY_OUTCOME_ROLES:
        return []
    return [row for row in context.get("outcomes") or [] if isinstance(row, Mapping)
            and row.get("outcome_role") not in NON_EFFICACY_OUTCOME_ROLES
            and row.get("hierarchy") in {"primary", "not_reported"}
            and row.get("direction") in {"null", "mixed", "negative"}]


def assess_claim_alignment(product: Mapping, context: Mapping, canonicals=(), *, supported_outcomes=(),
                           formula_level: bool = False) -> dict:
    """Compare the label's claims with one reviewed context's studied outcome.

    ``absent``: no recognized claim. ``aligned``/``mixed``: at least one claim
    shares the outcome's indication. ``unrelated``: every claim is elsewhere.
    ``ambiguous``: a recognized claim no category places. Alignment never
    earns more than absence; it only decides whether an unrelated claim
    stops this context from crediting the product. Qualifying findings bound
    the relationship; a signed scope may narrow it, never promote a null one.
    """
    from evidence_resolver import evidence_indication_categories
    from scoring_input_contract import ingredient_function_claims
    condition = _key(context.get("condition"))
    qualifying, held = qualifying_purpose_outcomes(context)
    named_outcomes = qualifying or evaluated_purpose_outcomes(context)
    outcome_categories = [evidence_indication_categories(str(row.get("name") or ""))
                          for row in named_outcomes]
    outcome = set().union(*outcome_categories) if outcome_categories else set()
    named = [str(value) for value in supported_outcomes if _key(value) == condition]
    signed = evidence_indication_categories(" ".join(named or map(str, supported_outcomes)))
    condition_categories = evidence_indication_categories(condition)
    if signed:
        # Preserve the signed source mapping for a measurement name the
        # category vocabulary cannot place in that scope (PSS, SBP or JKOM).
        # Incidental source prose, such as urinary potassium exposure, is
        # not a reason to discard that reviewed mapping.
        outcome = signed
        # A broad signed scope cannot promote its named null endpoint beside
        # a positive endpoint. The positive result itself must name it.
        nonpositive, _ = qualifying_purpose_outcomes(context, include_nonpositive=True)
        excluded = evidence_indication_categories(" ".join(str(row.get("name") or "")
            for row in nonpositive if row.get("direction") != "positive"))
        positive_categories = set().union(*outcome_categories) if qualifying and outcome_categories else set()
        outcome -= excluded - positive_categories if qualifying else set()
    patient_relationship = bool(named_outcomes) and all(
        row.get("kind") == "patient_important" for row in named_outcomes)
    if not outcome and not any(outcome_categories) and patient_relationship and not signed:
        # Patient-important scales can name an uncategorized measurement
        # (JKOM, WOMAC or NEC stage). Preserve their reviewed condition link;
        # a surrogate alone cannot broaden to the surrounding disease.
        outcome = condition_categories
    exact_relationship = bool(named_outcomes) and (
        bool(condition_categories & outcome)
        or (not condition_categories and patient_relationship)
        or any(_key(row.get("name")) == condition for row in named_outcomes))
    if condition and exact_relationship:
        pattern = re.compile(r"(?<!\w)" + r"[\s_-]+".join(re.escape(word) for word in condition.split()) + r"(?!\w)", re.I)
        # Names and warnings about a condition are not a claimed product purpose.
        excluded = {str(product.get("brand_name") or ""), str(product.get("serving_description") or "")}
        if any(text and text not in excluded and find_affirmative_label_match(pattern, text)
               for text in native_product_positioning_texts(product)):
            return {"state": "aligned", "sources": ["affirmative_exact_source_condition_claim"]}
    # A purpose the label attributes to this ingredient governs; unattributed
    # product positioning stands in only when the ingredient has no claim.
    claims = [(source, _claimed_purposes(text)) for canonical in sorted(set(canonicals))
              for source, text in ingredient_function_claims(product.get("statements"), canonical)]
    positioning, unclassified = _positioning_claims(product, purposes_only=True)
    if formula_level:
        # Formula-level marketing that neither names this ingredient nor its
        # studied outcome is attributable to other ingredients, not to it
        # (Sean, October 28, PR #280): it is no unrelated claim of this one.
        positioning = positioning if positioning & outcome else set()
        unclassified = False
    if not claims:
        if positioning:
            claims.append(("product_positioning", positioning))
        if unclassified:
            # A function sentence no category places is still a claim.
            claims.append(("product_positioning_unclassified", set()))
    if not claims:
        return {"state": "absent", "sources": []}
    if held:
        # An unresolved outcome holds the purpose; it neither aligns nor rejects.
        return {"state": "ambiguous", "sources": list(dict.fromkeys(source for source, _ in claims))}
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


_PREGNANT_SUBJECTS = re.compile(
    r"(?<![\w-])pregnant (?:women|adolescents|adults|participants)\b|\btrimester of pregnancy\b", re.I)
_LACTATING_SUBJECTS = re.compile(r"\b(?:breastfeeding|lactating|nursing) (?:mothers|women)\b", re.I)
_PREGNANT_TARGET = re.compile(r"\bpregnant\b", re.I)
_LACTATING_TARGET = re.compile(r"\b(?:lactating|lactation|breastfeeding|nursing)\b", re.I)
_MATERNAL_SUPPLEMENTATION = re.compile(r"\b(?:pregnan\w*|maternal|postpartum)\b", re.I)
_INFANT_TARGET = re.compile(r"\b(?:infants?|bab(?:y|ies)|newborns?|neonat\w*)\b", re.I)


def _studied_subjects(pattern: re.Pattern, description: str) -> bool:
    """A subject phrase in a sentence that does not exclude or negate it."""
    return any(pattern.search(sentence) and not re.search(r"\bexclu|\bnot\b|\bnon-?\w", sentence, re.I)
               for sentence in re.split(r"[.;]", description))


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
                           or _studied_subjects(_PREGNANT_SUBJECTS, description)):
        return "pregnancy"
    if age != "mixed" and _studied_subjects(_LACTATING_SUBJECTS, description):
        return "lactation"
    return None


def assess_context_population(product: Mapping, context: Mapping) -> str:
    """Compare a reviewed context's studied population with the label's targeting.

    Infant, pediatric and pregnancy-only research applies only to a product
    affirmatively labelled for that population (title or DSLD target groups,
    never a precaution). Any other restriction fails only on an explicit label
    conflict. This never infers an individual user's condition.
    """
    from rda_ul_calculator import label_is_for_children, _target_group_text
    from scoring_input_contract import _ROUTE_PRENATAL_KEYWORDS, _route_product_label_text
    population = context.get("population")
    if not isinstance(population, Mapping) or not isinstance(population.get("description"), str) or not population["description"].strip():
        return "unresolved"
    description = population["description"]
    title = _route_product_label_text(dict(product))
    groups = product.get("targetGroups") or []
    children = label_is_for_children(dict(product))
    group_texts = [_target_group_text(group) for group in groups]
    # Affirmative targeting only: "Not for use during pregnancy", "Women (not
    # pregnant or lactating)" and post-pregnancy titles are not pregnancy labels.
    prenatal_title = re.compile(r"(?<!post-)(?<!post )" + _ROUTE_PRENATAL_KEYWORDS.pattern, re.I)
    pregnancy = (any(find_affirmative_label_match(_PREGNANT_TARGET, text) for text in group_texts)
                 or bool(find_affirmative_label_match(prenatal_title, title)))
    lactation = any(find_affirmative_label_match(_LACTATING_TARGET, text) for text in [*group_texts, title])
    special = _special_population(context, description)
    if special == "infant":
        infant = children and bool(_INFANT_TARGET.search(" ".join([title, *map(_target_group_text, groups)])))
        return "eligible" if infant else "special_targeting_absent"
    if special == "pediatric":
        return "eligible" if children else "special_targeting_absent"
    if special == "pregnancy":
        return "eligible" if pregnancy else "special_targeting_absent"
    if special == "lactation":
        return "eligible" if lactation else "special_targeting_absent"
    if population.get("age_group") == "adult" and children:
        return "explicit_conflict"
    if children and not population.get("age_group"):
        # A legacy signed population description without a typed age group
        # cannot establish that pediatric use was studied.
        return "unresolved"
    # Pregnant women are not interchangeable with a studied nonpregnant group.
    if pregnancy and not _studied_subjects(_PREGNANT_SUBJECTS, description):
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
                for group in [title, *group_texts]):
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
    from evidence_resolver import clinical_record_sources_eligible
    source_pmids = policy.get("source_pmids") or None
    return [
        context for context in reference.get("study_contexts") or []
        if isinstance(context, Mapping)
        and clinical_record_sources_eligible(reference, context=context, source_pmids=source_pmids)
    ]


def _positioning_is_formula_level(product: Mapping, canonicals: set) -> bool:
    """Whether unattributed product positioning speaks for other ingredients too.

    Positioning is this ingredient's own claim on a single-subject label or when
    it names the ingredient; on a multi-ingredient formula that does not name
    it, the phrase cannot be attributed to this source row.
    """
    from scoring_input_contract import get_evidence_subject_rows, _named_in_title
    rows = get_evidence_subject_rows(dict(product))
    subjects = {str(row.get("canonical_id")) for row in rows if row.get("canonical_id")}
    if not subjects - set(canonicals):
        return False
    text = " ".join(text for text in native_product_positioning_texts(product) if text)
    # Reuse the role owner's bounded identity/alias matching: a label can name
    # creatine without printing its machine identity "creatine_monohydrate".
    return not any(_named_in_title(row, text.lower()) for row in rows
                   if str(row.get("canonical_id")) in canonicals)


def _assess_condition_scopes(product: Mapping, entry: Mapping, policy: Mapping, contexts: list) -> dict:
    """Return a blocking decision, or the components a qualifying scope adds.

    Population and claim are judged per context, so one applicable context
    cannot lend its approval, population or outcome to another. Preparation
    and amount checks still follow in the caller.
    """
    # A signed context establishes a reviewed relationship, not affirmative
    # benefit for every recorded endpoint. Claim absence cannot promote a null
    # primary, exploratory secondary or unresolved outcome into credit.
    positive_contexts = [context for context in contexts if qualifying_purpose_outcomes(context)[0]]
    evaluated_contexts = [context for context in contexts
                          if evaluated_purpose_outcomes(context)
                          and {row.get("direction") for row in qualifying_purpose_outcomes(
                              context, include_nonpositive=True)[0]} <= {"null", "negative"}]
    qualified_contexts = positive_contexts + evaluated_contexts
    if not qualified_contexts:
        held = any(qualifying_purpose_outcomes(context)[1] for context in contexts)
        return {"status": "unresolved" if held else "not_applicable",
                "reason_code": "invalid_applicability_contract" if held else "clinical_outcome_not_qualified"}
    contexts = qualified_contexts
    canonicals = {str(row.get("canonical_id")) for row in _linked_rows(product, entry, evidence_only=True)
                  if row.get("canonical_id")}
    formula_level = _positioning_is_formula_level(product, canonicals)
    results = [(context, assess_context_population(product, context),
                assess_claim_alignment(product, context, canonicals, formula_level=formula_level,
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
    affirmative = [(context, claim) for context, claim in qualifying if context in positive_contexts]
    if not affirmative:
        # Completed, source-bound negative findings are evaluated results, never
        # affirmative credit. A held or unfinished review cannot become a zero.
        from scoring_v4.modules.generic_evidence import _clinical_source_id
        review = assess_clinical_source_review({"id": _clinical_source_id(dict(entry))})
        if not review["is_complete"]:
            return {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
        return {"status": "not_applicable", "reason_code": "clinical_outcome_not_qualified",
                "claim_alignment": qualifying[0][1],
                "population_applicability": {"state": "eligible", "context_ids": [
                    context["context_id"] for context, _ in qualifying]}}
    qualifying = affirmative
    rank = {"aligned": 0, "mixed": 1, "absent": 2}
    components = {
        "claim_alignment": min((claim for _, claim in qualifying), key=lambda claim: rank[claim["state"]]),
        "population_applicability": {"state": "eligible",
                                     "context_ids": [context.get("context_id") for context, _ in qualifying]},
    }
    # Source holds were removed before this function received the contexts.
    # Compare canonical context/source coverage, never an already-filtered
    # count. A fully retained signed scope may be narrower than its source
    # population (for example hypertensive participants within a BP review).
    from scoring_v4.modules.generic_evidence import _clinical_source_id
    reference = reviewed_entries().get(_clinical_source_id(dict(entry)), entry)
    original_ids = {context.get("context_id") for context in reference.get("study_contexts") or []
                    if context.get("scoring_eligible") is True}
    qualifying_ids = {context.get("context_id") for context, _ in qualifying}
    qualifying_sources = {str(pmid) for context, _ in qualifying
                          for pmid in context.get("source_pmids") or []}
    full_scope = (bool(original_ids) and original_ids <= qualifying_ids
                  and set(map(str, policy.get("source_pmids") or [])) <= qualifying_sources)
    conditions = {_key(context.get("condition")) for context, _ in qualifying}
    components["supported_outcomes"] = (policy["supported_outcomes"]
        if full_scope and policy.get("supported_outcomes") else
        [value for value in policy.get("supported_outcomes", []) if _key(value) in conditions]
        or list(dict.fromkeys(context.get("condition") for context, _ in qualifying)))
    components["studied_population"] = (policy["studied_population"]
        if full_scope and policy.get("studied_population") else
        "; ".join(dict.fromkeys(context["population"]["description"] for context, _ in qualifying)))
    # Derive design from the contexts that actually qualified, including when
    # a held synthesis was removed before this function received the contexts.
    if all(context.get("evidence_role") == "direct_rct" for context, _ in qualifying):
        families = {context.get("trial_family") or context.get("context_id") for context, _ in qualifying}
        components["qualifying_study_type"] = "rct_single" if len(families) == 1 else "rct_multiple"
    return components


def _assess_legacy_signed_scope(product: Mapping, entry: Mapping, reference: Mapping, policy: Mapping) -> dict:
    # Preserve existing signed legacy scopes without inventing a migrated
    # context. The scope, its population and its sources remain one unit;
    # descriptive top-level goals confer no approval.
    from datetime import date
    from evidence_resolver import clinical_record_sources_eligible
    try:
        dated = date.fromisoformat(policy.get("reviewed_at", "")) <= date.today()
    except (TypeError, ValueError):
        dated = False
    sources = set(policy.get("source_pmids") or [])
    eligible_sources = {str(ref.get("pmid")) for ref in reference.get("references_structured") or []
                        if isinstance(ref, Mapping) and ref.get("pmid")
                        and clinical_record_sources_eligible({"references_structured": [ref]})}
    if (not dated or not sources or not sources <= eligible_sources
            or not policy.get("studied_population") or not policy.get("supported_outcomes")):
        return {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
    canonicals = {str(row.get("canonical_id")) for row in _linked_rows(product, entry, evidence_only=True)
                  if row.get("canonical_id")}
    population = assess_context_population(product, {"population": {"description": policy["studied_population"]}})
    claim = assess_claim_alignment(product, {}, canonicals,
                                   supported_outcomes=policy["supported_outcomes"],
                                   formula_level=_positioning_is_formula_level(product, canonicals))
    if population != "eligible":
        return {"status": "unresolved" if population == "unresolved" else "not_applicable",
                "reason_code": "invalid_applicability_contract" if population == "unresolved" else "clinical_population_mismatch",
                "population_applicability": {"state": population}}
    if claim["state"] not in _CREDITABLE_CLAIM_STATES:
        return {"status": "unresolved" if claim["state"] == "ambiguous" else "not_applicable",
                "reason_code": "label_claim_unclassified" if claim["state"] == "ambiguous" else "label_purpose_evidence_mismatch",
                "claim_alignment": claim, "population_applicability": {"state": population}}
    return {"claim_alignment": claim, "population_applicability": {"state": population}}


def assess_clinical_applicability(product: Mapping, entry: Mapping, *, assess_amount: bool = True) -> dict:
    from scoring_v4.modules.generic_evidence import _clinical_source_id
    registry_backed = bool(entry.get("id") or entry.get("study_id") or entry.get("source_data"))
    reference = reviewed_entries().get(_clinical_source_id(dict(entry))) if registry_backed else entry
    if reference is None:
        return {"status": "unresolved", "reason_code": "clinical_source_contexts_missing"}
    # The curated owner can retain research for context while withdrawing
    # numerical credit. An old enriched positive stamp cannot reverse that.
    if is_reference_only(reference):
        return {"status": "not_applicable", "reason_code": "reference_only_clinical_record"}
    from evidence_resolver import clinical_record_sources_eligible
    # Enrichment and downstream consumers share the hold. Known preparation
    # exclusions are still checked first, so a hold cannot erase that finding.
    source_block = ({"status": "unresolved", "reason_code": "clinical_sources_ineligible"}
                    if reference and not clinical_record_sources_eligible(reference) else None)
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
        if source_block:
            return source_block
        # A missing scope is not permission to score an unreviewed record.
        # Legacy approved contexts use this same population/outcome owner;
        # their missing policy cannot bypass it on a claim-free label.
        if not reference.get("study_contexts"):
            return {"status": "unresolved", "reason_code": "clinical_source_contexts_missing"}
        if not _accepted_condition_scopes(reference, {}):
            return {"status": "unresolved", "reason_code": "clinical_context_eligible_source_missing"}
        policy = {"scope": "ingredient"}
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
    if ((reference.get("study_contexts") and not accepted_scopes)
            or (not reference.get("study_contexts")
                and isinstance(reference.get("scoring_eligible"), bool)
                and policy.get("supported_outcomes"))):
        # Losing a signed context or its source binding cannot restore the
        # legacy unscoped path. Legacy records without an explicit eligibility
        # decision retain their existing preparation-only behavior.
        scope = {"status": "unresolved", "reason_code": "invalid_applicability_contract"}
    else:
        scope = _assess_condition_scopes(product, entry, policy, accepted_scopes) if accepted_scopes else {}
    # A source, claim or population block is decided after preparation, so a
    # known material mismatch is preserved and passing rows retain provenance.
    if not reference.get("study_contexts") and not scope:
        scope = _assess_legacy_signed_scope(product, entry, reference, policy)
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
    row_constraints = any(policy.get(field) for field in (
            "required_form_terms", "require_source_label_form", "dosage_forms",
            "minimum_daily_dose", "maximum_daily_dose", "dose_unit",
        ))
    exclusion_only = bool(excluded_canonicals or policy.get("excluded_form_terms")) and not row_constraints
    # Preparation-only judgments have no exposure prerequisite. A caller
    # asking for dose checks must still own a real reviewed amount constraint;
    # an undosed named material remains eligible for its form/literature review.
    exposure_required = assess_amount and policy.get("dose_unit") is not None
    applicable_rows = []
    components = {_key(value) for value in reference.get("aggregate_canonical_ids") or []}
    if components:
        from scoring_input_contract import get_evidence_subject_rows
        refs = set(entry.get("matched_source_row_refs") or [])
        composition_owners = [row for row in get_evidence_subject_rows(dict(product))
                              if row.get("raw_source_path") in refs
                              and {_key(value) for value in row.get("verified_child_canonicals") or []} == components]
        if len(composition_owners) != 1:
            return {"status": "unresolved", "reason_code": "clinical_source_row_unresolved"}
    linked_rows = _linked_rows(product, entry, source_only=source_only, evidence_only=not exposure_required,
                               discriminating_terms=policy.get("required_form_terms"))
    preparation_rows = (_linked_rows(
        product, entry, source_only=True, evidence_only=True,
        discriminating_terms=policy.get("required_form_terms"), source_preparation=True,
    ) if source_only and not exposure_required else [])
    explicit_refs = entry.get("matched_source_row_refs") or []
    # Explicit repeated declarations may share review provenance only when
    # their resolved physical identity is identical and no row constraint binds
    # the decision to a particular form, delivery or daily exposure.
    repeated_material = (not row_constraints and isinstance(explicit_refs, list)
        and all(isinstance(ref, str) and ref.strip() for ref in explicit_refs)
        and len(set(explicit_refs)) > 1
        and {row.get("raw_source_path") or row.get("source_row_ref") for row in linked_rows} == set(explicit_refs)
        and len({(_key(row.get("canonical_id")), _row_text(row), _key(row.get("form")), _key(row.get("collagen_subtype")))
                 for row in linked_rows}) == 1
        and all(_key(row.get("canonical_id")) and _row_text(row).strip() for row in linked_rows))
    for row in linked_rows:
        from scoring_input_contract import declared_source_form_matches_material
        if not declared_source_form_matches_material(row, [reference.get("standard_name"),
                                                          *(reference.get("aliases") or [])]):
            reasons.append("clinical_form_mismatch")
            continue
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
        preparation_text = _row_text(row, source_only=source_only, preserve_punctuation=True)
        if len(linked_rows) == len(preparation_rows) == 1:
            heading = preparation_rows[0]
            heading_ref = heading.get("raw_source_path") or heading.get("source_row_ref")
            row_ref = row.get("raw_source_path") or row.get("source_row_ref")
            if (isinstance(heading_ref, str) and isinstance(row_ref, str)
                    and row_ref.startswith(heading_ref + ".")):
                preparation_text += " " + _row_text(heading, source_only=True, preserve_punctuation=True)
        literal_source = normalize_text(preparation_text)
        preparation_key = " " + _key(preparation_text).replace(" as ", " ") + " "
        if forms and not any(
            find_affirmative_label_match(
                re.compile(r"(?<!\w)" + re.escape(normalize_text(form)) + r"(?!\w)", re.I), literal_source
            ) if "+" in form else find_affirmative_label_match(
                re.compile(r"(?<!\w)" + re.escape(_key(form)) + r"(?!\w)", re.I), preparation_key
            )
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
        if exclusion_only or repeated_material:
            applicable_rows.append(row)
            continue
        if source_block or scope.get("status"):
            return {**(source_block or scope),
                    "matched_canonical_ids": [row["canonical_id"]] if row.get("canonical_id") else [],
                    "matched_source_row_refs": [ref for ref in (
                        row.get("raw_source_path") or row.get("source_row_ref"),) if ref]}
        return {"status": "applicable", "reason_code": "reviewed_scope_match",
                "source_row_ref": row.get("raw_source_path") or row.get("source_row_ref"),
                "matched_canonical_ids": [row["canonical_id"]] if row.get("canonical_id") else [],
                "supported_outcomes": policy.get("supported_outcomes", []),
                "studied_population": policy.get("studied_population"),
                "scope": "ingredient", **scope}
    if applicable_rows and (source_block or scope.get("status")):
        return {**(source_block or scope),
                "matched_canonical_ids": list(dict.fromkeys(
                    row["canonical_id"] for row in applicable_rows if row.get("canonical_id"))),
                "matched_source_row_refs": list(dict.fromkeys(
            row.get("raw_source_path") or row.get("source_row_ref") for row in applicable_rows
            if row.get("raw_source_path") or row.get("source_row_ref")))}
    if applicable_rows:
        # Exclusion rejects identities/preparations, not legitimate siblings.
        # Preserve every independently passing exclusion-only row or explicit
        # declaration of the same physical material. Scoped form/dose decisions
        # above retain their existing single-source binding.
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


def filter_clinical_matches(product: Mapping, matches: list[dict], *, assess_amount: bool = True) -> tuple[list[dict], list[dict]]:
    accepted, rejected = [], []
    for entry in matches:
        decision = assess_clinical_applicability(product, entry, assess_amount=assess_amount)
        # Discovery may have coalesced aliases across unrelated ingredients.
        # The actual passing source rows own both clinical identity and its UI
        # attribution, including when a provider heading retains its reference.
        passing_refs = set(decision.get("matched_source_row_refs") or [])
        if decision.get("source_row_ref"):
            passing_refs.add(decision["source_row_ref"])
        if passing_refs and "matched_canonical_ids" in decision:
            entry = {**entry, "matched_canonical_ids": decision["matched_canonical_ids"]}
            names = {row.get("name") for row in _rows(product, source_only=True, evidence_only=True)
                     if (row.get("raw_source_path") or row.get("source_row_ref")) in passing_refs
                     and row.get("name")}
            from scoring_input_contract import get_evidence_subject_rows
            aggregate_components = {_key(value) for value in entry.get("aggregate_canonical_ids") or []}
            aggregate_owner = any(
                row.get("canonical_id") in decision["matched_canonical_ids"]
                and (row.get("raw_source_path") or row.get("source_row_ref")) in passing_refs
                and {_key(value) for value in row.get("verified_child_canonicals") or []} == aggregate_components
                for row in get_evidence_subject_rows(dict(product))) if aggregate_components else False
            if aggregate_owner:
                entry["ingredient"] = entry.get("standard_name") or entry.get("study_name")
            elif len(names) == 1:
                entry["ingredient"] = names.pop()
            elif names and entry.get("ingredient") not in names:
                entry["ingredient"] = (entry.get("standard_name") or entry.get("study_name")
                                       or ", ".join(sorted(names)))
        if (decision.get("reason_code") == "clinical_outcome_not_qualified"
                and decision.get("population_applicability", {}).get("state") == "eligible"
                and decision.get("population_applicability", {}).get("context_ids")
                and decision.get("matched_source_row_refs")):
            from scoring_v4.modules.generic_evidence import _clinical_source_id
            reference = reviewed_entries()[_clinical_source_id(dict(entry))]
            selected = set(decision["population_applicability"]["context_ids"])
            directions = {outcome["direction"] for context in reference["study_contexts"]
                          if context.get("context_id") in selected
                          for outcome in evaluated_purpose_outcomes(context)}
            accepted.append({**entry, "study_type": "reference", "evidence_level": "reference",
                             "effect_direction": "negative" if "negative" in directions else "null",
                             "matched_source_row_refs": decision["matched_source_row_refs"],
                             "applicability_assessment": decision})
            continue
        if decision["status"] == "applicable":
            scoped_entry = {**entry, "applicability_assessment": decision}
            if decision.get("qualifying_study_type"):
                from scoring_v4.modules.generic_evidence import _clinical_source_id
                reference = reviewed_entries().get(_clinical_source_id(dict(entry)), {})
                qualified_ids = decision.get("population_applicability", {}).get("context_ids", [])
                if (scoped_entry.get("study_type") != decision["qualifying_study_type"]
                        or len(qualified_ids) < len(reference.get("study_contexts") or [])):
                    # A stronger record or excluded sibling cannot lend its
                    # aggregate enrollment to the trial that actually qualified.
                    scoped_entry.pop("total_enrollment", None)
                scoped_entry["study_type"] = decision["qualifying_study_type"]
            # Only a product-level Evidence heading (a blend total the input
            # contract projects as the studied material) keeps its binding; an
            # ordinary parent row never lends its reference to a nested extract.
            from scoring_input_contract import get_evidence_subject_rows
            headings = {row.get("raw_source_path") for row in get_evidence_subject_rows(dict(product))
                        if row.get("scoring_input_kind") == "product_level_evidence"}
            anchors = [ref for ref in entry.get("matched_source_row_refs") or [] if isinstance(ref, str)]
            passing = decision.get("matched_source_row_refs") or [decision.get("source_row_ref")]
            if anchors and set(anchors) <= headings and all(
                    isinstance(ref, str) and any(ref.startswith(anchor + ".") for anchor in anchors)
                    for ref in passing):
                # The scope verified the named child of the heading this match
                # binds; the heading keeps its binding (a brand-named blend
                # total is that studied material's amount).
                accepted.append(scoped_entry)
                continue
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
