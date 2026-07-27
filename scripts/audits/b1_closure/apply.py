#!/usr/bin/env python3
"""Make the B1 medication-depletion corpus publication-complete and fail-closed."""
import json
from pathlib import Path
DATA=Path(__file__).resolve().parents[2]/'data'/'medication_depletions.json'
IDS={'DEP_STATINS_VITAMIND','DEP_CORTICOSTEROIDS_POTASSIUM','DEP_CORTICOSTEROIDS_MAGNESIUM','DEP_CORTICOSTEROIDS_VITAMINC','DEP_CORTICOSTEROIDS_ZINC','DEP_CORTICOSTEROIDS_VITAMINB6'}
NEUTRAL={'evidence_level':'possible','mechanism':'No consumer depletion mechanism is asserted pending exact supporting evidence.','clinical_impact':'No consumer depletion warning is emitted.','recommendation':'Do not supplement solely because of this medication or condition.','onset_timeline':'not established','monitoring_note':'No medication-specific nutrient monitoring recommendation is emitted.','alert_headline':'No medication-specific depletion alert','alert_body':'This record does not establish a medication-caused nutrient depletion warning.','acknowledgement_note':'No medication-specific nutrient coverage acknowledgement is emitted.','monitoring_tip_short':'Follow the monitoring plan set by your treating clinician.','food_sources_short':'Maintain dietary intake appropriate to your individual needs.'}
def main():
 d=json.loads(DATA.read_text()); m={e['id']:e for e in d['depletions']}
 for i in IDS:
  e=m[i]; e.update(citation_review_status='needs_revision',citation_review_note='B1 closure suppression: this record was unreviewed; no consumer claim may publish pending claim-matched evidence and scope.',reviewed_at='2026-07-27',reviewer='b1_corpus_closure_audit',**NEUTRAL); e.pop('adequacy_threshold_mcg',None); e.pop('adequacy_threshold_mg',None)
 DATA.write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__': main()
