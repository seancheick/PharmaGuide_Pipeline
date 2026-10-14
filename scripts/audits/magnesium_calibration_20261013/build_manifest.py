"""Build the Sean-approved magnesium calibration manifest (2026-10-13, Option C).

Glycerophosphate 2 -> 6 and the resulting unspecified floor 1 -> 2 are held as a
separate decision: no citable basis for 6 exists yet.

Apply with: scripts/iqm_form_evidence.py apply --manifest <this dir>/manifest.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]
sys.path.insert(0, str(SCRIPTS))
from iqm_form_evidence import form_digest  # noqa: E402

TODAY = "2026-10-13"
REVIEW = {"status": "source_verified",
          "by": "PharmaGuide primary-source review; calibration approved by Sean Cheick",
          "date": TODAY}


def ref(pmid, title, doi, published, types, grade):
    return {"type": "pubmed", "authority": "NCBI PubMed", "pmid": pmid, "doi": doi,
            "title": title, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "published_date": published, "publication_types": types,
            "evidence_grade": grade, "retracted": False,
            "supports_claims": ["systemic_bioavailability"],
            "verification_source": "pubmed_eutils", "verified_on": TODAY}


SCHUETTE = ref("7815675", "Bioavailability of magnesium diglycinate vs magnesium oxide in patients with ileal resection.",
               "10.1177/0148607194018005430", "1994",
               ["Clinical Trial", "Journal Article", "Randomized Controlled Trial", "Research Support, U.S. Gov't, P.H.S."], "rct")
PAJUELO = ref("39770988", "Comparative Clinical Study on Magnesium Absorption and Side Effects After Oral Intake of Microencapsulated Magnesium (MAGSHAPETM Microcapsules) Versus Other Magnesium Sources.",
              "10.3390/nu16244367", "2024-12-18",
              ["Journal Article", "Randomized Controlled Trial", "Comparative Study"], "rct")
BRILLI = ref("29630135", "Magnesium bioavailability after administration of sucrosomial® magnesium: results of an ex-vivo study and a comparative, double-blinded, cross-over study in healthy subjects.",
             "10.26355/eurrev_201803_14605", "2018-03-01",
             ["Comparative Study", "Journal Article", "Research Support, Non-U.S. Gov't"], "human_crossover")
WHITE = ref("1468087", "Blood and urinary magnesium kinetics after oral magnesium supplements.",
            None, "1992",
            ["Clinical Trial", "Comparative Study", "Journal Article", "Randomized Controlled Trial", "Research Support, Non-U.S. Gov't"], "rct")
EFSA = ref("38481468", "Safety of magnesium l-threonate as a novel food pursuant to regulation (EU) 2015/2283 and bioavailability of magnesium from this source in the context of Directive 2002/46/EC.",
           "10.2903/j.efsa.2024.8656", "2024-03-13", ["Journal Article"], "journal_article")


def evidence(level, supported, rationale, refs):
    return {"schema_version": "1.0.0", "evidence_level": level, "score_supported": supported,
            "rationale": rationale, "review": dict(REVIEW), "references_structured": refs}


TOP_TIE = (" Sean approved a tied top score of 15 for citrate, chloride, lactate and aspartate on 2026-10-13:"
           " cross-study evidence supports the top group, not an order within it.")

CHANGES = {
    "magnesium citrate": {"bio_score": 15, "notes": lambda n: n.replace(
        " Existing bio_score 14 retained pending clinical calibration review.", TOP_TIE)},
    "magnesium chloride": {"bio_score": 15, "notes": lambda n: n.rstrip() + TOP_TIE,
                           "form_evidence": lambda fe: {**fe, "rationale": fe["rationale"] + (
                               " A small randomized crossover in 12 healthy adults also found chloride solution "
                               "raised 24-hour urinary magnesium, with overall blood effects similar to gluconate "
                               "and slow-release chloride."),
                               "references_structured": fe["references_structured"] + [WHITE]}},
    "magnesium lactate": {"bio_score": 15, "notes": lambda n: n.rstrip() + TOP_TIE},
    "magnesium aspartate": {"bio_score": 15, "notes": lambda n: n.rstrip() + TOP_TIE},
    "magnesium glycinate": {
        "notes": lambda n: n.replace(
            "The existing bio_score 12 is retained pending clinical calibration review;",
            "Sean's 2026-10-13 calibration kept bio_score 12 because direct human evidence is mixed and does not place it in the tied top tier;"),
        "form_evidence_axis": "systemic_bioavailability",
        "form_evidence": evidence("moderate", True,
            "Graded moderate under the existing rubric: direct human absorption studies of the named glycine chelate "
            "with comparators, whose results are mixed. A randomized crossover isotope study gave 100 mg diglycinate or "
            "oxide to 12 patients after ileal resection: overall absorption was equal (23.5% vs 22.8%); the four poorest "
            "oxide absorbers absorbed more from diglycinate, with an earlier peak, a larger isotope AUC and better "
            "tolerance. Two industry-funded single-dose crossovers in healthy adults compared bisglycinate with citrate "
            "and oxide (one gave 375 mg magnesium as orosoluble powders; one gave 350 mg commercial preparations): one "
            "found no significant AUC difference among the tested sources, and neither showed bisglycinate "
            "superiority. These findings support 12, not the top tier, and do not extend to buffered, lysinate-glycinate "
            "or unspecified amino-acid chelate preparations.",
            [SCHUETTE, PAJUELO, BRILLI])},
    "magnesium threonate": {
        "bio_score": 11, "form_evidence_axis": "systemic_bioavailability",
        "form_evidence": evidence("limited", False,
            "EFSA's 2024 opinion concluded magnesium is bioavailable from magnesium L-threonate and that the source is "
            "not nutritionally disadvantageous, based on a dissociation study, two rat studies and one human trial. It "
            "did not compare it with other magnesium salts, so 11 is a calibrated placement matching citrate-malate, not "
            "a measured rank. Cognitive claims are assessed separately from bio_score.",
            [EFSA])},
    "magnesium gluconate": {
        "form_evidence_axis": "systemic_bioavailability",
        "form_evidence": evidence("limited", False,
            "A randomized crossover in 12 healthy adults compared magnesium gluconate tablets with magnesium chloride "
            "solution and slow-release chloride at 16 mmol. Overall serum, ultrafiltrable and leukocyte magnesium "
            "effects showed no major differences; only the chloride solution significantly raised 24-hour urinary "
            "magnesium over baseline. One small study does not establish a higher comparative tier, so the score stays 10.",
            [WHITE])},
}


def main():
    iqm = json.loads((SCRIPTS / "data" / "ingredient_quality_map.json").read_text())
    rows = []
    for name, spec in CHANGES.items():
        form = iqm["magnesium"]["forms"][name]
        values = {k: (v(form[k]) if callable(v) else v) for k, v in spec.items()}
        for k in ("notes",):
            if k in spec and values[k] == form[k]:
                raise SystemExit(f"{name}: {k} replacement did not match")
        rows.append({"ingredient_key": "magnesium", "form_key": name,
                     "expected_form_sha256": form_digest(form), "set": values})
    out = {"schema_version": "1.0.0", "approved_by": "Sean Cheick", "approved_on": TODAY, "changes": rows}
    (HERE / "manifest.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(len(rows), "changes")


if __name__ == "__main__":
    main()
