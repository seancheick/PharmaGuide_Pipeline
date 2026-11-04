"""Add the rejection records to backed_clinical_studies.json with PubMed-read citations."""
import importlib.util
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "backed_clinical_studies.json"
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


def main():
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
