import base64
import hashlib
import os
import urllib.request
from contextvars import ContextVar

from mcp.server import MCPServer
from mcp.types import BlobResourceContents, EmbeddedResource, ResourceLink, TextResourceContents

mcp = MCPServer("echo-mcp-lambda", version="0.1.0")

caller: ContextVar[str] = ContextVar("iam_caller", default="unknown")

POC_S3_BUCKET = os.environ.get("POC_S3_BUCKET", "cath-temp")
POC_S3_KEY = os.environ.get("POC_S3_KEY", "poc/sample.pdf")
POC_PRESIGN_SECONDS = 3600
POC_CODEX_MAX_BYTES = 1_000_000
POC_LARGE_KEYS = {
    "500mb": ("poc/large-500mb.bin", 524288000),
    "1gb": ("poc/large-1gb.bin", 1073741824),
}


def poc_s3():
    import boto3

    return boto3.client("s3")


def poc_presigned_url(key: str = POC_S3_KEY) -> str:
    return poc_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": POC_S3_BUCKET, "Key": key},
        ExpiresIn=POC_PRESIGN_SECONDS,
    )


def poc_object_bytes() -> bytes:
    return poc_s3().get_object(Bucket=POC_S3_BUCKET, Key=POC_S3_KEY)["Body"].read()


@mcp.tool()
def echo(text: str) -> str:
    """Return the text you were given, plus the IAM caller."""
    return f"{text}\nfrom {caller.get()}"


@mcp.tool()
def poc_download_resource_link() -> ResourceLink:
    """Return a resource_link with a 1-hour S3 pre-signed URL for the PoC PDF."""
    return ResourceLink(
        uri=poc_presigned_url(),
        name="sample.pdf",
        mimeType="application/pdf",
    )


@mcp.tool()
def poc_download_large(size: str) -> ResourceLink:
    """Return a pre-signed link to a large PoC file. size: 500mb or 1gb."""
    item = POC_LARGE_KEYS.get(size)
    if item is None:
        raise ValueError("size must be 500mb or 1gb")
    key, nbytes = item
    return ResourceLink(
        uri=poc_presigned_url(key),
        name=key.rsplit("/", 1)[-1],
        mimeType="application/octet-stream",
        size=nbytes,
    )


@mcp.tool()
def poc_upload_b64(data: str) -> str:
    """Accept a base64 file payload and return its decoded size."""
    return f"bytes={len(base64.b64decode(data, validate=True))}"


@mcp.tool()
def poc_download_b64() -> EmbeddedResource:
    """Return the PoC PDF as an embedded base64 blob."""
    raw = poc_object_bytes()
    return EmbeddedResource(
        resource=BlobResourceContents(
            uri=poc_presigned_url(POC_S3_KEY),
            mimeType="application/pdf",
            blob=base64.b64encode(raw).decode(),
        )
    )


@mcp.tool()
def poc_download_many_md() -> list[EmbeddedResource]:
    """Return 10 small markdown files in one tool result."""
    s3 = poc_s3()
    out: list[EmbeddedResource] = []
    for i in range(10):
        key = f"poc/md/note-{i:02d}.md"
        body = s3.get_object(Bucket=POC_S3_BUCKET, Key=key)["Body"].read().decode()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": POC_S3_BUCKET, "Key": key},
            ExpiresIn=POC_PRESIGN_SECONDS,
        )
        out.append(
            EmbeddedResource(
                resource=TextResourceContents(
                    uri=url,
                    mimeType="text/markdown",
                    text=body,
                )
            )
        )
    return out


@mcp.tool(meta={"openai/fileParams": ["file"]})
def poc_codex_file(file: dict | str) -> str:
    """Accept a Codex provided-file object and fetch download_url."""
    if isinstance(file, str):
        return "error: expected file object with download_url, got path string"
    url = file.get("download_url")
    if not isinstance(url, str) or not url.startswith("https://"):
        return "error: missing https download_url"
    with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as resp:
        data = resp.read(POC_CODEX_MAX_BYTES + 1)
    if len(data) > POC_CODEX_MAX_BYTES:
        return "error: file too large"
    name = file.get("file_name") or ""
    return f"bytes={len(data)} sha256={hashlib.sha256(data).hexdigest()} file_name={name}"
