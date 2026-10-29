from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_source_of_truth_contract import audit_scoring, audit_scoring_static  # noqa: E402


def _args(path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        product_file=[str(path)],
        enriched_file=[],
        enriched_dir=[],
        products_dir=None,
        dist_dir=None,
        strict_release=True,
        matrix=str(SCRIPTS_ROOT / "contracts" / "source_of_truth_matrix.json"),
    )


def _write(path: Path, product: dict) -> None:
    path.write_text(json.dumps([product]), encoding="utf-8")


def _scored(**overrides) -> dict:
    assessment_readiness = {
        "release_assessment": {"is_complete": True, "blockers": [], "unfinished_source_assessment": None},
        "enforcement_mode": "enforced",
        "enforced_dimensions": ["dose", "identity", "route", "verification"],
        "is_live_ready": True,
        "unavailable_reasons": [],
        "identity": {"readiness": "complete", "migration_inference": False},
        "dose": {"readiness": "complete", "migration_inference": False},
        "evidence": {"readiness": "complete", "migration_inference": False},
        "verification": {"readiness": "complete", "migration_inference": False},
        "route": {"readiness": "complete", "migration_inference": False},
    }
    product = {
        "dsld_id": "P1",
        "product_name": "Strict Product",
        "verdict": "SAFE",
        "quality_score": 50.0,
        "score_80": 50.0,
        "score_100_equivalent": 62.5,
        "mapped_coverage": 1.0,
        "quality_score_status": "scored",
        "score_basis": "bioactives_scored",
        "_v4_completeness_gate": {
            "is_live_eligible": True,
            "verdict": None,
        },
        "assessment_readiness": assessment_readiness,
        "scoring_ingredients_source": "ingredient_quality_data.ingredients_scorable",
        "scoring_fallbacks_used": [],
        "strict_scoring_contract": {"passed": True, "findings": []},
        "iqd_contract_diagnostics": {
            "scoring_ingredients_source": "ingredient_quality_data.ingredients_scorable",
            "iqd_ingredients_fallback_used": False,
            "scoring_fallbacks_used": [],
        },
    }
    product.update(overrides)
    return product


def test_scoring_audit_passes_strict_scored_product(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored())

    assert audit_scoring(_args(path)) == []


def test_scoring_audit_products_dir_reads_only_scored_outputs(tmp_path: Path) -> None:
    products_dir = tmp_path / "products"
    scored = products_dir / "output_Test_scored" / "scored" / "scored_batch_1.json"
    cleaned = products_dir / "output_Test" / "cleaned" / "cleaned_batch_1.json"
    enriched = products_dir / "output_Test_enriched" / "enriched" / "enriched_batch_1.json"
    report = products_dir / "output_Test_scored" / "reports" / "scoring_summary.json"

    for path, payload in (
        (scored, _scored()),
        (cleaned, {"dsld_id": "C1", "product_name": "Cleaned only"}),
        (enriched, {"dsld_id": "E1", "product_name": "Enriched only"}),
    ):
        path.parent.mkdir(parents=True)
        _write(path, payload)
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"summary": "not a scored product payload"}), encoding="utf-8")

    args = argparse.Namespace(
        product_file=[],
        enriched_file=[],
        enriched_dir=[],
        products_dir=str(products_dir),
        dist_dir=None,
        strict_release=True,
        matrix=str(SCRIPTS_ROOT / "contracts" / "source_of_truth_matrix.json"),
    )

    assert audit_scoring(args) == []


def test_scoring_audit_rejects_iqd_ingredients_fallback(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored(
        scoring_ingredients_source="ingredient_quality_data.ingredients",
        iqd_contract_diagnostics={
            "scoring_ingredients_source": "ingredient_quality_data.ingredients",
            "iqd_ingredients_fallback_used": True,
            "scoring_fallbacks_used": [
                {"fallback_class": "old_batch_compatibility", "fallback_reason": "legacy"}
            ],
        },
    )
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SOURCE_FORBIDDEN" in codes
    assert "SCORING_USED_IQD_FALLBACK" in codes


def test_scoring_audit_rejects_failed_strict_contract(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            strict_scoring_contract={
                "passed": False,
                "findings": ["missing_required_fields:raw_source_path"],
            }
        ),
    )

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_STRICT_CONTRACT_FAILED" in codes


def test_scoring_audit_keeps_mapping_coverage_separate_from_verdict(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored(mapped_coverage=0.2))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SAFE_LOW_COVERAGE" not in codes


def test_scoring_audit_requires_full_mapping_for_scored_product(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored(mapped_coverage=0.9999))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_LIVE_MAPPING_INCOMPLETE" in codes


def test_scoring_audit_requires_typed_readiness_for_scored_product(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product.pop("assessment_readiness")
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_READINESS_MISSING" in codes


def test_scoring_audit_rejects_legacy_readiness_inference(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product["assessment_readiness"]["dose"]["migration_inference"] = True
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_MIGRATION_INFERENCE" in codes


def test_scoring_audit_rejects_shadow_mode_readiness(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product["assessment_readiness"]["enforcement_mode"] = "shadow"
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_READINESS_NOT_ENFORCED" in codes


def test_scoring_audit_rejects_a_self_weakened_dimension_contract(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    product = _scored()
    product["assessment_readiness"]["enforced_dimensions"] = [
        "identity",
        "route",
        "verification",
    ]
    product["assessment_readiness"]["dose"]["readiness"] = "incomplete"
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_ASSESSMENT_ENFORCED_DIMENSIONS_MISMATCH" in codes
    assert "SCORING_ASSESSMENT_DIMENSION_INCOMPLETE" in codes


def test_scoring_audit_rejects_unresolved_dose_on_safety_suppressed_product(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    product = _scored(
        verdict="BLOCKED",
        quality_score_status="suppressed_safety",
        scoring_status="suppressed_safety",
    )
    product["assessment_readiness"]["is_live_ready"] = False
    product["assessment_readiness"]["unavailable_reasons"] = [
        "dose_assessment_readiness"
    ]
    product["assessment_readiness"]["dose"]["readiness"] = "incomplete"
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SUPPRESSED_SAFETY_DOSE_INCOMPLETE" in codes


def _confirmed_ban(**overrides) -> dict:
    """The safety gate's record of a confirmed, policy-verified ban."""
    decision = {
        "verdict": "BLOCKED",
        "winning_rule": "NOOTROPIC_SULBUTIAMINE",
        "substance": "Sulbutiamine",
        "matched_role": "active",
        "match_resolution": "confirmed",
        "reason_code": "banned_ingredient",
        "policy_basis": {
            "status": "banned",
            "ban_context": "substance",
            "policy_verification_status": "verified",
        },
    }
    decision.update(overrides)
    return decision


def _codes_for_unassessed_dose(tmp_path: Path, verdict: str, decision) -> set:
    path = tmp_path / "scored.json"
    product = _scored(
        verdict=verdict,
        quality_score_status="suppressed_safety",
        scoring_status="suppressed_safety",
    )
    if decision is not None:
        product["safety_decision"] = decision
    product["assessment_readiness"]["dose"]["readiness"] = "incomplete"
    _write(path, product)
    return {finding.code for finding in audit_scoring(_args(path))}


def _confirmed_recall() -> dict:
    return _confirmed_ban(
        verdict="UNSAFE",
        winning_rule="RECALL_RULE",
        substance="Recalled ingredient",
        reason_code="recalled_ingredient",
        policy_basis={"status": "recalled", "policy_verification_status": "verified"},
    )


def test_scoring_audit_never_holds_a_confirmed_ban_or_recall_for_its_dose(
    tmp_path: Path,
) -> None:
    # A banned or recalled ingredient decides the verdict at any amount, so its
    # dose decides nothing. The hold hid single-ingredient Sulbutiamine (252933):
    # no dose could be assessed, so a scan said "not found" instead of "Do not use".
    # The EDTA chelator entries declare their own reason code; the policy tier
    # is still a confirmed, verified ban.
    edta = _confirmed_ban(
        winning_rule="BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM",
        substance="Edetate Disodium",
        reason_code="NON_ROUTINE_CHELATOR",
    )
    for name, verdict, decision in (
        ("ban", "BLOCKED", _confirmed_ban()),
        ("recall", "UNSAFE", _confirmed_recall()),
        ("declared_reason", "BLOCKED", edta),
    ):
        case_dir = tmp_path / name
        case_dir.mkdir()
        codes = _codes_for_unassessed_dose(case_dir, verdict, decision)
        assert "SCORING_SUPPRESSED_SAFETY_DOSE_INCOMPLETE" not in codes, name


def test_scoring_audit_holds_every_other_suppressed_verdict_for_its_dose(
    tmp_path: Path,
) -> None:
    cases = {
        "likely_match": ("BLOCKED", _confirmed_ban(match_resolution="likely")),
        "unverified_policy": ("BLOCKED", _confirmed_ban(policy_basis={
            "status": "banned", "policy_verification_status": "needs_review",
        })),
        "ban_on_unsafe_product": ("UNSAFE", _confirmed_ban()),
        "recall_on_blocked_product": ("BLOCKED", _confirmed_recall()),
    }
    for name, (verdict, decision) in cases.items():
        case_dir = tmp_path / name
        case_dir.mkdir()
        codes = _codes_for_unassessed_dose(case_dir, verdict, decision)
        assert "SCORING_SUPPRESSED_SAFETY_DOSE_INCOMPLETE" in codes, name


def test_a_confirmed_ban_still_cannot_rely_on_legacy_dose_inference(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    product = _scored(
        verdict="BLOCKED",
        quality_score_status="suppressed_safety",
        scoring_status="suppressed_safety",
        safety_decision=_confirmed_ban(),
    )
    product["assessment_readiness"]["dose"]["migration_inference"] = True
    _write(path, product)

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SUPPRESSED_SAFETY_DOSE_INCOMPLETE" in codes


@pytest.mark.parametrize("readiness", [None, "", "unknown", "corrupt"])
def test_scoring_audit_requires_typed_incomplete_dose_for_ban_exception(
    tmp_path: Path, readiness: str | None,
) -> None:
    path = tmp_path / "scored.json"
    product = _scored(
        verdict="BLOCKED",
        quality_score_status="suppressed_safety",
        scoring_status="suppressed_safety",
        safety_decision=_confirmed_ban(),
    )
    product["assessment_readiness"]["dose"]["readiness"] = readiness
    _write(path, product)
    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SUPPRESSED_SAFETY_DOSE_INCOMPLETE" in codes


def test_scoring_audit_rejects_retired_nutrition_only_verdict(tmp_path: Path) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            verdict="NUTRITION_ONLY",
            quality_score=None,
            score_80=None,
            score_100_equivalent=None,
            mapped_coverage=None,
            scoring_status="not_applicable",
            quality_score_status="not_scored",
            score_basis="nutrition_only_food_shape",
            scoring_ingredients_source=None,
            _v4_completeness_gate={
                "is_live_eligible": False,
                "verdict": "NOT_SCORED",
            },
        ),
    )

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_RETIRED_NUTRITION_ONLY" in codes


def test_scoring_audit_uses_live_eligibility_not_nullable_gate_verdict(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            _v4_completeness_gate={
                "is_live_eligible": True,
                "verdict": None,
            }
        ),
    )

    assert audit_scoring(_args(path)) == []


def test_scoring_audit_rejects_scored_product_that_is_not_live_eligible(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scored.json"
    _write(
        path,
        _scored(
            _v4_completeness_gate={
                "is_live_eligible": False,
                "verdict": "NOT_SCORED",
            }
        ),
    )

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_COMPLETENESS_STATUS_MISMATCH" in codes


def test_static_audit_flags_direct_v4_iqd_fallback(tmp_path: Path) -> None:
    path = tmp_path / "bad_module.py"
    path.write_text("rows = iqd.get('ingredients') or product.get('activeIngredients')\n", encoding="utf-8")

    args = argparse.Namespace(path=[str(path)], strict_release=True, matrix="")
    codes = {finding.code for finding in audit_scoring_static(args)}

    assert "V4_IQD_INGREDIENTS_FALLBACK" in codes
    assert "V4_RAW_ACTIVE_FALLBACK" in codes


def test_static_audit_current_v4_modules_have_no_forbidden_fallbacks() -> None:
    args = argparse.Namespace(
        path=[str(SCRIPTS_ROOT / "scoring_v4")],
        strict_release=True,
        matrix="",
    )

    assert audit_scoring_static(args) == []


def test_scoring_audit_refuses_a_failed_safety_lookup(tmp_path: Path) -> None:
    # A resolver that could not check a label withholds the score (RR-08), and
    # the builder then leaves the product out of the catalog. At release that is
    # a bug to fix, never a smaller catalog to publish: a failure that hits every
    # product would otherwise ship an empty catalog without a single error.
    path = tmp_path / "scored.json"
    _write(path, _scored(
        verdict="NOT_SCORED",
        quality_score_status="not_scored",
        score_100_equivalent=None,
        score_unavailable_reason="safety_assessment_incomplete",
        _v4_completeness_gate={"is_live_eligible": True, "verdict": None},
    ))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SAFETY_ASSESSMENT_INCOMPLETE" in codes


@pytest.mark.parametrize("overrides", [
    # The completeness gate runs first, so its reason wins over the safety one.
    dict(verdict="NOT_SCORED", quality_score_status="not_scored", score_100_equivalent=None,
         score_unavailable_reason="blocked_by_completeness_gate",
         _v4_completeness_gate={"is_live_eligible": False, "verdict": "NOT_SCORED"}),
    # A hard verdict still ships, but the lookup that failed may have been the
    # one that would have found another ban: the build is unchecked either way.
    dict(verdict="BLOCKED", quality_score_status="suppressed_safety", score_100_equivalent=None,
         score_unavailable_reason="blocked_by_safety_gate"),
])
def test_scoring_audit_reads_the_resolver_errors_not_the_final_reason(tmp_path: Path, overrides) -> None:
    path = tmp_path / "scored.json"
    _write(path, _scored(_v4_safety_gate={"ingredient_assessment_errors": ["banned_recalled: lookup failed"]}, **overrides))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SAFETY_ASSESSMENT_INCOMPLETE" in codes


def test_scoring_audit_treats_a_capture_gap_as_a_fact(tmp_path: Path) -> None:
    from scoring_v4.gate_safety import _CAPTURE_GAP_PREFIX

    path = tmp_path / "scored.json"
    _write(path, _scored(_v4_safety_gate={"ingredient_assessment_errors": [_CAPTURE_GAP_PREFIX + " label rows"]}))

    codes = {finding.code for finding in audit_scoring(_args(path))}
    assert "SCORING_SAFETY_ASSESSMENT_INCOMPLETE" not in codes

@pytest.mark.parametrize('status', ['scored', 'not_scored', 'suppressed_safety'])
def test_strict_release_requires_completion_receipt_for_every_record(tmp_path, status):
    product = _scored(quality_score_status=status)
    product['assessment_readiness'].pop('release_assessment')
    path = tmp_path / 'scored.json'
    _write(path, product)
    codes = {f.code for f in audit_scoring(_args(path))}
    assert 'SCORING_RELEASE_ASSESSMENT_MISSING' in codes


def test_strict_release_rejects_unfinished_source_even_with_complete_dimensions(tmp_path):
    product = _scored()
    product['assessment_readiness']['release_assessment'] = {
        'is_complete': False, 'blockers': ['dose_amount_unread'],
        'unfinished_source_assessment': 'dose_amount_unread',
    }
    path = tmp_path / 'scored.json'
    _write(path, product)
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(_args(path))}


def test_warning_containment_cannot_erase_release_completion_blocker(tmp_path, monkeypatch):
    import audit_source_of_truth_contract as audit
    product = _scored(quality_score_status='not_scored', verdict='NOT_SCORED',
                      quality_score_v4_100=None, score_100_equivalent=None)
    product['assessment_readiness']['release_assessment'] = {
        'is_complete': False, 'blockers': ['evidence_assessment_incomplete'],
        'unfinished_source_assessment': None,
    }
    monkeypatch.setattr(audit, 'verified_contract_quarantines', lambda _path: {})
    monkeypatch.setattr(audit, 'verified_warning_only_products',
                        lambda _path, blocked_only=False: set() if blocked_only else {'P1'})
    path = tmp_path / 'scored.json'
    _write(path, product)
    args = _args(path)
    args.dist_dir = str(tmp_path)
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}


def test_completion_preflight_defers_candidate_contract_but_not_completion(tmp_path):
    product = _scored(scoring_ingredients_source='deliberately_invalid_source')
    path = tmp_path / 'scored.json'
    _write(path, product)
    args = _args(path)
    args.completion_only = True
    assert audit_scoring(args) == []
    args.completion_only = False
    assert 'SCORING_SOURCE_FORBIDDEN' in {f.code for f in audit_scoring(args)}


@pytest.mark.parametrize('status', ['scored', 'not_scored', 'suppressed_safety'])
def test_completion_preflight_enforces_missing_receipt_without_strict_flag(tmp_path, status):
    product = _scored(quality_score_status=status)
    product['assessment_readiness'].pop('release_assessment')
    path = tmp_path / 'scored.json'
    _write(path, product)
    args = _args(path)
    args.completion_only = True
    args.strict_release = False
    assert {f.code for f in audit_scoring(args)} == {'SCORING_RELEASE_ASSESSMENT_MISSING'}


def _held_scoring_pair(tmp_path, pid='321405', *, monkeypatch):
    """Source-owned facts matching the three measured retained-science cases."""
    from clinical_applicability import reviewed_entries, assess_clinical_source_review
    from pipeline_freshness import stage_input_fingerprints, stage_data_fingerprint, DATA_FINGERPRINT_KEY
    from stage_manifest import write_stage_manifest
    row = {'name': 'Bromelain', 'raw_source_text': 'Bromelain', 'canonical_id': 'bromelain',
           'mapped': True, 'raw_source_path': 'ingredientRows[0]', 'quantity': 500, 'unit': 'mg'}
    rid = 'INGR_BROMELAIN'
    if pid == '336337':
        row.update(name='Green Tea Phytosome', raw_source_text='Green Tea Phytosome', canonical_id='green_tea')
        rid = 'INGR_GREEN_TEA'
    source = {'id': pid, 'product_name': row['name'], 'activeIngredients': [row],
              'serving_basis': {'min_servings_per_day': 1, 'max_servings_per_day': 1, 'servings_per_day_source': 'label'},
              'ingredient_quality_data': {'ingredients_scorable': [row], 'ingredients': [row]},
              'evidence_data': {'clinical_matches': [{'id': rid, 'ingredient': row['name'],
                  'matched_canonical_ids': [row['canonical_id']], 'matched_source_row_refs': [row['raw_source_path']]}]}}
    from scoring_v4.modules.generic_evidence import score_evidence
    evidence = score_evidence(source, apply_primary_floor=True, owner_scoped=True)
    product = _scored(dsld_id=pid, quality_assessment_status='partial',
                      _v4_safety_gate={'ingredient_assessment_complete': True, 'ingredient_assessment_errors': [],
                                      'short_circuits_scoring': False, 'quarantine_required': False},
                      _v4_module_breakdown={'module': 'generic', 'dimensions': {'evidence': evidence}},
                      quality_pillars_v4={'evidence': {'score': 0.0, 'evidence_result_state': 'clinical_review_not_covered',
                          'receipt': {'entries': []}}})
    rows = [{'canonical_id': row['canonical_id'], 'name': row['name'], 'state': 'not_yet_evaluated',
             'source_row_ref': row['raw_source_path'], 'material': True, 'evidence_ids': []}]
    if pid == '306381':
        row.update(name='Beta-Alanine', raw_source_text='Beta-Alanine', canonical_id='beta_alanine', quantity=3000)
        source['product_name'] = 'Beta-Alanine Pre-Workout'
        source['evidence_data']['clinical_matches'] = [{**reviewed_entries()['INGR_BETA_ALANINE'], 'ingredient': row['name'],
            'effect_direction': 'positive_strong',  # measured enriched stamp; approval stays canonical
            'matched_canonical_ids': ['beta_alanine'], 'matched_source_row_refs': ['ingredientRows[0]']}]
        from scoring_v4.modules.generic_evidence import score_evidence
        evidence.update(score_evidence(source, apply_primary_floor=True, owner_scoped=True))
        rows = [{'canonical_id': 'beta_alanine', 'name': 'Beta-Alanine', 'state': 'evaluated_supported',
                 'source_row_ref': 'ingredientRows[0]', 'material': True, 'evidence_ids': ['INGR_BETA_ALANINE']},
                {'canonical_id': 'taurine', 'name': 'Taurine', 'state': 'not_yet_evaluated',
                 'source_row_ref': 'ingredientRows[1]', 'material': True, 'evidence_ids': []}]
    product['assessment_readiness']['evidence'].update(readiness='incomplete', ingredient_assessments=rows)
    product['assessment_readiness']['release_assessment'] = {
        'is_complete': False, 'blockers': ['evidence_assessment_incomplete'], 'unfinished_source_assessment': None}
    if pid in {'19067', '307621', '180290'}:
        from test_probiotic_applicability_rubric import _p299v
        from scoring_v4.modules.probiotic_evidence import score_evidence
        source = {**_p299v('Digestive Health Probiotic' if pid == '19067' else 'IBS Probiotic'), 'id': pid}
        evidence.clear(); evidence.update(score_evidence(source))
        product['_v4_module_breakdown']['module'] = 'probiotic'
    if pid in {'239729', '272720', '177500', '233218', '287810', '182627'}:
        from copy import deepcopy
        prenatal = pid in {'233218', '287810'}
        keys = (['folate', 'iron', 'iodine', 'vitamin_d', 'vitamin_b12'] if prenatal else
                ['folate', 'vitamin_b12', 'zinc'])
        if pid in {'239729', '272720'}:
            keys = ['vitamin_b7_biotin' if pid == '239729' else 'vitamin_c', 'keratin']
        source_rows = []
        for index, key in enumerate(keys):
            item = deepcopy(row)
            item.update(name=key.replace('_', ' '), raw_source_text=key.replace('_', ' '), canonical_id=key,
                        raw_source_path=f'ingredientRows[{index}]')
            source_rows.append(item)
        source.update(product_name=('Prenatal' if prenatal else source_rows[0]['name']),
            activeIngredients=source_rows, ingredient_quality_data={'ingredients_scorable': source_rows, 'ingredients': source_rows},
            evidence_data={'clinical_matches': []})
        if pid in {'239729', '272720'}:
            from scoring_v4.modules.generic_evidence import score_evidence
            payload = score_evidence(source, apply_primary_floor=True, owner_scoped=True)
        else:
            from scoring_v4.modules.multi_prenatal_evidence import score_evidence
            payload = score_evidence(source)
            product['_v4_module_breakdown']['module'] = 'multi_or_prenatal'
        evidence.clear(); evidence.update(payload)
    if pid == 'omega_generic':
        from test_v4_omega_evidence_p163 import _epa_dha_product
        from scoring_v4.modules.generic_evidence import score_evidence
        source = {**_epa_dha_product(name='Fish Oil Blend'), 'id': pid}
        source['ingredient_quality_data']['ingredients_scorable'].append({
            'name': 'Unreviewed companion', 'canonical_id': 'unreviewed_test_active',
            'quantity': 10, 'unit': 'mg', 'mapped': True})
        evidence.clear()
        evidence.update(score_evidence(source, apply_primary_floor=True, owner_scoped=True))
        product['assessment_readiness']['evidence']['ingredient_assessments'] = [
            {'canonical_id': row['canonical_id'], 'state': 'not_yet_evaluated',
             'source_row_ref': f'ingredientRows[{i}]', 'material': True, 'evidence_ids': []}
            for i, row in enumerate(source['ingredient_quality_data']['ingredients_scorable'])]
    if pid in {'omega_zero', 'b_panel', 'multi_fractional', 'multi_zero', 'weighted', 'authority_zero'}:
        from copy import deepcopy
        if pid == 'omega_zero':
            row.update(name='Fish Oil', canonical_id='fish_oil', quantity=1000)
            source.update(product_name='Fish Oil', evidence_data={'clinical_matches': []})
            from scoring_v4.modules.omega_evidence import score_evidence
            payload = score_evidence(source)
            product['_v4_module_breakdown']['module'] = 'omega'
        elif pid == 'b_panel':
            from test_v4_b_complex_module import _ideal_b_complex
            from scoring_v4.modules.b_complex import _score_evidence
            source = {**_ideal_b_complex(), 'id': pid}
            payload = _score_evidence(source)
            product['_v4_module_breakdown']['module'] = 'b_complex'
        elif pid.startswith('multi_'):
            from scoring_v4.modules.multi_prenatal_dose import CORE_MULTI_ANCHORS
            from scoring_v4.modules.multi_prenatal_evidence import score_evidence
            keys = CORE_MULTI_ANCHORS[:-1] if pid == 'multi_fractional' else ['unreviewed_test_active']
            rows = [{**deepcopy(row), 'canonical_id': key, 'name': key.replace('_', ' '),
                     'raw_source_path': f'ingredientRows[{i}]'} for i, key in enumerate(keys)]
            source.update(product_name='Daily Multivitamin', activeIngredients=rows,
                          ingredient_quality_data={'ingredients_scorable': rows, 'ingredients': rows},
                          evidence_data={'clinical_matches': []})
            payload = score_evidence(source)
            product['_v4_module_breakdown']['module'] = 'multi_or_prenatal'
        else:
            from scoring_v4.modules.generic_evidence import score_evidence
            if pid == 'weighted':
                # Isolate the existing weighted path; floor qualification has
                # separate signed-source and applicability regressions below.
                monkeypatch.setattr('scoring_v4.modules.generic_evidence.PRIMARY_FLOOR_ENABLED', False)
            key = 'ginger' if pid == 'weighted' else 'silicon'
            row.update(name='Ginger' if pid == 'weighted' else 'Silica', canonical_id=key)
            source.update(product_name=row['name'], evidence_data={'clinical_matches': []})
            if pid == 'weighted':
                rows, matches = [], []
                for i, (canonical, rid) in enumerate([('ginger', 'INGR_GINGER'),
                                                     ('cranberry', 'INGR_CRANBERRY'),
                                                     ('vitamin_c', 'INGR_VITAMIN_C')]):
                    item = {**deepcopy(row), 'canonical_id': canonical, 'name': canonical,
                            'raw_source_text': canonical, 'raw_source_path': f'ingredientRows[{i}]'}
                    rows.append(item)
                    matches.append({**deepcopy(reviewed_entries()[rid]), 'matched_canonical_ids': [canonical],
                                    'matched_source_row_refs': [item['raw_source_path']]})
                source.update(product_name='Daily Blend', activeIngredients=rows,
                              ingredient_quality_data={'ingredients_scorable': rows, 'ingredients': rows},
                              evidence_data={'clinical_matches': matches})
            payload = score_evidence(source, apply_primary_floor=True, owner_scoped=True)
        evidence.clear(); evidence.update(payload)
    from assessment_readiness import evaluate_release_assessment
    product['assessment_readiness']['release_assessment'] = evaluate_release_assessment(
        source, product['assessment_readiness'], product['_v4_module_breakdown'], unfinished_source=None)
    assert product['assessment_readiness']['release_assessment']['is_complete'] is False
    root = tmp_path / 'products'
    from scoring_v4.quality_score import _pillar_evidence, _normalized_receipt
    from scoring_v4.quality_score_config import config
    cfg = config()
    archetype = product['_v4_module_breakdown']['module'] if product['_v4_module_breakdown']['module'] in {
        'probiotic', 'multi_or_prenatal', 'omega', 'b_complex'} else 'generic_single_molecule'
    pillar = _pillar_evidence(evidence, 20, archetype, cfg)
    pillar['receipt'] = _normalized_receipt('evidence', pillar, evidence, 20,
        lambda dim: _pillar_evidence(dim, 20, archetype, cfg))
    product['quality_pillars_v4']['evidence'] = pillar
    enriched = root / 'output_Test_enriched/enriched/enriched_batch_1.json'
    scored = root / 'output_Test_scored/scored/scored_batch_1.json'
    clean = root / 'output_Test/cleaned/cleaned_batch_1.json'
    raw = tmp_path / 'raw/Test/1.json'
    monkeypatch.setenv('PHARMAGUIDE_DATASET_ROOT', str(tmp_path / 'raw'))
    clean.parent.mkdir(parents=True); raw.parent.mkdir(parents=True)
    enriched.parent.mkdir(parents=True); scored.parent.mkdir(parents=True)
    _write(enriched, source); _write(scored, product); _write(clean, source); _write(raw, source)
    write_stage_manifest(clean.parent, 'clean', [clean], input_fingerprints={**stage_input_fingerprints(REPO_ROOT, 'clean'),
        DATA_FINGERPRINT_KEY: stage_data_fingerprint([raw])})
    write_stage_manifest(enriched.parent, 'enrich', [enriched], input_fingerprints={**stage_input_fingerprints(REPO_ROOT, 'enrich'),
        DATA_FINGERPRINT_KEY: stage_data_fingerprint([clean])})
    inputs = {**stage_input_fingerprints(REPO_ROOT, 'score'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])}
    write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints=inputs)
    return source, product, enriched, scored


@pytest.mark.parametrize('pid', ['omega_zero', 'b_panel', 'multi_fractional', 'multi_zero', 'weighted', 'authority_zero'])
def test_retained_evidence_uses_the_current_selected_numerical_owner(tmp_path, pid, monkeypatch):
    from copy import deepcopy
    from assessment_readiness import _retained_evidence_is_publishable
    source, product, _, scored = _held_scoring_pair(tmp_path, pid, monkeypatch=monkeypatch)
    if pid == 'weighted':
        evidence = product['_v4_module_breakdown']['dimensions']['evidence']
        assert evidence['score'] > 0
        assert evidence['metadata']['primary_evidence_floor_decisive'] is False
    original = deepcopy(source)
    assert _retained_evidence_is_publishable(product, source)
    assert source == original
    assert audit_scoring(_args(scored)) == []
    assert product['quality_assessment_status'] == 'partial'
    assert product['assessment_readiness']['release_assessment']['is_complete'] is False


@pytest.mark.parametrize('pid', ['omega_zero', 'b_panel', 'multi_fractional', 'multi_zero', 'weighted', 'authority_zero'])
@pytest.mark.parametrize('change', ['inflated_score', 'stale_lineage', 'changed_component'])
def test_retained_evidence_owner_proof_rejects_changed_credit_or_lineage(tmp_path, pid, change, monkeypatch):
    source, product, enriched, scored = _held_scoring_pair(tmp_path, pid, monkeypatch=monkeypatch)
    evidence = product['_v4_module_breakdown']['dimensions']['evidence']
    if change == 'stale_lineage':
        enriched.write_text(enriched.read_text() + '\n')
    elif change == 'inflated_score':
        evidence['score'] += 1
        evidence['max'] = max(evidence['max'], evidence['score'])
        key = next(iter(evidence['components']), 'clinical_evidence')
        evidence['components'][key] = evidence['components'].get(key, 0) + 1
    else:
        evidence['components'] = {'clinical_evidence': evidence['score']}
    if change != 'stale_lineage':
        # Keep the public arithmetic internally consistent: the canonical
        # source proof, rather than a stale display receipt, must reject it.
        from scoring_v4.quality_score import _normalized_receipt, _pillar_evidence
        from scoring_v4.quality_score_config import config
        cfg = config()
        archetype = product['quality_pillars_v4']['evidence']['components']['archetype']
        pillar = _pillar_evidence(evidence, 20, archetype, cfg)
        pillar['receipt'] = _normalized_receipt('evidence', pillar, evidence, 20,
            lambda dim: _pillar_evidence(dim, 20, archetype, cfg))
        product['quality_pillars_v4']['evidence'] = pillar
        _write(scored, product)
        from assessment_readiness import _retained_evidence_is_publishable
        assert not _retained_evidence_is_publishable(product, source)
        from pipeline_freshness import DATA_FINGERPRINT_KEY, stage_data_fingerprint, stage_input_fingerprints
        from stage_manifest import write_stage_manifest
        write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints={
            **stage_input_fingerprints(REPO_ROOT, 'score'),
            DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])})
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(_args(scored))}


def test_weighted_retained_evidence_cannot_keep_credit_when_a_winning_source_is_held(tmp_path, monkeypatch):
    from copy import deepcopy
    import clinical_applicability as owner
    from assessment_readiness import _retained_evidence_is_publishable
    source, product, _, scored = _held_scoring_pair(tmp_path, 'weighted', monkeypatch=monkeypatch)
    assert _retained_evidence_is_publishable(product, source)
    records = deepcopy(owner.reviewed_entries())
    for context in records['INGR_CRANBERRY']['study_contexts']:
        context['scoring_eligible'] = False
    monkeypatch.setattr(owner, 'reviewed_entries', lambda: records)
    assert not _retained_evidence_is_publishable(product, source)
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(_args(scored))}


def test_current_evidence_receipt_uses_the_production_scoring_identity_view():
    from copy import deepcopy
    from assessment_readiness import _current_evidence_dimension_receipt
    from scoring_input_contract import NON_SCORING_IDENTITY_RATIONALE, score_eligible_identity_view
    from scoring_v4.modules.b_complex import _score_evidence
    from test_v4_b_complex_module import _ideal_b_complex
    source = _ideal_b_complex()
    source['ingredient_quality_data']['ingredients_scorable'][0]['identity_resolution_rationale'] = NON_SCORING_IDENTITY_RATIONALE
    original = deepcopy(source)
    expected = _score_evidence(score_eligible_identity_view(source))
    assert expected['score'] < 20
    assert _current_evidence_dimension_receipt(source, 'b_complex', expected)
    assert source == original


@pytest.mark.parametrize('pid', ['321405', '336337', '306381', '19067', '307621', '180290',
                               '239729', '272720', '177500', '233218', '287810', '182627', 'omega_generic'])
def test_current_lineage_allows_only_truthful_held_evidence_without_clearing_completion(tmp_path, pid, monkeypatch):
    _, product, _, scored = _held_scoring_pair(tmp_path, pid, monkeypatch=monkeypatch)
    args = _args(scored)
    for completion_only in (False, True):
        args.completion_only = completion_only
        assert audit_scoring(args) == []
    assert product['quality_assessment_status'] == 'partial'
    assert product['assessment_readiness']['release_assessment']['is_complete'] is False


@pytest.mark.parametrize('change', ['missing_metadata', 'positive_credit', 'identity', 'dose', 'safety',
                                   'missing_lineage', 'stale_hash', 'stale_fingerprint', 'ambiguous_source',
                                   'stale_clean_binding', 'stale_raw_binding', 'bool_coverage',
                                   'missing_safety_flag', 'quarantined', 'false_known_state'])
def test_held_evidence_exception_requires_current_noncredit_proof(tmp_path, change, monkeypatch):
    from pipeline_freshness import stage_input_fingerprints, stage_data_fingerprint, DATA_FINGERPRINT_KEY
    from stage_manifest import write_stage_manifest, MANIFEST_NAME
    source, product, enriched, scored = _held_scoring_pair(tmp_path, monkeypatch=monkeypatch)
    if change == 'missing_metadata':
        product.pop('_v4_module_breakdown')
    elif change == 'positive_credit':
        product['_v4_module_breakdown']['dimensions']['evidence']['score'] = 5
        product['quality_pillars_v4']['evidence']['score'] = 5
    elif change in {'identity', 'dose'}:
        product['assessment_readiness'][change]['readiness'] = 'incomplete'
    elif change == 'safety':
        product['_v4_safety_gate'].update(ingredient_assessment_complete=False,
                                        ingredient_assessment_errors=['banned_recalled: lookup failed'])
    elif change == 'bool_coverage':
        product['mapped_coverage'] = True
    elif change == 'missing_safety_flag':
        product['_v4_safety_gate'].pop('short_circuits_scoring')
    elif change == 'quarantined':
        product['_v4_safety_gate']['quarantine_required'] = True
    elif change == 'false_known_state':
        product['_v4_module_breakdown']['dimensions']['evidence']['metadata']['evidence_result_state'] = 'evaluated_applicable'
        product['quality_pillars_v4']['evidence']['evidence_result_state'] = 'evaluated_applicable'
    _write(scored, product)
    inputs = {**stage_input_fingerprints(REPO_ROOT, 'score'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])}
    write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints=inputs)
    if change == 'missing_lineage':
        (enriched.parent / MANIFEST_NAME).unlink()
    elif change == 'stale_hash':
        enriched.write_text(enriched.read_text() + '\n')
    elif change == 'stale_fingerprint':
        manifest = json.loads((enriched.parent / MANIFEST_NAME).read_text())
        manifest['input_fingerprints']['stage_code_sha256_v1'] = '0' * 64
        (enriched.parent / MANIFEST_NAME).write_text(json.dumps(manifest))
    elif change == 'ambiguous_source':
        enriched.write_text(json.dumps([source, source]))
        clean = tmp_path / 'products/output_Test/cleaned/cleaned_batch_1.json'
        write_stage_manifest(enriched.parent, 'enrich', [enriched], input_fingerprints={**stage_input_fingerprints(REPO_ROOT, 'enrich'),
            DATA_FINGERPRINT_KEY: stage_data_fingerprint([clean])})
        inputs[DATA_FINGERPRINT_KEY] = stage_data_fingerprint([enriched])
        write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints=inputs)
    elif change == 'stale_clean_binding':
        path = tmp_path / 'products/output_Test/cleaned' / MANIFEST_NAME
        manifest = json.loads(path.read_text())
        manifest['input_fingerprints'][DATA_FINGERPRINT_KEY] = '0' * 64
        path.write_text(json.dumps(manifest))
    elif change == 'stale_raw_binding':
        path = tmp_path / 'raw/Test/1.json'
        path.write_text(path.read_text() + '\n')
    args = _args(scored)
    args.completion_only = True
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}


def test_current_lineage_does_not_authorize_credit_after_its_canonical_source_is_held(tmp_path, monkeypatch):
    from copy import deepcopy
    import clinical_applicability as owner
    _, _, _, scored = _held_scoring_pair(tmp_path, '306381', monkeypatch=monkeypatch)
    records = deepcopy(owner.reviewed_entries())
    for context in records['INGR_BETA_ALANINE']['study_contexts']:
        context['scoring_eligible'] = False
    monkeypatch.setattr(owner, 'reviewed_entries', lambda: records)
    args = _args(scored)
    args.completion_only = True
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}


def test_held_evidence_proof_rejects_floor_value_tamper_with_the_same_reviewed_source(tmp_path, monkeypatch):
    from pipeline_freshness import stage_input_fingerprints, stage_data_fingerprint, DATA_FINGERPRINT_KEY
    from stage_manifest import write_stage_manifest
    _, product, enriched, scored = _held_scoring_pair(tmp_path, '306381', monkeypatch=monkeypatch)
    evidence = product['_v4_module_breakdown']['dimensions']['evidence']
    evidence['score'] = evidence['components']['primary_evidence_floor'] = evidence['metadata']['primary_evidence_floor'] = 18.0
    _write(scored, product)
    write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints={
        **stage_input_fingerprints(REPO_ROOT, 'score'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])})
    args = _args(scored)
    args.completion_only = True
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}


def test_release_source_join_keeps_one_dataset_index_and_can_revisit(tmp_path, monkeypatch):
    import audit_source_of_truth_contract as audit
    first = tmp_path / 'first'; second = tmp_path / 'second'
    _, _, _, left = _held_scoring_pair(first, '321405', monkeypatch=monkeypatch)
    _, _, _, right = _held_scoring_pair(second, '336337', monkeypatch=monkeypatch)
    cache = {}
    for directory, path, pid in [(first, left, '321405'), (second, right, '336337'), (first, left, '321405')]:
        monkeypatch.setenv('PHARMAGUIDE_DATASET_ROOT', str(directory / 'raw'))
        assert audit._scoring_enriched_source(path, pid, cache)['id'] == pid
        assert len([key for key in cache if isinstance(key, Path)]) == 1


@pytest.mark.parametrize('change', ['unresolved_primary', 'missing_approval', 'wrong_strain', 'inactivated'])
def test_native_partial_requires_approved_applicable_positive_primary(tmp_path, monkeypatch, change):
    from copy import deepcopy
    import studied_formulas
    from pipeline_freshness import stage_input_fingerprints, stage_data_fingerprint, DATA_FINGERPRINT_KEY
    from stage_manifest import write_stage_manifest
    source, _, enriched, scored = _held_scoring_pair(tmp_path, '307621', monkeypatch=monkeypatch)
    if change in {'unresolved_primary', 'missing_approval'}:
        registry = deepcopy(studied_formulas._clinical_strain_registry())
        for context in registry['STRAIN_PLANTARUM_299V']['study_contexts']:
            if change == 'missing_approval':
                context.pop('clinical_review', None)
            else:
                for outcome in context.get('outcomes') or []:
                    if outcome.get('hierarchy') == 'primary':
                        outcome['direction'] = 'unresolved'
        monkeypatch.setattr(studied_formulas, '_clinical_strain_registry', lambda: registry)
    else:
        if change == 'wrong_strain':
            source['probiotic_data']['clinical_strains'][0]['clinical_id'] = 'STRAIN_LGG'
        else:
            source['activeIngredients'][0]['name'] = 'Heat-killed Lactobacillus plantarum 299v'
            source['probiotic_data']['clinical_strains'][0]['strain'] = 'Heat-killed Lactobacillus plantarum 299v'
        _write(enriched, source)
        clean = tmp_path / 'products/output_Test/cleaned/cleaned_batch_1.json'
        write_stage_manifest(enriched.parent, 'enrich', [enriched], input_fingerprints={
            **stage_input_fingerprints(REPO_ROOT, 'enrich'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([clean])})
        write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints={
            **stage_input_fingerprints(REPO_ROOT, 'score'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])})
    args = _args(scored)
    args.completion_only = True
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}


@pytest.mark.parametrize('change', ['under_clinical_scope', 'missing_directions'])
def test_held_evidence_floor_never_bypasses_its_existing_signed_exposure_scope(tmp_path, monkeypatch, change):
    from pipeline_freshness import stage_input_fingerprints, stage_data_fingerprint, DATA_FINGERPRINT_KEY
    from stage_manifest import write_stage_manifest
    source, _, enriched, scored = _held_scoring_pair(tmp_path, '306381', monkeypatch=monkeypatch)
    if change == 'under_clinical_scope':
        source['ingredient_quality_data']['ingredients_scorable'][0]['quantity'] = 1
    else:
        source.pop('serving_basis')
    _write(enriched, source)
    clean = tmp_path / 'products/output_Test/cleaned/cleaned_batch_1.json'
    write_stage_manifest(enriched.parent, 'enrich', [enriched], input_fingerprints={
        **stage_input_fingerprints(REPO_ROOT, 'enrich'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([clean])})
    write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints={
        **stage_input_fingerprints(REPO_ROOT, 'score'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])})
    args = _args(scored)
    args.completion_only = True
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}


@pytest.mark.parametrize('pid', ['306381', '307621'])
def test_coherent_higher_score_cannot_borrow_a_valid_source_receipt(tmp_path, monkeypatch, pid):
    from pipeline_freshness import stage_input_fingerprints, stage_data_fingerprint, DATA_FINGERPRINT_KEY
    from stage_manifest import write_stage_manifest
    from scoring_v4.quality_score import _pillar_evidence, _normalized_receipt
    from scoring_v4.quality_score_config import config
    _, product, enriched, scored = _held_scoring_pair(tmp_path, pid, monkeypatch=monkeypatch)
    evidence = product['_v4_module_breakdown']['dimensions']['evidence']
    if pid == '306381':
        evidence['score'] = evidence['components']['primary_evidence_floor'] = evidence['metadata']['primary_evidence_floor'] = 18.0
    else:
        evidence['components']['independent_replication_consistency'] = 4.0
        evidence['score'] = 20.0
    cfg = config(); archetype = product['quality_pillars_v4']['evidence']['components']['archetype']
    pillar = _pillar_evidence(evidence, 20, archetype, cfg)
    pillar['receipt'] = _normalized_receipt('evidence', pillar, evidence, 20,
        lambda dim: _pillar_evidence(dim, 20, archetype, cfg))
    product['quality_pillars_v4']['evidence'] = pillar
    _write(scored, product)
    write_stage_manifest(scored.parent, 'score', [scored], input_fingerprints={
        **stage_input_fingerprints(REPO_ROOT, 'score'), DATA_FINGERPRINT_KEY: stage_data_fingerprint([enriched])})
    args = _args(scored); args.completion_only = True
    assert 'SCORING_RELEASE_ASSESSMENT_INCOMPLETE' in {f.code for f in audit_scoring(args)}
