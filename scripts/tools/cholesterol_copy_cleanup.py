#!/usr/bin/env python3
"""High cholesterol batch copy cleanup."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'high_cholesterol':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return


update('BANNED_RED_YEAST_RICE',
    alert_headline='Red yeast rice can act like a statin',
    alert_body=(
        'Red yeast rice contains monacolin K, which is chemically identical '
        'to lovastatin. If you take a statin or manage cholesterol, discuss '
        'red yeast rice with your clinician before use.'
    ),
)

update('coq10',
    alert_headline='Often discussed with statin therapy',
    alert_body=(
        'CoQ10 is commonly discussed alongside statin therapy because '
        'statins may reduce CoQ10 levels. Evidence for symptom benefit is '
        'mixed. If you take a statin, ask your clinician about CoQ10.'
    ),
)

update('berberine_supplement',
    alert_body=(
        'Berberine has demonstrated modest lipid-lowering effects in '
        'clinical trials. If you manage cholesterol with medication, '
        'mention berberine to your clinician to avoid unexpected overlap.'
    ),
)

update('citrus_bergamot',
    alert_body=(
        'Bergamot polyphenols may modestly reduce LDL cholesterol. If you '
        'manage cholesterol with medication, mention bergamot supplements '
        'to your clinician.'
    ),
)

update('garlic',
    alert_body=(
        'Garlic supplements may modestly reduce total cholesterol and '
        'LDL-C. If you manage cholesterol with medication, mention garlic '
        'supplements to your clinician.'
    ),
)

update('vitamin_b3_niacin',
    alert_headline='High-dose niacin needs clinician guidance',
    alert_body=(
        'Pharmacologic-dose niacin can shift HDL, LDL, and triglycerides. '
        'If you manage cholesterol with medication, do not add high-dose '
        'niacin without clinician guidance. Multivitamin doses are fine.'
    ),
)

# Validate
for r in rules:
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'high_cholesterol':
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            sr = r.get('subject_ref', {})
            cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} high_cholesterol changes:')
for c in changes: print(f'  \u2713 {c}')
