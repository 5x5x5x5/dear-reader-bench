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
corpus in the WPDR style (`data/segments.json` — purpose-built test fiction,
not an existing film). The *private track* accepts a user-supplied transcript
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
data/segments.json        public pastiche corpus
tests/
```

## Status

Design phase complete; corpus, schema, rubric, duration model, and BT
aggregation implemented with tests (`pip install -e '.[dev]' && pytest`).
Next per `DESIGN.md` §9: corpus season 2, then the translation/judge harness.

## License

Code and documentation: Apache-2.0 (`LICENSE`). The pastiche corpus in
`data/` (and system translations of it): CC BY 4.0 (`data/LICENSE`) — the
standard split for benchmarks whose dataset is a creative work.
