"""Minimal models for WebTap - removed unnecessary intermediates.

We work directly with CDP events and transform to dicts for display.
"""

# This file is now mostly empty since we removed the Summary dataclasses
# We keep it in case we need actual models later (e.g., for interception)

# The pipeline is now:
# CDP Events → Helpers (correlation) → Table dicts or raw responses
