import base64
from dataclasses import dataclass


MCP_PROTOCOL_VERSION = '2026-07-28'


class RpcError(Exception):
    def __init__(self, status_code, code, message, data=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class McpRequest:
    message: dict
    headers: dict
    caller: str

    @property
    def id(self):
        return self.message.get('id')

    @property
    def is_notification(self):
        return 'id' not in self.message

    @property
    def method(self):
        return self.message['method']

    @property
    def params(self):
        params = self.message.get('params')
        return params if isinstance(params, dict) else {}

    @property
    def meta_protocol_version(self):
        request_meta = self.params.get('_meta')
        if not isinstance(request_meta, dict):
            return None
        return request_meta.get('io.modelcontextprotocol/protocolVersion')

    @property
    def is_legacy_client(self):
        # mcp-proxy / MCP SDK 1.x omit Mcp-Method; after initialize they may still
        # send Mcp-Protocol-Version alone, so key off Mcp-Method for legacy mode.
        return not self.headers.get('mcp-method')


def check_protocol(request):
    header_error = _header_error(request)
    if header_error:
        raise RpcError(400, -32020, header_error)
    if request.meta_protocol_version != MCP_PROTOCOL_VERSION:
        raise RpcError(
            400,
            -32022,
            'Unsupported protocol version',
            {'supported': [MCP_PROTOCOL_VERSION], 'requested': request.meta_protocol_version},
        )


def _header_error(request):
    header_version = request.headers.get('mcp-protocol-version')
    header_method = request.headers.get('mcp-method')
    if not header_version or not header_method:
        return 'Missing required header'
    if header_version != request.meta_protocol_version or header_method != request.method:
        return 'Header mismatch'
    if request.method != 'tools/call':
        return None
    mcp_name_header = request.headers.get('mcp-name')
    if mcp_name_header is None:
        return 'Missing required header'
    tool_name = _decode_header(mcp_name_header)
    if tool_name is None or tool_name != request.params.get('name'):
        return 'Header mismatch'
    return None


_BASE64_PREFIX = '=?base64?'
_BASE64_SUFFIX = '?='


def _decode_header(header_value):
    if header_value.startswith(_BASE64_PREFIX) and header_value.endswith(_BASE64_SUFFIX):
        try:
            encoded_text = header_value[len(_BASE64_PREFIX) : -len(_BASE64_SUFFIX)]
            return base64.b64decode(encoded_text).decode()
        except (ValueError, UnicodeDecodeError):
            return None
    return header_value
