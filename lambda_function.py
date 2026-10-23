import base64
import json
import response
from mcp_request import McpRequest, RpcError, check_protocol
from mcp_server import dispatch


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(status_code)
        self.status_code = status_code


def lambda_handler(event, context):
    try:
        headers = require_post_headers(event)
        message = read_message(event)
    except HttpError as http_error:
        return response.http(http_error.status_code)

    request = McpRequest(message, headers, caller=iam_caller_label(event))

    if request.is_notification:
        return response.http(202 if request.is_legacy_client else 400)

    try:
        if not request.is_legacy_client:
            check_protocol(request)
        handler_result = dispatch(request)
        return response.result(request, handler_result)
    except RpcError as rpc_error:
        return response.error(request, rpc_error)


def require_post_headers(event):
    http_context = (event.get('requestContext') or {}).get('http') or {}
    http_method = (http_context.get('method') or 'POST').upper()
    if http_method != 'POST':
        raise HttpError(405)

    headers = {
        header_name.lower(): header_value
        for header_name, header_value in (event.get('headers') or {}).items()
    }
    if 'origin' in headers:
        raise HttpError(403)
    return headers


def read_message(event):
    body = event.get('body') or ''
    try:
        if event.get('isBase64Encoded') and body:
            body = base64.b64decode(body).decode()
        message = json.loads(body)
    except ValueError:
        raise HttpError(400)
    if not isinstance(message, dict) or not isinstance(message.get('method'), str):
        raise HttpError(400)
    return message


def iam_caller_label(event):
    iam_context = ((event.get('requestContext') or {}).get('authorizer') or {}).get('iam') or {}
    user_arn = iam_context.get('userArn') or ''
    principal_name = user_arn.rsplit('/', 1)[-1]
    if '@' in principal_name:
        return f'{principal_name} ({user_arn})'
    return user_arn or iam_context.get('userId') or 'unknown'
