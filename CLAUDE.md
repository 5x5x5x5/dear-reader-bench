# dear-reader-bench

An LLM benchmark for translating *Wizard People, Dear Reader*-style comedic narration: does the
humor, voice and running gags survive into another language, and does the result still fit the
time window it has to be spoken in.

## Read first

- `DESIGN.md` is authoritative (v3). Section 9 is the roadmap, in order of leverage.
- `README.md` is the public summary. It is also the website: see "The site" below.
- `RESEARCH.md` and `research/panel/` are background. Do not treat them as the current design.

## Where things stand

Implemented, with 19 passing tests:

- `src/dearreader_bench/schema.py`: segments, joke cards, adaptation jobs, judgments (pydantic v2).
- `rubric.py`: the four judged dimensions, two-condition prompts, weights.
- `speakability.py`: the duration model behind the performability term.
- `btmodel.py`: Davidson Bradley–Terry fit, phi, the DRS composite.
- `data/segments.json`: the public corpus, `pastiche-v0`, 12 segments.

Not built: no translation runner, no judge harness, no results, no leaderboard. Nothing has been
run against a model.

Next, per `DESIGN.md` §9: (1) corpus season 2 with joke cards, then (2) the harness
(adaptation-job protocol, translation runner, judgment cache, `run.lock`).

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
uv run --with pytest --with-editable . pytest -q   # tests
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
