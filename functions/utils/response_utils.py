import uuid
import json
from flask import Response
from collections import OrderedDict

def get_request_id(req):
    """Extract request ID from headers or generate new one"""
    if hasattr(req, 'headers'):
        return req.headers.get('X-Request-Id', str(uuid.uuid4()))
    elif hasattr(req, 'get'):
        return req.get('X-Request-Id', str(uuid.uuid4()))
    else:
        return str(uuid.uuid4())

def ordered_json_response(data, status=200):
    return Response(json.dumps(data, ensure_ascii=False), status=status, mimetype='application/json')

def create_error_response(request_id, code, message, description="", status_code=401):
    """Create standardized error response (Flask only)"""
    resp = OrderedDict([
        ("status", "error"),
        ("requestId", request_id),
        ("error", {
            "code": code,
            "message": message,
            "description": description
        })
    ])
    return ordered_json_response(resp, status=status_code)

def create_success_response(request_id, data=None):
    """Create standardized success response (Flask only)"""
    resp = OrderedDict([
        ("status", "success"),
        ("requestId", request_id),
        ("data", data or {})
    ])
    return ordered_json_response(resp)