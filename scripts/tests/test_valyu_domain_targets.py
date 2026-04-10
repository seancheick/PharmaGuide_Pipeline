import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_audit.valyu_domain_targets import load_iqm_gap_targets


def test_iqm_gap_targets_exclude_excipient_noise():
    iqm = {
        "ingredients": [
            {"standard_name": "Berberine", "category": "herb"},
            {"standard_name": "Silicon Dioxide", "category": "flow_agent_anticaking"},
        ]
    }
    clinical = {"backed_clinical_studies": []}

    targets = load_iqm_gap_targets(iqm, clinical)

    names = {row["entity_name"] for row in targets}
    assert "Berberine" in names
    assert "Silicon Dioxide" not in names


def test_iqm_gap_targets_do_not_depend_on_unmapped_inactive_outputs():
    iqm = {"ingredients": [{"standard_name": "Alpha Lipoic Acid", "category": "antioxidant"}]}
    clinical = {"backed_clinical_studies": []}

    targets = load_iqm_gap_targets(iqm, clinical)

    assert len(targets) == 1
    assert targets[0]["entity_name"] == "Alpha Lipoic Acid"
    assert "unmapped" not in targets[0]["target_file"].lower()
