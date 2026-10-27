import base64
import hashlib
import io
import json
import os
import unittest
from unittest.mock import patch

from lambda_function import lambda_handler
from server import caller

FUNCTION_HOST = "abc123.lambda-url.us-east-1.on.aws"
ADA = "arn:aws:iam::123456789012:user/ada@example.com"
GRACE = "arn:aws:iam::123456789012:user/grace@example.com"
PDF_BYTES = b"%PDF-1.4 poc"
PDF_URL = "https://cath-temp.s3.amazonaws.com/poc/sample.pdf?X-Amz-Expires=3600"


class LambdaHandlerTests(unittest.TestCase):
    def test_function_url_echo_twice(self):
        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            first = lambda_handler(function_url_event(ADA, "echo", {"text": "hi"}), None)
            second = lambda_handler(function_url_event(GRACE, "echo", {"text": "hi"}), None)

        self.assertEqual(caller.get(), "unknown")
        self.assertEqual(tool_content(first)["text"], f"hi\nfrom ada@example.com ({ADA})")
        self.assertEqual(tool_content(second)["text"], f"hi\nfrom grace@example.com ({GRACE})")

    def test_poc_download_resource_link(self):
        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            with patch("server.poc_presigned_url", return_value=PDF_URL):
                response = lambda_handler(
                    function_url_event(ADA, "poc_download_resource_link", {}), None
                )

        block = tool_content(response)
        self.assertEqual(block["type"], "resource_link")
        self.assertEqual(block["uri"], PDF_URL)
        self.assertEqual(block["name"], "sample.pdf")
        self.assertEqual(block["mimeType"], "application/pdf")

    def test_poc_download_large(self):
        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            with patch("server.poc_presigned_url", return_value=PDF_URL):
                response = lambda_handler(
                    function_url_event(ADA, "poc_download_large", {"size": "500mb"}),
                    None,
                )

        block = tool_content(response)
        self.assertEqual(block["type"], "resource_link")
        self.assertEqual(block["name"], "large-500mb.bin")
        self.assertEqual(block["size"], 524288000)
        self.assertEqual(block["uri"], PDF_URL)

    def test_poc_upload_b64(self):
        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            response = lambda_handler(
                function_url_event(
                    ADA, "poc_upload_b64", {"data": base64.b64encode(b"hi").decode()}
                ),
                None,
            )

        self.assertEqual(tool_content(response)["text"], "bytes=2")

    def test_poc_download_b64(self):
        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            with patch("server.poc_object_bytes", return_value=PDF_BYTES):
                with patch("server.poc_presigned_url", return_value=PDF_URL):
                    response = lambda_handler(
                        function_url_event(ADA, "poc_download_b64", {}), None
                    )

        block = tool_content(response)
        self.assertEqual(block["type"], "resource")
        self.assertEqual(block["resource"]["mimeType"], "application/pdf")
        self.assertEqual(block["resource"]["uri"], PDF_URL)
        self.assertEqual(block["resource"]["blob"], base64.b64encode(PDF_BYTES).decode())

    def test_poc_codex_file_fetches_download_url(self):
        payload = b"codex-file"

        class FakeResp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            with patch("server.urllib.request.urlopen", return_value=FakeResp(payload)):
                response = lambda_handler(
                    function_url_event(
                        ADA,
                        "poc_codex_file",
                        {
                            "file": {
                                "download_url": "https://example.com/f",
                                "file_id": "file_1",
                                "file_name": "f.txt",
                            }
                        },
                    ),
                    None,
                )

        self.assertEqual(
            tool_content(response)["text"],
            f"bytes={len(payload)} sha256={hashlib.sha256(payload).hexdigest()} file_name=f.txt",
        )

    def test_poc_codex_file_rejects_path_string(self):
        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            response = lambda_handler(
                function_url_event(ADA, "poc_codex_file", {"file": "/tmp/x"}),
                None,
            )

        self.assertIn("path string", tool_content(response)["text"])

    def test_poc_download_many_md(self):
        class FakeBody:
            def __init__(self, text):
                self._text = text

            def read(self):
                return self._text.encode()

        class FakeS3:
            def get_object(self, Bucket, Key):
                i = Key.rsplit("-", 1)[-1].removesuffix(".md")
                return {"Body": FakeBody(f"# note-{int(i)}\n")}

            def generate_presigned_url(self, *_args, **_kwargs):
                return PDF_URL

        with patch.dict(os.environ, {"MCP_ALLOWED_HOST": FUNCTION_HOST}):
            with patch("server.poc_s3", return_value=FakeS3()):
                response = lambda_handler(
                    function_url_event(ADA, "poc_download_many_md", {}), None
                )

        body = json.loads(response["body"])
        content = body["result"]["content"]
        self.assertEqual(len(content), 10)
        self.assertEqual(content[0]["type"], "resource")
        self.assertEqual(content[0]["resource"]["mimeType"], "text/markdown")
        self.assertIn("# note-0", content[0]["resource"]["text"])


def tool_content(response):
    if response["statusCode"] != 200:
        raise AssertionError(response)
    body = json.loads(response["body"])
    if body["result"].get("isError"):
        raise AssertionError(body)
    return body["result"]["content"][0]


def function_url_event(user_arn, tool_name, arguments):
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "0"},
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    return {
        "version": "2.0",
        "headers": {
            "host": FUNCTION_HOST,
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "tools/call",
            "mcp-name": tool_name,
        },
        "requestContext": {
            "http": {"method": "POST", "path": "/", "sourceIp": "127.0.0.1"},
            "authorizer": {"iam": {"userArn": user_arn}},
        },
        "body": json.dumps(message),
    }
