# dear-reader-bench

An LLM benchmark for translating *Wizard People, Dear Reader*-style comedic narration: does the
humor, voice and running gags survive into another language, and does the result still fit the
time window it has to be spoken in.

## Read first

- `DESIGN.md` is authoritative (v3). Section 9 is the roadmap, in order of leverage.
- `README.md` is the public summary. It is also the website: see "The site" below.
- `RESEARCH.md` and `research/panel/` are background. Do not treat them as the current design.

## Where things stand

Implemented, with 38 passing tests plus one per committed submission:

- `src/dearreader_bench/schema.py`: segments, joke cards, adaptation jobs, judgments (pydantic v2).
- `rubric.py`: the four judged dimensions, two-condition prompts, weights.
- `speakability.py`: the duration model behind the performability term.
- `btmodel.py`: Davidson Bradley–Terry fit, phi, the DRS composite.
- `data/season2.json` + `data/season2_cards.json`: the headline corpus, `pastiche-s2`, 48
  segments, 11 gag chains, 71 joke cards, canary GUID. Written to `data/STYLE_BIBLE.md`.
  **LLM-drafted (Claude Fable 5.2, 2026-11-16), no human edit, no second annotator**: good for
  building the harness, not for published humor results.
- `data/segments.json`: season 1, `pastiche-v0`, 12 segments, now a development set.
- `brief.py`: the adaptation prompt and the draft six-language slate. Bump `HARNESS_VERSION`
  on any change to it.
- `submission.py`: `prompt <lang>` and `check <file>`. `SUBMITTING.md`, the PR template and CI
  (`.github/workflows/test.yml`) are the intake path; files land in `submissions/`.

- `providers.py`: the one model call. OpenAI-compatible, OpenRouter by default
  (`OPENROUTER_API_KEY`, or `DRB_API_KEY` + `DRB_BASE_URL`). Models whose name starts with
  `mock` are local fakes with a known right answer; the tests run on them.
- `runner.py`: `python -m dearreader_bench.runner <family/model> <lang...> [--anchor
  literal|rewrite]` writes a checked submission file.
- `judge.py`: `python -m dearreader_bench.judge <lang> --judges ... [--pinned-anchor <sys>]` plans
  every pair, segment, dimension, order and eligible judge (passing blind-labeled bible + prior-arc
  context for `gags`), caches replies and provider-reported served model snapshots under
  `results/cache/`, folds orders, scores forfeits as losses, fits BT, bootstraps by gag chain, runs
  the audit panel, and writes
  `results/<lang>/{judgments.jsonl,leaderboard.md,leaderboard.json,audit.md,audit.json,run.lock}`.
  `--dry-run` prints the call count; use it before spending money.
- `audit.py`: `python -m dearreader_bench.audit <lang> [--pinned-anchor <sys>]` runs the offline
  DESIGN.md §6/§2.2 reliability and validity panel on any existing `judgments.jsonl` (zero API
  calls): position-swap consistency and first-position bias, Krippendorff's alpha per dimension
  (flagging alpha < 0.5 as tentative and republishing DRS without them), cluster split-half
  reliability with Spearman–Brown, leave-one-judge-out rank stability, judge-deviation heatmap,
  Dirichlet weight-sensitivity audit, anchor/known-groups validity checks, and fill-ratio summary.
- `layer2.py`: `python -m dearreader_bench.layer2 <lang> [--probes ...] [--dry-run]` computes the
  DESIGN.md §3 Layer-2 behavioral instruments (offline inflection-tolerant Gag Ledger, vacuity
  checks, autopsy taxonomy, and Layer-2/Layer-1 Spearman convergence; plus optional cached
  model-backed Gag Correspondence double extraction, Detection Asymmetry over `season2_cards.json`,
  and within-judge Payoff Lift).
- `lesions.py`: `python -m dearreader_bench.lesions <lang>` runs the DESIGN.md §6 controlled
  lesion battery (`pad`, `truncate`, `gag_shuffle`, `explain_joke`, `scene_contradict`,
  `canary_leak`) and null-calibration checks.

**First real run, 2026-11-16, Japanese only, a seed and not a result.** `submissions/` holds
eight systems for `ja` (Claude Sonnet 5.5, Gemini 4 Hydrogen, GPT-6.1 Terra, Ernie 5.5 Flash,
two Nemotron models, and the literal and source-withheld anchors on Nemotron 3 Ultra), all run
through `runner.py` over OpenRouter. They were judged by DeepSeek v4.1 Flash, Qwen 3.8 Flash
and Claude Haiku 5.5 with reasoning switched off (it was about 90% of judge cost). Output is in
`results/ja/` (gitignored). None of `DESIGN.md` §6 has been run, so the table must not be
published as a result. What the run taught:

- OpenRouter keeps a stalled request open with keep-alive whitespace, so `providers.py`
  enforces a total deadline; judge calls get 120 seconds and a retry.
- Some judges cannot turn reasoning off (GLM 5.3 Flash, Mistral Large 4 answer HTTP 400) and a
  new account is limited to 20 requests a minute on OpenAI's small models.
- Grok 4.7 did not return the script within 25 minutes and is not in the roster.
- There is no pinned open-weight mid-tier anchor yet, and four of eight systems are Nvidia's.

Not built (`DESIGN.md` §9 steps 4 to 6): the flattening probe (Layer-2), the TTS criterion study,
and the human sample. Remaining gaps inside what is built:

- There is no default pinned open-weight mid-tier anchor configured in code yet (pass
  `--pinned-anchor <system>` to `judge.py` / `audit.py` to check its presence).
- The site still renders only the README; there is no leaderboard page.

Still owed on the corpus: human edit of season 2, second annotator on the joke cards,
pre-registering the language slate.

## Rules that are not negotiable

- **Never add Brad Neely's text** or any transcript of the real work to this repo, its tests, its
  site or its results. The public track runs only on the original synthetic corpus in `data/`.
  The private track takes a user-supplied transcript at run time and stores none of it.
- **Licenses are split by work type:** code and docs are Apache-2.0 (`LICENSE`); the corpus in
  `data/` and system translations of it are CC BY 4.0 (`data/LICENSE`). New corpus material goes
  under `data/`.
- **No API keys or tokens in the repo.** `results/` is gitignored.
- Do not present a number as a result until the validation program in `DESIGN.md` §6 supports it.

## Commands

```sh
uv run --no-project --with pytest --with pydantic --with-editable . pytest -q   # tests (no uv.lock left behind)
uvx ruff check . && uvx ruff format .               # lint and format
uv run build_site.py                                # render README.md -> site/index.html
```

Use `uv`, never pip or venv directly. The README's Status section still says
`pip install -e '.[dev]' && pytest`; that line and the project's packaging (setuptools, no
`uv.lock` committed) have not been moved to uv yet.

## Conventions

- Type hints on all public functions. `logging`, not `print()`.
- Tests in `tests/`, pytest. Keep files small and focused.
- Default branch `main`. Git over SSH for clone, push and pull; `gh` for PRs and issues.
- Commit messages: short, imperative, about why.
- For a complex change, present a plan and get approval before editing.

## The site

- Live at **https://dear-reader-bench.5x5x5x5.dev**, first deployed 2026-11-16 from the README
  as it stood then.
- It is a Cloudflare Worker serving static files only. `wrangler.jsonc` points at `./site`,
  which is gitignored and produced by `build_site.py` from `README.md`. Editing the README and
  redeploying is how the page changes today.
- Deploy: `uv run build_site.py && npx wrangler deploy`. This needs `CLOUDFLARE_API_TOKEN` and
  `CLOUDFLARE_ACCOUNT_ID` in the environment. If they are missing, stop and ask; do not use
  `wrangler login` or `--temporary` as a workaround. Never print or commit the token.
- Run `npx wrangler deploy --dry-run` first. Check `npx wrangler <command> --help` before using
  a subcommand or flag; wrangler changes often.
- There is no CI deploy. Deploying is a manual step.
- The zone `5x5x5x5.dev` belongs to the owner's other projects. Its apex and `www` redirect to
  danielsiegle.com; do not touch DNS records or redirect rules on the zone. The custom domain
  for this Worker is created by wrangler from `wrangler.jsonc`, and that is the only change
  this repo should make there.
- When the site grows beyond the README (a leaderboard, sample outputs), replace
  `build_site.py` instead of layering on it. It is a 50-line placeholder.

## Related

- Owner's profile and project index: https://danielsiegle.com and https://github.com/5x5x5x5.
- Sibling project with the same source material: https://github.com/5x5x5x5/commentary-track.
