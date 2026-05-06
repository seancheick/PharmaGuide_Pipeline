#!/usr/bin/env python3
"""Seizure disorder batch copy cleanup per clinical team review."""
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
                if cr.get('condition_id') == 'seizure_disorder':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return


# 1. CBD
update('BANNED_CBD_US',
    alert_headline='CBD — seizure clinician guidance',
    alert_body=(
        'Prescription cannabidiol treats specific seizure disorders, but '
        'OTC CBD products vary in dose and purity. If you have seizures or '
        'take antiseizure medication, use CBD only with clinician guidance.'
    ),
)

# 2. Evening primrose oil — caution/probable → monitor/theoretical
update('evening_primrose_oil',
    severity='monitor',
    evidence_level='theoretical',
    alert_headline='Seizure evidence is mixed',
    alert_body=(
        'Older reports raised concern that evening primrose oil might affect '
        'seizure threshold, but later reviews questioned this link. If you '
        'have epilepsy, review use with your clinician.'
    ),
)

# 3. Borage seed oil — caution/probable → monitor/theoretical
update('borage_seed_oil',
    severity='monitor',
    evidence_level='theoretical',
    alert_headline='Seizure-threshold evidence is limited',
    alert_body=(
        'Borage seed oil contains GLA, which has been discussed in older '
        'seizure-threshold concerns. Evidence is limited. If you have '
        'epilepsy, review use with your clinician.'
    ),
)

# 4. Ginkgo — keep caution, improve copy
update('ginkgo',
    alert_headline='Ginkgo may lower seizure threshold',
    alert_body=(
        'Ginkgo seed and some products can contain ginkgotoxin, which may '
        'provoke seizures. If you have epilepsy or take antiseizure '
        'medication, review ginkgo use with your clinician.'
    ),
)

# 5. Guarana — keep caution, dose-gate language
update('guarana',
    alert_headline='High caffeine may affect seizures',
    alert_body=(
        'Guarana can add significant caffeine. High caffeine intake may '
        'lower seizure threshold in some people. If you have epilepsy, '
        'review high-caffeine supplements with your clinician.'
    ),
)

# 6. Huperzine A — keep caution/theoretical, improve copy
update('huperzine_a',
    alert_headline='Cholinergic effect — seizure caution',
    alert_body=(
        'Huperzine A affects acetylcholine signaling in the brain. If you '
        'have epilepsy or take antiseizure medication, use only with '
        'clinician guidance.'
    ),
)

# 7. Kava — keep caution, medication-interaction framing
update('kavalactones',
    alert_headline='May interact with seizure medications',
    alert_body=(
        'Kava can affect the central nervous system and liver drug '
        'metabolism. If you take antiseizure medication, review kava with '
        'your clinician before use.'
    ),
)

# 8. Melatonin — caution/probable → monitor/probable
update('melatonin',
    severity='monitor',
    alert_headline='Seizure effects can vary',
    alert_body=(
        'Melatonin may affect sleep and seizure patterns differently across '
        'people. If you have epilepsy, start only with clinician guidance, '
        'especially if seizures are unstable.'
    ),
)

# Validate
for r in rules:
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'seizure_disorder':
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} seizure changes:')
for c in changes: print(f'  \u2713 {c}')
