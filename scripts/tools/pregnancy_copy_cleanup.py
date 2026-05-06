#!/usr/bin/env python3
"""Pregnancy batch targeted cleanup — 8 items per clinical team review."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update_preg(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'pregnancy':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return True
    return False


def remove_preg(canonical_id):
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            cr_list = r.get('condition_rules', [])
            for j, cr in enumerate(cr_list):
                if cr.get('condition_id') == 'pregnancy':
                    cr_list.pop(j)
                    changes.append(f'{canonical_id}: REMOVED duplicate pregnancy rule')
                    return True
    return False


# 1. Bitter orange: contraindicated → avoid
update_preg('BANNED_BITTER_ORANGE',
    severity='avoid',
    alert_headline='Stimulant — avoid in pregnancy',
    alert_body=(
        'Bitter orange contains synephrine, a stimulant that can stress '
        'the cardiovascular system. If you are pregnant, avoid supplement-'
        'dose bitter orange.'
    ),
)

# 2. Dedupe yohimbe — remove the RISK_YOHIMBE pregnancy rule (keep yohimbe)
remove_preg('RISK_YOHIMBE')

# Update the kept yohimbe entry
update_preg('yohimbe',
    alert_headline='Stimulant — do not use in pregnancy',
)

# 3. Butterbur: improve PA-status copy
update_preg('butterbur',
    alert_headline='PA-containing butterbur is unsafe',
    alert_body=(
        'Raw or non-PA-free butterbur can contain pyrrolizidine alkaloids '
        'that are toxic to the liver. If PA-free status is not verified, '
        'avoid during pregnancy.'
    ),
)

# 4. Feverfew: remove unverified Cochrane/ACOG attribution from mechanism
for r in rules:
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    if cid == 'feverfew':
        for cr in r.get('condition_rules', []):
            if cr.get('condition_id') == 'pregnancy':
                mech = cr.get('mechanism', '')
                if 'Cochrane and ACOG recommend' in mech:
                    cr['mechanism'] = mech.replace(
                        'Cochrane and ACOG recommend avoidance during pregnancy.',
                        'It is not recommended during pregnancy due to uterotonic and bleeding concerns.'
                    )
                    changes.append('feverfew.mechanism: removed unverified Cochrane/ACOG attribution')
                cr['alert_body'] = (
                    'Feverfew has historical emmenagogue use and uterine-related '
                    'concerns. If you are pregnant, do not use it unless '
                    'specifically directed by your obstetric clinician.'
                )
                changes.append('feverfew.alert_body')
        break

# 5. Senna: soften uterine-contraction language
update_preg('senna',
    alert_headline='Use stimulant laxatives with guidance',
    alert_body=(
        'Senna may be used during pregnancy in some cases, but chronic '
        'or high-dose use can cause cramping, dehydration, or electrolyte '
        'shifts. Use with obstetric guidance.'
    ),
)

# 6. Wild yam: avoid/probable → avoid/theoretical
update_preg('wild_yam',
    evidence_level='theoretical',
    alert_headline='Hormone-active claims are uncertain',
    alert_body=(
        'Wild yam is marketed for hormone support, but pregnancy safety '
        'data are limited. Avoid concentrated wild yam supplements during '
        'pregnancy unless your obstetric clinician recommends them.'
    ),
)

# 7. NAC: clarify clinical vs supplement use
update_preg('nac',
    alert_body=(
        'NAC is used clinically in some pregnancy-related contexts, but '
        'high-dose or chronic supplement use should be supervised. Use '
        'with obstetric guidance.'
    ),
)

# Validate
for r in rules:
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'pregnancy':
            sr = r.get('subject_ref', {})
            cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

remaining = sum(1 for r in rules for cr in r.get('condition_rules', [])
                if cr.get('condition_id') == 'pregnancy')

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} changes. Pregnancy rules: 41 → {remaining}')
for c in changes: print(f'  \u2713 {c}')
