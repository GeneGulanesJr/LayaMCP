"""Tool registry.

To add a new tool:

1. Create ``laya_mcp/tools/mytool.py`` with a class extending :class:`Tool`.
2. Add an import + entry below.

That's the only edit needed — schemas, routes, and dispatch all derive
from the class.
"""
from .base import Tool
from .email import EmailTool
from .guard import GuardTool
from .moderate import ModerateTool
from .route import RouteTool
from .triage import TriageTool

TOOLS: list[Tool] = [
    GuardTool(),
    RouteTool(),
    ModerateTool(),
    TriageTool(),
    EmailTool(),
]

__all__ = ["TOOLS", "Tool"]