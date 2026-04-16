#!/usr/bin/env python3
"""Shared PubMed / NCBI E-utilities client for PharmaGuide audit tooling."""

from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import requests

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401


DEFAULT_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_API_KEY = os.environ.get("NCBI_API_KEY") or os.environ.get("PUBMED_API_KEY", "")
DEFAULT_TOOL = os.environ.get("NCBI_TOOL") or os.environ.get("PUBMED_TOOL") or "pharmaguide-audit"
DEFAULT_EMAIL = os.environ.get("NCBI_EMAIL") or os.environ.get("PUBMED_EMAIL") or ""
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_RATE_LIMIT_DELAY = 0.12
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 14
MAX_RETRIES = 4
DEFAULT_FAILURE_LIMIT = 3  # circuit breaker threshold

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


@dataclass
class PubMedConfig:
    api_key: str = DEFAULT_API_KEY
    tool: str = DEFAULT_TOOL
    email: str = DEFAULT_EMAIL
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY
    cache_path: Path | None = None
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS


def load_pubmed_config(env: Mapping[str, str] | None = None) -> PubMedConfig:
    source = env or os.environ
    cache_env = source.get("PUBMED_CACHE_FILE") or source.get("NCBI_CACHE_FILE")
    cache_path = Path(cache_env) if cache_env else None
    return PubMedConfig(
        api_key=source.get("NCBI_API_KEY") or source.get("PUBMED_API_KEY", ""),
        tool=source.get("NCBI_TOOL") or source.get("PUBMED_TOOL") or "pharmaguide-audit",
        email=source.get("NCBI_EMAIL") or source.get("PUBMED_EMAIL") or "",
        cache_path=cache_path,
    )


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def _parse_pub_date(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    year = _clean_text(node.findtext("Year"))
    month = _clean_text(node.findtext("Month"))
    day = _clean_text(node.findtext("Day"))
    medline = _clean_text(node.findtext("MedlineDate"))

    if year:
        month_value = MONTH_MAP.get(month[:3].lower(), month.zfill(2) if month.isdigit() else "01")
        day_value = day.zfill(2) if day.isdigit() else "01"
        return f"{year}-{month_value}-{day_value}"
    if medline:
        return medline
    return None


def parse_pubmed_article_xml(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    articles: list[dict[str, Any]] = []

    for article in root.findall(".//PubmedArticle"):
        pmid = _clean_text(article.findtext(".//MedlineCitation/PMID")) or _clean_text(
            article.findtext(".//ArticleId[@IdType='pubmed']")
        )
        doi = _clean_text(article.findtext(".//ArticleId[@IdType='doi']")) or _clean_text(
            article.findtext(".//ELocationID[@EIdType='doi']")
        )
        publication_types = [
            _clean_text(node.text) for node in article.findall(".//PublicationType") if _clean_text(node.text)
        ]
        mesh_terms = [
            _clean_text(node.text) for node in article.findall(".//MeshHeading/DescriptorName") if _clean_text(node.text)
        ]
        supplementary_terms = [
            _clean_text(node.text) for node in article.findall(".//SupplMeshName") if _clean_text(node.text)
        ]
        correction_refs = [
            ref.get("RefType", "") for ref in article.findall(".//CommentsCorrections")
        ]

        parsed = {
            "pmid": pmid,
            "doi": doi or None,
            "title": _clean_text(article.findtext(".//ArticleTitle")),
            "abstract": " ".join(
                _clean_text(node.text) for node in article.findall(".//Abstract/AbstractText") if _clean_text(node.text)
            ),
            "journal": _clean_text(article.findtext(".//Journal/Title")),
            "published_date": _parse_pub_date(article.find(".//JournalIssue/PubDate")),
            "publication_types": publication_types,
            "mesh_terms": mesh_terms,
            "supplementary_concepts": supplementary_terms,
            "retracted": any("retract" in value.lower() for value in publication_types),
            "has_erratum": any("erratum" in value.lower() for value in correction_refs + publication_types),
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
        }
        articles.append(parsed)

    return articles


def parse_ecitmatch_rows(payload: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 7:
            continue
        rows.append(
            {
                "journal_title": parts[0],
                "year": parts[1],
                "volume": parts[2],
                "first_page": parts[3],
                "author_name": parts[4],
                "local_key": parts[5],
                "pmid": parts[6],
            }
        )
    return rows


class PubMedClient:
    """Thin NCBI E-utilities client with retry, rate limit, circuit breaker, and optional disk cache."""

    def __init__(
        self,
        config: PubMedConfig | None = None,
        *,
        api_key: str | None = None,
        tool: str | None = None,
        email: str | None = None,
        cache_path: Path | None = None,
        timeout_seconds: float | None = None,
        rate_limit_delay: float | None = None,
        cache_ttl_seconds: int | None = None,
        failure_limit: int | None = None,
    ) -> None:
        cfg = config or load_pubmed_config()
        self.config = PubMedConfig(
            api_key=api_key if api_key is not None else cfg.api_key,
            tool=tool if tool is not None else cfg.tool,
            email=email if email is not None else cfg.email,
            base_url=cfg.base_url,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds,
            rate_limit_delay=rate_limit_delay if rate_limit_delay is not None else cfg.rate_limit_delay,
            cache_path=cache_path if cache_path is not None else cfg.cache_path,
            cache_ttl_seconds=cache_ttl_seconds if cache_ttl_seconds is not None else cfg.cache_ttl_seconds,
        )
        self._last_request_at = 0.0
        self._consecutive_failures = 0
        self._failure_limit = failure_limit if failure_limit is not None else DEFAULT_FAILURE_LIMIT
        self.circuit_open = False
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        path = self.config.cache_path
        if not path or not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _persist_cache(self) -> None:
        path = self.config.cache_path
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._cache, indent=2, ensure_ascii=True))

    def _cache_get(self, key: str) -> Any | None:
        record = self._cache.get(key)
        if not isinstance(record, dict):
            return None
        expires_at = record.get("expires_at")
        if isinstance(expires_at, (int, float)) and expires_at < time.time():
            return None
        return record.get("payload")

    def _cache_put(self, key: str, payload: Any) -> None:
        self._cache[key] = {
            "stored_at": time.time(),
            "expires_at": time.time() + self.config.cache_ttl_seconds,
            "payload": payload,
        }
        self._persist_cache()

    def _sleep_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)

    def _request(self, endpoint: str, *, params: dict[str, Any] | None = None, method: str = "GET") -> Any:
        if self.circuit_open:
            raise RuntimeError(
                f"PubMed circuit breaker open after {self._failure_limit} consecutive failures. "
                "Check network connectivity or NCBI service status."
            )

        params = dict(params or {})
        params.setdefault("db", "pubmed")
        if self.config.api_key:
            params.setdefault("api_key", self.config.api_key)
        if self.config.tool:
            params.setdefault("tool", self.config.tool)
        if self.config.email:
            params.setdefault("email", self.config.email)

        cache_key = json.dumps({"endpoint": endpoint, "method": method, "params": params}, sort_keys=True)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = f"{self.config.base_url.rstrip('/')}/{endpoint}"
        response = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._sleep_for_rate_limit()
            try:
                response = requests.request(method, url, params=params, timeout=self.config.timeout_seconds)
                self._last_request_at = time.time()
            except (requests.ConnectionError, requests.Timeout, OSError) as exc:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_limit:
                    self.circuit_open = True
                    raise RuntimeError(
                        f"PubMed circuit breaker tripped: {self._consecutive_failures} consecutive failures"
                    ) from exc
                time.sleep(min(2 ** attempt, 8))
                continue

            if response.status_code != 429:
                self._consecutive_failures = 0
                break
            time.sleep(min(2 ** attempt, 8))

        if response is None:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_limit:
                self.circuit_open = True
            raise RuntimeError("PubMed request did not return a response")

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "json" in content_type or params.get("retmode") == "json":
            payload = response.json()
        else:
            payload = response.text
        self._cache_put(cache_key, payload)
        return payload

    def esearch(self, term: str, **params: Any) -> dict[str, Any]:
        merged = {"term": term, "retmode": "json"}
        merged.update(params)
        return self._request("esearch.fcgi", params=merged)

    def esummary(self, ids: list[str] | str, **params: Any) -> dict[str, Any]:
        merged = {"id": ",".join(ids) if isinstance(ids, list) else ids, "retmode": "json"}
        merged.update(params)
        return self._request("esummary.fcgi", params=merged)

    def efetch(self, ids: list[str] | str, **params: Any) -> str:
        merged = {"id": ",".join(ids) if isinstance(ids, list) else ids, "retmode": "xml"}
        merged.update(params)
        return self._request("efetch.fcgi", params=merged)

    def elink(self, ids: list[str] | str, **params: Any) -> str:
        merged = {"id": ",".join(ids) if isinstance(ids, list) else ids, "retmode": "xml"}
        merged.update(params)
        return self._request("elink.fcgi", params=merged)

    def epost(self, ids: list[str], **params: Any) -> str:
        merged = {"id": ",".join(ids), "retmode": "xml"}
        merged.update(params)
        return self._request("epost.fcgi", params=merged, method="POST")

    def ecitmatch(self, bdata: str, **params: Any) -> str:
        merged = {"retmode": "xml", "bdata": bdata}
        merged.update(params)
        return self._request("ecitmatch.cgi", params=merged)


__all__ = [
    "DEFAULT_API_KEY",
    "DEFAULT_EMAIL",
    "DEFAULT_TOOL",
    "PubMedClient",
    "PubMedConfig",
    "load_pubmed_config",
    "parse_ecitmatch_rows",
    "parse_pubmed_article_xml",
]
