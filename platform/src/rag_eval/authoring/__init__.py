"""Private-document dataset authoring, isolated from Evaluation Core.

The package deliberately owns editable local authoring state only.  A future
exporter is responsible for crossing into the immutable Dataset Bundle store.
"""

from rag_eval.authoring.service import AuthoringService

__all__ = ["AuthoringService"]
