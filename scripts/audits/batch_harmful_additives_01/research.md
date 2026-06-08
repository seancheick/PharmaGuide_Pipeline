# Harmful-Additive Severity Recalibration — Batch 1 (colorants + BHA/BHT)

**Status:** RESEARCH-ONLY (no data edits yet — awaiting user sign-off). Date: 2026-06-08.
**Scope:** 9 artificial colorants + BHA/BHT (11 entries) in `scripts/data/harmful_additives.json`.
**Method:** 3 parallel opus research subagents, content-verified vs EFSA / FDA / IARC / NTP /
OEHHA Prop 65 / EU Reg (EC) 1333-2008. Every regulatory claim carries a real source URL; IARC
groups left UNVERIFIED where the official DB could not be confirmed (no invented groups).

## Verified findings + proposed changes

| id | additive | severity cur→prop | clean_label tier | dominant verified driver |
|---|---|---|---|---|
| ADD_YELLOW5 | FD&C Yellow 5 / Tartrazine / E102 | moderate → **moderate** (keep) | **elevated** | EU mandatory warning label (Reg 1333/2008, since 2010-07-20) |
| ADD_YELLOW6 | FD&C Yellow 6 / Sunset Yellow / E110 | moderate → **moderate** (keep) | **elevated** | EU mandatory warning label |
| ADD_RED40 | FD&C Red 40 / Allura Red / E129 | moderate → **moderate** (keep) | **elevated** | EU mandatory warning label |
| ADD_GREEN3 | FD&C Green 3 / Fast Green FCF | moderate → **high** | **elevated** | NOT on EU positive list (EU green is E142 Green S) — CONFIRMED |
| ADD_BLUE1 | FD&C Blue 1 / Brilliant Blue / E133 | moderate → **low** | informational | authorized US+EU, no major safety signal |
| ADD_BLUE2 | FD&C Blue 2 / Indigotine / E132 | moderate → **low** | informational | authorized US+EU, no major safety signal |
| ADD_CARAMEL_COLOR | Caramel Color / E150a-d | moderate → **moderate** (keep) | informational (elevated only E150d) | 4-MEI in E150d/Class IV = IARC 2B + Prop 65 |
| ADD_ALUMINUM_LAKE_GENERIC | Aluminium Lake (generic) | moderate → **moderate** (keep) | informational | Al TWI contributor; inherits parent-dye status |
| ADD_UNSPECIFIED_COLORS | Unspecified Colors (catch-all) | low → **low** (keep) | informational | unknown identity → transparency flag, not safety DQ |
| ADD_BHA | Butylated Hydroxyanisole / E320 | high → **high** (keep) | **elevated** | IARC 2B (Vol 40/Suppl 7) + NTP RoC listed + Prop 65 (1990) |
| ADD_BHT | Butylated Hydroxytoluene / E321 | moderate → **low** (low-to-moderate) | informational | IARC Group 3; NOT NTP-listed; NOT Prop 65 — differs sharply from BHA |

## 3 notable discoveries

1. **GAP — FD&C Red 3 / Erythrosine / E127 is MISSING and was FDA-REVOKED 2025-01-15**
   (Delaney Clause; food compliance 2027-01-15, drugs 2028-01-18). Fed. Reg. 90 FR 4628
   (2025-01-16). → Propose ADD it: severity **high**, clean_label **elevated**. A real US ban,
   distinct from the Southampton three. (FDA notes the rat-forestomach mechanism is not
   human-relevant, but the authorization revocation is a hard regulatory fact.)
2. **Green 3 dual-listing reconciliation** — Green 3 is in BOTH `banned_recalled` (high_risk,
   CAUTION, from clean-label work) AND `harmful_additives` (moderate, B1). The banned_recalled
   premise (EU-non-permitted for food) is CONFIRMED correct. Raise harmful_additives severity
   to high for consistency. Label nuance: "E143" is an informal/legacy number, not an EU food
   E-number — reason text should say "no EU food E-number; EU green is E142 Green S".
3. **Data-quality bugs in BHA/BHT entries (found incidentally, fix alongside):**
   - Both say `regulatory_status`/notes "GRAS" — they are 21 CFR 172.110/172.115
     (food additive PERMITTED, Subpart B), NOT GRAS. Correct the wording.
   - `ADD_BHA.gsrs.cfr_sections` = "21 CFR 171.110" is WRONG (171 = petition procedure);
     should be 172.110 (the entry's own `regulatory_status.US` already says 172.110).
   - BHT internal ADI 0.3 (JECFA) vs EFSA 2012 = 0.25 mg/kg (more recent/conservative) — note both.
   - "FDA Feb 2026 BHA reassessment" note → UNVERIFIED; flag/remove pending a primary citation.

## Clean-label policy matrix (Batch-1 output, feeds the soft-flag lane)
- **elevated** (EU-banned/restricted, mandatory-warning, or strong carcinogen signal):
  Green 3, Yellow 5, Yellow 6, Red 40, BHA, (+ Red 3 if added), (+ E150d Class-IV caramel).
- **informational** (clean-label preference, no hard regulatory/safety trigger):
  Blue 1, Blue 2, BHT, general Caramel, Aluminium Lake, Unspecified Colors.

## UNVERIFIED / confirm-before-write caveats (no-hallucination rule)
- **IARC groups for the azo dyes (Yellow 5/6, Red 40, Erythrosine): UNVERIFIED** — official IARC
  DB did not render per-substance; secondary sources conflict. Record as "none / not-evaluated",
  DO NOT write a group number.
- **EFSA exact ADI figures** (Tartrazine 7.5, Allura Red 7, Sunset Yellow 4, Blue1 6, Blue2 5,
  caramel group 300, BHA 1.0, BHT 0.25): high-confidence but several from press-release/secondary;
  confirm the primary EFSA Journal opinion PDF before writing any ADI number into the data file.
- Severity changes here rest on verified REGULATORY STATUS (EU warning label / non-permitted /
  IARC 2B / NTP / Prop 65), all URL-cited — those are the score-driving facts and are solid.

## Citations (key)
- Red 3 revocation: https://www.federalregister.gov/documents/2025/01/16/2025-00830/...
- FDA color additive status: https://www.fda.gov/industry/color-additives/summary-color-additives-use-united-states-foods-drugs-cosmetics-and-medical-devices
- BHA IARC 2B: https://www.inchem.org/documents/iarc/vol40/butylatedhydroxyanisole.html
- BHA NTP RoC: https://www.ncbi.nlm.nih.gov/books/NBK590883/  · Prop 65: https://oehha.ca.gov/proposition-65/chemicals/butylated-hydroxyanisole
- BHT IARC 3: https://www.inchem.org/documents/iarc/vol40/butylatedhydroxytoluene.html
- EFSA BHA 2011 (ADI 1.0): https://www.efsa.europa.eu/en/efsajournal/pub/2392 · BHT 2012 (0.25): https://www.efsa.europa.eu/en/efsajournal/pub/2588
- EU permitted colours (Green 3 absence; E142 is EU green): https://www.food.gov.uk/business-guidance/approved-additives-and-e-numbers
- McCann 2007 (Southampton): https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(07)61306-3/abstract
