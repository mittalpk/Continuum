class ValidationError(Exception):
    """Raised when tool input fails validation, before any SQL is issued.

    Maps to an MCP validation error at the protocol layer (docs/api/mcp-tools.md);
    this module doesn't depend on the mcp SDK so it stays testable in isolation.
    """
