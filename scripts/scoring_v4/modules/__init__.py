"""v4 per-class scoring modules.

Per `docs/plans/SCORING_V4_PROPOSAL.md` §6, each product class has its
own rubric, weighted across the shared 5-dimension spine:

  - generic (P1.3)          — single-nutrient, simple stacks, omega, botanicals
  - probiotic (P2)          — supplement_type=probiotic
  - multi_or_prenatal (P3)  — multivitamin, prenatal multi, men's/women's complete

Modules read enriched product fields directly + the safety/completeness
gate results passed by the shadow entry point. They MUST NOT import the
v3 scorer (§13 architecture lock).

Each module emits a normalized breakdown shape compatible with
`shadow_score_v4_breakdown["module"]`. See `generic.GenericModuleResult`
for the canonical contract.
"""

from __future__ import annotations

__all__ = ["generic"]
