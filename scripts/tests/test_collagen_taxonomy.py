"""Shared collagen subtype taxonomy — used by both enricher and v4 scorer."""
from __future__ import annotations

from collagen_taxonomy import (  # noqa: E402
    classify_collagen_subtype,
    classify_collagen_subtype_strict,
    SUBTYPE_TO_DOSING_ALIAS,
    UNDENATURED_TYPE_II, EGGSHELL_MEMBRANE, HYDROLYZED_TYPE_II, GELATIN, PEPTIDES_I_III,
)


def test_strict_asserts_only_on_row_signal():
    # row proves the subtype -> concrete
    assert classify_collagen_subtype_strict("undenatured type ii collagen uc-ii") == UNDENATURED_TYPE_II
    assert classify_collagen_subtype_strict("chicken sternum collagen") == HYDROLYZED_TYPE_II
    assert classify_collagen_subtype_strict("hydrolyzed collagen peptides") == PEPTIDES_I_III
    assert classify_collagen_subtype_strict("marine collagen") == PEPTIDES_I_III
    assert classify_collagen_subtype_strict("bovine gelatin") == GELATIN


def test_strict_leaves_generic_collagen_unspecified():
    # bare "collagen" with no distinguishing signal -> None (enricher emits
    # 'unspecified'; scorer resolves with product context)
    assert classify_collagen_subtype_strict("collagen") is None
    assert classify_collagen_subtype_strict("collagen (unspecified)") is None


def test_uc2_from_row_identity():
    assert classify_collagen_subtype("undenatured type ii collagen uc-ii") == UNDENATURED_TYPE_II
    assert classify_collagen_subtype("nt2 collagen") == UNDENATURED_TYPE_II
    assert classify_collagen_subtype("undenatured collagen") == UNDENATURED_TYPE_II


def test_uc2_not_inferred_from_product_name_only():
    # a co-ingredient UC-II named only in the title must NOT make a peptide row UC-II
    assert classify_collagen_subtype("hydrolyzed collagen peptides",
                                     product_name="Collagen Peptides Plus UC-II") == PEPTIDES_I_III


def test_eggshell_membrane():
    assert classify_collagen_subtype("natural eggshell membrane nem") == EGGSHELL_MEMBRANE


def test_hydrolyzed_type2_biocell_and_sternum():
    assert classify_collagen_subtype("biocell hydrolyzed type ii collagen") == HYDROLYZED_TYPE_II
    assert classify_collagen_subtype("chicken sternum collagen") == HYDROLYZED_TYPE_II


def test_pure_type2_from_product_name():
    # generic collagen row, Type II disclosed only in the product name
    assert classify_collagen_subtype("collagen", product_name="Type II Collagen Complex") == HYDROLYZED_TYPE_II


def test_multitype_blend_stays_peptides():
    assert classify_collagen_subtype("hydrolyzed type i type ii type iii collagen peptides") == PEPTIDES_I_III


def test_gelatin_not_hydrolyzed():
    assert classify_collagen_subtype("bovine gelatin") == GELATIN
    # "collagen hydrolysate" is hydrolyzed -> peptides, not gelatin
    assert classify_collagen_subtype("hydrolyzed gelatin collagen peptides") == PEPTIDES_I_III


def test_default_peptides():
    assert classify_collagen_subtype("hydrolyzed collagen peptides") == PEPTIDES_I_III
    assert classify_collagen_subtype("collagen") == PEPTIDES_I_III


def test_subtype_alias_map_complete():
    for subtype in (UNDENATURED_TYPE_II, EGGSHELL_MEMBRANE, HYDROLYZED_TYPE_II, GELATIN, PEPTIDES_I_III):
        assert subtype in SUBTYPE_TO_DOSING_ALIAS
