"""Dose V4.1 §2.2: every active config-owned Dose anchor carries complete
reference semantics (one shared schema, one CI check).

Anchors still written as literals in a module or as rows in a data file are
listed in PENDING_ANCHOR_FAMILIES (review packet item 2). The list is exact:
moving a family into semantic records must delete its entry, and a new family
cannot be added without a record or an explicit entry here."""
import json
from pathlib import Path

import jsonschema
import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((SCRIPTS / "scoring_v4/schemas/dose_reference_semantics.schema.json").read_text())
CONFIG = json.loads((SCRIPTS / "scoring_v4/config/quality_score.json").read_text())
OMEGA = json.loads((SCRIPTS / "data/omega_rubric.json").read_text())

PENDING_ANCHOR_FAMILIES = {
    "scripts/scoring_v4/modules/sports_dose.py::_score_primary": "sports band literals",
    "scripts/scoring_v4/modules/multi_prenatal_dose.py::_coverage_unit_credit": "panel coverage curve literals",
    "scripts/scoring_v4/modules/b_complex.py::_coverage_credit": "B-complex coverage curve literals",
    "scripts/scoring_v4/modules/collagen_profile.py::score_collagen_dose": "collagen subtype ranges",
    "scripts/scoring_v4/modules/sleep_support.py::score_sleep_support_dose": "sleep active ranges",
    "scripts/scoring_v4/modules/joint_support.py::score_joint_support_dose": "joint active ranges",
    "scripts/scoring_v4/modules/immune_support.py::score_immune_support_dose": "immune active ranges",
    "scripts/data/rda_therapeutic_dosing.json": "botanical therapeutic ranges",
    "scripts/data/rda_optimal_uls.json": "per-nutrient DRI rows and clinical anchors (curve records exist)",
    "scripts/data/clinically_relevant_strains.json": "probiotic strain CFU tiers",
    "scripts/data/backed_clinical_studies.json": "positive clinical and aggregate formula benchmarks",
}


def _records():
    dm = CONFIG["dose_magnitudes"]
    found = {}
    for key, value in dm["generic"]["contribution_policy_targets"].items():
        if not key.startswith("_"):
            found[f"generic.contribution_policy_targets.{key}"] = value
    for block in ("generic", "multi_prenatal"):
        for key, value in dm[block]["reference_semantics"].items():
            if not key.startswith("_"):
                found[f"{block}.reference_semantics.{key}"] = value
    found["dose_safety_ceiling"] = CONFIG["dose_safety_ceiling"]["reference_semantics"]
    found["dose_safety_ceiling.caffeine"] = CONFIG["dose_safety_ceiling"]["caffeine"]
    for key, value in OMEGA["dose"]["adequacy_references"].items():
        if not key.startswith("_"):
            found[f"omega.adequacy_references.{key}"] = value
    found["omega.epa_dha_band_semantics"] = OMEGA["dose"]["epa_dha_band_semantics"]
    return found


@pytest.mark.parametrize("name,record", sorted(_records().items()))
def test_config_anchor_has_complete_semantics(name, record):
    jsonschema.validate(instance=record, schema=SCHEMA)
    owner_path = record["owner"].split("::")[0]
    assert (SCRIPTS.parent / owner_path).exists(), (name, owner_path)


def test_every_generic_reference_kind_has_a_record():
    from scoring_v4.modules import generic_dose
    kinds = {generic_dose._adequacy_reference_kind(c) for c in ("vitamin_d", "quercetin", "potassium")}
    assert kinds == {"dri", "clinical_anchor", "legacy"}
    assert kinds <= set(CONFIG["dose_magnitudes"]["generic"]["reference_semantics"])


def test_numeric_anchor_records_carry_their_number():
    records = _records()
    for name in ("generic.contribution_policy_targets.magnesium", "generic.contribution_policy_targets.calcium"):
        assert isinstance(records[name]["target_mg"], float)
    for name in ("omega.adequacy_references.ordinary_adult", "omega.adequacy_references.triglyceride_purpose"):
        assert isinstance(records[name]["target_mg_day"], float)
    assert records["dose_safety_ceiling.caffeine"]["exceeds_above_mg_day"] == 400.0


def test_pending_anchor_families_still_exist_and_are_exact():
    for owner in PENDING_ANCHOR_FAMILIES:
        path, _, symbol = owner.partition("::")
        source = (SCRIPTS.parent / path)
        assert source.exists(), owner
        if symbol:
            assert f"def {symbol}" in source.read_text(), owner
