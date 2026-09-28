# python/otsafety/src/otsafety/__init__.py
"""Target-safety prediction over a biomedical knowledge graph.

EVERY LATER STEP IMPORTS THIS. The contracts, the ingest, the splits, the audit
and the model card all live beneath it; until this existed none of them could be
written, which is why it sat behind a policy release tag for no recorded reason
until G.73 cut that edge.

NOTHING BUT THE RELEASE IS DECLARED HERE. A package root that re-exports its
subpackages makes every import pull the whole tree, and 9.0 will forbid data
from importing models -- a boundary an eager __init__ quietly defeats.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
