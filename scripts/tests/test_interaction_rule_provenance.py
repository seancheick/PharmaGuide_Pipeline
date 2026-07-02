#!/usr/bin/env python3
"""Regression guard: every interaction rule must carry at least one http(s)
provenance source somewhere (a condition_rule, drug_class_rule, or the
pregnancy_lactation block) — the same invariant db_integrity_sanity_check.py
enforces (missing_provenance_sources), pinned as a fast unit test.

Motivated by two orphan rules that carried only a pregnancy_lactation block with
no sources (RULE_INGREDIENT_ELDERBERRY__AUTOIMMUNE, RULE_IQM_PYGEUM_NSAIDS). The
provenance added for them is content-verified (fetched live, confirmed on-topic):
  - elderberry: PubMed 24624087 (elderberry-in-pregnancy review) + NBK501835
    (LactMed "Elderberry" lactation monograph)
  - pygeum: Health Canada NHPID "PYGEUM - PRUNUS AFRICANA" monograph
All three are absence-of-data / caution sources, matching the rules'
"limited safety data" framing (they must NOT be read as showing safety).

Hermetic: reads the shipped data file, no network.
"""
import json
from pathlib import Path

RULES = json.loads(
    (Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json").read_text()
)["interaction_rules"]


def _http_sources(rule):
    out = []
    buckets = list(rule.get("condition_rules") or []) + list(rule.get("drug_class_rules") or [])
    pl = rule.get("pregnancy_lactation")
    if isinstance(pl, dict):
        buckets.append(pl)
    for sub in buckets:
        for s in (sub.get("sources") or []):
            if isinstance(s, str) and s.strip().startswith(("http://", "https://")):
                out.append(s.strip())
    return out


def test_every_rule_has_at_least_one_provenance_source():
    """No rule may ship with zero http(s) provenance (guards against orphan
    rules losing their sub-rules and their citations in a migration)."""
    orphans = [r.get("id") for r in RULES if not _http_sources(r)]
    assert not orphans, f"rules with no provenance source: {orphans}"


def test_previously_orphan_rules_carry_verified_sources():
    """Lock the content-verified provenance on the two rules that had none."""
    expected = {
        "RULE_INGREDIENT_ELDERBERRY__AUTOIMMUNE": {
            "https://pubmed.ncbi.nlm.nih.gov/24624087/",
            "https://www.ncbi.nlm.nih.gov/books/NBK501835/",
        },
        "RULE_IQM_PYGEUM_NSAIDS": {
            "https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=pygeum&lang=eng",
        },
    }
    by_id = {r.get("id"): r for r in RULES}
    for rid, want in expected.items():
        assert rid in by_id, f"{rid} missing"
        got = set(_http_sources(by_id[rid]))
        assert want <= got, f"{rid} missing verified sources: {want - got}"
