#!/usr/bin/env python3
"""Regression tests for FDA weekly sync relevance and extraction logic."""

import os
import subprocess
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


def test_run_fda_sync_is_report_only_and_reads_current_summary_key():
    runner = Path(__file__).resolve().parents[1] / "run_fda_sync.sh"
    content = runner.read_text()

    assert "requiring_claude_review" in content
    assert "new_substances_requiring_review" not in content
    assert "dangerously-skip-permissions" not in content
    assert "git add" not in content
    assert "git commit" not in content
    assert "REPORT-ONLY" in content


def test_run_fda_sync_rejects_unknown_arguments_before_network_access():
    runner = Path(__file__).resolve().parents[1] / "run_fda_sync.sh"

    result = subprocess.run(
        ["bash", str(runner), "--not-a-real-option"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Unknown option" in result.stderr


def test_fda_report_contract_uses_operator_neutral_review_language():
    script = Path(__file__).resolve().parents[1] / "api_audit" / "fda_weekly_sync.py"
    content = script.read_text()

    assert '"requiring_review"' in content
    assert '"review_instructions"' in content
    assert "Run /fda-weekly-sync in Claude Code" not in content


# ── FDA Medication Health Fraud notifications ────────────────────────────────
#
# These pages are the only source for undeclared-drug notifications (biQ-FEL,
# X10, ZUBB): they are not openFDA enforcement recalls and reach the RSS feeds
# only sporadically. The fixtures below are trimmed from the real index pages.

_SEXUAL_ENHANCEMENT_ROWS = (
    '<table><thead><tr><th>Date</th><th>Public Notification</th></tr></thead><tbody>'
    '<tr><td>5/29/2026</td><td><a href="/drugs/medication-health-fraud-notifications/'
    'x10-natural-enhancement-supplement-may-be-harmful-due-hidden-drug-ingredients" '
    'data-entity-type="node">X10 Natural Enhancement Supplement may be harmful due to '
    'hidden drug ingredients</a></td></tr>'
    '</tbody></table>'
)

# The weight-loss index renders the SAME data with the columns reversed.
_WEIGHT_LOSS_ROWS = (
    '<table><thead><tr><th>Public Notification</th><th>Date</th></tr></thead><tbody>'
    '<tr><td><a href="/drugs/medication-health-fraud-notifications/'
    'zubb-dietary-supplement-may-be-harmful-due-hidden-ingredient" '
    'data-entity-type="node">ZUBB Dietary Supplement may be harmful due to hidden '
    'ingredient</a></td><td>9/04/2026</td></tr>'
    '</tbody></table>'
)


def test_health_fraud_index_parses_both_column_orders():
    """The four index pages do not agree on column order; one rule must read all."""
    from api_audit.fda_weekly_sync import (
        _HEALTH_FRAUD_DATE_RE,
        _HEALTH_FRAUD_LINK_RE,
        _HEALTH_FRAUD_ROW_RE,
    )

    for markup, expected_slug, expected_date in (
        (_SEXUAL_ENHANCEMENT_ROWS, "x10-natural-enhancement", "5/29/2026"),
        (_WEIGHT_LOSS_ROWS, "zubb-dietary-supplement", "9/04/2026"),
    ):
        parsed = []
        for row in _HEALTH_FRAUD_ROW_RE.finditer(markup):
            link = _HEALTH_FRAUD_LINK_RE.search(row.group("row"))
            date = _HEALTH_FRAUD_DATE_RE.search(row.group("row"))
            if link and date:
                parsed.append((link.group("href"), date.group("date")))

        assert len(parsed) == 1, f"expected one data row, got {parsed}"
        href, date = parsed[0]
        assert expected_slug in href
        assert date == expected_date


def test_health_fraud_detail_anchor_tolerates_date_spacing():
    """Real advisories write both "[9-4-2026]" and "[ 8-18-2026]"."""
    from api_audit.fda_weekly_sync import _strip_html, advisory_body

    chrome = "Skip to main content " * 40
    for stamp in ("[9-4-2026]", "[ 8-18-2026]", "[ 8 - 18 - 2026 ]"):
        page = (
            f"<html><body><nav>{chrome}</nav><p>{stamp} The Food and Drug "
            "Administration is advising consumers not to purchase or use "
            "Example Product. FDA laboratory analysis confirmed that it "
            "contains sibutramine not listed on the product label.</p></body></html>"
        )
        body = advisory_body(_strip_html(page))
        assert "Skip to main content" not in body, f"chrome leaked for {stamp}"
        assert "sibutramine" in body


def test_health_fraud_detail_anchor_survives_a_missing_date_stamp():
    """No bracketed date must still yield prose, not 2000 characters of chrome."""
    from api_audit.fda_weekly_sync import _strip_html, advisory_body

    page = (
        "<html><body><nav>" + "Skip to main content " * 40 + "</nav>"
        "<p>The Food and Drug Administration is advising consumers not to use "
        "Example Product, which contains sildenafil not listed on the label.</p>"
        "</body></html>"
    )
    body = advisory_body(_strip_html(page))
    assert body.startswith("The Food and Drug Administration is advising")
    assert "sildenafil" in body


def test_health_fraud_records_are_relevant_without_supplement_keywords():
    """"biQ-FEL" contains no supplement keyword; keyword relevance would drop it."""
    record = {
        "product_description": "biQ-FEL may be harmful due to hidden drug ingredients",
        "reason_for_recall": (
            "FDA laboratory analysis confirmed that biQ-FEL contains sildenafil "
            "and tadalafil not listed on the product label."
        ),
        "title": "biQ-FEL may be harmful due to hidden drug ingredients",
        "description": "",
        "product_type": "Dietary Supplement",
        "_source_type": "fda_health_fraud",
    }

    is_relevant, primary_category, signals = classify_record(record)

    assert is_relevant
    assert primary_category == "illegal_spiking_agents"
    assert "pharmaceutical_adulterants" in signals
    assert set(extract_substances(record)) >= {"sildenafil", "tadalafil"}


def test_unknown_product_with_known_adulterant_still_enters_the_review_queue():
    """The core health-fraud case: the drug is always known, the product is not.

    MAXMAN Coffee was filed as informational because sildenafil and tadalafil
    were already in the substance registry, even though the product itself had
    never been seen. For this feed that is backwards — the news IS the product.
    """
    from api_audit.fda_weekly_sync import _classify_and_crossref

    record = {
        "title": "MAXMAN Coffee may be harmful due to hidden drug ingredients",
        "product_description": "MAXMAN Coffee may be harmful due to hidden drug ingredients",
        "reason_for_recall": (
            "FDA laboratory analysis confirmed that MAXMAN Coffee contains "
            "sildenafil and tadalafil not listed on the product label."
        ),
        "product_type": "Dietary Supplement",
        "_source_type": "fda_health_fraud",
        "_health_fraud_category": "sexual_enhancement",
        "link": "https://www.fda.gov/drugs/medication-health-fraud-notifications/maxman",
    }
    # Both adulterants already tracked; the product is not.
    index = {"sildenafil": {"id": "SPIKE_SILDENAFIL"},
             "tadalafil": {"id": "SPIKE_TADALAFIL"}}

    new_records, tracked_records, _, _ = _classify_and_crossref([record], index)

    assert len(new_records) == 1, "an unseen product must reach the review queue"
    assert not tracked_records
    entry = new_records[0]
    assert entry["product_name"] == "MAXMAN Coffee"
    assert entry["product_already_tracked"] is False
    # The adulterants are still correctly reported as already known.
    assert set(entry["substances_already_tracked"]) >= {"sildenafil", "tadalafil"}


def test_known_product_with_known_adulterant_stays_informational():
    """The other side of the split: nothing new, so nothing to action."""
    from api_audit.fda_weekly_sync import _classify_and_crossref

    record = {
        "title": "ZUBB Dietary Supplement may be harmful due to hidden ingredient",
        "product_description": "ZUBB Dietary Supplement may be harmful due to hidden ingredient",
        "reason_for_recall": (
            "FDA laboratory analysis confirmed that ZUBB Dietary Supplement "
            "contains sildenafil not listed on the product label."
        ),
        "product_type": "Dietary Supplement",
        "_source_type": "fda_health_fraud",
        "_health_fraud_category": "weight_loss",
        "link": "https://www.fda.gov/drugs/medication-health-fraud-notifications/zubb",
    }
    index = {"sildenafil": {"id": "SPIKE_SILDENAFIL"},
             "zubb dietary supplement": {"id": "RECALLED_ZUBB"}}

    new_records, tracked_records, _, _ = _classify_and_crossref([record], index)

    assert not new_records
    assert len(tracked_records) == 1
    assert tracked_records[0]["product_already_tracked"] is True
