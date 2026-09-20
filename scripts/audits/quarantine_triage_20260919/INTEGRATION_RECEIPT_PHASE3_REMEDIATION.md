# Integration Receipt — Phase-3 Remediation (2026-09-20)

**Prepared for:** Integrator · **Authority:** PharmaGuide Team acceptance, 2026-09-20
**Source branch:** `remediation/quarantine-clearing-20260919` · **Base:** `124982a0`
**Status:** Engineering implementation ACCEPTED FOR INTEGRATION REVIEW. Production release NOT approved. Branch is CLOSED to new feature work.

---

## 1. Cherry-pick set (order matters)

| Order | SHA | Content | Required? |
|---|---|---|---|
| 1 | `77cbb38c` | Phase-3 remediation: omega aggregate-owner survival, context-driven spec limits, standardization markers, %DV guard, IQM marker entries + vocab category, tests, replay harnesses (10 files, +1573/−42) | **Required** |
| 2 | `7ebf6c46` | Completes `77cbb38c`'s own contract: overlap-guard pin += 2 marker dual classifications (1 file, +4) | **Required — same review, never without #1** |
| — | `af9ae8d6` | Handoff docs (team's option: preserve in-repo) | Optional, at integrator discretion |

Cherry-pick **together and in that order**. Do NOT merge to `main`, publish, or rebuild production. Do NOT cherry-pick onto a branch carrying the peer session's uncommitted digestive-enzyme work without the coordination step in §8.

## 2. Cherry-pick review item: inspect `git show 7ebf6c46` directly

Team acceptance is conditional on the follow-up being pin-extension-only. Verified at receipt time — the entire diff is:

```diff
@@ -341,6 +341,10 @@ def test_iqm_banned_overlap_set_is_only_intentional_high_risk_dual_classificatio
         ("vinpocetine", "NOOTROPIC_VINPOCETINE"),
+        # Standardization markers (clinical sign-off 2026-09-19): resolve
+        # extract constituents canonically while preserving safety watchlist/caution.
+        ("withaferin_a", "WATCH_WITHAFERIN_A"),
+        ("miroestrol", "RISK_MIROESTROL"),
     }
     assert ("citrus_bioflavonoids", "RISK_BITTER_ORANGE") not in observed_parent_ids
     assert all(status in {"high_risk", "watchlist"} for _, _, status, _ in overlaps)
```

Detector semantics untouched: the banned/recalled hard-fail, the
`citrus_bioflavonoids` permissive-negative, and the status-class check are
unchanged. The exact-set assertion remains exact-set. The rationale comment
kept in-file: these identities legitimately exist in the IQM identity model
while simultaneously carrying dedicated risk/watchlist classifications
(same documented pattern as vinpocetine 2026-09-11 and DHEA).

## 3. Fast-tier regression status — recorded distinction

**"No known additional failures relative to base" is NOT "the repository is green."**

| Commit | Clean detached `test.sh fast` |
|---|---|
| base `124982a0` (targeted pair) | 1 failed / 1 passed |
| `77cbb38c` | 2 failed / **15,786 passed** / 191 skipped (5m50s) |
| `7ebf6c46` | 1 failed / **15,787 passed** / 191 skipped (5m35s) |

After `7ebf6c46`, the remediation introduces **no known new fast-tier failure
relative to its base**. One failure remains in the suite; see §4.

## 4. Known failure handed to the integrator (NOT this branch's to fix)

**Classification: `pre_existing_known_failure`** — verified to reproduce at
base `124982a0` in a clean detached worktree before any of this branch's
changes are considered.

- Test: `scripts/tests/test_scoring_source_of_truth_audit.py::test_static_audit_current_v4_modules_have_no_forbidden_fallbacks`
- Verbatim finding at base:
  `Finding(code='V4_IQD_INGREDIENTS_FALLBACK', message='scripts/scoring_v4/modules/generic_evidence.py:472 reads forbidden scoring fallback field', path='<worktree>/scripts/scoring_v4/modules/generic_evidence.py')`
- Base reproduction command + result:
  `pytest scripts/tests/test_scoring_source_of_truth_audit.py::test_static_audit_current_v4_modules_have_no_forbidden_fallbacks -q` → `1 failed, 1 passed`
- Owner: integrator/repo owner. Whether integration may proceed with this
  known failure is an **integrator/owner decision**. Per team direction, no
  allowlist or workaround was added to force the suite green on this branch.
  Note: `scoring_v4/modules/generic_evidence.py` also carries the peer
  session's uncommitted edits — repair belongs with that coordination (§8).

## 5. Approved clinical ledger updates (Phase-3 conclusions of record)

| Product(s) | Approved conclusion |
|---|---|
| **75188 / 243713** | `return_to_engineering` → **confirmed normalization defect.** Quantified Total Omega-3 parent is the dose owner; dose-less DHA/EPA remain subordinate constituents — no invented doses. |
| **328464** | **Confirmed specification/provenance modeling defect.** Ginkgolic-acid limit belongs to the standardized Ginkgo extract specification, never an independently dosed active. |
| **216948** | **Confirmed parent/standardization-constituent modeling defect.** Pueraria mirifica is the dose-bearing botanical; miroestrol/isoflavonoids are traceable standardization constituents. |
| **232718** | **Confirmed constituent/source-provenance modeling defect.** Withaferin A 12 mg preserved with ashwagandha provenance; the Withaferin A watchlist signal remains independently active — identity remediation did NOT and must not bypass Safety. |
| **13041** | **Confirmed source/incomplete-dose condition.** %DV without an explicit dose never fabricates a scoreable dose; `daily_value_no_amount` is the approved non-scoreable state. |
| **Bulk 1340 family** | **Removed from the missing-dose bucket.** Correct classification: *mixed* — genuine max-labeled-exposure Safety findings + stale-source duplication + form/completeness defects. Evaluate **per SKU** on its archived label. |
| **E2 ×6** (223563, 223572, 231334, 231335, 263865, 328644) | Reviewed source correction only; **no automatic plausibility conversion**. |

## 6. Bulk 1340 safety-receipt requirements (per SKU)

Every safety receipt must record: DSLD/product ID · label/source version or
retrieval date · amount per serving · labeled maximum servings/day · resulting
maximum daily exposure · UL/reference applied · rule ID.

- Safety uses the **applicable archived product's** label values (220 mg Mg in
  the audited records). Current manufacturer pages (190 mg Mg, 1–2 servings/day)
  may validate interpretation/directions but must never silently replace frozen
  historical amounts.
- 243808: after the folate triplication (stale/duplicated source rows) is
  corrected, it must **not** generate a clinical UL conclusion.
- 228823: the Vitamin-A completeness/form defect stays a separate finding from
  the independently valid niacin/magnesium evaluation.

## 7. Durable architecture contracts established by these commits

1. **Dose ownership** — a quantified parent must not disappear because DSLD
   provides subordinate molecular constituents/forms.
2. **No invented dose** — zero-dose children, %DV-only rows, standardization
   markers, and composition descriptions never acquire inferred quantities
   except through an explicitly reviewed conversion/correction mechanism.
3. **Specification ≠ ingredient** — contaminant/spec limits may be
   display/metadata provenance when structural context establishes the role;
   ppm/ppb units alone are insufficient.
4. **Standardization marker ≠ unrelated active** — keep genuinely declared
   quantitative constituents while preserving source relationships; no orphan
   identity conflicts.
5. **Identity remediation cannot bypass Safety** — correcting identity or
   provenance never automatically clears a safety rule.

## 8. Mandatory integration gate: frozen-corpus full replay

The 10-record live-DSLD shadow A/B (`shadow_replay_ab.py`: 10 replayed, 5
changed, 0 crashes, changes matched intended defect classes) is supporting
evidence, **not** a substitute. After cherry-picking into an environment with
the frozen corpus, run the full replay and report:

1. total products replayed; 2. crashes; 3. cleaned-representation changes;
4. numerical score changes; 5. quarantine exits; 6. new quarantine entries;
7. every Safety-gate change; 8. every changed product outside the expected
defect families (75188/243713 omega family, 216948/232718 markers, 328464
spec limits, 13041 %DV family, ppm/ppb-nested rows); 9. largest score deltas.

Plus a Phase-3-specific before/after list bucketing each product as:
fixed automatically / still quarantined correctly / requires clinical-policy
review / requires engineering / requires source refresh.

**Stop-and-investigate rule:** if the replay shows unexpected cross-family
effects, do not publish.

## 9. Release criterion (the standard the replay is judged against)

> source-faithful representations, deterministic scoring behavior, no
> fabricated doses, no lost safety signals, and only justified quarantine
> changes.

"Not more products leaving quarantine" is explicitly NOT the goal.

## 10. Open Phase-3 items kept separate from the remediated defects

- E2 unit/source cases ×6 (receipt path, §5)
- `needs_info` ×4: 12300, 75291, 254396, 254413 (label retrieval)
- EDTA safety-policy products ×16 → `safety_policy_review_required`
- Vitamin-A form/completeness gap (228823's completeness row is an instance)
- Bulk 1340 per-SKU source defects remaining after refresh/reconciliation
- Peer-session coordination: per-enzyme IQM entries (currently 12 schema-test
  failures), `scoring_v4/modules` edits, the §4 static-audit failure, and the
  27 uncommitted files in the shared worktree — all owned by the peer/
  integrator track, none of it cherry-picked with this set.
