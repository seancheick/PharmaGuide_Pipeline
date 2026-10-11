import json
from api_audit.ingest_caers import aggregate_caers_signals


def test_er_visit_requires_a_separate_serious_outcome(tmp_path):
    records=[]
    for outcomes in [['Visited Emergency Room'],['Visited Emergency Room','Hospitalization'],['Death']]:
        records.append({'products':[{'industry_code':'54','role':'SUSPECT','name_brand':'Vitamin D'}],'outcomes':outcomes,'date_created':'20250101'})
    path=tmp_path/'reports.json';path.write_text(json.dumps({'results':records}))
    signals, count, _=aggregate_caers_signals(path,{'vitamin d':'vitamin_d'})
    assert count == 3
    assert signals['vitamin_d']['total_reports'] == 3
    assert signals['vitamin_d']['serious_reports'] == 2
    assert signals['vitamin_d']['outcomes']['Visited Emergency Room'] == 2
