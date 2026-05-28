from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IdentityResult:
    canonical_name: str
    canonical_id: Optional[str] = None
    source_db: Optional[str] = None
    match_method: Optional[str] = None
    mapped: bool = False
    confidence: str = "low"

