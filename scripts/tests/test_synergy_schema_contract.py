#!/usr/bin/env python3
"""Targeted contract tests for synergy_cluster schema validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db_integrity_sanity_check import check_synergy_cluster


def _base_cluster():
    return {
        "id": "test_cluster",
        "standard_name": "Test Cluster",
        "ingredients": ["vitamin c", "zinc"],
        "min_effective_doses": {"vitamin c": 250, "zinc": 10},
        "evidence_tier": 1,
        "synergy_mechanism": "Test mechanism",
        "note": "Test note",
        "sources": [
            {
                "source_type": "nih_ods",
                "label": "Vitamin C Fact Sheet",
                "url": "https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/",
            }
        ],
    }


def test_synergy_rejects_query_placeholder_source_url():
    cluster = _base_cluster()
    cluster["sources"] = [
        {
            "source_type": "pubmed",
            "label": "Query placeholder",
            "url": "https://pubmed.ncbi.nlm.nih.gov/?term=vitamin+c+zinc+trial",
        }
    ]
    findings = []
    check_synergy_cluster(findings, {"synergy_clusters": [cluster]}, "synergy_cluster.json")

    assert any(f.issue == "query_placeholder_not_allowed" for f in findings)


def test_synergy_rejects_invalid_source_type():
    cluster = _base_cluster()
    cluster["sources"] = [
        {
            "source_type": "pubmed_query",
            "label": "Old style query source",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9619120/",
        }
    ]
    findings = []
    check_synergy_cluster(findings, {"synergy_clusters": [cluster]}, "synergy_cluster.json")

    assert any(
        f.issue == "invalid_enum" and f.path.endswith(".source_type")
        for f in findings
    )


def test_synergy_accepts_curated_source_types():
    cluster = _base_cluster()
    cluster["sources"] = [
        {
            "source_type": "pubmed",
            "label": "PubMed trial",
            "url": "https://pubmed.ncbi.nlm.nih.gov/9619120/",
        },
        {
            "source_type": "fda",
            "label": "FDA Q&A",
            "url": "https://www.fda.gov/food/information-consumers-using-dietary-supplements/questions-and-answers-dietary-supplements",
        },
        {
            "source_type": "nccih",
            "label": "NCCIH Probiotics",
            "url": "https://www.nccih.nih.gov/health/probiotics-usefulness-and-safety",
        },
        {
            "source_type": "nih_ods",
            "label": "NIH ODS Fact Sheet List",
            "url": "https://ods.od.nih.gov/factsheets/list-all/",
        },
    ]
    findings = []
    check_synergy_cluster(findings, {"synergy_clusters": [cluster]}, "synergy_cluster.json")

    assert findings == []
