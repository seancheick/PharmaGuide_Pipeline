# Shared standard: glucosamine and chondroitin for osteoarthritis (2026-10-28)

Applies identically to INGR_CHONDROITIN_SULFATE (lane 3) and INGR_GLUCOSAMINE_SULFATE (lane 2).
Binding basis: Dr. Pham's third ruling set (DR_PHAM_RULINGS_20261028.md): "ACR (Sept 2026)
recommends against both; VA/DoD (May 2026) finds evidence insufficient for or against. Never zero
one while keeping broad credit for the other."

## Guideline sources (fetched and read 2026-10-28)
- ACR 2026 OA guideline summary, posted 14 Sep 2026:
  https://assets.contentstack.io/v3/assets/bltee37abb6b278ab2c/bltb3d12c34020da842/oa-guideline-summary-2026.pdf
  Recommendation table: "In people with knee, hip, and hand OA, we strongly recommend against
  glucosamine, chondroitin, and combination preparations of glucosamine and chondroitin." Strength:
  Strong. Certainty: low for glucosamine alone, moderate for the combination; the summary does not
  print a separate certainty for chondroitin alone. Marked as a change of direction since 2019.
- VA/DoD CPG for the Non-Surgical Management of Hip & Knee OA, Version 3.0, May 2026:
  https://www.healthquality.va.gov/HEALTHQUALITY/guidelines/CD/OA/Osteoarthritis-CPG_2026-Guideline_final_20260618.pdf
  Recommendation 30 (pp. 69-70): insufficient evidence to recommend for or against chondroitin,
  glucosamine, or glucosamine plus chondroitin (neither for nor against). Discussion: evidence mixed
  (one SR found placebo better than the combination); confidence very low; effect sizes judged likely
  below a clinically meaningful difference; trial products (e.g. laboratory standardized) may differ
  from consumer products.

## The standard (same outcome for both ingredients)
1. No routine joint, knee, hip or hand credit for either ingredient, alone or combined. Both records
   are completed no-credit assessments on the existing reference path (study_type/evidence_level
   "reference"; approved contexts with scoring_eligible false). Neither record keeps broad credit
   while the other is zeroed.
2. This is "no applicable qualifying support", not "not studied" and not "proven ineffective": every
   context keeps its true source directions (e.g. small short-term pain benefits where the source
   shows them), and limitations cite both guidelines.
3. Exact-preparation evidence (e.g. pharmaceutical-grade or prescription preparations, a specific
   salt or brand) is recorded with its own identity and direction but cannot override the two
   guidelines for retail-supplement credit in this batch. Any future preparation-specific credit needs
   a new explicit Dr. Pham decision; it is not inferred here.
4. No new applicability block, dose threshold or excluded-claim policy is added for either record.

## Shared rationale text (paste verbatim as a limitation in both patches)
"Shared OA supplement standard (2026-10-28): the ACR 2026 guideline strongly recommends against
glucosamine, chondroitin and their combination for knee, hip and hand OA (certainty low for
glucosamine alone, moderate for the combination), and the VA/DoD 2026 guideline (Recommendation 30)
finds insufficient evidence for or against them (very low confidence; effects likely below a
clinically meaningful difference). Per Dr. Pham's 2026-10-28 ruling, glucosamine and chondroitin
records use one standard: completed no-credit on the reference path with true source directions
retained; exact-preparation findings are recorded but do not create retail-supplement credit."
