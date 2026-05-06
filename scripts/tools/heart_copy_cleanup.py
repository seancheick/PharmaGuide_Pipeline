#!/usr/bin/env python3
"""Heart disease batch cleanup per clinical team review.

Key principle: heart_disease is a broad MVP gate. Copy must say
"if you have a heart condition" not diagnosis-specific claims.
Severity should be conservative (caution/monitor/informational),
not avoid, since we can't distinguish CAD from HF from arrhythmia.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update_hd(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'heart_disease':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return


# 1. CoQ10 — monitor → informational, reframe as adjunctive
update_hd('coq10',
    severity='informational',
    alert_headline='Discuss CoQ10 with your heart clinician',
    alert_body=(
        'CoQ10 has been studied in some heart conditions, but it should '
        'not replace prescribed heart medication. Ask your clinician if it '
        'fits your care plan.'
    ),
)

# 2. Omega-3 — reframe, not danger
update_hd('omega_3',
    severity='informational',
    alert_headline='Review high-dose omega-3 with clinician',
    alert_body=(
        'Omega-3s may be appropriate for some heart-risk profiles, but '
        'high doses can matter for bleeding risk, rhythm history, or '
        'medication plans. Review with your clinician.'
    ),
)

# 3. Magnesium — informational
update_hd('magnesium',
    severity='informational',
    alert_headline='Discuss magnesium with your clinician',
    alert_body=(
        'Magnesium is relevant in some heart contexts, but excess can be '
        'an issue with kidney disease or certain medications. Ask your '
        'clinician about dose and monitoring.'
    ),
)

# 4. Vitamin D — dose/lab-gate language
update_hd('vitamin_d',
    alert_headline='High-dose vitamin D needs monitoring',
    alert_body=(
        'Normal vitamin D is generally fine, but very high doses can cause '
        'hypercalcemia. If you have a heart condition, use blood levels '
        'and clinician guidance for dosing.'
    ),
)

# 5. Calcium — supplement-specific, dose-gate
update_hd('calcium',
    alert_headline='Supplemental calcium — review with clinician',
    alert_body=(
        'Some studies link calcium supplements with a modest increase in '
        'cardiovascular events. If you have a heart condition, review your '
        'total calcium intake with your clinician.'
    ),
)

# 6. L-arginine — caution, broad "heart condition" language (not post-MI specific yet)
update_hd('l_arginine',
    alert_headline='Review L-arginine with your heart clinician',
    alert_body=(
        'L-arginine affects blood vessel function and may not be '
        'appropriate for all heart conditions. If you have a heart '
        'condition, use only with clinician guidance.'
    ),
)

# 7. Potassium — medication-aware copy
update_hd('potassium',
    alert_headline='May raise potassium with heart medications',
    alert_body=(
        'If you have a heart condition and take medications that raise '
        'potassium (ACE inhibitors, ARBs, spironolactone), extra potassium '
        'can be risky. Ask your clinician before adding potassium.'
    ),
)

# 8. Licorice — strong, rhythm + potassium
update_hd('licorice_root',
    alert_headline='May affect blood pressure and heart rhythm',
    alert_body=(
        'Licorice can lower potassium and raise blood pressure, which may '
        'matter if you have a heart condition or take heart medications. '
        'This does not apply to DGL licorice.'
    ),
)

# 9. Hawthorn — clinician-guided, not fear
update_hd('hawthorn',
    alert_headline='Use with clinician guidance in heart disease',
    alert_body=(
        'Hawthorn may affect heart function and has been studied in heart '
        'failure. If you use heart medications, review hawthorn with your '
        'clinician.'
    ),
)

# 10. Guarana — stimulant
update_hd('guarana',
    alert_headline='Stimulant — review with heart clinician',
    alert_body=(
        'Guarana adds caffeine that can affect heart rate and blood '
        'pressure. If you have a heart condition, review caffeine-'
        'containing supplements with your clinician.'
    ),
)

# 11. Yerba mate — stimulant
update_hd('yerba_mate',
    alert_headline='Stimulant — review with heart clinician',
    alert_body=(
        'Yerba mate contains caffeine that can affect heart rate and blood '
        'pressure. If you have a heart condition, review caffeine-'
        'containing supplements with your clinician.'
    ),
)

# 12. Icariin — PDE5/medication context
update_hd('icariin',
    alert_headline='PDE5-like effect — review with clinician',
    alert_body=(
        'Icariin may have PDE5-inhibitor-like effects on blood vessels. If '
        'you have a heart condition or take nitrates or blood pressure '
        'medicines, review use with your clinician.'
    ),
)

# Validate
for r in rules:
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'heart_disease':
            sr = r.get('subject_ref', {})
            cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} heart disease changes:')
for c in changes: print(f'  \u2713 {c}')
