"""Trader package orchestrating execution, guards, trailing and metrics.

Incremental rebuild after legacy purge.
"""
from .core import Trader

__all__ = ["Trader"]
