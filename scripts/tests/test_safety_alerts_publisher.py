"""Publisher tests — resolution, feed assembly, and the manifest contract.

Uses fixtures throughout rather than scripts/dist, so these are safe to run
while a release is building.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from build_safety_alerts import (  # noqa: E402
    build_feed,
    build_ingredient_index,
    resolve_scope,
    stage,
)


def _blob(dsld_id, canonical_ids):
    """Mirror of the shipped blob shape: display_ingredients carries the
    COMPLETE ingredient list, including demoted and inactive rows."""
    return {
        "dsld_id": dsld_id,
        "display_ingredients": [{"canonical_id": cid} for cid in canonical_ids],
    }


@pytest.fixture
def blobs(tmp_path):
    directory = tmp_path / "detail_blobs"
    directory.mkdir()
    fixtures = {
        # a demoted absorption aid — still physically in the bottle
        "306237": ["ashwagandha", "piperine", "PII_HPMC", "silica"],
        "111111": ["tianeptine", "PII_HPMC"],
        "222222": ["ashwagandha"],
        "333333": ["caffeine"],
    }
    for dsld_id, ids in fixtures.items():
        (directory / f"{dsld_id}.json").write_text(json.dumps(_blob(dsld_id, ids)))
    return directory


def _alert(**overrides):
    record = {
        "alert_id": "SA_2026_0001",
        "revision": 1,
        "event_type": "ingredient_ban",
        "status": "published",
        "authority": "FDA",
        "source_url": "https://www.fda.gov/example",
        "evidence_verified_at": "2026-08-08",
        "fda_class": None,
        "jurisdiction": "US",
        "effective_date": "2026-08-01",
        "published_at": "2026-08-08T14:00:00Z",
        "scope": {"ingredient_canonical_ids": ["tianeptine"], "dsld_ids": []},
        "resolved_dsld_ids": ["111111"],
        "catalog_snapshot_version": "2026.08.07.192916",
        "lots": None,
        "headline": "Tianeptine is prohibited",
        "body": "FDA has determined tianeptine is not a lawful dietary ingredient.",
        "action": "Stop taking this product.",
        "expires_at": None,
        "retracted": False,
    }
    record.update(overrides)
    return record


class TestIngredientIndex:
    def test_indexes_every_canonical_id(self, blobs):
        index = build_ingredient_index(blobs)
        assert index["tianeptine"] == {"111111"}
        assert index["ashwagandha"] == {"306237", "222222"}

    def test_a_demoted_ingredient_is_still_indexed(self, blobs):
        """Bioperine is demoted to an absorption aid by scoring — it is still in
        the bottle. A ban must not be escapable by scoring treatment."""
        assert build_ingredient_index(blobs)["piperine"] == {"306237"}

    def test_inactive_rule_ids_are_indexed_too(self, blobs):
        """A banned substance can appear as an excipient, not just an active."""
        assert build_ingredient_index(blobs)["silica"] == {"306237"}

    def test_unparseable_blob_is_skipped_not_fatal(self, blobs):
        (blobs / "broken.json").write_text("{not json")
        assert build_ingredient_index(blobs)["tianeptine"] == {"111111"}


class TestResolution:
    def test_ingredient_ban_resolves_to_containing_products(self, blobs):
        index = build_ingredient_index(blobs)
        resolved, warnings = resolve_scope(_alert(), index, set())
        assert resolved == ["111111"]
        assert warnings == []

    def test_multiple_scoped_ingredients_union(self, blobs):
        index = build_ingredient_index(blobs)
        record = _alert(scope={"ingredient_canonical_ids": ["tianeptine", "caffeine"], "dsld_ids": []})
        resolved, _ = resolve_scope(record, index, set())
        assert resolved == ["111111", "333333"]

    def test_unknown_ingredient_warns_but_does_not_fail(self, blobs):
        """The substance may genuinely not be in this snapshot. The usual cause
        is an id typo, which a curator should see — but it is not fatal."""
        index = build_ingredient_index(blobs)
        record = _alert(scope={"ingredient_canonical_ids": ["not_a_real_id"], "dsld_ids": []})
        resolved, warnings = resolve_scope(record, index, set())
        assert resolved == []
        assert any("not_a_real_id" in w for w in warnings)

    def test_product_recall_resolves_only_known_ids(self, blobs):
        index = build_ingredient_index(blobs)
        record = _alert(
            event_type="product_recall",
            scope={"ingredient_canonical_ids": [], "dsld_ids": ["306237", "999999"]},
        )
        resolved, warnings = resolve_scope(record, index, {"306237", "111111"})
        assert resolved == ["306237"]
        assert any("999999" in w for w in warnings)

    def test_resolution_never_matches_on_name_similarity(self, blobs):
        index = build_ingredient_index(blobs)
        record = _alert(scope={"ingredient_canonical_ids": ["tianeptine sodium"], "dsld_ids": []})
        resolved, _ = resolve_scope(record, index, set())
        assert resolved == []


class TestFeed:
    def test_only_the_latest_revision_ships(self):
        feed = build_feed([_alert(revision=1), _alert(revision=2, headline="corrected")], "2026-08-08")
        assert feed["alert_count"] == 1
        assert feed["alerts"][0]["revision"] == 2
        assert feed["alerts"][0]["headline"] == "corrected"

    def test_draft_revision_cannot_hide_the_current_published_alert(self):
        feed = build_feed(
            [
                _alert(revision=1),
                _alert(revision=2, status="draft", headline="unapproved edit"),
            ],
            "2026-08-08",
        )
        assert feed["alert_count"] == 1
        assert feed["alerts"][0]["revision"] == 1

    def test_retracted_and_expired_are_dropped(self):
        records = [
            _alert(alert_id="SA_2026_0001"),
            _alert(alert_id="SA_2026_0002", status="retracted", retracted=True),
            _alert(alert_id="SA_2026_0003", expires_at="2026-08-01"),
            _alert(alert_id="SA_2026_0004", status="draft"),
            _alert(alert_id="SA_2026_0005", effective_date="2026-12-01"),
        ]
        feed = build_feed(records, "2026-08-08")
        assert [a["alert_id"] for a in feed["alerts"]] == ["SA_2026_0001"]

    def test_internal_fields_never_ship(self):
        record = _alert()
        record["_source_path"] = "/somewhere/local.json"
        feed = build_feed([record], "2026-08-08")
        assert not any(k.startswith("_") for k in feed["alerts"][0])


class TestManifestContract:
    def test_checksum_lives_in_the_manifest_not_the_feed(self, tmp_path):
        """A file cannot contain its own digest without invalidating it. Same
        contract the interaction DB already ships under."""
        staged = stage([_alert()], "2026-08-08", dist_dir=tmp_path)
        feed_text = (tmp_path / "safety_alerts.json").read_text()
        assert "checksum" not in feed_text
        assert staged["checksum"].startswith("sha256:")

    def test_manifest_checksum_matches_the_feed_on_disk(self, tmp_path):
        staged = stage([_alert()], "2026-08-08", dist_dir=tmp_path)
        actual = hashlib.sha256((tmp_path / "safety_alerts.json").read_bytes()).hexdigest()
        assert staged["checksum"] == f"sha256:{actual}"

    def test_manifest_reports_only_snapshots_pinned_in_approved_records(self, tmp_path):
        staged = stage(
            [
                _alert(catalog_snapshot_version="2026.08.01.010203"),
                _alert(
                    alert_id="SA_2026_0002",
                    catalog_snapshot_version="2026.08.02.010203",
                ),
            ],
            "2026-08-08",
            dist_dir=tmp_path,
        )
        assert staged["catalog_snapshot_versions"] == [
            "2026.08.01.010203",
            "2026.08.02.010203",
        ]

    def test_manifest_publishes_the_latest_revision_map(self, tmp_path):
        """Clients ignore a revision they have applied and never apply a lower
        one — the map lets them decide without parsing the whole feed."""
        staged = stage([_alert(revision=1), _alert(revision=4)], "2026-08-08", dist_dir=tmp_path)
        assert staged["latest_revisions"] == {"SA_2026_0001": 4}

    def test_manifest_retains_a_retraction_revision_as_a_tombstone(self, tmp_path):
        """A client must distinguish an intentional retraction from omission."""
        staged = stage(
            [
                _alert(revision=1),
                _alert(revision=2, status="retracted", retracted=True),
            ],
            "2026-08-08",
            dist_dir=tmp_path,
        )
        assert staged["latest_revisions"] == {"SA_2026_0001": 2}
        assert staged["retired_alerts"] == {"SA_2026_0001": 2}

    def test_no_temp_file_is_left_behind(self, tmp_path):
        stage([_alert()], "2026-08-08", dist_dir=tmp_path)
        assert not list(tmp_path.glob("*.tmp")), "partially written feed would fail a client checksum"

    def test_restaging_identical_input_is_byte_stable(self, tmp_path):
        """A feed that churns on every run would make clients re-download and
        re-evaluate for nothing."""
        first = stage([_alert()], "2026-08-08", dist_dir=tmp_path)["checksum"]
        second = stage([_alert()], "2026-08-08", dist_dir=tmp_path)["checksum"]
        assert first == second

    def test_changed_same_day_feed_gets_a_new_release_version(self, tmp_path):
        first = stage([_alert()], "2026-08-08", dist_dir=tmp_path)
        second = stage(
            [_alert(headline="Corrected safety notice")],
            "2026-08-08",
            dist_dir=tmp_path,
        )
        assert first["feed_version"] != second["feed_version"]


class TestStageImmutability:
    def test_resolution_does_not_mutate_a_published_record(self, tmp_path, monkeypatch):
        """Approval freezes the exact applicability set under its revision."""
        import build_safety_alerts as publisher

        dist_dir = tmp_path / "dist"
        blobs_dir = dist_dir / "detail_blobs"
        blobs_dir.mkdir(parents=True)
        (dist_dir / "export_manifest.json").write_text(
            json.dumps({"db_version": "2026.08.08.010203"}),
        )
        (blobs_dir / "999999.json").write_text(
            json.dumps(_blob("999999", ["tianeptine"])),
        )
        record = _alert(
            resolved_dsld_ids=["111111"],
            catalog_snapshot_version="2026.08.01.010203",
        )
        monkeypatch.setattr(publisher, "BLOBS_DIR", blobs_dir)
        monkeypatch.setattr(publisher, "CATALOG_MANIFEST", dist_dir / "export_manifest.json")

        outcome = publisher.resolve_all([record], write=False)
        assert outcome["ok"]
        assert record["resolved_dsld_ids"] == ["111111"]
        assert record["catalog_snapshot_version"] == "2026.08.01.010203"
