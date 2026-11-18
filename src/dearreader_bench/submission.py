"""Check a submitted adaptation against the corpus, and print the job prompt.

python -m dearreader_bench.submission prompt ja > prompt.txt
python -m dearreader_bench.submission check submissions/acme__model-1/ja.json
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from .brief import LANGUAGES, adaptation_prompt
from .schema import AdaptationResult, Corpus, load_corpus
from .speakability import fill_ratio, performability_score

log = logging.getLogger(__name__)

# Assumes an editable install or a checkout: data/ sits at the repo root, not in the package.
DEFAULT_CORPUS = Path(__file__).parents[2] / "data" / "season2.json"

# An anchor run carries its variant as a suffix: family/model+literal.
_SYSTEM_ID = re.compile(r"^[a-z0-9-]+/[A-Za-z0-9._:-]+(\+(literal|rewrite))?$")
_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def check_submission(result: AdaptationResult, corpus: Corpus) -> list[str]:
    """Return every reason this submission cannot be scored; empty means it can."""
    problems: list[str] = []
    if result.language not in LANGUAGES:
        problems.append(
            f"language {result.language!r} is not in the slate {sorted(LANGUAGES)}"
        )
    if not _SYSTEM_ID.match(result.system):
        # no_self_judging() reads the provider family from the part before the slash.
        problems.append(f"system {result.system!r} must look like 'family/model'")

    wanted = [s.id for s in corpus.segments]
    got = [s.segment_id for s in result.segments]
    if sorted(got) != sorted(wanted):
        missing = sorted(set(wanted) - set(got))
        extra = sorted(set(got) - set(wanted))
        problems.append(
            f"segment ids do not match the corpus: missing {missing}, unknown {extra}"
        )
    if len(got) != len(set(got)):
        problems.append("duplicate segment ids")
    problems += [
        f"{s.segment_id}: empty text" for s in result.segments if not s.text.strip()
    ]

    for kind, required, given in (
        ("names", corpus.names, result.bible.names),
        ("gag_anchors", corpus.gags, result.bible.gag_anchors),
    ):
        absent = [key for key in required if not given.get(key, "").strip()]
        if absent:
            problems.append(f"bible.{kind} has no rendering for {absent}")

    guid = _GUID.search(corpus.canary)
    if guid and guid.group() in result.model_dump_json():
        problems.append(
            "output contains the corpus canary GUID (training-data contamination)"
        )
    return problems


def performability(result: AdaptationResult, corpus: Corpus) -> tuple[float, list[str]]:
    """P (DESIGN.md §2.3) and the ids of forfeited segments. The only DRS term needing no judge."""
    windows = {s.id: s.seconds for s in corpus.segments}
    scores = {
        s.segment_id: performability_score(
            s.text, result.language, windows[s.segment_id]
        )
        for s in result.segments
    }
    return sum(scores.values()) / len(scores), [
        sid for sid, m in scores.items() if m == 0.0
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["prompt", "check"])
    parser.add_argument(
        "target", help="language code for prompt; submission file for check"
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    corpus = load_corpus(args.corpus)

    if args.command == "prompt":
        sys.stdout.write(adaptation_prompt(corpus, args.target))
        return 0

    result = AdaptationResult.model_validate_json(
        Path(args.target).read_text(encoding="utf-8")
    )
    problems = check_submission(result, corpus)
    for problem in problems:
        log.error("REJECT %s", problem)
    if problems:
        return 1
    p, forfeits = performability(result, corpus)
    windows = {s.id: s.seconds for s in corpus.segments}
    fills = [
        fill_ratio(s.text, result.language, windows[s.segment_id])
        for s in result.segments
    ]
    log.info("OK %s [%s] on %s", result.system, result.language, corpus.corpus)
    log.info("performability P = %.3f, forfeits: %s", p, forfeits or "none")
    log.info("fill ratio min %.2f, max %.2f (diagnostic only)", min(fills), max(fills))
    return 0


if __name__ == "__main__":
    sys.exit(main())
