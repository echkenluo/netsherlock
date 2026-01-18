"""
API module for NetSherlock webhook endpoints.

Provides FastAPI application for receiving alerts and diagnostic requests.
"""

from .webhook import app, main

__all__ = ["app", "main"]
