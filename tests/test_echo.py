import json
import os
import unittest
from unittest.mock import patch

from lambda_function import lambda_handler
from server import caller

FUNCTION_HOST = "abc123.lambda-url.us-east-1.on.aws"
ADA = "arn:aws:iam::123456789012:user/ada@example.com"
GRACE = "arn:aws:iam::123456789012:user/grace@example.com"


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
            response = lambda_handler(
                function_url_event(ADA, "poc_download_resource_link", {}), None
            )

        block = tool_content(response)
        self.assertEqual(block["type"], "resource_link")
        self.assertEqual(block["uri"], "https://httpbin.org/robots.txt")
        self.assertEqual(block["name"], "robots.txt")


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
