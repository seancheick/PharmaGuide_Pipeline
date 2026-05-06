#!/usr/bin/env python3
"""Liver disease batch cleanup per clinical team review.

Key changes:
1. Merge duplicate milk_thistle → one informational rule
2. Fix 6× "Not recommended with liver disease" headlines → specific
3. CBD: "CBD may raise liver enzymes"
4. Black cohosh: "Linked to rare liver injury"
5. Green tea extract: "Green tea extract may injure liver"
6. Kava: "Kava is not recommended with liver disease"
7. Butterbur: "PA-containing butterbur can injure liver"
8. Cascara: avoid→caution, chronic-use language
9. Improve metals copy (copper, iron, manganese)
10. Case-report herbs: soften to case-report language
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update_liver(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'liver_disease':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return True
    return False


# ── 1. Merge duplicate milk_thistle ──
# Remove liver_disease rule from the SECOND milk_thistle entry (index 117)
# Keep the first (index 49) and update it
milk_thistle_hits = []
for i, r in enumerate(rules):
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    if cid == 'milk_thistle':
        for j, cr in enumerate(r.get('condition_rules', [])):
            if cr.get('condition_id') == 'liver_disease':
                milk_thistle_hits.append((i, j))

if len(milk_thistle_hits) > 1:
    # Remove the second one
    ri, ci = milk_thistle_hits[-1]
    rules[ri]['condition_rules'].pop(ci)
    changes.append('milk_thistle: REMOVED duplicate liver_disease rule')

# Update the canonical one
update_liver('milk_thistle',
    severity='informational',
    evidence_level='probable',
    alert_headline='Discuss milk thistle with liver clinician',
    alert_body=(
        'Milk thistle is commonly used by people with liver conditions, but '
        'evidence varies by condition and product. It should not replace '
        'medical care or prescribed treatment.'
    ),
)

# ── 2. CBD ──
update_liver('BANNED_CBD_US',
    alert_headline='CBD may raise liver enzymes',
    alert_body=(
        'CBD is processed by the liver and can raise liver enzymes, '
        'especially at higher doses or with other liver-metabolized '
        'medicines. If you have liver disease, use only with clinician guidance.'
    ),
)

# ── 3. Black cohosh ──
update_liver('black_cohosh',
    alert_headline='Linked to rare liver injury',
    alert_body=(
        'Black cohosh has been linked to rare but serious liver injury in '
        'case reports. If you have liver disease, avoid unless your liver '
        'clinician specifically recommends it.'
    ),
)

# ── 4. Green tea extract ──
update_liver('green_tea_extract',
    alert_headline='Green tea extract may injure the liver',
    alert_body=(
        'Concentrated green tea extract has been linked to rare but serious '
        'liver injury. If you have liver disease, avoid concentrated extract '
        'supplements unless your clinician recommends them.'
    ),
)

# ── 5. Kava/kavalactones ──
update_liver('kavalactones',
    alert_headline='Kava is not recommended with liver disease',
    alert_body=(
        'Kava products have been linked to rare but serious liver injury. '
        'If you have liver disease, avoid kava unless your liver clinician '
        'specifically recommends it.'
    ),
)

# ── 6. Butterbur ──
update_liver('butterbur',
    alert_headline='PA-containing butterbur can injure liver',
    alert_body=(
        'Butterbur containing pyrrolizidine alkaloids is hepatotoxic. If you '
        'have liver disease, avoid butterbur unless it is verified PA-free '
        'and your clinician approves.'
    ),
)

# ── 7. Cascara — avoid→caution, chronic-use language ──
update_liver('cascara_sagrada',
    severity='caution',
    evidence_level='probable',
    alert_headline='Chronic use may affect the liver',
    alert_body=(
        'Chronic or high-dose stimulant laxative use has been linked to '
        'liver injury. If you have liver disease, use cascara only with '
        'clinician guidance.'
    ),
)

# ── 8. Schisandra ──
update_liver('schisandra',
    alert_headline='May alter liver-metabolized drugs',
    alert_body=(
        'Schisandra may affect liver drug-metabolizing enzymes. If you have '
        'liver disease or take medicines processed by the liver, review use '
        'with your clinician.'
    ),
)

# ── 9. Vitamin A ──
update_liver('vitamin_a',
    alert_headline='High-dose vitamin A can harm the liver',
    alert_body=(
        'High-dose preformed vitamin A (retinol) can cause liver injury. '
        'If you have liver disease, avoid high-dose vitamin A supplements '
        'unless your clinician monitors you.'
    ),
)

# ── 10. Niacin ──
update_liver('vitamin_b3_niacin',
    alert_headline='High-dose niacin can injure the liver',
    alert_body=(
        'Pharmacologic-dose niacin can cause liver enzyme elevation and '
        'hepatotoxicity. If you have liver disease, do not use high-dose '
        'niacin without clinician monitoring.'
    ),
)

# ── 11. Turmeric ──
update_liver('turmeric',
    alert_headline='Concentrated curcumin — liver caution',
    alert_body=(
        'High-dose curcumin extract has been linked to liver injury in '
        'recent reports. If you have liver disease, review use of '
        'concentrated curcumin with your clinician.'
    ),
)

# ── 12. Chinese skullcap ──
update_liver('chinese_skullcap',
    alert_headline='Linked to herb-induced liver injury',
    alert_body=(
        'Scutellaria species have been linked to liver injury in case '
        'reports. If you have liver disease, review use with your clinician '
        'and stop if liver symptoms occur.'
    ),
)

# ── 13. Metals: copper, iron, manganese ──
update_liver('copper',
    alert_headline='Copper handling depends on the liver',
    alert_body=(
        'The liver is central to copper metabolism and excretion. If you '
        'have liver disease, avoid extra copper unless your clinician '
        'recommends it based on lab testing.'
    ),
)

update_liver('iron',
    alert_headline='Extra iron may worsen liver overload',
    alert_body=(
        'Extra iron can worsen iron overload in some liver conditions. If '
        'you have liver disease, use iron supplements only with clinician '
        'guidance and lab monitoring.'
    ),
)

update_liver('manganese',
    alert_headline='Manganese clearance depends on the liver',
    alert_body=(
        'Manganese clearance can be impaired in liver disease, leading to '
        'accumulation. If you have liver disease, avoid high-dose manganese '
        'unless your clinician monitors levels.'
    ),
)

# ── 14. Case-report herbs ──
update_liver('andrographis',
    alert_headline='Rare liver injury reports',
    alert_body=(
        'Rare case reports have linked andrographis to liver injury. If you '
        'have liver disease, review use with your clinician and stop if '
        'liver symptoms occur.'
    ),
)

update_liver('gotu_kola',
    alert_headline='Rare liver injury reports',
    alert_body=(
        'Rare case reports have linked gotu kola to liver injury. If you '
        'have liver disease, review use with your clinician and stop if '
        'liver symptoms occur.'
    ),
)

update_liver('saw_palmetto',
    alert_headline='Rare liver injury reports',
    alert_body=(
        'Rare case reports have linked saw palmetto to liver injury. If you '
        'have liver disease, review use with your clinician and stop if '
        'liver symptoms occur.'
    ),
)

update_liver('valerian',
    alert_headline='Rare liver injury reports',
    alert_body=(
        'Rare case reports have linked valerian to liver injury. If you '
        'have liver disease, review use with your clinician and stop if '
        'liver symptoms occur.'
    ),
)

update_liver('tribulus',
    alert_headline='Rare liver injury reports',
    alert_body=(
        'Rare case reports have linked tribulus to liver injury. If you '
        'have liver disease, review use with your clinician and stop if '
        'liver symptoms occur.'
    ),
)

# ── Validate lengths ──
for r in rules:
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'liver_disease':
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

# Count remaining
remaining = sum(1 for r in rules for cr in r.get('condition_rules', [])
                if cr.get('condition_id') == 'liver_disease')

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} changes. Liver rules: 21 → {remaining}')
for c in changes: print(f'  \u2713 {c}')
