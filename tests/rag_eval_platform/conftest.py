from __future__ import annotations

import sys
from pathlib import Path

PLATFORM_SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(PLATFORM_SRC))
