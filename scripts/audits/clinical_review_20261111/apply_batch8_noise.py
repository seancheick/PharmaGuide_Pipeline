"""Apply source-supported G1 noise corrections; unresolved form/quantity work stays held."""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'scripts'))
import data_batch  # noqa: E402


def apply():
    path = REPO / 'scripts/data/ingredient_interaction_rules.json'
    data = data_batch.load(path)
    rules = {r['id']: r for r in data['interaction_rules']}
    changes = []
    for ident, nutrient in [('RULE_IQM_MAGNESIUM_HYPERTENSION', 'magnesium'),
                            ('RULE_IQM_POTASSIUM_HYPERTENSION', 'potassium')]:
        row = next(r for r in rules[ident]['condition_rules'] if r['condition_id'] == 'kidney_disease')
        row.update(severity='caution',
                   action=f'If you have kidney disease, check with your kidney-care team before adding {nutrient} supplements. Use them only as your care team advises.',
                   alert_headline=f'Check with your kidney-care team before adding {nutrient}')
        if nutrient == 'magnesium':
            row['mechanism'] = 'Reduced kidney function can limit magnesium removal, allowing magnesium from supplements, laxatives or antacids to accumulate and cause toxicity. A kidney-disease checkbox does not establish the degree of kidney impairment or a dose that is appropriate.'
            row['sources'] = ['https://pubmed.ncbi.nlm.nih.gov/37512002/', 'https://pubmed.ncbi.nlm.nih.gov/31379418/', 'https://pubmed.ncbi.nlm.nih.gov/30805197/', 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8cc7d52a-8fc3-4f52-9e50-b15613ddd02c', 'https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/']
        else:
            row['mechanism'] = 'Reduced kidney function can limit potassium removal. Supplements can raise blood potassium dangerously, particularly with medicines that also reduce potassium excretion. General-population intake recommendations do not establish an appropriate supplement amount for someone with kidney disease.'
        row['alert_body'] = ('If you have kidney disease, magnesium can accumulate and cause toxicity. Check with your kidney-care team before adding magnesium supplements, laxatives or antacids.' if nutrient == 'magnesium' else 'If you have kidney disease, potassium supplements can raise blood potassium dangerously. Check with your kidney-care team before adding them, especially with potassium-raising medicines.')
        changes.append(row)

    row = next(r for r in rules['RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES']['drug_class_rules'] if r['drug_class_id'] == 'antihypertensives')
    row.update(severity='informational', direction='neutral',
               action='Tell your prescriber about L-theanine use. The cited studies do not establish a harmful interaction with blood-pressure medicines.',
               alert_headline='Limited evidence with blood-pressure medicine',
               alert_body='Small studies examined blood-pressure responses to stress or caffeine, not harmful hypotension in people taking blood-pressure medicines. An additive effect with these medicines remains theoretical.',
               informational_note='A harmful interaction with blood-pressure medicines remains unproven in the cited L-theanine studies.')
    row['mechanism'] = row['mechanism'].replace('It has not been studied with antihypertensive drugs, so an additive lowering effect is theoretical.', 'These studies did not test coadministration with antihypertensive drugs; an additive lowering effect with those medicines remains theoretical.')
    changes.append(row)
    row = next(r for r in rules['RULE_IQM_ZINC']['drug_class_rules'] if r['drug_class_id'] == 'thyroid_medications')
    row.update(severity='informational', direction='neutral',
               alert_headline='Limited evidence about zinc with levothyroxine',
               informational_note='A specific zinc-levothyroxine interaction or spacing interval is not established by the cited zinc-deficiency report.')
    changes.append(row)

    row = next(r for r in rules['RULE_INGREDIENT_VITAMIN_D']['drug_class_rules'] if r['drug_class_id'] in ('anticoagulants', 'vitamin_k_antagonists'))
    row.update(drug_class_id='vitamin_k_antagonists', severity='informational', direction='neutral', evidence_level='limited',
               mechanism='A small trial in vitamin-D-deficient patients receiving warfarin found lower warfarin dose requirements after deficiency treatment. A separate retrospective study found a weak association between vitamin D status and warfarin sensitivity. These findings do not establish bleeding from ordinary vitamin D supplements, an interaction threshold, or the same effect with other anticoagulants.',
               action='If you take warfarin and are starting or changing treatment for vitamin D deficiency, tell your anticoagulation team; they can advise whether INR follow-up is needed. Do not change warfarin on your own.',
               alert_headline='Vitamin D deficiency treatment may affect warfarin needs',
               alert_body='If you take warfarin, tell your anticoagulation team when starting or changing vitamin D deficiency treatment; small studies suggest your warfarin needs may change.',
               informational_note='Evidence concerns vitamin D status and deficiency treatment in warfarin users.',
               sources=['https://pubmed.ncbi.nlm.nih.gov/27225617/', 'https://pubmed.ncbi.nlm.nih.gov/35718837/'])
    row['profile_gate']['requires']['drug_classes_any'] = ['vitamin_k_antagonists']
    row['profile_gate']['dose'] = None
    changes.append(row)
    for row in changes:
        row['clinical_review'] = {
            'reviewer': 'Dr. Pham', 'reviewed_at': '2026-11-11',
            'file': 'audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md',
            'notes': 'G1 and response govern the action. Wording and source verification prepared by Codex on 2026-11-12, not reviewed by Dr. Pham. No new numerical threshold.'
        }
    row = next(r for r in rules['RULE_INGREDIENT_VITAMIN_D']['drug_class_rules'] if r['drug_class_id'] == 'vitamin_k_antagonists')
    row['clinical_review']['notes'] += ' Existing VKA gate supplies conditional warfarin information; it does not assert an interaction with other VKAs or establish exact-drug targeting.'
    data_batch.save(path, data)


if __name__ == '__main__':
    apply()
