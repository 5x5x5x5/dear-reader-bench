"""Judge every pair of submissions in one language and write the leaderboard.

    python -m dearreader_bench.judge ja --judges google/gemini-3-pro openai/gpt-5.5 qwen/qwen3-72b --dry-run
    python -m dearreader_bench.judge ja --judges google/gemini-3-pro openai/gpt-5.5 qwen/qwen3-72b

Writes results/<language>/{judgments.jsonl, leaderboard.md, leaderboard.json, run.lock}.
Judge replies are cached by content, so a re-run only pays for what changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path

from . import __version__
from .audit import audit_run, render_audit
from .brief import HARNESS_VERSION, LANGUAGES
from .btmodel import composite, fit, tally
from .providers import complete, extract_json
from .rubric import (
    JUDGE_QUESTIONS,
    WEIGHTS,
    build_gag_context,
    no_self_judging,
    pairwise_prompt,
)
from .runner import DEFAULT_SUBMISSIONS
from .schema import AdaptationResult, Corpus, Dimension, PairwiseJudgment, load_corpus
from .speakability import is_forfeit
from .submission import DEFAULT_CORPUS, check_submission, performability

log = logging.getLogger(__name__)

# (segment_id, dimension, system_a, system_b, winner) after order-folding; one per judge.
Outcome = tuple[str, str, str, str, str]


def load_roster(
    submissions: Path, language: str, corpus: Corpus
) -> dict[str, AdaptationResult]:
    roster = {}
    for path in sorted(submissions.glob(f"*/{language}.json")):
        result = AdaptationResult.model_validate_json(path.read_text(encoding="utf-8"))
        problems = check_submission(result, corpus)
        if problems:
            raise ValueError(f"{path}: {problems}")
        roster[result.system] = result
    return roster


def plan(
    roster: dict[str, AdaptationResult], corpus: Corpus, judges: list[str]
) -> list[tuple]:
    """Every judge call owed: (segment, dimension, a, b, order, judge). Forfeits are not judged."""
    texts = {
        name: {s.segment_id: s.text for s in r.segments} for name, r in roster.items()
    }
    calls = []
    for a, b in combinations(sorted(roster), 2):
        eligible = [j for j in judges if no_self_judging(j, a, b)]
        if not eligible:
            log.warning("no eligible judge for %s vs %s; pair skipped", a, b)
        for segment in corpus.segments:
            language = roster[a].language
            if any(
                is_forfeit(texts[s][segment.id], language, segment.seconds)
                for s in (a, b)
            ):
                continue
            calls += [
                (segment, dimension, a, b, order, judge)
                for dimension in Dimension
                for order in (0, 1)
                for judge in eligible
            ]
    return calls


def _judge_once(
    call: tuple,
    roster: dict[str, AdaptationResult],
    corpus: Corpus,
    cache: Path,
    served_models: dict[str, set[str]] | None = None,
    served_lock: threading.Lock | None = None,
) -> PairwiseJudgment:
    segment, dimension, a, b, order, judge = call
    text = {
        n: next(s.text for s in roster[n].segments if s.segment_id == segment.id)
        for n in (a, b)
    }
    first, second = (a, b) if order == 0 else (b, a)
    language = roster[a].language
    gag_context = (
        build_gag_context(segment, corpus, roster[first], roster[second])
        if dimension is Dimension.GAGS
        else ""
    )
    prompt = pairwise_prompt(
        segment,
        LANGUAGES[language],
        dimension,
        text[first],
        text[second],
        gag_context=gag_context,
    )
    entry = cache / (
        hashlib.sha256(f"{judge}\n{prompt}".encode()).hexdigest() + ".json"
    )
    served = ""
    if entry.exists():
        cached = json.loads(entry.read_text(encoding="utf-8"))
        reply = cached["reply"]
        served = str(cached.get("served_model", ""))
    else:
        meta: dict[str, str] = {}
        reply = complete(
            judge, prompt, temperature=0, timeout=120, reasoning=False, meta=meta
        )
        served = meta.get("served_model", "")
        # Identical candidate texts give both orders the same key, so write atomically.
        scratch = entry.with_suffix(f".{threading.get_ident()}.tmp")
        scratch.write_text(
            json.dumps({"judge": judge, "served_model": served, "reply": reply}),
            encoding="utf-8",
        )
        scratch.replace(entry)
    if served and served_models is not None:
        if served_lock is not None:
            with served_lock:
                served_models.setdefault(judge, set()).add(served)
        else:
            served_models.setdefault(judge, set()).add(served)
    try:
        verdict = extract_json(reply)
        shown = verdict["winner"] if verdict["winner"] in ("a", "b", "tie") else "tie"
        rationale = str(verdict.get("rationale", ""))
    except (ValueError, KeyError, TypeError):
        shown, rationale = "tie", "UNPARSEABLE"
    # Record the winner against (system_a, system_b), whatever order the judge saw.
    winner = shown if order == 0 or shown == "tie" else ("b" if shown == "a" else "a")
    return PairwiseJudgment(
        segment_id=segment.id,
        language=language,
        dimension=dimension,
        system_a=a,
        system_b=b,
        judge=judge,
        order=order,
        winner=winner,
        rationale=rationale,
    )


def run_judges(
    calls: list[tuple],
    roster: dict[str, AdaptationResult],
    corpus: Corpus,
    cache: Path,
    workers: int = 8,
    served_models: dict[str, set[str]] | None = None,
) -> list[PairwiseJudgment]:
    cache.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    with ThreadPoolExecutor(workers) as pool:
        return list(
            pool.map(
                lambda call: _judge_once(
                    call, roster, corpus, cache, served_models, lock
                ),
                calls,
            )
        )


def fold(
    judgments: list[PairwiseJudgment],
    roster: dict[str, AdaptationResult],
    corpus: Corpus,
) -> list[Outcome]:
    """Fold the two presentation orders into one verdict (disagreement is a tie), add forfeits."""
    by_key: dict[tuple, list[str]] = {}
    for j in judgments:
        key = (j.segment_id, j.dimension.value, j.system_a, j.system_b, j.judge)
        by_key.setdefault(key, []).append(j.winner)
    outcomes = [
        (*key[:4], w[0] if len(set(w)) == 1 else "tie") for key, w in by_key.items()
    ]

    # A forfeited segment loses to every eligible opponent on every dimension (DESIGN.md §2.3).
    for a, b in combinations(sorted(roster), 2):
        forfeits = {n: set(performability(roster[n], corpus)[1]) for n in (a, b)}
        for segment_id in forfeits[a] ^ forfeits[b]:
            winner = "b" if segment_id in forfeits[a] else "a"
            outcomes += [(segment_id, d.value, a, b, winner) for d in Dimension]
    return outcomes


def score(
    outcomes: list[Outcome], p: dict[str, float], iters: int = 2000
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """DRS per system, and phi per dimension per system."""
    phi = {}
    for dimension in Dimension:
        rows = [(a, b, w) for _, d, a, b, w in outcomes if d == dimension.value]
        if rows:
            phi[dimension.value] = fit(tally(rows), iters=iters).phi
    return composite(phi, {d.value: w for d, w in WEIGHTS.items()}, p), phi


def leaderboard(
    outcomes: list[Outcome],
    roster: dict[str, AdaptationResult],
    corpus: Corpus,
    replicates: int = 200,
    seed: int = 0,
) -> list[dict]:
    """Rows sorted by DRS with 95% intervals and tiers (DESIGN.md §2.2)."""
    p = {name: performability(result, corpus)[0] for name, result in roster.items()}
    drs, phi = score(outcomes, p)

    # Gag chains are correlated, so each chain resamples as one cluster.
    cluster = {s.id: s.gag_id or s.id for s in corpus.segments}
    by_cluster: dict[str, list[Outcome]] = {}
    for outcome in outcomes:
        by_cluster.setdefault(cluster[outcome[0]], []).append(outcome)
    names, rng = sorted(by_cluster), random.Random(seed)
    draws: dict[str, list[float]] = {name: [] for name in drs}
    for _ in range(replicates):
        sample = [o for c in rng.choices(names, k=len(names)) for o in by_cluster[c]]
        # Same fit settings as the point estimate: a shorter fit shifts every replicate.
        for name, value in score(sample, p)[0].items():
            draws[name].append(value)

    rows = []
    for name in sorted(drs, key=drs.get, reverse=True):
        d = sorted(draws[name]) or [drs[name]]
        rows.append(
            {
                "system": name,
                "drs": drs[name],
                "lo": d[int(0.025 * (len(d) - 1))],
                "hi": d[int(0.975 * (len(d) - 1))],
                "p": p[name],
                **{dim: phi[dim][name] for dim in phi if name in phi[dim]},
            }
        )
    # A new tier starts where a system's interval falls wholly below the tier leader's.
    tier, floor = 0, float("inf")
    for row in rows:
        if row["hi"] < floor:
            tier, floor = tier + 1, row["lo"]
        row["tier"] = tier
    return rows


def render(
    rows: list[dict],
    language: str,
    corpus: Corpus,
    judges: list[str],
    audit: dict | None = None,
) -> str:
    mock = any(n.startswith("mock") for n in [*judges, *(r["system"] for r in rows)])
    dims = [d.value for d in Dimension if any(d.value in r for r in rows)]
    banners: list[str] = [
        "**MOCK RUN: these numbers test the pipeline and describe no model.**"
        if mock
        else "**Unvalidated: the DESIGN.md §6 validation program has not been run on this.**"
    ]
    if audit is not None:
        validity = audit.get("validity", {})
        if validity.get("status") == "invalid":
            reasons = "; ".join(validity.get("failures", []))
            banners.append(f"**INVALID RUN (known-groups check failed): {reasons}.**")
        tentative = audit.get("tentative_dimensions") or []
        if tentative:
            banners.append(
                f"**Tentative dimensions (Krippendorff's alpha < 0.5): {', '.join(tentative)}.** "
                "See `audit.md` for DRS republished without them."
            )
    lines = [
        f"# {LANGUAGES[language]} on {corpus.corpus}",
        "",
        *banners,
        "",
        "| tier | system | DRS | 95% interval | P | " + " | ".join(dims) + " |",
        "|---|---|---|---|---|" + "---|" * len(dims),
    ]
    lines += [
        f"| {r['tier']} | {r['system']} | {r['drs']:.3f} | {r['lo']:.3f} to {r['hi']:.3f} | "
        f"{r['p']:.3f} | "
        + " | ".join(f"{r.get(d, float('nan')):.3f}" for d in dims)
        + " |"
        for r in rows
    ]
    return "\n".join([*lines, "", f"Judges: {', '.join(judges)}", ""])


def run_lock(
    corpus_path: Path,
    corpus: Corpus,
    judges: list[str],
    roster: list[str],
    served_models: dict[str, set[str]] | None = None,
    pinned_anchor: str | None = None,
) -> dict:
    lock: dict = {
        "corpus": corpus.corpus,
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "harness_version": HARNESS_VERSION,
        "judge_questions_sha256": hashlib.sha256(
            json.dumps(
                {d.value: q for d, q in JUDGE_QUESTIONS.items()}, sort_keys=True
            ).encode()
        ).hexdigest(),
        "gags_bible_context": True,
        "estimator_version": __version__,
        "weights": {d.value: w for d, w in WEIGHTS.items()},
        "judges": judges,
        "judge_settings": {"temperature": 0, "reasoning": False},
        "systems": roster,
    }
    if served_models:
        lock["served_models"] = {
            j: sorted(models) for j, models in sorted(served_models.items()) if models
        }
    if pinned_anchor is not None:
        lock["pinned_anchor"] = pinned_anchor
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language", choices=sorted(LANGUAGES))
    parser.add_argument(
        "--judges", nargs="+", required=True, help="family/model, three families"
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--submissions", type=Path, default=DEFAULT_SUBMISSIONS)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_CORPUS.parents[1] / "results"
    )
    parser.add_argument(
        "--pinned-anchor",
        default=None,
        help="Pinned open-weight mid-tier anchor system id (DESIGN.md §2.2)",
    )
    parser.add_argument("--replicates", type=int, default=200)
    parser.add_argument("--workers", type=int, default=8, help="parallel judge calls")
    parser.add_argument(
        "--dry-run", action="store_true", help="count the judge calls and stop"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    corpus = load_corpus(args.corpus)
    roster = load_roster(args.submissions, args.language, corpus)
    if len(roster) < 2:
        log.error(
            "need at least two submissions in %s for %s",
            args.submissions,
            args.language,
        )
        return 1
    calls = plan(roster, corpus, args.judges)
    log.info("%d systems, %d judge calls", len(roster), len(calls))
    if args.dry_run:
        return 0

    out = args.out / args.language
    out.mkdir(parents=True, exist_ok=True)
    served_models: dict[str, set[str]] = {}
    judgments = run_judges(
        calls, roster, corpus, args.out / "cache", args.workers, served_models
    )
    unparseable = sum(j.rationale == "UNPARSEABLE" for j in judgments)
    if unparseable:
        log.warning(
            "%d judge replies could not be parsed and count as ties", unparseable
        )
    (out / "judgments.jsonl").write_text(
        "".join(j.model_dump_json() + "\n" for j in judgments), encoding="utf-8"
    )
    rows = leaderboard(fold(judgments, roster, corpus), roster, corpus, args.replicates)
    audit = audit_run(
        judgments,
        roster,
        corpus,
        pinned_anchor=args.pinned_anchor,
        split_half_splits=min(20, max(2, args.replicates)),
    )
    table = render(rows, args.language, corpus, args.judges, audit=audit)
    (out / "leaderboard.md").write_text(table, encoding="utf-8")
    (out / "leaderboard.json").write_text(
        json.dumps(rows, indent=1) + "\n", encoding="utf-8"
    )
    (out / "audit.json").write_text(
        json.dumps(audit, indent=1) + "\n", encoding="utf-8"
    )
    (out / "audit.md").write_text(
        render_audit(audit, args.language, corpus), encoding="utf-8"
    )
    lock = run_lock(
        args.corpus,
        corpus,
        args.judges,
        sorted(roster),
        served_models=served_models,
        pinned_anchor=args.pinned_anchor,
    )
    (out / "run.lock").write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8")
    sys.stdout.write(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
