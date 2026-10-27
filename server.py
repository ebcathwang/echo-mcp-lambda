from contextvars import ContextVar

from mcp.server import MCPServer
from mcp.types import ResourceLink

mcp = MCPServer("echo-mcp-lambda", version="0.1.0")

caller: ContextVar[str] = ContextVar("iam_caller", default="unknown")

# Public HTTPS so a host/browser can GET the bytes (not an MCP-only URI).
POC_DOWNLOAD_URI = "https://httpbin.org/robots.txt"


@mcp.tool()
def echo(text: str) -> str:
    """Return the text you were given, plus the IAM caller."""
    return f"{text}\nfrom {caller.get()}"


@mcp.tool()
def poc_download_resource_link() -> ResourceLink:
    """Return a resource_link to a publicly downloadable file."""
    return ResourceLink(
        uri=POC_DOWNLOAD_URI,
        name="robots.txt",
        mimeType="text/plain",
    )
