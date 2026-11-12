"""Apply G1 remaining source/scope corrections without inventing dose thresholds."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'scripts'))
import data_batch  # noqa: E402


def apply():
    path = REPO / 'scripts/data/ingredient_interaction_rules.json'
    data = data_batch.load(path)
    rules = {r['id']: r for r in data['interaction_rules']}
    reviewed = []
    omega_sources = ['https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/', 'https://pubmed.ncbi.nlm.nih.gov/38742535/']
    for ident in ['RULE_INGREDIENT_OMEGA_3', 'RULE_INGREDIENT_FISH_OIL', 'RULE_IQM_DHA_BLEEDING', 'RULE_IQM_EPA_BLEEDING']:
        for row in rules[ident]['drug_class_rules']:
            if row['drug_class_id'] not in ('anticoagulants', 'antiplatelets'):
                continue
            row.update(severity='monitor',
                       mechanism='Omega-3 preparations can affect platelet function, but randomized-trial evidence does not show an overall increase in bleeding. High-dose purified prescription EPA has a separate bleeding signal; that finding does not establish the same risk for ordinary EPA/DHA supplements or a universal supplement cutoff.',
                       action='Tell your prescriber when starting, stopping or changing omega-3 supplements and report unusual bruising or bleeding. If you take warfarin, ask your anticoagulation team whether INR follow-up is needed.',
                       alert_headline='Omega-3 supplements: monitor with blood-thinning medicines',
                       alert_body='If you take blood-thinning medicine, tell your prescriber about omega-3 supplements and report unusual bruising or bleeding. Warfarin users may need INR follow-up when changing use.',
                       informational_note='Ordinary supplemental omega-3 findings are monitored together; prescription purified EPA requires its own guidance.',
                       sources=omega_sources.copy())
            reviewed.append(row)
    thyroid_sources = ['https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1e11ad30-1041-4520-10b0-8f9d30d30fcc']
    for ident in ['RULE_IQM_CALCIUM', 'RULE_IQM_IRON_HYPERTENSION']:
        row = next(x for x in rules[ident]['drug_class_rules'] if x['drug_class_id'] == 'thyroid_medications')
        row.update(mechanism='Calcium and iron supplements can bind oral levothyroxine and reduce its absorption. The SYNTHROID label instructs patients to separate these supplements by at least 4 hours; this instruction is not limited to a calcium study dose.',
                   action='If you take oral levothyroxine, take calcium or iron supplements at least 4 hours before or after it. Follow your prescriber\'s instructions for your thyroid medicine.',
                   alert_headline='Separate calcium or iron from levothyroxine',
                   alert_body='Calcium or iron supplements can reduce oral levothyroxine absorption. Take them at least 4 hours before or after levothyroxine. Ask your prescriber about timing if you take another thyroid medicine.',
                   informational_note='This spacing guidance concerns oral levothyroxine; calcium and iron are grouped into the same finding.',
                   sources=thyroid_sources.copy())
        reviewed.append(row)
    rule = rules['RULE_IQM_NIACIN_DIABETES']
    for row in [x for x in rule['condition_rules'] if x['condition_id'] == 'diabetes'] + [x for x in rule['drug_class_rules'] if x['drug_class_id'].startswith('hypoglycemics')]:
        row.update(mechanism='Pharmacologic nicotinic acid can raise blood glucose. Prescription extended-release treatment starts at 500 mg/day and carries glucose-monitoring instructions, so 1 g/day is not an absolute onset boundary. Routine nutrient amounts and nicotinamide should not automatically inherit this nicotinic-acid finding.',
                   action='If using pharmacologic nicotinic acid, ask your diabetes care team about glucose monitoring and any treatment adjustments. Do not change diabetes medicines yourself.',
                   alert_headline='Pharmacologic nicotinic acid may raise blood glucose',
                   alert_body='If you have diabetes or take diabetes medicine, ask your care team before using pharmacologic nicotinic acid. It can raise blood glucose; routine amounts and nicotinamide have different evidence.',
                   informational_note='This glucose concern is specific to pharmacologic nicotinic acid; form and daily exposure matter.',
                   sources=['https://ods.od.nih.gov/factsheets/Niacin-HealthProfessional/', 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=249e27ac-e1e7-42dc-84f6-cd32fd1d9dee'])
        row['profile_gate']['excludes']['nutrient_forms_any'] = ['niacinamide']
        reviewed.append(row)
    chromium = rules['RULE_IQM_CHROMIUM_GLUCOSE']
    thyroid_id = 'RULE_IQM_CHROMIUM_PICOLINATE_THYROID'
    if thyroid_id not in rules:
        thyroid = next(x for x in chromium['drug_class_rules'] if x['drug_class_id'] == 'thyroid_medications')
        chromium['drug_class_rules'].remove(thyroid)
        rules[thyroid_id] = {'id': thyroid_id, 'subject_ref': chromium['subject_ref'].copy(),
            'form_scope': ['chromium picolinate', 'chromium (unspecified)'],
            'form_scope_match': 'fail_open', 'condition_rules': [], 'drug_class_rules': [thyroid]}
        data['interaction_rules'].append(rules[thyroid_id])
    rules[thyroid_id].update(last_reviewed='2026-11-12',
        review_owner='Codex source/applicability implementation of Dr. Pham G1; not a new clinician review',
        dose_thresholds=[])
    row = rules[thyroid_id]['drug_class_rules'][0]
    row.update(action='If you use chromium picolinate with levothyroxine, separate them by several hours as your prescriber advises; the study does not establish an exact universal interval.',
               alert_headline='Chromium picolinate may reduce levothyroxine absorption',
               alert_body='If you take levothyroxine, ask about separating chromium picolinate by several hours. The small study does not establish one exact interval or the same effect for other chromium forms.',
               informational_note='Direct evidence concerns chromium picolinate with levothyroxine; other chromium forms need separate evidence.')
    reviewed.append(row)
    rule = rules['RULE_IQM_VITAMIN_B6_LACTATION']
    row = next(x for x in rule['condition_rules'] if x['condition_id'] == 'lactation')
    row.update(alert_body='If you are breastfeeding, discuss high-dose B6 with your clinician. Milk-suppression studies were inconsistent and do not establish this effect at routine nutrient amounts.',
               informational_note='Lactation-suppression evidence at high doses is inconsistent; routine nutrient amounts have different evidence.')
    reviewed.append(row)
    row = rule['pregnancy_lactation']
    row.update(mechanism='Vitamin B6 is an essential nutrient. Trials of 450–600 mg/day pyridoxine for postpartum milk suppression produced inconsistent results, including inconsistent prolactin findings; a dopaminergic mechanism is not established.',
               notes='Routine nutrient quantities are not established to suppress milk supply. The current presence gate cannot distinguish those quantities from pharmacologic exposure; dose-sensitive applicability remains unresolved.',
               alert_body='Vitamin B6 is an essential nutrient. High-dose studies for postpartum milk suppression had inconsistent results. Discuss concentrated B6 with your prenatal or lactation clinician; general B6 toxicity is a separate concern.',
               informational_note='Lactation-suppression evidence at high doses is inconsistent; routine nutrient amounts have different evidence.')
    # State the evidence without presenting the old conjectured mechanism as fact.
    row['mechanism'] = row['mechanism'].replace('; a dopaminergic mechanism is not established', '')
    reviewed.append(row)
    rule = rules['RULE_IQM_GREEN_TEA_HYPERTENSION']
    row = next(x for x in rule['drug_class_rules'] if x['drug_class_id'] in ('beta_blockers', 'nadolol'))
    row.update(drug_class_id='nadolol',
               mechanism='A human study found about 85% lower nadolol exposure after green-tea consumption, consistent with inhibition of intestinal OATP1A2 uptake. This finding does not establish the same interaction for other beta-blockers or an extract-dose threshold.',
               action='Avoid combining green tea or concentrated catechin supplements with nadolol unless your prescriber specifically advises it. A universal spacing interval has not been established.',
               alert_headline='Green tea may reduce nadolol effect',
               alert_body='If you take nadolol, avoid green tea or catechin supplements unless your prescriber advises it. They can reduce nadolol absorption; spacing has not been established to prevent this.',
               informational_note='The evidence concerns nadolol, not every beta-blocker or blood-pressure medicine.')
    row['profile_gate']['requires']['drug_classes_any'] = ['nadolol']
    rule['drug_class_rules'] = [row]
    reviewed.append(row)
    row = next(x for x in rule['condition_rules'] if x['condition_id'] == 'hypertension')
    row.update(severity='informational', direction='neutral',
               alert_headline='Check green tea use if you take nadolol',
               informational_note='High blood pressure alone does not establish this interaction; the evidence concerns nadolol.')
    reviewed.append(row)
    for row in reviewed:
        row['clinical_review'] = {'reviewer': 'Dr. Pham', 'reviewed_at': '2026-11-11',
            'file': 'audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md',
            'notes': 'G1 supplies the decision. Codex source and applicability implementation 2026-11-12; this wording is agent-authored, not a new clinician review. No new numerical threshold.'}
    data_batch.save(path, data)
    path = REPO / 'scripts/data/curated_interactions/curated_interactions_v1.json'
    data = data_batch.load(path)
    row = next(x for x in data['interactions'] if x['id'] == 'DSI_WAR_OMEGA3')
    row.update(severity='Minor', display_layer='background',
        background_rationale='Signed G1: ordinary omega-3 supplementation receives monitoring information, not a prominent caution. Warfarin INR follow-up remains in the management text; no safe dose threshold is inferred.')
    data_batch.save(path, data)
    path = REPO / 'scripts/data/drug_classes.json'
    data = data_batch.load(path)
    data['classes']['class:nadolol'] = {'display_name': 'Nadolol', 'description': 'Nadolol, kept as its own class for the green-tea interaction that names it.', 'member_rxcuis': ['7226'], 'member_names': ['nadolol'], 'rxclass_id': 'C07AA', 'atc_codes': ['C07AA'], 'notes': 'Single-medicine class, following clobazam and lithium. RxNorm 7226 content-verified as nadolol, IN, unsuppressed on 2026-11-12. G1 limits green-tea coverage to the studied medicine; no class-wide beta-blocker extrapolation.'}
    data_batch.save(path, data)
    path = REPO / 'scripts/data/drug_class_vocab.json'
    data = data_batch.load(path)
    if not any(x['id'] == 'nadolol' for x in data['drug_classes']):
        template = next(x for x in data['drug_classes'] if x['id'] == 'beta_blockers')
        data['drug_classes'].append({**template, 'id': 'nadolol', 'name': 'Nadolol',
            'notes': 'Exact nadolol scope for the supported green-tea interaction; broader beta-blocker membership does not trigger it.', 'examples': ['nadolol']})
    data['_metadata']['description'] = 'Controlled vocabulary for interaction drug-class identifiers, split into user-selectable profile choices and rule-only classes. Consumer education fields supply group labels and common uses.'
    data['_metadata']['rule_only_count'] = sum(not x.get('user_selectable') for x in data['drug_classes'])
    data_batch.save(path, data)
    path = REPO / 'scripts/data/clinical_risk_taxonomy.json'
    data = data_batch.load(path)
    if not any(x['id'] == 'nadolol' for x in data['drug_classes']):
        data['drug_classes'].append({'id': 'nadolol', 'label': 'Nadolol', 'category': 'cardiovascular', 'display_priority': 25})
    data['_metadata']['total_entries'] = sum(len(data[k]) for k in ('conditions', 'drug_classes', 'severity_levels', 'evidence_levels', 'profile_flags', 'product_forms', 'sources'))
    data['_metadata']['drug_classes_count'] = len(data['drug_classes'])
    migrations = data['_metadata']['migration']['completed_migrations']
    if not any('nadolol' in item.get('summary', '').lower() for item in migrations):
        old = data['_metadata']['schema_version']
        major, minor, _ = old.split('.')
        new = f'{major}.{int(minor) + 1}.0'
        data['_metadata']['schema_version'] = new
        migrations.insert(0, {'from': old, 'to': new, 'date': '2026-11-12',
            'summary': 'Additive: nadolol gate vocabulary for the signed G1 green-tea interaction scope; unrelated beta-blockers no longer inherit this finding.'})
    data_batch.save(path, data)


if __name__ == '__main__':
    apply()
