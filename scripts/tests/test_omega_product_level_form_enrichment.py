"""Product-level omega form disclosures must reach the IQM-owned row."""

from enrich_supplements_v3 import SupplementEnricherV3
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
