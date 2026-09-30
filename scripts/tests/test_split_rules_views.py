"""The clinician views are generated from ingredient_interaction_rules.json.

A view the generator no longer produces (a drug class that was split, a condition
with no rules left) must disappear on regeneration, or clinicians review a
stale policy. Only files the generator wrote (its header) may be removed.
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "split_rules_by_condition.py"


def _module():
    spec = importlib.util.spec_from_file_location("split_rules_by_condition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stale_generated_views_are_removed_and_hand_written_files_kept(tmp_path):
    views = _module()
    views.VIEWS_DIR = tmp_path
    out = tmp_path / "by_drug_class"
    out.mkdir()
    (out / "hypoglycemics.md").write_text(views.HEADER + "# retired class\n")
    (out / "notes.md").write_text("# hand-written, not generated\n")
    rules = [{
        "subject_ref": {"canonical_id": "berberine", "db": "ingredient_quality_map"},
        "drug_class_rules": [{"drug_class_id": "hypoglycemics_high_risk", "severity": "caution"}],
    }]

    views.write_drug_class_views(rules, [{"id": "hypoglycemics_high_risk", "label": "High risk"}])

    assert (out / "hypoglycemics_high_risk.md").exists()
    assert not (out / "hypoglycemics.md").exists()
    assert (out / "notes.md").exists()
