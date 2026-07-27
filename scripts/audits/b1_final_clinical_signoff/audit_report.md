# B1 final clinical-content audit

Status: **approved for controlled beta**

The AI clinical-content audit reviewed all 33 records that were
consumer-visible at the start of the final gate. Dr. Pham of the PharmaGuide
Clinical Team subsequently provided licensed-pharmacist approval for the
bounded controlled-beta corpus on 2026-07-27.

| Disposition | Count | Runtime result |
|---|---:|---|
| Approved | 18 | active |
| Approved with wording/scope change | 13 | active |
| Requires evidence revision | 1 | suppressed |
| Remove from release | 1 | rejected |

Final consumer-visible count: **31**.
Final suppressed/rejected count: **49**.
Unreviewed records in the bounded B1 sign-off scope: **0**.

## Nonapproved records

| Record | Disposition | Reason |
|---|---|---|
| `DEP_OCP_VITAMINB6` | requires evidence revision | Estrogen-containing oral-pill evidence cannot publish through the overbroad systemic hormonal class. |
| `DEP_ANTICONVULSANTS_VITAMINK` | remove from release | Pregnancy-specific, conflicting evidence cannot support a significant class-wide runtime warning without pregnancy context. |

## Material corrections

- Warfarin/vitamin K narrowed from all anticoagulants to RxCUI `11289`.
- Corticosteroid/calcium and vitamin D narrowed from a route-ambiguous class to
  long-term oral prednisone RxCUI `8640`.
- Metformin/B12 monitoring and treatment copy aligned with ADA 2026 and MHRA.
- PPI/calcium reclassified from depletion to monitoring.
- Unsupported automatic supplement advice removed from thiazide/zinc.
- SSRI/hyponatremia mechanism and monitoring timing made non-categorical.
- Methotrexate/folate copy now separates low-dose inflammatory regimens from
  oncology/rescue protocols.
- Warfarin copy now centers consistent vitamin K intake and INR stability,
  without speculative osteoporosis or vascular-calcification claims.

## Change control

`medication_depletions_b1_signoff.json` fingerprints:

- all 31 active clinical records, including citations and consumer copy;
- the exact membership of every class referenced by an active record;
- all 33 final dispositions and review rationales.

The release test fails if active copy, citations, active status, or class
membership changes without a new evidence review and ledger update.

The machine-readable ledger preserves the AI audit as supporting provenance
and records Dr. Pham's licensed-pharmacist sign-off as the release authority.
