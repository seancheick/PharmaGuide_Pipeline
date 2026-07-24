# Section 2 — remaining acid-reduction records (calcium, iron, vitamin C, zinc)

Reviewer: `lead_clinician_acid_reduction` · 2026-07-24

All 12 PMIDs independently content-verified against live PubMed. **2 verified · 2 rejected.**

Central finding: these four sat on `class:antacids` ("PPIs and antacids"), but the
mechanism is acid-SUPPRESSION (PPI/H2), not neutralizing antacids — and a
calcium-carbonate antacid is itself a calcium *source*. Each re-scoped to what the
evidence supports; neutralizing antacids are NOT a depletion mechanism for any.

| Record | Verdict | New scope | drug_ref |
|--------|---------|-----------|----------|
| iron | **SUPPORTED** | PPI **+ H2** (spans both tiers) | NEW `class:acid_suppressants` |
| calcium | **SUPPORTED-BUT-NARROW** | **PPI-only** (H2 null in fracture meta) | `class:proton_pump_inhibitors` |
| vitamin C | **REJECT** (as depletion) | — | rejected/suppressed |
| zinc | **REJECT** (as depletion) | — | rejected/suppressed |

## 1. Iron — SUPPORTED (verified) → class:acid_suppressants

The one relationship that spans both tiers → justifies the new combined class.
- **PMID 27890768** Lam JR, *Gastroenterology* 2017 — ≥2 yr PPI: iron-deficiency OR **2.49** (2.35–2.64); ≥2 yr H2RA (no PPI): OR **1.58** (1.46–1.71); dose-response, **reversible** after stopping. 77,046 cases. (Both tiers significant in one cohort → PPI+H2 class.)
- **PMID 17344278** Hutchinson C, *Gut* 2007 — 7-day PPI cut non-haem iron absorption from a test meal (serum-iron AUC 2145→1059; %recovery 20.5→11.0, p<0.01). Mechanism (hereditary haemochromatosis; hyper-absorbers, so mechanism-clean not general-deficiency).
NOT supported: short-term/occasional use; heme iron; antacid *depletion* (antacids reduce iron co-ingested in the same dose — a timing interaction, not depletion).

## 2. Calcium — SUPPORTED-BUT-NARROW (verified) → class:proton_pump_inhibitors

Fracture epi is **PPI-specific**; H2 null. Mechanism = calcium CARBONATE on an empty stomach only.
- **PMID 4000241** Recker RR, *NEJM* 1985 — achlorhydria: fasting carbonate fractional absorption 0.04 vs citrate 0.45 (p<0.0001); **food normalized carbonate**. (carbonate needs acid; citrate doesn't; food rescues.)
- **PMID 15989913** O'Connell MB, *Am J Med* 2005 — 7-day omeprazole reduced fasting calcium-carbonate absorption in older women (RCT crossover). ⚠️ no abstract in eutils — direction verified, exact % from PDF only (did NOT transcribe figures).
- **PMID 17190895** Yang YX, *JAMA* 2006 — >1 yr PPI hip-fracture AOR **1.44** (1.30–1.59); high-dose 2.65. Behind the 2010 FDA communication.
- **PMID 30539272** Poly TN, *Osteoporos Int* 2019 — PPI hip-fracture RR **1.20** (1.14–1.28), 24 studies; explicitly **"not observed in H2RA."** (scope anchor)
- **PMID 8568113** Serfaty-Lacrosniere C, *J Am Coll Nutr* 1995 — omeprazole: **no** change in calcium absorption from a food meal (counter-evidence → carbonate-fasting-specific).
NOT supported: H2/antacid calcium depletion; citrate acid-dependence; carbonate-with-food malabsorption; a calcium-antacid "depleting" calcium (it IS a calcium source). Frame as modest, confounded association.

## 3. Vitamin C — REJECT as a depletion warning (evidence-based)

Only one small systemic study; the rest is intragastric (cancer mechanism, not nutrition).
- **PMID 16167970** Henry EB, *Aliment Pharmacol Ther* 2005 — omeprazole 40 mg × 4 wk: plasma vit C **−12.3% (p=0.04)**, authors say **"clinical significance is unclear"**; concentrated in H. pylori+/low-baseline. n=29.
- **PMID 10092303** Mowat C, *Gastroenterology* 1999 / **PMID 10930369** Mowat 2000 — *gastric-juice* ascorbate (N-nitrosation/cancer mechanism, NOT body status); Hp-dependent.
→ Reject: no clinically meaningful depletion; no H2/antacid data; irrelevant to well-nourished Hp− people. Retire the Pelton handbook cite; document with Henry 2005.

## 4. Zinc — REJECT as a depletion warning (evidence-based)

Only acute PK of fasting soluble zinc salts; contradicted for food zinc; no deficiency shown.
- **PMID 1894892** Sturniolo GC, *J Am Coll Nutr* 1991 — cimetidine/ranitidine (**H2**) reduced absorption of an oral **ZnSO₄ 220 mg** load (p<0.005/0.01). Fasting supplement salt.
- **PMID 12546170** Ozutemiz AO, *Indian J Gastroenterol* 2002 — omeprazole (**PPI**) reduced zinc AUC after 300 mg ZnSO₄ (p<0.01). Fasting supplement salt. (no DOI; cite by PMID)
- **PMID 8568113** Serfaty-Lacrosniere 1995 — omeprazole: **no** change in zinc absorption from **food**.
→ Reject: supported only for fasting supplement salts, contradicted for food, no clinical deficiency. Retire the Pelton handbook cite; document with the three PMIDs.

## New taxonomy
`class:acid_suppressants` = PPI (A02BC: esomeprazole, lansoprazole, omeprazole, pantoprazole, rabeprazole) + H2 (A02BA: cimetidine, famotidine, nizatidine, ranitidine). 9 members, RxNorm-verified. Distinct from `class:antacids` (neutralizers) and `class:proton_pump_inhibitors` (PPI-only).

## Outcome
2 verified (iron→acid_suppressants, calcium→PPI) · 2 rejected (vitamin C, zinc — evidence-based, documented). Corpus verified floor → ≥21.
