from mcp_request import MCP_PROTOCOL_VERSION, RpcError


LEGACY_DEFAULT_PROTOCOL = '2025-11-25'

SERVER_INFO = {'name': 'echo-mcp-lambda', 'version': '0.1.0'}

TOOL_SPECS = [
    {
        'name': 'echo',
        'description': 'Return the text you were given, plus the IAM caller.',
        'inputSchema': {
            'type': 'object',
            'properties': {'text': {'type': 'string'}},
            'required': ['text'],
        },
    }
]


class _ToolInputError(Exception):
    pass


def dispatch(request):
    handlers = LEGACY_HANDLERS if request.is_legacy_client else HANDLERS
    method_handler = handlers.get(request.method)
    if method_handler is None:
        raise RpcError(404, -32601, f'Method not found: {request.method}')
    return method_handler(request)


def _handle_initialize(request):
    return {
        'protocolVersion': request.params.get('protocolVersion') or LEGACY_DEFAULT_PROTOCOL,
        'capabilities': {'tools': {}},
        'serverInfo': SERVER_INFO,
    }


def _handle_ping(request):
    return {}


def _handle_discover(request):
    # Legacy clients get resultType here too.
    return {
        'resultType': 'complete',
        'supportedVersions': [MCP_PROTOCOL_VERSION],
        'capabilities': {'tools': {}},
        '_meta': {'io.modelcontextprotocol/serverInfo': SERVER_INFO},
    }


def _handle_tools_list(request):
    if request.is_legacy_client:
        return {'tools': TOOL_SPECS}
    return {'tools': TOOL_SPECS, 'ttlMs': 3600000, 'cacheScope': 'public'}


def _handle_tools_call(request):
    tool_name = request.params.get('name')
    tool_function = TOOLS.get(tool_name)
    if tool_function is None:
        raise RpcError(200, -32602, f'Unknown tool: {tool_name}')

    raw_arguments = request.params.get('arguments') or {}
    arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
    try:
        output_text = tool_function(arguments, request.caller)
        is_error = False
    except _ToolInputError as tool_error:
        output_text = str(tool_error)
        is_error = True
    return {'content': [{'type': 'text', 'text': output_text}], 'isError': is_error}


HANDLERS = {
    'server/discover': _handle_discover,
    'tools/list': _handle_tools_list,
    'tools/call': _handle_tools_call,
}

LEGACY_HANDLERS = {
    **HANDLERS,
    'initialize': _handle_initialize,
    'ping': _handle_ping,
}


def _echo(arguments, caller):
    text = arguments.get('text')
    if not isinstance(text, str):
        raise _ToolInputError('echo requires a string argument named text')
    return f'{text}\nfrom {caller}'


TOOLS = {'echo': _echo}
