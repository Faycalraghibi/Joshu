"""Joshu: a coding agent for the terminal. See joshu.sdk for the Python API."""

__all__ = ["__version__", "Session", "Result", "run"]
__version__ = "0.3.0"


def __getattr__(name):
    # Imported on first use: the agent pulls in tools and config
    if name in ("Session", "Result", "run"):
        from joshu import sdk

        return getattr(sdk, name)
    raise AttributeError(f"module 'joshu' has no attribute {name!r}")
