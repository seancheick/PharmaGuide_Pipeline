"""Confirmed route audit defects: group votes, hidden amounts and daily betaine."""
import pytest

from test_v4_sports_dose_p171 import _product, _row
from test_v4_botanical_profile import _botanical_product, _botanical_ingredient
from scoring_v4.modules.sports_dose import score_dose
from scoring_v4.modules.sports_helpers import EAA_CANONICALS
from scoring_v4.scored_artifact import build_scored_artifact


def _dose(product):
    return build_scored_artifact(product)["quality_pillars_v4"]["dose"]["score"]


def test_bcaa_aggregate_is_one_coprimary_vote():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"),
                       _row("branched_chain_amino_acids", 1, "Gram(s)"),
                       name="Creatine + BCAA", primary_type="pre_workout")
    assert _dose(product) == 15.7  # (20 + neutral 11.4) / 2
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [c["ingredient"] for c in contributions] == ["creatine", "bcaa"]


def test_split_bcaa_gets_one_group_vote_not_three_amino_acid_votes():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"),
                       _row("l_leucine", 1, "Gram(s)"),
                       _row("l_isoleucine", .5, "Gram(s)"),
                       _row("l_valine", .5, "Gram(s)"),
                       name="Creatine + BCAA", primary_type="pre_workout")
    assert _dose(product) == 15.7  # one neutral BCAA preparation vote
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [c["ingredient"] for c in contributions] == ["creatine", "bcaa"]
    assert contributions[1]["amount_per_serving"] == 2.0


def test_complete_eaa_aggregate_is_one_vote_and_does_not_add_a_bcaa_vote():
    eaa = {**_row("essential_amino_acids", 5, "Gram(s)"),
           "scoring_input_kind": "product_level_evidence", "evidence_type": "sports_primary_dose",
           "verified_child_canonicals": sorted(EAA_CANONICALS)}
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), eaa,
                       name="Creatine + Essential Amino Acids", primary_type="pre_workout")
    assert _dose(product) == 15.7  # one neutral EAA preparation vote
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [c["ingredient"] for c in contributions] == ["creatine", "eaa"]
    assert contributions[1]["amount_per_serving"] == 5.0


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("identity", ["bcaa", "eaa"])
def test_group_leading_average_equals_its_standalone_assessment_in_either_order(identity, reverse):
    creatine = _row("creatine_monohydrate", 1, "Gram(s)")
    if identity == "bcaa":
        amino_rows = [_row("l_leucine", 2.5, "Gram(s)"),
                      _row("l_isoleucine", 1.25, "Gram(s)"), _row("l_valine", 1.25, "Gram(s)")]
        title = "Creatine + BCAA"
    else:
        amino_rows = [{**_row("essential_amino_acids", 8, "Gram(s)"),
                      "scoring_input_kind": "product_level_evidence", "evidence_type": "sports_primary_dose",
                      "verified_child_canonicals": sorted(EAA_CANONICALS)}]
        title = "Creatine + Essential Amino Acids"
    rows = [creatine, *amino_rows]
    if reverse:
        rows.reverse()
    group_score = _dose(_product(*amino_rows, name=title, primary_type="pre_workout"))
    creatine_score = _dose(_product(creatine, name="Creatine", primary_type="pre_workout"))
    product = _product(*rows, name=title, primary_type="pre_workout")
    assert group_score == 11.4 and creatine_score == 6.7
    assert _dose(product) == 9.0  # unrounded raw (11.4 + 20/3)/2
    assert "sports_ratio_or_completeness" not in score_dose(product)["components"]
    standalone = score_dose(_product(*amino_rows, name=title, primary_type="pre_workout"))
    # The preparation's contribution includes its composition assessment;
    # a receipt must not lose those points or add them globally after averaging.
    assert standalone["metadata"]["dose_contributions"][0]["credit_raw"] == standalone["score"] == 11.4


@pytest.mark.parametrize("hidden,expected", [(True, 15.7), (False, 0)])
def test_only_positive_label_hiding_gets_a_neutral_coprimary_vote(hidden, expected):
    missing = {**_row("beta_alanine", 1, "Gram(s)"), "quantity": None, "unit": ""}
    if hidden:
        missing["isNestedIngredient"] = True
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), missing,
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    assert _dose(product) == expected
    if not hidden:
        assert score_dose(product)["score"] is None
        assert score_dose(product)["metadata"]["assessment_status"] == "incomplete"
    contribution = score_dose(product)["metadata"]["dose_contributions"][1]
    assert (contribution["assessment"] == "hidden_amount_neutral") is hidden
    assert contribution.get("amount_per_serving") is None


def test_unresolved_disclosed_sports_amount_is_not_hidden_neutral():
    unread = {**_row("beta_alanine", 4, "Gram(s)"), "quantity_operator": "ambiguous",
              "isNestedIngredient": True}
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"), unread,
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    assert build_scored_artifact(product)["quality_score_status"] == "not_scored"
    assert all(c["assessment"] != "hidden_amount_neutral"
               for c in score_dose(product)["metadata"]["dose_contributions"])


@pytest.mark.parametrize("minimum,maximum,expected", [(2, 2, 11.4), (1, 2, 11.4), (2, 4, 11.4)])
def test_betaine_daily_target_uses_the_minimum_directed_exposure(minimum, maximum, expected):
    product = _product(_row("betaine", 1.25, "Gram(s)"), name="Betaine", primary_type="pre_workout")
    product["servingSizes"][0].update(minDailyServings=minimum, maxDailyServings=maximum)
    assert _dose(product) == expected
    contribution = score_dose(product)["metadata"]["dose_contributions"][0]
    assert contribution["amount_per_serving"] == 1.25
    assert contribution["amount_at_minimum"] == 1.25 * minimum
    assert contribution["amount_at_maximum"] == 1.25 * maximum
    assert contribution["amount_unit"] == "g"
    assert "reference_value" not in contribution
    assert contribution["assessment"] == "betaine_completed_no_general_benchmark"


def test_per_use_atp_target_is_not_multiplied_by_daily_directions():
    # PMID 34957398 used a single acute dose; its 400mg comparison is per use.
    product = _product(_row("atp", 200, "mg"), name="ATP", primary_type="pre_workout")
    product["servingSizes"][0].update(minDailyServings=2, maxDailyServings=2)
    assert _dose(product) == 11.4


@pytest.mark.parametrize("quantity,hidden,expected", [(None, False, 0), (None, True, 11.4), (300, False, 11.4)])
def test_no_botanical_benchmark_does_not_hide_missing_capture(quantity, hidden, expected):
    row = _botanical_ingredient(name="Elderflower", standard_name="Elderflower",
                               canonical_id="elderflower", quantity=quantity, unit="mg")
    if hidden:
        row["isNestedIngredient"] = True
    assert _dose(_botanical_product(row)) == expected


def test_sports_contributions_record_each_serving_and_directed_daily_amount():
    product = _product(_row("creatine_monohydrate", 5, "Gram(s)"),
                       _row("beta_alanine", 1, "Gram(s)"),
                       name="Creatine + Beta-Alanine", primary_type="pre_workout")
    product["servingSizes"][0].update(minDailyServings=1, maxDailyServings=2)
    contributions = score_dose(product)["metadata"]["dose_contributions"]
    assert [(c["ingredient"], c["amount_per_serving"], c["amount_at_minimum"],
             c["amount_at_maximum"], c["amount_unit"]) for c in contributions] == [
                 ("creatine", 5, 5, 10, "g"), ("beta_alanine", 1, 1, 2, "g")]


def test_offlist_sports_receipt_keeps_each_declared_purpose_assessment():
    product = _product(_row("l_carnitine", 1, "Gram(s)"),
                       _row("branched_chain_amino_acids", 250, "mg"),
                       name="Carnitine 1000 + BCAA", primary_type="pre_workout")
    artifact = build_scored_artifact(product)
    dose = artifact["quality_pillars_v4"]["dose"]
    receipt = dose["explanation"]["dose_receipt"]
    assert dose["score"] == 11.4
    assert receipt["reconciles"] is True
    assert receipt["aggregation"] == "co_primary_average"
    assert {c["ingredient"] for c in receipt["contributions"]} == {"l_carnitine", "bcaa"}
    assert {c["assessment"] for c in receipt["contributions"]} == {"no_benchmark_neutral", "bcaa_completed_no_general_benchmark"}


@pytest.mark.parametrize('amount', [1, 3, 4])
def test_declared_offlist_sports_purpose_gets_one_equal_vote(amount):
    product = _product(_row('creatine_monohydrate', 3, 'g'),
                       _row('l_tyrosine', amount, 'g', name='L-Tyrosine'),
                       name='Creatine + L-Tyrosine', primary_type='pre_workout')
    artifact = build_scored_artifact(product)
    dimension = artifact['_v4_module_breakdown']['dimensions']['dose']
    assert artifact['quality_pillars_v4']['dose']['score'] == 15.7
    assert dimension['metadata']['dose_aggregation'] == 'co_primary_average'
    assert [(row['ingredient'], row['credit_raw']) for row in dimension['metadata']['dose_contributions']] == [
        ('creatine', 20), ('l_tyrosine', 11.4)]


def test_lost_declared_offlist_sports_amount_keeps_the_assessment_incomplete():
    product = _product(_row('creatine_monohydrate', 3, 'g'),
                       _row('l_tyrosine', None, 'g', name='L-Tyrosine'),
                       name='Creatine + L-Tyrosine', primary_type='pre_workout')
    dimension = build_scored_artifact(product)['_v4_module_breakdown']['dimensions']['dose']
    assert dimension['score'] is None
    assert dimension['metadata']['assessment_status'] == 'incomplete'
    assert [row['ingredient'] for row in dimension['metadata']['dose_contributions']] == ['creatine', 'l_tyrosine']


@pytest.mark.parametrize('amount', [0.1, 4])
def test_incidental_offlist_mass_does_not_create_a_sports_purpose_vote(amount):
    product = _product(_row('creatine_monohydrate', 3, 'g'),
                       _row('l_tyrosine', amount, 'g', name='L-Tyrosine'),
                       name='Creatine Monohydrate', primary_type='pre_workout')
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] == 20
    assert [row['ingredient'] for row in artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['dose_contributions']] == ['creatine']


def test_declared_offlist_nutrient_uses_its_existing_generic_contribution_owner():
    product = _product(_row('creatine_monohydrate', 3, 'g'), _row('magnesium', 42, 'mg'),
                       name='Creatine + Magnesium', primary_type='pre_workout')
    product['rda_ul_data'] = {'adequacy_results': [{'canonical_id': 'magnesium', 'nutrient': 'Magnesium',
        'amount': 42, 'unit': 'mg', 'per_day_min': 42, 'per_day_max': 42,
        'rda_ai': 420, 'pct_rda': 10}]}
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] == 15
    entries = artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['dose_contributions']
    assert entries[1]['ingredient'] == 'magnesium'
    assert entries[1]['assessment'] == 'contribution_policy_target'
    assert entries[1]['reference_value'] == 84
    assert entries[1]['credit_raw'] == 10


def test_genuinely_hidden_offlist_sports_purpose_keeps_its_neutral_vote():
    tyrosine = {**_row('l_tyrosine', None, 'g', name='L-Tyrosine'), 'isNestedIngredient': True}
    product = _product(_row('creatine_monohydrate', 3, 'g'), tyrosine,
                       name='Creatine + L-Tyrosine', primary_type='pre_workout')
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] == 15.7
    assert artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['dose_contributions'][1]['assessment'] == 'hidden_amount_neutral'


@pytest.mark.parametrize('identity,amount,unit,name', [
    ('protein', 20, 'g', 'Whey Protein'),
    ('creatine_monohydrate', 3, 'g', 'Creatine Monohydrate'),
    ('beta_alanine', 4, 'g', 'Beta-Alanine'),
    ('hmb', 3, 'g', 'HMB-Ca'),
    ('caffeine', 200, 'mg', 'Caffeine'),
])
@pytest.mark.parametrize('groups,expected', [
    (['Children 4 or More Years of Age'], 11.4),
    (['Pregnant Women'], 11.4),
    (['Lactating'], 11.4),
    (['Adult (18 - 50 Years)', 'Children 4 or More Years of Age'], 11.4),
    (['Adult Female (18 - 50 Years)', 'Pregnant Women'], 11.4),
    (['Women (not pregnant or lactating)'], 20),
    (['Adult (18 - 50 Years)'], 20),
    (['Seniors/Mature (>50 Years) - Women ONLY'], 20),
    ([], 20),
])
def test_sports_adult_targets_require_the_whole_label_population(identity, amount, unit, name, groups, expected):
    from test_v4_sports_dose_p171 import _declared_protein_row

    rows = ([_row('whey_protein', 25, 'g', name='Whey Protein'), _declared_protein_row(amount)]
            if identity == 'protein' else [_row(identity, amount, unit, name=name)])
    product = _product(*rows, name=name, primary_type='protein_powder' if identity == 'protein' else 'pre_workout')
    product['targetGroups'] = groups
    artifact = build_scored_artifact(product)
    assert artifact['quality_pillars_v4']['dose']['score'] == expected
    assert artifact['quality_assessment_status'] == 'complete'
    entry = artifact['_v4_module_breakdown']['dimensions']['dose']['metadata']['dose_contributions'][0]
    assert entry['assessment'].endswith('_contribution_policy') is (expected == 20)
    assert artifact['quality_pillars_v4']['dose']['explanation']['dose_receipt']['reconciles'] is True


@pytest.mark.parametrize('groups', [
    ['Children 4 or More Years of Age'], ['Pregnant Women'], ['Lactating'],
])
@pytest.mark.parametrize('hidden', [False, True])
def test_inapplicable_sports_reference_keeps_hidden_and_lost_amounts_distinct(groups, hidden):
    row = _row('creatine_monohydrate', None, 'g', name='Creatine Monohydrate')
    if hidden:
        row['isNestedIngredient'] = True
    product = _product(row, name='Creatine Monohydrate', primary_type='pre_workout')
    product['targetGroups'] = groups
    dose = score_dose(product)
    if hidden:
        assert dose['score'] == 11.4
        assert dose['metadata']['dose_basis'] == 'hidden_amount_neutral'
        assert dose['metadata'].get('assessment_status') != 'incomplete'
    else:
        assert dose['score'] is None
        assert dose['metadata']['assessment_status'] == 'incomplete'
        assert dose['metadata']['reason_code'] == 'unresolved_source_quantity'
