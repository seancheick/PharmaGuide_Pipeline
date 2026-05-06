#!/usr/bin/env python3
"""Bleeding disorders batch cleanup per clinical team review.

Key changes:
1. Dedup omega-3: keep fish_oil as canonical, remove bleeding rule from
   omega_3, dha, epa, and duplicate fish_oil
2. Dedup curcumin/turmeric: curcumin = high-dose extract, turmeric = informational
3. Remove vitamin D from bleeding_disorders (weak, warfarin-specific at best)
4. Downgrade NAC caution→monitor
5. Fix repetitive headlines — 13 entries say "May raise bleeding risk"
6. Improve copy across the board
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def find_bleeding_rule(canonical_id):
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for j, cr in enumerate(r.get('condition_rules', [])):
                if isinstance(cr, dict) and cr.get('condition_id') == 'bleeding_disorders':
                    return i, j
    return None, None


def remove_bleeding_rule(canonical_id):
    """Remove the bleeding_disorders condition_rule from this entry."""
    ri, ci = find_bleeding_rule(canonical_id)
    if ri is not None:
        rules[ri]['condition_rules'].pop(ci)
        changes.append(f'{canonical_id}: REMOVED bleeding_disorders rule (dedup/irrelevant)')
        return True
    return False


def update(canonical_id, **fields):
    ri, ci = find_bleeding_rule(canonical_id)
    if ri is None:
        return
    cr = rules[ri]['condition_rules'][ci]
    for k, v in fields.items():
        if cr.get(k) != v:
            cr[k] = v
            changes.append(f'{canonical_id}.{k}: updated')


# ── 1. Dedup omega-3: keep fish_oil (first), remove from omega_3, dha, epa ──
# Find and remove from omega_3, dha, epa
for dup in ['omega_3', 'dha', 'epa']:
    remove_bleeding_rule(dup)

# Remove the SECOND fish_oil (index 127 — there are two fish_oil entries)
# Find all fish_oil entries with bleeding_disorders
fish_oil_hits = []
for i, r in enumerate(rules):
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    if cid == 'fish_oil':
        for j, cr in enumerate(r.get('condition_rules', [])):
            if cr.get('condition_id') == 'bleeding_disorders':
                fish_oil_hits.append((i, j))

if len(fish_oil_hits) > 1:
    # Remove the second (duplicate) — pop from the end to avoid index shift
    ri, ci = fish_oil_hits[-1]
    rules[ri]['condition_rules'].pop(ci)
    changes.append('fish_oil: REMOVED duplicate bleeding_disorders rule')

# Update the canonical fish_oil bleeding rule
update('fish_oil',
    alert_headline='High-dose omega-3 may affect bleeding',
    alert_body=(
        'High-dose EPA/DHA (3g+/day) can modestly affect platelet function. '
        'If you have a bleeding disorder or use blood thinners, review your '
        'omega-3 dose with your clinician.'
    ),
)

# ── 2. Dedup curcumin/turmeric ──
# Turmeric → informational (culinary is not the same as extract)
update('turmeric',
    severity='informational',
    evidence_level='probable',
    alert_headline='Culinary turmeric is generally low-risk',
    alert_body=(
        'Culinary turmeric has low bioavailability. High-dose curcumin '
        'extract is the real concern for bleeding. If you use concentrated '
        'curcumin supplements, see the curcumin-specific warning.'
    ),
)

# Curcumin → keep caution but better headline
update('curcumin',
    alert_headline='High-dose curcumin may raise bleeding risk',
    alert_body=(
        'Concentrated curcumin extract can affect platelet aggregation, '
        'especially with piperine or enhanced bioavailability formulas. '
        'If you have a bleeding disorder, review use with your clinician.'
    ),
)

# ── 3. Remove vitamin D from bleeding_disorders ──
remove_bleeding_rule('vitamin_d')

# ── 4. Downgrade NAC caution→monitor ──
update('nac',
    severity='monitor',
    alert_headline='Bleeding signal is limited',
    alert_body=(
        'NAC may affect platelet biology at high doses, but clinical '
        'bleeding risk in supplement users is not well established. If you '
        'have a bleeding disorder, mention NAC to your clinician.'
    ),
)

# ── 5. Fix remaining headlines ──
update('ginger',
    alert_headline='Concentrated ginger may raise bleeding risk',
    alert_body=(
        'High-dose ginger supplements may affect platelet activity. If you '
        'have a bleeding disorder or use blood thinners, review use with '
        'your clinician. Normal food-level ginger is generally fine.'
    ),
)

update('ginkgo',
    alert_headline='May increase bleeding risk',
    alert_body=(
        'Ginkgo inhibits platelet-activating factor and has been linked to '
        'bleeding events in case reports. If you have a bleeding disorder, '
        'avoid unless your clinician specifically recommends it.'
    ),
)

update('white_willow_bark',
    alert_headline='Salicylate — raises bleeding risk',
    alert_body=(
        'White willow bark contains salicylate-like compounds. If you have '
        'a bleeding disorder or use blood thinners, avoid unless your '
        'clinician specifically recommends it.'
    ),
)

update('saw_palmetto',
    alert_headline='Stop before surgery unless advised',
    alert_body=(
        'Saw palmetto has been linked to intraoperative bleeding in case '
        'reports. If you have a bleeding disorder or upcoming surgery, '
        'discuss stopping with your clinician.'
    ),
)

update('chamomile',
    alert_headline='May affect blood-thinner stability',
    alert_body=(
        'Chamomile contains natural coumarins that may interact with '
        'blood-thinning medicines. If you have a bleeding disorder or use '
        'anticoagulants, review with your clinician.'
    ),
)

update('cranberry',
    alert_headline='May affect warfarin stability',
    alert_body=(
        'Cranberry may affect how warfarin is metabolized. If you use '
        'warfarin or other blood thinners, monitor your INR and mention '
        'cranberry to your clinician.'
    ),
)

update('glucosamine',
    alert_headline='Monitor if using blood thinners',
    alert_body=(
        'Rare case reports link glucosamine to altered INR in warfarin '
        'users. If you use blood thinners and take glucosamine, mention it '
        'to your clinician.'
    ),
)

update('chondroitin',
    alert_headline='Monitor if using blood thinners',
    alert_body=(
        'Chondroitin sulfate has weak structural similarity to heparin. '
        'Clinical significance at supplement doses is uncertain. If you '
        'use blood thinners, mention it to your clinician.'
    ),
)

update('boswellia',
    alert_headline='May affect platelet activity',
    alert_body=(
        'Boswellic acids may inhibit platelet aggregation. If you have a '
        'bleeding disorder or use blood thinners, review use with your '
        'clinician.'
    ),
)

update('cat_s_claw',
    alert_headline='May affect platelet activity',
    alert_body=(
        'Cat\u2019s claw extract may have antiplatelet and antithrombotic '
        'effects. If you have a bleeding disorder or use blood thinners, '
        'review use with your clinician.'
    ),
)

update('andrographis',
    alert_headline='May affect platelet activity',
    alert_body=(
        'Andrographis may inhibit platelet aggregation. If you have a '
        'bleeding disorder or use blood thinners, review use with your '
        'clinician.'
    ),
)

update('red_clover',
    severity='monitor',
    alert_headline='Coumarin-like — limited bleeding evidence',
    alert_body=(
        'Red clover contains natural coumarins, but clinical bleeding '
        'significance at supplement doses is uncertain. If you use blood '
        'thinners, mention red clover to your clinician.'
    ),
)

update('resveratrol',
    alert_headline='May affect platelet activity',
    alert_body=(
        'Resveratrol may inhibit platelet aggregation at high doses. If you '
        'have a bleeding disorder or use blood thinners, review use with '
        'your clinician.'
    ),
)

update('gotu_kola',
    alert_headline='Bleeding evidence is limited',
    alert_body=(
        'Gotu kola may affect vascular remodeling at high doses, but '
        'clinical bleeding evidence is very limited. If you have a bleeding '
        'disorder, mention it to your clinician.'
    ),
)

update('devils_claw',
    alert_headline='May affect platelet activity',
    alert_body=(
        'Devil\u2019s claw may have mild antiplatelet properties. If you '
        'have a bleeding disorder or use blood thinners, review use with '
        'your clinician.'
    ),
)

# ── Validate lengths ──
for r in rules:
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'bleeding_disorders':
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} headline len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} alert_body len {len(ab)}: "{ab}"'

# ── Write ──
with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

# Count remaining bleeding rules
remaining = sum(
    1 for r in rules
    for cr in r.get('condition_rules', [])
    if cr.get('condition_id') == 'bleeding_disorders'
)

print(f'Applied {len(changes)} changes. Bleeding rules: 26 → {remaining}')
for c in changes:
    print(f'  \u2713 {c}')
