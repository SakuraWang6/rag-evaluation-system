from __future__ import annotations

import sys
from pathlib import Path

MONOREPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MONOREPO / "platform" / "src"))
sys.path.insert(0, str(MONOREPO / "adapters" / "lightrag" / "src"))
sys.path.insert(0, str(MONOREPO / "adapters" / "rag-anything" / "src"))
