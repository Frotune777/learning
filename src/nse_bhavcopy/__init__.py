"""
File: src/nse_bhavcopy/__init__.py
Purpose: Package initialization for the local NSE Bhavcopy downloader and processor.

Dependencies:
External:
- None
Internal:
- src.storage.downloader: Core downloader module

Key Components:
Classes:
- None
Functions:
- None

Last Modified: 2026-05-26
Modified By: Fortune

Open Tasks:
- None

Related Files:
- src/nse_bhavcopy/downloader.py: Core downloader module
"""

from src.storage.downloader import BhavcopyDownloader

__all__ = ["BhavcopyDownloader"]
