#!/usr/bin/env python3
"""Fail-close unsupported Section 6 psychiatric medication claims."""
import json
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'data'/'medication_depletions.json'
DISPOSITIONS={
'DEP_SSRIS_CALCIUM':('rejected','SSRI calcium depletion claim lacks claim-matched clinical evidence.'),
'DEP_SSRIS_VITAMIND':('rejected','SSRI vitamin D depletion claim lacks claim-matched clinical evidence.'),
'DEP_ANTIPSYCHOTICS_VITAMIND':('needs_revision','Suppressed: PMID 25638514 is a content mismatch; no antipsychotic vitamin D consumer claim is emitted.'),
'DEP_ANTIPSYCHOTICS_COQ10':('needs_revision','Suppressed: PMID 18316143 is a content mismatch; no antipsychotic CoQ10 consumer claim is emitted.'),
'DEP_STIMULANTS_MAGNESIUM':('rejected','Rejected: PMID 9368236 is a supplementation trial, not evidence that stimulants deplete magnesium.'),
'DEP_STIMULANTS_VITAMINC':('needs_revision','Suppressed: PMID 10870150 is a content mismatch; no stimulant vitamin C consumer claim is emitted.'),
'DEP_MAOIS_VITAMINB6':('rejected','MAOI vitamin B6 depletion claim lacks claim-matched clinical evidence.'),
'DEP_SEDATIVES_VITAMIND':('rejected','Sedative vitamin D depletion claim lacks claim-matched clinical evidence.'),
'DEP_BENZODIAZEPINES_MELATONIN':('needs_revision','Suppressed: PMID 2733455 is a content mismatch; no benzodiazepine melatonin consumer claim is emitted.'),
}
def main():
 d=json.loads(P.read_text()); m={e['id']:e for e in d['depletions']}
 for i,(s,n) in DISPOSITIONS.items():
  e=m[i]; e.update(citation_review_status=s,evidence_level='possible',mechanism='No consumer depletion mechanism is asserted pending exact supporting evidence.',clinical_impact='No consumer depletion warning is emitted.',recommendation='Do not supplement solely because of this medication class.',citation_review_note=n,reviewed_at='2026-07-26',reviewer='medication_depletion_section_06_psychiatry_audit')
 P.write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__': main()
