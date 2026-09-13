"""Bounded Gemini and Groq vision transports for the one label-draft contract.

Provider code owns only transport, response decoding, usage, and model-service
pinning. The label instructions and envelope assembly remain owned by the same
contract used by Ollama, and every result still crosses ``label_draft_v1``'s
runtime validator before a worker can record it.

Hosted model APIs do not expose a cryptographic weights digest. The existing
``model_digest`` configuration field therefore pins the provider's complete
model descriptor. This catches alias, capability, context, and price changes;
it must not be described as proof that a provider has disclosed its weights.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
from decimal import Decimal, ROUND_CEILING
from typing import Any
from urllib.parse import quote

from ..bounded_http import TransportError, request
from ..envelope import LabelDraftError, generation_schema
from ..extractor import (
    ExtractionConfig,
    ExtractionError,
    ExtractionResult,
    PreparedBundle,
    Usage,
)
from .ollama_adapter import VISION_INSTRUCTION, to_model_envelope

HOSTED_PROMPT_VERSION = "label-draft-hosted-v2"
HOSTED_INPUT_INSTRUCTION = (
    "\nOrdered image aliases: {aliases}. In every model-authored photo_id field, "
    "return the matching input alias exactly. Internal photo identifiers are "
    "bound by the program after the response."
)
GEMINI_FREE_RETENTION_POLICY = "gemini-api-unpaid-terms-2026-09-13"
GROQ_DEFAULT_RETENTION_POLICY = "groq-inference-default-up-to-30d-2026-09-13"
GROQ_ZDR_RETENTION_POLICY = "groq-inference-zdr-2026-09-13"

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_TIMEOUT_SECONDS = 180.0
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# Both services cap inline-image requests at 20 MB. Base64 expands bytes by
# roughly one third, and the schema/prompt also consume body space.
MAX_TOTAL_IMAGE_BYTES = 14 * 1024 * 1024
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,118}[A-Za-z0-9]$")


def model_descriptor_digest(provider: str, descriptor: dict[str, Any]) -> str:
    """Fingerprint the exact provider descriptor used to admit a model."""
    if provider not in {"gemini", "groq"} or not isinstance(descriptor, dict):
        raise ValueError("unsupported model descriptor")
    canonical = json.dumps(
        descriptor, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(provider.encode("ascii") + b"\0" + canonical).hexdigest()


class HostedVisionAdapter:
    """One implementation with two fixed, explicitly decoded provider shapes."""

    def __init__(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        transport: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if provider not in {"gemini", "groq"}:
            raise ExtractionError("provider_unavailable", "unsupported hosted provider")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ExtractionError("provider_unavailable", "invalid hosted request deadline")
        key_name = "GEMINI_API_KEY" if provider == "gemini" else "GROQ_API_KEY"
        key = api_key if api_key is not None else os.environ.get(key_name)
        if not isinstance(key, str) or not key.strip():
            raise ExtractionError("provider_unavailable", f"{key_name} API key is not configured")
        self.provider = provider
        self._api_key = key.strip()
        self._timeout = timeout
        self._transport = transport or _HttpTransport()
        self.prompt_sha256 = _prompt_digest(provider)

    def extract(
        self, bundle: PreparedBundle, config: ExtractionConfig,
    ) -> ExtractionResult:
        self._validate_configuration(config)
        if sum(photo.byte_size for photo in bundle.photos) > MAX_TOTAL_IMAGE_BYTES:
            raise ExtractionError(
                "unsupported_evidence", "prepared evidence exceeds hosted request limit",
                usage=Usage(),
            )
        descriptor = self._verify_model(config)
        body = self._request_body(bundle, config)
        try:
            payload = self._transport.request_json(
                "POST", self._completion_url(config.model),
                headers=self._headers, body=body, timeout=self._timeout,
            )
        except ExtractionError:
            raise
        except Exception as error:
            # The request may have reached the provider. Unknown spend remains
            # unknown so the worker stops admitting more paid calls.
            raise ExtractionError("provider_unavailable", "hosted request failed") from error
        reading, usage = (
            _parse_gemini(payload, config)
            if self.provider == "gemini"
            else _parse_groq(payload, config, descriptor)
        )
        try:
            draft = to_model_envelope(reading, bundle, config)
        except LabelDraftError as error:
            # A contract path is safe operational detail; never include the
            # model's label text or the provider's raw body in an error.
            raise ExtractionError(
                "model_failure",
                f"invalid hosted label reading at {error.path}",
                usage=usage,
            ) from error
        except (ValueError, TypeError, KeyError) as error:
            raise ExtractionError("model_failure", "invalid hosted label reading", usage=usage) from error
        return ExtractionResult(draft, usage)

    def verify_model(self, config: ExtractionConfig) -> dict[str, Any]:
        """Public, read-only preflight used before any photograph is opened."""
        self._validate_configuration(config)
        return self._verify_model(config)

    def current_model_digest(self, model: str) -> str:
        """Return the descriptor pin for a diagnostic configuration."""
        _validate_model_name(model)
        descriptor = self._read_model_descriptor(model)
        _validate_descriptor(self.provider, model, descriptor)
        return model_descriptor_digest(self.provider, descriptor)

    def _validate_configuration(self, config: ExtractionConfig) -> None:
        if config.provider != self.provider or config.prompt_version != HOSTED_PROMPT_VERSION:
            raise ExtractionError(
                "provider_unavailable", "unsupported hosted configuration", usage=Usage(),
            )
        _validate_model_name(config.model)
        allowed = (
            {GEMINI_FREE_RETENTION_POLICY}
            if self.provider == "gemini"
            else {GROQ_DEFAULT_RETENTION_POLICY, GROQ_ZDR_RETENTION_POLICY}
        )
        if config.retention_policy_version not in allowed:
            raise ExtractionError(
                "provider_unavailable", "unsupported hosted retention policy", usage=Usage(),
            )

    def _verify_model(self, config: ExtractionConfig) -> dict[str, Any]:
        descriptor = self._read_model_descriptor(config.model)
        _validate_descriptor(self.provider, config.model, descriptor)
        if model_descriptor_digest(self.provider, descriptor) != config.model_digest:
            raise ExtractionError(
                "provider_unavailable", "hosted model descriptor does not match its pinned value",
                usage=Usage(),
            )
        return descriptor

    def _read_model_descriptor(self, model: str) -> dict[str, Any]:
        try:
            payload = self._transport.request_json(
                "GET", self._model_url(model), headers=self._headers,
                timeout=min(self._timeout, 30.0),
            )
        except ExtractionError:
            raise
        except Exception as error:
            raise ExtractionError(
                "provider_unavailable", "hosted model metadata is unavailable", usage=Usage(),
            ) from error
        if not isinstance(payload, dict):
            raise ExtractionError(
                "provider_unavailable", "hosted model metadata is invalid", usage=Usage(),
            )
        return payload

    @property
    def _headers(self) -> dict[str, str]:
        if self.provider == "gemini":
            return {"x-goog-api-key": self._api_key}
        return {"Authorization": f"Bearer {self._api_key}"}

    def _completion_url(self, model: str) -> str:
        if self.provider == "gemini":
            encoded = quote(model, safe="._-")
            return (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{encoded}:generateContent"
            )
        return "https://api.groq.com/openai/v1/chat/completions"

    def _model_url(self, model: str) -> str:
        encoded = quote(model, safe="/._-")
        if self.provider == "gemini":
            return f"https://generativelanguage.googleapis.com/v1beta/models/{encoded}"
        return f"https://api.groq.com/openai/v1/models/{encoded}"

    def _request_body(
        self, bundle: PreparedBundle, config: ExtractionConfig,
    ) -> dict[str, Any]:
        prompt = _prompt_for(bundle)
        if self.provider == "gemini":
            return {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        *[
                            {"inlineData": {
                                "mimeType": photo.content_type,
                                "data": base64.b64encode(photo.data).decode("ascii"),
                            }}
                            for photo in bundle.photos
                        ],
                    ],
                }],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 32_000,
                    "thinkingConfig": {"thinkingBudget": 0},
                    "responseMimeType": "application/json",
                    "responseJsonSchema": generation_schema(compact=True),
                },
            }
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend({
            "type": "image_url",
            "image_url": {"url": (
                f"data:{photo.content_type};base64,"
                f"{base64.b64encode(photo.data).decode('ascii')}"
            )},
        } for photo in bundle.photos)
        return {
            "model": config.model,
            "messages": [{"role": "user", "content": content}],
            # Qwen 3.8 vision currently advertises JSON mode, not Groq's strict
            # JSON-schema decoder. Runtime label_draft_v1 validation is unchanged.
            "response_format": {"type": "json_object"},
            "temperature": 1e-8,
            "seed": 0,
            "reasoning_effort": "none",
            "max_completion_tokens": 16_000,
            "stream": False,
        }


class GeminiAdapter(HostedVisionAdapter):
    """Gemini native ``generateContent`` API adapter."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("gemini", **kwargs)


class GroqAdapter(HostedVisionAdapter):
    """Groq OpenAI-compatible vision adapter."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("groq", **kwargs)


def _prompt_for(bundle: PreparedBundle) -> str:
    aliases = [photo.input_id for photo in bundle.photos]
    return VISION_INSTRUCTION + HOSTED_INPUT_INSTRUCTION.format(
        aliases=json.dumps(aliases),
    )


def _prompt_digest(provider: str) -> str:
    # Bind provider-specific output enforcement as well as shared prose.
    format_contract: dict[str, Any]
    if provider == "gemini":
        format_contract = {
            "api": "generateContent-v1beta",
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 32_000,
                "thinkingConfig": {"thinkingBudget": 0},
                "responseMimeType": "application/json",
                "responseJsonSchema": generation_schema(compact=True),
            },
        }
    else:
        format_contract = {
            "api": "openai-chat-completions",
            "response_format": {"type": "json_object"},
            "temperature": 1e-8,
            "seed": 0,
            "reasoning_effort": "none",
            "max_completion_tokens": 16_000,
        }
    body = {
        "prompt": VISION_INSTRUCTION,
        "input_instruction": HOSTED_INPUT_INSTRUCTION,
        "format_contract": format_contract,
    }
    return hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")).hexdigest()


def _validate_model_name(model: str) -> None:
    if (not isinstance(model, str) or not _MODEL_NAME.fullmatch(model)
            or ".." in model or "//" in model):
        raise ExtractionError("provider_unavailable", "invalid hosted model name", usage=Usage())


def _validate_descriptor(provider: str, model: str, descriptor: dict[str, Any]) -> None:
    if provider == "gemini":
        if (descriptor.get("name") != f"models/{model}"
                or not isinstance(descriptor.get("version"), str)
                or "generateContent" not in descriptor.get("supportedGenerationMethods", [])):
            raise ExtractionError(
                "provider_unavailable", "Gemini model is unavailable or incompatible",
                usage=Usage(),
            )
        return
    if (descriptor.get("id") != model or descriptor.get("active") is not True
            or "image" not in descriptor.get("input_modalities", [])
            or "text" not in descriptor.get("output_modalities", [])
            or "json_mode" not in descriptor.get("supported_features", [])):
        raise ExtractionError(
            "provider_unavailable", "Groq model is unavailable or incompatible", usage=Usage(),
        )


def _parse_gemini(
    payload: Any, config: ExtractionConfig,
) -> tuple[dict[str, Any], Usage]:
    usage = _gemini_usage(payload, config)
    if not isinstance(payload, dict) or payload.get("modelVersion") != config.model:
        raise ExtractionError("model_failure", "Gemini answered with a different model", usage=usage)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ExtractionError("model_failure", "Gemini returned an invalid reading", usage=usage)
    candidate = candidates[0]
    if not isinstance(candidate, dict) or candidate.get("finishReason") != "STOP":
        raise ExtractionError("model_failure", "Gemini did not complete its reading", usage=usage)
    content = candidate.get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    texts = [
        part.get("text")
        for part in parts if isinstance(part, dict) and part.get("thought") is not True
        and isinstance(part.get("text"), str)
    ]
    return _decode_reading(texts, "Gemini", usage), usage


def _gemini_usage(payload: Any, config: ExtractionConfig) -> Usage:
    raw = payload.get("usageMetadata", {}) if isinstance(payload, dict) else {}
    details = _token_details(raw)
    return Usage(microcents=0, details=details)


def _parse_groq(
    payload: Any, config: ExtractionConfig, descriptor: dict[str, Any],
) -> tuple[dict[str, Any], Usage]:
    raw_usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    details = _token_details(raw_usage)
    cost = _groq_list_price_microcents(raw_usage, descriptor)
    usage = Usage(microcents=cost, details=details)
    if not isinstance(payload, dict) or payload.get("model") != config.model:
        raise ExtractionError("model_failure", "Groq answered with a different model", usage=usage)
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ExtractionError("model_failure", "Groq returned an invalid reading", usage=usage)
    choice = choices[0]
    message = choice.get("message", {}) if isinstance(choice, dict) else {}
    if choice.get("finish_reason") != "stop" or not isinstance(message, dict):
        raise ExtractionError("model_failure", "Groq did not complete its reading", usage=usage)
    return _decode_reading([message.get("content")], "Groq", usage), usage


def _decode_reading(
    texts: list[Any], provider_name: str, usage: Usage,
) -> dict[str, Any]:
    if len(texts) != 1 or not isinstance(texts[0], str) or not texts[0].strip():
        raise ExtractionError(
            "model_failure", f"{provider_name} returned no single JSON reading", usage=usage,
        )
    try:
        reading = json.loads(texts[0])
    except (TypeError, ValueError) as error:
        raise ExtractionError(
            "model_failure", f"{provider_name} reading was not JSON", usage=usage,
        ) from error
    if not isinstance(reading, dict):
        raise ExtractionError(
            "model_failure", f"{provider_name} reading was not an object", usage=usage,
        )
    return reading


def _token_details(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens", "promptTokenCount"),
        "output_tokens": ("output_tokens", "completion_tokens", "candidatesTokenCount"),
        "total_tokens": ("total_tokens", "totalTokenCount"),
    }
    result: dict[str, int] = {}
    for target, keys in aliases.items():
        values = [raw.get(key) for key in keys if raw.get(key) is not None]
        if values and type(values[0]) is int and values[0] >= 0:
            result[target] = values[0]
    return result


def _groq_list_price_microcents(raw: Any, descriptor: dict[str, Any]) -> int:
    if not isinstance(raw, dict):
        raise ExtractionError("model_failure", "Groq usage was not reported")
    prompt = raw.get("prompt_tokens")
    completion = raw.get("completion_tokens")
    prices = descriptor.get("pricing", {})
    if (type(prompt) is not int or prompt < 0 or type(completion) is not int
            or completion < 0 or not isinstance(prices, dict)):
        raise ExtractionError("model_failure", "Groq usage was not reported")
    try:
        dollars = Decimal(prompt) * Decimal(str(prices["prompt"]))
        dollars += Decimal(completion) * Decimal(str(prices["completion"]))
    except (KeyError, ArithmeticError, ValueError):
        raise ExtractionError("model_failure", "Groq pricing was not reported") from None
    return int((dollars * Decimal(100_000_000)).to_integral_value(rounding=ROUND_CEILING))


class _HttpTransport:
    def request_json(
        self, method: str, url: str, *, headers: dict[str, str],
        body: dict[str, Any] | None = None, timeout: float,
    ) -> Any:
        try:
            response = request(
                method, url, headers=headers, body=body, timeout=timeout,
                max_bytes=MAX_RESPONSE_BYTES,
            )
        except TransportError:
            raise ExtractionError("provider_unavailable", "hosted request failed") from None
        if not 200 <= response.status_code < 300:
            raise ExtractionError(
                "provider_unavailable", f"hosted provider answered {response.status_code}"
            )
        try:
            return json.loads(response.content.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise ExtractionError("model_failure", "hosted response was unreadable") from error
