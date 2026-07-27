import json
from pathlib import Path
def test_section6_claims_fail_closed_except_verified_ssri_sodium():
 e={x['id']:x for x in json.loads((Path(__file__).resolve().parent.parent/'data'/'medication_depletions.json').read_text())['depletions']}
 assert e['DEP_SSRIS_SODIUM']['citation_review_status']=='verified'
 for i in ['DEP_SSRIS_CALCIUM','DEP_SSRIS_VITAMIND','DEP_ANTIPSYCHOTICS_VITAMIND','DEP_ANTIPSYCHOTICS_COQ10','DEP_STIMULANTS_MAGNESIUM','DEP_STIMULANTS_VITAMINC','DEP_MAOIS_VITAMINB6','DEP_SEDATIVES_VITAMIND','DEP_BENZODIAZEPINES_MELATONIN']:
  assert e[i].get('citation_review_status') in {'needs_revision','rejected'}
