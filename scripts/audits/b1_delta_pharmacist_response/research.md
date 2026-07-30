# B1 delta pharmacist-response reconciliation — 2026-07-30

Scope: the 11-record B1 clinical-copy delta only.

The PharmaGuide Clinical Team returned:

- 7 records approved as written;
- 2 records approved after exact wording changes;
- 2 records requiring evidence revision;
- 0 records removed.

Global licensed-pharmacist sign-off remains false because the response did not
review the supplied app unavailable/partial presentation or clinician PDF, and
the two evidence revisions require a final exact-current recheck after they are
authored.

## Primary-source verification

### Acid suppressants → iron

- Lam et al., PMID 27890768: observational association after at least two years;
  stronger with dose/duration; association attenuated after discontinuation.
- Hutchinson et al., PMID 17344278: PPI suppression of non-haem iron absorption
  in hereditary haemochromatosis.
- Snook et al., BSG adult IDA guideline, PMID 34497146 / Gut 2021:
  ferritin is the most useful marker, blood testing is part of diagnosis, and
  confirmed IDA requires investigation for its underlying cause.

Authored resolution: use the pharmacist-supplied discontinuation caveat, add
the BSG management guideline, and explicitly tell users not to stop the acid
reducer independently.

### Levothyroxine → calcium

- Levothyroxine DailyMed set
  `a8db0f7d-8863-9309-e053-2995a90a284a` directs administration on an empty
  stomach and at least four hours apart from calcium/iron products.

Authored resolution: use the exact pharmacist replacement in `recommendation`.

### Orlistat → vitamin A

- XENICAL DailyMed set `6240792b-9224-2d10-e053-2a91aa0a2c3e` directs a daily
  multivitamin containing A/D/E/K plus beta-carotene at least two hours apart
  (bedtime is an example) and states that XENICAL is contraindicated in
  pregnancy.
- NIH ODS Vitamin A supports avoiding excess preformed vitamin A in pregnancy.

Authored resolution: use the exact pharmacist replacement in `recommendation`.

### SSRIs → sodium

- De Picker et al., PMID 25262043: class review supporting SSRI-associated
  hyponatremia/SIADH and risk groups.
- Sertraline DailyMed set
  `4883ccdf-0e02-579d-e054-00144ff88e88`: hyponatremia symptoms include
  headache, confusion, weakness and unsteadiness; severe/acute cases can
  include syncope, seizure and coma.
- Leth-Møller et al., PMID 27194321 / BMJ Open 2016: risk was highest in the
  first 14 days after treatment initiation.

Authored resolution: add the label and population study and narrow the record
from “starting or increasing” to treatment initiation, because the supplied
evidence does not establish a class-wide post-dose-increase window.

## Governance disposition

The delta ledger records the returned per-record dispositions and their
implementation state. It must not claim final licensed-pharmacist sign-off
until:

1. the two evidence-revision records are rechecked in their exact-current form;
2. the verified/unavailable/partial app states are reviewed; and
3. the current clinician report/PDF is reviewed.
