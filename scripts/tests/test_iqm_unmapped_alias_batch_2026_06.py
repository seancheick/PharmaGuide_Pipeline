"""IQM verified-alias batch (2026-06 unmapped triage).

Unmapped DSLD labels whose compound IS an existing IQM identity get aliased onto
the parent so they SCORE correctly — NOT recognized as non-scorable markers (that
would under-credit the active). Each is per-item chemistry-verified against the
existing IQM parent before aliasing.

  - "Silibinins" (plural) == the silibinin / silybin flavonolignan group
    (silibinin A + B), the milk_thistle active. "Silibinin" singular already maps
    to milk_thistle and "silybins" plural is already an alias; the plural
    "silibinins" was the actual unmapped DSLD label (per Codex review).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.mark.parametrize("label", ["Silibinins", "silibinins", "Silibinin"])
def test_silibinin_forms_map_to_milk_thistle(enricher, label):
    iqm = enricher.databases["ingredient_quality_map"]
    m = enricher._match_quality_map(label, label, iqm)
    assert m is not None and m.get("canonical_id") == "milk_thistle", (
        f"{label!r} must map to the milk_thistle IQM active (silibinin flavonolignan); got {m}"
    )


# Per-item chemistry-verified: each unmapped label IS the named IQM parent's compound.
@pytest.mark.parametrize(
    "label,expected",
    [
        ("Chinese Red Ginseng", "ginseng"),                  # steamed Panax = red ginseng
        ("Total Caffeoylquinic Acids", "caffeoyl_derivatives"),  # "Total" variant of caffeoylquinic acids
        ("Glucomannan root extract", "fiber"),               # konjac glucomannan fiber
        ("Isoflavonoids", "isoflavones"),                    # isoflavone class
        ("Soy Germ Isoflavones Concentrate", "isoflavones"), # soy germ isoflavone concentrate
        ("Allin", "garlic"),                                 # typo of alliin; alliin AND allicin both -> garlic
        ("beta-sitostanol", "phytosterols"),                 # == sitostanol (already a phytosterols alias)
        ("Boswellia serrata AKBA standardized extract", "boswellia"),  # standardized extract, not the bare AKBA marker
        ("LuraLean Propolmannan (Amorphophallus konjac K. Koch, ssp. Amorphophallus japonica) fiber extract", "fiber"),  # purified konjac glucomannan
        ("Bioflavonoid Fruit Extract", "bioflavonoids"),     # generic bioflavonoid active
    ],
)
# DEFERRED branded items (NOT aliased — would over-credit / unverified marketing salts):
#   - "40% MCTs": explicit 40% standardization, direct mct_oil alias over-credits 2.5x.
#   - "Acetyl L-Carnitine Arginate Di-HCl" / "L-Tauro Acetyl-L-Carnitine Taurinate HCl":
#     novel branded carnitine salts; the IQM treats novel arginate salts as marketing
#     forms (cf. chromium chelidamate arginate downgraded to bio 0.02, zero PubMed PK).
#   - "Biolut Marigold Extract" -> routed to the marigold BOTANICAL (dose-aware lutein
#     via marker contribution), NOT a direct lutein IQM alias — see the botanical batch.
def test_unmapped_label_maps_to_verified_iqm_parent(enricher, label, expected):
    iqm = enricher.databases["ingredient_quality_map"]
    m = enricher._match_quality_map(label, label, iqm)
    assert m is not None and m.get("canonical_id") == expected, (
        f"{label!r} must map to the {expected!r} IQM parent; got {m}"
    )


@pytest.mark.parametrize(
    "label,expected",
    [
        ("LuraLean Propolmannan (Amorphophallus konjac K. Koch, ssp. Amorphophallus japonica) fiber extract", "fiber"),
        ("ForsLean (Coleus forskohlii) root extract", "forskolin"),
        ("Boswellia serrata AKBA standardized extract (wood) resin", "boswellia"),
    ],
)
def test_generic_extract_form_does_not_block_verified_iqm_alias(enricher, label, expected):
    """Cleaner-parsed bare ``extract`` is a generic descriptor, not failed form evidence."""
    iqm = enricher.databases["ingredient_quality_map"]
    m = enricher._match_quality_map(
        label,
        label,
        iqm,
        cleaned_forms=[{"name": "extract", "prefix": None, "category": None, "ingredientGroup": None}],
    )
    assert m is not None and m.get("canonical_id") == expected, (
        f"{label!r} should still map through the clean→enrich seam; got {m}"
    )
    assert m.get("match_status") != "FORM_UNMAPPED"


def test_bare_chicken_sternum_collagen_is_not_global_iqm_alias(enricher):
    """Bare chicken-sternum text is product-context routed, not a global IQM alias.

    The same row text can describe BioCell hydrolyzed chicken sternal cartilage
    or native/undenatured type-II material. product_context_canonical_overrides
    owns the reviewed Jarrow BioCell case; a global alias would bypass that guard.
    """
    collagen = enricher.databases["ingredient_quality_map"]["collagen"]
    forbidden = {"chicken sternum collagen extract", "chicken sternum collagen"}
    for form_name, form in collagen.get("forms", {}).items():
        aliases = {str(alias).lower() for alias in form.get("aliases", [])}
        assert aliases.isdisjoint(forbidden), (
            f"bare chicken sternum alias found in collagen form {form_name!r}"
        )
