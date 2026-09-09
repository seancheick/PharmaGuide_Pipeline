"""The extractor boundary: what a provider adapter may and may not get away with.

These run entirely on the fake adapter. No provider is called, no holdout
answer is read, and nothing here measures a model; the point is that the parts
around a model are correct before one is chosen.
"""
from __future__ import annotations

import copy
import hashlib

import pytest

from submission_review.extraction.adapters.fake_adapter import FakeAdapter
from submission_review.extraction.extractor import (
    PreparedBundle,
    PreparedInput,
    ExtractionConfig,
    ExtractionError,
    LabelDraftExtractor,
    ExtractionResult,
    Usage,
)

_PHOTO_A = "10000000-0000-0000-0000-000000000001"
_PHOTO_B = "10000000-0000-0000-0000-000000000002"


def _bundle(revision: int = 1) -> PreparedBundle:
    return PreparedBundle(
        submission_id="018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
        evidence_revision=revision,
        photos=(
            PreparedInput("i0", _PHOTO_A, "a" * 64, hashlib.sha256(b"one").hexdigest(), "image/jpeg", 3, b"one"),
            PreparedInput("i1", _PHOTO_B, "b" * 64, hashlib.sha256(b"two").hexdigest(), "image/jpeg", 3, b"two"),
        ),
    )


def _config(**overrides) -> ExtractionConfig:
    base = {
        "provider": "fake",
        "model": "fake-1",
        "model_digest": "c" * 64,
        "prompt_version": "p1",
        "retention_policy_version": "fixture-retention-v1",
    }
    base.update(overrides)
    return ExtractionConfig(**base)


class _Adapter:
    """Returns whatever it is told to, so the boundary can be probed."""

    def __init__(self, payload):
        self.payload = payload

    def extract(self, bundle, config):
        return ExtractionResult(copy.deepcopy(self.payload), Usage())


class _CrashingAdapter:
    def extract(self, bundle, config):
        raise RuntimeError("provider response contained a secret")


def _valid_payload(bundle, config):
    return FakeAdapter().extract(bundle, config).draft


def test_a_valid_model_draft_passes_with_its_usage() -> None:
    result = LabelDraftExtractor(FakeAdapter()).extract(_bundle(), _config())

    assert result.draft["schema_version"] == "label_draft_v1"
    assert result.draft["evidence_snapshot"] == _bundle().snapshot
    assert result.usage.latency_seconds >= 0
    assert result.usage.as_payload()["cost_microcents"] == 0


def test_an_adapter_without_stated_retention_terms_never_runs() -> None:
    # Silence is not consent. A provider that has not said what it does with a
    # user's photos does not get to see them.
    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(FakeAdapter()).extract(
            _bundle(), _config(retention_policy_version=None)
        )

    assert error.value.code == "provider_unavailable"


def test_a_draft_about_other_photos_is_refused() -> None:
    bundle = _bundle()
    payload = _valid_payload(bundle, _config())
    payload["evidence_snapshot"] = {_PHOTO_A: "a" * 64}
    payload["sent_inputs"] = [
        {
            "input_id": "i0",
            "photo_id": _PHOTO_A,
            "original_sha256": "a" * 64,
            "sent_sha256": "a" * 64,
        }
    ]

    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_Adapter(payload)).extract(bundle, _config())

    assert error.value.code == "model_failure"
    assert "leased evidence" in error.value.detail


def test_a_draft_for_the_wrong_revision_is_refused() -> None:
    bundle = _bundle(revision=2)
    payload = _valid_payload(bundle, _config())
    payload["evidence_revision"] = 1

    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_Adapter(payload)).extract(bundle, _config())

    assert "revision" in error.value.detail


def test_a_draft_claiming_another_model_is_refused() -> None:
    bundle = _bundle()
    payload = _valid_payload(bundle, _config())
    payload["model"] = "something-else"

    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_Adapter(payload)).extract(bundle, _config())

    assert error.value.code == "model_failure"


def test_a_mismatched_origin_is_caught_by_the_envelope_contract() -> None:
    # The envelope owns this rule: a human transcription must name a human
    # provider. The extractor does not restate it, it surfaces it typed.
    bundle = _bundle()
    payload = _valid_payload(bundle, _config())
    payload["draft_origin"] = "human_transcription"

    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_Adapter(payload)).extract(bundle, _config())

    assert error.value.code == "model_failure"
    assert "invalid provider draft" in error.value.detail


def test_an_extractor_configured_as_human_still_cannot_file_transcription() -> None:
    # The attack the extractor's own check exists for: a configuration that
    # claims to be a person, so the envelope's provider rule is satisfied.
    human = _config(provider="human", model="human")
    bundle = _bundle()
    payload = _valid_payload(bundle, human)
    payload["draft_origin"] = "human_transcription"
    payload["sent_inputs"] = []

    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_Adapter(payload)).extract(bundle, human)

    assert "model drafts only" in error.value.detail


def test_an_invalid_envelope_becomes_a_typed_failure_not_a_crash() -> None:
    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_Adapter({"schema_version": "nonsense"})).extract(
            _bundle(), _config()
        )

    assert error.value.code == "model_failure"
    assert error.value.as_envelope()["schema_version"] == "extraction_failure_v1"


def test_an_empty_lease_is_refused_before_any_provider_work() -> None:
    empty = PreparedBundle(
        submission_id="018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
        evidence_revision=1,
        photos=(),
    )

    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(FakeAdapter()).extract(empty, _config())

    assert error.value.code == "unsupported_evidence"


def test_adapter_failures_stay_typed() -> None:
    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(FakeAdapter(fail_with="provider_unavailable")).extract(
            _bundle(), _config()
        )

    assert error.value.code == "provider_unavailable"


def test_unexpected_adapter_failures_are_typed_without_leaking_details() -> None:
    with pytest.raises(ExtractionError) as error:
        LabelDraftExtractor(_CrashingAdapter()).extract(_bundle(), _config())

    assert error.value.code == "provider_unavailable"
    assert error.value.detail == "provider adapter failed"
    assert "secret" not in str(error.value)


def test_an_unknown_failure_code_cannot_be_invented() -> None:
    with pytest.raises(ValueError):
        ExtractionError("something_new", "not in the vocabulary")


def test_adapter_usage_is_preserved_and_cannot_be_overridden_by_details() -> None:
    class PaidAdapter(FakeAdapter):
        def extract(self, bundle, config):
            result = super().extract(bundle, config)
            return ExtractionResult(result.draft, Usage(microcents=12, details={"cost_microcents": 0}))

    result = LabelDraftExtractor(PaidAdapter()).extract(_bundle(), _config())
    assert result.usage.as_payload()["cost_microcents"] == 12


def test_draft_with_invented_transmission_hash_is_rejected() -> None:
    payload = _valid_payload(_bundle(), _config())
    payload["sent_inputs"][0]["sent_sha256"] = "f" * 64
    with pytest.raises(ExtractionError, match="prepared evidence"):
        LabelDraftExtractor(_Adapter(payload)).extract(_bundle(), _config())
