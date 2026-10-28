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


def test_qualifying_studies_use_one_name_per_fact(records):
    """effect/design were aliases of effect_direction/study_type. primary_endpoint
    (what was measured) and outcome (what was found) are distinct facts."""
    aliased = [(cid, s.get("pmid")) for cid, r in records.items()
               for s in r["qualifying_human_studies"] if "effect" in s or "design" in s]
    assert not aliased


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
    "fucoxanthin": "pomegranate seed oil", "fennel": "essence",
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


def test_pomegranate_preserves_verified_extract_research(records):
    from evidence_resolver import resolve_evidence_for_canonical
    record = records["pomegranate"]
    assert record["effect_direction"] == "positive_weak"
    assert record["studied_dose_exposure"] == {}
    assert _study(record, "38410857")["effect_direction"] == "positive_weak"
    assert "extract diastolic results were not statistically significant" in record["applicability_decision"]
    assert "mainly to juice" not in record["applicability_decision"]
    resolution = resolve_evidence_for_canonical("pomegranate")
    assert "literature_applicability_unestablished" not in resolution.blocking_reasons


def test_fucoxanthin_preserves_component_surrogate_without_weight_loss_transfer(records):
    record = records["fucoxanthin"]
    study = _study(record, "19840063")
    assert record["effect_direction"] == "applicability_unestablished"
    assert record["studied_dose_exposure"] == {}
    assert "standalone fucoxanthin increased resting energy expenditure" in study["outcome"]
    assert "Combination reduced weight" in study["outcome"]
    assert "surrogate" in record["applicability_decision"]
    assert "standalone fucoxanthin weight loss" in record["applicability_decision"]


@pytest.mark.parametrize("cid", ['olive_fruit_extract', 'black_garlic', 'superoxide_dismutase', 'schisandra', 'shiitake_mushroom', 'fucoxanthin', 'perilla_oil', 'undecylenic_acid'])
def test_corrected_applicability_metadata_is_coherent(records, cid):
    from evidence_resolver import resolve_evidence_for_canonical
    record = records[cid]
    assert record["applicability_status"] == "applicability_unestablished"
    resolution = resolve_evidence_for_canonical(cid)
    if cid in {"superoxide_dismutase", "schisandra", "perilla_oil"}:
        assert resolution.applicability_status == "unverified_literature_record"
        assert resolution.blocking_reasons == ["literature_verification_pending"]
    else:
        assert resolution.applicability_status == "applicability_unestablished"



def test_b_part1_doses_remain_bound_to_the_cited_regimen(records):
    assert records["beta_glucan"]["studied_dose_exposure"] == {"values": [250], "unit": "mg", "basis": "daily_intake"}
    assert records["chitosan"]["studied_dose_exposure"] == {}
    shark = records["OI_SHARK_CARTILAGE"]
    assert shark["studied_dose_exposure"] == {}
    study = _study(shark, "15912493")
    assert "titrated" in study["dose"] and "as tolerated" in study["dose"]
    assert "underpowered" in shark["applicability_decision"]
    assert "worse" in study["outcome"]
    assert "not an established effective-dose range" in shark["applicability_decision"]


def test_b_part1_arjuna_does_not_convert_within_group_significance(records):
    text = records["arjuna"]["applicability_decision"]
    assert "within the treated group" in text
    assert "does not establish a statistically significant between-group effect" in text
    assert "Angina frequency fell in both groups" in text


def test_b_part1_larch_uses_the_source_intervention_period(records):
    assert _study(records["larch_arabinogalactan"], "20796315")["duration"] == "72 days"
    assert "72 days" in records["larch_arabinogalactan"]["applicability_decision"]


def test_b_part2_lecithin_does_not_erase_placebo_group(records):
    r = records['lecithin']
    s = _study(records['lecithin'], '21490917')
    assert s['study_type'] != 'uncontrolled_clinical_study'
    assert 'no control group' not in s['outcome'].lower()
    assert 'placebo' in r['applicability_decision'].lower()
    assert 'uncontrolled' not in r['applicability_decision'].lower()

def test_b_part2_grape_seed_primary_null_not_overridden_by_exploratory_subgroup(records):
    r = records['grape_seed']
    s = _study(records['grape_seed'], '33671310')
    assert r['effect_direction'] == s['effect_direction'] == 'mixed'
    assert '0.7197' in s['outcome']
    assert 'primary' in r['applicability_decision'].lower()
    assert 'not superior' in r['applicability_decision'].lower()
    assert r['studied_dose_exposure']['values'] == [300]

def test_b_part2_nad_cannot_inherit_nr_trial_applicability(records, monkeypatch):
    import evidence_resolver as er
    monkeypatch.setattr(er, '_load_literature_evidence', lambda: records)
    r = er.resolve_evidence_for_canonical('nad', name='NAD+ (Nicotinamide Adenine Dinucleotide)')
    assert r.disposition == 'research_present_applicability_unestablished'
    assert records['nad']['studied_dose_exposure'] == {}
    assert '250' not in records['nad']['applicability_decision'] or 'No 250' in records['nad']['applicability_decision']

def test_b_part2_leucine_umbrella_not_assigned_unverified_699_enrollment(records):
    assert 'sample_size' not in _study(records['l_leucine'], '32483625')

def test_b_part2_pregnenolone_no_unverified_derived_dose_after_source_dose_abstention(records):
    assert 'dose' not in _study(records['pregnenolone'], '25030803')
    assert records['pregnenolone']['studied_dose_exposure'] == {}

def test_b_part2_epo_actual_tested_exposure_retained_with_null_conclusion(records):
    assert records['evening_primrose_oil']['studied_dose_exposure']['values'] == [1000]
    assert records['evening_primrose_oil']['effect_direction'] == 'null'

def test_b_part2_nr_identity_own_trials_remain_separate_and_resolved(records, monkeypatch):
    import evidence_resolver as er
    monkeypatch.setattr(er, '_load_literature_evidence', lambda: records)
    r = er.resolve_evidence_for_canonical('nicotinamide_riboside')
    assert r.disposition == 'resolved_by_reviewed_clinical_evidence'
    assert records['nicotinamide_riboside']['studied_dose_exposure']['values'] == [100, 300, 1000]


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
    ("nad", None), ("atp", [400]), ("milk_basic_protein", [40]),
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


# B0 primary-content corrections: portable literals, no local corpus required.
def test_b0_rhubarb_randomized_is_not_completed_or_isolated_rhein(records):
    record = records["turkey_rhubarb_root"]
    study = _study(record, "36499011")
    assert study["sample_size"] == 42
    assert "42 randomized, 39 analyzed" in record["applicability_decision"]
    assert "42 completed" not in record["applicability_decision"]
    assert "anthraquinone derivatives expressed as rhein" in study["dose"]
    assert record["studied_dose_exposure"] == {}


def test_b0_red_clover_review_population_is_distinct_from_hot_flush_subset(records):
    record = records["red_clover"]
    assert _study(record, "33920485")["sample_size"] == 1179
    assert "12 trials with 1,179 women overall" in record["applicability_decision"]
    assert "1,043 in the final analysis" in record["applicability_decision"]
    assert "8 trials (10 comparisons)" in record["applicability_decision"]
    assert ">= 80 mg/day subgroup was not significant" in record["applicability_decision"]


def test_b0_vinegar_reports_auc_and_blueberry_is_not_a_meta_analysis(records):
    outcome = _study(records["apple_cider_vinegar"], "28292654")["outcome"]
    assert "area under the curve (AUC)" in outcome
    assert "peaks" not in outcome
    assert _study(records["blueberry"], "30999017")["study_type"] == "systematic_review"


def test_b0_capsaicin_source_does_not_assert_capsiate_equivalence(records):
    record = records["capsaicin"]
    assert record["material_form"] == "Red chili pepper providing quantified capsaicin (2.56 mg per meal)"
    assert "does not establish capsiate preparation equivalence" in record["applicability_decision"]
    assert record["studied_dose_exposure"] == {"values": [2.56], "unit": "mg", "basis": "capsaicin_per_meal"}


def test_b0_lions_mane_tablet_mass_is_not_an_exact_powder_or_part_claim(records):
    record = records["lions_mane"]
    assert "plant part not specified in the abstract" in record["material_form"]
    assert "fruiting" not in record["material_form"]
    assert "96%" in _study(record, "18844328")["dose"]
    assert "3 g/day tablet mass" in _study(record, "18844328")["dose"]
    assert record["studied_dose_exposure"] == {}


def test_b0_schisandra_preparation_stays_unknown_and_review_pending(records):
    record = records["schisandra"]
    assert "plant part and extraction unspecified" in record["material_form"]
    assert record["verification_result"] == "verification_failure_unresolved"
    assert _study(record, "18515024")["scoring_eligible"] is False


def test_african_mango_daily_exposure_is_not_a_threshold_or_single_dose(records):
    record = records['african_mango']
    study = _study(record, '19254366')
    assert record['studied_dose_exposure'] == {'values': [300], 'unit': 'mg'}
    assert '120' in study['notes'] and '102' in study['notes']
    assert 'minimum' in record['applicability_decision']
    assert '>=' not in record['applicability_decision']
    assert '150 mg twice daily' in record['applicability_decision']
    assert record['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
    assert record['reference_semantics']['reference_type'] == 'no_benchmark'
    assert record['reference_semantics']['source_ids'] == ['PMID:19254366']


@pytest.mark.parametrize('cid', ['theobromine', 'white_willow_bark', 'l_ornithine', 'maqui', 'royal_jelly', 'caralluma', 'ashwagandha_root'])
def test_single_regimen_does_not_become_an_open_ended_minimum(records, cid):
    assert '>=' not in records[cid]['applicability_decision']


def test_ornithine_includes_the_exercise_day_regimen(records):
    r = records['l_ornithine']
    assert r['studied_dose_exposure']['values'] == [2000, 6000]
    s = _study(r, '19083482')
    assert '6000' in s['dose'] and s['duration'] == '8 days'


def test_ashwagandha_single_capsule_is_not_a_daily_dose(records):
    assert records['ashwagandha_root']['studied_dose_exposure']['values'] == [600]


@pytest.mark.parametrize('cid, unsupported', [
    ('maqui', 'Delphinol'), ('ashwagandha_root', 'Sensoril'),
    ('royal_jelly', '10-HDA'), ('caralluma', 'pregnane'),
    ('white_willow_bark', 'Salix alba'),
])
def test_source_preparation_does_not_add_unverified_brand_or_standardization(records, cid, unsupported):
    assert unsupported not in records[cid]['material_form']


def test_tart_cherry_source_summary_retains_pre_event_and_race_day_regimen(records):
    row = records['tart_cherry']
    assert '7 days before and on race day' in row['applicability_decision']
    assert '7 days before and on race day' == _study(row, '20459662')['duration']
    assert 'does not transfer to dry tart cherry powder or extract' in row['applicability_decision']


@pytest.mark.parametrize('canonical,pmids', [
    ('skullcap', {'12652886','23878109'}),
    ('noni', {'21294416','23097636','22436097'}),
    ('corn_silk', {'25727941'}),
    ('yarrow_aerial_parts', {'26238568'}),
    ('korean_pine', {'18355411'}),
    ('tremella_fuciformis', {'29319408','38439104'}),
    ('cistanche', {'33477648'}),
    ('french_oak', {'32230721'}),
    ('shatavari', {'34959836'}),
    ('black_rice', {'34547006'}),
    ('juniper', {'39842749'}),
    ('peppermint_essential_oil', {'42024666'}),
    ('theacrine', {'26766930','27164220','31660991','40048726'}),
    ('kawaratake', {'12814145','25006989','28375640'}),
    ('oi_solarplast', {'39684397'}),
])
def test_related_human_sources_replace_false_absence_without_clinical_clearance(records, canonical, pmids):
    from evidence_resolver import resolve_evidence_for_canonical, EvidenceDisposition
    record = records[canonical]
    assert record['effect_direction'] == 'applicability_unestablished'
    assert record['verification_result'] == 'verification_failure_unresolved'
    assert pmids <= {str(study['pmid']) for study in record['qualifying_human_studies']}
    assert all(study['scoring_eligible'] is False for study in record['qualifying_human_studies'])
    assert record['studied_dose_exposure'] == {}
    dose_reviewed = {'skullcap', 'noni', 'corn_silk', 'yarrow_aerial_parts', 'korean_pine',
                     'tremella_fuciformis', 'cistanche', 'french_oak', 'shatavari', 'black_rice',
                     'juniper', 'theacrine', 'kawaratake'}
    if canonical in dose_reviewed:
        from dose_assessment import verified_reference_citations
        assert record['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
        assert verified_reference_citations(record)
    else:
        assert not record.get('reference_semantics')
    result = resolve_evidence_for_canonical(canonical)
    assert result.disposition == EvidenceDisposition.LITERATURE_RESOLUTION_REQUIRED.value
    assert result.points_eligible is False
