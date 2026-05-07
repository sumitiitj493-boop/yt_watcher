"""Shared state for active streaming files.

Keeps track of filenames currently being streamed so other routes
can attempt to force-release or be aware of active streams.
"""
from typing import Set

active_streams: Set[str] = set()
