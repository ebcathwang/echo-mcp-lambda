from contextvars import ContextVar

from mcp.server import MCPServer

mcp = MCPServer("echo-mcp-lambda", version="0.1.0")

caller: ContextVar[str] = ContextVar("iam_caller", default="unknown")


@mcp.tool()
def echo(text: str) -> str:
    """Return the text you were given, plus the IAM caller."""
    return f"{text}\nfrom {caller.get()}"
