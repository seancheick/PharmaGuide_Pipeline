"""Apply the first Evidence review batch to literature_evidence_records.json."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUDIT = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import data_batch

loaded = importlib.util.spec_from_file_location("evidence_review_spec", AUDIT / "spec.py")
spec = importlib.util.module_from_spec(loaded)
loaded.loader.exec_module(spec)
receipts = json.loads((AUDIT / "receipts.json").read_text(encoding="utf-8"))
PATH = ROOT / "scripts" / "data" / "literature_evidence_records.json"
REVIEWED_AT = "2026-11-03T00:00:00+00:00"
REPLACED = {"material_form", "search_query", "search_date", "databases_searched", "records_screened",
            "qualifying_human_studies", "effect_direction", "population_context", "studied_dose_exposure",
            "applicability_decision", "applicability_status", "verification_result"}


def study_row(study):
    article = receipts["articles"][study["pmid"]]
    row = {key: value for key, value in study.items() if key != "quote"}
    row["title"] = article["title"]
    row["verification_provenance"] = {
        "pmid_verified": True,
        "authoritative_live_title": article["title"],
        "human_subjects_verified": article["human_mesh"],
        "topic_match_verified": True,
        "retracted": article["retracted"],
        "verified_source": f"https://pubmed.ncbi.nlm.nih.gov/{study['pmid']}/",
        "verified_at": REVIEWED_AT,
        "abstract_evidence_quote": study["quote"],
    }
    return row


blob = data_batch.load(PATH)
records = blob["literature_evidence_records"]
by_id = {record["canonical_id"]: record for record in records}
for cid, entry in spec.RECORDS.items():
    search = receipts["searches"][cid]
    record = by_id.get(cid)
    if record is None:
        record = {"canonical_id": cid}
        records.append(record)
    for key in REPLACED:
        record.pop(key, None)
    prior = record.get("verification_provenance") or {}
    provenance = {
        "verified_by": (f"Claude live PubMed esearch/efetch review {search['date']}: {search['records_screened']} "
                        "titles screened, abstracts of the cited studies read; no clinician approval and no scoring "
                        "credit; receipts scripts/audits/evidence_review_batch1_20261102"),
        "verified_at": REVIEWED_AT,
        "all_pmids_verified": True,
        "retractions_found": False,
    }
    if entry.get("notes"):
        record["notes"] = entry["notes"]
    if entry.get("documented_review_scope"):
        record["documented_review_scope"] = entry["documented_review_scope"]
    if prior.get("reference_citations"):
        provenance["reference_citations"] = prior["reference_citations"]
    record.update({
        "material_form": entry["material_form"],
        "search_query": search["search_query"],
        "search_date": search["date"],
        "databases_searched": ["PubMed"],
        "records_screened": search["records_screened"],
        "qualifying_human_studies": [study_row(study) for study in entry["studies"]],
        "effect_direction": entry["effect_direction"],
        "population_context": entry["population_context"],
        "studied_dose_exposure": entry.get("studied_dose_exposure", {}),
        "applicability_decision": entry["applicability_decision"],
        "applicability_status": entry["applicability_status"],
        "verification_result": "authoritative_pubmed_verified",
        "verification_provenance": provenance,
    })
print(data_batch.save(PATH, blob))
