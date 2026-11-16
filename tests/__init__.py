"""Test package.

The corruption/recovery tests intentionally trigger error logs; keep the test
output focused on results instead of expected diagnostics.
"""

import logging

logging.getLogger("app").setLevel(logging.CRITICAL)
