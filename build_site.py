# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown"]
# ///
"""Render README.md to site/index.html, the page served at dear-reader-bench.5x5x5x5.dev.

uv run build_site.py && npx wrangler deploy
"""

from pathlib import Path

import markdown

REPO = "https://github.com/5x5x5x5/dear-reader-bench"
ROOT = Path(__file__).parent

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>dear-reader-bench</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 17px/1.6 system-ui, sans-serif; max-width: 44rem; margin: 2rem auto; padding: 0 1rem; }}
  pre, table {{ display: block; overflow-x: auto; }}
  pre {{ padding: 1rem; border: 1px solid; }}
  th, td {{ padding: .3rem .6rem; border: 1px solid; text-align: left; }}
  table {{ border-collapse: collapse; }}
</style>
{body}
<p><a href="{repo}">{repo}</a></p>
</html>
"""


def build() -> Path:
    """Write site/index.html from README.md and return its path."""
    body = markdown.markdown(
        (ROOT / "README.md").read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code"],
    )
    out = ROOT / "site" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(PAGE.format(body=body, repo=REPO), encoding="utf-8")
    return out


if __name__ == "__main__":
    html = build().read_text(encoding="utf-8")
    assert "<table>" in html and "<h1>dear-reader-bench</h1>" in html, (
        "README did not render"
    )
