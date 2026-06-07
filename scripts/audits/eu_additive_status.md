# EU Food Regulatory Status — `harmful_additives.json` Additives

**Date:** 2026-06-07
**Source file:** `scripts/data/harmful_additives.json` (schema 5.4.0, 116 entries)
**Scope:** EU FOOD/SUPPLEMENT regulatory status only. US bans are explicitly excluded from the bucket decision.
**Standard:** Every BANNED/RESTRICTED claim is tied to a named EU instrument (Regulation / Directive / Annex / EFSA opinion). Items I could not tie to a specific instrument are marked UNVERIFIED.

## Key scoping finding

Several "famous" EU-banned additives the brief asked about are **NOT present in this file** and therefore cannot be moved to a watchlist here:
**titanium dioxide (E171), potassium bromate, brominated vegetable oil (BVO), azodicarbonamide, FD&C Red No. 3 / erythrosine.**
They were searched by `standard_name` + `aliases` and returned no match. If these are wanted on the watchlist they must first be added as entries. (E171's status is documented in the BANNED table below for reference, flagged "NOT IN FILE.")

**Critical distinction applied:** The "Southampton Six" colours (in this file: Yellow 5 / E102, Yellow 6 / E110, Red 40 / E129) are **RESTRICTED (mandatory hyperactivity warning)**, NOT banned. They remain legally authorised in the EU. Only genuinely *prohibited-for-food* items are placed in BANNED.

---

## BANNED — prohibited for EU food use (watchlist-move candidates)

| additive (id) | standard_name | EU status | regulation citation | effective date | confidence | source URL |
|---|---|---|---|---|---|---|
| `ADD_GREEN3` | FD&C Green No. 3 (E143, Fast Green FCF) | **BANNED** | Not on the EU positive list (Annex II) of **Regulation (EC) No 1333/2008**. E143 is one of the colours authorised in the US but not permitted in the EU. | Positive-list regime in force 20 Jan 2010 | high | https://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ:L:2008:354:0016:0033:en:PDF |
| `ADD_PROPYLPARABEN` | Propylparaben (E216) | **BANNED** | Authorisation withdrawn by **Directive 2006/52/EC**, following **EFSA 2004 opinion** (ADI invalidated — adverse effects on sex hormones / male reproductive organs in juvenile rats). E216 + E217 removed from authorised food additives. | 2006 (UK also prohibits E216 in food) | high | https://www.efsa.europa.eu/en/efsajournal/pub/83 |
| *(NOT IN FILE)* | Titanium dioxide (E171) | **BANNED** (reference only) | **Commission Regulation (EU) 2022/63** withdrew the E171 authorisation, following **EFSA May 2021** opinion (genotoxicity concern, no safe level establishable). In force 7 Feb 2022; 6-month transition. | No food on market after **7 Aug 2022** | high | https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32022R0063 |

> The file's own `jurisdictional_statuses` already encodes `ADD_GREEN3` EU `status_code: "banned"`. `ADD_PROPYLPARABEN` EU ban is captured in its `regulatory_status.EU` prose but NOT yet in a `jurisdictional_statuses` `banned` record — worth adding for machine-readability.

---

## RESTRICTED — permitted in EU but with mandatory warning / strict limit

| additive (id) | standard_name | EU status | regulation citation | effective date | confidence | source URL |
|---|---|---|---|---|---|---|
| `ADD_YELLOW5` | FD&C Yellow No. 5 (E102, Tartrazine) | **RESTRICTED** — Southampton hyperactivity warning | **Regulation (EC) No 1333/2008, Art. 24 + Annex V**: "may have an adverse effect on activity and attention in children." Authorised; ADI 7.5 mg/kg bw/day (EFSA 2009). | Warning mandatory 20 Jul 2010 | high | https://www.legislation.gov.uk/eur/2008/1333/contents |
| `ADD_YELLOW6` | FD&C Yellow No. 6 (E110, Sunset Yellow FCF) | **RESTRICTED** — Southampton hyperactivity warning | Reg (EC) 1333/2008, Art. 24 / Annex V. Authorised; ADI 4 mg/kg bw/day (EFSA 2009). | 20 Jul 2010 | high | https://www.legislation.gov.uk/eur/2008/1333/contents |
| `ADD_RED40` | FD&C Red No. 40 (E129, Allura Red AC) | **RESTRICTED** — Southampton hyperactivity warning | Reg (EC) 1333/2008, Art. 24 / Annex V. Authorised; ADI 7 mg/kg bw/day (EFSA 2009, unchanged). | 20 Jul 2010 | high | https://www.legislation.gov.uk/eur/2008/1333/contents |
| `ADD_PARTIALLY_HYDROGENATED_CORN_OIL` | Partially Hydrogenated Corn Oil (industrial trans fat) | **RESTRICTED** — capped, not banned | **Regulation (EU) 2019/649**: max **2 g industrial trans fat per 100 g fat** in food for final consumer/retail. | Applicable **1 Apr 2021** | high | https://eur-lex.europa.eu/eli/reg/2019/649/oj/eng |
| `ADD_HYDROGENATED_COCONUT_OIL` | Partially Hydrogenated Coconut Oil (industrial trans fat) | **RESTRICTED** — capped, not banned | Regulation (EU) 2019/649, 2 g/100 g fat limit. (Fully hydrogenated coconut oil = no trans fat, permitted.) | 1 Apr 2021 | high | https://eur-lex.europa.eu/eli/reg/2019/649/oj/eng |
| `ADD_CARMINE_RED` | Carmine Red / Cochineal (E120) | **RESTRICTED** — mandatory allergen labelling | Authorised (Reg (EC) 1333/2008) with purity criteria; allergen-labelling obligation. Distinct basis from Southampton warning. | — | med | https://world.openfoodfacts.org/facets/additives |
| `ADD_CARAMEL_COLOR` | Caramel Color (E150a–d) | **RESTRICTED** — per-class limits / 4-MEI purity criteria | Authorised under Reg (EC) 1333/2008 with maximum-use-level + purity criteria per caramel class (E150a/b/c/d). Not a warning-label item. | — | med | https://food.ec.europa.eu/food-safety/food-improvement-agents/additives/eu-rules_en |

> **Not Southampton dyes:** Blue 1 (E133) and Blue 2 (E132) are authorised **without** the hyperactivity warning → classified PERMITTED below, not RESTRICTED.

---

## PERMITTED — authorised in EU without special restriction

| additive (id) | standard_name | EU code | EU status | citation | confidence | source |
|---|---|---|---|---|---|---|
| `ADD_BLUE1` | FD&C Blue No. 1 | E133 | PERMITTED (ADI 6 mg/kg, EFSA 2010) | Reg (EC) 1333/2008 positive list | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_BLUE2` | FD&C Blue No. 2 | E132 | PERMITTED (ADI 5 mg/kg, EFSA 2014, reconfirmed 2023) | Reg (EC) 1333/2008 positive list | high | https://www.efsa.europa.eu/en/efsajournal/pub/3768 |
| `ADD_BHA` | Butylated Hydroxyanisole | E320 | PERMITTED (max use levels; ADI 1.0 mg/kg, EFSA 2011). NOT banned. | Commission Reg (EU) No 1129/2011 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_BHT` | Butylated Hydroxytoluene | E321 | PERMITTED (max use levels; ADI 0.25 mg/kg) | Commission Reg (EU) No 1129/2011 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_TBHQ` | Tertiary Butylhydroquinone | E319 | PERMITTED (max use levels). (Banned in Japan, NOT EU.) | Commission Reg (EU) No 1129/2011 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_PROPYLENE_GLYCOL` | Propylene Glycol | E1520 | PERMITTED (ADI 25 mg/kg) | Reg (EC) 1333/2008 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_POLYSORBATE80` | Polysorbate 80 | E433 | PERMITTED | Reg (EC) 1333/2008 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_CARRAGEENAN` | Carrageenan | E407 / E407a | PERMITTED (temp. group ADI 75 mg/kg, EFSA 2018) | Reg (EC) 1333/2008 | high | https://efsa.onlinelibrary.wiley.com |
| `ADD_MSG` | Monosodium Glutamate | E621 | PERMITTED with limits (group ADI 30 mg/kg, EFSA 2017) | Reg (EC) 1333/2008 | high | https://doi.org/10.2903/j.efsa.2017.4910 |
| `ADD_SODIUM_BENZOATE` | Sodium Benzoate | E211 | PERMITTED (ADI 5 mg/kg, EFSA 2016) | Reg (EC) 1333/2008 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_METHYLPARABEN` | Methylparaben | E218 | PERMITTED (ADI 10 mg/kg). Distinct from propylparaben — NOT banned. | Reg (EC) 1333/2008 | high | https://www.efsa.europa.eu/en/efsajournal |
| `ADD_SODIUM_LAURYL_SULFATE` | Sodium Lauryl Sulfate | E487 | PERMITTED (quantum satis in specific categories; EFSA 2018 no concern) | Reg (EC) 1333/2008 | med | https://www.efsa.europa.eu/en/efsajournal |

---

## UNVERIFIED — could not tie to a specific EU instrument

| additive (id) | standard_name | note |
|---|---|---|
| `ADD_ALUMINUM_LAKE_GENERIC` | Aluminum Lake (Unspecified Color) | Generic/umbrella entry — `regulatory_status` is `null`. EU status of an "aluminium lake" depends on the underlying colour (E173 aluminium itself is restricted; aluminium lakes of permitted colours are allowed with Al-content limits per Reg (EU) 380/2012). Cannot assign a single bucket to an unspecified-colour umbrella. Mark UNVERIFIED pending decomposition into specific colours. |
| `ADD_MINERAL_OIL` | Mineral Oil | EU action is **in-progress, not yet a prohibition**: draft Commission regulation on MOAH limits (EFSA 2023 opinion, doi:10.2903/j.efsa.2023.8215); France restricts MOAH in food-contact inks. No EU food-use ban citable today → not BANNED. Effectively PERMITTED-with-pending-restriction; left UNVERIFIED for "banned" purposes. |

---

## Verification log (what was live-checked vs. relied-on-from-file)

**Live web-verified this session (high confidence):**
- E143 / Green 3 not on EU positive list (Reg (EC) 1333/2008) — confirmed.
- E216 / Propylparaben withdrawn via Directive 2006/52/EC + EFSA 2004 — confirmed.
- E171 / Titanium dioxide ban Reg (EU) 2022/63, food off-market 7 Aug 2022 — confirmed (item not in file).
- Southampton Six warning = Art. 24 + Annex V of Reg (EC) 1333/2008, mandatory 20 Jul 2010 — confirmed.
- Industrial trans fat 2 g/100 g cap = Reg (EU) 2019/649, applicable 1 Apr 2021 — confirmed.
- E132 / Blue 2 authorised (EFSA 2014, ADI 5 mg/kg) — confirmed.

**Relied on existing file `regulatory_status` (uncontroversial, not re-litigated):** E133, E320, E321, E319, E1520, E433, E407, E621, E211, E218, E487, E150, E120 — all consistent with EU positive-list authorisation; flagged med where the file lacked a `jurisdictional_statuses` record.
