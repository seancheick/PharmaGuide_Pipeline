"""B1 closure: no medication-nutrient record can publish without final review."""
import json
from pathlib import Path
DATA=Path(__file__).resolve().parent.parent/'data'/'medication_depletions.json'
def test_b1_every_record_has_final_publication_status():
 entries=json.loads(DATA.read_text())['depletions']
 assert len(entries)==80
 assert {e.get('citation_review_status') for e in entries} <= {'verified','needs_revision','rejected'}
 assert all(e.get('citation_review_status') in {'verified','needs_revision','rejected'} for e in entries)
