# Section 3 — Antiseizure medication relationships: final disposition

**Completed:** 2026-07-26 · **Authoring script:** `apply.py` (idempotent) ·
**Runtime artifact:** interaction DB v1.0.3 (published before merge)

## Scope correction

The original seven records used `class:anticonvulsants`, a 40-member umbrella
that mixes enzyme inducers, the CYP inhibitor valproate, and medicines without
the relevant mechanism. Section 3 replaces that broad attribution with
drug-specific or mechanism-specific scopes. A record is shown to users only
when its citation review is `verified`; `needs_revision` remains intentionally
suppressed.

| Record | Final runtime scope | Evidence / citation result | Final disposition |
|---|---|---|---|
| Vitamin D | carbamazepine (RxCUI 2002) | Established; PMID 34847425 content-verified | **Verified, carbamazepine-specific.** No class-wide antiseizure inference. |
| Calcium | enzyme-inducing antiseizure class | Established bone-health context; PMID 15123011 content-verified | **Verified, narrowed.** No universal calcium dose is recommended. |
| Folate | phenytoin (RxCUI 8183) | Established; PMID 6370643 content-verified | **Verified, phenytoin-specific.** |
| Vitamin B12 | phenytoin (RxCUI 8183) | Probable; PMID 30896627 content-verified | **Verified, phenytoin-specific.** The mechanism remains uncertainty-preserving. |
| Vitamin K | enzyme-inducing antiseizure class, pregnancy context only | Possible; PMIDs 16812962 and 8456897 content-verified | **Verified, pregnancy-specific and uncertainty-preserving.** It does not claim routine prophylaxis for all patients. |
| L-carnitine | `class:valproate` | Probable; PMID 8040784 content-verified | **Verified, valproate-specific.** Copy is limited to chronic/long-term treatment context; it does not extrapolate to all antiseizure medicines. |
| Biotin | `class:anticonvulsants` labelled “scope under review” | Possible; PMIDs 9371938 and 9523856 do not establish valproate-specific effect | **Suppressed (`needs_revision`).** It cannot ship until an exact, supportable scope is established. |

`class:valproate` covers the RxNorm-verified dispensed forms divalproex sodium
(266856), sodium valproate (9919), valproate (40254), and valproic acid
(11118). It is deliberately separate from
`class:enzyme_inducing_antiseizure_medications`: none of those four identifiers
may resolve to the enzyme-inducing class. The runtime release guard and Flutter
bridge tests assert both positive and negative membership.

## Citation-audit containment outside Section 3

Eleven unrelated records were suppressed pending their own family audits after
the content gate found real-but-unrelated PMIDs:

`DEP_OCP_MAGNESIUM`, `DEP_OCP_ZINC`, `DEP_ANTIPSYCHOTICS_VITAMIND`,
`DEP_ANTIPSYCHOTICS_COQ10`, `DEP_STIMULANTS_VITAMINC`,
`DEP_HIVPI_VITAMIND`, `DEP_HIVPI_ZINC`, `DEP_IMMUNOSUPPRESSANTS_MAGNESIUM`,
`DEP_IMMUNOSUPPRESSANTS_VITAMIND`, `DEP_BENZODIAZEPINES_MELATONIN`, and
`DEP_BVITAMINS_INTERACTIONS`.

This is a safe containment action, not a verification of the underlying claim.
The oral-contraceptive magnesium and zinc records are therefore explicitly part
of Section 4 and must not be reactivated without a record-level content review.

## Verification record

- Live PubMed content gate: 8 reviewed Section 3 citation expectations matched.
- Live RxNorm identity gate: direct medication identifiers and referenced classes resolved.
- Pipeline fast suite: **10,832 passed, 40 skipped**.
- Flutter artifact parity and focused stack tests: passed before runtime release;
  the v1.0.3 hydration and real bridge checks are the release prerequisites.

No enrichment, scoring, or dashboard rebuild is part of this section: the
records are reference data consumed by the medication-depletion and interaction
runtime path, not by the product-score pipeline.
