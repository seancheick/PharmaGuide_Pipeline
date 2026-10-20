"""Literature records state only what their cited articles report (review 2026-10-20).

A content read of every study in literature_evidence_records.json against its PubMed abstract
(PMC full text where cited) found rows citing the wrong paper, doses, sample sizes, materials and
outcomes the papers do not report, and evidence for one preparation credited to another.
Receipts: scripts/audits/literature_records_review_20261020/research.md.
"""
import json
import logging
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "literature_evidence_records.json"


@pytest.fixture(scope="module")
def records():
    return {r["canonical_id"]: r for r in json.loads(DATA.read_text())["literature_evidence_records"]}


def _study(record, pmid):
    return next(s for s in record["qualifying_human_studies"] if s["pmid"] == pmid)


# Rows whose PMID is a different paper (review, in-vitro or animal study) than the trial recorded.
NO_VERIFIED_TRIAL = {
    "l_carnosine": "20091069",              # beta-alanine review
    "l_phenylalanine": "37629744",          # Parkinson's depression review
    "docosapentaenoic_acid_dpa": "30716358",  # narrative review
    "dimethyl_glycine": "34823458",         # DMG-in-autism review
    "boswellia_serrata_resin": "32565872",  # rat + in-vitro study
    "perilla_oil": "21909287",              # fatty-acid composition review
    "superoxide_dismutase": "15742357",     # animal study
    "schisandra_berry": "18515024",         # narrative overview
    "schisandra": "18515024",
}


@pytest.mark.parametrize("cid, pmid", sorted(NO_VERIFIED_TRIAL.items()))
def test_a_record_without_a_verified_trial_reads_review_pending(records, cid, pmid):
    from evidence_resolver import resolve_evidence_for_canonical
    record = records[cid]
    assert record["verification_result"] == "verification_failure_unresolved"
    assert record["verification_provenance"]["all_pmids_verified"] is False
    assert record["studied_dose_exposure"] == {}
    for study in record["qualifying_human_studies"]:
        # a kept non-trial citation is labelled as what it is and carries no trial figures
        assert study["pmid"] == pmid and study["scoring_eligible"] is False
        assert not {"sample_size", "dose", "duration"} & set(study)
    assert pmid in record["applicability_decision"]
    logging.disable(logging.WARNING)
    resolution = resolve_evidence_for_canonical(cid)
    assert resolution.blocking_reasons == ["literature_verification_pending"]


def test_broccoli_cites_the_sprout_trial_it_cannot_inherit(records):
    record = records["broccoli"]
    study, = record["qualifying_human_studies"]
    assert study["pmid"] == "24913818" and study["sample_size"] == 291
    assert record["effect_direction"] == "applicability_unestablished"
    assert "30372361" in record["applicability_decision"] and "cannot inherit" in record["applicability_decision"]


@pytest.mark.parametrize("cid", ["l_carnosine", "l_phenylalanine"])
def test_a_wrong_paper_row_is_removed(records, cid):
    assert records[cid]["qualifying_human_studies"] == []


# Evidence for one preparation credited to another: combination, food, beverage, topical,
# different species or plant part, whole protein. None may resolve as reviewed clinical evidence.
PREPARATION_MISMATCH = {
    "l_isoleucine": "BCAA", "l_valine": "BCAA", "ginger_extract": "Alpinia galanga",
    "l_tryptophan": "alpha-lactalbumin", "cyanidin_3_glucoside": "anthocyanin mixture",
    "phosphatidylcholine": "30% phosphatidylcholine", "marshmallow_root": "ivy leaf",
    "keratin": "vitamins and minerals", "winged_treebine": "green tea", "magnolia_bark": "Phellodendron",
    "fucoxanthin": "pomegranate seed oil", "fennel": "essence", "pomegranate": "juice",
    "acai_berry": "pulp", "chrysin": "honey", "cat_s_claw": "guianensis", "wild_yam_root": "cream",
    "pumpkin_seed_oil": "No seed-oil arm", "spearmint": "tea", "moringa": "leaves",
    "shiitake": "Whole-mushroom", "shiitake_mushroom": "Whole-mushroom", "oolong_tea_leaf": "tea",
    "dark_sweet_cherry": "fresh Bing cherries", "olive_fruit_extract": "leaf",
    "black_garlic": "aged garlic extract", "undecylenic_acid": "Topical",
    "l_threonine": "not an efficacy trial",
}


@pytest.mark.parametrize("cid, studied", sorted(PREPARATION_MISMATCH.items()))
def test_studied_preparation_does_not_transfer(records, cid, studied):
    record = records[cid]
    assert record["effect_direction"] == "applicability_unestablished"
    assert studied.lower() in record["applicability_decision"].lower()


def test_barberry_trial_is_a_null_result(records):
    record = records["barberry_root"]
    study = _study(record, "37575603")
    assert record["effect_direction"] == "null" and study["effect_direction"] == "null"
    assert study["sample_size"] == 88 and "three times daily" in study["dose"]
    assert "did not prevent" in record["applicability_decision"]


# (record, pmid, field, value the article reports, value the record had)
FIGURES = [
    ("l_valine", "28638350", "dose", "1.6 g valine", "1.4 g valine"),
    ("cyanidin_3_glucoside", "25833778", "sample_size", 58, 160),
    ("phosphatidylcholine", "33440385", "sample_size", 160, 30),
    ("marshmallow_root", "16391481", "sample_size", 62, 822),
    ("moringa", "37229639", "sample_size", 40, 60),
    ("moringa", "37229639", "duration", "14 days", "12 weeks"),
    ("dark_sweet_cherry", "12771324", "sample_size", 10, 18),
    ("l_threonine", "37004875", "sample_size", 11, 7),
    ("winged_treebine", "16948861", "sample_size", 123, 92),
    ("magnolia_bark", "18426577", "duration", "6 weeks", "4 weeks"),
    ("fennel", "12566188", "sample_size", 30, 60),
    ("pumpkin_seed_oil", "25196580", "effect_direction", "null", "positive_moderate"),
    ("acai_berry", "21569436", "dose", "100 g acai pulp twice daily", "1000 mg extract equivalent"),
]


@pytest.mark.parametrize("cid, pmid, field, reported, recorded", FIGURES)
def test_study_figures_match_the_article(records, cid, pmid, field, reported, recorded):
    value = _study(records[cid], pmid)[field]
    if isinstance(reported, str):
        assert reported in value and recorded not in value
    else:
        assert value == reported != recorded


def test_no_invented_dose_threshold_survives_in_corrected_records(records):
    old = {"l_isoleucine": ">= 1", "pomegranate": "500 mg", "l_tryptophan": "1000 mg",
           "cyanidin_3_glucoside": "100 mg", "phosphatidylcholine": "500 mg", "marshmallow_root": "500 mg",
           "keratin": ">= 500", "fennel": "120 mg", "acai_berry": "1000 mg", "spearmint": "500 mg",
           "moringa": "1000 mg", "oolong_tea_leaf": "500 mg", "dark_sweet_cherry": "500 mg",
           "undecylenic_acid": "250", "black_garlic": "600"}
    for cid, phrase in old.items():
        assert phrase not in records[cid]["applicability_decision"], cid
