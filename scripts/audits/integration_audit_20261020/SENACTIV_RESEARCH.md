# Senactiv identity and advisory research — 2026-10-20

Initial read-only research requested by Sean before deciding the held identity-policy question. The approved implementation and validation follow-up is recorded below; no pipeline run was started by this worker.

## Approved implementation and verification update

Final CI copy-length follow-up: the first candidate correctly failed two strict production-copy tests because three bodies exceeded 200 characters and notes exceeded 120. Reproduced both named failures; no limit was weakened. Shortened only the Senactiv entry's bodies/notes, preserving full mechanisms and action fields. Shared body explicitly says other notoginseng preparations affected platelets, applicability to Senactiv is unknown, and bleeding risk is not established. Final body lengths: bleeding disorder 184, surgery 182, antiplatelet 194; notes 105. Meaningful assertions now also pin those uncertainty statements and the existing limits. The complete notoginseng + safety_copy_production + validate_safety_copy files passed: **79 tests in 4.60 s**. Exact HEAD-relative data batch check: one Senactiv entry changed, zero problems.

Superseding frozen raw capture: `senactiv_replay/candidate_copy_final.jsonl` and `diff_copy_final.json`, versus the same immutable 5d15 baseline. Receipt source_unchanged=true, all 8 labels complete; only 295773/309960/329215 differ, with the same expected identity/advisory effects below. All eight numerical scores, six pillars, quality status and product safety status remain unchanged. This capture supersedes candidate_final only for concise warning copy. Integrator owns the finished-candidate CI retry; no commit made by this worker.

Sean subsequently approved the bounded correction. Implemented at `identity_integrity.resolve_identity`: the exact curated Senactiv/Seneactiv name, supplied NHA_SENACTIV identity, unscored blend-header role, both printed constituent forms, and no contradictory nested member are required to override BLEND_GENERAL. Existing label-source rows supply nested member names through an internal optional argument in the existing enricher caller, because normalized header nestedIngredients can be empty after children flatten. No persisted/public field, registry, status or second identity matcher was added. Another brand receives no exception.

The existing Senactiv rule alone now explicitly attributes evidence to other notoginseng preparations, states Senactiv applicability is unknown, and retains qualified clinician/surgical-team communication without established bleeding, stop-use or medication-dose claims. ADR-0005 records the approved exception. The frozen raw329215 fixture was added;295773/309960 fixtures remain unchanged.

Fail-first regressions reproduced both lost identities and missing applicability wording. Independent review found nested contradictory member evidence initially missing; its new end-to-end regression failed, then passed after source-path evidence plumbing. Anonymous/near-name controls do not gain NHA_SENACTIV or the advisory; incomplete/mismatched/extra forms and extra nested Caffeine retain BLEND_GENERAL. Agreeing nested constituent rows remain compatible. All positive headers remain unscored and absent from ingredients_scorable.

Validation: final named owner/consumer slice **168 passed in29.70s** (notoginseng, identity_integrity, nonscorable_identity_kept, interaction_blend_header_subject); notoginseng file independently rerun by integrator **20 passed**. `data_batch.py check ... --since HEAD --expect interaction_rules/RULE_OTHER_SENACTIV_ANTIPLATELET`: one changed entry, zero problems. Dedicated `verify_interaction_rules_citations.py --strict --changed-since HEAD`: PASS; all4PMIDs fetched,12 subject-extrapolation suspects covered by existing manual reviews, with applicability now explicitly qualified. The generic all-citations verifier has no configuration for interaction_rules and was not a successful check; the dedicated verifier plus live research receipts cover that file. Independent reviewer approved the corrected guard. No commit by this worker.

Bounded replay: frozen IDs **15698,1650,212273,243676,295773,309960,329215,42235**, baseline HEAD `5d15a3f2383af92b59995d96360f1ef961efed1c` source captured before edits versus final candidate; both receipts source_unchanged=true and8/8completed. Only295773,309960,329215 changed.295773 has warning-copy changes only.309960/329215 gain NHA_SENACTIV instead of BLEND_GENERAL and the already-authored Senactiv advisory; no rule is removed. All8 retain identical six pillars, numerical totals, quality status and product_safety_status. Affected totals stay82.9,80.9,80.0. The two changed scored-record hashes reflect evidence-readiness identity/reason/list-order receipts (structural row->nonmaterial active), not changed score/eligibility/status. Five raw controls are byte-identical across all captured stages. Files: `senactiv_replay/base.jsonl`, `candidate_final.jsonl`, `diff_final.json` and their metadata/full records. The earlier candidate.jsonl is superseded by candidate_final after nested-member guard correction.

Integrator committed the completed source as `e117f7768` after the captures. The final landed data check against immutable baseline `5d15a3f2383af92b59995d96360f1ef961efed1c` passed: one expected entry, zero problems. A HEAD-relative check after that commit correctly found no remaining uncommitted entry changes.

Limits: no broad suite, full corpus, release or publication. A separately authorized external pipeline was running in the primary checkout during final focused validation; these receipts use the isolated source tree and immutable frozen raw labels and make no claim about that pipeline's mutable outputs. Integrator owns final CI, integration and any required regeneration.

## Recommendation

**Senactiv is a known branded botanical complex; its identity should not depend on whether DSLD writes “Blend” or “Proprietary Blend”. Its bleeding/antiplatelet advisory is a qualified constituent-based precaution, not a demonstrated Senactiv interaction.** These are separate decisions. Resolve the existing ADR exception explicitly before implementation; do not infer a second canonical from raw text inside the safety scanner.

Recommended bounded identity rule: when the label exactly names a curated branded complex and its printed forms are compatible with that complex, retain the existing canonical owner, here `other_ingredients/NHA_SENACTIV`, while keeping the existing `blend_header_total` role and its scoring exclusion. Do not turn 50 mg of Senactiv into 50 mg of notoginseng or Rg1. Anonymous “Proprietary Blend” rows retain BLEND_GENERAL. Contradictory forms require an unresolved/conflict decision, not brand-name immunity.

## Observed identity evidence

NuLiv, the ingredient supplier, identifies Senactiv as a blend of Panax notoginseng and Rosa roxburghii extracts and recommends 50 mg. Its formulation page describes highly purified, fractionated extracts. This supports the branded-complex identity; it does not equate the mixture chemically to Panax ginseng, whole notoginseng root, or isolated Rg1. [Supplier ingredient page](https://nulivscience.com/ingredients/senactiv), [supplier formulation page](https://discover.nulivscience.com/senactiv-energy-regeneration), [supplier product sheet](https://discover.nulivscience.com/hubfs/Digital%20Resource%20Center%20-%20Nuliv%20Nexus/Research/Senactiv%C2%AE%20PFS%20e241023.pdf).

A NuLiv composition statement revised March 4, 2025, item NLS04r, lists 47.5% Panax notoginseng root extract, 47.5% Rosa roxburghii whole-fruit extract and 5% tapioca-derived maltodextrin. It describes hot-water/ethanol extraction. This is a supplier-authored document hosted by a third party, not independently authenticated batch documentation; do not assume its proportions apply retrospectively to all DSLD labels or use them to invent per-product constituent doses. [NuLiv statement](https://ss3-production-public.s3.amazonaws.com/seller-document/1/4DE2E78B4281992B7AA9DA7A4F3B021B.pdf).

Locally inspected raw label rows:

| Product | Raw row | Name | Total | Printed forms | DSLD group |
|---|---|---|---|---|---|
| 295773 | ingredientRows[16] | Seneactiv | 50 mg | Panax notoginseng; Rosa roxburghii | Blend |
| 309960 | ingredientRows[8] | Senactiv | 50 mg | Panax notoginseng; Rosa roxburghii | Proprietary Blend |
| 329215 | ingredientRows[10] | Senactiv | 50 mg | Panax notoginseng; Rosa roxburghii | Proprietary Blend |

295773/309960 are frozen test fixtures; 329215 was read from `/Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands/Transparent_Labs/329215.json`. In the prior live enrichment probe, 309960 starts with cleaner NHA_SENACTIV, then `resolve_identity` repairs it to BLEND_GENERAL, dropping the brand-authored rule. The scientific identity evidence is equivalent across these labels; their difference is DSLD classification metadata.

Current owner conflict: ADR-0005 decision 2 explicitly lets the general blend group override even a brand, and `identity_integrity.py` enforces that exception. Conversely, NHA_SENACTIV's existing curated notes call it a branded complex, not a product-level proprietary blend container. Existing retained-header interaction code uses the already-decided canonical; it does not independently infer a branded subject. Correct this once at `resolve_identity` after policy clarification, preserving row role. No new field, registry or second matcher is needed.

## Live clinical-source assessment

**PMID 33370633, primary randomized study:** 42 people with stable coronary heart disease and chronic gastritis received aspirin alone or Panax notoginseng saponins plus aspirin for two months. Added saponins increased platelet-inhibition measures. The intervention was PNS, not identified as Senactiv or the two-plant branded mixture. The abstract reports platelet and gastric outcomes, not a clinical bleeding-risk estimate. The study does not establish that Senactiv 50 mg causes bleeding or reproduces the PNS effect. [PubMed](https://pubmed.ncbi.nlm.nih.gov/33370633/). Content also retrieved live from the Europe PMC core API after direct PubMed open was intermittently incomplete.

**PMID 31471773, review:** describes interactions of clopidogrel with TCM preparations, including increased antiplatelet activity with notoginseng. It supplies constituent/preparation context, not a Senactiv coadministration trial. [PubMed](https://pubmed.ncbi.nlm.nih.gov/31471773/).

**PMID 36754189, review:** surveys in-vivo/in-vitro notoginseng drug interactions and calls for investigating their clinical importance. It is not product-specific confirmation of Senactiv harm. [PubMed](https://pubmed.ncbi.nlm.nih.gov/36754189/).

**PMID 39364700, case:** esophageal submucosal hematoma followed five notoginseng capsules in a 57-year-old woman. The abstract does not identify Senactiv. A temporal case report supports caution, not a quantified causal risk for a different mixture. Content verified live through Europe PMC core API. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/39364700/), [journal DOI](https://doi.org/10.17235/reed.2024.10775/2024).

**PMID 34307625, case:** a 60-year-old man developed a large esophageal hematoma after a homemade mixture of hirudin and notoginseng powder. Hirudin is a major attribution confounder; this cannot demonstrate notoginseng-alone or Senactiv bleeding harm. [PubMed](https://pubmed.ncbi.nlm.nih.gov/34307625/).

**Rg1 plausibility is not whole-product clinical proof.** A primary in-vitro human-platelet study found Rg1 inhibited aggregation at experimental concentrations. It does not establish comparable concentrations or bleeding outcomes after Senactiv 50 mg. Different notoginseng saponins can also have opposing effects: Ft1 promoted aggregation in a preclinical study. The composition/preparation boundary therefore matters. [Rg1, PMID 2907575](https://pubmed.ncbi.nlm.nih.gov/2907575/), [Ft1, PMID 24117220](https://pubmed.ncbi.nlm.nih.gov/24117220/).

The supplier's research library associates Senactiv with Rg1 exercise research. A cited primary 2015 paper used capsules providing 5 mg Rg1, studied exercise/muscle outcomes, and excluded recent medication use. It did not test aspirin/clopidogrel interaction or establish bleeding safety in those users. Supplier association with an ingredient's research must not be treated as proof of a whole-formula interaction outcome. [Supplier research library](https://nulivscience.com/the-research-library), [PLOS primary paper, PMID 25617625](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0116387).

Targeted searches and the reviewed supplier library did not locate a Senactiv-branded clinical platelet, bleeding or perioperative trial. This is a bounded search finding, not proof that none exists. Current technical specifications and a product-specific interaction study could narrow uncertainty; no contact/request was sent.

## Existing warning: reasonable action intensity, incomplete applicability wording

The current `RULE_OTHER_SENACTIV_ANTIPLATELET` is `monitor`, `limited`, profile-gated to antiplatelet users, bleeding disorders or scheduled surgery. It says bleeding risk is not established and asks users to inform clinicians/surgeons. It contains no stop-use instruction, imposed washout duration, INR recommendation or medication-dose change. Those are appropriately cautious actions for an explicitly labeled extrapolation.

However, “Senactiv (notoginseng) may affect platelet function” collapses the mixture into a constituent. The mechanism describes other notoginseng preparations without explicitly telling readers that Senactiv itself was not tested. “Bleeding risk not established” alone does not disclose that applicability gap. Surgery advice is a precautionary communication recommendation; no located study demonstrated perioperative harm from Senactiv.

Researched wording proposal (the implemented rule now uses the same explicit applicability distinction):

> Senactiv contains notoginseng extract. Other notoginseng preparations have affected platelet activity, but whether this applies to Senactiv is unknown. If you take aspirin or another antiplatelet medicine, tell your clinician you use it.

For bleeding disorder/surgery profiles, retain the same explicit uncertainty and change only the contextual action to “discuss it with your clinician” / “tell your surgical team before your procedure”. Do not claim established clinical bleeding, tell users to stop prescribed medicines, or invent a concentration/dose threshold.

## Approved decision and boundary

Sean approved the narrow distinction between this specifically identified curated complex and an anonymous blend, retaining the unscored blend role and a transparently extrapolated, limited, profile-targeted advisory. The implementation and measurements above exercise all three raw labels and anonymous/contradictory controls. Identity evidence is strong; whole-product clinical interaction evidence is not. This approval does not authorize a release or expand the exception to other complexes.
