#!/usr/bin/env python3
"""Thyroid disorder batch cleanup per clinical team review."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update_thyroid(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'thyroid_disorder':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return


# 1. Ashwagandha — keep caution, improve copy
update_thyroid('ashwagandha',
    alert_headline='May raise thyroid hormone activity',
    alert_body=(
        'Ashwagandha has been linked to increased thyroid hormone activity '
        'and rare thyrotoxicosis reports. If you have thyroid disease or '
        'take thyroid medication, review use with your clinician.'
    ),
)

# 2. Iodine — keep caution, dose-gate language
update_thyroid('iodine',
    alert_headline='High iodine may disrupt thyroid control',
    alert_body=(
        'Iodine is essential for thyroid function, but high-dose iodine or '
        'kelp supplements can disrupt thyroid control in people with thyroid '
        'disease. Review iodine dose with your clinician.'
    ),
)

# 3. Acetyl-L-carnitine — broader copy for mixed thyroid population
update_thyroid('acetyl_l_carnitine',
    alert_headline='May affect thyroid hormone action',
    alert_body=(
        'L-carnitine may reduce some thyroid hormone effects in tissues. '
        'If you have thyroid disease or use thyroid medication, review use '
        'with your clinician.'
    ),
)

# 4. Biotin — lab interference, consider established
update_thyroid('vitamin_b7_biotin',
    evidence_level='established',
    alert_headline='May interfere with thyroid lab tests',
    alert_body=(
        'High-dose biotin can distort some thyroid blood tests, including '
        'TSH and thyroid hormone assays. Tell your clinician and lab if you '
        'take biotin before thyroid testing.'
    ),
)

# 5. Selenium — caution → informational, dose-gate
update_thyroid('selenium',
    severity='informational',
    alert_headline='Keep selenium within thyroid-safe range',
    alert_body=(
        'Selenium is involved in thyroid hormone metabolism, but excessive '
        'intake can be harmful. If you have thyroid disease, avoid stacking '
        'multiple high-selenium products without clinician guidance.'
    ),
)

# 6. Bacopa — caution/theoretical → monitor/theoretical
update_thyroid('bacopa',
    severity='monitor',
    alert_headline='Thyroid effects are uncertain',
    alert_body=(
        'Animal studies suggest bacopa may affect thyroid hormone levels, '
        'but human relevance is unclear. If you have thyroid disease, '
        'monitor symptoms and labs with your clinician.'
    ),
)

# 7. Quercetin — caution/probable → monitor/theoretical
update_thyroid('quercetin',
    severity='monitor',
    evidence_level='theoretical',
    alert_headline='High-dose quercetin may affect thyroid',
    alert_body=(
        'Quercetin may affect thyroid-related enzymes in preclinical '
        'research. Clinical relevance is uncertain. If you have thyroid '
        'disease, use high-dose supplements with clinician guidance.'
    ),
)

# 8. Genistein — monitor/caution, isoflavone-focused
update_thyroid('genistein',
    severity='monitor',
    alert_headline='Isoflavones may affect thyroid balance',
    alert_body=(
        'High-dose isoflavone supplements may affect thyroid hormone '
        'synthesis, especially when iodine intake is low or thyroid disease '
        'is present. Review concentrated isoflavone use with your clinician.'
    ),
)

# 9. Red clover — monitor/caution
update_thyroid('red_clover',
    severity='monitor',
    alert_headline='Isoflavones may affect thyroid balance',
    alert_body=(
        'Red clover contains isoflavones that may affect thyroid enzyme '
        'activity. If you have thyroid disease, review concentrated red '
        'clover supplements with your clinician.'
    ),
)

# 10. L-tyrosine — keep caution, improve copy
update_thyroid('l_tyrosine',
    alert_headline='Thyroid hormone precursor — use caution',
    alert_body=(
        'L-tyrosine is used to make thyroid hormones, but supplement '
        'effects vary. If you have thyroid disease or take thyroid '
        'medication, review high-dose tyrosine with your clinician.'
    ),
)

# Validate
for r in rules:
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'thyroid_disorder':
            sr = r.get('subject_ref', {})
            cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} thyroid changes:')
for c in changes: print(f'  \u2713 {c}')
