"""v4 per-class scoring modules.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6, each product class has its
own rubric, weighted across the shared 5-dimension spine:

  - generic (P1.3)          — single-nutrient, simple stacks, botanicals
  - probiotic (P2)          — supplement_type=probiotic
  - omega (P1.6)            — fish-oil / krill / algae / cod-liver, EPA+DHA-bearing
  - fiber_digestive (P1.8)  — fiber, prebiotic fiber, digestive enzymes
  - multi_or_prenatal (P3)  — multivitamin, prenatal multi, men's/women's complete

Modules read enriched product fields directly + the safety/completeness
gate results passed by the v4 entry point. They MUST NOT import the
legacy scorer (§13 architecture lock).

Each module emits a normalized breakdown shape compatible with
`v4_breakdown["module"]`. See `generic.GenericModuleResult`,
`probiotic.ProbioticModuleResult`, and `omega.OmegaModuleResult` for the
canonical contract.
"""

from __future__ import annotations

__all__ = ["generic", "probiotic", "omega", "multi_prenatal", "fiber_digestive"]
