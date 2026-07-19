"""The six scored dimensions, their weights, and judge prompt builders.

Design (see RESEARCH.md): anchored pairwise comparison on narrow questions,
because holistic absolute scoring by LLM judges is known to over-rate machine
output on literary text (LitEval finding). Performability is computed, not
judged — see speakability.py.
"""

from __future__ import annotations

from .schema import Dimension, Segment

WEIGHTS: dict[Dimension, float] = {
    Dimension.VOICE: 0.25,
    Dimension.HUMOR: 0.25,
    Dimension.NAMES: 0.15,
    Dimension.CULTURE: 0.10,
    Dimension.PERFORMABILITY: 0.15,  # computed by speakability.py, not judged
    Dimension.FIDELITY: 0.10,
}

# Narrow, professional-translator-style questions (LiTransProQA shape).
JUDGE_QUESTIONS: dict[Dimension, str] = {
    Dimension.VOICE: (
        "Which translation better preserves the narrator's voice: grandiose, "
        "wheezing, overwrought audiobook bombast that keeps its momentum when read "
        "aloud? Penalize flat, neutral, 'translated-sounding' prose."
    ),
    Dimension.HUMOR: (
        "Which translation is funnier to a native speaker of the target language? "
        "A joke rebuilt to land in the target language beats a literal rendering "
        "of the English joke. Penalize humor that survives only if the reader "
        "back-translates to English."
    ),
    Dimension.NAMES: (
        "Which translation handles the invented names and epithets better? Good "
        "handling keeps them consistent with earlier segments, comically grandiose, "
        "and natural in the target language's sound system."
    ),
    Dimension.CULTURE: (
        "Which translation adapts cultural references better for a target-language "
        "audience? Adapted or substituted references beat preserved-but-opaque ones; "
        "explanatory glosses are a failure."
    ),
    Dimension.FIDELITY: (
        "Which translation still accurately narrates what is happening on screen? "
        "The comedy may transform freely, but the described events must match the "
        "scene."
    ),
}


def pairwise_prompt(
    segment: Segment,
    language: str,
    dimension: Dimension,
    text_a: str,
    text_b: str,
    gag_context: str = "",
) -> str:
    """Build the anchored pairwise judge prompt for one dimension."""
    if dimension == Dimension.PERFORMABILITY:
        raise ValueError("performability is computed, not judged")
    gag = f"\nRunning-gag context from earlier segments:\n{gag_context}\n" if gag_context else ""
    return (
        "You are judging two translations of a segment from a bombastic comedic "
        "film-narration performance (in the tradition of alternate-audio riff "
        f"tracks). Target language: {language}.\n\n"
        f"On screen during this segment: {segment.scene}\n"
        f"Time window when performed aloud: {segment.seconds:.0f} seconds\n{gag}\n"
        f"Original (English):\n{segment.text}\n\n"
        f"Translation A:\n{text_a}\n\n"
        f"Translation B:\n{text_b}\n\n"
        f"Question — {JUDGE_QUESTIONS[dimension]}\n\n"
        "Answer with a JSON object: {\"winner\": \"a\"|\"b\"|\"tie\", "
        "\"rationale\": \"<one or two sentences>\"}. Judge only the stated "
        "question, not overall quality."
    )


def no_self_judging(judge_system: str, *candidate_systems: str) -> bool:
    """A judge may not score output from its own provider family."""
    judge_family = judge_system.split("/")[0].lower()
    return all(judge_family != c.split("/")[0].lower() for c in candidate_systems)
