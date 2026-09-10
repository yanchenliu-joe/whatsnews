"""Editorial engine configuration."""

import os


def editorial_engine_enabled() -> bool:
    """Return True unless ENABLE_EDITORIAL_ENGINE is explicitly false."""
    return os.getenv("ENABLE_EDITORIAL_ENGINE", "true").lower() != "false"
