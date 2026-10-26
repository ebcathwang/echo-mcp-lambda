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
            first = lambda_handler(function_url_event(ADA), None)
            second = lambda_handler(function_url_event(GRACE), None)

        self.assertEqual(caller.get(), "unknown")
        self.assertEqual(echo_text(first), f"hi\nfrom ada@example.com ({ADA})")
        self.assertEqual(echo_text(second), f"hi\nfrom grace@example.com ({GRACE})")


def echo_text(response):
    if response["statusCode"] != 200:
        raise AssertionError(response)
    body = json.loads(response["body"])
    if body["result"]["isError"]:
        raise AssertionError(body)
    return body["result"]["content"][0]["text"]


def function_url_event(user_arn):
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "echo",
            "arguments": {"text": "hi"},
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
            "mcp-name": "echo",
        },
        "requestContext": {
            "http": {"method": "POST", "path": "/mcp", "sourceIp": "127.0.0.1"},
            "authorizer": {"iam": {"userArn": user_arn}},
        },
        "body": json.dumps(message),
    }
