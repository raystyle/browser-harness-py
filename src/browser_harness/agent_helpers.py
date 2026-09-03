"""Legacy import name for browser_helpers (renamed in v0.6.8).

Kept for one release so workspace copies and external code doing
``from browser_harness.agent_helpers import ...`` keep working; the merge
loader itself reads browser_helpers.
"""

from .browser_helpers import *  # noqa: F401,F403
