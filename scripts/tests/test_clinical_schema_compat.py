import os
import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements import SupplementScorer


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TestClinicalSchemaCompatibility:
    @pytest.fixture
    def enricher(self):
        return SupplementEnricherV3()

    @pytest.fixture
    def scorer(self):
        return SupplementScorer()

    def test_enrichment_passthroughs_optional_clinical_fields(self, enricher):
        enricher.databases["backed_clinical_studies"] = {
            "backed_clinical_studies": [
                {
                    "id": "INGR_TEST_DOSING",
                    "standard_name": "Test Ingredient",
                    "aliases": ["test ingredient alias"],
                    "evidence_level": "ingredient-human",
                    "study_type": "rct_single",
                    "min_clinical_dose": 500,
                    "dose_unit": "mg",
                    "typical_effective_dose": "500-1000 mg/day",
                    "dose_range": {"min": 500, "max": 1000, "unit": "mg"},
                    "base_points": 4,
                    "multiplier": 0.65,
                    "computed_score": 2.6,
                    "published_studies_count": 42,
                    "published_rct_count": 12,
                    "published_meta_review_count": 3,
                    "registry_completed_trials_count": 18,
                    "primary_outcome": "Immune Support",
                    "effect_direction_rationale": "Three meta-analyses and multiple human RCTs support benefit.",
                    "effect_direction_confidence": "high",
                    "endpoint_relevance_tags": ["immune_support", "fatigue"],
                }
            ]
        }

        product = {
            "activeIngredients": [
                {"name": "Test Ingredient", "standardName": "Test Ingredient", "quantity": 600, "unit": "mg"}
            ]
        }

        result = enricher._collect_evidence_data(product)
        assert result["match_count"] == 1
        match = result["clinical_matches"][0]
        assert match["min_clinical_dose"] == 500
        assert match["dose_unit"] == "mg"
        assert match["typical_effective_dose"] == "500-1000 mg/day"
        assert match["dose_range"]["max"] == 1000
        assert match["base_points"] == 4
        assert match["multiplier"] == 0.65
        assert match["computed_score"] == 2.6
        assert match["published_studies_count"] == 42
        assert match["published_rct_count"] == 12
        assert match["published_meta_review_count"] == 3
        assert match["registry_completed_trials_count"] == 18
        assert match["primary_outcome"] == "Immune Support"
        assert match["effect_direction_rationale"].startswith("Three meta-analyses")
        assert match["effect_direction_confidence"] == "high"
        assert match["endpoint_relevance_tags"] == ["immune_support", "fatigue"]

    def test_enrichment_respects_exclude_aliases(self, enricher):
        enricher.databases["backed_clinical_studies"] = {
            "backed_clinical_studies": [
                {
                    "id": "INGR_MAGNESIUM_GENERIC",
                    "standard_name": "Magnesium (Generic)",
                    "aliases": ["magnesium"],
                    "aliases_normalized": ["magnesium"],
                    "exclude_aliases": ["magnesium stearate"],
                    "evidence_level": "ingredient-human",
                    "study_type": "rct_single",
                }
            ]
        }

        product = {
            "activeIngredients": [
                {"name": "Magnesium Stearate", "standardName": "Magnesium"}
            ]
        }

        result = enricher._collect_evidence_data(product)
        assert result["match_count"] == 0
        assert result["clinical_matches"] == []

    def test_scorer_uses_optional_base_points_and_multiplier(self, scorer):
        scorer.config.setdefault("section_C_evidence_research", {})
        scorer.config["section_C_evidence_research"]["cap_per_ingredient"] = 10
        scorer.config["section_C_evidence_research"]["cap_total"] = 20

        product = {
            "activeIngredients": [{"name": "Test", "quantity": 1, "unit": "mg"}],
            "evidence_data": {
                "clinical_matches": [
                    {
                        "id": "E_TEST",
                        "standard_name": "Test",
                        "study_type": "rct_single",
                        "evidence_level": "ingredient-human",
                        "base_points": 7.0,
                        "multiplier": 1.0,
                    }
                ]
            },
        }
        section_c = scorer._score_section_c(product, [])
        assert section_c["score"] == pytest.approx(7.0)
        assert section_c["max"] == pytest.approx(20.0)

    def test_scorer_depth_bonus_uses_published_studies_count(self, scorer):
        product = {
            "activeIngredients": [{"name": "Test", "quantity": 1, "unit": "mg"}],
            "evidence_data": {
                "clinical_matches": [
                    {
                        "id": "E_TEST",
                        "standard_name": "Test",
                        "study_type": "rct_single",
                        "evidence_level": "ingredient-human",
                        "published_studies": ["RCT", "meta-analysis"],
                        "published_studies_count": 68,
                    }
                ]
            },
        }
        section_c = scorer._score_section_c(product, [])
        assert section_c["depth_bonus"] == pytest.approx(0.5)
        assert section_c["score"] == pytest.approx(3.1, abs=0.01)


class TestAuditRegressionData:
    def _clinical_entry(self, entry_id: str):
        data = json.loads((DATA_DIR / "backed_clinical_studies.json").read_text())
        for entry in data["backed_clinical_studies"]:
            if entry.get("id") == entry_id:
                return entry
        raise AssertionError(f"Clinical entry not found: {entry_id}")

    def test_clinical_entries_match_their_own_evidence_notes(self):
        apigenin = self._clinical_entry("PRECLIN_APIGENIN")
        assert apigenin["evidence_level"] == "preclinical"
        assert apigenin["study_type"] == "in_vitro"

        luteolin = self._clinical_entry("PRECLIN_LUTEOLIN")
        assert luteolin["evidence_level"] == "preclinical"
        assert luteolin["study_type"] == "animal_study"

        zylofresh = self._clinical_entry("BRAND_ZYLOFRESH")
        assert "RCT" not in zylofresh.get("published_studies", [])

        spermidine = self._clinical_entry("PRECLIN_SPERMIDINE")
        assert "RCT" in spermidine.get("published_studies", [])

        iodine = self._clinical_entry("INGR_IODINE")
        assert "RCT" in iodine.get("published_studies", [])
        assert iodine["study_type"] == "rct_multiple"

    def test_clinical_db_schema_version_is_current_for_new_fields(self):
        data = json.loads((DATA_DIR / "backed_clinical_studies.json").read_text())
        assert data["_metadata"]["schema_version"] == "5.3.0"

    def test_numeric_study_count_uses_dedicated_field(self):
        data = json.loads((DATA_DIR / "backed_clinical_studies.json").read_text())
        entries = data["backed_clinical_studies"]

        assert all(not isinstance(entry.get("published_studies"), int) for entry in entries)

        numeric_count_entries = [entry for entry in entries if entry.get("published_studies_count") is not None]
        assert numeric_count_entries, "Expected at least one clinical entry with published_studies_count"
        assert all(isinstance(entry["published_studies_count"], int) for entry in numeric_count_entries)

    def test_curcumin_clinical_notes_do_not_preserve_debunked_bioavailability_claims(self):
        longvida = self._clinical_entry("BRAND_LONGVIDA")
        assert "65x" not in longvida.get("notable_studies", "")

        bioperine = self._clinical_entry("BRAND_BIOPERINE")
        assert "Verhoeven 2025" in bioperine.get("notable_studies", "")

    def test_priority_audit_cleanup_entries_hold_current_classification(self):
        data = json.loads((DATA_DIR / "backed_clinical_studies.json").read_text())
        entries = {entry["id"]: entry for entry in data["backed_clinical_studies"]}

        assert entries["PRECLIN_AKG"]["evidence_level"] == "preclinical"
        assert "placebo-controlled" not in entries["PRECLIN_AKG"]["notes"].lower()
        assert "randomized" not in entries["PRECLIN_AKG"]["notable_studies"].lower()

        assert entries["PRECLIN_APIGENIN"]["evidence_level"] == "preclinical"
        assert "rct" not in entries["PRECLIN_APIGENIN"]["notable_studies"].lower()
        assert entries["PRECLIN_APIGENIN"]["registry_completed_trials_count"] == 10

        assert entries["PRECLIN_LUTEOLIN"]["evidence_level"] == "preclinical"
        assert "22492777" not in json.dumps(entries["PRECLIN_LUTEOLIN"])
        assert entries["PRECLIN_LUTEOLIN"]["registry_completed_trials_count"] == 10

        assert entries["INGR_BLACK_COHOSH"]["effect_direction"] == "mixed"

    def test_clinical_risk_taxonomy_metadata_count_matches_arrays(self):
        data = json.loads((DATA_DIR / "clinical_risk_taxonomy.json").read_text())
        total = sum(len(value) for value in data.values() if isinstance(value, list))
        assert data["_metadata"]["total_entries"] == total

    def test_engineered_curcumin_forms_are_not_marked_natural(self):
        iqm = json.loads((DATA_DIR / "ingredient_quality_map.json").read_text())
        forms = iqm["curcumin"]["forms"]
        for form_id in [
            "meriva curcumin",
            "theracurmin",
            "bcm-95 curcumin",
            "curcuwin",
            "hydrocurc",
            "longvida curcumin",
        ]:
            assert forms[form_id]["natural"] is False

    def test_batch1_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_MITOQ",
            "BRAND_SETRIA",
            "BRAND_UCII",
            "BRAND_NIAGEN",
            "BRAND_MENAQ7",
            "BRAND_AFFRON",
            "BRAND_EGB761",
            "BRAND_MITOPURE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch2_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_MEGASPORE_BIOTIC",
            "BRAND_ESTERC",
            "BRAND_OPTIFERRIN",
            "BRAND_CIRCADIN",
            "BRAND_CARNIPURE",
            "BRAND_PHOSPHATIDYLSERINE",
            "BRAND_MEDIHERB_SILYMARIN",
            "INGR_BETA_ALANINE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch3_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_KANEKA_UBIQUINOL",
            "BRAND_QUATREFOLIC",
            "BRAND_SEAKELP",
            "BRAND_COGNIZIN",
            "BRAND_SUNTHEANINE",
            "BRAND_LACTOSPORE",
            "BRAND_OPTISHARP",
            "BRAND_WELLMUNE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch4_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_PYCNOGENOL",
            "BRAND_FLORASTOR",
            "BRAND_ASTAREAL",
            "BRAND_OPTIMSM",
            "BRAND_AQUAMIN",
            "BRAND_CURCUMIN_C3",
            "BRAND_BIOCELL",
            "BRAND_RELORA",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch5_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_MERIVA",
            "BRAND_KSM66",
            "BRAND_SENSORIL",
            "BRAND_BCM95",
            "BRAND_THERACURMIN",
            "BRAND_FORCEVAL",
            "BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN",
            "BRAND_ZYLOFRESH",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch6_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_CREAPURE",
            "BRAND_ALBION_MINERALS",
            "BRAND_NITROSIGINE",
            "BRAND_LJ100",
            "BRAND_SHODEN",
            "BRAND_TESTOFEN",
            "BRAND_MAGTEIN",
            "BRAND_SUNFIBER",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch7_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "BRAND_CYNATINE_HNS",
            "BRAND_TAMAFLEX",
            "BRAND_HMB",
            "BRAND_ZYNAMITE",
            "BRAND_HEAL9",
            "BRAND_LUTEMAX_2020",
            "BRAND_PRIMAVIE_SHILAJIT",
            "BRAND_PUREWAY_C",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch8_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_L_CITRULLINE",
            "INGR_COLLAGEN_PEPTIDES",
            "INGR_HYALURONIC_ACID",
            "INGR_GARLIC",
            "INGR_VITAMIN_K2",
            "INGR_SELENIUM",
            "INGR_SAME",
            "INGR_CAFFEINE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch9_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_BERBERINE_HCL",
            "INGR_RHODIOLA_3_SALIDROSIDE",
            "INGR_MAG_GLYCINATE",
            "INGR_NAC",
            "INGR_QUERCETIN",
            "INGR_L_THEANINE",
            "INGR_BACOPA",
            "INGR_COQ10",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch10_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_ZINC_PICOLINATE",
            "INGR_LUTEIN",
            "INGR_BIOTIN",
            "INGR_MELATONIN",
            "INGR_GINSENG",
            "INGR_RHODIOLA",
            "INGR_VITAMIN_B12",
            "INGR_PROBIOTICS",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch11_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_TURMERIC",
            "INGR_VITAMIN_C",
            "INGR_GINGER",
            "INGR_ASHWAGANDHA",
            "INGR_GREEN_TEA",
            "INGR_LION_MANE",
            "INGR_GLYCINE",
            "INGR_TART_CHERRY",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch12_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_ELDERBERRY",
            "INGR_FENUGREEK",
            "INGR_BITTER_MELON",
            "INGR_ALPHA_LIPOIC_ACID",
            "INGR_RED_YEAST_RICE",
            "INGR_GLUCOSAMINE_SULFATE",
            "INGR_CINNAMON_EXTRACT",
            "INGR_DIGESTIVE_ENZYMES",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch13_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_INULIN",
            "INGR_IRON_BISGLYCINATE",
            "INGR_FOLATE_MTHF",
            "INGR_VALERIAN",
            "INGR_PASSIONFLOWER",
            "INGR_LEMON_BALM",
            "STRAIN_REUTERI_PRODENTIS",
            "INGR_VITAMIN_A_BETA_CAROTENE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch14_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "PRECLIN_FISETIN",
            "PRECLIN_AKG",
            "PRECLIN_QUERCETIN_PHYTOSOME",
            "PRECLIN_NADH",
            "PRECLIN_ASTAXANTHIN_GENERIC",
            "PRECLIN_SULFORAPHANE",
            "PRECLIN_PTEROSTILBENE",
            "PRECLIN_ARTICHOKE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch15_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "PRECLIN_DGL",
            "PRECLIN_ZINC_CARNOSINE",
            "PRECLIN_BOSWELLIA",
            "PRECLIN_HUPERZINE_A",
            "PRECLIN_CORDYCEPS",
            "PRECLIN_BETAINE_HCL",
            "PRECLIN_SAFFRON",
            "PRECLIN_CHROMIUM_PICOLINATE",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_chromium_picolinate_uses_compound_unii_not_elemental_chromium(self):
        entry = self._clinical_entry("PRECLIN_CHROMIUM_PICOLINATE")

        assert entry["external_ids"]["unii"] == "S71T8B8Z6P"

    def test_s_boulardii_clinical_entry_does_not_borrow_generic_brewers_yeast_unii(self):
        entry = self._clinical_entry("STRAIN_SBOULARDII")

        assert (entry.get("external_ids") or {}).get("unii") in (None, "")

    def test_florastor_brand_entry_does_not_borrow_generic_brewers_yeast_unii(self):
        entry = self._clinical_entry("BRAND_FLORASTOR")

        assert (entry.get("external_ids") or {}).get("unii") in (None, "")

    def test_batch16_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "PRECLIN_NMN",
            "PRECLIN_PQQ",
            "PRECLIN_RESVERATROL",
            "PRECLIN_CURCUMIN_GENERIC",
            "PRECLIN_BERBERINE_GENERIC",
            "INGR_MAGNESIUM_GENERIC",
            "INGR_VITAMIN_B6",
            "INGR_THIAMINE_B1",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id

    def test_batch17_human_evidence_entries_include_explicit_source_breadcrumbs(self):
        explicit_markers = ("PMID", "NIH ODS", "NCCIH", "PubMed", "FDA", "LiverTox", "EFSA", "ClinicalTrials.gov")
        for entry_id in [
            "INGR_PANTOTHENIC_ACID_B5",
            "INGR_RIBOFLAVIN_B2",
            "INGR_POTASSIUM",
            "INGR_MANGANESE",
            "INGR_PHOSPHORUS",
            "INGR_BORON",
            "INGR_HONEY",
            "PRECLIN_DIM",
            "PRECLIN_SHILAJIT_GENERIC",
        ]:
            entry = self._clinical_entry(entry_id)
            combined = f"{entry.get('notes', '')} {entry.get('notable_studies', '')}"
            assert any(marker in combined for marker in explicit_markers), entry_id
