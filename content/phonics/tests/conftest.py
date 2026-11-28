import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # content/phonics
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))