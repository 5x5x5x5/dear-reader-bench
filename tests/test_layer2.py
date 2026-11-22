"""Tests for Layer-2 behavioral instruments, autopsies, convergence, and lesion battery."""

from __future__ import annotations

import json
from pathlib import Path

from dearreader_bench import layer2, lesions
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
CARDS = layer2.load_joke_cards(ROOT / "data" / "season2_cards.json")


def _clean_submission(
    system: str = "acme/model-1", language: str = "fr"
) -> AdaptationResult:
    name_map = {n: f"Epithete{i}Alpha" for i, n in enumerate(CORPUS.names)}
    gag_map = {g: f"Ancre{i}Beta" for i, g in enumerate(CORPUS.gags)}
    return AdaptationResult(
        system=system,
        language=language,
        bible=Bible(
            names=name_map,
            gag_anchors=gag_map,
            register_note="bombastic",
        ),
        segments=[
            TranslatedSegment(
                segment_id=s.id,
                text=(
                    s.text
                    + " "
                    + " ".join(
                        name_map[n] for n in CORPUS.names if n.lower() in s.text.lower()
                    )
                    + (
                        f" {gag_map[s.gag_id]}"
                        if s.gag_id and CORPUS.gags[s.gag_id].lower() in s.text.lower()
                        else ""
                    )
                ),
            )
            for s in CORPUS.segments
        ],
    )


# --- Gag Ledger -------------------------------------------------------------


def test_gag_ledger_exact_and_inflected_matching():
    # Japanese possessive prefix stripping (real case from claude-sonnet-5.5 s2-035).
    assert (
        layer2._match_anchor("わたくしの主治医", "主治医はハラハラするなと申した", "ja")
        == "inflected"
    )
    assert layer2._match_anchor("神器", "彼女が「神器」と呼ぶ", "ja") == "exact"
    assert layer2._match_anchor("神器", "ただの板です", "ja") == "missing"

    # Space-delimited stem-prefix inflection tolerance (German/French case endings).
    assert (
        layer2._match_anchor("der Gebügelte", "dem Gebügelten Mann", "de")
        == "inflected"
    )
    assert (
        layer2._match_anchor("eleven minutes", "totally unrelated text", "fr")
        == "missing"
    )


def test_gag_ledger_detects_vacuous_and_untranslated_entries():
    sub = _clean_submission(language="ja")
    # Force an untranslated English entry and a collision between distinct keys.
    bad_bible = sub.bible.model_copy(
        update={
            "names": {
                **sub.bible.names,
                "Counter of Heads": "Counter of Heads",
                "the Great Shrug": sub.bible.names["Odalys the Enumerator"],
            }
        }
    )
    ledger = layer2.gag_ledger_deterministic(
        sub.model_copy(update={"bible": bad_bible}), CORPUS
    )
    assert any("untranslated verbatim" in v for v in ledger["vacuous_entries"])
    assert any("collides with" in v for v in ledger["vacuous_entries"])


def test_gag_correspondence_double_extraction_and_agreement(tmp_path):
    roster = {"acme/m1": _clean_submission("acme/m1")}
    res = layer2.run_gag_correspondence(
        roster,
        CORPUS,
        extractors=["mock-a/ext", "mock-b/ext"],
        cache=tmp_path / "cache",
        workers=4,
    )
    assert res["inter_extractor_agreement"] == 1.0
    assert res["source_correspondence_by_system"]["acme/m1"] == 1.0


# --- Detection Asymmetry & Payoff Lift --------------------------------------


def test_detection_asymmetry_prompt_blind_hides_source():
    seg = CORPUS.segments[0]
    blind = layer2.blind_detection_prompt(seg, "French", "Une traduction.")
    assert seg.text not in blind
    assert seg.scene in blind
    assert "untrusted" in blind


def test_detection_asymmetry_distinguishes_clean_vs_explained_lesion(tmp_path):
    clean = _clean_submission("acme/clean")
    explained = lesions.apply_lesion(clean, CORPUS, "explain_joke").model_copy(
        update={"system": "beta/explained"}
    )
    roster = {clean.system: clean, explained.system: explained}
    # Use a small slice of cards to keep the test snappy.
    few_cards = CARDS[:6]
    det = layer2.run_detection_asymmetry(
        roster,
        CORPUS,
        few_cards,
        probes=["mock-p/probe"],
        cache=tmp_path / "cache",
        workers=4,
    )
    assert det["by_system"]["acme/clean"]["survival_rate"] == 1.0
    assert det["by_system"]["beta/explained"]["explained_rate"] == 1.0
    assert det["by_system"]["beta/explained"]["survival_rate"] == 0.0


def test_payoff_lift_runs_and_computes_within_judge_lift(tmp_path):
    a = _clean_submission("acme/long")
    b = lesions.apply_lesion(a, CORPUS, "truncate").model_copy(
        update={"system": "beta/short"}
    )
    roster = {a.system: a, b.system: b}
    # Supply standalone judgments where beta/short won, so context (where mock prefers longer) yields positive lift for acme/long.
    payoff_ids = [seg.id for _, seg, _ in layer2.payoff_chains(CORPUS)]
    standalone = [
        PairwiseJudgment(
            segment_id=sid,
            language="fr",
            dimension=Dimension.HUMOR,
            system_a="acme/long",
            system_b="beta/short",
            judge="mock-j/longer",
            order=order,
            winner="b",
        )
        for sid in payoff_ids
        for order in (0, 1)
    ]
    res = layer2.run_payoff_lift(
        roster,
        CORPUS,
        judges=["mock-j/longer"],
        cache=tmp_path / "cache",
        standalone_judgments=standalone,
        workers=4,
    )
    assert len(res["payoff_segments"]) == len(CORPUS.gags)
    assert res["by_system"]["acme/long"]["context_win_rate"] == 1.0
    assert res["by_system"]["acme/long"]["lift"] == 1.0
    assert res["by_system"]["beta/short"]["lift"] == -1.0


def test_convergence_report_flags_unexpected_divergence():
    ledgers = {
        "a": {
            "overall_consistency": 1.0,
            "name_consistency": 1.0,
            "gag_consistency": 1.0,
        },
        "b": {
            "overall_consistency": 0.5,
            "name_consistency": 0.5,
            "gag_consistency": 0.5,
        },
        "c": {
            "overall_consistency": 0.0,
            "name_consistency": 0.0,
            "gag_consistency": 0.0,
        },
    }
    # Invert Layer-1 gags relative to gag_consistency -> must flag divergence.
    lb = [
        {
            "system": "a",
            "drs": 0.2,
            "gags": 0.1,
            "humor": 0.5,
            "voice": 0.5,
            "fidelity": 0.5,
        },
        {
            "system": "b",
            "drs": 0.5,
            "gags": 0.5,
            "humor": 0.5,
            "voice": 0.5,
            "fidelity": 0.5,
        },
        {
            "system": "c",
            "drs": 0.8,
            "gags": 0.9,
            "humor": 0.5,
            "voice": 0.5,
            "fidelity": 0.5,
        },
    ]
    conv = layer2.convergence_report(ledgers, lb)
    assert conv["correlations"]["gag_consistency"]["gags"] == -1.0
    assert any("gag_consistency vs gags" in d for d in conv["divergences"])


# --- Lesion Battery & Null Calibration --------------------------------------


def test_offline_lesion_battery_passes_on_clean_submission():
    clean = _clean_submission()
    results = lesions.run_offline_lesions(clean, CORPUS)
    assert set(results) == {"pad", "truncate", "gag_shuffle", "canary_leak"}
    for kind, info in results.items():
        assert info["passed"], (kind, info)


def test_scene_contradict_lesion_rotates_all_segments():
    clean = _clean_submission()
    rotated = lesions.apply_lesion(clean, CORPUS, "scene_contradict")
    assert rotated.segments[0].text == clean.segments[1].text
    assert rotated.segments[-1].text == clean.segments[0].text


def test_null_calibration_check():
    rows = [
        {"system": "acme/m1#run1", "drs": 0.61, "lo": 0.56, "hi": 0.66},
        {"system": "acme/m1#run2", "drs": 0.59, "lo": 0.54, "hi": 0.64},
        {"system": "beta/m2", "drs": 0.30, "lo": 0.25, "hi": 0.35},
    ]
    ok = lesions.check_null_calibration(rows, "acme/m1#run1", "acme/m1#run2")
    assert ok["passed"] is True
    bad = lesions.check_null_calibration(rows, "acme/m1#run1", "beta/m2")
    assert bad["passed"] is False


def test_layer2_and_lesions_clis_run_offline(tmp_path):
    subs = tmp_path / "submissions"
    out = tmp_path / "results"
    sub = _clean_submission("acme/m1", "fr")
    p = subs / "acme__m1" / "fr.json"
    p.parent.mkdir(parents=True)
    p.write_text(sub.model_dump_json(), encoding="utf-8")

    assert layer2.main(["fr", "--submissions", str(subs), "--results", str(out)]) == 0
    data = json.loads((out / "fr" / "layer2.json").read_text(encoding="utf-8"))
    assert data["gag_ledger"]["acme/m1"]["overall_consistency"] == 1.0
    assert (out / "fr" / "layer2.md").exists()

    assert lesions.main(["fr", "--submissions", str(subs)]) == 0
