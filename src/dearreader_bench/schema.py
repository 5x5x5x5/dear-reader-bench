"""Data models: segments, joke cards, adaptation jobs, and judgments."""

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


class Mechanism(str, Enum):
    """GTVH-style comic mechanisms (Joke Card taxonomy, DESIGN.md §3)."""

    EXAGGERATION = "exaggeration"
    ANTICLIMAX = "anticlimax"
    PERSONIFICATION = "personification"
    LITERALIZATION = "literalization"
    REGISTER_CRASH = "register_crash"
    FALSE_PRECISION = "false_precision"
    PSEUDO_AUTHORITY = "pseudo_authority"
    CALLBACK = "callback"
    WORDPLAY = "wordplay"            # non-portable by definition
    CATEGORY_ERROR = "category_error"
    UNDERSTATEMENT = "understatement"
    ABSURD_SIMILE = "absurd_simile"
    OTHER = "other"                  # open-world escape: taxonomy gaps must not become scoring bugs


class JokeCard(BaseModel):
    """One-time annotation of a comic unit (substrate for Layer-2 instruments).

    Survival scoring is segment-scoped and compensation-aware: for
    portable=False jokes (puns), any functioning joke within the segment
    counts (Delabastita's substitution norms) — never locus-pinned.
    """

    joke_id: str
    segment_id: str
    setup_span: str
    punchline_span: str
    mechanism: Mechanism
    script_opposition: tuple[str, str] = Field(
        description="The two clashing scripts, e.g. ('NATURAL_DISASTER', 'AUNT')"
    )
    portable: bool = Field(description="Can the mechanism be rebuilt without language-specific material?")
    gag_id: str | None = None


class Bible(BaseModel):
    """The system's own key-names-and-phrases sheet, delivered with its translation."""

    names: dict[str, str] = Field(default_factory=dict, description="source epithet -> chosen rendering")
    gag_anchors: dict[str, str] = Field(default_factory=dict, description="gag_id -> anchor rendering")
    register_note: str = ""


class TranslatedSegment(BaseModel):
    segment_id: str
    text: str


class AdaptationResult(BaseModel):
    """The full-script adaptation job deliverable (DESIGN.md §1)."""

    system: str = Field(description="Model/system identifier, e.g. 'anthropic/claude-opus-4-8'")
    language: str = Field(description="Target language code, e.g. 'ja'")
    bible: Bible
    segments: list[TranslatedSegment]


# Back-compat alias for the earlier per-segment shape.
class Translation(BaseModel):
    segment_id: str
    system: str
    language: str
    text: str


class Dimension(str, Enum):
    """The four judged dimensions. Performability is measured, not judged."""

    VOICE = "voice"     # source-blind
    HUMOR = "humor"     # source-blind; absorbs culture until the corpus earns it back
    GAGS = "gags"       # source-aware: names/epithets/running gags
    FIDELITY = "fidelity"  # source-aware: scene + source events


class PairwiseJudgment(BaseModel):
    """An anchored pairwise verdict on one dimension for one segment."""

    segment_id: str
    language: str
    dimension: Dimension
    system_a: str
    system_b: str
    judge: str = Field(description="Judge model identifier")
    order: int = Field(default=0, description="Presentation order: 0 = (a,b), 1 = (b,a) shown swapped")
    winner: str = Field(description="'a', 'b', or 'tie'")
    rationale: str = ""


def load_segments(path: str | Path) -> list[Segment]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = [Segment.model_validate(item) for item in raw["segments"]]
    ids = [s.id for s in segments]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate segment ids in corpus")
    return segments
