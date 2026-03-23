#!/usr/bin/env python3
"""Regression tests for FDA weekly sync relevance and extraction logic."""

import os
import sys
import types
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

requests_stub = types.SimpleNamespace(
    Response=object,
    Timeout=type("Timeout", (Exception,), {}),
    ConnectionError=type("ConnectionError", (Exception,), {}),
    RequestException=type("RequestException", (Exception,), {}),
)
sys.modules.setdefault("requests", requests_stub)

from fda_weekly_sync import classify_record, extract_substances


def test_extract_substances_strips_undeclared_prefix():
    record = {
        "product_description": "MR. 7 SUPER 700000 capsule",
        "reason_for_recall": "The product was found to contain undeclared sildenafil and tadalafil.",
        "title": "",
        "description": "",
    }

    assert extract_substances(record) == ["sildenafil", "tadalafil"]


def test_classify_filters_conventional_food_false_positive():
    record = {
        "product_type": "Food",
        "product_description": "Mushroom, Spinach & Salsa Tamales with 2 Cheeses",
        "reason_for_recall": "Potential contamination with biological hazards (Listeria monocytogenes).",
        "title": "",
        "_source_type": "openfda_enforcement",
    }

    assert classify_record(record) == (False, "", [])


def test_classify_filters_device_rss_false_positive():
    record = {
        "product_type": "",
        "product_description": "Cardinal Health Issues Voluntary Nationwide Recall of Webcol Large Alcohol Prep Pad",
        "reason_for_recall": "The product is being recalled due to microbial contamination identified as Paenibacillus phoenicis.",
        "title": "Cardinal Health Issues Voluntary Nationwide Recall of Webcol Large Alcohol Prep Pad",
        "link": "https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/cardinal-health-webcol",
        "_source_type": "fda_rss",
    }

    assert classify_record(record) == (False, "", [])


def test_classify_filters_generic_rss_drug_safety_page():
    record = {
        "product_type": "",
        "product_description": "Drugs@FDA Data Files",
        "reason_for_recall": "Drugs@FDA Data Files",
        "title": "Drugs@FDA Data Files",
        "link": "https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files",
        "_source_type": "fda_rss",
    }

    assert classify_record(record) == (False, "", [])


def test_classify_keeps_tainted_supplement_with_food_like_branding():
    record = {
        "product_type": "Dietary Supplement",
        "product_description": "DTF Sexual Chocolate dietary supplement capsule",
        "reason_for_recall": "FDA analysis found undeclared sildenafil and tadalafil.",
        "title": "",
        "_source_type": "openfda_enforcement",
    }

    relevant, primary, detected = classify_record(record)

    assert relevant is True
    assert primary == "supplement_adulterant"
    assert "pharmaceutical_contaminant" in detected


def test_classify_keeps_tainted_supplement_juice_shot():
    record = {
        "product_type": "Dietary Supplement",
        "product_description": "Collagen juice shot",
        "reason_for_recall": "Contains undeclared tadalafil.",
        "title": "",
        "_source_type": "openfda_enforcement",
    }

    relevant, primary, detected = classify_record(record)

    assert relevant is True
    assert primary == "supplement_adulterant"
    assert "pharmaceutical_contaminant" in detected


def test_classify_filters_allergen_only_supplement_recall():
    record = {
        "product_type": "Food",
        "product_description": "Pure Factors Professional Nighttime Sleep Formula liquid dietary supplement",
        "reason_for_recall": "Label declares bovine colostrum but does not declare milk allergen.",
        "title": "",
        "_source_type": "openfda_enforcement",
    }

    assert classify_record(record) == (False, "", [])


def test_run_fda_sync_reads_current_summary_key():
    runner = Path(__file__).resolve().parents[1] / "run_fda_sync.sh"
    content = runner.read_text()

    assert "requiring_claude_review" in content
    assert "new_substances_requiring_review" not in content
