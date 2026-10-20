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


# ---- batch B: study facts restated from the article; determinations unchanged -----------------

# A row that pointed at the wrong paper now cites the trial it describes (PubMed-searched,
# abstract read): old PMID -> new PMID.
REPOINTED = {
    "goldenseal": ("32591416", "17495878"),
    "dong_quai": ("34090852", "9418683"),
    "chitosan": ("32437302", "18646097"),
    "ipriflavone": ("10479216", "11255425"),
}


@pytest.mark.parametrize("cid, pmids", sorted(REPOINTED.items()))
def test_a_wrong_paper_citation_is_repointed_to_the_trial(records, cid, pmids):
    old, new = pmids
    study, = records[cid]["qualifying_human_studies"]
    assert study["pmid"] == new != old
    prov = study["verification_provenance"]
    assert prov["verified_source"].endswith(f"/{new}/") and prov["authoritative_live_title"] == study["title"]


def test_ipriflavone_keeps_its_safety_finding_on_the_real_trial(records):
    record = records["ipriflavone"]
    study = _study(record, "11255425")
    assert record["effect_direction"] == "negative" and study["sample_size"] == 474
    assert "lymphocytopenia" in study["outcome"]


FIGURES_B = [
    ("l_glutamine", "32992440", "sample_size", 14, 8),
    ("lignans", "32575611", "dose", "50 mg/day SDG", "600 mg/day"),
    ("cryptoxanthin", "37242207", "sample_size", 90, 32),
    ("green_coffee_bean", "16820341", "sample_size", 28, 117),
    ("pumpkin", "25196580", "sample_size", 1431, 47),
    ("rose_hips", "16195164", "sample_size", 94, 112),
    ("globe_artichoke", "14653829", "dose", "three times daily", "640 mg/day"),
    ("uva_ursi_leaf", "34111592", "sample_size", 398, 57),
    ("nicotinamide_riboside", "27721479", "dose", "single doses", "1000 mg/day"),
    ("beta_glucan", "23378458", "sample_size", 77, 162),
    ("borage_seed_oil", "8214997", "sample_size", 37, 56),
    ("atp", "28080323", "sample_size", 42, 16),
    ("milk_basic_protein", "17048062", "sample_size", 35, 30),
    ("algae_oil", "18589030", "sample_size", 32, 11),
    ("tudca", "8674405", "sample_size", 24, 80),
    ("nopal", "22805855", "sample_size", 6, 10),
    ("lychee_polyphenol", "40887285", "dose", "200 mg/day", "100 mg/day"),
    ("jujube", "33385511", "sample_size", 12, 40),
    ("cranberry_fruit", "37068952", "sample_size", 8857, 8611),
    ("ginkgo_biloba_leaf", "25114079", "sample_size", 2561, 2372),
    ("green_tea_leaf", "21715508", "sample_size", 1136, 1415),
    ("fucoidan", "36307493", "sample_size", 20, 75),
    ("diamine_oxidase", "31807350", "sample_size", 28, 39),
    ("lactase", "20391953", "sample_size", 60, 40),
    ("african_geranium", "17184981", "sample_size", 2099, 468),
    ("l_cysteine", "33105552", "dose", "N-acetylcysteine", "1000 mg/day L-cysteine"),
    ("guggul", "12915429", "dose", "three times daily", "1000 - 2000 mg/day"),
    ("red_clover", "33920485", "sample_size", 1179, 894),
]


@pytest.mark.parametrize("cid, pmid, field, reported, recorded", FIGURES_B)
def test_batch_b_study_figures_match_the_article(records, cid, pmid, field, reported, recorded):
    test_study_figures_match_the_article(records, cid, pmid, field, reported, recorded)


# Figures no cited source reports are removed rather than kept.
REMOVED = [
    ("chlorophyll", "7350215", "dose"), ("pygeum", "11869585", "dose"), ("hawthorn", "12798455", "dose"),
    ("aloe_vera", "27009750", "dose"), ("horse_chestnut_seed", "15106197", "dose"),
    ("butchers_broom_root", "12040966", "dose"), ("evening_primrose_oil", "23633319", "dose"),
    ("activated_charcoal", "3521259", "dose"), ("colostrum", "21148400", "dose"),
    ("glutathione", "24791752", "scoring_eligible"), ("capsaicin", "23844093", "sample_size"),
]


@pytest.mark.parametrize("cid, pmid, field", REMOVED)
def test_an_unreported_figure_is_removed(records, cid, pmid, field):
    assert field not in _study(records[cid], pmid)


def test_glutathione_cites_its_trial_once(records):
    assert [s["pmid"] for s in records["glutathione"]["qualifying_human_studies"]] == ["24791752"]


def test_safety_signal_records_keep_their_direction_and_state_their_source(records):
    for cid in ("graviola", "artemisinin", "PII_ARTEMISININ"):
        assert records[cid]["effect_direction"] == "negative"
    assert "not established" in _study(records["artemisinin"], "19680221")["outcome"]
    assert "neurotoxicity" not in records["artemisinin"]["applicability_decision"]
    assert _study(records["graviola"], "14521988")["study_type"] == "in_vitro"


# ---- integrator-audit leftovers (batch C) ------------------------------------------------------

def test_no_unsourced_threshold_in_applicability(records):
    """A '>= N' in applicability text must be a threshold the cited study sets (or be gone)."""
    for cid in ("coleus_forskohlii_root", "nad", "atp", "activated_charcoal", "milk_basic_protein",
                "mastic_gum", "capsaicin", "cayenne_pepper"):
        text = records[cid]["applicability_decision"]
        assert ">=" not in text and "≥" not in text, cid
    # the one source-set minimum is stated as the article states it
    assert "at least 2 mg capsaicinoids taken before a meal" in records["cayenne_pepper"]["applicability_decision"]


@pytest.mark.parametrize("cid, values", [
    ("chitosan", None), ("activated_charcoal", None), ("coleus_forskohlii_root", [500]),
    ("nad", [1000]), ("atp", [400]), ("milk_basic_protein", [40]),
])
def test_studied_dose_exposure_is_one_daily_basis_or_empty(records, cid, values):
    sde = records[cid]["studied_dose_exposure"]
    if values is None:
        assert sde == {}
    else:
        assert sde == {"values": values, "unit": "mg", "basis": "daily_intake"}


@pytest.mark.parametrize("cid", ["olive_fruit_extract", "black_garlic", "superoxide_dismutase", "schisandra",
                                 "shiitake_mushroom", "fucoxanthin", "perilla_oil", "undecylenic_acid"])
def test_no_record_keeps_a_stale_applicable_status(records, cid):
    assert records[cid]["applicability_status"] == "applicability_unestablished"
