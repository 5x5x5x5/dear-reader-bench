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

## The headline: DRS (Dear-Reader Score)

**DRS = performability × Σ (weight × expected win rate vs. the field)** over
four judged dimensions, fit with a Davidson Bradley–Terry model on anchored
pairwise comparisons:

| dimension | weight | judge condition | what's measured |
|---|---|---|---|
| Humor | 35% | source-blind | Jokes land *in the target language* — rebuilt, not transliterated; references adapted, never footnoted |
| Voice | 30% | source-blind | The wheezing, grandiose narrator bombast survives, including its deliberate register drops |
| Gags | 20% | source-aware | Names/epithets/running gags derive from the *source's* gags and stay consistent with the system's own bible |
| Fidelity | 15% | source-aware | The narration still describes this scene and this source segment |

Performability (fits the time window) is **measured, not judged**: a continuous
penalty from 110% of the window, forfeiture at 150%, and no dead-air penalty —
the English source itself spans 57–101% fill because the pauses *are* the
comic timing. Humor/voice are judged without the English (the audience never
hears it); gags/fidelity plus a tethering battery keep it a *translation*
benchmark rather than scene-conditioned comedy generation.

## Design

The full architecture — instrument positions, aggregation statistics,
bias/gaming/contamination defenses, the no-human-blocking validation program,
and the Layer-2 behavioral instruments (detection asymmetry, gag ledger,
payoff lift, joke cards, autopsy taxonomy) — lives in **`DESIGN.md`**. It was
produced by a four-lens adversarial design panel (measurement theory, benchmark
engineering, AVT industry practice, humor science); `RESEARCH.md` holds the
literature notes.

Headlines of the design:

- **Two tracks.** The *public track* uses an original, copyright-safe pastiche
  corpus written in the WPDR style (see `data/segments.json` — the ongoing saga
  of *Moon Over Gorganzola*). The *private track* runs the same harness on a
  user-supplied transcript of the real work — **this repo does not and will not
  distribute Brad Neely's text** — and is declared source-side contaminated by
  default; the pastiche track is the scientific instrument.
- **The task is an adaptation job, not per-segment MT:** systems deliver a
  full-script translation *plus a bible* (their own key-names-and-phrases
  sheet), and are held to it.
- **Positions, argued:** BLEU excluded entirely; chrF++ appendix-only as a
  pre-registered discriminant-validity witness; COMET-KIWI as a catastrophe
  floor; MQM replaced by a comedy-native autopsy taxonomy. Validity is argued
  from construct logic, bounded by an automated reliability/lesion-battery
  panel, and pre-registered — with a small bilingual human sample required
  before the first public leaderboard makes humor claims.
- **Honest statistics:** gag-chain cluster bootstrap, tiers instead of ranks,
  fixed anchor systems in every run (forced-literal, open-weight mid-tier,
  unconstrained-rewrite — the latter two double as validity checks), and a
  published power statement: at the current 12-segment corpus, most systems
  are indistinguishable, and the leaderboard says so.

## Repository layout

```
DESIGN.md                 the authoritative v3 architecture (panel-synthesized)
RESEARCH.md               research notes: metrics literature, judge bias
src/dearreader_bench/
  schema.py               segments, joke cards, adaptation jobs (bible), judgments
  rubric.py               four judged dimensions, two-condition prompts, weights
  speakability.py         mixed-script duration model, penalty/forfeit/fill-ratio
  btmodel.py              Davidson Bradley-Terry fit, phi, DRS composite
data/
  segments.json           public pastiche corpus (copyright-safe, original)
tests/
```

## Status

Design phase complete (v3, panel-synthesized — see `DESIGN.md`). Implemented
with tests: the corpus, schema (incl. joke cards and the adaptation-job/bible
deliverable), the two-condition rubric, the mixed-script duration model with
its exploit surface closed, and the Davidson BT aggregation. Next per the
DESIGN.md roadmap: corpus season 2 (the binding constraint), then the
translation/judge harness reusing the provider registry from
[commentary-track](../Gorganzola).
