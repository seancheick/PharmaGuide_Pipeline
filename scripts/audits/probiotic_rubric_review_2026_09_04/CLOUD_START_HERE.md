# Start here — Claude Code cloud continuation

## Scope and checkpoint status

This branch is an **unfinished engineering checkpoint**, not a release candidate.
The operator authorized committing/pushing the local continuation so cloud work
can proceed while the laptop is off. Do not start from main or discard this work.

- Repository: `seancheick/PharmaGuide_Pipeline` (PUBLIC).
- Source branch: `codex/probiotic-evidence-coverage`.
- Previous committed baseline: `cea87d01512cc6e88acc13aa8212e26815bbd6d7`.
- Select the latest pushed source-branch tip, verify its SHA against the operator's
  handoff, and create/use your cloud continuation branch descended from that tip.
- Read [the full handoff](CLAUDE_HANDOFF_2026_09_04.md), then
  [EXECUTION.md](EXECUTION.md). This file supersedes only the full handoff's
  historical “uncommitted/local-only” transport status, not its technical findings.
- Read actual source/tests before accepting any previous model's claims.

The full handoff records absolute Mac paths for audit provenance. In cloud, use
your checkout root for `scripts/...` paths. Do not create fake Mac directories,
copy reports into an “accepted” filename, or bypass missing-input checks.

## What the pushed branch provides

Code, reference-data changes, regression tests, individual source research and
the existing benchmark/acceptance roadmap. The last task remains RED.

Fresh checkpoint verification on 2026-09-04:

```bash
scripts/test.sh fast \
  scripts/tests/test_evidence_primary_source_ownership.py \
  scripts/tests/test_botanical_evidence_reachability.py \
  scripts/tests/test_botanical_identity_projection.py \
  scripts/tests/test_clinical_source_owner_projection.py \
  scripts/tests/test_green_tea_evidence_identity.py \
  scripts/tests/test_native_study_contexts.py \
  scripts/tests/test_synergy_dose_native_units.py
```

**1 failed, 175 passed in 5.60 seconds.** The sole failure is
`test_ps_complex_total_does_not_dilute_its_only_evidenced_active`
(actual floor 0 versus control 18). Preserve and fix this regression. The broad
fast suite has NOT been rerun green on the complete continuation. No release or
full suite was run for this handoff.

Global weights remain unchanged; `quality_score.json` SHA-256:
`18b7ff59dc1c4baa4e89562492ffa9338491bb618da42e4044900f805beae9e1`.

## Small real-label fixtures available without the laptop

[cloud_source_lineage_fixtures.json](cloud_source_lineage_fixtures.json) contains
exact selected fields from three public DSLD cleaned labels:

- 213475: SerinAid complex with its nested phosphatidylserine child.
- 218600: reverse hierarchy, phosphatidylserine and its supplying complex.
- 218838: sibling complex / phosphatidylserine / phosphatidylcholine rows;
  **no linkage may be invented**.

Each record includes its source batch SHA-256 and a projection SHA-256 computed
with Python JSON serialization (`sort_keys=True, ensure_ascii=False,
separators=(",", ":")`, UTF-8). Field values and numeric representation are
preserved; no source-owner link was added during transfer. Brand contacts,
photos and unrelated fields were omitted. These are source-lineage diagnostics,
**not complete-product snapshots, scored goldens, or full-corpus inputs**.

Use them to inspect actual source shape and extend source-ownership tests.
Keep unrelated aggregate controls and standalone-blend behavior. Do not drop all
product-level evidence, alter clinical thresholds or tune to desired scores.

## Runtime and cloud preflight

1. Confirm repository, source commit ancestry, handoff and regression test exist.
2. Install Python **3.13.3** and the repository's `requirements-dev.txt`.
   Use a repository `.venv`; `scripts/python_env.sh` already discovers it.
   Do not replace the canonical test runner or relax its interpreter guard.
3. Use `scripts/test.sh fast` for tests, never raw pytest. Run focused suites
   during iteration; use the full fast backstop at the engineering acceptance step.
4. Configure research network access to the primary PubMed/PMC, FDA/GSRS, NIH
   and other exact sources needed by the handoff. Local browser/MCP sessions and
   local environment secrets are NOT inherited.
5. If a required API needs credentials, request narrowly scoped cloud credentials
   through secure environment configuration. Never put secrets or .env in Git/chat.
   This engineering task does not need production Supabase write access.
6. Reproduce the known RED before fixing it. Validate source-fixture hashes before
   using them. Report missing prerequisites explicitly rather than claiming a gate
   passed without its data.

## What is NOT in Git and cannot be claimed complete remotely yet

The existing whole-corpus audit references **174 local input files totaling
8,956,945,899 bytes**, plus large baseline/candidate reports. They are ignored by
Git. Private Product_Submissions data must not be uploaded into this public repo.
The operator has not supplied these inputs to a private cloud artifact location.

Therefore: cloud can continue code, unit/regression tests, bounded public-label
probes and source research. **Full-corpus acceptance is still pending until the
exact manifest-owned inputs and baseline chain are securely provisioned, or the
operator returns and runs the read-only comparisons locally.** Never substitute
freshly downloaded labels for the frozen baseline without rebuilding matched
controls and disclosing the input change.

Do not claim completion of the 15,415-product comparison from these three fixtures.
Do not upload the local corpus, .env, user photos, signing keys or submission
metadata to a public branch/release asset. Phone/Xcode verification also requires
an appropriate available build host/device, not this pipeline cloud session.

## Work order and stopping boundary

Follow sections 5–10 of the full handoff:
source-total ownership fix → bounded evidence/preparation reviews → affected-family
inventory → same-input corpus comparison → fast tests → independent review →
small reviewed commits → precise return report.

If corpus access blocks acceptance, continue independent in-scope engineering
and research, preserve the blocker in the ledger, and stop at the real boundary.
Human clinical sign-off and independent reviewer ratings cannot be fabricated.
No automatic main merge, operational pipeline/release, Supabase upload, Flutter
import or global-weight calibration is authorized by this handoff.

Return branch/commit range, RED/GREEN outputs, research, fixture/corpus hashes,
categorized deltas and unresolved prerequisites for Codex's independent audit.

Official cloud setup:
- https://code.claude.com/docs/en/web-quickstart
- https://code.claude.com/docs/en/claude-code-on-the-web
