"""Product-level omega form disclosures must reach the IQM-owned row."""

from enrich_supplements_v3 import SupplementEnricherV3
import pytest

from normalization import omega_molecular_form_disclosure


def test_shared_detector_accepts_real_disclosure_and_rejects_false_contexts() -> None:
    assert omega_molecular_form_disclosure(
        ["All fish oils are in the triglyceride form."]
    ) == "triglyceride"
    assert omega_molecular_form_disclosure(
        ["Contains medium-chain triglycerides (MCT oil)."]
    ) is None
    assert omega_molecular_form_disclosure(
        ["Supports healthy triglyceride levels."]
    ) is None
    assert omega_molecular_form_disclosure(
        ["Triglyceride Form (TG as rTG)."]
    ) == "re-esterified triglyceride"


def test_product_level_triglyceride_disclosure_upgrades_unspecified_epa_dha() -> None:
    enricher = SupplementEnricherV3()
    rows = [
        {
            "canonical_id": canonical_id,
            "matched_form": f"{canonical_id} (unspecified)",
            "form_id": f"{canonical_id} (unspecified)",
            "bio_score": 8.0,
            "mapped": True,
            "form_match_status": "n/a",
            "matched_forms": [],
            "unmapped_forms": [],
        }
        for canonical_id in ("epa", "dha")
    ]
    quality = {"ingredients": rows, "ingredients_scorable": rows}
    product = {
        "statements": [{
            "type": "Formulation re: Other",
            "notes": "All fish oils are in the triglyceride form.",
        }]
    }

    changed = enricher._apply_product_level_omega_form_disclosure(product, quality)

    assert changed == 2
    assert {row["matched_form"] for row in rows} == {
        "EPA fish oil triglyceride",
        "DHA fish oil triglyceride",
    }
    assert {row["bio_score"] for row in rows} == {11.0}
    assert {row["form_match_status"] for row in rows} == {"mapped"}
    assert {row["form_source"] for row in rows} == {"product_label_disclosure"}


def test_product_level_disclosure_does_not_override_named_or_unmapped_form() -> None:
    enricher = SupplementEnricherV3()
    rows = [
        {
            "canonical_id": "epa",
            "matched_form": "ethyl ester form",
            "form_id": "ethyl ester form",
            "bio_score": 9.0,
            "mapped": True,
            "form_match_status": "mapped",
        },
        {
            "canonical_id": "dha",
            "matched_form": None,
            "form_id": None,
            "bio_score": None,
            "mapped": True,
            "form_match_status": "unmapped",
        },
    ]
    quality = {"ingredients": rows, "ingredients_scorable": rows}

    changed = enricher._apply_product_level_omega_form_disclosure(
        {"labelText": {"raw": "All fish oils are in triglyceride form."}},
        quality,
    )

    assert changed == 0
    assert rows[0]["matched_form"] == "ethyl ester form"
    assert rows[1]["form_match_status"] == "unmapped"


@pytest.mark.parametrize("claim", [
    "EPA and DHA help lower triglyceride levels.",
    "Helps reduce triglycerides.",
    "Triglyceride lowering support.",
    "Supports healthy triglycerides.",
    "Reduces blood triglycerides.",
    "Supports healthy triglyceride levels and triglyceride metabolism.",
    "Supports healthy triglyceride levels. Triglycerides are a type of fat in the blood.",
])
def test_lipid_claim_is_not_molecular_form(claim):
    assert omega_molecular_form_disclosure([claim]) is None


@pytest.mark.parametrize("surface", [
    "Natural triglyceride form. Helps reduce triglycerides.",
    "Natural triglyceride form helps maintain healthy triglyceride levels.",
    "Supports healthy triglycerides; fish oil in triglyceride form.",
    "Natural triglyceride form with medium-chain triglycerides (MCT).",
    "Fish Oil Triglycerides",
    "As natural triglycerides",
    "Triglyceride-form fish oil",
    "Triglycerides, Natural",
    "Omega-3 Triglyceride Oil Extract",
    "Better absorption\nTrue triglyceride\nGreat taste!",
])
def test_real_form_survives_separate_health_claim(surface):
    assert omega_molecular_form_disclosure([surface]) == "triglyceride"


def test_health_claim_cannot_upgrade_enriched_forms_or_public_pillars():
    import json
    from copy import deepcopy
    from pathlib import Path
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / "fixtures/omega_claim_11609_raw.json").read_text())
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    enricher = SupplementEnricherV3()
    before, _ = enricher.enrich_product(deepcopy(clean))
    claimed = deepcopy(clean)
    claimed.setdefault("statements", []).append({"notes": "EPA and DHA help lower triglyceride levels."})
    after, _ = enricher.enrich_product(claimed)
    assert after["ingredient_quality_data"] == before["ingredient_quality_data"]
    old, new = build_scored_artifact(before), build_scored_artifact(after)
    for pillar in ("formulation", "transparency", "evidence"):
        assert new["quality_pillars_v4"][pillar] == old["quality_pillars_v4"][pillar]


@pytest.mark.parametrize("surface", [
    "Total Omega-3 (Form: from Ethyl Esters, and Triglycerides)",
    "As ethyl esters and triglycerides.",
    "Triglyceride, ehtyl-ester & phospholipid omega-3 forms",
])
def test_coordinated_form_disclosure_remains_ambiguous(surface):
    assert omega_molecular_form_disclosure([surface]) is None


@pytest.mark.parametrize("carrier", ["MCT", "C8", "C10", "medium-chain", "caprylic", "capric", "coconut"])
def test_explicit_carrier_form_is_not_fish_oil_form(carrier):
    assert omega_molecular_form_disclosure([f"{carrier} triglyceride form"]) is None


@pytest.mark.parametrize("surface", [
    "MCT oil in triglyceride form", "MCT oil in the triglyceride form",
    "Triglyceride form (MCT)", "C8 oil in triglyceride form",
])
def test_carrier_form_with_oil_or_parenthesis_remains_excluded(surface):
    assert omega_molecular_form_disclosure([surface]) is None
