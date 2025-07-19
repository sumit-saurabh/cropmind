from utils.request_utils import get_request_id, get_auth_token, validate_auth_token
from utils.response_utils import create_error_response, create_success_response

def handle_ping_request(req):
    """Health check endpoint handler (shared by Flask and GCF)"""
    request_id = get_request_id(req)
    auth_token = get_auth_token(req)
    is_valid, error_msg = validate_auth_token(auth_token)
    if not is_valid:
        return create_error_response(request_id, "ER100", error_msg, "Auth token required in header.", 401)
    return create_success_response(request_id, {"message": "server is up and running"}) 