import os

from mangum import Mangum
from mcp.server.transport_security import TransportSecuritySettings

from server import caller, mcp


def lambda_handler(event, context):
    token = caller.set(iam_caller_label(event))
    try:
        app = mcp.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts()),
        )
        return Mangum(app)(event, context)
    finally:
        caller.reset(token)


def allowed_hosts():
    host = os.environ.get("MCP_ALLOWED_HOST", "").strip()
    if not host:
        return []
    if host.endswith(":*"):
        return [host]
    return [host, f"{host}:*"]


def iam_caller_label(event):
    iam_context = ((event.get("requestContext") or {}).get("authorizer") or {}).get("iam") or {}
    user_arn = iam_context.get("userArn") or ""
    principal_name = user_arn.rsplit("/", 1)[-1]
    if "@" in principal_name:
        return f"{principal_name} ({user_arn})"
    return user_arn or iam_context.get("userId") or "unknown"
