"""The safety gate records whether its ingredient assessment completed.

Facts only: resolver failures and capture gaps are listed, never silently
treated as a clean label, and they do not change the gate's verdict.
"""
from scoring_v4.gate_safety import evaluate_safety_gate


def _product(actives, inactives=()):
    return {'id': 'TEST', 'product_name': 'Test', 'activeIngredients': list(actives),
            'inactiveIngredients': list(inactives)}


def test_a_captured_label_completes_the_assessment():
    result = evaluate_safety_gate(_product([{'name': 'Vitamin C', 'standardName': 'Vitamin C'}]))
    assert result.ingredient_assessment_complete is True
    assert result.ingredient_assessment_errors == []


def test_an_empty_active_panel_is_not_a_clean_label():
    result = evaluate_safety_gate(_product([]))
    assert result.ingredient_assessment_complete is False
    assert 'capture_unavailable:activeIngredients' in result.ingredient_assessment_errors


def test_a_nameless_row_is_a_capture_gap():
    result = evaluate_safety_gate(_product([{'name': ''}]))
    assert 'capture_unavailable:activeIngredients[0]' in result.ingredient_assessment_errors


def test_the_facts_do_not_change_the_verdict():
    complete = evaluate_safety_gate(_product([{'name': 'Vitamin C', 'standardName': 'Vitamin C'}]))
    gap = evaluate_safety_gate(_product([{'name': 'Vitamin C', 'standardName': 'Vitamin C'}, {'name': ''}]))
    assert complete.verdict == gap.verdict
