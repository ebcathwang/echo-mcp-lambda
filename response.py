import json


def http(status_code, body='', headers=None):
    payload = {'statusCode': status_code, 'body': body}
    if headers:
        payload['headers'] = headers
    return payload


def _jsonrpc(status_code, message_id, **outcome):
    envelope = {'jsonrpc': '2.0', 'id': message_id, **outcome}
    return http(status_code, json.dumps(envelope), headers={'content-type': 'application/json'})


def result(request, handler_result):
    rpc_result = (
        handler_result
        if request.is_legacy_client
        else {'resultType': 'complete', **handler_result}
    )
    return _jsonrpc(200, request.id, result=rpc_result)


def error(request, rpc_error):
    error_object = {'code': rpc_error.code, 'message': rpc_error.message}
    if rpc_error.data is not None:
        error_object['data'] = rpc_error.data
    return _jsonrpc(rpc_error.status_code, request.id, error=error_object)
