#!/usr/bin/env python3
"""Breastfeeding batch copy cleanup per clinical team review.

Changes:
1. Fenugreek: fix wrong headline (pregnancy → lactation), rewrite body
2. Sage: refine headline + evidence
3. Vitamin B6: raise dose gate threshold (50→200mg), refine copy
4. Wild yam: avoid/probable → caution/theoretical, soften copy
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def find_lactation_rule(canonical_id):
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for j, cr in enumerate(r.get('condition_rules', [])):
                if isinstance(cr, dict) and cr.get('condition_id') == 'lactation':
                    return i, j
    raise KeyError(f'Lactation rule not found for {canonical_id}')


def find_lactation_dose_threshold(canonical_id):
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for j, dt in enumerate(r.get('dose_thresholds', [])):
                if isinstance(dt, dict) and dt.get('target_id') == 'lactation':
                    return i, j
    return None, None


# ── 1. Fenugreek: fix wrong headline + body ──
ri, ci = find_lactation_rule('fenugreek')
cr = rules[ri]['condition_rules'][ci]
cr['alert_headline'] = 'May affect milk supply and digestion'
cr['alert_body'] = (
    'Fenugreek is commonly used for milk supply, but results vary and side '
    'effects can occur. If breastfeeding, use with clinician guidance, '
    'especially if you or your baby develop digestive symptoms.'
)
cr['informational_note'] = (
    'Fenugreek is a common galactagogue — relevant to anyone breastfeeding.'
)
changes.append('fenugreek: fixed wrong pregnancy headline on lactation rule')

# ── 2. Sage: refine headline + downgrade evidence to limited ──
ri, ci = find_lactation_rule('sage')
cr = rules[ri]['condition_rules'][ci]
cr['alert_headline'] = 'May reduce milk supply'
cr['evidence_level'] = 'limited'
cr['alert_body'] = (
    'Concentrated sage is traditionally used to reduce lactation. If you are '
    'breastfeeding and trying to maintain supply, avoid concentrated sage '
    'supplements unless your clinician recommends it.'
)
changes.append('sage: refined headline, evidence probable→limited (LactMed: no studies located)')

# ── 3. Vitamin B6: raise dose gate 50→200mg, refine copy ──
ri, ci = find_lactation_rule('vitamin_b6_pyridoxine')
cr = rules[ri]['condition_rules'][ci]
cr['alert_headline'] = 'High-dose B6 may affect milk supply'
cr['alert_body'] = (
    'Very high doses of B6 have been studied for suppressing lactation. '
    'Normal multivitamin B6 levels do not trigger this concern. Use high-dose '
    'B6 while breastfeeding only with clinician guidance.'
)
changes.append('vitamin_b6_pyridoxine: refined copy')

# Raise dose threshold
dri, dci = find_lactation_dose_threshold('vitamin_b6_pyridoxine')
if dri is not None:
    dt = rules[dri]['dose_thresholds'][dci]
    dt['value'] = 200
    dt['comparator'] = '>='
    dt['severity_if_met'] = 'caution'
    dt['severity_if_not_met'] = 'informational'
    # Update dose inside profile_gate if present
    gate_dose = dt.get('profile_gate', {}).get('dose')
    if gate_dose:
        gate_dose['value'] = 200
        gate_dose['comparator'] = '>='
        gate_dose['severity_if_met'] = 'caution'
        gate_dose['severity_if_not_met'] = 'informational'
    changes.append('vitamin_b6_pyridoxine: dose gate raised 50→200mg, severity_if_not_met avoid→informational')

# ── 4. Wild yam: avoid/probable → caution/theoretical ──
ri, ci = find_lactation_rule('wild_yam')
cr = rules[ri]['condition_rules'][ci]
cr['severity'] = 'caution'
cr['evidence_level'] = 'theoretical'
cr['alert_headline'] = 'Hormone-active claims are uncertain'
cr['alert_body'] = (
    'Wild yam is marketed for hormone support, but breastfeeding safety data '
    'are limited. If breastfeeding, review use with your clinician before '
    'taking concentrated wild yam supplements.'
)
cr['mechanism'] = (
    'Wild yam contains diosgenin, a steroidal saponin marketed as a natural '
    'hormone precursor. The human body does not convert diosgenin into '
    'progesterone. Breastfeeding safety data in humans are absent.'
)
changes.append('wild_yam: avoid/probable → caution/theoretical, softened mechanism')

# Also update pregnancy_lactation block lactation_category for wild_yam
pl = rules[ri].get('pregnancy_lactation', {})
if pl.get('lactation_category') == 'avoid':
    pl['lactation_category'] = 'caution'
    changes.append('wild_yam: pregnancy_lactation.lactation_category avoid→caution')

# ── Validate lengths ──
for cid in ['fenugreek', 'sage', 'vitamin_b6_pyridoxine', 'wild_yam']:
    ri, ci = find_lactation_rule(cid)
    cr = rules[ri]['condition_rules'][ci]
    hl = cr.get('alert_headline', '')
    ab = cr.get('alert_body', '')
    assert 20 <= len(hl) <= 60, f'{cid} headline len {len(hl)}: "{hl}"'
    assert 60 <= len(ab) <= 200, f'{cid} alert_body len {len(ab)}: "{ab}"'

# ── Write ──
with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} breastfeeding copy changes:')
for c in changes:
    print(f'  ✓ {c}')
