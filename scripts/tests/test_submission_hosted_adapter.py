"""Hosted vision candidates use one label contract and pinned provider state."""
from __future__ import annotations

import hashlib
import json

import pytest

from submission_review.extraction.adapters.fake_adapter import FakeAdapter
from submission_review.extraction.adapters.hosted_adapter import (
    GEMINI_FREE_RETENTION_POLICY,
    GROQ_DEFAULT_RETENTION_POLICY,
    HOSTED_PROMPT_VERSION,
    GeminiAdapter,
    GroqAdapter,
    model_descriptor_digest,
)
from submission_review.extraction.envelope import LABEL_CONTENT_KEYS, generation_schema
from submission_review.extraction.extractor import (
    ExtractionConfig,
    ExtractionError,
    PreparedBundle,
    PreparedInput,
)

PHOTO_ID = "10000000-0000-0000-0000-000000000001"
ORIGINAL_DIGEST = "c" * 64
SENT_BYTES = b"prepared-jpeg"
SENT_DIGEST = hashlib.sha256(SENT_BYTES).hexdigest()


def _bundle() -> PreparedBundle:
    return PreparedBundle(
        submission_id="018f4c79-7c7e-4c70-9d62-7fc3b9ce6a11",
        evidence_revision=2,
        photos=(PreparedInput(
            input_id="i0",
            photo_id=PHOTO_ID,
            original_sha256=ORIGINAL_DIGEST,
            sent_sha256=SENT_DIGEST,
            content_type="image/jpeg",
            byte_size=len(SENT_BYTES),
            data=SENT_BYTES,
        ),),
    )


def _reading() -> dict:
    draft = FakeAdapter().extract(
        _bundle(),
        ExtractionConfig(
            provider="fake",
            model="fake-1",
            model_digest="f" * 64,
            prompt_version="p1",
            retention_policy_version="local-only-v1",
        ),
    ).draft
    return {key: draft[key] for key in LABEL_CONTENT_KEYS}


GEMINI_DESCRIPTOR = {
    "name": "models/gemini-2.5-flash",
    "version": "001",
    "displayName": "Gemini 2.5 Flash",
    "supportedGenerationMethods": ["generateContent"],
    "inputTokenLimit": 1_048_576,
    "outputTokenLimit": 65_536,
}
GROQ_DESCRIPTOR = {
    "id": "qwen/qwen3.8-27b",
    "active": True,
    "input_modalities": ["text", "image"],
    "output_modalities": ["text"],
    "supported_features": ["json_mode", "reasoning"],
    "context_window": 131_042,
    "max_completion_tokens": 16_384,
    "pricing": {"prompt": "0.0000008", "completion": "0.000004"},
}


class _Transport:
    def __init__(self, provider: str, reading: dict | None = None) -> None:
        self.provider = provider
        self.reading = _reading() if reading is None else reading
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []

    def request_json(self, method, url, *, headers, body=None, timeout):
        self.calls.append((method, url, headers, body))
        assert timeout > 0
        if method == "GET":
            return GEMINI_DESCRIPTOR if self.provider == "gemini" else GROQ_DESCRIPTOR
        if self.provider == "gemini":
            return {
                "modelVersion": "gemini-2.5-flash",
                "candidates": [{"finishReason": "STOP", "content": {
                    "parts": [{"text": json.dumps(self.reading)}],
                }}],
                "usageMetadata": {"promptTokenCount": 100,
                                  "candidatesTokenCount": 50,
                                  "totalTokenCount": 150},
            }
        return {
            "model": "qwen/qwen3.8-27b",
            "choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(self.reading),
            }}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "total_tokens": 150},
        }


def _config(provider: str, descriptor: dict, **overrides) -> ExtractionConfig:
    base = {
        "provider": provider,
        "model": ("gemini-2.5-flash" if provider == "gemini"
                  else "qwen/qwen3.8-27b"),
        "model_digest": model_descriptor_digest(provider, descriptor),
        "prompt_version": HOSTED_PROMPT_VERSION,
        "retention_policy_version": (
            GEMINI_FREE_RETENTION_POLICY if provider == "gemini"
            else GROQ_DEFAULT_RETENTION_POLICY
        ),
    }
    base.update(overrides)
    return ExtractionConfig(**base)


def test_gemini_uses_native_structured_output_and_program_owned_provenance() -> None:
    transport = _Transport("gemini")
    adapter = GeminiAdapter(api_key="secret", transport=transport)

    result = adapter.extract(_bundle(), _config("gemini", GEMINI_DESCRIPTOR))

    post = next(call for call in transport.calls if call[0] == "POST")
    headers, body = post[2], post[3]
    assert headers["x-goog-api-key"] == "secret"
    assert "secret" not in json.dumps(body)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseJsonSchema"] == generation_schema(compact=True)
    assert body["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/jpeg"
    prompt = body["contents"][0]["parts"][0]["text"]
    assert '"i0"' in prompt
    assert PHOTO_ID not in prompt
    assert result.draft["provider"] == "gemini"
    assert result.draft["evidence_snapshot"] == {PHOTO_ID: ORIGINAL_DIGEST}
    assert result.usage.microcents == 0
    assert result.usage.details["total_tokens"] == 150


def test_groq_uses_supported_json_mode_then_the_same_runtime_validator() -> None:
    transport = _Transport("groq")
    adapter = GroqAdapter(api_key="secret", transport=transport)

    result = adapter.extract(_bundle(), _config("groq", GROQ_DESCRIPTOR))

    body = next(call[3] for call in transport.calls if call[0] == "POST")
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["content"][1]["type"] == "image_url"
    assert result.draft["provider"] == "groq"
    # Conservative list-price accounting: $0.0000008 input, $0.000004 output.
    assert result.usage.microcents == 28_000
    assert result.usage.details["total_tokens"] == 150


@pytest.mark.parametrize(
    ("adapter_type", "provider", "descriptor"),
    [(GeminiAdapter, "gemini", GEMINI_DESCRIPTOR),
     (GroqAdapter, "groq", GROQ_DESCRIPTOR)],
)
def test_hosted_model_metadata_is_pinned_before_photos_are_sent(
    adapter_type, provider, descriptor,
) -> None:
    transport = _Transport(provider)
    adapter = adapter_type(api_key="secret", transport=transport)
    bad = _config(provider, descriptor, model_digest="0" * 64)

    with pytest.raises(ExtractionError) as raised:
        adapter.extract(_bundle(), bad)

    assert raised.value.code == "provider_unavailable"
    assert "pinned" in raised.value.detail
    assert [call[0] for call in transport.calls] == ["GET"]


@pytest.mark.parametrize("adapter_type", [GeminiAdapter, GroqAdapter])
def test_missing_key_is_refused_without_contacting_a_provider(adapter_type) -> None:
    with pytest.raises(ExtractionError) as raised:
        adapter_type(api_key="")

    assert raised.value.code == "provider_unavailable"
    assert "API key" in raised.value.detail


@pytest.mark.parametrize(
    ("provider", "descriptor"),
    [("gemini", GEMINI_DESCRIPTOR), ("groq", GROQ_DESCRIPTOR)],
)
def test_model_descriptor_digest_ignores_key_order(provider, descriptor) -> None:
    reversed_descriptor = dict(reversed(tuple(descriptor.items())))
    assert model_descriptor_digest(provider, descriptor) == model_descriptor_digest(
        provider, reversed_descriptor
    )


def test_gemini_free_tier_policy_is_explicit_not_generic() -> None:
    adapter = GeminiAdapter(api_key="secret", transport=_Transport("gemini"))

    with pytest.raises(ExtractionError) as raised:
        adapter.extract(
            _bundle(),
            _config("gemini", GEMINI_DESCRIPTOR,
                    retention_policy_version="third-party-ai"),
        )

    assert raised.value.code == "provider_unavailable"
    assert "retention" in raised.value.detail


def test_invalid_hosted_draft_reports_only_the_contract_path() -> None:
    reading = _reading()
    reading["identity"]["brand"]["status"] = "invented"
    adapter = GeminiAdapter(
        api_key="secret", transport=_Transport("gemini", reading=reading)
    )

    with pytest.raises(ExtractionError) as raised:
        adapter.extract(_bundle(), _config("gemini", GEMINI_DESCRIPTOR))

    assert raised.value.code == "model_failure"
    assert raised.value.detail == "invalid hosted label reading at $.identity.brand.status"
    assert "Example" not in raised.value.detail
