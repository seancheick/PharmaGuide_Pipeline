import json
from pathlib import Path


DATA = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curated_interactions"
    / "curated_interactions_v1.json"
)
PAYLOAD = json.loads(DATA.read_text())
BY_ID = {row["id"]: row for row in PAYLOAD["interactions"]}


def test_latest_interaction_copy_edit_is_recorded_in_metadata():
    metadata = PAYLOAD["_metadata"]

    assert metadata["last_updated"] == "2026-08-08"
    assert any(
        note.startswith("2026-08-08:")
        and "vitamin E/warfarin" in note
        and "chromium/diabetes-medication" in note
        for note in metadata["migration_notes"]
    )


def test_disease_or_nutrient_associations_do_not_ship_as_interactions():
    rejected = {
        "DSI_ACEI_IRON",
        "DSI_ANTICONV_VITD",
        "DSI_CORTICO_CALCIUM_VITD",
        "DSI_DM_VITD",
        "DSI_DM_MAGNESIUM",
        "DSI_IRON_PPI",
        "DSI_PPI_B12",
        "DSI_PPI_CALCIUM",
        "DSI_PPI_IRON",
        "DSI_PPI_MAGNESIUM",
        "DSI_SSRI_FISHOIL",
        "DSI_STATINS_COQ10",
        "DSI_THYROID_TURMERIC",
        "DSI_VITE_ANTICOAG",
        "SSI_MAGNESIUM_CALCIUM",
        "SSI_VITE_VITK",
    }

    assert rejected.isdisjoint(BY_ID), (
        "Disease associations, unsupported ratio advice, and the duplicate "
        "vitamin E/vitamin K supplement warning must not ship as interactions"
    )


def test_fluoroquinolone_cation_rules_preserve_real_risk_without_false_precision():
    calcium = BY_ID["DSI_CALCIUM_CIPROFLOXACIN"]
    zinc = BY_ID["DSI_ZINC_FLUOROQUINOLONE"]

    assert calcium["agent1_id"] == "2551"
    assert calcium["agent1_name"] == "Ciprofloxacin"
    assert calcium["source_pmids"] == ["1524699"]
    assert "2 hours before or 6 hours after" in calcium["management"]

    assert zinc["agent1_id"] == "class:fluoroquinolones"
    assert zinc["source_pmids"] == ["1524699"]
    assert "timing interval differs by drug" in zinc["management"].lower()
    assert "prescription label" in zinc["management"].lower()
    assert "at least 2 hours before or 6 hours after" not in zinc["management"].lower()


def test_maoi_5htp_copy_does_not_apply_fluoxetine_washout_to_tranylcypromine():
    rule = BY_ID["DSI_MAOI_5HTP"]
    management = rule["management"].lower()

    assert "5 weeks after stopping tranylcypromine" not in management
    assert "product-specific washout" in management
    assert "prescriber" in management


def test_fluvoxamine_melatonin_rule_is_not_broadened_to_all_ssris():
    rule = BY_ID["DSI_SSRI_MELATONIN"]

    assert rule["agent1_id"] == "42355"
    assert rule["agent1_name"] == "Fluvoxamine"
    assert rule["source_pmids"] == ["10877005"]
    assert "other ssris" not in rule["management"].lower()


def test_zinc_copper_rule_only_fires_at_its_authored_screening_floor():
    rule = BY_ID["SSI_ZINC_COPPER"]
    management = rule["management"].lower()

    assert rule["materiality"] == "dose_dependent"
    assert rule["dose_threshold"]["agent_canonical_id"] == "zinc"
    assert rule["dose_threshold"]["value"] == 25
    assert rule["dose_threshold"]["unit"] == "mg"
    assert "screening threshold" in management
    assert "toxicity cutoff" in management
    assert "separate" not in management


def test_alpha_lipoic_acid_uses_the_parent_ingredient_cui():
    rule = BY_ID["DSI_METFORMIN_ALA"]

    assert rule["agent2_id"] == "C0023791"
    assert rule["agent2_canonical_id"] == "alpha_lipoic_acid"


def test_low_severity_rules_are_explicitly_background_only():
    low_severity = [
        row for row in BY_ID.values()
        if row["severity"] in {"Minor", "Monitor"}
    ]

    assert low_severity
    for row in low_severity:
        assert row.get("display_layer") == "background", row["id"]
        assert row.get("background_rationale", "").strip(), row["id"]


def test_warfarin_vitamin_e_guidance_does_not_claim_a_safe_cutoff():
    rule = BY_ID["DSI_WAR_VITE"]
    mechanism = rule["mechanism"].lower()
    management = rule["management"].lower()

    assert rule["agent1_id"] == "11289"
    assert rule["source_pmids"] == ["24166490"]
    assert "generally safe" not in management
    assert "≤400" not in management
    assert "<=400" not in management
    assert "elevate inr" not in mechanism
    assert "do not change warfarin" in management
    assert "anticoagulation" in management
    assert "does not mean" in management
    assert "known dose limit" in management
    assert management.startswith("contains vitamin e. large supplemental doses")


def test_warfarin_vitamin_k_copy_describes_direction_and_consistency():
    rule = BY_ID["DSI_WAR_VITK"]
    mechanism = rule["mechanism"].lower()
    management = rule["management"].lower()

    assert "reduce the anticoagulant effect" in mechanism
    assert "increase it" in mechanism
    assert "raises inr" not in mechanism
    assert "consistency warning, not a ban" in management
    assert ">100" not in management
    assert "food and supplements" in management
    assert "do not change warfarin" in management
    assert rule["severity"] == "Moderate", (
        "A consistency/monitoring interaction must ship in the review tier, "
        "not the app's categorical 'Not recommended' tier"
    )


def test_chromium_copy_explains_the_authored_screening_threshold():
    rule = BY_ID["DSI_DM_CHROMIUM"]
    management = rule["management"].lower()
    threshold = rule["dose_threshold"]

    assert rule["severity"] == "Minor"
    assert rule["display_layer"] == "background"
    assert rule["background_rationale"].strip()
    assert threshold["value"] == 200
    assert threshold["unit"] == "mcg"
    assert threshold["confidence_basis"] == "inferred_from_dose_range"
    assert "not a guideline cutoff" in threshold["rationale"].lower()
    assert "at least 200 mcg/day" in management
    assert "screening threshold" in management
    assert "not a proven toxicity cutoff" in management
    assert "do not change" in management
    assert management.startswith("chromium may lower blood glucose")
