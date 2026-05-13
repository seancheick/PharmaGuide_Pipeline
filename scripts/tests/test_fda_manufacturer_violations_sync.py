#!/usr/bin/env python3
"""Tests for FDA manufacturer violations sync."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api_audit.fda_manufacturer_violations_sync as sync


def test_default_paths_point_to_real_scripts_locations():
    repo_root = Path(__file__).resolve().parents[2]

    assert sync.DATA_PATH == repo_root / "scripts" / "data" / "manufacturer_violations.json"
    assert sync.DEDUCTION_EXPL_PATH == repo_root / "scripts" / "data" / "manufacture_deduction_expl.json"
    assert sync.REPORT_DIR == repo_root / "scripts" / "api_audit" / "reports"


def test_extract_manufacturer_from_title_and_reason_handles_rss_recall_entities():
    title_record = {
        "title": "Aphreseller (Buy-herbal.com) Issues Voluntary Nationwide Recall of Kian Pee Wan Capsules",
    }
    reason_record = {
        "reason_for_recall": (
            "FOR IMMEDIATE RELEASE - 03/30/2026 - Flushing, New York, "
            "Aphreseller (Ebay seller ID), Buy-herbal.com is recalling all lots of Kian Pee Wan capsules."
        )
    }

    assert sync.extract_manufacturer_from_text(title_record) == "Aphreseller (Buy-herbal.com)"
    assert sync.extract_manufacturer_from_text(reason_record) == "Buy-herbal.com"


def test_dry_run_reads_output_file_and_dedupes_same_run_recall_ids(monkeypatch, tmp_path):
    data_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    data_path.write_text(
        json.dumps(
            {
                "_metadata": {"total_entries": 1, "statistics": {}},
                "manufacturer_violations": [
                    {
                        "id": "V010",
                        "manufacturer": "Existing Co",
                        "fda_recall_id": "RCL-EXISTING",
                        "severity_level": "high",
                        "is_resolved": False,
                    }
                ],
            }
        )
    )

    records = [
        {
            "recall_number": "RCL-EXISTING",
            "recalling_firm": "Existing Co",
            "product_description": "Existing supplement",
            "reason_for_recall": "undeclared sildenafil",
            "classification": "Class I",
            "status": "open",
            "recall_initiation_date": "20260401",
        },
        {
            "recall_number": "RCL-NEW",
            "recalling_firm": "New Co",
            "product_description": "New supplement",
            "reason_for_recall": "undeclared sildenafil",
            "classification": "Class I",
            "status": "open",
            "recall_initiation_date": "20260401",
        },
        {
            "recall_number": "RCL-NEW",
            "recalling_firm": "New Co",
            "product_description": "Duplicate same-run supplement",
            "reason_for_recall": "undeclared sildenafil",
            "classification": "Class I",
            "status": "open",
            "recall_initiation_date": "20260401",
        },
    ]

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: records if args[0] == "food/enforcement" else [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "classify_record", lambda record: (True, "supplement", 1.0))
    monkeypatch.setattr(sync, "is_noise", lambda record: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(data_path),
            "--report",
            str(report_path),
            "--dry-run",
        ],
    )

    assert sync.main() == 0

    report = json.loads(report_path.read_text())
    assert report["data_file"] == str(data_path)
    assert report["existing_total"] == 1
    assert report["added_count"] == 1
    assert report["added_ids"] == ["V011"]
    assert report["skip_reasons"]["existing_recall_id"] == 1
    assert report["skip_reasons"]["batch_duplicate_recall_id"] == 1


def test_persist_mode_creates_parent_dirs_and_counts_severity_stats(monkeypatch, tmp_path):
    output_path = tmp_path / "nested" / "manufacturer_violations.json"
    report_path = tmp_path / "reports" / "sync_report.json"

    records = [
        {
            "recall_number": "RCL-CRIT",
            "recalling_firm": "Critical Co",
            "product_description": "Critical supplement",
            "reason_for_recall": "undeclared sildenafil",
            "classification": "Class I",
            "status": "open",
            "recall_initiation_date": "20260401",
        },
        {
            "recall_number": "RCL-HIGH",
            "recalling_firm": "High Co",
            "product_description": "High supplement",
            "reason_for_recall": "cGMP problems",
            "classification": "Class II",
            "status": "open",
            "recall_initiation_date": "20260401",
        },
    ]

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: records if args[0] == "food/enforcement" else [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "classify_record", lambda record: (True, "supplement", 1.0))
    monkeypatch.setattr(sync, "is_noise", lambda record: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ],
    )

    assert sync.main() == 0

    written = json.loads(output_path.read_text())
    stats = written["_metadata"]["statistics"]
    assert stats["critical_violations"] == 1
    assert stats["high_violations"] == 1
    assert stats["moderate_violations"] == 0
    assert stats["low_violations"] == 0
    assert written["_metadata"]["total_entries"] == 2


def test_persist_mode_recalculates_existing_entry_fields(monkeypatch, tmp_path):
    output_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    output_path.write_text(
        json.dumps(
            {
                "_metadata": {"total_entries": 2, "statistics": {}},
                "manufacturer_violations": [
                    {
                        "id": "V001",
                        "manufacturer": "Repeat Co",
                        "manufacturer_id": "mfg_repeat_co",
                        "product": "Legacy product A",
                        "reason": "undeclared sildenafil",
                        "violation_type": "Class I",
                        "fda_recall_id": "OLD-1",
                        "date": "2025-04-01",
                        "days_since_violation": 1,
                        "recency_multiplier": 0.0,
                        "base_deduction": -1,
                        "severity_level": "low",
                        "product_lines_affected": 3,
                        "multiple_product_lines": False,
                        "repeat_violation": False,
                        "is_resolved": False,
                        "total_deduction_applied": -1.0,
                        "source_type": "openfda_enforcement",
                        "fda_source_url": "",
                    },
                    {
                        "id": "V002",
                        "manufacturer": "Repeat Co",
                        "manufacturer_id": "mfg_repeat_co",
                        "product": "Legacy product B",
                        "reason": "undeclared sildenafil",
                        "violation_type": "Class I",
                        "fda_recall_id": "OLD-2",
                        "date": "2024-12-01",
                        "days_since_violation": 1,
                        "recency_multiplier": 0.0,
                        "base_deduction": -1,
                        "severity_level": "low",
                        "product_lines_affected": 1,
                        "multiple_product_lines": False,
                        "repeat_violation": False,
                        "is_resolved": False,
                        "total_deduction_applied": -1.0,
                        "source_type": "openfda_enforcement",
                        "fda_source_url": "",
                    },
                ],
            }
        )
    )

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ],
    )

    assert sync.main() == 0

    written = json.loads(output_path.read_text())
    first, second = written["manufacturer_violations"]
    assert first["manufacturer_id"] == "mfg_repeat_co"
    assert first["base_deduction"] == -15
    assert first["severity_level"] == "critical"
    assert first["multiple_product_lines"] is True
    assert first["repeat_violation"] is True
    assert first["recency_multiplier"] in {1.0, 0.5}
    assert first["total_deduction_applied"] == -13.0
    assert second["repeat_violation"] is True

    report = json.loads(report_path.read_text())
    assert report["recalculated_entry_count"] >= 2
    assert report["statistics"]["repeat_offenders"] == 1


def test_statistics_recompute_active_outbreaks_from_rows(monkeypatch, tmp_path):
    output_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    output_path.write_text(
        json.dumps(
            {
                "_metadata": {"total_entries": 1, "statistics": {}},
                "manufacturer_violations": [
                    {
                        "id": "V001",
                        "manufacturer": "Outbreak Co",
                        "manufacturer_id": "mfg_outbreak",
                        "product": "Outbreak greens",
                        "reason": "salmonella contamination",
                        "violation_type": "Class I",
                        "fda_recall_id": "OLD-1",
                        "date": "2026-01-01",
                        "severity_level": "critical",
                        "base_deduction": -15,
                        "is_resolved": False,
                        "repeat_violation": False,
                        "multiple_product_lines": False,
                        "product_lines_affected": 1,
                        "total_deduction_applied": -15.0,
                        "source_type": "openfda_enforcement",
                        "fda_source_url": "",
                        "cdc_outbreak_investigation": True,
                    }
                ],
            }
        )
    )

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ],
    )

    assert sync.main() == 0
    report = json.loads(report_path.read_text())
    assert report["statistics"]["active_outbreaks"] == 1


def test_repeat_violation_prefers_curated_manufacturer_family_id(monkeypatch, tmp_path):
    output_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    output_path.write_text(
        json.dumps(
            {
                "_metadata": {"total_entries": 2, "statistics": {}},
                "manufacturer_violations": [
                    {
                        "id": "V001",
                        "manufacturer": "Volt Candy",
                        "manufacturer_id": "mfg_voltcandy",
                        "manufacturer_family_id": "fam_rhino",
                        "product": "Rhino product A",
                        "reason": "undeclared sildenafil",
                        "violation_type": "Class I",
                        "fda_recall_id": "OLD-1",
                        "date": "2025-06-01",
                        "severity_level": "critical",
                        "base_deduction": -15,
                        "is_resolved": False,
                        "repeat_violation": False,
                        "multiple_product_lines": False,
                        "product_lines_affected": 1,
                        "total_deduction_applied": -15.0,
                        "source_type": "openfda_enforcement",
                        "fda_source_url": "",
                    },
                    {
                        "id": "V002",
                        "manufacturer": "Gear Isle",
                        "manufacturer_id": "mfg_gearisle",
                        "manufacturer_family_id": "fam_rhino",
                        "product": "Rhino product B",
                        "reason": "undeclared tadalafil",
                        "violation_type": "Class I",
                        "fda_recall_id": "OLD-2",
                        "date": "2025-08-01",
                        "severity_level": "critical",
                        "base_deduction": -15,
                        "is_resolved": False,
                        "repeat_violation": False,
                        "multiple_product_lines": False,
                        "product_lines_affected": 1,
                        "total_deduction_applied": -15.0,
                        "source_type": "openfda_enforcement",
                        "fda_source_url": "",
                    },
                ],
            }
        )
    )

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ],
    )

    assert sync.main() == 0

    written = json.loads(output_path.read_text())
    for row in written["manufacturer_violations"]:
        assert row["repeat_violation"] is True
        assert row["manufacturer_family_id"] == "fam_rhino"

    report = json.loads(report_path.read_text())
    assert report["statistics"]["repeat_offenders"] == 1


def test_dry_run_dedupes_blank_recall_id_records_by_source_fingerprint(monkeypatch, tmp_path):
    data_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    data_path.write_text(json.dumps({"_metadata": {}, "manufacturer_violations": []}))

    rss_item = {
        "title": "FDA warns consumers not to use Example Herb capsules",
        "description": "Example Herb capsules may contain undeclared sildenafil.",
        "link": "https://example.test/fda-alert-1",
        "product_description": "Example Herb capsules",
        "reason_for_recall": "Example Herb capsules may contain undeclared sildenafil.",
        "classification": "Recall",
        "status": "Ongoing",
        "report_date": "2026-04-02",
        "_source_type": "fda_rss",
    }

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [dict(rss_item), dict(rss_item)])
    monkeypatch.setattr(sync, "classify_record", lambda record: (True, "supplement", 1.0))
    monkeypatch.setattr(sync, "is_noise", lambda record: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(data_path),
            "--report",
            str(report_path),
            "--include-rss",
            "--dry-run",
        ],
    )

    assert sync.main() == 0
    report = json.loads(report_path.read_text())
    assert report["added_count"] == 1
    assert report["skip_reasons"]["batch_duplicate_source"] == 3


def test_repeat_violation_uses_existing_manufacturer_history(monkeypatch, tmp_path):
    data_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    data_path.write_text(
        json.dumps(
            {
                "_metadata": {"total_entries": 1, "statistics": {}},
                "manufacturer_violations": [
                    {
                        "id": "V010",
                        "manufacturer": "Herbal Doctor Remedies",
                        "manufacturer_id": "herbaldoctorremedies",
                        "fda_recall_id": "",
                        "severity_level": "high",
                        "is_resolved": False,
                    }
                ],
            }
        )
    )

    records = [
        {
            "recall_number": "RCL-NEW-2",
            "recalling_firm": "Herbal Doctor Remedies",
            "product_description": "Another supplement",
            "reason_for_recall": "undeclared sildenafil",
            "classification": "Class I",
            "status": "open",
            "recall_initiation_date": "20260401",
        }
    ]

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: records if args[0] == "food/enforcement" else [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "classify_record", lambda record: (True, "supplement", 1.0))
    monkeypatch.setattr(sync, "is_noise", lambda record: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(data_path),
            "--report",
            str(report_path),
            "--dry-run",
        ],
    )

    assert sync.main() == 0
    report = json.loads(report_path.read_text())
    assert report["added_count"] == 1
    assert report["new_entries"][0]["repeat_violation"] is True


def test_dry_run_filters_generic_rss_drug_alert_without_strong_supplement_signal(monkeypatch, tmp_path):
    data_path = tmp_path / "manufacturer_violations.json"
    report_path = tmp_path / "report.json"
    data_path.write_text(json.dumps({"_metadata": {}, "manufacturer_violations": []}))

    rss_items = [
        {
            "title": "FDA advises patients not to use Herbal Doctor Remedies medicines",
            "description": "FDA advises patients not to use any drugs manufactured by Herbal Doctor Remedies because these drugs were made under poor conditions.",
            "product_description": "",
            "reason_for_recall": "FDA advises patients not to use any drugs manufactured by Herbal Doctor Remedies because these drugs were made under poor conditions.",
            "link": "https://example.test/herbal-doctor-remedies",
            "classification": "Recall",
            "status": "Ongoing",
            "report_date": "2026-04-02",
            "_source_type": "fda_rss",
        },
        {
            "title": "Aphreseller issues recall of Kian Pee Wan capsules",
            "description": "Kian Pee Wan capsules may contain undeclared dexamethasone and cyproheptadine.",
            "product_description": "Kian Pee Wan capsules",
            "reason_for_recall": "Presence of undeclared dexamethasone and cyproheptadine in Kian Pee Wan capsules.",
            "link": "https://example.test/kian-pee-wan",
            "classification": "Recall",
            "status": "Ongoing",
            "report_date": "2026-04-02",
            "_source_type": "fda_rss",
        },
    ]

    def fake_classify(record):
        title = (record.get("title") or "").lower()
        if "herbal doctor remedies" in title:
            return True, "supplement_general", []
        return True, "supplement_adulterant", ["supplement_adulterant"]

    monkeypatch.setattr(sync, "fetch_enforcement", lambda *args, **kwargs: [])
    monkeypatch.setattr(sync, "fetch_fda_rss", lambda *args, **kwargs: list(rss_items))
    monkeypatch.setattr(sync, "classify_record", fake_classify)
    monkeypatch.setattr(sync, "is_noise", lambda record: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fda_manufacturer_violations_sync.py",
            "--output",
            str(data_path),
            "--report",
            str(report_path),
            "--include-rss",
            "--dry-run",
        ],
    )

    assert sync.main() == 0
    report = json.loads(report_path.read_text())
    assert report["added_count"] == 1
    assert report["skip_reasons"]["weak_rss_signal"] == 2
    assert report["skip_reasons"]["batch_duplicate_source"] == 1
    assert report["new_entries"][0]["product"] == "Kian Pee Wan capsules"


# ---------------------------------------------------------------------------
# Filter tightening regression tests (2026-05-13)
#
# These pin the false-positive cases that the 90-day dry-run surfaced before
# the hard_reject / pharmaceutical_only_form layers landed. Each test feeds
# is_eligible_manufacturer_record() a real FDA recall record and asserts that
# the record is rejected for the right reason. Without these tests, anyone
# loosening the filter would silently re-admit pharmaceutical / cosmetic /
# food false positives into the manufacturer trust DB.
# ---------------------------------------------------------------------------


def _eligibility(product: str, reason: str = "", product_type: str = "Drug",
                 source_type: str = "fda_enforcement") -> tuple[bool, str]:
    return sync.is_eligible_manufacturer_record({
        "product_type": product_type,
        "product_description": product,
        "reason_for_recall": reason,
        "_source_type": source_type,
    })


def test_filter_rejects_rx_only_prazosin_capsules():
    """V014 — Prazosin Hydrochloride Capsules USP Rx Only. "drug substance"
    in reason mis-fires supplement_adulterant; hard_reject must catch it
    via "rx only" before override is consulted."""
    eligible, reason = _eligibility(
        "Prazosin Hydrochloride Capsules, USP, 1mg, 100-count bottle, Rx Only",
        "cGMP deviation: detection of Nitrosamine Drug Substance-Related Impurities",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_fentanyl_injectable_solution():
    """V016 — fentaNYL Citrate Injectable Solution. Injection + narcotic =
    unambiguous Rx; never a dietary supplement adulterant."""
    eligible, reason = _eligibility(
        "fentaNYL Citrate Injectable Solution in 0.9% Sodium Chloride, 1000 mcg/50mL",
        "CGMP deviations",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_oxycodone_tablets_cii():
    """V015 — Oxycodone Hydrochloride Tablets CII. Schedule II controlled
    substance; never legitimately a supplement."""
    eligible, reason = _eligibility(
        "Oxycodone Hydrochloride Tablets, USP (CII), 5 mg, 100-Count blister",
        "CGMP deviations",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_thea_pharma_sterile_lubricant_eye_drops():
    """V014/V015 from earlier dry-run — Similasan iVIZIA Sterile Lubricant
    Eye Drops. Ophthalmic-only product; never a supplement."""
    eligible, reason = _eligibility(
        "Similasan, iVIZIA, Sterile Lubricant Eye Drops (Povidone 0.5%), 0.33 Fl oz",
        "CGMP deviations",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_dadi_dried_chilli_vegetable():
    """V083 from earlier dry-run — DADI NONGFU DRIED SALT CHILLI VEGETABLE.
    Conventional food; never a dietary supplement (caught earlier by
    classify_record returning False; this test pins the regression)."""
    eligible, reason = _eligibility(
        "DADI NONGFU DRIED SALT CHILLI VEGETABLE(S); Ingredients: Radish, chili, roasted sesame",
        "Products contain banned sweetener: cyclamates.",
        product_type="Food",
    )
    assert not eligible
    # Either not_supplement (classify_record rejects) or pure_food (filter rejects).
    assert reason in ("not_supplement",) or reason.startswith("pure_food") or reason.startswith("hard_reject")


def test_filter_rejects_acme_antimicrobial_alcohol_hand_wipe():
    """V030 from earlier dry-run — Antimicrobial Alcohol Hand Wipe. OTC
    topical antiseptic; not a dietary supplement."""
    eligible, reason = _eligibility(
        "Antimicrobial Alcohol Hand Wipe, Isopropyl Alcohol 70%",
        "CGMP Deviations",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_avantor_magnesium_chloride_bulk_api():
    """V034 from earlier dry-run — Magnesium Chloride, Bulk active
    pharmaceutical ingredient (API). Bulk pharma API; the supplement_adulterant
    signal misfires on "active pharmaceutical ingredient" in product
    description, but hard_reject catches "bulk active pharmaceutical" first."""
    eligible, reason = _eligibility(
        "Magnesium Chloride, 6-Hydrate, Crystal, 500G per bottle, Bulk active pharmaceutical ingredient",
        "Subpotent drug",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_hydropeptide_benzoyl_peroxide_serum():
    """V036 from earlier dry-run — HydroPeptide BENZOYL PEROXIDE Serum.
    OTC topical acne cosmetic; "peptide" in brand name accidentally matches
    supplement_terms, but hard_reject catches "benzoyl peroxide" first."""
    eligible, reason = _eligibility(
        "HydroPeptide CLEAR ALLIANCE SERUM, 2.5% BENZOYL PEROXIDE, 1 FL OZ/30ml",
        "Chemical contamination: Presence of benzene",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_rejects_asteria_testosterone_sterile_pellet():
    """V012-and-friends from earlier dry-run — Asteria Health Testosterone
    Sterile Pellet. Compounded HRT pharmaceutical; not a supplement (even
    though testosterone overlaps with anabolic-steroid supplement adulterants,
    sterile pellets are exclusively pharmaceutical compounding)."""
    eligible, reason = _eligibility(
        "Testosterone, 100 mg, 1 Sterile Pellet, Asteria Health 432 Industrial Ln",
        "Compounded drug subpotency",
    )
    assert not eligible
    assert reason.startswith("hard_reject")


def test_filter_keeps_pure_vitamins_sildenafil_spiked_male_enhancement():
    """V005 from dry-run — Blue Bull Extreme Male Enhancement spiked with
    sildenafil. THE canonical supplement-relevance case; must NOT be rejected."""
    eligible, reason = _eligibility(
        "Blue Bull Extreme Male Enhancement Supplement, total of 15 pouches per box",
        "FDA analysis revealed the presence of undeclared sildenafil",
    )
    assert eligible, f"rejected with reason={reason!r}"


def test_filter_keeps_aonic_complete_liquid_supplement_drink():
    """V001 from dry-run — Aonic Complete Hers liquid dietary supplement
    drink shot with microbial contamination. Must NOT be rejected — it is
    a labeled dietary supplement with a real contamination recall."""
    eligible, reason = _eligibility(
        "Aonic Complete Hers. Dosage: Single serving liquid dietary supplement drink shot, 34 ml",
        "Possible coliforms, E.coli, and/or Pseudomonas aeruginosa contamination.",
        product_type="Food",  # FDA food/enforcement endpoint
    )
    assert eligible, f"rejected with reason={reason!r}"


def test_filter_keeps_moringa_dietary_supplement_capsules():
    """V011 from dry-run — Rosabella MORINGA DIETARY SUPPLEMENT CAPSULES.
    Explicit "DIETARY SUPPLEMENT" labeling; must be kept."""
    eligible, reason = _eligibility(
        "Rosabella brand MORINGA; DIETARY SUPPLEMENT CAPSULES; 60 capsules per bottle",
        "Microbial contamination",
        product_type="Food",
    )
    assert eligible, f"rejected with reason={reason!r}"
