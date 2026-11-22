"""Controlled lesion battery and null-calibration checks (DESIGN.md §6).

Lesions are instrument unit tests (necessary-but-not-sufficient): controlled
degradations must be caught by their target instrument (sensitivity) and must
not trigger unrelated instruments (specificity).

Run offline deterministic lesion checks on any language's submissions:
    python -m dearreader_bench.lesions ja
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from .brief import LANGUAGES
from .layer2 import gag_ledger_deterministic
from .runner import DEFAULT_SUBMISSIONS
from .schema import AdaptationResult, Corpus, TranslatedSegment, load_corpus
from .speakability import fill_ratio
from .submission import DEFAULT_CORPUS, check_submission, performability

log = logging.getLogger(__name__)

LESION_KINDS = (
    "pad",
    "truncate",
    "gag_shuffle",
    "explain_joke",
    "scene_contradict",
    "canary_leak",
)


def apply_lesion(
    result: AdaptationResult, corpus: Corpus, kind: str
) -> AdaptationResult:
    """Create a controlled degraded copy of `result` targeting one construct."""
    if kind not in LESION_KINDS:
        raise ValueError(f"unknown lesion {kind!r}; expected one of {LESION_KINDS}")

    segs = result.segments
    if kind == "pad":
        new_segs = [
            TranslatedSegment(
                segment_id=s.segment_id, text=f"{s.text} {s.text} {s.text} {s.text}"
            )
            for s in segs
        ]
    elif kind == "truncate":
        new_segs = [
            TranslatedSegment(
                segment_id=s.segment_id,
                text=(s.text.strip()[: max(4, len(s.text.strip()) // 6)] or "x"),
            )
            for s in segs
        ]
    elif kind == "gag_shuffle":
        # Replace every declared bible name and gag anchor (plus stripped stems for CJK
        # possessives) in segment text with unrelated placeholder tokens so bible
        # consistency breaks while segment length stays close.
        raw_tokens = {
            v.strip()
            for v in (*result.bible.names.values(), *result.bible.gag_anchors.values())
            if v.strip()
        }
        expanded: set[str] = set(raw_tokens)
        for tok in raw_tokens:
            if len(tok) >= 4 and "の" in tok:
                tail = tok.rsplit("の", 1)[-1]
                if len(tail) >= 2:
                    expanded.add(tail)
        replacements = sorted(expanded, key=len, reverse=True)
        new_segs = []
        for idx, s in enumerate(segs):
            text = s.text
            for r_idx, token in enumerate(replacements):
                if token in text:
                    text = text.replace(token, f"ZZ{(idx + r_idx) % 97:02d}")
            new_segs.append(TranslatedSegment(segment_id=s.segment_id, text=text))
    elif kind == "explain_joke":
        gloss = " (This is funny because of the ironic contrast.)"
        new_segs = [
            TranslatedSegment(segment_id=s.segment_id, text=f"{s.text}{gloss}")
            for s in segs
        ]
    elif kind == "scene_contradict":
        # Cyclically rotate texts across unrelated scenes (preserves voice & length distribution).
        n = len(segs)
        new_segs = [
            TranslatedSegment(
                segment_id=segs[i].segment_id, text=segs[(i + 1) % n].text
            )
            for i in range(n)
        ]
    elif kind == "canary_leak":
        guid = corpus.canary.rsplit(":", 1)[-1]
        new_segs = [
            TranslatedSegment(
                segment_id=s.segment_id,
                text=(f"{s.text} {guid}" if i == 0 else s.text),
            )
            for i, s in enumerate(segs)
        ]
    else:  # pragma: no cover
        raise AssertionError(kind)

    return result.model_copy(
        update={
            "system": f"{result.system}",
            "segments": new_segs,
        }
    )


def run_offline_lesions(
    result: AdaptationResult, corpus: Corpus
) -> dict[str, dict[str, Any]]:
    """Run deterministic instrument sensitivity & specificity checks (zero API calls)."""
    base_p, _ = performability(result, corpus)
    base_ledger = gag_ledger_deterministic(result, corpus)
    windows = {s.id: s.seconds for s in corpus.segments}
    base_mean_fill = sum(
        fill_ratio(s.text, result.language, windows[s.segment_id])
        for s in result.segments
    ) / len(result.segments)

    checks: dict[str, dict[str, Any]] = {}

    # 1. pad: performability must collapse to 0; gag consistency must stay intact (specificity).
    padded = apply_lesion(result, corpus, "pad")
    pad_p, pad_forfeits = performability(padded, corpus)
    pad_ledger = gag_ledger_deterministic(padded, corpus)
    checks["pad"] = {
        "passed": pad_p < 0.1
        and len(pad_forfeits) >= len(corpus.segments) // 2
        and abs(pad_ledger["overall_consistency"] - base_ledger["overall_consistency"])
        < 1e-9,
        "base_p": base_p,
        "lesion_p": pad_p,
        "forfeits": len(pad_forfeits),
        "consistency_preserved": abs(
            pad_ledger["overall_consistency"] - base_ledger["overall_consistency"]
        )
        < 1e-9,
    }

    # 2. truncate: fill ratio drops, performability must NOT penalize underrun (DESIGN.md §2.3).
    trunc = apply_lesion(result, corpus, "truncate")
    trunc_p, trunc_forfeits = performability(trunc, corpus)
    trunc_mean_fill = sum(
        fill_ratio(s.text, trunc.language, windows[s.segment_id])
        for s in trunc.segments
    ) / len(trunc.segments)
    checks["truncate"] = {
        "passed": trunc_mean_fill < base_mean_fill * 0.5
        and trunc_p == 1.0
        and len(trunc_forfeits) == 0,
        "base_mean_fill": base_mean_fill,
        "lesion_mean_fill": trunc_mean_fill,
        "lesion_p": trunc_p,
    }

    # 3. gag_shuffle: gag ledger consistency must plunge; performability must stay stable.
    shuffled = apply_lesion(result, corpus, "gag_shuffle")
    shuf_p, _ = performability(shuffled, corpus)
    shuf_ledger = gag_ledger_deterministic(shuffled, corpus)
    checks["gag_shuffle"] = {
        "passed": shuf_ledger["overall_consistency"]
        < base_ledger["overall_consistency"] - 0.5
        and abs(shuf_p - base_p) < 0.05,
        "base_consistency": base_ledger["overall_consistency"],
        "lesion_consistency": shuf_ledger["overall_consistency"],
        "p_delta": shuf_p - base_p,
    }

    # 4. canary_leak: submission checker must reject with canary contamination.
    leaked = apply_lesion(result, corpus, "canary_leak")
    problems = check_submission(leaked, corpus)
    checks["canary_leak"] = {
        "passed": any("canary" in prob for prob in problems),
        "problems": problems,
    }

    return checks


def check_null_calibration(
    rows: list[dict[str, Any]], system_a: str, system_b: str
) -> dict[str, Any]:
    """Verify two same-system pseudo-entrants have overlapping 95% DRS intervals (DESIGN.md §6)."""
    by_sys = {r["system"]: r for r in rows}
    if system_a not in by_sys or system_b not in by_sys:
        raise ValueError(f"missing {system_a!r} or {system_b!r} in leaderboard rows")
    ra, rb = by_sys[system_a], by_sys[system_b]
    overlaps = max(ra["lo"], rb["lo"]) <= min(ra["hi"], rb["hi"])
    return {
        "passed": overlaps,
        "system_a": system_a,
        "system_b": system_b,
        "drs_gap": ra["drs"] - rb["drs"],
        "interval_a": [ra["lo"], ra["hi"]],
        "interval_b": [rb["lo"], rb["hi"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language", choices=sorted(LANGUAGES))
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--submissions", type=Path, default=DEFAULT_SUBMISSIONS)
    parser.add_argument(
        "--system",
        default=None,
        help="Run lesions on one system id (default: first non-anchor submission)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    corpus = load_corpus(args.corpus)
    roster: dict[str, AdaptationResult] = {}
    for path in sorted(args.submissions.glob(f"*/{args.language}.json")):
        res = AdaptationResult.model_validate_json(path.read_text(encoding="utf-8"))
        roster[res.system] = res
    if not roster:
        log.error("no submissions found in %s for %s", args.submissions, args.language)
        return 1

    target = args.system or next(
        (s for s in sorted(roster) if not s.endswith(("+literal", "+rewrite"))),
        min(roster),
    )
    if target not in roster:
        log.error("system %s not found in roster %s", target, sorted(roster))
        return 1

    results = run_offline_lesions(roster[target], corpus)
    all_ok = all(info["passed"] for info in results.values())
    lines = [
        f"# Offline lesion battery: {target} [{args.language}] on {corpus.corpus}",
        "",
        f"**Overall:** {'PASS' if all_ok else 'FAIL'}",
        "",
        "| lesion | passed | details |",
        "|---|---|---|",
    ]
    for kind, info in results.items():
        details = ", ".join(
            f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
            for k, v in info.items()
            if k != "passed"
        )
        lines.append(f"| {kind} | {'PASS' if info['passed'] else 'FAIL'} | {details} |")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
