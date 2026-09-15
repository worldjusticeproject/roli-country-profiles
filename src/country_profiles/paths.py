"""Where generated files go.

``data/`` holds only the input workbook; rendered PDFs are build output and land
in ``output/`` at the repo root (git-ignored).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output"
