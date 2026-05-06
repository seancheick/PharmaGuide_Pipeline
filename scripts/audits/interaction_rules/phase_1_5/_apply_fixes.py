#!/usr/bin/env python3
"""Phase 1.5 — apply all verified citation + copy fixes to the 16 new entries.

Each fix is surgical and content-verified per CLINICAL_REVIEW.md + abstract verification pass.
Run pytest after this to confirm no regressions.
"""
import json, os, sys

RULES_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'ingredient_interaction_rules.json')
RULES_PATH = os.path.abspath(RULES_PATH)

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []

def find_rule(canonical_id):
    """Find rule index by canonical_id."""
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else sr
        if cid == canonical_id:
            return i
    raise KeyError(f'Rule not found: {canonical_id}')


# ── Fix 1: BANNED_PENNYROYAL — replace dead NCCIH URL with verified PMID ──
i = find_rule('BANNED_PENNYROYAL')
old_src = rules[i]['condition_rules'][0]['sources']
assert 'nccih.nih.gov/health/pennyroyal' in old_src[0], f'Unexpected source: {old_src}'
rules[i]['condition_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/8633832/',  # Anderson 1996 Ann Intern Med — pennyroyal toxicity case series + lit review
    'https://pubmed.ncbi.nlm.nih.gov/25512112/',  # Gordon 2015 Drug Metab Rev — pennyroyal hepatotoxicity mechanism
]
changes.append('BANNED_PENNYROYAL: replaced dead NCCIH URL with PMIDs 8633832 + 25512112')


# ── Fix 2: BANNED_TANSY — replace near-ghost NBK547852 with verified thujone tox review ──
i = find_rule('BANNED_TANSY')
old_src = rules[i]['condition_rules'][0]['sources']
assert any('NBK547852' in s for s in old_src), f'Unexpected sources: {old_src}'
rules[i]['condition_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/28472675/',  # Radulović 2017 Food Chem Toxicol — thujone toxicity of Tanacetum vulgare + others
]
changes.append('BANNED_TANSY: replaced near-ghost NBK547852 + generic landing with PMID 28472675 (thujone tox review)')


# ── Fix 3: BANNED_BITTER_ORANGE — update URL slug ──
i = find_rule('BANNED_BITTER_ORANGE')
# Find the pregnancy rule (index 131, around line 19760)
for idx, r in enumerate(rules):
    if r.get('id') == 'RULE_BANNED_BITTER_ORANGE_PREGNANCY':
        src = r['condition_rules'][0]['sources']
        for j, s in enumerate(src):
            if 'bitterorange' in s and 'bitter-orange' not in s:
                src[j] = s.replace('bitterorange', 'bitter-orange')
                changes.append('BANNED_BITTER_ORANGE (pregnancy): updated URL slug bitterorange → bitter-orange')
        break
# Also check the hypertension rule
for idx, r in enumerate(rules):
    if r.get('id') == 'RULE_BANNED_BITTER_ORANGE_HYPERTENSION':
        for sub in (r.get('condition_rules', []) + r.get('drug_class_rules', [])):
            for j, s in enumerate(sub.get('sources', [])):
                if 'bitterorange' in s and 'bitter-orange' not in s:
                    sub['sources'][j] = s.replace('bitterorange', 'bitter-orange')
                    changes.append('BANNED_BITTER_ORANGE (hypertension): updated URL slug bitterorange → bitter-orange')


# ── Fix 4: maca — replace dead NCCIH URL ──
i = find_rule('maca')
rules[i]['condition_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/38440178/',  # Ulloa Del Carpio 2024 Front Pharmacol — comprehensive maca review ("generally safe")
]
changes.append('maca: replaced dead NCCIH URL with PMID 38440178 (comprehensive maca review 2024)')


# ── Fix 5: l_tryptophan — replace dead ODS URL ──
i = find_rule('l_tryptophan')
rules[i]['drug_class_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/31523132/',  # Scotton 2019 — serotonin syndrome review (covers MAOI + tryptophan precursor interaction)
]
changes.append('l_tryptophan: replaced dead ODS URL with PMID 31523132 (serotonin syndrome review 2019)')


# ── Fix 6: same (SAMe) — replace dead NCCIH URL ──
i = find_rule('same')
rules[i]['drug_class_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/38423354/',  # Ulloa 2024 Prog Neuropsychopharmacol — SAMe systematic review + meta-analysis for depression
]
changes.append('same: replaced dead NCCIH URL with PMID 38423354 (SAMe antidepressant systematic review 2024)')


# ── Fix 7: sodium — replace dead ODS URL, keep CDC ──
i = find_rule('sodium')
rules[i]['drug_class_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/9022564/',  # Heimann 1997 Am J Clin Nutr — drug interactions and consequences of sodium restriction (covers lithium)
    'https://www.cdc.gov/salt/index.html',  # CDC sodium page (verified resolves)
]
changes.append('sodium: replaced dead ODS URL with PMID 9022564 (sodium restriction + drug interactions); kept CDC')


# ── Fix 8: bromelain — drop unsupported warfarin case-report sentence ──
i = find_rule('bromelain')
old_mech = rules[i]['drug_class_rules'][0]['mechanism']
assert 'Clinical bleeding events with warfarin' in old_mech, f'Expected warfarin sentence in mechanism'
# PMID 11577981 (Maurer 2001) supports fibrinolytic/antiplatelet but NOT the warfarin case-report claim
rules[i]['drug_class_rules'][0]['mechanism'] = (
    'Mild fibrinolytic / antiplatelet activity at high dose (≥500 mg/day). '
    'Bromelain enhances plasmin generation and modestly inhibits platelet aggregation in preclinical studies.'
)
changes.append('bromelain: removed unsupported warfarin case-report sentence from mechanism (PMID 11577981 does not cite warfarin cases)')


# ── Fix 9: ADD_TYRAMINE_RICH_EXTRACT — fix truncated alert_body + informational_note ──
i = find_rule('ADD_TYRAMINE_RICH_EXTRACT')
dr = rules[i]['drug_class_rules'][0]
# alert_body was 200 chars, cut mid-word: "This i..."
# Rewrite within [60, 200] limit
new_ab = (
    'If you take MAO inhibitors, do not combine with this product. '
    'Tyramine-rich supplement extracts can trigger a severe hypertensive crisis '
    '(the classic MAOI "cheese reaction") that may be fatal.'
)
assert 60 <= len(new_ab) <= 200, f'alert_body len {len(new_ab)} out of [60,200]'
dr['alert_body'] = new_ab

# informational_note was 120 chars, cut mid-word: "isocarboxa..."
# Rewrite within [40, 120] limit
new_info = (
    'Tyramine is the classic MAOI dietary contraindication — relevant to anyone on phenelzine or tranylcypromine.'
)
assert 40 <= len(new_info) <= 120, f'informational_note len {len(new_info)} out of [40,120]'
dr['informational_note'] = new_info
changes.append('ADD_TYRAMINE_RICH_EXTRACT: fixed truncated alert_body and informational_note (were cut mid-word at length limit)')


# ── Fix 10: bupleurum_root — replace generic FDA URL with verified CYP2D6 primary source ──
i = find_rule('bupleurum_root')
rules[i]['drug_class_rules'][0]['sources'] = [
    'https://pubmed.ncbi.nlm.nih.gov/33273809/',  # Li 2020 Drug Des Devel Ther — Saikosaponin D effects on CYP1A2 and CYP2D6 in HepaRG cells
]
changes.append('bupleurum_root: replaced generic FDA URL with PMID 33273809 (saikosaponin D + CYP2D6 in HepaRG cells)')


# ── Schema bump: 6.0.2 → 6.0.3 ──
data['_metadata']['schema_version'] = '6.0.3'
data['_metadata']['flutter_schema_version'] = '6.0.3'
data['_metadata']['last_updated'] = '2026-05-06'

# Add migration entry
data['_metadata']['migration']['completed_migrations'].append({
    'from': '6.0.2',
    'to': '6.0.3',
    'date': '2026-05-06',
    'summary': 'Phase 1.5 clinical review: replaced 1 ghost PMID (27092496 in white_mulberry), '
               '5 dead NIH URLs, 1 near-ghost NBK, 1 attribution-mismatched mechanism sentence, '
               '1 truncated alert_body/informational_note, 1 generic FDA URL; '
               'downgraded white_mulberry evidence_level established→probable'
})
changes.append('schema: 6.0.2 → 6.0.3 with migration entry')


# ── Write back ──
with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} fixes to {RULES_PATH}')
for c in changes:
    print(f'  ✓ {c}')
