---
name: pg-scoring-change
description: Procedure for any PharmaGuide change that can move a v4 quality score, pillar, route or verdict. That covers scorer modules, scoring_input_contract, quality_score.json, IQM bio_score or forms, and enricher fields the scorer reads. Use before editing scoring code or config, when calibrating, when a product's score looks wrong, or when the user says "change the score", "recalibrate", "fix the scoring", or "why did this product score X".
---

# Changing a score

Scores ship to consumers. Green unit tests have hidden over-promotion and silent regressions
before, and a full pipeline rerun costs about 45 minutes. This procedure measures the real effect
cheaply and keeps one owner per decision. The invariants live in `.claude/rules/scoring.md`; this
skill covers the steps.

## Steps

1. **Owner Check.** Find the concept in `scripts/contracts/source_of_truth_matrix.json`: its owner
   (`path::symbol`) and its `forbidden_recomputation`. Extend that owner. If the change needs a new
   semantic owner, a new field or a new policy, stop and ask Sean. Record the Owner Check block
   (AGENTS.md) in the plan.
2. **Baseline one real product** that exercises the path, at the scored layer. Print the driver,
   not just the total:

   ```bash
   source scripts/python_env.sh && $PG_PYTHON - <<'EOF'
   import glob, json, sys
   sys.path.insert(0, "scripts")
   from scoring_v4.scored_artifact import build_scored_artifact
   BRAND, PID = "Airborne", "178352"   # pick one that exercises the change
   for f in glob.glob(f"scripts/products/output_{BRAND}_enriched/enriched/*.json"):
       for p in json.load(open(f)):
           if str(p.get("id")) == PID:
               a = build_scored_artifact(p)
               print(a.get("quality_score_v4_100"), a.get("quality_score_status"))
               print(json.dumps(a.get("quality_pillars_v4"), indent=1)[:4000])
   EOF
   ```

3. **Write a failing regression test** through the production seam
   (`scoring_v4/scored_artifact.py::build_scored_artifact`), in `scripts/tests/test_<topic>.py`.
4. **Make the edit.** Magnitudes go only in `scripts/scoring_v4/config/quality_score.json`. When
   retiring a component, move its explanation, copy and pinned tests with it.
5. **Re-probe** the same product, then a few brands that exercise the path. For enricher-side
   changes, measure through `SupplementEnricherV3.enrich_product`; calling one `_collect_*` method
   directly invents regressions.
6. **Measure before claiming.** Score stored inputs from a clean HEAD worktree (never with
   uncommitted scoring edits in the tree) into an old and a new directory. Compare with
   `python3 scripts/audit_source_of_truth_contract.py shadow-diff --old-dir <old> --new-dir <new>`
   and a score diff. Explain the top movers. Any unexplained identity or status change: revert.
   Run one corpus job at a time.
7. **Fresh-context review.** Give a reviewer only the requirement, the matrix owner, the diff and
   the measured deltas. It must answer: does the diff add a new name? Does a near-name already exist
   (`rg` the stem in `scripts/` and `/Users/seancheick/PharmaGuide ai/lib`)?
8. **Tests.** Run `scripts/test.sh fast -k <topic>` while iterating and the full `scripts/test.sh fast`
   once at the end. If shipped scores move, show Sean the measured deltas before any release.
