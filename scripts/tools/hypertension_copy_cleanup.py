#!/usr/bin/env python3
"""Hypertension batch cleanup per clinical team review."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update_ht(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'hypertension':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return


def remove_ht(canonical_id):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            cr_list = r.get('condition_rules', [])
            for j, cr in enumerate(cr_list):
                if cr.get('condition_id') == 'hypertension':
                    cr_list.pop(j)
                    changes.append(f'{canonical_id}: REMOVED hypertension rule (dedup)')
                    return


# ── 1. Dedup yohimbe ──
remove_ht('RISK_YOHIMBE')
update_ht('yohimbe',
    evidence_level='established',
    alert_body=(
        'If you have high blood pressure, avoid yohimbe. It stimulates '
        'adrenergic activity and may raise blood pressure or heart rate.'
    ),
)

# ── 2. Dedup licorice ──
remove_ht('licorice_root')
update_ht('licorice',
    alert_headline='Licorice may raise blood pressure',
    alert_body=(
        'Glycyrrhizin in licorice can raise blood pressure, cause sodium '
        'retention, and lower potassium. If you have high blood pressure, '
        'avoid licorice unless it is DGL (deglycyrrhizinated).'
    ),
)

# ── 3. Bitter orange ──
update_ht('RISK_BITTER_ORANGE',
    alert_headline='Stimulant — may raise blood pressure',
    alert_body=(
        'Bitter orange contains synephrine, which can raise blood pressure '
        'or heart rate, especially with caffeine. If you have high blood '
        'pressure, avoid supplement-dose bitter orange.'
    ),
)

# ── 4. Caffeine ──
update_ht('caffeine',
    alert_body=(
        'Caffeine can acutely raise blood pressure through adenosine '
        'antagonism. If you have high blood pressure, review your total '
        'caffeine intake with your clinician.'
    ),
)

# ── 5. Guarana ──
update_ht('guarana',
    alert_headline='Stimulant source — may raise BP',
    alert_body=(
        'Guarana adds caffeine load that can raise blood pressure. If you '
        'have high blood pressure, review caffeine-containing supplements '
        'with your clinician.'
    ),
)

# ── 6. Yerba mate ──
update_ht('yerba_mate',
    alert_headline='Stimulant source — may raise BP',
    alert_body=(
        'Yerba mate contains caffeine that can raise blood pressure. If you '
        'have high blood pressure, review caffeine-containing supplements '
        'with your clinician.'
    ),
)

# ── 7. Potassium — medication-aware copy ──
update_ht('potassium',
    alert_headline='May raise potassium with some BP meds',
    alert_body=(
        'If you take ACE inhibitors, ARBs, or potassium-sparing medicines, '
        'extra potassium can raise blood potassium too much. Use potassium '
        'supplements only with clinician guidance.'
    ),
)

# ── 8. St. John's wort — medication-interaction framing ──
update_ht('st_johns_wort',
    alert_headline='May reduce some BP medication levels',
    alert_body=(
        'St. John\u2019s wort can induce drug-metabolizing enzymes and may '
        'reduce levels of some blood pressure medicines. If you take BP '
        'medication, review with your clinician before combining.'
    ),
)

# ── 9. Green tea extract — soften, nadolol-focused ──
update_ht('green_tea_extract',
    severity='monitor',
    alert_headline='May reduce nadolol absorption',
    alert_body=(
        'Green tea extract may reduce absorption of nadolol through '
        'intestinal transporter effects. If you take nadolol or blood '
        'pressure medication, ask your clinician about timing.'
    ),
)

# ── 10. Ginkgo — soften ──
update_ht('ginkgo',
    severity='monitor',
    alert_headline='May affect some BP medications',
    alert_body=(
        'Ginkgo may affect drug metabolism and could change effects of '
        'some blood pressure medicines. If you take BP medication, review '
        'ginkgo use with your clinician.'
    ),
)

# ── 11. Black seed oil — caution → monitor ──
update_ht('black_seed_oil',
    severity='monitor',
    alert_body=(
        'Black seed oil may modestly lower blood pressure. If you take '
        'blood pressure medication, monitor for dizziness or low BP '
        'symptoms and mention it to your clinician.'
    ),
)

# ── 12. Garlic — improve body ──
update_ht('garlic',
    alert_body=(
        'Garlic supplements may modestly lower blood pressure. If you take '
        'blood pressure medication, monitor for dizziness or low BP '
        'symptoms.'
    ),
)

# ── 13. Hawthorn ──
update_ht('hawthorn',
    alert_headline='May add to BP-medication effects',
    alert_body=(
        'Hawthorn may modestly lower blood pressure. If you take blood '
        'pressure medication, review hawthorn use with your clinician to '
        'avoid excessive BP lowering.'
    ),
)

# ── 14. L-arginine ──
update_ht('l_arginine',
    alert_body=(
        'L-arginine may modestly lower blood pressure through nitric oxide '
        'pathways. If you take BP medications or nitrates, review use with '
        'your clinician.'
    ),
)

# ── 15. Rhodiola / Tribulus — keep low ──
update_ht('rhodiola',
    alert_headline='Blood-pressure evidence is limited',
    alert_body=(
        'Rhodiola may have mild effects on blood pressure in early '
        'research. If you have high blood pressure, mention it to your '
        'clinician.'
    ),
)

update_ht('tribulus',
    alert_headline='Blood-pressure evidence is limited',
    alert_body=(
        'Tribulus may have mild effects on blood pressure in early '
        'research. If you have high blood pressure, mention it to your '
        'clinician.'
    ),
)

# Validate
for r in rules:
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'hypertension':
            sr = r.get('subject_ref', {})
            cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

remaining = sum(1 for r in rules for cr in r.get('condition_rules', [])
                if cr.get('condition_id') == 'hypertension')

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} changes. Hypertension rules: 19 → {remaining}')
for c in changes: print(f'  \u2713 {c}')
