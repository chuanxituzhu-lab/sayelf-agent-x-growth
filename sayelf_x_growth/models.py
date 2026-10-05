from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass
class Signal:
    id: str
    kind: str
    text: str
    evidence_ids: list[str]
    classification: str = 'Unknown'
    origin: str = 'manual'
    trend: bool = False
    claims: list[dict] = field(default_factory=list)
    original_work: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Opportunity:
    id: str
    signal_id: str
    decision: str
    reason: str


@dataclass
class Draft:
    id: str
    signal_id: str
    account: str
    day: str
    kind: str
    text: str
    claims: list[dict]
    evidence_ids: list[str]
    classification: str
    scores: dict
    review: dict
    trend: bool = False
    revision: int = 1
    state: str = 'PREPARED'
    variant: str = 'NARRATIVE'
    matched_trends: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    id: str
    path: str
    sha256: str
    excerpt: str
    classification: str
    verified_by: str


@dataclass
class Publication:
    id: str
    draft_id: str
    state: str
    content_digest: str
    published_at: str | None = None
    post_id: str | None = None


@dataclass
class Observation:
    id: str
    publication_id: str
    window_hours: int
    metrics: dict
    source: str
    observed_at: str
    epistemic: str = 'Observation'


@dataclass
class Learning:
    id: str
    publication_id: str
    mechanism: str
    evidence_ids: list[str]
    epistemic: str = 'Hypothesis'
    status: str = 'UNVALIDATED'


class PlatformIntelligence(Protocol):
    """Interface only; no collector, rules engine, monitoring or network implementation."""
    def context(self, platform: str, as_of: str) -> dict: ...


class Composer(Protocol):
    def compose(self, signal: Signal, variant: str = 'NARRATIVE') -> str: ...
