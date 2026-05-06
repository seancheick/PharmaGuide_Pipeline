#!/usr/bin/env python3
"""Autoimmune batch copy cleanup per clinical team review.

Key changes:
- Echinacea, cat's claw, elderberry: avoid→caution (not proven universal autoimmune avoid)
- Vitamin D: caution→informational (immunomodulatory, not immune-stimulant)
- Rhodiola: caution/probable→monitor/theoretical
- Probiotics: re-gate from autoimmune to severely_immunocompromised profile_flag
- Fix templated body copy across 7 entries
- Astragalus: keep avoid/probable (strongest evidence)
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def find_autoimmune_rule(canonical_id):
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for j, cr in enumerate(r.get('condition_rules', [])):
                if isinstance(cr, dict) and cr.get('condition_id') == 'autoimmune':
                    return i, j
    raise KeyError(f'Autoimmune rule not found for {canonical_id}')


def update(canonical_id, **fields):
    ri, ci = find_autoimmune_rule(canonical_id)
    cr = rules[ri]['condition_rules'][ci]
    for k, v in fields.items():
        old = cr.get(k, '')
        if old != v:
            cr[k] = v
            changes.append(f'{canonical_id}.{k}: updated')


# ── 1. Astragalus — keep strong, improve body ──
update('astragalus',
    alert_headline='Not recommended with autoimmune conditions',
    alert_body=(
        'Astragalus may stimulate immune activity and may interfere with '
        'immune-suppressing treatment. If you have an autoimmune condition, '
        'avoid use unless your clinician specifically recommends it.'
    ),
)

# ── 2. Echinacea — avoid→caution ──
update('echinacea',
    severity='caution',
    alert_headline='Immune-active herb — use caution',
    alert_body=(
        'Echinacea may affect immune activity and may interact with '
        'immune-suppressing medicines. If you have an autoimmune condition, '
        'review use with your clinician.'
    ),
)

# ── 3. Cat's claw — avoid→caution ──
update('cat_s_claw',
    severity='caution',
    alert_headline='Immune-active herb — use caution',
    alert_body=(
        'Cat\u2019s claw may affect immune-cell signaling. If you have an '
        'autoimmune condition or take immune-suppressing medication, review '
        'use with your clinician.'
    ),
)

# ── 4. Elderberry — avoid→caution ──
update('elderberry',
    severity='caution',
    alert_headline='Immune-active supplement — use caution',
    alert_body=(
        'Elderberry may affect cytokine and immune signaling. If you have an '
        'autoimmune condition or use immune-suppressing medication, review it '
        'with your clinician.'
    ),
)

# ── 5. Andrographis — keep caution, fix body ──
update('andrographis',
    alert_headline='Immune-active herb — use caution',
    alert_body=(
        'Andrographis may stimulate immune pathways. If you have an '
        'autoimmune condition or take immune-suppressing medication, review '
        'use with your clinician.'
    ),
)

# ── 6. Cordyceps — keep caution, fix body ──
update('cordyceps',
    alert_headline='Immune-active mushroom — use caution',
    alert_body=(
        'Cordyceps may affect immune signaling. If you have an autoimmune '
        'condition or take immune-suppressing medication, review use with '
        'your clinician.'
    ),
)

# ── 7. Reishi — keep caution, fix body ──
update('reishi',
    alert_headline='Immune-active mushroom — use caution',
    alert_body=(
        'Reishi may affect immune signaling. If you have an autoimmune '
        'condition or take immune-suppressing medication, review use with '
        'your clinician.'
    ),
)

# ── 8. Rhodiola — caution/probable → monitor/theoretical ──
update('rhodiola',
    severity='monitor',
    evidence_level='theoretical',
    alert_headline='May affect immune signaling',
    alert_body=(
        'Rhodiola has immune-modulating effects in early research. If your '
        'autoimmune condition is active or you use immune-suppressing '
        'medicine, review it with your clinician.'
    ),
)

# ── 9. Vitamin D — caution/probable → informational/probable ──
update('vitamin_d',
    severity='informational',
    alert_headline='Use labs to guide vitamin D',
    alert_body=(
        'Vitamin D affects immune regulation and is often monitored in '
        'autoimmune care. Use blood levels and clinician guidance to avoid '
        'under- or over-supplementing.'
    ),
)

# ── 10. Probiotics — re-gate from autoimmune to severely_immunocompromised ──
ri, ci = find_autoimmune_rule('probiotics')
cr = rules[ri]['condition_rules'][ci]
# Change the gate from condition:autoimmune to profile_flag:severely_immunocompromised
cr['profile_gate'] = {
    'gate_type': 'profile_flag',
    'requires': {
        'conditions_any': [],
        'drug_classes_any': [],
        'profile_flags_any': ['severely_immunocompromised'],
    },
    'excludes': {
        'conditions_any': [],
        'drug_classes_any': [],
        'profile_flags_any': [],
        'product_forms_any': [],
        'nutrient_forms_any': [],
    },
    'dose': None,
}
# Also update condition_id to reflect the new scope
cr['condition_id'] = 'immunocompromised'
cr['alert_headline'] = 'Caution if severely immunocompromised'
cr['alert_body'] = (
    'If you are severely immunocompromised, on chemotherapy, or have '
    'an organ transplant, live probiotic organisms carry a small '
    'infection risk. Discuss with your clinician.'
)
cr['informational_note'] = (
    'Probiotic infection risk applies to severe immunocompromise, not '
    'general autoimmune conditions.'
)
changes.append('probiotics: re-gated from autoimmune→severely_immunocompromised profile_flag')

# ── Validate lengths ──
for cid in ['astragalus', 'echinacea', 'cat_s_claw', 'elderberry',
            'andrographis', 'cordyceps', 'reishi', 'rhodiola', 'vitamin_d',
            'probiotics']:
    for r in rules:
        sr = r.get('subject_ref', {})
        rcid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if rcid == cid:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') in ('autoimmune', 'immunocompromised'):
                    hl = cr.get('alert_headline', '')
                    ab = cr.get('alert_body', '')
                    assert 20 <= len(hl) <= 60, f'{cid} headline len {len(hl)}: "{hl}"'
                    assert 60 <= len(ab) <= 200, f'{cid} alert_body len {len(ab)}: "{ab}"'
            break

# ── Write ──
with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} autoimmune copy changes:')
for c in changes:
    print(f'  \u2713 {c}')
