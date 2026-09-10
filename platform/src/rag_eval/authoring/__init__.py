"""Private-document dataset authoring, isolated from Evaluation Core.

The package deliberately owns editable local authoring state only.  Formal
publication crosses into the immutable Benchmark Release store.
"""

from rag_eval.authoring.service import AuthoringService

__all__ = ["AuthoringService"]
