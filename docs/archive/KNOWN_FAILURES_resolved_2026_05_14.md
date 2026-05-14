# Known Test Failures — Resolved Archive (2026-05-14)

This file is the audit trail for entries that were tracked in
`docs/KNOWN_FAILURES.md` during Sprint 1.1 and resolved on 2026-05-14.

All 6 entries below were green by the time the full pytest baseline ran
end of day (`7591 passed, 30 skipped, 30 xfailed, 0 failed`). They are
archived here, out of the active KNOWN_FAILURES.md, to keep the active
file lean. Pulling them back into rotation requires explicit re-tracking
in the live file with a new entry number.

---

## 1. `test_safety_copy_production.py::test_banned_recalled_production_strict` — RESOLVED 2026-05-14

**Surfaced during:** Multiple commits 2026-01-15 → 2026-05-13 added 9
RECALLED_* banned_recalled entries that didn't satisfy the strict
safety_warning validator's phrasing rules.

**Specific origin commits:**
- `ebec9a3` — add 2 TKS Co-pack Aonic Complete microbial recalls (2026-01-15)
- `2a78b4a` — add SiluetaYa Tejocote Class I recall (2025-10-29 recall date)
- `2a0a496` — add 2 Imu-Tek Colostrum-5 under-processing recalls (2026-02-24)
- `75fec72` — add TG Foods Divided Sunset Collagen — undeclared egg (2026-02-27)
- `865b6c9` — add 3 Pure Vitamins LLC sildenafil/tadalafil recalls (2026-03-13)
- `3ce2847` — schema-parity patch on the 9 new RECALLED_ entries (2026-05-13)
- `9db25ce` — expand RECALLED_SILUETAYA_TEJOCOTE aliases (2026-05-13)

**Validator gaps the 9 entries hit:**
- `adulterant_in_supplements` (3 entries — Pure Vitamins trio): missing
  the clinical guardrail phrase `in supplement` / `in product` / `in
  dietary` so users on prescribed versions of the same compound don't
  panic (e.g. someone on prescribed Viagra reading "undeclared sildenafil
  found in Blue Bull Extreme pouches" must read "in this supplement"
  to anchor the warning to the supplement context).
- `contamination_recall` (6 entries — TKS pair, SiluetaYa, Imu-Tek pair,
  Divided Sunset): missing one of `recalled` / `withdrawn` / `removed
  from market` / `FDA enforcement` — past-tense regulatory-action verb
  required (the original copy used the noun form "FDA Class II recall:"
  which the validator correctly does not accept).

**Resolved by:** Reauthored the 9 entries' `safety_warning` text in Dr
Pham past-tense voice (Sprint 1.1 reauthoring pass, 2026-05-14).

Pattern for adulterant entries:
```
<Product> was recalled after FDA found undeclared <drug> in this
supplement. <Harm>. Stop the supplement and consult a doctor.
```

Pattern for contamination recalls:
```
<Product> was recalled after <evidence>. Stop and consult a doctor
if symptoms develop.
```

All 9 entries pass the strict validator. Voice preserved (Dr Pham
past-tense, clinical, action-closing). Length window [50, 200] respected.

---

## 2. `test_safety_copy_production.py::test_manufacturer_violations_production_strict` — RESOLVED 2026-05-14

**Surfaced during:** `6f012cb` — feat(mfg-violations): add 10 manufacturer
recalls + recalc all 89 entries + Dr Pham voice copy (2026-05-13 sweep).

**Validator gap:** 4 entries (V082, V083, V084, V086 — the Pure Vitamins
LLC + StuffbyNainax male-enhancement set) had `brand_trust_summary` of
123 chars, outside the strict `[40, 120]` window. Also contained
semicolons (E1.1.4 punctuation contract: em-dashes only in one-liners
and brand summaries).

**Resolved by:** Trimmed each summary to 116-118 chars and swapped
semicolons for em-dashes (Sprint 1.1 reauthoring pass, 2026-05-14).
Unified pattern: `"Class I recall — <product type> with undeclared
<substance>. Stop use — <risk descriptor>."`

---

## 3. `test_validate_safety_copy.py::test_production_banned_recalled_clean_in_authoring_mode` — RESOLVED 2026-05-14

**Surfaced during:** Same commits as resolved-#1.

**Resolved by:** Same Sprint 1.1 reauthoring pass (2026-05-14). The
authoring-mode validator and strict-mode validator share the same
phrasing requirements; both went green after the 9 banned_recalled
entries were reauthored.

---

## 4. `test_form_sensitive_nutrient_gate.py` (entire file — collection error) — RESOLVED 2026-05-14

**Origin:** Pre-existing — fails on Python 3.9 (the harness's pyenv).
File used Python 3.10+ syntax `int | None` at line 122 in the
`_iter_blob_paths` function annotation.

**Failure detail:**
```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```
Affected test collection — the whole file was skipped. The file's
form-sensitive nutrient gate was not enforced as a result.

**Resolved by:** Rewrote the annotation `limit: int | None = None` to
`limit: Optional[int] = None` (the file already imported `Optional`
from `typing` at line 25, so no new import was required). Confirmed
under Python 3.9: file now collects 23 tests and all 23 pass.

**Validation:** `python3 -m pytest scripts/tests/test_form_sensitive_nutrient_gate.py -v`
→ `23 passed in 11.10s`. Commit: `d831cb7`.

---

## 5. `test_iqm_cui_cleanup.py::test_all_iqm_null_cui_entries_have_status_and_note` — RESOLVED 2026-05-14

**Surfaced during:** Sprint 2-prep (commit `e318dc8` added IQM:milk_basic_protein
schema drift introducing `cui_status: governed_null` in IQM).

**Resolved by:** Sprint 1.1 Phase A3 (commit `29d37d8`) restored IQM's
original `cui_status: "no_confirmed_umls_match"` for milk_basic_protein.
The test now passes without changing its `APPROVED_NULL_STATUSES` enum.

---

## 6. `test_other_ingredients_cui_remediation.py::test_verified_other_ingredients_gsrs_unii_fills` — RESOLVED 2026-05-14

**Surfaced during:** Sprint 2-prep (commit `3106050` governed-null'd
NHA_MALATE_GENERIC's UNII per triage policy).

**Resolved by:** Updated the test inline (commit `7c7fe70`) to assert the
new governed_null posture instead of the original CAS+UNII pinning.
Rationale documented in the assertion's docstring.
