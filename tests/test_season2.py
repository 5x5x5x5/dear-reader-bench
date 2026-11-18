"""Season 2: the corpus meets the DESIGN.md §7 blueprint, and submissions are checked."""

import json
from collections import Counter
from pathlib import Path

import pytest

from dearreader_bench.brief import adaptation_prompt
from dearreader_bench.runner import submission_path
from dearreader_bench.schema import (
    AdaptationResult,
    Bible,
    Feature,
    JokeCard,
    Mechanism,
    TranslatedSegment,
    load_corpus,
)
from dearreader_bench.speakability import fill_ratio
from dearreader_bench.submission import (
    LANGUAGES,
    check_submission,
    main,
    performability,
)

ROOT = Path(__file__).parent.parent
CORPUS = load_corpus(ROOT / "data" / "season2.json")
CARDS = [
    JokeCard.model_validate(c)
    for c in json.loads(
        (ROOT / "data" / "season2_cards.json").read_text(encoding="utf-8")
    )["cards"]
]
TEXT = {s.id: s.text for s in CORPUS.segments}
GUID = CORPUS.canary.rsplit(":", 1)[-1]


def test_blueprint_quotas():
    segments = CORPUS.segments
    assert len(segments) >= 48
    per_feature = Counter(f for s in segments for f in s.features)
    for feature in Feature:
        assert per_feature[feature] >= 8, feature
    chains = Counter(s.gag_id for s in segments if s.gag_id)
    assert len(chains) >= 10
    assert all(n >= 3 for n in chains.values()), chains
    assert set(chains) == set(CORPUS.gags)


def test_bible_keys_are_grounded_in_the_text():
    everything = " ".join(TEXT.values())
    for name in CORPUS.names:
        assert name in everything, name
    for gag_id, anchor in CORPUS.gags.items():
        chain = [s.text for s in CORPUS.segments if s.gag_id == gag_id]
        assert any(anchor in text for text in chain), gag_id


def test_source_fits_its_own_windows():
    for s in CORPUS.segments:
        assert 0.5 <= fill_ratio(s.text, "en", s.seconds) <= 1.10, s.id


def test_joke_cards_cover_the_corpus():
    assert len({c.joke_id for c in CARDS}) == len(CARDS)
    for card in CARDS:
        text = TEXT[card.segment_id]
        assert card.setup_span in text and card.punchline_span in text, card.joke_id
        assert card.gag_id is None or card.gag_id in CORPUS.gags, card.joke_id
        assert (card.mechanism is Mechanism.WORDPLAY) <= (not card.portable), (
            card.joke_id
        )
    assert {c.segment_id for c in CARDS} == set(TEXT)
    puns = {c.segment_id for c in CARDS if c.mechanism is Mechanism.WORDPLAY}
    assert puns == {s.id for s in CORPUS.segments if Feature.PUN in s.features}


def _submission(**changes) -> AdaptationResult:
    base = AdaptationResult(
        system="acme/model-1",
        language="fr",
        bible=Bible(
            names={n: n for n in CORPUS.names},
            gag_anchors=dict(CORPUS.gags),
            register_note="x",
        ),
        segments=[
            TranslatedSegment(segment_id=s.id, text=s.text) for s in CORPUS.segments
        ],
    )
    return base.model_copy(update=changes)


def test_complete_submission_is_accepted():
    result = _submission()
    assert check_submission(result, CORPUS) == []
    p, forfeits = performability(result, CORPUS)
    assert p == 1.0 and forfeits == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"language": "xx"}, "slate"),
        ({"system": "model-1"}, "family/model"),
        ({"segments": _submission().segments[1:]}, "missing ['s2-001']"),
        (
            {"segments": _submission().segments + _submission().segments[:1]},
            "duplicate",
        ),
        (
            {"segments": [TranslatedSegment(segment_id=i, text=" ") for i in TEXT]},
            "empty text",
        ),
        ({"bible": Bible(names={n: n for n in CORPUS.names})}, "gag_anchors"),
        ({"bible": Bible(gag_anchors=dict(CORPUS.gags))}, "names"),
        (
            {"bible": _submission().bible.model_copy(update={"register_note": GUID})},
            "canary",
        ),
    ],
)
def test_broken_submissions_are_rejected(changes, expected):
    problems = check_submission(_submission(**changes), CORPUS)
    assert any(expected in p for p in problems), problems


def test_overlong_segments_cost_performability():
    padded = [TranslatedSegment(segment_id=i, text=t * 3) for i, t in TEXT.items()]
    p, forfeits = performability(_submission(segments=padded), CORPUS)
    assert p == 0.0 and len(forfeits) == len(TEXT)


def test_prompt_carries_the_script_but_not_the_canary():
    prompt = adaptation_prompt(CORPUS, "ja")
    assert GUID not in prompt
    assert all(s.id in prompt for s in CORPUS.segments)
    assert all(gag_id in prompt for gag_id in CORPUS.gags)
    assert "Counter of Heads" in prompt


def test_slate_is_six_languages():
    assert len(set(LANGUAGES)) == 6


@pytest.mark.parametrize(
    "path", sorted((ROOT / "submissions").glob("*/*.json")), ids=str
)
def test_committed_submissions_pass(path):
    assert main(["check", str(path)]) == 0
    result = AdaptationResult.model_validate_json(path.read_text(encoding="utf-8"))
    # The path is the roster key, so it must agree with what the file says.
    assert path == submission_path(path.parents[1], result.system, result.language)
