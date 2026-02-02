"""
Entry point kept for backward compatibility:

  python mcp_tavily_demo.py

Implementation has been modularized into the `verifier2/` package.
"""

from __future__ import annotations

from verifier2.cli import main


if __name__ == "__main__":
    raise SystemExit(main())


