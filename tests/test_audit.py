"""Tests for gag-bible context, provider snapshot capture, and the audit panel."""

from __future__ import annotations

import json
from pathlib import Path

from dearreader_bench import audit, judge
from dearreader_bench.rubric import build_gag_context, pairwise_prompt
from dearreader_bench.schema import (
    AdaptationResult,
    Bible,
    Dimension,
    PairwiseJudgment,
    TranslatedSegment,
    load_corpus,
)

ROOT = Path(__file__).parent.parent
CORPUS = load_corpus(ROOT / "data" / "season2.json")


def _make_result(system: str, tag: str, language: str = "fr") -> AdaptationResult:
    return AdaptationResult(
        system=system,
        language=language,
        bible=Bible(
            names={n: f"{tag}:{n}" for n in CORPUS.names},
            gag_anchors={g: f"{tag}:{v}" for g, v in CORPUS.gags.items()},
            register_note=tag,
        ),
        segments=[
            TranslatedSegment(segment_id=s.id, text=f"{tag} {s.text}")
            for s in CORPUS.segments
        ],
    )


# --- gag-bible context in GAGS judging --------------------------------------


def test_build_gag_context_includes_bible_and_prior_arc_without_system_ids():
    first = _make_result("alpha/secret-model", "ALPHA")
    second = _make_result("beta/other-model", "BETA")
    # s2-003 is the second segment in 'the-funicular' chain (s2-001 came first).
    seg = next(s for s in CORPUS.segments if s.id == "s2-003")
    ctx = build_gag_context(seg, CORPUS, first, second)

    assert "the-funicular" in ctx
    assert 'Text A bible = "ALPHA:eleven minutes"' in ctx
    assert 'Text B bible = "BETA:eleven minutes"' in ctx
    assert "[s2-001]" in ctx
    assert "ALPHA " in ctx and "BETA " in ctx
    # System identifiers must never leak into judge prompts.
    assert "alpha/secret-model" not in ctx
    assert "beta/other-model" not in ctx

    # Swapping presentation order swaps Text A and Text B in context too.
    swapped = build_gag_context(seg, CORPUS, second, first)
    assert 'Text A bible = "BETA:eleven minutes"' in swapped
    assert 'Text B bible = "ALPHA:eleven minutes"' in swapped


def test_build_gag_context_includes_declared_names_in_segment():
    first = _make_result("alpha/m1", "ALPHA")
    second = _make_result("beta/m2", "BETA")
    seg = CORPUS.segments[0]  # s2-001 mentions Odalys the Enumerator & Counter of Heads
    ctx = build_gag_context(seg, CORPUS, first, second)
    assert "Odalys the Enumerator" in ctx
    assert 'Text A = "ALPHA:Odalys the Enumerator"' in ctx
    assert 'Text B = "BETA:Odalys the Enumerator"' in ctx


def test_source_blind_prompt_ignores_gag_context():
    seg = CORPUS.segments[0]
    blind = pairwise_prompt(
        seg, "French", Dimension.HUMOR, "A", "B", gag_context="SECRET_SOURCE_HINT"
    )
    assert "SECRET_SOURCE_HINT" not in blind
    aware = pairwise_prompt(
        seg, "French", Dimension.GAGS, "A", "B", gag_context="BIBLE_HINT"
    )
    assert "BIBLE_HINT" in aware


def test_judge_passes_gag_context_only_for_gags_and_records_served_model(
    tmp_path, monkeypatch
):
    first = _make_result("alpha/m1", "ALPHA")
    second = _make_result("beta/m2", "BETA")
    roster = {first.system: first, second.system: second}
    seg = next(s for s in CORPUS.segments if s.id == "s2-003")
    seen_prompts: dict[Dimension, str] = {}

    def fake_complete(model, prompt, **kwargs):
        if kwargs.get("meta") is not None:
            kwargs["meta"]["served_model"] = f"{model}@2026-11-22"
        seen_prompts[current_dim[0]] = prompt
        return json.dumps({"winner": "a", "rationale": "ok"})

    monkeypatch.setattr(judge, "complete", fake_complete)
    cache = tmp_path / "cache"
    cache.mkdir()
    served: dict[str, set[str]] = {}
    current_dim = [Dimension.GAGS]
    for dim in (Dimension.GAGS, Dimension.HUMOR, Dimension.FIDELITY):
        current_dim[0] = dim
        judge._judge_once(
            (seg, dim, first.system, second.system, 0, "gamma/j1"),
            roster,
            CORPUS,
            cache,
            served_models=served,
        )

    assert 'Text A bible = "ALPHA:eleven minutes"' in seen_prompts[Dimension.GAGS]
    assert "[s2-001]" in seen_prompts[Dimension.GAGS]
    assert "ALPHA:eleven minutes" not in seen_prompts[Dimension.HUMOR]
    assert "ALPHA:eleven minutes" not in seen_prompts[Dimension.FIDELITY]
    assert served == {"gamma/j1": {"gamma/j1@2026-11-22"}}

    # Cache hit preserves served_model even without calling complete().
    def refuse(*a, **k):
        raise AssertionError("should have hit cache")

    monkeypatch.setattr(judge, "complete", refuse)
    served_from_cache: dict[str, set[str]] = {}
    judge._judge_once(
        (seg, Dimension.GAGS, first.system, second.system, 0, "gamma/j1"),
        roster,
        CORPUS,
        tmp_path / "cache",
        served_models=served_from_cache,
    )
    assert served_from_cache == {"gamma/j1": {"gamma/j1@2026-11-22"}}


# --- reliability & audit metrics --------------------------------------------


def _judgment(seg: str, dim: Dimension, a: str, b: str, j: str, order: int, w: str):
    return PairwiseJudgment(
        segment_id=seg,
        language="fr",
        dimension=dim,
        system_a=a,
        system_b=b,
        judge=j,
        order=order,
        winner=w,
    )


def test_position_swap_consistency_and_first_position_bias():
    judgments = [
        # j/consistent always picks 'a' regardless of presentation order -> 100% agree, 0 bias
        _judgment("s2-001", Dimension.HUMOR, "x/1", "y/1", "j/consistent", 0, "a"),
        _judgment("s2-001", Dimension.HUMOR, "x/1", "y/1", "j/consistent", 1, "a"),
        # j/first-biased picks shown-A in order 0 ('a') and shown-A in order 1 ('b')
        _judgment("s2-001", Dimension.HUMOR, "x/1", "y/1", "j/first-biased", 0, "a"),
        _judgment("s2-001", Dimension.HUMOR, "x/1", "y/1", "j/first-biased", 1, "b"),
    ]
    stats = audit.position_swap_consistency(judgments)
    assert stats["j/consistent"]["agreement"] == 1.0
    assert stats["j/consistent"]["first_position_bias"] == 0.0
    assert stats["j/first-biased"]["agreement"] == 0.0
    assert stats["j/first-biased"]["first_position_bias"] == 1.0


def test_krippendorff_alpha_perfect_vs_disagreement():
    perfect = [
        ("s2-001", "humor", "x/1", "y/1", "j/1", "a"),
        ("s2-001", "humor", "x/1", "y/1", "j/2", "a"),
        ("s2-002", "humor", "x/1", "y/1", "j/1", "b"),
        ("s2-002", "humor", "x/1", "y/1", "j/2", "b"),
        ("s2-003", "humor", "x/1", "y/1", "j/1", "tie"),
        ("s2-003", "humor", "x/1", "y/1", "j/2", "tie"),
    ]
    res_p = audit.krippendorff_by_dimension(perfect)["humor"]
    assert res_p["alpha"] == 1.0
    assert res_p["alpha_nominal"] == 1.0
    assert res_p["tentative"] is False

    opposed = [
        ("s2-001", "voice", "x/1", "y/1", "j/1", "a"),
        ("s2-001", "voice", "x/1", "y/1", "j/2", "b"),
        ("s2-002", "voice", "x/1", "y/1", "j/1", "b"),
        ("s2-002", "voice", "x/1", "y/1", "j/2", "a"),
    ]
    res_o = audit.krippendorff_by_dimension(opposed)["voice"]
    assert res_o["alpha"] is not None and res_o["alpha"] < 0.0
    assert res_o["tentative"] is True


def test_judge_deviation_heatmap_detects_biased_judge():
    # j/1 and j/2 agree that x/1 beats y/1; j/biased gives y/1 the win.
    folded = [
        ("s2-001", "humor", "x/1", "y/1", "j/1", "a"),
        ("s2-001", "humor", "x/1", "y/1", "j/2", "a"),
        ("s2-001", "humor", "x/1", "y/1", "j/biased", "b"),
    ]
    heat = audit.judge_deviation_heatmap(folded)
    assert heat["j/biased"]["y/1"] > 0.5
    assert heat["j/biased"]["x/1"] < -0.5
    assert abs(sum(heat[j]["x/1"] for j in heat)) < 1e-9


def test_dirichlet_weight_audit_separates_invariant_and_sensitive_pairs():
    phi = {
        "humor": {"dominant": 0.9, "humor_specialist": 0.8, "voice_specialist": 0.3},
        "voice": {"dominant": 0.9, "humor_specialist": 0.3, "voice_specialist": 0.8},
        "gags": {"dominant": 0.9, "humor_specialist": 0.5, "voice_specialist": 0.5},
        "fidelity": {"dominant": 0.9, "humor_specialist": 0.5, "voice_specialist": 0.5},
    }
    p = {s: 1.0 for s in phi["humor"]}
    res = audit.dirichlet_weight_audit(phi, p, draws=500, seed=42)
    assert res["total_pairs"] == 3
    # dominant always beats both specialists; the two specialists flip depending on weights.
    sensitive_pairs = {
        (sp["system_a"], sp["system_b"]) for sp in res["sensitive_pairs"]
    }
    assert ("humor_specialist", "voice_specialist") in sensitive_pairs
    assert res["invariant_pairs"] == 2


def test_anchor_and_known_groups_validity_checks():
    roster = {
        s: _make_result(s, s)
        for s in (
            "a/good",
            "b/pinned",
            "b/pinned+literal",
            "b/pinned+rewrite",
        )
    }
    valid_phi = {
        "humor": {
            "a/good": 0.70,
            "b/pinned": 0.55,
            "b/pinned+literal": 0.25,
            "b/pinned+rewrite": 0.60,
        },
        "voice": {
            "a/good": 0.65,
            "b/pinned": 0.50,
            "b/pinned+literal": 0.40,
            "b/pinned+rewrite": 0.55,
        },
        "gags": {
            "a/good": 0.70,
            "b/pinned": 0.60,
            "b/pinned+literal": 0.55,
            "b/pinned+rewrite": 0.05,
        },
        "fidelity": {
            "a/good": 0.70,
            "b/pinned": 0.60,
            "b/pinned+literal": 0.65,
            "b/pinned+rewrite": 0.05,
        },
    }
    ok = audit.check_anchors_and_validity(roster, valid_phi, pinned_anchor="b/pinned")
    assert ok["status"] == "valid_automated"
    assert ok["failures"] == [] and ok["missing_anchors"] == []

    # Without specifying pinned_anchor -> incomplete (not invalid).
    inc = audit.check_anchors_and_validity(roster, valid_phi)
    assert inc["status"] == "incomplete"

    # If +literal wins humor or +rewrite survives tethering -> invalid.
    broken_phi = {
        **valid_phi,
        "humor": {**valid_phi["humor"], "b/pinned+literal": 0.90},
        "gags": {**valid_phi["gags"], "b/pinned+rewrite": 0.80},
        "fidelity": {**valid_phi["fidelity"], "b/pinned+rewrite": 0.80},
    }
    bad = audit.check_anchors_and_validity(roster, broken_phi, pinned_anchor="b/pinned")
    assert bad["status"] == "invalid"
    assert len(bad["failures"]) >= 2
