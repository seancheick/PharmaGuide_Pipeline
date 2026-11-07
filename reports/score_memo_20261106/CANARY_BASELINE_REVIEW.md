# Canary baseline reconciliation — November 6

Owner: scripts/release_artifact_paths.py::canary_baseline_dir. Existing assertion/release readers share this path. No new scoring, identity or clinical owner is introduced.

Only1036 is replaced with independently replayed qualified main output. The other eight baseline files retain their exact November4 bytes. All nine original raw hashes and all old baseline hashes verify against the preserved November4 manifest. Older directories are unchanged.

Raw1036 prints Rutin powder, no forms. Its inferred standardName is Citrus Bioflavonoids; canonical identity remains citrus_bioflavonoids. Current accepted source-proof handling retains an unknown/unspecified preparation, bio8, and removes the unsupported inferred Citrus Bioflavonoids Complex/bio9 and its preparation prose. No grade or policy is changed here.

Full replay at November4 source539ee64f7 reproduces the prior guarded fields. Full replay at pre-efficiency992f3d4ca produces a whole blob exactly equal to current runtime2247ee982. Thus the drift predates the efficiency batch. The method-only e3 ablation did not establish causality and is not used as such proof.

The original two1036 assertions fail against the old baseline. Independent review confirms the proposed baseline passes all54 assertions against both current-main and scientific canaries. Every assertion and allowed-field set is retained. The whole1036 replacement also contains already-integrated unguarded source/evidence/nutrition/provenance differences; these are enumerated privately in ALL_1036_BASELINE_PATHS.json, not described as only eight whole-blob changes. The guard itself concerns eight ingredient fields plus their display mirrors. Other eight current blobs may have unguarded drift; their baselines are intentionally unchanged.

This is development fixture maintenance, not clinical approval or release qualification. Full raw/Score/blob/core scientific comparisons and final current-artifact/app validation remain separate. Private proof: pipeline-stabilization-20261106/canary-reconciliation and evidence-completion-20261106/CURRENT_MAIN_CANARY9_GUARDED_PARITY.json.
