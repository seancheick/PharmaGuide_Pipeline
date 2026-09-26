#!/usr/bin/env python3
"""Content-verify every PubMed and NCBI Bookshelf citation in ingredient_interaction_rules.json.

The mandated content verifier (verify_all_citations_content.py) does NOT cover
this file: its PMIDs live nested under interaction_rules[].condition_rules[] /
drug_class_rules[] / pregnancy_lactation.sources[], not a flat array. That gap
left ~200 clinical PMIDs unchecked against the live PubMed API.

This walks the nested structure, fetches each cited PMID live (reusing
verify_all_citations_content.fetch_articles, whole abstracts), and checks it
against every sub-rule that cites it:

  SUBJECT  a name of the rule's subject (standard_name, latin_name, aliases,
           IQM form names and aliases, canonical id; each also without a
           trailing part word such as "root" or "extract") appears in the live
           title or abstract. MeSH is not used: "Senna Plant" also indexes
           Cassia seed papers.
  TOPIC    a stem for the sub-rule's condition or drug class (TOPIC_STEMS)
           appears in the live title, abstract or MeSH.

NCBI Bookshelf sources (www.ncbi.nlm.nih.gov/books/NBK...) are per-drug
monographs such as LiverTox and LactMed, so they get the SUBJECT check only,
against the chapter title and its book titles (resolved through E-utilities;
the pages answer scripts with a captcha). NBK548375, LiverTox "Muscle
Relaxants", was once cited for senna and later for 5-HTP.

The previous check pooled topic words from every claim a PMID supported,
including the subject's own name, so any on-subject paper passed. It passed
PMID 32876395 (a cascaroside chromatography paper cited for cascara pregnancy,
liver, kidney and digoxin rules) and PMID 36702448 (a Cassiae Semen review
cited for senna). Both fail these checks.

Both checks are word heuristics with false positives (class-level reviews,
constituent names). Flagged PMIDs are for MANUAL review, never auto-edited.
``--strict`` turns the report into a gate: a suspect or an unresolved PMID
fails until it is reviewed in scripts/data/interaction_rules_ghost_review.json
with a rationale, the same contract as verify_backed_studies_citations.py.

Usage:
    python3 scripts/api_audit/verify_interaction_rules_citations.py
    python3 scripts/api_audit/verify_interaction_rules_citations.py --strict
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# load .env (PUBMED_API_KEY) the same way the audit tools do
_env = REPO / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from verify_all_citations_content import RATE_LIMIT, SSL_CTX, fetch_articles  # noqa: E402

DATA = REPO / "scripts" / "data"
RULES = DATA / "ingredient_interaction_rules.json"
REVIEW_PATH = DATA / "interaction_rules_ghost_review.json"
PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
BOOK_RE = re.compile(r"ncbi\.nlm\.nih\.gov/books/(NBK\d+)")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# subject_ref.db -> list key; the IQM is a top-level map keyed by canonical id
SUBJECT_LISTS = {
    "banned_recalled_ingredients": "ingredients",
    "botanical_ingredients": "botanical_ingredients",
    "harmful_additives": "harmful_additives",
    "other_ingredients": "other_ingredients",
}
TRAILING_PART_WORDS = {
    "root", "leaf", "bark", "seed", "berry", "fruit", "herb", "flower",
    "extract", "powder", "oil", "juice",
}
# Ordinary words left by stripping a part word; they name no ingredient.
GENERIC_HEADS = {"black", "fish", "green", "mate", "olive", "red", "sea", "sweet", "white",
                 "whole", "wild"}

# Stems matched as word prefixes (a stem with a space is matched as a phrase).
_BLEEDING = [
    "bleed", "hemorrh", "haemorrh", "platelet", "coagul", "thromb", "fibrin",
    "inr", "hematom", "haematom",
]
_GLUCOSE = ["diabet", "glycem", "glycaem", "hypoglyc", "hyperglyc", "glucose", "insulin",
            "hba1c", "metformin", "sulfonylure"]
TOPIC_STEMS = {
    # conditions
    "pregnancy": ["pregnan", "gestat", "fetal", "fetus", "foetal", "obstet", "matern",
                  "teratogen", "prenatal", "perinatal", "uter", "miscarr", "abortifac"],
    "lactation": ["lactat", "breast", "milk", "nursing", "infant"],
    "ttc": ["fertil", "infertil", "concept", "preconcept", "ovulat", "oocyte", "sperm",
            "reproduct", "pregnan"],
    "surgery_scheduled": ["surg", "operat", "perioperat", "preoperat", "postoperat",
                          "anesthe", "anaesthe"] + _BLEEDING,
    "hypertension": ["hypertens", "blood pressure", "pressor", "vasoconstrict",
                     "vasodilat", "hypotens"],
    "heart_disease": ["heart", "cardi", "arrhythm", "tachycard", "bradycard", "coronary",
                      "myocard", "vascular", "atrial", "ventric", "angina", "hypertens",
                      "blood pressure"],
    "diabetes": _GLUCOSE,
    "bleeding_disorders": _BLEEDING,
    "kidney_disease": ["kidney", "renal", "nephr", "dialys", "electrolyt", "potassium",
                       "hyperkal", "hypokal", "creatinin"],
    "liver_disease": ["liver", "hepat", "cirrho", "jaundic", "transamin", "cholesta"],
    "thyroid_disorder": ["thyr", "tsh", "iodin", "goitr", "peroxidase"],
    "autoimmune": ["autoimmun", "immun", "lupus", "rheumat", "arthrit", "sclerosis",
                   "inflamm"],
    "immunocompromised": ["immun", "neutropen", "transplant", "bacteremi", "fungemi",
                          "sepsis", "infect", "malignan", "cancer", "chemotherap"],
    "seizure_disorder": ["seizur", "epilep", "convuls"],
    "high_cholesterol": ["cholester", "lipid", "lipoprotein", "triglycer", "statin",
                         "ldl", "hdl"],
    "current_smoker": ["smok", "tobacco", "cigarett"],
    "former_smoker": ["smok", "tobacco", "cigarett"],
    "asbestos_exposure": ["asbestos"],
    # drug classes
    "anticoagulants": ["warfarin", "coumarin", "heparin", "apixaban", "rivaroxaban",
                       "dabigatran"] + _BLEEDING,
    "doacs": ["apixaban", "rivaroxaban", "dabigatran", "edoxaban"] + _BLEEDING,
    "vitamin_k_antagonists": ["warfarin", "coumarin", "vitamin k"] + _BLEEDING,
    "antiplatelets": ["aspirin", "clopidogrel", "aggregat"] + _BLEEDING,
    "nsaids": ["nsaid", "nonsteroid", "antiinflamm", "anti inflamm", "ibuprofen",
               "naproxen", "aspirin", "cyclooxygenase", "cox"] + _BLEEDING,
    "antihypertensives": ["antihypertens", "hypertens", "blood pressure", "hypotens",
                          "vasodilat", "pressor"],
    "hypoglycemics_high_risk": _GLUCOSE,
    "hypoglycemics_lower_risk": _GLUCOSE,
    "hypoglycemics_unknown": _GLUCOSE,
    "thyroid_medications": ["thyr", "levothyrox", "tsh"],
    "sedatives": ["sedat", "sleep", "hypnot", "benzodiazep", "gaba", "anxi", "drows", "cns"],
    "immunosuppressants": ["immun", "cyclospor", "tacrolimus", "transplant", "cyp",
                           "cytochrome", "glycoprotein"],
    "statins": ["statin", "myopath", "rhabdomyol", "hmg", "cholester", "lipid"],
    "antidepressants_ssri_snri": ["seroton", "ssri", "snri", "antidepress"],
    "maois": ["maoi", "monoamine", "tyramine", "seroton", "pressor", "phenelzine",
              "selegiline"],
    "serotonergic_medications": ["seroton", "tramadol", "triptan", "linezolid"],
    "cardiac_glycosides": ["digoxin", "digitoxin", "digitalis", "hypokal", "potassium"],
    "anticholinergics": ["cholinerg", "acetylcholin", "muscarin", "cholinesterase"],
    "anticonvulsants": ["anticonvuls", "antiepilep", "seizur", "epilep", "phenytoin",
                        "valpro", "carbamazep"],
    "thiazide_diuretics": ["thiazide", "diuret", "potassium", "hypokal"],
    "lithium": ["lithium", "diuret", "renal", "kidney"],
    "calcium_channel_blockers": ["calcium channel", "amlodipine", "nifedipine",
                                 "verapamil", "diltiazem", "felodipine", "cyp3a",
                                 "cytochrome"],
    "oral_contraceptives": ["contracept", "estrogen", "oestrogen", "ethinyl", "progest",
                            "hormon"],
    "antiarrhythmics": ["arrhythm", "amiodarone", "potassium", "qt"],
    "cyp3a4_substrates": ["cyp3a", "cytochrome", "p450", "midazolam"],
    "cyp2d6_substrates": ["cyp2d6", "cytochrome", "p450"],
    "potassium_sparing_diuretics": ["potassium", "spironolact", "amiloride", "triamterene",
                                    "hyperkal", "diuret"],
    "tetracycline_antibiotics": ["tetracycl", "doxycycl", "minocycl", "antibiot", "chelat"],
    "beta_blockers": ["blocker", "adrenerg", "propranolol", "metoprolol", "atenolol"],
    "fluoroquinolones": ["fluoroquinol", "quinolone", "floxacin", "chelat", "antibiot"],
}


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def load_subject_entries() -> dict[tuple[str, str], dict]:
    """(subject_ref.db, canonical_id) -> owning entry."""
    iqm = json.loads((DATA / "ingredient_quality_map.json").read_text())
    entries = {
        ("ingredient_quality_map", key): value
        for key, value in iqm.items()
        if key != "_metadata" and isinstance(value, dict)
    }
    for db, list_key in SUBJECT_LISTS.items():
        for entry in json.loads((DATA / f"{db}.json").read_text())[list_key]:
            entries[(db, entry.get("id"))] = entry
    return entries


def subject_phrases(subject_ref: dict, entries: dict) -> set[str]:
    db, canonical_id = subject_ref.get("db"), subject_ref.get("canonical_id") or ""
    entry = entries.get((db, canonical_id)) or {}
    names = [canonical_id.replace("_", " "), entry.get("standard_name"),
             entry.get("latin_name"), *(entry.get("aliases") or [])]
    for form_name, form in (entry.get("forms") or {}).items():
        names += [form_name, *((form or {}).get("aliases") or [])]
    own_name = _norm(entry.get("standard_name"))
    phrases = set()
    for name in names:
        words = _norm(name).split()
        phrase = " ".join(words)
        # A short single word ("age" for AGE, "same" for SAMe, "hip") is usually a
        # common English word: it counts only with a digit ("b12") or as the
        # entry's own name.
        if len(words) > 1 or len(phrase) >= 5 or any(c.isdigit() for c in phrase) or (
            phrase and phrase == own_name
        ):
            phrases.add(phrase)
        while len(words) > 1 and words[-1] in TRAILING_PART_WORDS:
            words = words[:-1]
            head = " ".join(words)
            if len(words) > 1 or (len(head) >= 4 and head not in GENERIC_HEADS):
                phrases.add(head)  # "kava root" -> "kava", but not "fish oil" -> "fish"
    return phrases


def _topic_stems(sub_rule: str) -> list[str] | None:
    if sub_rule == "pregnancy_lactation":
        return TOPIC_STEMS["pregnancy"] + TOPIC_STEMS["lactation"]
    return TOPIC_STEMS.get(sub_rule.partition(":")[2])


def _names_subject(text: str, phrases: set[str]) -> bool:
    return any(f" {p} " in f" {text} " for p in phrases)


def check_citation(article: dict, phrases: set[str], sub_rule: str) -> list[str]:
    """Return the failed checks ("subject", "topic") for one cited sub-rule."""
    failed = []
    title_abstract = f" {_norm(article.get('title'))} {_norm(article.get('abstract'))} "
    if not _names_subject(title_abstract, phrases):
        failed.append("subject")
    everything = title_abstract + " ".join(_norm(m) for m in article.get("mesh_terms") or [])
    tokens = everything.split()
    stems = _topic_stems(sub_rule)
    if not stems or not any(
        f" {stem}" in everything if " " in stem else any(t.startswith(stem) for t in tokens)
        for stem in stems
    ):
        failed.append("topic")
    return failed


def check_book_chapter(chapter: dict, phrases: set[str]) -> list[str]:
    """A Bookshelf chapter must name the subject in its own or its book's title."""
    titles = " ".join(_norm(t) for t in [chapter.get("title"), *chapter.get("books", [])])
    return [] if _names_subject(titles, phrases) else ["subject"]


def book_chapter(record: dict) -> dict:
    """Chapter title plus parent book titles from an esummary db=books record."""
    books = []
    if record.get("bookinfo"):
        books = [el.findtext("Title") or "" for el in ET.fromstring(record["bookinfo"]).iter("Parent")]
    return {"title": record.get("title", ""), "books": books}


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "pharmaguide-audit/1.0"})
    with urllib.request.urlopen(request, timeout=30, context=SSL_CTX) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_book_chapters(nbk_ids: list[str]) -> dict[str, dict]:
    """NBK id -> chapter via E-utilities (esearch, then esummary, db=books)."""
    key = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
    suffix = f"&api_key={key}" if key else ""
    chapters = {}
    for nbk in nbk_ids:
        try:
            uids = _get_json(f"{EUTILS}esearch.fcgi?db=books&retmode=json&retmax=100&term={nbk}{suffix}")[
                "esearchresult"]["idlist"]
            time.sleep(RATE_LIMIT)
            if uids:
                result = _get_json(f"{EUTILS}esummary.fcgi?db=books&retmode=json&id={','.join(uids)}{suffix}")["result"]
                for uid in result.get("uids", []):
                    if result[uid].get("rid") == nbk:
                        chapters[nbk] = book_chapter(result[uid])
        except Exception as error:  # an unresolved NBK is reported as not found
            print(f"  Bookshelf error {nbk}: {error}", file=sys.stderr)
        time.sleep(RATE_LIMIT)
    return chapters


def collect_claims(rules: list[dict], entries: dict) -> dict[str, list[tuple]]:
    """PMID or NBK id -> [(rule_id, sub_rule, subject phrases)]"""
    claims: dict[str, list[tuple]] = {}
    for rule in rules:
        phrases = subject_phrases(rule.get("subject_ref") or {}, entries)
        sub_rules = [(f"condition:{c.get('condition_id')}", c) for c in rule.get("condition_rules") or []]
        sub_rules += [(f"drug:{d.get('drug_class_id')}", d) for d in rule.get("drug_class_rules") or []]
        if isinstance(rule.get("pregnancy_lactation"), dict):
            sub_rules.append(("pregnancy_lactation", rule["pregnancy_lactation"]))
        for label, sub_rule in sub_rules:
            for source in sub_rule.get("sources") or []:
                match = PMID_RE.search(str(source)) or BOOK_RE.search(str(source))
                if match:
                    claims.setdefault(match.group(1), []).append((rule.get("id", "?"), label, phrases))
    return claims


def reviewed_keys(path: Path = REVIEW_PATH) -> set[str]:
    """Reviewed suspects with a rationale, keyed "PMID:rule_id:sub_rule"."""
    if not path.is_file():
        return set()
    reviewed = json.loads(path.read_text(encoding="utf-8")).get("reviewed") or []
    return {
        f"{item.get('pmid')}:{item.get('rule_id')}:{item.get('sub_rule')}"
        for item in reviewed
        if isinstance(item, dict) and item.get("rationale")
    }


def unreviewed(suspects: list[tuple], keys: set[str]) -> list[tuple]:
    return [s for s in suspects if f"{s[0]}:{s[1]}:{s[2]}" not in keys]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on an unreviewed suspect or an unresolved source")
    parser.add_argument("--rules", type=Path, default=RULES, help="rules file to check")
    args = parser.parse_args()

    rules = json.loads(args.rules.read_text()).get("interaction_rules") or []
    claims = collect_claims(rules, load_subject_entries())
    pmids = sorted(k for k in claims if not k.startswith("NBK"))
    nbk_ids = sorted(k for k in claims if k.startswith("NBK"))
    print(f"Rules: {len(rules)} | distinct PubMed PMIDs: {len(pmids)} | Bookshelf chapters: "
          f"{len(nbk_ids)} | cited sub-rules: {sum(len(c) for c in claims.values())}\n")
    if not claims:
        print("No PubMed or Bookshelf sources cited in this file.")
        return 0

    print(f"Fetching {len(pmids)} PMIDs (efetch) and {len(nbk_ids)} Bookshelf chapters (esummary)...\n")
    articles = fetch_articles(pmids, abstract_chars=None) if pmids else {}
    chapters = fetch_book_chapters(nbk_ids)

    notfound, suspects = [], []
    for source_id in pmids + nbk_ids:
        record = articles.get(source_id) if source_id in articles else chapters.get(source_id)
        if not record:
            notfound.append(source_id)
            continue
        for rule_id, sub_rule, phrases in claims[source_id]:
            if source_id.startswith("NBK"):
                failed, title = check_book_chapter(record, phrases), " / ".join([record["title"], *record["books"]])
            else:
                failed, title = check_citation(record, phrases, sub_rule), record.get("title", "")
            if failed:
                suspects.append((source_id, rule_id, sub_rule, failed, title))

    ok = sum(len(c) for c in claims.values()) - len(suspects) - sum(len(claims[p]) for p in notfound)
    print(f"RESULT: on-topic={ok}  GHOST-SUSPECT={len(suspects)} "
          f"({len({s[0] for s in suspects})} sources)  not-found={len(notfound)}\n")
    for source_id in notfound:
        cites = "; ".join(f"{rid}/{label}" for rid, label, _ in claims[source_id])
        print(f"  NOT FOUND {source_id}   cited by: {cites}")
    if suspects:
        print("=== GHOST-SUSPECT (MANUAL REVIEW each; subject = identity absent from "
              "title/abstract or Bookshelf chapter/book title, topic = claim topic absent) ===")
        for source_id, rule_id, sub_rule, failed, title in suspects:
            label = source_id if source_id.startswith("NBK") else f"PMID {source_id}"
            print(f"  {label} [{'+'.join(failed)}] {rule_id}/{sub_rule}")
            print(f"    real title : {title[:110]}")

    if not args.strict:
        return 0
    blocking = unreviewed(suspects, reviewed_keys())
    if blocking or notfound:
        print(f"\nSTRICT: FAIL - {len(blocking)} unreviewed suspect(s), "
              f"{len(notfound)} unresolved source(s). Fix the citation or record a "
              f"reviewed rationale in {REVIEW_PATH.relative_to(REPO)}.")
        return 1
    print("\nSTRICT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
