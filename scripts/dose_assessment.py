"""Canonical typed dose and upper-limit assessment contract.

Enrichment is the sole producer. Scoring and release gates consume the typed
states instead of reinterpreting nullable booleans, failed conversions, or
free-text skip reasons.
"""

from __future__ import annotations

import math
import hashlib
from datetime import datetime, timezone
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from normalization import canonicalize_mass_unit
from scoring_v4.exposure import row_exposure


def reference_semantics_sha256(semantics: dict) -> str:
    """Bind Dose source verification to the complete reviewed reference."""
    return hashlib.sha256(json.dumps(semantics, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _reviewed_reference_correction(result: dict) -> bool:
    review = result.get("correction_review")
    if not isinstance(review, dict):
        return False
    try:
        reviewed = datetime.fromisoformat(review.get("verified_at", ""))
        if reviewed.tzinfo is None or reviewed > datetime.now(timezone.utc):
            return False
    except (ValueError, TypeError):
        return False
    return (review.get("source_sha256") == result.get("content_sha256")
            and review.get("is_complete") is True
            and bool(review.get("source_ids"))
            and isinstance(review.get("source_ids"), list)
            and all(isinstance(source, str) and source.strip() for source in review["source_ids"])
            and bool(review.get("reviewed_by")) and bool(review.get("notes")))


def verified_reference_citations(record: dict) -> bool:
    """Check source proof only; this never establishes Evidence approval."""
    semantics = record.get("reference_semantics")
    provenance = record.get("verification_provenance") or {}
    if not isinstance(provenance, dict):
        return False
    proof = provenance.get("reference_citations")
    if not isinstance(semantics, dict) or not isinstance(proof, dict):
        return False
    sources = semantics.get("source_ids")
    if (not isinstance(sources, list) or not sources
            or any(not isinstance(source, str) or not source.strip() for source in sources)
            or len(set(sources)) != len(sources)
            or proof.get("source_ids") != sources
            or proof.get("is_complete") is not True
            or proof.get("source_sha256") != reference_semantics_sha256(semantics)):
        return False
    try:
        verified = datetime.fromisoformat(proof.get("verified_at", ""))
        if verified.tzinfo is None or verified > datetime.now(timezone.utc):
            return False
    except (ValueError, TypeError):
        return False
    results = proof.get("results")
    if not isinstance(results, list) or len(results) != len(sources):
        return False
    return all(isinstance(result, dict) and result.get("source_id") == source
               and result.get("verified") is True
               and isinstance(result.get("content_sha256"), str)
               and len(result["content_sha256"]) == 64
               and all(char in "0123456789abcdef" for char in result["content_sha256"])
               and bool(result.get("article_title"))
               and all(result.get(flag) is False for flag in
                       ("retracted", "expression_of_concern"))
               and (result.get("has_erratum") is False
                    or (result.get("has_erratum") is True and _reviewed_reference_correction(result)))
               for source, result in zip(sources, results))


ASSESSED_WITHIN_LIMIT = "assessed_within_limit"
ASSESSED_OVER_LIMIT = "assessed_over_limit"
NO_UL_APPLICABLE = "no_ul_applicable"
NOT_DISTINCT_EXPOSURE = "not_distinct_exposure"
UNRESOLVED_UNIT = "unresolved_unit"
UNRESOLVED_FORM = "unresolved_form"
UNRESOLVED_COMPOUND_MASS = "unresolved_compound_mass"
ASSESSMENT_ERROR = "assessment_error"

READINESS_COMPLETE = "complete"
READINESS_INCOMPLETE = "incomplete"
READINESS_NOT_APPLICABLE = "not_applicable"

CONVERSION_CONVERTED = "converted"
CONVERSION_NOT_REQUIRED = "not_required"
CONVERSION_NOT_APPLICABLE = "not_applicable"
CONVERSION_FAILED = "failed"

_NOT_DISTINCT_REASONS = {
    "component_within_assessed_parent_total",
    "composition_share_of_declared_total",
    "form_component_of_declared_total",
    "compound_duplicate_row",
    "vitamin_a_components_own_ul",
    "folate_components_own_ul",
}
_NO_UL_REASONS = {
    "not_ul_applicable",
    "beta_carotene_no_established_ul",
    "provitamin_a_carotenoid_no_established_ul",
    "non_folic_acid_folate_ul_basis",
}
_BOUNDED_UL_REASONS = {
    "worst_case_compound_mass_within_ul",
    "worst_case_folic_acid_within_ul",
    "worst_case_natural_vitamin_e_within_ul",
    "worst_case_preformed_vitamin_a_within_ul",
    "worst_case_vitamin_e_mass_within_ul",
}
_UNRESOLVED_FORM_REASONS = {
    "unresolved_form",
    "unknown_folate_form_lineage",
    "unknown_vitamin_form",
    "mixed_vitamin_a_preformed_fraction_unknown",
    "supplemental_magnesium_fraction_unknown",
}
_UNRESOLVED_UNIT_REASONS = {
    "label_unit_conflict",
    "amount_not_declared",
    "conversion_failed",
    "unit_unrecognized",
    "no_conversion_rule",
    "conversion_exception",
}

_POSITIVE_BENCHMARK_DIRECTIONS = {"positive_strong", "positive_moderate", "positive_weak"}
_CLINICAL_RECORDS_PATH = Path(__file__).resolve().parent / "data" / "backed_clinical_studies.json"


def clinical_research_exposure_assessments(product: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Describe reviewed exposures without supplying adequacy or safety points.

    Enrichment produces this once. Source links and preparation/purpose remain
    owned by clinical applicability; daily quantities remain owned by exposure.
    A missing frequency, member amount or comparable preparation stays unknown.
    """
    from clinical_applicability import _linked_rows, _row_text, _key, assess_clinical_applicability, reviewed_entries
    from evidence_resolver import evidence_record_matches_declared_purpose

    assessments = []
    seen = set()
    for match in (product.get("evidence_data") or {}).get("clinical_matches") or []:
        if not isinstance(match, dict):
            continue
        record = reviewed_entries().get(str(match.get("id") or "")) or {}
        reference = record.get("studied_regimens")
        if not isinstance(reference, dict) or reference.get("kind") != "studied_regimen":
            continue
        scoped = {**match, **record}
        rows = _linked_rows(product, scoped, evidence_only=True,
                            discriminating_terms=(record.get("applicability") or {}).get("required_form_terms"))
        for row in rows:
            ref = row.get("raw_source_path") or row.get("source_row_ref")
            key = (record["id"], ref)
            if key in seen:
                continue
            decision = assess_clinical_applicability(
                product, {**scoped, "matched_source_row_refs": [ref] if ref else []}, assess_amount=False)
            if (decision.get("status") != "applicable"
                    or not evidence_record_matches_declared_purpose(product, row, record)):
                continue
            seen.add(key)
            exposure = row_exposure(product, row, basis="daily", unit=reference.get("unit") or "mg")
            row_reference = reference
            source_text = _row_text(row, source_only=True)
            for preparation in reference.get("preparations") or []:
                groups = preparation.get("required_source_terms") if isinstance(preparation, dict) else None
                if (isinstance(groups, list) and groups and all(
                        isinstance(group, list) and group and any(
                            isinstance(term, str) and _key(term)
                            and " " + _key(term) + " " in source_text for term in group)
                        for group in groups)):
                    row_reference = {**reference, **preparation}
                    break
            bands = row_reference.get("regimens") or []
            valid = (isinstance(bands, list) and all(
                isinstance(band, dict)
                and type(band.get("minimum")) in (int, float)
                and type(band.get("maximum")) in (int, float)
                and _finite_number(band.get("minimum")) is not None
                and _finite_number(band.get("maximum")) is not None
                and 0 < band["minimum"] <= band["maximum"]
                and isinstance(band.get("notes"), str) and band["notes"]
                for band in bands))
            status = "unknown"
            notes = reference.get("unknown_notes") or "Daily research exposure comparison is unavailable."
            low, high = exposure.minimum, exposure.maximum
            if low is not None and high is not None and exposure.uncertainty is None:
                if not valid or not bands:
                    status = "reference_uncertain"
                    notes = reference.get("notes") or "A comparable research exposure reference is not established."
                else:
                    bands = sorted(bands, key=lambda band: band["minimum"])
                    matching = next((b for b in bands if b["minimum"] <= low <= high <= b["maximum"]), None)
                    if matching:
                        status, notes = "matches", matching["notes"]
                    elif high < bands[0]["minimum"]:
                        status, notes = "below", row_reference["below_notes"]
                    elif low > bands[-1]["maximum"]:
                        status, notes = "above", row_reference["above_notes"]
                    elif any(left["maximum"] < low <= high < right["minimum"]
                             for left, right in zip(bands, bands[1:])):
                        status, notes = "between", row_reference["between_notes"]
                    else:
                        status = "crosses_regimens"
                        notes = "The label-directed daily range crosses reviewed study regimens; it does not match a single studied regimen."
            if exposure.uncertainty == "daily_frequency_unknown":
                notes = "Daily research exposure comparison is unavailable because the label does not establish daily serving frequency."
            assessments.append({
                "record_id": record["id"], "name": record["standard_name"],
                "kind": "studied_regimen", "status": status, "notes": notes,
                "source_row_ref": ref, "unit": exposure.unit,
                "minimum": low, "maximum": high, "uncertainty": exposure.uncertainty,
                "studied_population": (record.get("applicability") or {}).get("studied_population"),
                "supported_outcomes": (record.get("applicability") or {}).get("supported_outcomes", []),
                "source_pmids": row_reference.get("source_pmids", []),
            })
    return assessments


@dataclass(frozen=True)
class ClinicalBenchmarkAssessment:
    record_id: str
    benchmark_value: float
    benchmark_maximum: Optional[float]
    benchmark_unit: str
    exposure_value: float
    ratio: float
    source_row_ref: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AggregateClinicalBenchmarkAssessment:
    record_id: str
    benchmark_value: float
    benchmark_maximum: Optional[float]
    benchmark_unit: str
    exposure_value: float
    ratio: float
    member_canonical_ids: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["member_canonical_ids"] = list(self.member_canonical_ids)
        return payload


@lru_cache(maxsize=1)
def _positive_clinical_benchmark_records() -> tuple[Dict[str, Any], ...]:
    raw = json.loads(_CLINICAL_RECORDS_PATH.read_text(encoding="utf-8"))
    return tuple(
        record for record in raw.get("backed_clinical_studies", [])
        if isinstance(record, dict)
        and str(record.get("effect_direction") or "").strip().lower() in _POSITIVE_BENCHMARK_DIRECTIONS
        and (_finite_number(record.get("min_clinical_dose")) or 0) > 0
        # A studied regimen and positive outcome do not establish a minimum
        # or interpolation curve. Only explicitly reviewed numerical meaning
        # is eligible; missing metadata fails closed.
        and (record.get("reference_semantics") or {}).get("reference_type")
            in {"supported_minimum", "bounded_window", "supplement_contribution_policy"}
        and str((record.get("reference_semantics") or {}).get("approval_status") or "").startswith("approved_")
        and (record.get("reference_semantics") or {}).get("curve") != "completed_no_benchmark_neutral"
    )


def _identity_text(value: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _record_names(record: Dict[str, Any]) -> set[str]:
    return {
        text for text in (
            _identity_text(record.get("standard_name")),
            *(_identity_text(alias) for alias in record.get("aliases") or []),
        ) if text
    }


def _source_dose_row(product: Dict[str, Any], row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bind material facts to one original active row, never a borrowed total."""
    from clinical_applicability import _linked_rows
    from scoring_input_contract import _source_tree_rows, is_lent_blend_mass

    ref = row.get("raw_source_path") or row.get("source_row_ref")
    if not isinstance(ref, str) or not ref.strip() or is_lent_blend_mass(row):
        return None
    originals = [source for source in _source_tree_rows(product)
                 if (source.get("raw_source_path") or source.get("source_row_ref")) == ref]
    if len(originals) != 1:
        return None
    linked = _linked_rows(product, {"matched_source_row_refs": [ref]}, source_only=True)
    if len(linked) != 1:
        return None
    source = originals[0]
    literal = source.get("raw_source_text")
    if not isinstance(literal, str) or not literal.strip():
        return None
    if (source.get("canonical_id") and row.get("canonical_id")
            and _identity_text(source["canonical_id"]) != _identity_text(row["canonical_id"])):
        return None
    return source


def _row_names(row: Dict[str, Any], *, source_only: bool = False,
               product: Optional[Dict[str, Any]] = None) -> set[str]:
    qualified = set()
    if source_only and product is not None:
        source = _source_dose_row(product, row)
        if source is None:
            return set()
        # plantPart here belongs to the original source row. The enriched
        # matched form, another row and the product title cannot supply it.
        part = source.get("plantPart")
        if isinstance(part, str) and part.strip():
            qualified.add(_identity_text(source["raw_source_text"] + " " + part))
        row = {"canonical_id": row.get("canonical_id"), "raw_source_text": source["raw_source_text"]}
    if source_only:
        # Preparation binding uses printed source identity, not an enriched
        # matched form or a parent/product name that could lend a brand.
        row = {"canonical_id": row.get("canonical_id"),
               "name": row.get("raw_source_text") or row.get("name"),
               "standard_name": row.get("source_label_name") or row.get("name")}
    return qualified | {
        text for text in (
            _identity_text(row.get("canonical_id")),
            _identity_text(row.get("standard_name") or row.get("standardName")),
            _identity_text(row.get("name")),
            _identity_text(row.get("matched_form")),
        ) if text
    }


def _dose_source_preparation_matches(product: Dict[str, Any], row: Dict[str, Any], record: Dict[str, Any]) -> bool:
    """Apply source physical constraints under the selected Dose reference scope."""
    from clinical_applicability import _row_text, _valid_policy
    from normalization import find_affirmative_label_match, normalize_text
    import re

    source = _source_dose_row(product, row)
    if source is None:
        return False
    exact_preparation = (record.get("reference_semantics") or {}).get("scope") == "exact_preparation"
    policy = record.get("applicability")
    if policy is None:
        return not exact_preparation
    if not _valid_policy(policy) or policy.get("scope") != "ingredient":
        return False
    if exact_preparation and policy.get("dosage_forms"):
        from form_factor_normalizer import FORM_FACTOR_UNKNOWN, canonicalize_form_factor
        # Delivery is an original product fact, separate from the ingredient's
        # same-row identity. A title or an enrichment guess cannot supply it.
        physical = product.get("physicalState")
        if not isinstance(physical, (dict, str)):
            return False
        description = ((physical.get("langualCodeDescription") or physical.get("name"))
                       if isinstance(physical, dict) else physical)
        code = physical.get("langualCode") if isinstance(physical, dict) else None
        by_code = canonicalize_form_factor(None, langual_code=code)
        by_text = canonicalize_form_factor(description)
        if by_code != FORM_FACTOR_UNKNOWN and by_text != FORM_FACTOR_UNKNOWN and by_code != by_text:
            return False
        delivery = canonicalize_form_factor(description, langual_code=code)
        allowed = {canonicalize_form_factor(value) for value in policy["dosage_forms"]}
        if FORM_FACTOR_UNKNOWN in allowed or delivery == FORM_FACTOR_UNKNOWN or delivery not in allowed:
            return False
    if exact_preparation and (
            policy.get("require_source_label_form") is not True
            or not policy.get("required_form_terms")
            or _identity_text(source["raw_source_text"]) not in _record_names(record)):
        return False
    # Notes on IQM rows are curated bio context. Only the original linked
    # row's notes and source taxonomy can contradict a literal preparation.
    # Original whole-row quantity may qualify a finished-material source
    # bridge. This private assertion is not a daily dose or efficacy bound.
    quantity_text = ""
    try:
        quantity = float(source.get("quantity"))
        unit = canonicalize_mass_unit(str(source.get("unit") or ""))
        if math.isfinite(quantity) and quantity > 0 and unit:
            quantity_text = f"Quantity: {quantity:g} {unit}"
    except (TypeError, ValueError, OverflowError):
        pass
    text = "; ".join(normalize_text(str(value)) for value in (
        _row_text(source, source_only=True, preserve_punctuation=True), source.get("notes"), quantity_text,
        "PlantPart: " + str(source["plantPart"]) if source.get("plantPart") else "",
        "Genus: " + str(source["genus"]) if source.get("genus") else "",
        "Species: " + str(source["species"]) if source.get("species") else "") if value)
    # A no-DER scope excludes every affirmative declared ratio, not a
    # finite list of ratios seen during review. Keep this feature private to
    # source matching and preserve the shared clause-negation semantics.
    ratio_pattern = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?(?![\w.])")
    ratio_feature = "declared extraction ratio"
    has_declared_ratio = False
    declared_ratios = {re.sub(r"\s+", "", ratio.group()) for ratio in ratio_pattern.finditer(text)}
    for ratio in ratio_pattern.finditer(text):
        marked = text[:ratio.start()] + ratio_feature + text[ratio.end():]
        if find_affirmative_label_match(re.compile(re.escape(ratio_feature), re.I), marked):
            text += "; " + ratio_feature
            has_declared_ratio = True
            break

    def present(term: str) -> bool:
        return bool(find_affirmative_label_match(
            re.compile(r"(?<!\w)" + re.escape(normalize_text(term)) + r"(?!\w)", re.I), text))

    if any(present(term) for term in policy.get("excluded_form_terms", [])):
        return False
    # Existing required_form_terms is an OR of complete source assertions.
    # Curated IQM biology and a product title cannot supply physical facts.
    # Clinical preparation restrictions and a general Dose determination are
    # separate policies. Only explicit Dose exact_preparation scope requires
    # this record's complete source assertions on every selection path.
    required = (policy.get("required_form_terms") or []) if exact_preparation else []
    # "std." is a label abbreviation, not a sentence boundary. Preserve
    # measurement punctuation (especially %) when matching material assertions.
    required_text = text.replace("std.", "std")
    def required_present(term: str) -> bool:
        # Policy assertions use the cleaner's existing structured-note syntax.
        # Parse the policy, never reparse source notes to refill a missing fact.
        from enhanced_normalizer import EnhancedDSLDNormalizer
        for clause in term.split(";"):
            if clause.lstrip().partition(":")[0].lower() not in {"plantpart", "genus", "species"}:
                # A literal nested form may describe its own source tissue
                # (e.g. orange peel within Cordiart), not the parent's part.
                continue
            expected = EnhancedDSLDNormalizer._parse_botanical_details(clause)
            # A literal mixed-part statement can be retained without a typed
            # part. An independently supplied conflicting typed part cannot
            # override that same-row source assertion.
            if (clause.lstrip().partition(":")[0].lower() == "plantpart"
                    and "plantPart" not in expected and source.get("plantPart")
                    and normalize_text(str(source["plantPart"])) != normalize_text(clause.partition(":")[2])):
                return False
            if any(normalize_text(str(source.get(field) or "")) != normalize_text(str(expected[field]))
                   for field in ("plantPart", "genus", "species") if field in expected):
                return False
        assertion = normalize_text(term).replace("std.", "std")
        if has_declared_ratio and re.search(r"\bder not declared\b", assertion):
            # An explicit absence assertion cannot coexist with a declared
            # ratio. A separate approved ratio-specific OR branch may match.
            return False
        # Semicolons join required facts on this one original source row;
        # they are not a demand that the label printed fields consecutively.
        # Each material clause still uses the canonical negation owner.
        for raw_clause in assertion.split(";"):
            clause = raw_clause.strip()
            # A ratio clause names the row's one declared ratio: "4:1" is not
            # proven by "4:1.5", "4:1 to 10:1" or "10:1 and 4:1".
            if ratio_pattern.fullmatch(clause) and declared_ratios != {re.sub(r"\s+", "", clause)}:
                return False
            pattern = re.compile(r"(?<!\w)" + re.escape(clause) + r"(?!\w)", re.I)
            if not clause or not find_affirmative_label_match(pattern, required_text):
                return False
            # A second, negated assertion is a conflict, not proof supplied
            # by an earlier affirmative occurrence elsewhere on the same row.
            for context in re.split(r"[.;!?\r\n]+|\b(?:but|however)\b", required_text, flags=re.I):
                if pattern.search(context) and not find_affirmative_label_match(pattern, context):
                    return False
        return True

    return not required or any(required_present(term) for term in required)



def positive_clinical_benchmark(
    product: Dict[str, Any], row: Dict[str, Any],
) -> Optional[ClinicalBenchmarkAssessment]:
    """Return an exact, positive, applicable preparation benchmark for ``row``.

    Clinical records remain the source of the reviewed benchmark.  Exact
    enrichment source linkage is authoritative.  A branded whole-preparation
    row may also match its own registry name/alias; generic parent or member
    identity never borrows that branded benchmark.  Null/mixed/inapplicable
    records are absent from the eligible record set. Literature studied-dose
    exposures remain descriptive: a positive outcome at a discrete regimen
    does not establish a minimum effective dose or an interpolation curve.
    """
    row_ref = str(row.get("raw_source_path") or row.get("source_row_ref") or "").strip()
    row_names = _row_names(row)
    matches = [
        match for match in ((product.get("evidence_data") or {}).get("clinical_matches") or [])
        if isinstance(match, dict)
    ]
    candidates: list[Dict[str, Any]] = []
    eligible_by_id = {str(record.get("id")): record for record in _positive_clinical_benchmark_records()}

    def applicable_record(record: Dict[str, Any], *, source_refs: Iterable[str] = ()) -> bool:
        from clinical_applicability import assess_clinical_applicability
        from evidence_resolver import evidence_record_matches_declared_purpose

        scoped_record = {**record, "matched_source_row_refs": [
            ref for ref in source_refs if ref
        ]}
        decision = assess_clinical_applicability(product, scoped_record, assess_amount=False)
        return (
            decision.get("status") in {"applicable", "not_curated"}
            and evidence_record_matches_declared_purpose(product, row, record)
        )

    for match in matches:
        record = eligible_by_id.get(str(match.get("id") or ""))
        if record is None:
            continue
        is_brand = str(record.get("id") or "").upper().startswith("BRAND_")
        if is_brand and not (row_names & _record_names(record)):
            # Source linkage can associate a blend member or generic parent
            # with the whole branded intervention. Dose requires the exact
            # branded preparation on this row.
            continue
        refs = {str(ref).strip() for ref in match.get("matched_source_row_refs") or [] if str(ref).strip()}
        if row_ref and row_ref in refs and applicable_record(record, source_refs=refs):
            candidates.append(record)
    for record in _positive_clinical_benchmark_records():
        if not str(record.get("id") or "").upper().startswith("BRAND_"):
            continue
        if (
            row_names & _record_names(record)
            and record not in candidates
            and applicable_record(record, source_refs=[row_ref] if row_ref else [])
        ):
            candidates.append(record)

    exact_branded = [
        record for record in candidates
        if str(record.get("id") or "").upper().startswith("BRAND_")
        and row_names & _record_names(record)
    ]
    if exact_branded:
        candidates = exact_branded

    assessments = []
    for record in candidates:
        benchmark = _finite_number(record.get("min_clinical_dose"))
        unit = str(record.get("dose_unit") or "mg").strip().lower()
        if benchmark is None or benchmark <= 0:
            continue
        exposure = row_exposure(product, row, basis="daily", unit=unit).benchmark_amount
        if exposure is None or exposure <= 0:
            continue
        assessments.append(ClinicalBenchmarkAssessment(
            record_id=str(record.get("id") or ""),
            benchmark_value=benchmark,
            benchmark_maximum=_finite_number(record.get("max_studied_clinical_dose")),
            benchmark_unit=unit,
            exposure_value=exposure,
            ratio=exposure / benchmark,
            source_row_ref=row_ref,
        ))
    return min(assessments, key=lambda item: (item.benchmark_value, item.record_id), default=None)


def positive_aggregate_clinical_benchmark(
    product: Dict[str, Any], rows: Iterable[Dict[str, Any]],
) -> Optional[AggregateClinicalBenchmarkAssessment]:
    """Return one exact benchmark for a reviewed multi-ingredient formula.

    Aggregate records such as the complete BCAA triad describe one intervention,
    so Dose must sum its required members once.  Every required identity must be
    present exactly once with a compatible disclosed exposure, and the curated
    aggregate record must already be projected into the product's clinical
    matches.  Individual members never borrow the formula benchmark.
    """
    eligible_by_id = {
        str(record.get("id")): record
        for record in _positive_clinical_benchmark_records()
        if isinstance(record.get("aggregate_canonical_ids"), list)
        and record.get("aggregate_canonical_ids")
    }
    matches = [
        match for match in ((product.get("evidence_data") or {}).get("clinical_matches") or [])
        if isinstance(match, dict) and str(match.get("id") or "") in eligible_by_id
    ]
    rows_by_canonical: Dict[str, list[Dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if canonical:
            rows_by_canonical.setdefault(canonical, []).append(row)

    assessments: list[AggregateClinicalBenchmarkAssessment] = []
    for match in matches:
        record = eligible_by_id[str(match.get("id"))]
        members = tuple(
            str(value).strip().lower()
            for value in record.get("aggregate_canonical_ids") or []
            if str(value).strip()
        )
        if not members or any(len(rows_by_canonical.get(member, [])) != 1 for member in members):
            continue
        benchmark = _finite_number(record.get("min_clinical_dose"))
        unit = str(record.get("dose_unit") or "mg").strip().lower()
        if benchmark is None or benchmark <= 0:
            continue
        exposures = [
            row_exposure(product, rows_by_canonical[member][0], basis="daily", unit=unit).benchmark_amount
            for member in members
        ]
        if any(value is None or value <= 0 for value in exposures):
            continue
        exposure = sum(float(value) for value in exposures if value is not None)
        assessments.append(AggregateClinicalBenchmarkAssessment(
            record_id=str(record.get("id") or ""),
            benchmark_value=benchmark,
            benchmark_maximum=_finite_number(record.get("max_studied_clinical_dose")),
            benchmark_unit=unit,
            exposure_value=exposure,
            ratio=exposure / benchmark,
            member_canonical_ids=members,
        ))
    return min(assessments, key=lambda item: (item.benchmark_value, item.record_id), default=None)


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


@dataclass(frozen=True)
class DoseAssessment:
    source_row_ref: Optional[str]
    source_path: Optional[str]
    linked_row_refs: tuple[str, ...]
    owner_row_ref: Optional[str]
    ingredient: str
    canonical_id: Optional[str]
    dose_class: Optional[str]
    evidence_type: Optional[str]
    material: bool
    source_value: Optional[float]
    source_unit: Optional[str]
    normalized_value: Optional[float]
    normalized_unit: Optional[str]
    conversion_rule_id: Optional[str]
    conversion_status: str
    ul_assessment_status: str
    ul_value: Optional[float]
    ul_unit: Optional[str]
    pct_ul: Optional[float]
    ul_gate_eligible: Optional[bool]
    reason_code: Optional[str]
    readiness: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["linked_row_refs"] = list(self.linked_row_refs)
        return payload


def build_dose_assessment(
    *,
    source_row_ref: Any,
    source_path: Any,
    linked_row_refs: Any,
    owner_row_ref: Any,
    ingredient: Any,
    canonical_id: Any,
    dose_class: Any,
    evidence_type: Any,
    source_value: Any,
    source_unit: Any,
    normalized_value: Any,
    normalized_unit: Any,
    conversion_evidence: Any,
    dose_role: Any,
    skip_ul_check: bool,
    skip_ul_reason: Any,
    ul_status: Any,
    ul_value: Any,
    ul_unit: Any,
    pct_ul: Any,
    over_ul: bool,
    ul_gate_eligible: Any,
    ul_gate_ineligible_reason: Any,
    assessment_error: Any = None,
) -> DoseAssessment:
    """Build one typed result from a single source-label exposure row."""
    evidence = conversion_evidence if isinstance(conversion_evidence, dict) else {}
    source_amount = _finite_number(source_value)
    normalized_amount = _finite_number(normalized_value)
    material = bool(source_amount is not None and source_amount > 0)
    reason = str(skip_ul_reason or ul_gate_ineligible_reason or "").strip() or None
    role = str(dose_role or "").strip().lower()

    if assessment_error:
        conversion_status = (
            CONVERSION_NOT_REQUIRED
            if normalized_amount is not None
            else CONVERSION_FAILED
        )
        assessment_status = ASSESSMENT_ERROR
        readiness = READINESS_INCOMPLETE
        reason = "dose_assessment_exception"
    else:
        rule_id = str(evidence.get("conversion_rule_id") or "").strip().lower()
        if evidence.get("success") is True and normalized_amount is not None:
            conversion_status = (
                CONVERSION_NOT_REQUIRED
                if rule_id in {
                    "identity_mass_passthrough",
                    "identity",
                    "mass_conversion",
                }
                and _finite_number(evidence.get("conversion_factor")) == 1.0
                else CONVERSION_CONVERTED
            )
        elif evidence.get("nonfatal_reason") and normalized_amount is not None:
            conversion_status = CONVERSION_NOT_REQUIRED
        elif (
            reason in _NO_UL_REASONS
            or reason in _BOUNDED_UL_REASONS
            or role == "form_component"
        ):
            conversion_status = (
                CONVERSION_NOT_APPLICABLE
                if normalized_amount is None
                else CONVERSION_CONVERTED
            )
        else:
            conversion_status = CONVERSION_FAILED

        normalized_ul_status = str(ul_status or "").strip().lower()
        if reason in _NOT_DISTINCT_REASONS or role == "form_component":
            assessment_status = NOT_DISTINCT_EXPOSURE
            readiness = READINESS_NOT_APPLICABLE
        elif (
            reason in _NO_UL_REASONS
            or normalized_ul_status.startswith("not_determined")
            or normalized_ul_status.startswith("not_applicable")
        ):
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE
            # No UL cannot validate an unresolved nutrient-specific unit.
            # A known native mass (e.g. alpha-carotene mg) remains usable even
            # without retinol equivalence. Do not invent that converted value.
            # Native activity/count units with no nutrient rule are unchanged.
            if (
                material
                and evidence.get("success") is False
                and evidence.get("conversion_rule_id")
                and not evidence.get("nonfatal_reason")
                and canonicalize_mass_unit(source_unit) not in {"g", "mg", "mcg"}
            ):
                conversion_status = CONVERSION_FAILED
                readiness = READINESS_INCOMPLETE
                reason = "conversion_failed"
        elif reason in _UNRESOLVED_FORM_REASONS:
            assessment_status = UNRESOLVED_FORM
            readiness = READINESS_INCOMPLETE
        elif (
            reason in _BOUNDED_UL_REASONS
            and _finite_number(pct_ul) is not None
        ):
            assessment_status = ASSESSED_WITHIN_LIMIT
            readiness = READINESS_COMPLETE
        elif (
            reason == "compound_mass_not_elemental"
            or (
                ul_gate_eligible is False
                and str(ul_gate_ineligible_reason or "").strip()
                == "compound_mass_not_elemental"
            )
        ):
            assessment_status = UNRESOLVED_COMPOUND_MASS
            readiness = READINESS_INCOMPLETE
        elif reason in _UNRESOLVED_UNIT_REASONS or normalized_amount is None:
            assessment_status = UNRESOLVED_UNIT
            readiness = READINESS_INCOMPLETE
        elif over_ul:
            assessment_status = ASSESSED_OVER_LIMIT
            readiness = READINESS_COMPLETE
        elif _finite_number(pct_ul) is not None:
            assessment_status = ASSESSED_WITHIN_LIMIT
            readiness = READINESS_COMPLETE
        elif normalized_ul_status.startswith("not_applicable"):
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE
        elif skip_ul_check:
            assessment_status = UNRESOLVED_UNIT
            readiness = READINESS_INCOMPLETE
        else:
            assessment_status = NO_UL_APPLICABLE
            readiness = READINESS_NOT_APPLICABLE

    return DoseAssessment(
        source_row_ref=str(source_row_ref or "").strip() or None,
        source_path=str(source_path or "").strip() or None,
        linked_row_refs=tuple(dict.fromkeys(
            str(value).strip()
            for value in (linked_row_refs or [])
            if str(value).strip()
        )),
        owner_row_ref=str(owner_row_ref or "").strip() or None,
        ingredient=str(ingredient or "").strip(),
        canonical_id=str(canonical_id or "").strip() or None,
        dose_class=str(dose_class or "").strip() or None,
        evidence_type=str(evidence_type or "").strip() or None,
        material=material,
        source_value=source_amount,
        source_unit=str(source_unit or "").strip() or None,
        normalized_value=normalized_amount,
        normalized_unit=str(normalized_unit or "").strip() or None,
        conversion_rule_id=(
            str(evidence.get("conversion_rule_id") or "").strip() or None
        ),
        conversion_status=conversion_status,
        ul_assessment_status=assessment_status,
        ul_value=_finite_number(ul_value),
        ul_unit=str(ul_unit or "").strip() or None,
        pct_ul=_finite_number(pct_ul),
        ul_gate_eligible=(
            ul_gate_eligible if isinstance(ul_gate_eligible, bool) else None
        ),
        reason_code=reason,
        readiness=readiness,
    )


def has_incomplete_material_dose_assessment(
    assessments: Iterable[Any],
) -> bool:
    """Return whether any material exposure is not ready for live scoring."""
    for assessment in assessments or []:
        if not isinstance(assessment, dict):
            return True
        if (
            assessment.get("material") is True
            and assessment.get("readiness")
            not in {READINESS_COMPLETE, READINESS_NOT_APPLICABLE}
        ):
            return True
    return False
