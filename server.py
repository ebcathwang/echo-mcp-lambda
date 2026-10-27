import base64
import hashlib
import urllib.request
from contextvars import ContextVar

from mcp.server import MCPServer
from mcp.types import BlobResourceContents, EmbeddedResource, ResourceLink

mcp = MCPServer("echo-mcp-lambda", version="0.1.0")

caller: ContextVar[str] = ContextVar("iam_caller", default="unknown")

POC_DOWNLOAD_URI = "https://httpbin.org/robots.txt"
POC_B64_BLOB = base64.b64encode(b"poc b64\n").decode()
POC_B64_URI = f"https://httpbin.org/base64/{POC_B64_BLOB}"
POC_CODEX_MAX_BYTES = 1_000_000


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


@mcp.tool()
def poc_upload_b64(data: str) -> str:
    """Accept a base64 file payload and return its decoded size."""
    return f"bytes={len(base64.b64decode(data, validate=True))}"


@mcp.tool()
def poc_download_b64() -> EmbeddedResource:
    """Return a small file as an embedded base64 blob."""
    return EmbeddedResource(
        resource=BlobResourceContents(
            uri=POC_B64_URI,
            mimeType="text/plain",
            blob=POC_B64_BLOB,
        )
    )
