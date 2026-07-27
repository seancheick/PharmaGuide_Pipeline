import json
from pathlib import Path

DATA=Path(__file__).resolve().parent.parent/'data'/'medication_depletions.json'
def test_section5_cardiovascular_claims_fail_closed():
 e={x['id']:x for x in json.loads(DATA.read_text())['depletions']}
 expected={'DEP_ACEINHIBITORS_ZINC':'needs_revision','DEP_BETABLOCKERS_COQ10':'needs_revision','DEP_BETABLOCKERS_MELATONIN':'needs_revision','DEP_CALCIUMCHANNELBLOCKERS_POTASSIUM':'rejected','DEP_ANTIHYPERTENSIVES_ZINC':'rejected','DEP_ANTIHYPERTENSIVES_COQ10':'rejected'}
 assert {k:e[k].get('citation_review_status') for k in expected} == expected
