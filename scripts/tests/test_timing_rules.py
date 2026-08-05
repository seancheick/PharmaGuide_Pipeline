#!/usr/bin/env python3
"""Contract and data-quality tests for timing_rules.json (schema 6.x).

Schema 6.0.0 removed the scheduler: there is no `rule_type`, no `daily_slots`,
and no `daily_plan_eligible`. A rule now carries a structured `timing_relation`
plus five INDEPENDENT fields — category, actionability, evidence_level,
source_authority, review_status — so that "well evidenced" can never imply
"urgent", and a mechanism paper can never present like a drug label.

`review_status` is the publication gate. Only `verified` rules render, and the
migration deliberately left every rule at `needs_revision` until Section 2
verifies each one against its source with positive and negative catalog
canaries.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TIMING_FILE = DATA_DIR / "timing_rules.json"
REJECTION_LEDGER = DATA_DIR / "timing_rules_rejected.json"

VALID_RELATION_TYPES = {
    "separate_from",
    "separate_from_medications",
    "with_food",
    "empty_stomach",
    "before_event",
    "after_event",
    "consistent_relative_to_prescription",
}
BINARY_RELATION_TYPES = {"separate_from"}
VALID_EVENTS = {"intended_sleep", "meal"}
VALID_CATEGORIES = {"important_separation", "how_to_take", "optional"}
VALID_APPLIES_TO = {"standalone", "any"}
VALID_ACTIONABILITY = {"recommended", "optional", "informational"}
VALID_REVIEW_STATUS = {"verified", "needs_revision", "rejected"}
VALID_SOURCE_AUTHORITY = {
    "fda_label",
    "product_label",
    "guideline",
    "systematic_review",
    "clinical_study",
    "mechanism",
    "reference",
}
VALID_EVIDENCE_LEVELS = {"established", "probable", "possible"}
VALID_SOURCE_TYPES = {"pubmed", "reference", "nih_ods", "fda", "nccih"}

# Fields the scheduler owned. Their return would mean the solver came back.
FORBIDDEN_LEGACY_FIELDS = {"rule_type", "daily_slots", "daily_plan_eligible"}


@pytest.fixture(scope="module")
def timing_data():
    with open(TIMING_FILE) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def rules(timing_data):
    return timing_data["timing_rules"]


# ── Metadata contract ──────────────────────────────────────────────

class TestTimingMetadata:
    def test_has_metadata(self, timing_data):
        assert "_metadata" in timing_data

    def test_metadata_required_fields(self, timing_data):
        meta = timing_data["_metadata"]
        for field in ("description", "purpose", "schema_version", "last_updated", "total_entries"):
            assert field in meta, f"Missing metadata field: {field}"

    def test_schema_version_is_6x(self, timing_data):
        ver = timing_data["_metadata"]["schema_version"]
        assert ver.startswith("6."), f"Expected 6.x schema, got {ver}"

    def test_total_entries_matches(self, timing_data, rules):
        declared = timing_data["_metadata"]["total_entries"]
        actual = len(rules)
        assert declared == actual, f"Metadata says {declared} entries but found {actual}"

    def test_purpose_is_timing(self, timing_data):
        assert timing_data["_metadata"]["purpose"] == "timing_optimization"

    def test_metadata_reports_the_real_state(self, timing_data, rules):
        meta = timing_data["_metadata"]
        assert meta["runtime_policy"] == "verified_only"
        counts = meta["status_counts"]
        actual_verified = sum(1 for r in rules if r["review_status"] == "verified")
        actual_pending = sum(
            1 for r in rules if r["review_status"] == "needs_revision"
        )
        assert counts["verified"] == actual_verified
        assert counts["needs_revision"] == actual_pending
        ledger = json.loads(REJECTION_LEDGER.read_text())
        assert counts["rejected"] == len(ledger["rejected"])


# ── Schema contract per rule ───────────────────────────────────────

class TestTimingRuleSchema:
    def test_all_ids_unique(self, rules):
        ids = [r["id"] for r in rules]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_ids_prefixed(self, rules):
        for r in rules:
            assert r["id"].startswith("timing_"), f"ID must start with 'timing_': {r['id']}"

    def test_required_fields_present(self, rules):
        required = {
            "id",
            "ingredient1",
            "timing_relation",
            "category",
            "applies_to",
            "actionability",
            "source_authority",
            "review_status",
            "advice",
            "mechanism",
            "score_impact",
            "evidence_level",
            "sources",
        }
        for r in rules:
            missing = required - set(r.keys())
            assert not missing, f"Rule {r['id']} missing fields: {missing}"

    def test_no_scheduler_fields_survive(self, rules):
        for r in rules:
            present = FORBIDDEN_LEGACY_FIELDS & set(r.keys())
            assert not present, f"Rule {r['id']} still carries scheduler fields: {present}"

    def test_relation_type_valid(self, rules):
        for r in rules:
            relation = r["timing_relation"]
            assert relation["type"] in VALID_RELATION_TYPES, \
                f"Rule {r['id']} has invalid relation: {relation['type']}"

    def test_separation_relations_have_positive_hours(self, rules):
        for r in rules:
            relation = r["timing_relation"]
            if relation["type"] in {"separate_from", "separate_from_medications"}:
                hours = relation.get("minimum_hours")
                assert isinstance(hours, int) and hours > 0, \
                    f"Rule {r['id']} needs a positive minimum_hours"

    def test_event_relations_are_user_anchored(self, rules):
        """An event must be something the user can answer, never a clock time."""
        for r in rules:
            relation = r["timing_relation"]
            if relation["type"] not in {"before_event", "after_event"}:
                assert "event" not in relation, f"{r['id']} authors a stray event"
                continue
            assert relation.get("event") in VALID_EVENTS, r["id"]
            minimum = relation.get("minimum_minutes")
            assert isinstance(minimum, int) and minimum > 0, r["id"]
            maximum = relation.get("maximum_minutes")
            if maximum is not None:
                assert maximum >= minimum, r["id"]

    def test_only_binary_relations_carry_a_second_identity(self, rules):
        for r in rules:
            is_binary = r["timing_relation"]["type"] in BINARY_RELATION_TYPES
            has_second = bool(r.get("ingredient2_tags") or r.get("ingredient2_rxcuis"))
            assert has_second == is_binary, (
                f"{r['id']}: a second identity is required for a binary relation "
                f"and forbidden otherwise"
            )

    def test_every_rule_has_a_first_identity(self, rules):
        for r in rules:
            assert r.get("ingredient1_tags") or r.get("ingredient1_rxcuis"), r["id"]

    def test_identity_tags_are_canonical_shape(self, rules):
        """Tags must look like catalog tags, not free-text ingredient names."""
        for r in rules:
            for key in ("ingredient1_tags", "ingredient2_tags"):
                for tag in r.get(key, []):
                    assert tag == tag.lower(), f"{r['id']}: {tag} is not lowercase"
                    assert " " not in tag, f"{r['id']}: {tag} contains a space"
                    assert "-" not in tag, f"{r['id']}: {tag} contains a hyphen"

    def test_taxonomy_fields_valid(self, rules):
        for r in rules:
            assert r["category"] in VALID_CATEGORIES, r["id"]
            assert r["applies_to"] in VALID_APPLIES_TO, r["id"]
            assert r["actionability"] in VALID_ACTIONABILITY, r["id"]
            assert r["review_status"] in VALID_REVIEW_STATUS, r["id"]
            assert r["source_authority"] in VALID_SOURCE_AUTHORITY, r["id"]

    def test_evidence_level_valid(self, rules):
        for r in rules:
            assert r["evidence_level"] in VALID_EVIDENCE_LEVELS, r["id"]

    def test_score_impact_is_int(self, rules):
        for r in rules:
            assert isinstance(r["score_impact"], int), f"Rule {r['id']} score_impact must be int"

    def test_ingredients_lowercase(self, rules):
        for r in rules:
            assert r["ingredient1"] == r["ingredient1"].lower(), r["id"]
            if "ingredient2" in r:
                assert r["ingredient2"] == r["ingredient2"].lower(), r["id"]

    def test_medication_rules_author_exact_live_rxcuis(self, rules):
        levothyroxine_rules = [
            rule for rule in rules
            if rule["ingredient1"] == "levothyroxine"
            or rule.get("ingredient2") == "levothyroxine"
        ]

        assert levothyroxine_rules
        for rule in levothyroxine_rules:
            if rule["ingredient1"] == "levothyroxine":
                assert rule.get("ingredient1_rxcuis") == ["10582"], rule["id"]
                assert "ingredient2_rxcuis" not in rule
            else:
                assert rule.get("ingredient2_rxcuis") == ["10582"], rule["id"]
                assert "ingredient1_rxcuis" not in rule

    def test_optional_category_requires_clinician_approval(self, rules):
        """Failing to qualify for the other categories is not an argument."""
        for r in rules:
            if r["category"] == "optional" and r["review_status"] == "verified":
                assert r.get("clinician_approved") is True, (
                    f"{r['id']} is a verified optional rule without explicit "
                    f"clinician approval"
                )

    def test_migration_placeholders_can_never_be_verified(self, rules):
        """A parked relation must be structurally unpublishable.

        The schema migration had to give every rule a parseable relation. Where
        the legacy `take_together` had no equivalent, it parked `with_food` —
        a value the pipeline never authored. Promoting such a rule would ship a
        placeholder as clinical guidance.
        """
        for r in rules:
            if r.get("_relation_is_migration_placeholder"):
                assert r["review_status"] != "verified", (
                    f"{r['id']} carries a placeholder relation and must be "
                    f"re-authored from its source before promotion"
                )

    def test_min_dose_shape(self, rules):
        """A dose gate either gates, or the artifact is rejected.

        The legacy parser accepted a malformed min_dose by silently dropping the
        threshold, converting a dose-conditional rule into one that always
        fires. Nothing tested this on either side of the sync.
        """
        for r in rules:
            if "min_dose" not in r:
                continue
            gate = r["min_dose"]
            assert isinstance(gate, dict), r["id"]
            assert set(gate) == {"tag", "mg"}, (
                f"{r['id']}: min_dose must be exactly {{tag, mg}}, got {sorted(gate)}"
            )
            assert isinstance(gate["tag"], str) and gate["tag"].strip(), r["id"]
            assert gate["tag"] == gate["tag"].lower(), r["id"]
            assert isinstance(gate["mg"], (int, float)) and gate["mg"] > 0, r["id"]


# ── Publication gate ───────────────────────────────────────────────

class TestTimingPublication:
    def test_no_rule_is_verified_without_canonical_identity(self, rules):
        for r in rules:
            if r["review_status"] != "verified":
                continue
            assert r.get("ingredient1_tags") or r.get("ingredient1_rxcuis"), r["id"]

    def test_rejected_rules_are_not_shipped_in_the_runtime_artifact(self, rules):
        for r in rules:
            assert r["review_status"] != "rejected", (
                f"{r['id']} is rejected and must be moved to the rejection "
                f"ledger, not left in the runtime artifact"
            )

    def test_rejection_ledger_records_every_removed_rule(self, rules):
        """Runtime omission must not erase clinical history.

        Without a ledger the same unsupported rule gets rediscovered and
        reintroduced later, with the same citation, by someone acting in good
        faith.
        """
        if not REJECTION_LEDGER.exists():
            pytest.skip("no rules rejected yet")
        ledger = json.loads(REJECTION_LEDGER.read_text())
        shipped = {r["id"] for r in rules}
        for entry in ledger["rejected"]:
            for field in (
                "id",
                "prior_claim",
                "rejection_reason",
                "source_reviewed",
                "reviewer",
                "reviewed_on",
            ):
                assert field in entry, f"{entry.get('id')} missing {field}"
            assert entry["id"] not in shipped, (
                f"{entry['id']} is both rejected and shipped"
            )
            # A fingerprint makes reintroduction under a different id or
            # slightly reworded advice detectable instead of invisible.
            assert entry.get("clinical_fingerprint"), (
                f"{entry['id']} has no clinical fingerprint"
            )

    def test_no_shipped_rule_matches_a_rejected_fingerprint(self, rules):
        """Guard against a rejected claim returning under a new id."""
        if not REJECTION_LEDGER.exists():
            pytest.skip("no rules rejected yet")
        ledger = json.loads(REJECTION_LEDGER.read_text())
        rejected_pairs = set()
        for entry in ledger["rejected"]:
            fp = entry.get("clinical_fingerprint") or {}
            pair = (fp.get("ingredient1"), fp.get("ingredient2"))
            if all(pair):
                rejected_pairs.add(tuple(sorted(str(x) for x in pair)))

        for r in rules:
            pair = (r["ingredient1"], r.get("ingredient2"))
            if not all(pair):
                continue
            key = tuple(sorted(str(x) for x in pair))
            assert key not in rejected_pairs, (
                f"{r['id']} reintroduces a rejected claim ({key}). If this is "
                f"deliberate, the ledger entry needs a superseding_rule."
            )


# ── Source quality ─────────────────────────────────────────────────

class TestTimingSources:
    def test_every_rule_has_at_least_one_source(self, rules):
        for r in rules:
            assert len(r["sources"]) >= 1, f"Rule {r['id']} has no sources"

    def test_source_type_valid(self, rules):
        for r in rules:
            for s in r["sources"]:
                assert s["source_type"] in VALID_SOURCE_TYPES, \
                    f"Rule {r['id']} has invalid source_type: {s['source_type']}"

    def test_sources_have_url(self, rules):
        for r in rules:
            for s in r["sources"]:
                assert "url" in s and s["url"].startswith("http"), \
                    f"Rule {r['id']} source missing valid URL"

    def test_source_type_matches_the_url(self, rules):
        """A PubMed URL typed as `reference` lets a primary study masquerade
        as a general reference — and vice versa — which defeats the whole point
        of keeping source_authority separate from evidence_level."""
        for r in rules:
            for s in r["sources"]:
                if "pubmed.ncbi.nlm.nih.gov" in s["url"]:
                    assert s["source_type"] == "pubmed", (
                        f"{r['id']}: PubMed URL typed as {s['source_type']}"
                    )
                if "dailymed.nlm.nih.gov" in s["url"]:
                    assert s["source_type"] == "fda", (
                        f"{r['id']}: DailyMed URL typed as {s['source_type']}"
                    )
                if "ods.od.nih.gov" in s["url"]:
                    assert s["source_type"] in {"nih_ods", "reference"}, (
                        f"{r['id']}: ODS URL typed as {s['source_type']}"
                    )

    def test_pubmed_urls_are_specific(self, rules):
        """PubMed URLs must point to a specific article, not a search query."""
        for r in rules:
            for s in r["sources"]:
                if s["source_type"] == "pubmed":
                    url = s["url"]
                    assert "?term=" not in url and "/?term=" not in url, \
                        f"Rule {r['id']} has query-placeholder PubMed URL: {url}"

    def test_authority_matches_at_least_one_cited_source(self, rules):
        """`source_authority` is a claim about provenance, not a vibe.

        A mechanism paper cannot justify fda_label, and a PubMed citation
        cannot justify product_label. Each authority must be backed by a
        source of a compatible type.
        """
        compatible = {
            "fda_label": {"fda"},
            "product_label": {"fda", "reference"},
            "guideline": {"reference", "nih_ods", "nccih", "pubmed"},
            "systematic_review": {"pubmed"},
            "clinical_study": {"pubmed"},
            "mechanism": {"pubmed", "reference"},
            "reference": {"reference", "nih_ods", "nccih", "pubmed", "fda"},
        }
        for r in rules:
            if r["review_status"] != "verified":
                continue
            allowed = compatible[r["source_authority"]]
            types = {s["source_type"] for s in r["sources"]}
            assert types & allowed, (
                f"{r['id']} claims source_authority={r['source_authority']} "
                f"but cites only {sorted(types)}"
            )

    def test_verified_rules_carry_canaries(self, rules):
        for r in rules:
            if r["review_status"] != "verified":
                continue
            canaries = r.get("canaries")
            assert canaries, f"{r['id']} is verified without canaries"
            assert canaries.get("negative"), (
                f"{r['id']} has no negative canary — reachability alone does "
                f"not prove a rule stops firing where it should not"
            )

    def test_suppressed_rules_record_structured_blockers(self, rules):
        for r in rules:
            if r["review_status"] != "needs_revision":
                continue
            assert r.get("review_note"), f"{r['id']} suppressed with no reason"
            assert r.get("review_blockers"), (
                f"{r['id']} has no structured blockers, so the remaining work "
                f"is not measurable"
            )

    def test_fda_authority_is_backed_by_an_fda_source(self, rules):
        """`source_authority: fda_label` is a claim about provenance.

        It is the strongest authority the app can display, so it must not be
        assignable to a rule whose only citation is a mechanism paper.
        """
        for r in rules:
            if r["source_authority"] != "fda_label":
                continue
            assert any(s["source_type"] == "fda" for s in r["sources"]), (
                f"{r['id']} claims FDA-label authority without an FDA source"
            )


# ── Data quality ───────────────────────────────────────────────────

class TestTimingDataQuality:
    def test_corpus_does_not_silently_empty(self, rules):
        """A count floor is the wrong guard now.

        Section 2 shrinks the corpus deliberately — a rule whose source does
        not support it is removed, and that is the product working, not
        failing. What must not happen is the file quietly emptying, or rules
        vanishing without a ledger entry (covered by
        test_rejection_ledger_records_every_removed_rule).
        """
        assert rules, "the timing corpus is empty"
        verified = [r for r in rules if r["review_status"] == "verified"]
        assert verified, (
            "no rule is verified — the feature would render nothing at all"
        )

    def test_established_separations_have_penalty(self, rules):
        for r in rules:
            if (
                r["timing_relation"]["type"] in {"separate_from", "separate_from_medications"}
                and r["evidence_level"] == "established"
            ):
                assert r["score_impact"] < 0, \
                    f"Established separation rule {r['id']} should have negative score_impact"

    def test_iron_calcium_separation_exists(self, rules):
        """The most clinically important supplement pair must be present."""
        pairs = {(r["ingredient1"], r.get("ingredient2")) for r in rules}
        assert ("iron", "calcium") in pairs or ("calcium", "iron") in pairs

    def test_actionable_pairs_are_unique(self, rules):
        pairs = [
            tuple(sorted((r["ingredient1"], r.get("ingredient2") or "")))
            for r in rules
        ]
        duplicates = sorted({pair for pair in pairs if pairs.count(pair) > 1})
        assert duplicates == [], f"Duplicate timing pairs: {duplicates}"

    def test_psyllium_med_spacing_rule_exists(self, rules):
        rule = next(
            (r for r in rules if r["id"] == "timing_psyllium_water_med_spacing"),
            None,
        )
        assert rule is not None
        assert rule["ingredient1"] == "psyllium"
        # No specific second bottle exists here, so the relation must not
        # invent one.
        assert rule["timing_relation"]["type"] == "separate_from_medications"
        assert rule["timing_relation"]["minimum_hours"] == 3
        assert "8 oz" in rule["advice"]
        assert any("medlineplus.gov" in s["url"] for s in rule["sources"])

    def test_unsupported_or_misclassified_timing_rules_do_not_ship(self, rules):
        rejected = {
            "timing_berberine_b_vitamins_separate",
            "timing_fiber_minerals_separate",
            "timing_iron_calcium_zinc_separate",
            "timing_thyroid_med_minerals_separate",
            "timing_vitamin_e_vitamin_k_separate",
            "timing_vitamin_k_anticoagulants_consistency",
        }

        assert rejected.isdisjoint({r["id"] for r in rules})

    def test_rejected_vitamin_a_rule_does_not_return(self, rules):
        """timing_fat_soluble_vitamins_with_food was rejected on 2026-08-01:
        the ODS vitamin A page contains no fat or food guidance at all, and the
        catalog tags beta-carotene products as `vitamin_a`, so retinol and
        provitamin carotenoids cannot be told apart by tag."""
        assert "timing_fat_soluble_vitamins_with_food" not in {
            r["id"] for r in rules
        }

    def test_lipoic_acid_does_not_invent_a_meal_interval(self, rules):
        """The cited LPI page supports fasting, but not a 30-minute window."""
        rule = next(r for r in rules if r["id"] == "timing_ala_empty_stomach")

        assert rule["review_status"] == "verified"
        assert rule["timing_relation"] == {"type": "empty_stomach"}
        assert "30 min" not in rule["advice"].lower()

    def test_brewed_tea_trial_is_not_published_for_extract_capsules(self, rules):
        """A beverage/meal trial cannot verify supplement-form spacing."""
        rule = next(r for r in rules if r["id"] == "timing_egcg_iron_separate")

        assert rule["review_status"] == "needs_revision"
        assert "form_specific_evidence_missing" in rule["review_blockers"]

    def test_vitamin_e_rule_cites_direct_meal_absorption_evidence(self, rules):
        rule = next(r for r in rules if r["id"] == "timing_vitamin_e_with_food")
        urls = {source["url"] for source in rule["sources"]}

        assert "https://pubmed.ncbi.nlm.nih.gov/15522126/" in urls

    def test_calcium_thyroid_copy_stays_within_its_citations(self, rules):
        rule = next(
            r for r in rules
            if r["id"] == "timing_calcium_iron_thyroid_separate"
        )
        mechanism = rule["mechanism"].lower()

        assert "physiologic ph" not in mechanism
        assert "calcium citrate" not in mechanism

    def test_levothyroxine_rules_do_not_generalize_to_all_thyroid_drugs(
        self, rules
    ):
        scoped = [
            rule for rule in rules
            if rule["review_status"] == "verified"
            and "10582" in (
                rule.get("ingredient1_rxcuis", [])
                + rule.get("ingredient2_rxcuis", [])
            )
        ]

        assert scoped
        for rule in scoped:
            advice = rule["advice"].lower()
            assert "levothyroxine" in advice, rule["id"]
            assert "thyroid medication" not in advice, rule["id"]

    def test_advice_is_consumer_friendly(self, rules):
        for r in rules:
            assert len(r["advice"]) >= 20, f"Rule {r['id']} advice too short"
            assert len(r["advice"]) <= 300, f"Rule {r['id']} advice too long for UI"

    def test_advice_voice_stays_calm_advisory(self, rules):
        """No directives anywhere in consumer-facing copy, not just at the start.

        The project voice is calm-advisory: "Worth a conversation with your
        doctor", never "Avoid" / "Do not" / "Never". Checking only the opening
        word let a directive sit mid-sentence, which is where they actually
        occur. Only VERIFIED rules are gated — a suppressed rule's copy is
        rewritten as part of its promotion.
        """
        banned = (
            "avoid",
            "do not ",
            "don't ",
            "never ",
            "must ",
            "stop ",
            "should not",
        )
        for r in rules:
            if r["review_status"] != "verified":
                continue
            lowered = r["advice"].lower()
            found = [phrase for phrase in banned if phrase in lowered]
            assert not found, (
                f"{r['id']} uses directive voice {found}: {r['advice'][:70]}"
            )

    def test_no_advice_shouts(self, rules):
        """All-caps words read as alarm, which the voice rules exclude."""
        import re as _re

        for r in rules:
            shouted = _re.findall(r"\b[A-Z]{3,}\b", r["advice"])
            allowed = {"EGCG", "CoQ10", "DHA", "EPA", "ALA", "IU"}
            offenders = [w for w in shouted if w not in allowed]
            assert not offenders, f"{r['id']} shouts: {offenders}"
