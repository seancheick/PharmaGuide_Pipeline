"""Exhaustive Dose V4.1 source semantics: native records and active config owners.

Every new source record or numeric target is inspected, without a pending-family
allow-list. Descriptive regimens are not source-authorized continuous curves.
"""
import json
from pathlib import Path

import jsonschema
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((SCRIPTS / "scoring_v4/schemas/dose_reference_semantics.schema.json").read_text())
CONFIG = json.loads((SCRIPTS / "scoring_v4/config/quality_score.json").read_text())


def _records():
    found = {}
    def walk(value, path):
        if isinstance(value, dict):
            if "reference_type" in value and "curve" in value:
                found[path] = value
                return
            for key, child in value.items():
                if not key.startswith("_"):
                    walk(child, path + "." + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path + "." + str(index))
    walk(CONFIG, "quality_score")
    walk(json.loads((SCRIPTS / "data/omega_rubric.json").read_text()), "omega")
    # These owners have reference amounts on every native record.
    for filename, key in [("rda_optimal_uls", "nutrient_recommendations"),
                          ("rda_therapeutic_dosing", "therapeutic_dosing"),
                          ("clinically_relevant_strains", "clinically_relevant_strains")]:
        data = json.loads((SCRIPTS / ("data/" + filename + ".json")).read_text())
        for record in data[key]:
            name = filename + ":" + record["id"]
            if filename == "clinically_relevant_strains" and not record.get("reference_semantics"):
                # Native identity/Evidence records with no CFU anchor do not
                # constitute an active numerical curve. New numeric tiers
                # cannot enter this exception.
                thresholds = record.get("cfu_thresholds") or {}
                assert thresholds.get("tiers_cfu_per_day") is None, name
                assert thresholds.get("evidence") is None, name
                continue
            assert isinstance(record.get("reference_semantics"), dict), name
            found[name] = record["reference_semantics"]
    for filename, key in [("backed_clinical_studies", "backed_clinical_studies"),
                          ("literature_evidence_records", "literature_evidence_records")]:
        for record in json.loads((SCRIPTS / ("data/" + filename + ".json")).read_text())[key]:
            # Only actual curated amount owners are Dose references; clinical
            # records containing no regimen/minimum remain Evidence-only.
            if any(record.get(field) is not None for field in (
                    "min_clinical_dose", "studied_dose_min", "studied_dose_max")) or record.get("reference_semantics"):
                name = filename + ":" + str(record.get("id") or record.get("canonical_id"))
                assert isinstance(record.get("reference_semantics"), dict), name
                found[name] = record["reference_semantics"]
    return found


@pytest.mark.parametrize("name,record", sorted(_records().items()))
def test_config_anchor_has_complete_semantics(name, record):
    jsonschema.validate(instance=record, schema=SCHEMA)
    assert record["reference_type"] != "unfinished_review", name
    assert (SCRIPTS.parent / record["owner"].split("::")[0]).exists(), name
    assert not record["approval_status"].startswith("current_production_interim"), name
    if record["curve"] != "completed_no_benchmark_neutral":
        assert record["source_ids"], name


def test_every_generic_reference_kind_has_a_record():
    from scoring_v4.modules import generic_dose
    kinds = {generic_dose._adequacy_reference_kind(c) for c in ("vitamin_d", "phosphorus", "quercetin", "potassium")}
    assert kinds == {"dri", "no_benchmark"}
    assert kinds <= set(CONFIG["dose_magnitudes"]["generic"]["reference_semantics"])


def test_every_sports_contribution_target_has_approved_native_semantics():
    sports = CONFIG["dose_magnitudes"]["sports"]
    assert set(sports["contribution_targets"]) == {"protein", "creatine", "beta_alanine", "hmb", "caffeine"}
    for identity in sports["contribution_targets"]:
        record = sports["reference_semantics"][identity]
        assert record["curve"] == "proportional_then_plateau"
        assert record["approval_status"] == "approved_sean_2026_10_18"


def test_retired_generic_paths_cannot_supply_an_unreviewed_fallback():
    from scoring_v4.modules import generic_dose
    block = CONFIG["dose_magnitudes"]["generic"]
    assert "window_rda_threshold" not in block
    assert "_clinical_anchor_reference_by_canonical" not in block
    for identity in ("quercetin", "unknown_reference", "sodium", "chloride", "magnesium", "calcium"):
        assert generic_dose._band_credit(1000, None, identity) is None


def test_numeric_anchor_records_carry_their_number():
    records = _records()
    for name in ("magnesium", "calcium"):
        assert isinstance(records["quality_score.dose_magnitudes.generic.contribution_policy_targets." + name]["target_mg"], float)
    assert CONFIG["dose_safety_ceiling"]["caffeine"]["exceeds_above_mg_day"] == 400.0


@pytest.mark.parametrize('nutrient', ['magnesium', 'calcium'])
def test_contribution_targets_do_not_misname_fda_high_source_threshold(nutrient):
    # 21 CFR101.54(b)/(c): high >=20%, good source10-19%, perRACC.
    rationale = CONFIG['dose_magnitudes']['generic']['contribution_policy_targets'][nutrient]['rationale']
    assert "'good source'" not in rationale
    assert 'high' in rationale and 'RACC' in rationale


def test_rda_curve_does_not_claim_fda_prescribes_its_half_credit():
    rationale = CONFIG['dose_magnitudes']['generic']['reference_semantics']['dri']['rationale']
    assert 'PharmaGuide policy' in rationale
    assert 'Daily Value' in rationale and 'RDA/AI' in rationale
    assert 'RACC' in rationale


def test_semantic_owner_symbols_exist():
    import ast
    for name, record in _records().items():
        path, separator, symbol = record['owner'].partition('::')
        assert separator and symbol, (name, record['owner'])
        source = SCRIPTS.parent / path
        if source.suffix == '.json':
            if source.name == 'literature_evidence_records.json':
                # This existing registry is keyed by canonical_id, not id.
                entries = json.loads(source.read_text())['literature_evidence_records']
                assert sum(row.get('canonical_id') == symbol for row in entries) == 1, (name, record['owner'])
                continue
            def ids(value):
                if isinstance(value, dict):
                    yield value.get('id')
                    for child in value.values():
                        yield from ids(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from ids(child)
            assert symbol in set(ids(json.loads(source.read_text()))), (name, record['owner'])
            continue
        tree = ast.parse(source.read_text())
        symbols = {node.name for node in ast.walk(tree)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        assert symbol.split('.')[-1] in symbols, (name, record['owner'])
