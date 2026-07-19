# Design panel archive (July 2026)

Primary sources for the v3 design in `../../DESIGN.md`. Four independent
design proposals were produced from distinct expert lenses, and each was
attacked by an adversarial critique before synthesis. These documents are the
reasoning record: when a future session asks "why is the benchmark shaped
this way?", the answer is usually in here.

| lens | proposal | critique | headline idea | fate in v3 |
|---|---|---|---|---|
| Measurement theory / psychometrics | `design-psychometrics.md` | `critique-psychometrics.md` | DRS as gated pairwise win-probability composite; formative construct; probe battery; payoff lift | Largest contributor — adopted with the critique's repairs (continuous penalty instead of a 1.25× cliff; source-blind limited to humor/voice; anchors added) |
| ML benchmark engineering | `design-benchmark-engineering.md` | `critique-benchmark-engineering.md` | Davidson BT + open-weight anchor; distractor systems; season protocol; judgment cache; cost arithmetic | Statistics, anchors, contamination and reproducibility machinery adopted; its single-call judging was proven self-contradictory (can't both show and hide the source) |
| AVT industry practice | `design-avt-industry.md` | `critique-avt-industry.md` | Adaptation job with a bible (KNP sheet) deliverable; retake taxonomy; TTS table read; flattening probe | Bible deliverable and autopsy/retake taxonomy adopted; conjunctive-gate FPA rejected (its dead-air floor flunked the English source — the critique ran the numbers) |
| Humor science / computational humor | `design-humor-science.md` | `critique-humor-science.md` | Joke Cards (GTVH mechanisms); detection asymmetry; behavioral probes over preference | Joke Cards and detection asymmetry adopted as Layer-2; strict mechanical JSR rejected (recognizability ≠ survival; punishes compensation; Goodhart surface) |

Cross-cutting critique findings that shaped v3 (see `DESIGN.md` §0):

- Pure source-blind judging measures scene-conditioned comedy *generation*,
  not translation — hence the two-condition split plus the tethering battery.
- Pairwise judging cancels judge severity (a main effect), **not**
  preference-direction bias — LitEval-style taste bias survives head-to-head,
  which is why the human humor sample is required before public claims.
- Cliffs inside an estimator's error band are noise amplifiers; only
  validated measurements may gate hard.
- The corpus, not API spend, is the project's real cost; no statistics can
  rescue 12 segments.

Provenance: generated 2026-07-19 by a workflow of eight model agents (four
designers, four critics) with repository read access; synthesized by the
session's main agent into `DESIGN.md`. These are research inputs, not
authoritative specifications — where they conflict with `DESIGN.md`,
`DESIGN.md` wins.

Historical note: these documents quote the original v0 corpus (a fictional
film titled "Moon Over Gorganzola", segment ids `mog-NNN`). That corpus was
later replaced by the current `pastiche-v0` corpus (`ps-NNN`), which preserves
the same segment windows, feature tags, and gag topology with new surface
content — so the panel's structural analyses (fill ratios, gag-chain counts,
cluster arithmetic) carry over. The archives are preserved verbatim as primary
sources.
