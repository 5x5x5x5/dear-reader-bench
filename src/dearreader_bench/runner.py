"""Run one system on the adaptation job and save a submission file.

python -m dearreader_bench.runner anthropic/claude-sonnet-5-5 ja
python -m dearreader_bench.runner openai/gpt-5.5 ja --anchor literal
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .brief import ANCHORS, LANGUAGES, adaptation_prompt
from .providers import complete, extract_json
from .schema import AdaptationResult, Corpus, load_corpus
from .submission import DEFAULT_CORPUS, check_submission

log = logging.getLogger(__name__)

DEFAULT_SUBMISSIONS = DEFAULT_CORPUS.parents[1] / "submissions"


def submission_path(root: Path, system: str, language: str) -> Path:
    # Colons (provider suffixes like ":free") are not legal in Windows paths.
    return root / system.replace("/", "__").replace(":", "_") / f"{language}.json"


def translate(
    model: str, language: str, corpus: Corpus, anchor: str | None = None
) -> AdaptationResult:
    """One call, no retries on content: a system that returns a broken script fails the job."""
    reply = complete(model, adaptation_prompt(corpus, language, anchor))
    system = f"{model}+{anchor}" if anchor else model
    result = AdaptationResult(system=system, language=language, **extract_json(reply))
    problems = check_submission(result, corpus)
    if problems:
        raise ValueError(f"{system} [{language}] is not scoreable: {problems}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", help="family/model, as the provider names it")
    parser.add_argument("languages", nargs="+", choices=sorted(LANGUAGES))
    parser.add_argument("--anchor", choices=sorted(ANCHORS))
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_SUBMISSIONS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    corpus = load_corpus(args.corpus)
    for language in args.languages:
        result = translate(args.model, language, corpus, args.anchor)
        path = submission_path(args.out, result.system, language)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
        log.info("wrote %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
