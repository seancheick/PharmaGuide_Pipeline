# Batch 3 — sports-amino bioactives migrated to rda_optimal_uls.json

Migrated OUT of `rda_therapeutic_dosing.json` (inert there — non-botanical) and INTO
`rda_optimal_uls.json` (generic dose path), each with content-verified PMIDs (re-verified via
`verify_all_citations_content.py` → 8/8 match, 0 mismatch). `rda_ai` anchor = lower bound of the
clinically effective dose (no official DRI exists). `ul: null` / `ul_status: not_determined` — none
has a toxicity UL; the old "upper_limit" values were tolerability soft-caps.

| Ingredient | unit | optimal_range | rda_ai anchor | UL | Verified PMIDs (exact titles) |
|---|---|---|---|---|---|
| Beta-Alanine | g | 3.2–6.4 | 3.2 | none (tol. ~6.4 g/dose, paresthesia) | **26175657** ISSN position stand: Beta-Alanine (JISSN 2015) · **22270875** Effects of β-alanine supplementation on exercise performance: a meta-analysis (Amino Acids 2012) · **27797728** β-alanine supplementation to improve exercise capacity and performance: systematic review and meta-analysis (BJSM 2017) |
| Citrulline Malate | mg | 6000–8000 | 6000 | none | **20386132** Citrulline malate enhances athletic anaerobic performance and relieves muscle soreness (JSCR 2010) · **31977835** Effects of Citrulline Supplementation on Exercise Performance in Humans: A Review (JSCR 2020) |
| L-Citrulline | mg | 3000–6000 | 3000 | none | **31977835** Effects of Citrulline Supplementation on Exercise Performance in Humans: A Review (JSCR 2020) |
| HMB | g | 3 | 3 | none (≈38 mg/kg; tol. soft-cap 6 g) | **23374455** ISSN Position Stand: beta-hydroxy-beta-methylbutyrate (HMB) (JISSN 2013) · **41305674** The Role of HMB Supplementation in Enhancing the Effects of Resistance Training in Older Adults: SR & meta-analysis (Nutrients 2025) |

Discarded during verification (off-topic titles, never written): 28642676, 25401771, 28615996, 28977644,
34669012, 30343668, 30790115, 28737585, 28433617, 32824945, 36724505, 32521058.

Calculator check (representative dose): beta-alanine 3.2 g → pct_rda 100% (optimal); citrulline malate
8 g → 133%; l-citrulline 4 g → 133%; hmb 3 g → 100% — all scoring-eligible (≥25% → full v4 window credit).
