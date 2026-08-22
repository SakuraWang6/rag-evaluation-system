from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
SIBLING_PLATFORM = REPOSITORY.parent / "rag-eval-platform" / "src"
if SIBLING_PLATFORM.is_dir():
    sys.path.insert(0, str(SIBLING_PLATFORM))
sys.path.insert(0, str(REPOSITORY / "lightrag" / "src"))
sys.path.insert(0, str(REPOSITORY / "rag_anything" / "src"))
