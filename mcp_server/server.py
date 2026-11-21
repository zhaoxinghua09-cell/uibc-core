"""Compatibility shim: the MCP server lives in uibc_core.mcp_server.

Kept so existing checkouts and clients configured with
``python -m mcp_server.server`` keep working. New installs should use
the ``uibc-mcp`` console script (``pip install uibc-core``).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.mcp_server import TOOLS, TOOL_FUNCS, handle, main  # noqa: E402,F401

if __name__ == "__main__":
    main()
