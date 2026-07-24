# Section 2 — remaining acid-reduction records — audit report

- **reviewer:** `lead_clinician_acid_reduction` · **2026-07-24**
- **outcome:** 2 verified · 2 rejected (evidence-based). All 12 PMIDs live-verified against PubMed.

## Dispositions

| Record | Verdict | New scope | drug_ref |
|--------|---------|-----------|----------|
| iron | **verified** | PPI **+ H2** | NEW `class:acid_suppressants` |
| calcium | **verified** | **PPI-only** | `class:proton_pump_inhibitors` |
| vitamin C | **rejected** (evidence-based) | — | suppressed |
| zinc | **rejected** (evidence-based) | — | suppressed |

Root problem: all four sat on `class:antacids` ("PPIs and antacids"), but the
mechanism is acid-SUPPRESSION (PPI/H2), and a calcium-carbonate antacid is itself
a calcium *source* — so "neutralizing antacid → depletion" is incoherent.

- **iron → `class:acid_suppressants`** (new PPI+H2 composite): Lam 2017 shows a
  dose-response for BOTH tiers (PPI OR 2.49, H2 OR 1.58) → the one relationship
  that justifies the combined class. + Hutchinson 2007 (mechanism).
- **calcium → PPI-only**: fracture epi is PPI-specific (Yang, Poly — H2 null);
  mechanism is calcium-carbonate-on-empty-stomach (Recker: citrate fine, food
  rescues; Serfaty: no effect from food). Framed as modest, confounded.
- **vitamin C → rejected**: one small study (Henry 2005: −12%, "clinical
  significance unclear"); rest is intragastric (cancer mechanism, not status).
  Not a defensible consumer warning. Documented, not a data gap.
- **zinc → rejected**: only acute fasting supplement-salt absorption
  (Sturniolo/Ozutemiz); food zinc unaffected (Serfaty); no deficiency shown.

All four dropped the Pelton-handbook / NIH-ODS-fact-sheet placeholders for
primary PMIDs. Unsupported `adequacy_threshold_*` comparison amounts removed.

## New taxonomy
`class:acid_suppressants` = PPI (A02BC) + H2 blockers (A02BA), 9 members,
RxNorm-verified. Distinct from `class:antacids` (neutralizers) and
`class:proton_pump_inhibitors` (PPI-only).

---

## Rides along: critical rxcui-identity fix (Codex 2026-07-24 audit, verified)

A live-RxNorm audit flagged 9 stale/swapped member rxcuis in `drug_classes.json`,
embedded in the shipped interaction DB — verified against RxNorm and corrected:

| class / drug | was | is |
|---|---|---|
| bisphosphonates: alendronate | 3009 (retired) | 46041 |
| bisphosphonates: ibandronate | 42470 (retired) | 115264 |
| bisphosphonates: risedronate | 35894 (retired) | 73056 |
| bisphosphonates: zoledronic acid | 77634 (retired) | 77655 |
| antiplatelet_agents: prasugrel | 73731 (retired) | 613391 |
| antiplatelet_agents: ticagrelor | 323455 (retired) | 1116632 |
| proton_pump_inhibitors + acid_suppressants: lansoprazole | 112002 (retired) | 17128 |
| fluoroquinolones: moxifloxacin | **6922 = metronidazole** | 139462 |
| fluoroquinolones: ofloxacin | **139462 = moxifloxacin** | 7623 |

Retired ids → missed warnings (a user's current-rxcui med never matches);
the moxi/oflox swap → wrong warnings. Now guarded by
`test_no_known_stale_rxcuis` + `test_corrected_drug_rxcuis_present` (static) and a
new live gate `scripts/api_audit/verify_drug_class_rxcuis.py` (release-time).
Also fixed: `release_full.sh` now stages `medication_depletions.json` (was
omitted); the primary depletion card's error branch now shows the unavailable
card instead of rendering nothing (B1.2 "unavailable is never clean").

## Outcome
2 verified · 2 rejected. Corpus verified floor → ≥21. drug_class_map changes
(new class:acid_suppressants + PPI/bisphosphonate/antiplatelet/fluoroquinolone
rxcui corrections) → app propagation with a rebuilt interaction DB + new Release.
