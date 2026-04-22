"""Shared utilities for the ipoipo downloader pipeline.

This package provides helper modules used across all pipeline stages:

Submodules:
    headers     — Browser-like HTTP header generation with random User-Agent rotation.
    sanitize    — Filename cleaning (removing illegal characters), timestamp extraction,
                  and page count parsing from report titles.
    helpers     — Retry decorator with exponential backoff, jitter-based sleep,
                  and URL validation helpers.

Usage::

    from utils.headers import get_headers
    from utils.sanitize import sanitize_filename, extract_timestamp
    from utils.helpers import retry, jitter_sleep
"""
