# dear-reader-bench

**An AI benchmark for translating *Wizard People, Dear Reader*-style comedic
narration into other languages.**

Machine translation benchmarks measure whether a model can move *meaning*
between languages. This benchmark measures whether it can move a *performance*:
Brad Neely's 2004 alternate audio track for *Harry Potter and the Sorcerer's
Stone* is wall-to-wall bombastic narration — invented epithets, running gags,
register whiplash, pop-culture riffs, and prose that only works read aloud over
a muted film at a fixed tempo. It is close to a worst case for translation, which
makes it a great benchmark: a model that can carry *Wizard People* into Japanese
can carry anything.

## What makes this hard (the six dimensions)

| dimension | weight | what's measured |
|---|---|---|
| Voice & register | 25% | The wheezing, grandiose audiobook-narrator bombast survives |
| Humor | 25% | The jokes land *in the target language* — rebuilt, not transliterated |
| Names & epithets | 15% | Invented names stay funny and consistent across segments |
| Cultural adaptation | 10% | References are adapted for the target audience, not footnoted |
| Performability | 15% | Speakable aloud in the segment's time window (isochrony) |
| Scene fidelity | 10% | The narration still describes what's on screen |

## Design

- **Two tracks.** The *public track* uses an original, copyright-safe pastiche
  corpus written in the WPDR style (see `data/segments.json` — the ongoing saga
  of *Moon Over Gorganzola*). The *private track* runs the same harness on a
  user-supplied transcript of the real work — **this repo does not and will not
  distribute Brad Neely's text**; bring your own copy for personal research.
- **Segments, not sentences.** Units are timed narration segments (10–45s) with
  tagged features (`epithet`, `running_gag`, `pun`, `register_shift`,
  `pop_culture`, `aside`) so scores can be broken out by phenomenon.
- **Every instrument runs; humans decide which ones count.** Automatic metrics
  (chrF++, BLEU, COMET/COMET-KIWI), a multi-provider LLM judge ensemble
  (anchored pairwise, no judge scores its own provider family), and a computed
  speakability metric are all reported. A meta-evaluation step correlates each
  instrument against a bilingual human-rated sample; instruments earn their
  place in the headline score empirically, and dimension weights are
  recalibrated against the same data. See `RESEARCH.md` §1 for the protocol
  and the literature-documented risks it controls for (including LLM-judge
  bias on literary text).
- **Performability is computed, not judged.** A speakability metric estimates
  spoken duration of the translation against the segment's time window —
  a fully-specified construct needing no model opinion.

## Repository layout

```
RESEARCH.md               research notes: metrics literature, judge bias, design rationale
src/dearreader_bench/
  schema.py               Segment / Translation / Judgment data models
  rubric.py               the six dimensions, weights, and judge prompt builders
  speakability.py         duration estimation vs. time window (isochrony score)
data/
  segments.json           public pastiche corpus (copyright-safe, original)
tests/
```

## Status

Early research phase. The corpus, rubric, schema, and speakability metric are
in place with tests; the judge/translation harness (multi-provider, reusing the
registry design from [commentary-track](../Gorganzola)) is the next milestone —
see the roadmap at the end of `RESEARCH.md`.
