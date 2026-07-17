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
        ("Soybean Seed Extract", "soybean"),                 # explicit seed wording for soybean extract
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


# REAL cleaned forms[] captured from the corpus (output_<brand>/cleaned/*.json),
# NOT a hand-faked bare {"name": "extract"} token. The cleaner emits the
# adjective qualifiers (extract+standardized) or the botanical genus
# (Amorphophallus konjac) — none is a literal bare
# "extract" — so these are the ACTUAL inputs the clean→enrich seam sees. A
# low-level _match_quality_map(label, label, iqm) probe (no cleaned_forms) cannot
# exercise this boundary; an earlier fictional bare-"extract" test gave false green.
@pytest.mark.parametrize(
    "label,cleaned_forms,expected",
    [
        (
            "Boswellia serrata AKBA standardized extract (wood) resin",
            [{"name": "extract", "source": "name_extraction"},
             {"name": "standardized", "source": "name_extraction"}],
            "boswellia",
        ),
        (
            "LuraLean Propolmannan (Amorphophallus konjac K. Koch, ssp. Amorphophallus japonica) fiber extract",
            [{"name": "Amorphophallus konjac", "ingredientId": 150162, "order": 1,
              "prefix": None, "percent": None, "category": "botanical",
              "ingredientGroup": "Konjac", "uniiCode": None},
             {"name": "ssp. Amorphophallus japonica", "ingredientId": 150163, "order": 2,
              "prefix": None, "percent": None, "category": "botanical",
              "ingredientGroup": "Konjac", "uniiCode": None}],
            "fiber",
        ),
    ],
)
def test_branded_extract_labels_resolve_through_real_seam(enricher, label, cleaned_forms, expected):
    """Branded extract labels reach the verified IQM parent with their REAL
    cleaned forms[], so the clean→enrich seam (not just label text) is exercised.
    The Boswellia case is the guard for the extract+standardized adjective-qualifier
    exemption; konjac exercises botanical-form resolution. Source-botanical
    ForsLean is intentionally tested at the cleaner identity seam instead: it
    remains Coleus while forskolin is separate marker evidence.
    """
    iqm = enricher.databases["ingredient_quality_map"]
    m = enricher._match_quality_map(label, label, iqm, cleaned_forms=cleaned_forms)
    assert m is not None and m.get("canonical_id") == expected, (
        f"{label!r} should resolve to {expected!r} through the real seam; got {m}"
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


def test_transglucosidase_routes_to_specific_digestive_enzyme(enricher):
    iqm = enricher.databases["ingredient_quality_map"]
    direct_match = enricher._match_quality_map(
        "Transglucosidase",
        "Transglucosidase",
        iqm,
    )
    assert direct_match is not None
    assert direct_match.get("canonical_id") == "digestive_enzymes"
    assert direct_match.get("form_id") == "specific enzymes"

    source_match = enricher._match_quality_map(
        "Transglucosidase",
        "Transglucosidase",
        iqm,
        cleaned_forms=[
            {
                "name": "Aspergillus niger",
                "category": "botanical",
                "ingredientGroup": "Aspergillus niger",
                "uniiCode": "9IOA40ANG6",
            }
        ],
    )
    assert source_match is not None
    assert source_match.get("canonical_id") == "digestive_enzymes"
    assert enricher._identity_taxonomy_coherent(
        {
            "name": "Transglucosidase",
            "uniiCode": None,
            "forms": [
                {
                    "name": "Aspergillus niger",
                    "category": "botanical",
                    "ingredientGroup": "Aspergillus niger",
                    "uniiCode": "9IOA40ANG6",
                }
            ],
        },
        source_match,
        iqm,
    ) is True
