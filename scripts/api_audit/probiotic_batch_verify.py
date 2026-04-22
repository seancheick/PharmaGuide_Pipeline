#!/usr/bin/env python3
"""probiotic_batch_verify.py — one-shot PubMed dose-anchor lookup for every
remaining strain in clinically_relevant_strains.json.

Writes out probiotic_verified_citations.json with for each strain:

    {
      "strain_id": "...",
      "standard_name": "...",
      "indication_primary": "...",
      "primary_citation": {pmid, title, journal, year, url},
      "secondary_citation": {pmid, title, journal, year, url} | null
    }

Human-review step: the operator inspects the output JSON, confirms each
title is about the claimed strain + indication (not a hallucinated
match), and ONLY THEN writes the cfu_thresholds block to the data file.

Rate-limited per NCBI E-utilities policy (~3 req/s with API key).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from pubmed_client import (  # noqa: E402
    PubMedClient,
    load_pubmed_config,
    parse_pubmed_article_xml,
)

OUT = Path("/tmp/probiotic_verified_citations.json")


# Each strain maps to (primary_indication, PubMed query terms). Queries
# favour strain-specific meta-analyses / RCTs. A secondary-indication
# query is optional.
STRAIN_QUERIES = {
    # --- oral / throat ---
    "STRAIN_K12": (
        "oral health and halitosis prevention",
        '"Streptococcus salivarius K12"[TIAB] AND (halitosis OR pharyngitis OR oral)',
        None,
    ),
    "STRAIN_M18": (
        "dental plaque and caries risk reduction",
        '"Streptococcus salivarius M18"[TIAB] AND (caries OR plaque OR dental)',
        None,
    ),
    # --- Bacillus coagulans ---
    "STRAIN_COAGULANS_GBI30": (
        "irritable bowel symptom relief",
        '"Bacillus coagulans GBI-30"[TIAB] AND (IBS OR irritable bowel OR digestion)',
        None,
    ),
    "STRAIN_COAGULANS_MTCC5856": (
        "irritable bowel symptom relief",
        '"Bacillus coagulans MTCC 5856"[TIAB] AND (IBS OR irritable bowel)',
        None,
    ),
    "STRAIN_COAGULANS_IS2": (
        "bacterial vaginosis or gut health",
        '"Bacillus coagulans"[TIAB] AND "IS-2"[TIAB]',
        None,
    ),
    "STRAIN_COAGULANS_SNZ1969": (
        "gut health and digestive support",
        '"Bacillus coagulans"[TIAB] AND ("SNZ 1969" OR "SNZ1969" OR Unique)',
        None,
    ),
    # --- L. reuteri variants ---
    "STRAIN_REUTERI_PRODENTIS": (
        "gingivitis and plaque reduction",
        '"Lactobacillus reuteri"[TIAB] AND (Prodentis OR "ATCC PTA 5289") '
        'AND (gingivitis OR plaque OR periodontal)',
        None,
    ),
    "STRAIN_REUTERI_ATCC6475": (
        "bone density support",
        '"Lactobacillus reuteri"[TIAB] AND ("ATCC 6475" OR "ATCC PTA 6475") '
        'AND (bone OR osteoporosis OR testosterone)',
        None,
    ),
    # --- Bifidobacterium ---
    "STRAIN_LACTIS_BI07": (
        "immune support and respiratory health",
        '"Bifidobacterium"[TIAB] AND ("Bi-07" OR "Bi07") AND (immune OR cold OR infection)',
        None,
    ),
    "STRAIN_INFANTIS_35624": (
        "irritable bowel syndrome symptom relief",
        '"Bifidobacterium infantis 35624"[TIAB] AND (IBS OR irritable bowel)',
        None,
    ),
    "STRAIN_LACTIS_BB12": (
        "immune support and gut health",
        '"Bifidobacterium"[TIAB] AND ("BB-12" OR "BB12") AND (immune OR intestinal OR infection)',
        None,
    ),
    "STRAIN_LONGUM_BB536": (
        "allergic rhinitis and gut health",
        '"Bifidobacterium longum BB536"[TIAB] AND (allergy OR rhinitis OR immune)',
        None,
    ),
    "STRAIN_BREVE_M16V": (
        "prevention of necrotizing enterocolitis in preterm infants",
        '"Bifidobacterium breve M-16V"[TIAB] AND (preterm OR NEC OR necrotizing OR infant)',
        None,
    ),
    "STRAIN_LACTIS_BL04": (
        "respiratory infection and immune support",
        '"Bifidobacterium"[TIAB] AND ("Bl-04" OR "Bl04") AND (respiratory OR immune OR cold)',
        None,
    ),
    "STRAIN_LONGUM_R0175": (
        "mood and anxiety support (psychobiotic)",
        '"Bifidobacterium longum"[TIAB] AND "R0175"[TIAB] AND (anxiety OR depression OR mood)',
        None,
    ),
    "STRAIN_LONGUM_1714": (
        "stress response and cognition",
        '"Bifidobacterium longum 1714"[TIAB] AND (stress OR cognition OR anxiety)',
        None,
    ),
    "STRAIN_LACTIS_UABla12": (
        "gut health and digestive support",
        '"Bifidobacterium"[TIAB] AND ("UABla-12" OR "UABla12")',
        None,
    ),
    # --- Lactobacillus plantarum variants ---
    "STRAIN_PLANTARUM_HEAL9": (
        "immune support and cold prevention",
        '"Lactobacillus plantarum HEAL9"[TIAB]',
        None,
    ),
    # --- Lactobacillus paracasei variants ---
    "STRAIN_PARACASEI_8700": (
        "allergic rhinitis symptom relief",
        '"Lactobacillus paracasei 8700:2"[TIAB] OR ("Lactobacillus paracasei"[TIAB] AND "8700:2")',
        None,
    ),
    "STRAIN_CASEI_SHIROTA": (
        "bowel regularity and gut transit",
        '"Lactobacillus casei Shirota"[TIAB] AND (bowel OR constipation OR gut OR transit)',
        None,
    ),
    "STRAIN_CASEI_431": (
        "immune support and common cold duration",
        '"Lactobacillus paracasei"[TIAB] AND ("L.CASEI 431" OR "CASEI 431") AND (immune OR cold)',
        None,
    ),
    "STRAIN_PARACASEI_LPC37": (
        "immune support",
        '"Lactobacillus paracasei"[TIAB] AND ("Lpc-37" OR "Lpc37") AND (immune OR stress)',
        None,
    ),
    # --- Lactobacillus acidophilus variants ---
    "STRAIN_ACIDOPHILUS_NCFM": (
        "abdominal bloating and gut health",
        '"Lactobacillus acidophilus NCFM"[TIAB] AND (bloating OR IBS OR intestinal)',
        None,
    ),
    "STRAIN_ACIDOPHILUS_LA5": (
        "gut health and diarrhea",
        '"Lactobacillus acidophilus LA-5"[TIAB] OR ("Lactobacillus acidophilus"[TIAB] AND "LA-5")',
        None,
    ),
    "STRAIN_ACIDOPHILUS_DDS1": (
        "lactose digestion and gut health",
        '"Lactobacillus acidophilus DDS-1"[TIAB]',
        None,
    ),
    # --- Lactobacillus rhamnosus variants ---
    "STRAIN_RHAMNOSUS_HN001": (
        "atopic eczema prevention in infants",
        '"Lactobacillus rhamnosus HN001"[TIAB] AND (eczema OR atopic OR allergy)',
        None,
    ),
    "STRAIN_RHAMNOSUS_GR1": (
        "urogenital health and bacterial vaginosis",
        '"Lactobacillus rhamnosus GR-1"[TIAB] AND (vaginal OR vaginosis OR urogenital)',
        None,
    ),
    "STRAIN_RHAMNOSUS_SP1": (
        "dental caries prevention",
        '"Lactobacillus rhamnosus"[TIAB] AND ("SP1" OR "SP-1") AND (caries OR dental)',
        None,
    ),
    # --- Other Lactobacillus / Limosilactobacillus ---
    "STRAIN_FERMENTUM_RC14": (
        "urogenital health and bacterial vaginosis (with GR-1)",
        '"Lactobacillus reuteri RC-14"[TIAB] OR ("Lactobacillus"[TIAB] AND "RC-14"[TIAB])',
        None,
    ),
    "STRAIN_FERMENTUM_ME3": (
        "oxidative stress and cardiovascular markers",
        '"Lactobacillus fermentum ME-3"[TIAB]',
        None,
    ),
    "STRAIN_GASSERI_SBT2055": (
        "reduction of abdominal visceral fat",
        '"Lactobacillus gasseri SBT2055"[TIAB] AND (fat OR obesity OR weight)',
        None,
    ),
    "STRAIN_GASSERI_BNR17": (
        "weight and metabolic support",
        '"Lactobacillus gasseri BNR17"[TIAB]',
        None,
    ),
    "STRAIN_HELVETICUS_R0052": (
        "mood and anxiety support (psychobiotic, with B. longum R0175)",
        '"Lactobacillus helveticus R0052"[TIAB]',
        None,
    ),
    "STRAIN_CRISPATUS_CTV05": (
        "recurrent bacterial vaginosis prevention",
        '"Lactobacillus crispatus CTV-05"[TIAB] OR ("Lactin-V"[TIAB])',
        None,
    ),
    # --- Bacillus (non-coagulans) ---
    "STRAIN_SUBTILIS_DE111": (
        "gut health and digestive support",
        '"Bacillus subtilis DE111"[TIAB]',
        None,
    ),
    "STRAIN_CLAUSII": (
        "acute diarrhea and antibiotic-associated diarrhea",
        '"Bacillus clausii"[TIAB] AND (diarrhea OR diarrhoea OR Enterogermina)',
        None,
    ),
    # --- E. coli ---
    "STRAIN_NISSLE_1917": (
        "ulcerative colitis remission maintenance",
        '"Escherichia coli Nissle 1917"[TIAB] AND (ulcerative colitis OR IBD OR remission)',
        None,
    ),
}


def search(client: PubMedClient, query: str, n: int = 5) -> list[dict]:
    esr = client.esearch(db="pubmed", term=query, retmax=n, sort="relevance")
    ids = (esr.get("esearchresult") or {}).get("idlist") or [] if isinstance(esr, dict) else []
    if not ids:
        return []
    xml = client.efetch(ids=ids, db="pubmed", rettype="xml", retmode="xml")
    return parse_pubmed_article_xml(xml)


def best_hit(arts: list[dict]) -> dict | None:
    """Pick the first hit that has an abstract (guards against bare
    citation stubs)."""
    for a in arts:
        if (a.get("abstract") or "").strip():
            return a
    return arts[0] if arts else None


def main() -> int:
    client = PubMedClient(load_pubmed_config())
    out: dict[str, dict] = {}
    for sid, (indication, q1, q2) in STRAIN_QUERIES.items():
        print(f"\n--- {sid} ---", flush=True)
        arts = search(client, q1, n=5)
        primary = best_hit(arts)
        if primary:
            pm = primary.get("pmid", "")
            title = (primary.get("title") or "").strip()
            print(f"  primary PMID {pm}  {title[:120]}")
        else:
            print("  !! no primary hit")
        out[sid] = {
            "indication_primary": indication,
            "query_primary": q1,
            "primary": {
                "pmid": primary.get("pmid") if primary else None,
                "title": (primary.get("title") or "").strip() if primary else None,
                "journal": primary.get("journal") if primary else None,
                "year": primary.get("pub_year") if primary else None,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{primary['pmid']}/" if primary else None,
            } if primary else None,
        }
        # rate-limit politeness (~3 req/s with key)
        time.sleep(0.25)

    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT} ({len(out)} strains)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
