"""Curated drug-supplement pairs cite sources about the pair they describe.

A real PMID about the right ingredient but the wrong topic is a ghost reference.
Receipts: scripts/audits/pending_items_20260926/research.md.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
PAIRS = {
    entry["id"]: entry
    for entry in json.loads((DATA / "curated_interactions" / "curated_interactions_v1.json").read_text())["interactions"]
}


def test_garlic_warfarin_does_not_cite_the_allicin_antimicrobial_paper():
    """PMID 10594976 (Ankri & Mirelman 1999) is "Antimicrobial properties of
    allicin from garlic"; it says nothing about warfarin or bleeding. NCCIH's
    garlic page, which states the bleeding risk with anticoagulants, remains."""
    pair = PAIRS["DSI_WAR_GARLIC"]
    assert "10594976" not in pair.get("source_pmids", [])
    assert not any("10594976" in url for url in pair.get("source_urls", []))
    assert any("nccih.nih.gov" in url for url in pair["source_urls"])


def test_ginkgo_antiplatelet_observational_source_is_not_promoted_to_established():
    """PMID 40198642 is retrospective observational, not a systematic review."""
    from build_interaction_db import build_interaction_row
    pair = PAIRS['DSI_GINKGO_ANTIPLATELET']
    assert pair['evidence_basis'] == 'observational'
    assert build_interaction_row(pair, rxcui_to_class={}, build_time='2026-10-11', interaction_db_version='audit')['evidence_level'] == 'moderate'
    assert pair['severity'] == 'Major'  # evidence strength does not soften hazard
    assert '7 days' not in pair['management']
    assert 'surgical team' in pair['management'].lower()


def test_fish_oil_case_report_cannot_define_a_one_gram_warning_floor():
    """PMID 17192169 reports 6 g/day + aspirin + warfarin after a fall, no 1 g floor."""
    from build_interaction_db import build_interaction_row
    pair = PAIRS['DSI_WAR_OMEGA3']
    assert pair['materiality'] == 'presence'
    assert pair.get('dose_threshold') is None
    row = build_interaction_row(pair, rxcui_to_class={}, build_time='2026-10-11', interaction_db_version='audit')
    assert row['dose_dependent'] == 0
    assert row['dose_threshold_json'] is None
    text = (pair['mechanism'] + ' ' + pair['management']).lower()
    assert 'up to 1 g/day' not in text
    assert '≥3 g/day' not in text
    assert 'most research' in text and 'inr' in text
    assert pair['severity'] == 'Moderate'


def test_ginkgo_warfarin_mechanism_keeps_mixed_evidence_explicit():
    pair = PAIRS['DSI_WAR_GINKGO']
    assert 'significantly amplifies' not in pair['mechanism'].lower()
    assert 'mixed' in pair['mechanism'].lower()
    assert pair['severity'] == 'Major'
    assert pair['materiality'] == 'presence'


def test_red_yeast_rice_does_not_assert_exact_statin_dose_doubling():
    pair = PAIRS['DSI_STATINS_RYR']
    assert 'doubles the effective statin dose' not in pair['mechanism'].lower()
    assert 'varies' in pair['mechanism'].lower()
    assert pair['severity'] == 'Major'


def test_st_johns_wort_does_not_prescribe_a_universal_ssri_washout():
    pair = PAIRS['DSI_SSRI_SJW']
    assert '5 half-lives' not in pair['management']
    assert 'prescriber' in pair['management'].lower()
    assert pair['severity'] == 'Contraindicated'
    assert 'can cause serotonin syndrome' in pair['mechanism']
    assert 'this creates severe' not in pair['mechanism'].lower()


def test_real_source_pairs_preserve_clinical_tier_and_identity_through_export():
    """Independent source expectations supplement synthetic builder fixtures.

    These are the brief's checked pairs, not a complete clinical-registry audit.
    Severity expectations follow the current authored policy; evidence strength
    remains a separate axis. See per-source receipts in research.md.
    """
    from api_audit.verify_interactions import normalize_severity
    from build_interaction_db import build_interaction_row, build_rxcui_to_class
    classes = json.loads((DATA / 'drug_classes.json').read_text())
    expected = {
        'DSI_ACEI_POTASSIUM': ('avoid', 'potassium', 'established'),
        'DSI_WAR_GINKGO': ('avoid', 'ginkgo', 'probable'),
        'DSI_GINKGO_ANTIPLATELET': ('avoid', 'ginkgo', 'moderate'),
        'DSI_SSRI_SJW': ('contraindicated', 'st_johns_wort', 'established'),
        'DSI_STATINS_RYR': ('avoid', 'red_yeast_rice', 'established'),
        'DSI_WAR_OMEGA3': ('caution', 'fish_oil', 'probable'),
        'DSI_WAR_VITK': ('caution', 'vitamin_k', 'established'),
        'DSI_LEVOTHYROXINE_CALCIUM': ('caution', 'calcium', 'established'),
        'DSI_LEVOTHYROXINE_IRON': ('caution', 'iron', 'established'),
        'DSI_LEVOTHYROXINE_MAGNESIUM': ('caution', 'magnesium', 'probable'),
    }
    for id, (severity, canonical, evidence) in expected.items():
        entry = dict(PAIRS[id])
        entry['severity'] = normalize_severity(entry['severity'])
        row = build_interaction_row(entry, rxcui_to_class=build_rxcui_to_class(classes), build_time='2026-10-11', interaction_db_version='audit')
        assert row['severity'] == severity, id
        assert row['agent2_canonical_id'] == canonical, id
        assert row['evidence_level'] == evidence, id
        assert row['mechanism'] == entry['mechanism'], id
        assert row['management'] == entry['management'], id
        assert row['source_urls_json'], id
    assert '4' in PAIRS['DSI_LEVOTHYROXINE_CALCIUM']['management']
    assert '4' in PAIRS['DSI_LEVOTHYROXINE_IRON']['management']


def test_ace_inhibitor_potassium_cites_a_real_lisinopril_label():
    """DailyMed API returned404 for old setid; replacement label5.5/7.1 supports risk."""
    pair = PAIRS['DSI_ACEI_POTASSIUM']
    assert not any('f4cb6e1e-2d43-4d17-8c6e-c9d3f7b4c4a0' in url for url in pair['source_urls'])
    assert 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=34ebeea1-6812-4697-84c4-b2ae4f39e55f' in pair['source_urls']
    assert 'https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional/' in pair['source_urls']
    assert pair['severity'] == 'Major'
    assert pair['agent1_id'] == 'class:ace_inhibitors'
    assert pair['agent2_canonical_id'] == 'potassium'
