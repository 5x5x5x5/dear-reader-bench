# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2"]
# ///
"""Build the static site into site/ for dear-reader-bench.5x5x5x5.dev.

uv run build_site.py
npx wrangler deploy --dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dearreader_bench.sitegen import build_site, main


def build() -> Path:
    """Build site/index.html (and companion static assets) and return its path."""
    return build_site(out_dir=ROOT / "site")


if __name__ == "__main__":
    sys.exit(main())
