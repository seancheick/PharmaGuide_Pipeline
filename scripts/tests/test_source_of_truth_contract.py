import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / "scripts" / "audit_source_of_truth_contract.py"
MATRIX_PATH = REPO_ROOT / "scripts" / "contracts" / "source_of_truth_matrix.json"


spec = importlib.util.spec_from_file_location("audit_source_of_truth_contract", AUDIT_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_source_of_truth_matrix_is_complete():
    args = argparse.Namespace(matrix=str(MATRIX_PATH), strict_release=True)
    findings = audit.audit_matrix(args)
    assert findings == []


def test_source_of_truth_matrix_declares_enrichment_contract_concepts():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    required = {
        "ingredient_identity_resolution",
        "ingredient_quality_data_contract",
        "taxonomy_input_contract",
        "enriched_active_safety_contract",
        "enriched_inactive_safety_contract",
        "interaction_profile_contract",
        "enrichment_fallback_policy",
        "display_ingredient_contract",
    }
    assert required.issubset(set(matrix["required_concepts"]))
    assert required.issubset({concept["concept_id"] for concept in matrix["concepts"]})


def test_source_of_truth_matrix_rejects_dev_only_fallback_in_strict_release(tmp_path):
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    matrix["concepts"][0]["fallback_class"] = "dev_only_missing_vocab"
    path = tmp_path / "matrix.json"
    write_json(path, matrix)

    args = argparse.Namespace(matrix=str(path), strict_release=True)
    findings = audit.audit_matrix(args)

    assert "MATRIX_DEV_FALLBACK_RELEASE" in {finding.code for finding in findings}


def test_cleaner_iqd_contract_blocks_ineligible_inactive_and_display_roles(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "canary",
                "ingredient_quality_data": {
                    "ingredients": [
                        {
                            "name": "Proprietary Blend",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "blend_header_total",
                            "score_eligible_by_cleaner": False,
                            "dose_class": "blend_total_weight",
                        }
                    ],
                    "ingredients_scorable": [
                        {
                            "name": "Proprietary Blend",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "blend_header_total",
                            "score_eligible_by_cleaner": False,
                            "dose_class": "blend_total_weight",
                        },
                        {
                            "name": "Leucine",
                            "source_section": "inactive",
                            "raw_source_path": "otheringredients[2]",
                            "cleaner_row_role": "inactive",
                            "score_eligible_by_cleaner": False,
                            "dose_class": "none",
                        },
                    ],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_cleaner(args)}

    assert "IQD_SCORABLE_NOT_CLEANER_ELIGIBLE" in codes
    assert "IQD_BLOCKED_ROLE_SCORABLE" in codes
    assert "IQD_INACTIVE_PROMOTED" in codes


def test_cleaner_contract_rejects_source_rows_missing_cleaner_fields(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "missing-cleaner-source-contract",
                "activeIngredients": [{"name": "Vitamin C", "raw_source_path": "ingredientRows[0]"}],
                "ingredient_quality_data": {
                    "ingredients": [],
                    "ingredients_scorable": [],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_cleaner(args)}

    assert "CLEANER_SOURCE_ROW_FIELD_MISSING" in codes


def test_enrichment_contract_blocks_recognized_rows_in_scorable_and_iqd_fallback(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "enrichment-contract-canary",
                "supplement_taxonomy": {
                    "primary_type": "omega_3",
                    "classification_input_source": "ingredient_quality_data.ingredients_fallback",
                },
                "iqd_contract_diagnostics": {"iqd_ingredients_fallback_used": True},
                "ingredient_quality_data": {
                    "ingredients": [
                        {
                            "name": "Sunflower Oil",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "active_scorable",
                            "score_eligible_by_cleaner": True,
                            "score_exclusion_reason": None,
                            "dose_class": "therapeutic_mass",
                            "raw_taxonomy": {},
                            "canonical_id": "sunflower_oil",
                            "canonical_source_db": "other_ingredients",
                            "normalized_key": "sunflower_oil",
                            "match_tier": None,
                            "matched_alias": None,
                            "matched_target": None,
                            "identity_confidence": 1.0,
                            "identity_decision_reason": "recognized_non_scorable",
                            "mapped": True,
                            "mapped_identity": True,
                            "scoreable_identity": False,
                            "role_classification": "recognized_non_scorable",
                            "recognition_source": "other_ingredients",
                            "recognition_type": "carrier",
                            "recognition_reason": "recognized_non_scorable",
                            "form_id": None,
                            "form_source": None,
                            "form_unmapped": False,
                            "delivers_markers": [],
                        }
                    ],
                    "ingredients_scorable": [
                        {
                            "name": "Sunflower Oil",
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                            "cleaner_row_role": "active_scorable",
                            "score_eligible_by_cleaner": True,
                            "score_exclusion_reason": None,
                            "dose_class": "therapeutic_mass",
                            "raw_taxonomy": {},
                            "canonical_id": "sunflower_oil",
                            "canonical_source_db": "other_ingredients",
                            "normalized_key": "sunflower_oil",
                            "match_tier": None,
                            "matched_alias": None,
                            "matched_target": None,
                            "identity_confidence": 1.0,
                            "identity_decision_reason": "recognized_non_scorable",
                            "mapped": True,
                            "mapped_identity": True,
                            "scoreable_identity": False,
                            "role_classification": "recognized_non_scorable",
                            "recognition_source": "other_ingredients",
                            "recognition_type": "carrier",
                            "recognition_reason": "recognized_non_scorable",
                            "form_id": None,
                            "form_source": None,
                            "form_unmapped": False,
                            "delivers_markers": [],
                        }
                    ],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_enrichment(args)}

    assert "ENRICHMENT_RECOGNIZED_IN_SCORABLE" in codes
    assert "ENRICHMENT_SCORABLE_NOT_SCOREABLE_IDENTITY" in codes
    assert "ENRICHMENT_SCORABLE_ROLE_NOT_ACTIVE" in codes
    assert "ENRICHMENT_FALLBACK_DIAGNOSTICS_MISSING" in codes
    assert "ENRICHMENT_TAXONOMY_USED_IQD_FALLBACK" in codes
    assert "ENRICHMENT_SCORING_USED_IQD_FALLBACK" in codes


def test_enrichment_contract_rejects_old_batch_cleaner_contract_defaults(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "old-batch-cleaner-default-canary",
                "ingredient_quality_data": {
                    "ingredients": [
                        {
                            "name": "Vitamin C",
                            "source_section": "active",
                            "raw_source_path": "activeIngredients",
                            "cleaner_row_role": "active_scorable",
                            "score_eligible_by_cleaner": True,
                            "score_exclusion_reason": None,
                            "dose_class": "therapeutic_mass",
                            "raw_taxonomy": {},
                            "canonical_id": "vitamin_c",
                            "canonical_source_db": "ingredient_quality_map",
                            "normalized_key": "vitamin_c",
                            "match_tier": "exact",
                            "matched_alias": None,
                            "matched_target": "Vitamin C",
                            "identity_confidence": 1.0,
                            "identity_decision_reason": "quality_map_match",
                            "mapped": True,
                            "mapped_identity": True,
                            "scoreable_identity": True,
                            "role_classification": "active_scorable",
                            "recognition_source": None,
                            "recognition_type": None,
                            "recognition_reason": None,
                            "form_id": None,
                            "form_source": None,
                            "form_unmapped": False,
                            "delivers_markers": [],
                            "cleaner_contract_fallback_used": True,
                            "cleaner_contract_missing_fields": ["source_section"],
                            "fallback_class": "old_batch_compatibility",
                            "fallback_reason": "missing_cleaner_contract_fields",
                        }
                    ],
                    "ingredients_scorable": [],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_enrichment(args)}

    assert "ENRICHMENT_CLEANER_CONTRACT_FALLBACK_USED" in codes


def test_enrichment_contract_rejects_zero_np_therapeutic_mass_as_scorable(tmp_path):
    product_file = tmp_path / "product.json"
    base_row = {
        "name": "Saffron Extract",
        "source_section": "active",
        "raw_source_path": "ingredientRows[0]",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "score_exclusion_reason": None,
        "dose_class": "therapeutic_mass",
        "raw_taxonomy": {},
        "canonical_id": "saffron",
        "canonical_source_db": "ingredient_quality_map",
        "normalized_key": "saffron_extract",
        "match_tier": "exact",
        "matched_alias": "saffron",
        "matched_target": "Saffron",
        "identity_confidence": 1.0,
        "identity_decision_reason": "quality_map_match",
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "role_classification": "active_scorable",
        "recognition_source": None,
        "recognition_type": None,
        "recognition_reason": None,
        "form_id": None,
        "form_source": None,
        "form_unmapped": False,
        "delivers_markers": [],
        "quantity": "0.0",
        "unit": "NP",
    }
    write_json(
        product_file,
        [
            {
                "id": "zero-np-dose-canary",
                "ingredient_quality_data": {
                    "ingredients": [base_row],
                    "ingredients_scorable": [base_row],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    cleaner_codes = {finding.code for finding in audit.audit_cleaner(args)}
    enrichment_codes = {finding.code for finding in audit.audit_enrichment(args)}

    assert "IQD_SCORABLE_MISSING_DOSE_EVIDENCE" in cleaner_codes
    assert "ENRICHMENT_SCORABLE_MISSING_DOSE" in enrichment_codes


def test_enrichment_contract_validates_product_scoring_evidence(tmp_path):
    product_file = tmp_path / "product.json"
    write_json(
        product_file,
        [
            {
                "id": "cfu-false-positive",
                "supplement_taxonomy": {"primary_type": "mineral"},
                "probiotic_data": {"total_cfu": 10_000_000_000},
                "product_scoring_evidence": [
                    {
                        "evidence_type": "probiotic_cfu",
                        "scoreable": True,
                        "scoreable_identity": True,
                        "score_eligible_by_cleaner": True,
                        "dose_class": "probiotic_cfu",
                        "dose_value": 10_000_000_000,
                        "dose_unit": "CFU",
                        "source": "statements",
                        "raw_source_path": "statements[0]",
                        "evidence_scope": "product_level",
                        "linked_rows": ["statements[0]"],
                        "confidence": "high",
                        "reason": "product_level_cfu_with_probiotic_identity",
                    }
                ],
                "ingredient_quality_data": {
                    "ingredients_scorable": [],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            },
            {
                "id": "cfu-missing-diagnostic",
                "supplement_taxonomy": {"primary_type": "probiotic"},
                "probiotic_data": {"total_cfu": 20_000_000_000},
                "ingredient_quality_data": {
                    "ingredients_scorable": [],
                    "ingredients_recognized_non_scorable": [],
                    "ingredients_skipped": [],
                },
            },
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_enrichment(args)}

    assert "ENRICHMENT_PRODUCT_CFU_FALSE_POSITIVE" in codes
    assert "ENRICHMENT_PRODUCT_CFU_EVIDENCE_MISSING" in codes


def test_clinical_drift_gates_catch_known_failure_shapes(tmp_path):
    product_file = tmp_path / "products.json"
    write_json(
        product_file,
        [
            {
                "id": "chromium",
                "name": "Multivitamin with Chromium",
                "banned_substances": {"substances": [{"rule_id": "HM_CHROMIUM_HEXAVALENT"}]},
                "ingredient_quality_data": {
                    "ingredients_scorable": [
                        {
                            "name": "Chromium",
                            "canonical_id": "chromium",
                            "score_eligible_by_cleaner": True,
                            "source_section": "active",
                            "raw_source_path": "ingredientRows[0]",
                        }
                    ]
                },
            },
            {
                "id": "omega-zyme",
                "name": "Omega-Zyme Enzyme Blend",
                "supplement_taxonomy": {"primary_type": "omega_3"},
                "ingredient_quality_data": {"ingredients_scorable": [{"name": "Protease", "canonical_id": "protease"}]},
            },
            {
                "id": "pm",
                "name": "Liver Cleanser PM",
                "supplement_taxonomy": {"primary_type": "sleep_support"},
                "ingredient_quality_data": {"ingredients_scorable": [{"name": "Milk Thistle", "canonical_id": "milk_thistle"}]},
            },
            {
                "id": "enzyme",
                "name": "Natto-Serra Serrapeptase 120000 SPU",
                "ingredient_quality_data": {
                    "ingredients": [{"name": "Serrapeptase", "unit": "SPU"}],
                    "ingredients_scorable": [{"name": "Calcium", "canonical_id": "calcium", "quantity": 20, "dose_class": "therapeutic_mass"}],
                },
            },
            {
                "id": "softgel",
                "name": "Softgel Product",
                "form_factor": "Softgel Capsule",
                "form_factor_canonical": "capsule",
                "ingredient_quality_data": {"ingredients_scorable": []},
            },
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_clinical(args)}

    assert "GENERIC_CHROMIUM_CRVI" in codes
    assert "PRODUCT_NAME_ONLY_OMEGA3" in codes
    assert "PM_ONLY_SLEEP_SUPPORT" in codes
    assert "ENZYME_ACTIVITY_NOT_DOSE_EVIDENCE" in codes
    assert "FORM_FACTOR_CANONICAL_NOT_SOFTGEL" in codes


def test_clinical_omega_gate_accepts_taxonomy_scorable_id_evidence(tmp_path):
    product_file = tmp_path / "products.json"
    write_json(
        product_file,
        [
            {
                "id": "scored-omega-without-iqd-rows",
                "name": "High Concentrate EPA",
                "supplement_taxonomy": {
                    "primary_type": "omega_3",
                    "percentile_category": "fish_oil",
                    "classification_input_source": "ingredient_quality_data.ingredients_scorable",
                    "classification_reasons": ["omega-3: ids=['epa'], name_match=False"],
                    "category_breakdown": {"fatty_acid": 1},
                },
                "ingredient_quality_data": {"ingredients_scorable": []},
            }
        ],
    )

    args = argparse.Namespace(
        enriched_file=[],
        enriched_dir=[],
        product_file=[str(product_file)],
        products_dir=None,
        dist_dir=None,
    )
    codes = {finding.code for finding in audit.audit_clinical(args)}

    assert "PRODUCT_NAME_ONLY_OMEGA3" not in codes


def test_shadow_diff_requires_approval_for_taxonomy_verdict_safety_or_coverage_shift(tmp_path):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    write_json(
        old_dir / "products.json",
        [
            {
                "id": "shadow",
                "supplement_taxonomy": {"primary_type": "multivitamin"},
                "verdict": "SAFE",
                "banned_substances": {"substances": []},
                "mapped_coverage": 1.0,
            }
        ],
    )
    write_json(
        new_dir / "products.json",
        [
            {
                "id": "shadow",
                "supplement_taxonomy": {"primary_type": "omega_3"},
                "verdict": "UNSAFE",
                "banned_substances": {"substances": [{"rule_id": "x"}]},
                "mapped_coverage": 0.5,
            }
        ],
    )

    args = argparse.Namespace(
        old_dir=str(old_dir),
        new_dir=str(new_dir),
        max_taxonomy_shifts=0,
        max_verdict_shifts=0,
        max_safety_shifts=0,
        max_mapped_coverage_drop=0.0,
        manual_approval=False,
    )
    codes = {finding.code for finding in audit.audit_shadow_diff(args)}

    assert "SHADOW_TAXONOMY_SHIFT" in codes
    assert "SHADOW_VERDICT_SHIFT" in codes
    assert "SHADOW_SAFETY_SHIFT" in codes
    assert "SHADOW_MAPPED_COVERAGE_DROP" in codes

    args.manual_approval = True
    assert audit.audit_shadow_diff(args) == []


def test_artifact_lineage_rejects_scored_file_older_than_matching_enriched(tmp_path):
    enriched_dir = tmp_path / "enriched"
    scored_dir = tmp_path / "scored"
    enriched = enriched_dir / "enriched_cleaned_batch_1.json"
    scored = scored_dir / "scored_cleaned_batch_1.json"
    write_json(enriched, [{"id": "p1"}])
    write_json(scored, [{"id": "p1"}])
    now = time.time()
    os.utime(scored, (now - 60, now - 60))
    os.utime(enriched, (now, now))

    args = argparse.Namespace(enriched_dir=str(enriched_dir), scored_dir=str(scored_dir))

    codes = {finding.code for finding in audit.audit_artifact_lineage(args)}
    assert "ARTIFACT_LINEAGE_SCORED_STALE" in codes


def test_interaction_and_flutter_parity_gates_accept_matching_artifacts(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "interaction_db.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE interactions (id TEXT, severity TEXT, retired_at TEXT, retired_reason TEXT)")
        conn.execute("INSERT INTO interactions VALUES ('i1', 'caution', NULL, NULL)")
        conn.execute("CREATE TABLE interaction_db_metadata (key TEXT, value TEXT)")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('version', '1.0.0')")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_drafts_count', '1')")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_suppai_count', '0')")
    write_json(
        dist / "interaction_db_manifest.json",
        {
            "checksum_sha256": sha256(db_path),
            "interaction_db_version": "1.0.0",
            "total_interactions": 1,
            "source_drafts_count": 1,
            "source_suppai_count": 0,
        },
    )
    source_rules = tmp_path / "rules.json"
    severity_vocab = tmp_path / "severity_vocab.json"
    write_json(source_rules, {"interaction_rules": [{"id": "r1"}]})
    write_json(severity_vocab, {"severities": [{"id": "caution"}]})

    orphan_allowlist = tmp_path / "orphan_allowlist.json"
    write_json(orphan_allowlist, {"allowlist": []})

    args = argparse.Namespace(
        dist_dir=str(dist),
        source_rules=str(source_rules),
        severity_vocab=str(severity_vocab),
        orphan_allowlist=str(orphan_allowlist),
    )
    assert audit.audit_interaction(args) == []

    catalog_db = dist / "pharmaguide_core.db"
    catalog_db.write_bytes(b"catalog")
    write_json(dist / "export_manifest.json", {"checksum_sha256": sha256(catalog_db)})
    flutter_assets = tmp_path / "flutter" / "assets" / "db"
    flutter_assets.mkdir(parents=True)
    for name in ("interaction_db.sqlite", "interaction_db_manifest.json", "pharmaguide_core.db", "export_manifest.json"):
        shutil.copy2(dist / name, flutter_assets / name)

    flutter_args = argparse.Namespace(dist_dir=str(dist), flutter_repo=str(tmp_path / "flutter"))
    assert audit.audit_flutter(flutter_args) == []


def _build_interaction_db_with_canonical_ids(
    db_path: Path,
    interactions: list[dict],
    source_drafts_count: int = 0,
) -> None:
    """Helper: build a richer interactions DB schema matching production layout
    (with agent1_type/agent1_canonical_id/agent2_type/agent2_canonical_id) for
    the new referential-integrity tests.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE interactions ("
            "id TEXT, severity TEXT, retired_at TEXT, retired_reason TEXT,"
            " agent1_type TEXT, agent1_canonical_id TEXT,"
            " agent2_type TEXT, agent2_canonical_id TEXT"
            ")"
        )
        for row in interactions:
            conn.execute(
                "INSERT INTO interactions (id, severity, retired_at, retired_reason,"
                " agent1_type, agent1_canonical_id, agent2_type, agent2_canonical_id)"
                " VALUES (?, ?, NULL, NULL, ?, ?, ?, ?)",
                (
                    row["id"],
                    row.get("severity", "caution"),
                    row.get("agent1_type", "drug"),
                    row.get("agent1_canonical_id"),
                    row.get("agent2_type", "supplement"),
                    row.get("agent2_canonical_id"),
                ),
            )
        conn.execute("CREATE TABLE interaction_db_metadata (key TEXT, value TEXT)")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('version', '1.0.0')")
        conn.execute(
            "INSERT INTO interaction_db_metadata VALUES ('source_drafts_count', ?)",
            (str(source_drafts_count),),
        )
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_suppai_count', '0')")


def test_interaction_parity_accepts_drafts_exceeding_rule_entries(tmp_path):
    """Regression test for the false-positive count-comparison gate.

    Before the fix: source_drafts_count=148 > source_rule_count=145 fired
    INTERACTION_SOURCE_COUNT_EXCEEDS_RULES even though one ingredient entry
    can legitimately host many pairwise interactions (e.g., St Johns Wort
    has ~10 drug interactions packed into one ingredient_interaction_rules
    entry). Wave 8 commit 821931df pushed pairwise above ingredient count.

    After the fix: pairwise > ingredient is NOT a violation.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "interaction_db.sqlite"

    # 3 pairwise interactions, all referencing 'st_johns_wort' which has 1 rule entry.
    # This is the exact scenario the old gate falsely rejected.
    _build_interaction_db_with_canonical_ids(
        db_path,
        [
            {"id": "i1", "agent2_canonical_id": "st_johns_wort"},
            {"id": "i2", "agent2_canonical_id": "st_johns_wort"},
            {"id": "i3", "agent2_canonical_id": "st_johns_wort"},
        ],
        source_drafts_count=3,
    )
    write_json(
        dist / "interaction_db_manifest.json",
        {
            "checksum_sha256": sha256(db_path),
            "interaction_db_version": "1.0.0",
            "total_interactions": 3,
            "source_drafts_count": 3,
            "source_suppai_count": 0,
        },
    )
    source_rules = tmp_path / "rules.json"
    write_json(
        source_rules,
        {"interaction_rules": [{"id": "r1", "subject_ref": {"db": "iqm", "canonical_id": "st_johns_wort"}}]},
    )
    severity_vocab = tmp_path / "severity_vocab.json"
    write_json(severity_vocab, {"severities": [{"id": "caution"}]})
    orphan_allowlist = tmp_path / "orphan_allowlist.json"
    write_json(orphan_allowlist, {"allowlist": []})

    args = argparse.Namespace(
        dist_dir=str(dist),
        source_rules=str(source_rules),
        severity_vocab=str(severity_vocab),
        orphan_allowlist=str(orphan_allowlist),
    )
    findings = audit.audit_interaction(args)
    codes = {f.code for f in findings}
    assert "INTERACTION_SOURCE_COUNT_EXCEEDS_RULES" not in codes, (
        f"Old count-comparison gate must not fire when source_drafts > source_rule_count. "
        f"Got findings: {[(f.code, f.message) for f in findings]}"
    )
    assert findings == [], f"Unexpected findings: {[(f.code, f.message) for f in findings]}"


def test_interaction_parity_catches_orphan_supplement_canonical_id(tmp_path):
    """Referential-integrity check: a supplement canonical_id used in pairwise
    interactions must exist as a subject_ref.canonical_id in
    ingredient_interaction_rules.json (or be on the allowlist)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "interaction_db.sqlite"

    _build_interaction_db_with_canonical_ids(
        db_path,
        [
            # Valid: vitamin_k is in rules
            {"id": "i1", "agent2_canonical_id": "vitamin_k"},
            # Orphan: ghost_supp does NOT have a rule entry and is NOT allowlisted
            {"id": "i2", "agent2_canonical_id": "ghost_supp"},
        ],
        source_drafts_count=2,
    )
    write_json(
        dist / "interaction_db_manifest.json",
        {
            "checksum_sha256": sha256(db_path),
            "interaction_db_version": "1.0.0",
            "total_interactions": 2,
            "source_drafts_count": 2,
            "source_suppai_count": 0,
        },
    )
    source_rules = tmp_path / "rules.json"
    write_json(
        source_rules,
        {
            "interaction_rules": [
                {"id": "r_vit_k", "subject_ref": {"db": "iqm", "canonical_id": "vitamin_k"}}
            ]
        },
    )
    severity_vocab = tmp_path / "severity_vocab.json"
    write_json(severity_vocab, {"severities": [{"id": "caution"}]})
    orphan_allowlist = tmp_path / "orphan_allowlist.json"
    write_json(orphan_allowlist, {"allowlist": []})

    args = argparse.Namespace(
        dist_dir=str(dist),
        source_rules=str(source_rules),
        severity_vocab=str(severity_vocab),
        orphan_allowlist=str(orphan_allowlist),
    )
    findings = audit.audit_interaction(args)
    codes = {f.code for f in findings}
    assert "INTERACTION_ORPHAN_SUPPLEMENT_CANONICAL" in codes, (
        f"Expected INTERACTION_ORPHAN_SUPPLEMENT_CANONICAL but got: {[(f.code, f.message) for f in findings]}"
    )
    # Verify the orphan id is named in the message
    orphan_findings = [f for f in findings if f.code == "INTERACTION_ORPHAN_SUPPLEMENT_CANONICAL"]
    assert any("ghost_supp" in f.message for f in orphan_findings), (
        f"Orphan canonical_id 'ghost_supp' must be named in finding message; got: {[f.message for f in orphan_findings]}"
    )


def test_live_interaction_db_has_no_orphan_canonicals():
    """Root-cause guard against the recurring INTERACTION_ORPHAN_SUPPLEMENT_CANONICAL
    release failures (the red_yeast_rice / cbd / vinpocetine / kava whack-a-mole).

    Supplement canonical placeholders (``BANNED_*`` / ``RISK_*`` / ``NOOTROPIC_*``)
    are assigned during the interaction-DB BUILD, not in committed curated source,
    so a source-only check can't see them. This runs the REAL parity audit against
    the freshly built interaction DB in ``scripts/dist/`` — so an unmapped
    placeholder fails HERE (pytest, seconds) instead of at the end of a ~25-minute
    ``release_full.sh`` run, which was the patch-per-patch pain.

    To fix a failure: add the placeholder -> clean-identity mapping to
    ``scripts/identity/interaction.py::INTERACTION_CANONICAL_ALIASES`` (preferred —
    use the canonical the catalog ``key_ingredient_tags`` + the rules file already
    use), or add an entry to ``scripts/data/interaction_orphan_allowlist.json`` for
    a genuinely pairwise-only signal. Then rebuild the interaction DB.

    Skips only when no build artifact exists (e.g. a clean CI checkout that has not
    run ``scripts/rebuild_interaction_db.sh``).
    """
    import pytest

    dist = REPO_ROOT / "scripts" / "dist"
    if not (dist / "interaction_db.sqlite").exists():
        pytest.skip(
            "no built scripts/dist/interaction_db.sqlite — "
            "run scripts/rebuild_interaction_db.sh first"
        )
    data = REPO_ROOT / "scripts" / "data"
    args = argparse.Namespace(
        dist_dir=str(dist),
        source_rules=str(data / "ingredient_interaction_rules.json"),
        severity_vocab=str(data / "severity_vocab.json"),
        orphan_allowlist=str(data / "interaction_orphan_allowlist.json"),
    )
    findings = audit.audit_interaction(args)
    assert findings == [], (
        "Live interaction-DB source-of-truth audit FAILED in pytest — this is the "
        "SAME gate that blocks release_full.sh, caught early. Fix at the root: add "
        "a clean-identity alias in scripts/identity/interaction.py "
        "(INTERACTION_CANONICAL_ALIASES) or an allowlist entry, then rebuild.\n"
        + "\n".join(f"  {f.code}: {f.message}" for f in findings)
    )


def test_interaction_parity_respects_orphan_allowlist(tmp_path):
    """Allowlisted orphans must NOT trigger INTERACTION_ORPHAN_SUPPLEMENT_CANONICAL.

    This is how we ship with known-tracked exceptions (e.g., NOOTROPIC_VINPOCETINE
    has a real anticoagulant pairwise interaction but no standalone rule entry yet).
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "interaction_db.sqlite"

    _build_interaction_db_with_canonical_ids(
        db_path,
        [
            {"id": "i1", "agent2_canonical_id": "NOOTROPIC_VINPOCETINE"},
        ],
        source_drafts_count=1,
    )
    write_json(
        dist / "interaction_db_manifest.json",
        {
            "checksum_sha256": sha256(db_path),
            "interaction_db_version": "1.0.0",
            "total_interactions": 1,
            "source_drafts_count": 1,
            "source_suppai_count": 0,
        },
    )
    source_rules = tmp_path / "rules.json"
    write_json(source_rules, {"interaction_rules": [{"id": "r1", "subject_ref": {"db": "iqm", "canonical_id": "something_else"}}]})
    severity_vocab = tmp_path / "severity_vocab.json"
    write_json(severity_vocab, {"severities": [{"id": "caution"}]})
    orphan_allowlist = tmp_path / "orphan_allowlist.json"
    write_json(
        orphan_allowlist,
        {
            "allowlist": [
                {
                    "canonical_id": "NOOTROPIC_VINPOCETINE",
                    "reason": "test fixture: vinpocetine pairwise-only signal",
                    "todo": "add rule entry",
                    "added": "2026-05-27",
                }
            ]
        },
    )

    args = argparse.Namespace(
        dist_dir=str(dist),
        source_rules=str(source_rules),
        severity_vocab=str(severity_vocab),
        orphan_allowlist=str(orphan_allowlist),
    )
    findings = audit.audit_interaction(args)
    codes = {f.code for f in findings}
    assert "INTERACTION_ORPHAN_SUPPLEMENT_CANONICAL" not in codes, (
        f"Allowlisted orphan must not fire finding. Got: {[(f.code, f.message) for f in findings]}"
    )


def test_interaction_parity_skips_referential_check_when_schema_lacks_canonical_id_columns(tmp_path):
    """Backward compatibility: legacy DB schemas without agent1_canonical_id /
    agent2_canonical_id columns must NOT crash the audit. The referential
    check silently skips for these schemas (the column-presence check is
    permissive)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "interaction_db.sqlite"
    # Old/minimal schema — no canonical_id columns
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE interactions (id TEXT, severity TEXT, retired_at TEXT, retired_reason TEXT)")
        conn.execute("INSERT INTO interactions VALUES ('i1', 'caution', NULL, NULL)")
        conn.execute("CREATE TABLE interaction_db_metadata (key TEXT, value TEXT)")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('version', '1.0.0')")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_drafts_count', '1')")
        conn.execute("INSERT INTO interaction_db_metadata VALUES ('source_suppai_count', '0')")
    write_json(
        dist / "interaction_db_manifest.json",
        {
            "checksum_sha256": sha256(db_path),
            "interaction_db_version": "1.0.0",
            "total_interactions": 1,
            "source_drafts_count": 1,
            "source_suppai_count": 0,
        },
    )
    source_rules = tmp_path / "rules.json"
    write_json(source_rules, {"interaction_rules": [{"id": "r1"}]})
    severity_vocab = tmp_path / "severity_vocab.json"
    write_json(severity_vocab, {"severities": [{"id": "caution"}]})
    orphan_allowlist = tmp_path / "orphan_allowlist.json"
    write_json(orphan_allowlist, {"allowlist": []})

    args = argparse.Namespace(
        dist_dir=str(dist),
        source_rules=str(source_rules),
        severity_vocab=str(severity_vocab),
        orphan_allowlist=str(orphan_allowlist),
    )
    findings = audit.audit_interaction(args)
    assert findings == [], (
        f"Legacy schema (no canonical_id columns) must not crash; got: {[(f.code, f.message) for f in findings]}"
    )


def _minimal_catalog_db(path: Path):
    """Write a tiny valid, clean products_core. audit_export now inspects the DB
    via the V4 pillar contract gate, so manifest-focused tests need a real
    catalog rather than a placeholder byte string."""
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            "CREATE TABLE products_core ("
            "dsld_id TEXT, quality_score_status TEXT, quality_score_v4_100 REAL, "
            "pillar_formulation_v4 REAL, pillar_dose_v4 REAL, pillar_evidence_v4 REAL, "
            "pillar_transparency_v4 REAL, pillar_verification_v4 REAL, pillar_safety_hygiene_v4 REAL)"
        )
        # 11.2+20+18.9+15+6+10 = 81.1 reconciles with the total.
        conn.execute(
            "INSERT INTO products_core VALUES ('1', 'scored', 81.1, 11.2, 20.0, 18.9, 15.0, 6.0, 10.0)"
        )


def test_export_contract_requires_stamped_manifest_when_requested(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    db_path = dist / "pharmaguide_core.db"
    _minimal_catalog_db(db_path)
    write_json(dist / "export_manifest.json", {"schema_version": "1.0.0", "product_count": 1, "checksum_sha256": sha256(db_path)})

    args = argparse.Namespace(dist_dir=str(dist), require_stamped_manifest=True)
    codes = {finding.code for finding in audit.audit_export(args)}

    assert "EXPORT_MANIFEST_CONTRACT_FIELD" in codes


def test_stamp_manifest_accepts_working_build_checksum_field(tmp_path):
    dist = tmp_path / "final_db_output"
    dist.mkdir()
    db_path = dist / "pharmaguide_core.db"
    _minimal_catalog_db(db_path)
    write_json(
        dist / "export_manifest.json",
        {
            "schema_version": "1.0.0",
            "product_count": 1,
            "checksum": f"sha256:{sha256(db_path)}",
        },
    )

    args = argparse.Namespace(
        dist_dir=str(dist),
        matrix=str(MATRIX_PATH),
        strict_release=True,
        require_stamped_manifest=False,
    )

    assert audit.stamp_manifest(args) == []
    manifest = json.loads((dist / "export_manifest.json").read_text())
    assert manifest["checksum_sha256"] == sha256(db_path)
    assert manifest["pipeline_contract_version"] == "cleaner_first_source_of_truth_v1"
    assert manifest["strict_gate_summary"]["strict_mode"] is True
