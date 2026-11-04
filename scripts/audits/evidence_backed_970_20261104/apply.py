"""Apply the agent-reviewed rejections and no-credit literature corrections, with PubMed-read citations."""
import importlib.util
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "backed_clinical_studies.json"
LITERATURE = HERE.parents[1] / "data" / "literature_evidence_records.json"
REVIEWED_AT = "2026-11-04T00:00:00+00:00"
spec = importlib.util.spec_from_file_location("records", HERE / "records.py")
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


def citation(pmid):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id={pmid}"
    article = ET.fromstring(urllib.request.urlopen(url, timeout=60).read()).find(".//PubmedArticle")
    time.sleep(0.4)
    medline = article.find("MedlineCitation/Article")
    ids = {node.get("IdType"): node.text for node in article.findall("PubmedData/ArticleIdList/ArticleId")}
    year = medline.find("Journal/JournalIssue/PubDate/Year")
    entry = {
        "type": "pubmed",
        "authority": "NCBI PubMed",
        "pmid": pmid,
        "title": "".join(medline.find("ArticleTitle").itertext()),
        "citation": f"{medline.findtext('Journal/Title')} ({year.text if year is not None else 'n.d.'})",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "publication_types": [node.text for node in medline.findall("PublicationTypeList/PublicationType")],
    }
    if ids.get("doi"):
        entry["doi"] = ids["doi"]
    return entry


def fetch_article(pmid):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id={pmid}"
    article = ET.fromstring(urllib.request.urlopen(url, timeout=60).read()).find(".//PubmedArticle")
    time.sleep(0.4)
    citation = article.find("MedlineCitation")
    text = " ".join("".join(node.itertext()) for node in citation.findall("Article/Abstract/AbstractText"))
    return {
        "title": "".join(citation.find("Article/ArticleTitle").itertext()),
        "abstract": " ".join(text.split()),
        "humans": "Humans" in [node.text for node in citation.findall("MeshHeadingList/MeshHeading/DescriptorName")],
        "retracted": "Retracted Publication" in [node.text for node in citation.findall("Article/PublicationTypeList/PublicationType")],
    }


def study_row(study):
    article = fetch_article(study["pmid"])
    if study["quote"] not in article["abstract"]:
        raise SystemExit(f"quote not in the abstract of {study['pmid']}: {study['quote']}")
    row = {key: value for key, value in study.items() if key != "quote"}
    row["title"] = article["title"]
    row["verification_provenance"] = {
        "pmid_verified": True,
        "authoritative_live_title": article["title"],
        "human_subjects_verified": article["humans"],
        "topic_match_verified": True,
        "retracted": article["retracted"],
        "verified_source": f"https://pubmed.ncbi.nlm.nih.gov/{study['pmid']}/",
        "verified_at": REVIEWED_AT,
        "abstract_evidence_quote": study["quote"],
    }
    return row


def correct_literature():
    payload = json.loads(LITERATURE.read_text())
    by_id = {record["canonical_id"]: record for record in payload["literature_evidence_records"]}
    changed = []
    for cid, fix in getattr(records, "LITERATURE_CORRECTIONS", {}).items():
        record = by_id[cid]
        if record.get("effect_direction") == fix["effect_direction"] and record.get("applicability_decision") == fix["applicability_decision"]:
            continue
        if fix.get("result") == "no_qualifying_human_evidence":
            # The owner's rule: this result carries no studies, so the decision text names them.
            for quote in fix["quotes"]:
                if quote["quote"] not in fetch_article(quote["pmid"])["abstract"]:
                    raise SystemExit(f"quote not in the abstract of {quote['pmid']}: {quote['quote']}")
            record["qualifying_human_studies"] = []
            record["applicability_status"] = fix["result"]
        else:
            have = {study["pmid"] for study in record["qualifying_human_studies"]}
            record["qualifying_human_studies"] += [study_row(study) for study in fix["studies"] if study["pmid"] not in have]
            record["applicability_status"] = "reviewed_null_evidence"
        record["effect_direction"] = fix["effect_direction"]
        record["applicability_decision"] = fix["applicability_decision"]
        record["verification_result"] = "authoritative_pubmed_verified"
        provenance = record.setdefault("verification_provenance", {})
        provenance["verified_by"] = ("Claude live PubMed esearch/efetch review 2026-11-04: " + fix["receipt"]
                                     + "; no clinician approval and no scoring credit; receipts scripts/audits/evidence_backed_970_20261104")
        provenance["verified_at"] = REVIEWED_AT
        changed.append(cid)
    if changed:
        payload["_metadata"]["last_updated"] = "2026-11-04"
        LITERATURE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print("corrected", changed)


def main():
    correct_literature()
    payload = json.loads(DATA.read_text())
    studies = payload["backed_clinical_studies"]
    known = {study["id"] for study in studies}
    added = []
    for record in records.RECORDS:
        if record["id"] in known:
            continue
        studies.append({**record, "references_structured": [citation(pmid) for pmid in record["published_studies"]]})
        added.append(record["id"])
    if added:
        meta = payload["_metadata"]
        meta["total_entries"] = len(studies)
        meta["last_updated"] = "2026-11-04"
        meta["changelog"].insert(0, "2026-11-04: Added agent-reviewed preparation rejections for the 970-label Evidence review ("
                                    + ", ".join(added) + "). No credit; not clinician reviewed.")
        DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print("added", added, "total", len(studies))


if __name__ == "__main__":
    sys.exit(main())
