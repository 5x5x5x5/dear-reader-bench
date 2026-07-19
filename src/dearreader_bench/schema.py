"""Data models for segments, translations, and judgments."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Feature(str, Enum):
    """Comedy/translation phenomena a segment exercises (scores break out by these)."""

    EPITHET = "epithet"              # invented character names/titles
    RUNNING_GAG = "running_gag"      # callback that must stay consistent across segments
    PUN = "pun"                      # wordplay that must be rebuilt, not carried
    REGISTER_SHIFT = "register_shift"  # bombast crashing into the mundane (or back)
    POP_CULTURE = "pop_culture"      # reference that may need cultural adaptation
    ASIDE = "aside"                  # narrator breaks off / addresses the listener


class Segment(BaseModel):
    """One timed unit of narration from the source performance."""

    id: str
    seconds: float = Field(gt=0, description="Time window available when performed aloud")
    text: str = Field(description="Source narration (English)")
    scene: str = Field(description="What is on screen — used to judge scene fidelity")
    features: list[Feature] = Field(default_factory=list)
    gag_id: str | None = Field(
        default=None, description="Shared key linking segments of one running gag"
    )


class Translation(BaseModel):
    """One system's translation of one segment."""

    segment_id: str
    system: str = Field(description="Model/system identifier, e.g. 'anthropic/claude-opus-4-8'")
    language: str = Field(description="Target language code, e.g. 'ja'")
    text: str


class Dimension(str, Enum):
    VOICE = "voice"
    HUMOR = "humor"
    NAMES = "names"
    CULTURE = "culture"
    PERFORMABILITY = "performability"
    FIDELITY = "fidelity"


class PairwiseJudgment(BaseModel):
    """An anchored pairwise verdict on one dimension for one segment."""

    segment_id: str
    language: str
    dimension: Dimension
    system_a: str
    system_b: str
    judge: str = Field(description="Judge model identifier")
    winner: str = Field(description="'a', 'b', or 'tie'")
    rationale: str = ""


def load_segments(path: str | Path) -> list[Segment]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = [Segment.model_validate(item) for item in raw["segments"]]
    ids = [s.id for s in segments]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate segment ids in corpus")
    return segments
