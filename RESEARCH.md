# Research Notes

*Compiled July 2026. This document grounds the benchmark's design decisions in
the current MT-evaluation and multilingual-LLM literature.*

## 1. Why standard MT metrics fail here

- **BLEU** punishes paraphrase and rewards n-gram overlap — but a good WPDR
  translation is *mostly paraphrase*: the joke gets rebuilt, not carried word
  by word. BLEU would actively reward the worst translations.
- **chrF/chrF++** fixes tokenization sensitivity, not the paraphrase problem.
- **COMET**-family learned metrics correlate with human judgment on news-style
  text and remain the WMT workhorse, but they're trained on adequacy/fluency
  judgments, not on "did the bombast survive." Useful as a sanity floor
  (a translation that fails COMET badly is probably broken), useless as the
  headline number.
- Conclusion: standard metrics are kept only as **diagnostics**; the headline
  score must come from rubric-based judgment plus computed performability.

## 2. What the literary-translation-evaluation literature says

- **LitEval-Corpus** (2,000+ paragraphs, MQM-annotated, 4 language pairs) is
  the reference point for metric validation on literary text. Its headline
  finding is our central design warning: **LLM judges (including GEMBA-MQM
  -style approaches) systematically prefer machine translations over
  professional human literary translations** — misaligned with human experts.
  Mitigations adopted here:
  1. **Anchored pairwise comparison** rather than absolute scoring
     (JP-TL-Bench shows anchored pairwise stabilizes LLM judgment).
  2. **Judge ensemble across providers**, with a no-self-judging rule
     (a judge never scores output from its own provider family).
  3. **Rubric decomposition** — six narrow questions instead of one holistic
     "which is better," reducing the fluency-bias surface.
  4. **MQM-style error spans** retained as diagnostics (per GEMBA-MQM /
     Auto-MQM / MQM-APE lineage) so failures are inspectable.
- **LiTransProQA** (EMNLP 2025) operationalizes literary translation QA as
  professional-translator questions answered by an LLM — validation of the
  "narrow questions beat holistic scores" approach; our rubric prompts follow
  this shape.

## 3. Performability (the "Dear Reader" constraint)

WPDR is a *performed* text: each segment must be speakable in the time the
muted film allows. This is the automatic-dubbing **isochrony** problem.
Research on isometric MT (phoneme/character-count-ratio control, e.g.
PCR-reward RL) shows length control is measurable and optimizable without any
judge. We implement it directly: estimated spoken duration of the translation
÷ segment time window → a computed performability score. Length ratios also
get reported per language, since scripts differ wildly in information density
per syllable.

## 4. Which models to expect on the leaderboard (per-language priors)

From our July-2026 multilingual research (see commentary-track):

- Frontier near-parity at the top overall: Claude Fable 5 / Opus tier (top
  MMMLU-multilingual, 0.927), Gemini 3.x Pro, GPT-5.5.
- **Chinese:** native models (DeepSeek, Qwen, GLM, Kimi) match frontier at a
  fraction of the cost.
- **Japanese/Korean:** Gemini Pro + Claude Opus lead per-language indices;
  Qwen best open-weight CJK.
- **European languages:** Claude repeatedly cited as best for preserving tone,
  humor, and literary style — the core of this benchmark; Mistral the
  European specialist.
- **Lower-resource (ar, hi, id, ...):** Gemini leads.

Hypothesis worth testing: **rankings on this benchmark will diverge from
general multilingual rankings**, because humor reconstruction and register are
closer to creative writing (where Claude leads by a wide margin on EQ-Bench
Creative Writing / arena) than to translation adequacy (where translation
specialists like Qwen-MT and Minimax score highest). If the divergence shows
up, that's the benchmark's headline result.

## 5. Copyright posture

*Wizard People, Dear Reader* is Brad Neely's copyrighted work. This project:

- ships **only** an original pastiche corpus (public track) that imitates the
  *form* — bombastic narrator, epithets, running gags — with original
  characters and story;
- accepts a **user-supplied** transcript for the private track and never
  redistributes, embeds, or caches the real text;
- quotes nothing from the original in code, data, prompts, or docs.

## 6. Sources

- LitEval / literary metric validation: arxiv.org/html/2505.05423 (LiTransProQA, incl. LitEval discussion); aclanthology.org/2025.emnlp-main.1482
- Anchored pairwise LLM judging: arxiv.org/pdf/2601.00223 (JP-TL-Bench)
- MQM-span LLM evaluation lineage: arxiv.org/pdf/2310.13988 (GEMBA-MQM)
- LLM-as-judge long-form limits: arxiv.org/html/2606.01629
- Metric landscape 2026 (COMET-22 primary, chrF secondary; FLORES/WMT suites):
  awesomeagents.ai/leaderboards/translation-benchmarks-leaderboard;
  arxiv.org/pdf/2508.18549 (COMET-poly)
- Isochrony / isometric MT: arxiv.org/pdf/2403.15469
- Multilingual per-language leaders: artificialanalysis.ai/models/multilingual;
  llm-stats.com/benchmarks/mmmlu; benchlm.ai/multilingual
- Creative-writing rankings: EQ-Bench Creative Writing; arena.ai leaderboards

## 7. Roadmap

1. ✅ Corpus v0 (12 pastiche segments, feature-tagged), schema, rubric,
   speakability metric.
2. Translation harness: multi-provider generation (reuse commentary-track's
   provider registry), N systems × M languages.
3. Judge harness: anchored pairwise ensemble + MQM spans; agreement analysis
   between judges before trusting any ranking.
4. Baseline COMET/chrF diagnostics via `unbabel-comet` / `sacrebleu`.
5. Human spot-validation: bilingual raters on a 10% sample to check judge
   alignment (the LitEval warning makes this non-optional).
6. Leaderboard report: per-language, per-dimension, per-feature breakdowns.
