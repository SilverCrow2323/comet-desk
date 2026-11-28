"""Keep repository-root modules importable for both pytest entry points.

The GitHub Actions workflow invokes the `pytest` console script, whose initial
sys.path can omit the checkout root. Tests import the source tool as a package
without requiring an install step, so add the repository root explicitly.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
root_text = str(ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)
