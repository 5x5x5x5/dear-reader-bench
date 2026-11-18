# dear-reader-bench

**An AI benchmark for translating *Wizard People, Dear Reader*-style comedic
narration into other languages.**

Most translation benchmarks measure whether a model can move *meaning* between
languages. This one measures whether it can move a *performance*: wall-to-wall
bombastic narration with invented epithets, running gags, register whiplash,
and prose that must be speakable over a muted film in fixed time windows. A
model that can carry that into Japanese can carry anything.

## What it measures

Headline score **DRS** = performability × weighted win rate across four judged
dimensions (anchored pairwise, Davidson Bradley–Terry):

| dimension | weight | judged | measures |
|---|---|---|---|
| Humor | 35% | source-blind | jokes rebuilt to land in the target language |
| Voice | 30% | source-blind | the bombastic narrator register survives |
| Gags | 20% | source-aware | names/epithets/running gags derive from the source's and stay consistent |
| Fidelity | 15% | source-aware | still narrates this scene and this source |

Performability (fits the time window) is computed, not judged. Behavioral
instruments — joke cards, detection asymmetry, the gag ledger, payoff lift —
are reported alongside. Full architecture, instrument positions, statistics,
and validation program: **`DESIGN.md`**. Literature and reasoning:
**`RESEARCH.md`** and the design-panel archive in **`research/panel/`**.

## Corpus and copyright

Two tracks. The *public track* runs on an original, copyright-safe synthetic
corpus in the WPDR style (`data/season2.json`, 48 segments with joke cards —
purpose-built test fiction, not an existing film; `data/segments.json` is the
earlier 12-segment development set). The *private track* accepts a user-supplied transcript
of the real work; **this repo does not and will not distribute Brad Neely's
text.**

## Layout

```
DESIGN.md                 authoritative v3 architecture
RESEARCH.md               literature notes
research/panel/           design-panel proposals + critiques (primary sources)
src/dearreader_bench/
  schema.py               segments, joke cards, adaptation jobs (bible), judgments
  rubric.py               judged dimensions, two-condition prompts, weights
  speakability.py         mixed-script duration model, penalty/forfeit/fill-ratio
  btmodel.py              Davidson Bradley-Terry fit, phi, DRS composite
  brief.py                the adaptation prompt, the same for every system
  submission.py           submission checker and prompt printer
  providers.py            one OpenAI-compatible model call (OpenRouter by default), plus mock models
  runner.py               run a system on the adaptation job, write a submission
  judge.py                pairwise judging, cache, leaderboard with tiers, run.lock
data/season2.json         public corpus, season 2 (headline)
data/season2_cards.json   joke cards for season 2
data/segments.json        season 1, now a development set
data/STYLE_BIBLE.md       how a season is written; the blueprint
SUBMITTING.md             how to submit a system
submissions/              submitted adaptations, one folder per system
tests/
```

## Status

No results yet. A first seed run exists (eight systems, Japanese only, cheap
judges, nothing validated) and its numbers are deliberately not published.
Built and tested:
schema, rubric, duration model, BT aggregation, the season 2 corpus with joke
cards, submission intake, the translation runner and the judge harness (`uv run --with pytest --with-editable . pytest -q`).
Season 2 was drafted by an LLM and has not had its human edit, so it is fit
for building the harness and not yet for published humor claims
(`data/STYLE_BIBLE.md`). Next: a first real run, then the Layer-2 instruments
and the validation program (`DESIGN.md` §9). Systems can be submitted now: see
`SUBMITTING.md`.

## Running it

```sh
export OPENROUTER_API_KEY=...   # or DRB_API_KEY + DRB_BASE_URL for any OpenAI-compatible server
python -m dearreader_bench.runner <family/model> ja fr        # writes submissions/
python -m dearreader_bench.runner <family/model> ja --anchor literal
python -m dearreader_bench.judge ja --judges <three models, three families> --dry-run   # counts calls
python -m dearreader_bench.judge ja --judges <three models, three families>             # writes results/ja/
```

Models named `mock/echo`, `mock/terse`, `mock/padded` and judges named `mock.../longer` need
no key and cost nothing; their leaderboard is labelled a mock run.

## License

Code and documentation: Apache-2.0 (`LICENSE`). The pastiche corpus in
`data/` (and system translations of it): CC BY 4.0 (`data/LICENSE`) — the
standard split for benchmarks whose dataset is a creative work.
