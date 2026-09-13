"""Every probiotic label strain resolves to one honest identity state.

"Not reviewed yet" must never read as "no evidence", and a species name must
never inherit a strain's research. The resolution is a label fact computed
once by the enricher and carried on the blend row into the blob.
"""
import pytest

from probiotic_measurements import label_strain_identity_resolution


REGISTRY = {
    "STRAIN_LGG": {"id": "STRAIN_LGG", "standard_name": "Lactobacillus rhamnosus GG",
                   "aliases": ["LGG"], "cfu_thresholds": {"dr_pham_signoff": True}},
    "STRAIN_ACIDOPHILUS_LA14": {"id": "STRAIN_ACIDOPHILUS_LA14",
                                "standard_name": "Lactobacillus acidophilus La-14",
                                "aliases": ["La-14"], "evidence_level": "unreviewed",
                                "cfu_thresholds": {"dr_pham_signoff": False}},
}


@pytest.mark.parametrize("label,clinical_id,expected", [
    ("Lactobacillus rhamnosus GG", "STRAIN_LGG", "exact_strain_reviewed"),
    ("Lactobacillus acidophilus La-14", "STRAIN_ACIDOPHILUS_LA14", "exact_strain_unreviewed"),
    ("Lactobacillus acidophilus Lp-999", None, "strain_designation_unregistered"),
    ("Bifidobacterium bifidum (CUL 20)", None, "strain_designation_unregistered"),
    ("Lactobacillus acidophilus", None, "species_only"),
    ("L. acidophilus", None, "species_only"),
    ("Bifidobacterium animalis subsp. lactis", None, "species_only"),
    ("Lactobacillus", None, "genus_only"),
    ("Bulgarian Yogurt concentrate", None, "unresolved_label_text"),
    ("", None, "unresolved_label_text"),
])
def test_label_resolution_states(label, clinical_id, expected):
    out = label_strain_identity_resolution(label, clinical_id, REGISTRY)
    assert out["resolution"] == expected
    assert out["clinical_id"] == clinical_id


def test_blocked_or_hold_rows_are_rejected_not_unreviewed():
    out = label_strain_identity_resolution("Streptococcus uberis KJ2", "BLOCKED_OR_HOLD", REGISTRY)
    assert out["resolution"] == "rejected_by_clinician"


def test_species_only_never_borrows_a_strain_identity():
    out = label_strain_identity_resolution("Lactobacillus acidophilus", "STRAIN_ACIDOPHILUS_LA14", REGISTRY)
    # The caller may pass a clinical_id, but a species-only label cannot own a strain.
    assert out["resolution"] == "species_only"
    assert out["clinical_id"] is None
