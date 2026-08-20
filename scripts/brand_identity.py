#!/usr/bin/env python3
"""Exact catalog brand display projection with immutable source identity."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def normalize_brand_key(value: Any) -> str:
    """Normalize case and whitespace only; never guess by substring."""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def _display_fallback(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split())


@dataclass(frozen=True)
class BrandIdentity:
    source_brand: str
    display_brand: str
    family: str
    product_line: str | None
    matched: bool


@dataclass(frozen=True)
class WaveBrand:
    query_brand: str
    folder: str
    expected_live_labels: int


class BrandRegistry:
    """Reviewed exact-alias registry used only for consumer display identity."""

    def __init__(
        self,
        aliases: dict[str, tuple[str, str, str | None]],
        wave_1: tuple[WaveBrand, ...],
    ) -> None:
        self._aliases = aliases
        self.wave_1 = wave_1

    @classmethod
    def load(cls, path: str | Path) -> "BrandRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BrandRegistry":
        metadata = payload.get("_metadata") or {}
        if metadata.get("schema_version") != "1.0.0":
            raise ValueError("catalog brand registry schema_version must be 1.0.0")

        aliases: dict[str, tuple[str, str, str | None]] = {}
        for brand in payload.get("brands", []):
            display_name = str(brand.get("display_name") or "").strip()
            family = str(brand.get("family") or display_name).strip()
            if not display_name:
                raise ValueError("catalog brand registry entry is missing display_name")
            for alias in brand.get("aliases", []):
                alias_name = str(alias.get("name") or "")
                key = normalize_brand_key(alias_name)
                if not key:
                    raise ValueError(f"empty alias for {display_name}")
                if key in aliases:
                    raise ValueError(f"brand alias collision after normalization: {alias_name!r}")
                product_line = alias.get("product_line")
                aliases[key] = (
                    display_name,
                    family,
                    str(product_line).strip() if product_line else None,
                )

        wave_1 = tuple(
            WaveBrand(
                query_brand=str(item["query_brand"]),
                folder=str(item["folder"]),
                expected_live_labels=int(item["expected_live_labels"]),
            )
            for item in payload.get("wave_1", [])
        )
        return cls(aliases, wave_1)

    def resolve(self, raw_brand: Any) -> BrandIdentity:
        source_brand = str(raw_brand or "")
        match = self._aliases.get(normalize_brand_key(source_brand))
        if match is None:
            fallback = _display_fallback(source_brand)
            return BrandIdentity(
                source_brand=source_brand,
                display_brand=fallback,
                family=fallback,
                product_line=None,
                matched=False,
            )
        display_brand, family, product_line = match
        return BrandIdentity(
            source_brand=source_brand,
            display_brand=display_brand,
            family=family,
            product_line=product_line,
            matched=True,
        )


__all__ = [
    "BrandIdentity",
    "BrandRegistry",
    "WaveBrand",
    "normalize_brand_key",
]
