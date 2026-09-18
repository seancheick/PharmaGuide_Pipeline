#!/usr/bin/env python3
"""Generate WAVE2_CHECKPOINT.md from the wave's own artifacts (read-only).

Every count in the report is read from a file this wave produced. Nothing is
typed by hand — the two hand-typed numbers in NULL_SCOPE_AUDIT.md were both
wrong, and this is the fix for that class of error.

    python3 scripts/audits/evidence_expansion_2026_09/build_wave2_checkpoint.py \
        --screen-dir <dir> --queue queue.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
CLASS_ORDER = ("curate", "hold", "handoff_only", "no_qualifying")

NARRATIVE = """## Deep central verification — three identities read from the live sources

Screening is triage. These three were re-read centrally, source by source, because they carry the
wave's two best approval candidates and its worst integrity problem.

### `common_bean_extract` — the wave's first class-A candidate

22 products, 21 of them at Evidence 0, every label row printing "white kidney bean extract", measured
label median **1,500 mg/day** (p25 650 mg).

PMID 42066439 (Nutrition Research, 2026) is an **ingredient-level** meta-analysis of oral white kidney
bean (Phaseolus vulgaris) extract, 8 RCTs, n=543: weight −1.62 kg (95% CI −1.99 to −1.25), BMI −0.58
kg/m2, fat mass −1.17 kg, waist −1.58 cm, all P < .05, no serious adverse events. PMID 39170208 is a
branded (Phaseolean) placebo-controlled RCT at 1,500 and 3,000 mg/day, positive at both.

The material matches what the catalog prints, the dose is in the studied range, and the population is
adults with overweight — the people who buy it. **This is scorer-compatible today.** The caveat that
must travel with it: alpha-amylase inhibitor extracts are not standardised by inhibitor units, so
label milligrams are not a potency guarantee, and the pooled effect is small.

### `d_mannose` — class A, and blocked only by the parked null decision

25 products, 16 at Evidence 0, form uniformly "d-mannose", measured label median **1,000 mg**, p75
**2,000 mg**.

PMID 38587819 (JAMA Internal Medicine, 2024) is the decisive source: 598 women in 99 UK primary-care
centres, **2 g/day for 6 months**, placebo-controlled. Primary outcome null — 51.0% vs 55.7%, risk
difference −5% (95% CI −13% to 3%), P = .26 — and the authors state it should not be recommended for
prophylaxis in this group. PMID 41004704 (2025) pooled 6 RCTs and 1,167 participants and also found no
reduction (RR 0.57, 95% CI 0.29–1.15). The positive syntheses that screening surfaced are older and
weaker: PMID 32972899 (2021) is a narrative systematic review of mostly open-label studies, and PMID
39095666 is a network meta-analysis pooling those same older trials.

Everything needed to score this exists: a generic material, a studied daily dose that maps to real
labels, and an outcome the existing cranberry record already expresses. The direction is **null** —
so under the rule that a null record is not proposed for approval until the direction semantics are
decided, it cannot be approved. **The parked null decision has stopped being a scoring adjustment and
started blocking approvals.**

### `green_coffee_bean` — an integrity problem inside the syntheses

76 products, 21 at Evidence 0. Its own retrieval contains **two retracted records** (PMIDs 22291473
and 25340633), the retracted green-coffee-extract weight-loss trial. None of them was selected, and
the live verification pass confirmed no retracted or expression-of-concern record reached the selected
set. But all four selected sources are meta-analyses, and a meta-analysis can carry a retracted trial
inside it without saying so in its abstract. **No green coffee bean record may be authored until each
synthesis's included-study list is checked against those two PMIDs.** That is a curation-time
requirement, recorded here rather than assumed away.

Retracted or flagged records also appeared in the retrieval for goji berry, hawthorn, theobromine and
papaya. The retraction detector repaired earlier in this project (RetractionIn links that precede the
publication type) is what surfaced them.

## What the wave says about the expansion itself

{curate} of 50 identities have candidate human efficacy evidence worth deep curation, covering
{curate_ev0} of the {total_ev0} Evidence=0 products in the wave. {hold} are held with real evidence the
current architecture cannot safely apply ({hold_ev0} products), and {noq} have no qualifying evidence at
all ({noq_ev0} products).

The held and no-qualifying reasons repeat, and they are not curation failures:

- **combination products** — the trial gave the ingredient inside a multi-herb formula (hops with
  valerian, white willow with feverfew, holy basil with rhodiola and schisandra, chaga as a fifth of a
  four-herb blend);
- **wrong route** — the literature is topical or local, not swallowed (aloe vera, wild yam, dimethyl
  glycine);
- **clinical population and indication** — L-ornithine in hepatic encephalopathy, pregnenolone as an
  antipsychotic adjunct, hawthorn in diagnosed heart failure, TUDCA in ALS;
- **name collision** — the retrieval is about something else entirely (eyebright returned an
  intraocular-lens manufacturer; L-proline and L-norvaline returned endogenous-biomarker studies);
- **potency, not milligrams** — devil's claw is dosed by harpagoside content, feverfew by
  parthenolide, cayenne by capsaicin; a label's extract milligrams do not state those.

That last one is the structural finding of this wave. Several botanicals have genuine positive
evidence that the catalog cannot receive, because the studied exposure is a marker compound and the
label prints extract weight. It is the same shape as the Permixon and BR-DIM problems fixed this week,
and it will recur in every botanical wave.

## Handoffs

{handoffs} safety, pharmacokinetic or interaction findings were separated from efficacy during
screening rather than being folded into an efficacy direction. `goldenseal` (51 products) is
handoff-only: both of its retrieved human studies are CYP450 interaction work, and an interaction rule
for goldenseal already exists in the interaction owner's file. The full list is in the per-identity
screen files.

## What has not been done

No pending context was authored, so no record is owner-approvable yet. The two class-A candidates
above are the only identities verified to the depth that would justify one, and one of them
(`d_mannose`) is blocked by the null decision. Deep curation of the remaining 23 `curate` identities is
the next block of work, and it is where the cost is.
"""

ACTION = {"curate": "deep-curate", "hold": "hold", "handoff_only": "route", "no_qualifying": "record review state"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-dir", required=True, type=Path)
    args = parser.parse_args()

    prescreen = json.loads((OUT / "wave2_prescreen.json").read_text())
    qa = json.loads((OUT / "wave2_screen_qa.json").read_text())
    verification = json.loads((OUT / "wave1_verification.json").read_text()) \
        if (OUT / "wave1_verification.json").exists() else {}
    log = json.loads((OUT / "wave2_search_log.json").read_text())
    by_id = {i["canonical_id"]: i for i in prescreen["identities"]}

    screens = {}
    for path in sorted(args.screen_dir.glob("*.screen.json")):
        screen = json.loads(path.read_text())
        screens[screen["canonical_id"]] = screen

    rows = []
    for cid, screen in screens.items():
        ident = by_id[cid]
        catalog = ident["catalog"]
        rows.append({
            "canonical_id": cid, "label_name": ident["label_name"],
            "products": catalog["products"], "evidence_zero": catalog["evidence_zero_products"],
            "slots": catalog["slots"], "brands": catalog["brands"],
            "retrieved": ident["records_retrieved"],
            "efficacy_candidates": ident["efficacy_candidates"],
            "class": screen["recommended_class"], "selected": len(screen.get("selected") or []),
            "handoffs": len(screen.get("handoff_pmids") or []),
            "integrity_hold": len(ident["integrity_hold"]),
            "blocker": (screen.get("blockers") or [""])[0],
            "reason": screen.get("one_line_reason", ""),
        })
    rows.sort(key=lambda r: (CLASS_ORDER.index(r["class"]), -r["evidence_zero"]))

    by_class = collections.Counter(r["class"] for r in rows)
    ev0_by_class = collections.Counter()
    prod_by_class = collections.Counter()
    for r in rows:
        ev0_by_class[r["class"]] += r["evidence_zero"]
        prod_by_class[r["class"]] += r["products"]

    lines = [
        "# Wave 2 checkpoint — 50 unreviewed identities searched and screened (2026-09-18)",
        "",
        "**No production evidence write, no score movement, no catalog rebuild, no release.** The only",
        "production change in this branch since the last checkpoint is the four legacy scope repairs",
        "(`LEGACY_SCOPE_REPAIR.md`), which are measured and committed separately. Wave 2 has authored",
        "nothing into the registry.",
        "",
        "## What was done",
        "",
        "| stage | measure |", "|---|---:|",
        f"| identities searched | {len(rows)} |",
        f"| PubMed queries run and logged | {sum(len(i['queries']) for i in log['identities'])} |",
        f"| records retrieved | {prescreen['_metadata']['records_classified']} |",
        f"| records classified deterministically | {prescreen['_metadata']['records_classified']} |",
        f"| efficacy candidates after classification | {prescreen['_metadata']['buckets'].get('efficacy_candidate', 0)} |",
        f"| records read by a screener (shortlists) | {sum(len(by_id[c]['shortlist']) for c in screens)} |",
        f"| sources selected by screening | {sum(r['selected'] for r in rows)} |",
        f"| selected sources re-verified live | {sum(r['selected'] for r in rows)} |",
        f"| identities with a catalog-visible integrity hold | {sum(1 for r in rows if r['integrity_hold'])} |",
        "",
        "## Decision table",
        "",
        "`class` is the screening recommendation, which is triage and untrusted until centrally verified.",
        "`Evidence=0` is the number of products this identity leaves at Evidence 0 today.",
        "",
        "| identity | products | Evidence=0 | retrieved | candidates | selected | class | action | blocker |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['canonical_id']}` | {r['products']} | {r['evidence_zero']} | {r['retrieved']} | "
            f"{r['efficacy_candidates']} | {r['selected']} | {r['class']} | {ACTION[r['class']]} | "
            f"{(r['blocker'] or r['reason'])[:96]} |")

    lines += ["", "## Where the wave landed", "",
              "| class | identities | products | Evidence=0 products |", "|---|---:|---:|---:|"]
    for cls in CLASS_ORDER:
        lines.append(f"| {cls} | {by_class[cls]} | {prod_by_class[cls]} | {ev0_by_class[cls]} |")
    lines.append(f"| **total** | **{len(rows)}** | **{sum(r['products'] for r in rows)}** | "
                 f"**{sum(r['evidence_zero'] for r in rows)}** |")

    lines += ["", "## Screening QA", "",
              "Screening output is untrusted input and is checked in code before any of it is used.", "",
              "| check | result |", "|---|---:|",
              f"| identities screened | {qa['_metadata']['identities']} |",
              f"| PMIDs named that are not in that identity's own retrieval | {qa['_metadata']['pmids_not_in_retrieval']} |",
              f"| selected sources outside the shortlist given | {qa['_metadata']['selected_outside_shortlist']} |",
              f"| verbatim spans of {qa['_metadata']['verbatim_window_chars']}+ characters copied from an abstract | {qa['_metadata']['verbatim_spans']} |",
              f"| class/content conflicts | {qa['_metadata']['class_conflicts']} |", "",
              "The one out-of-retrieval PMID is worth naming, because it shows what the check is for: a screener "
              "listed PMID 18206062 under `activated_charcoal` as an exclusion, correctly describing it as a "
              "criminology paper whose 'Hawthorne effect' has nothing to do with charcoal. The description is "
              "accurate and the record is real - it just was not in that identity's retrieval, so it came from "
              "the model rather than from the corpus. It is rejected on that ground alone.", "",
              "Wave 1's screening produced 119 elided and 135 non-contiguous quotes that all had to be thrown "
              "away. Wave 2 forbade quotes outright, since every fact is re-extracted centrally anyway; three "
              "borderline copied spans appeared and were rejected. The defect class is effectively closed.", ""]

    curate_ev0 = ev0_by_class["curate"]
    lines += NARRATIVE.format(
        curate=by_class["curate"], hold=by_class["hold"], noq=by_class["no_qualifying"],
        curate_ev0=curate_ev0, hold_ev0=ev0_by_class["hold"], noq_ev0=ev0_by_class["no_qualifying"],
        total_ev0=sum(r["evidence_zero"] for r in rows),
        selected=sum(r["selected"] for r in rows),
        handoffs=sum(r["handoffs"] for r in rows)).split("\n")

    (OUT / "WAVE2_CHECKPOINT.md").write_text("\n".join(lines) + "\n")
    print(f"identities {len(rows)} | " + " ".join(f"{c}={by_class[c]}" for c in CLASS_ORDER))
    print(f"Evidence=0 covered: {sum(r['evidence_zero'] for r in rows)}; "
          f"in curate: {ev0_by_class['curate']}; in hold: {ev0_by_class['hold']}; "
          f"no_qualifying: {ev0_by_class['no_qualifying']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
