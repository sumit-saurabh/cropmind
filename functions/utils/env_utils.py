
import os

def is_local_environment():
    """Check if running in local development environment, with override for real API testing."""
    if os.getenv('FORCE_REAL_API', 'false').lower() == 'true':
        return False
    return os.getenv('FUNCTIONS_EMULATOR') is None and os.getenv('FUNCTION_TARGET') is None

def is_deployed_environment():
    """True only if running in Firebase Functions (not local, not FORCE_REAL_API)"""
    return os.getenv('FUNCTIONS_EMULATOR') is not None or os.getenv('FUNCTION_TARGET') is not None

def should_import_cloud_services():
    """Determine if Google Cloud services should be imported."""
    return is_deployed_environment() or os.getenv('FORCE_REAL_API', 'false').lower() == 'true'

class MockHttpsFn:
    class Request:
        pass
    class Response:
        def __init__(self, content, status=200, mimetype='application/json'):
            self.content = content
            self.status = status
            self.mimetype = mimetype

    @staticmethod
    def on_request():
        def decorator(func):
            return func
        return decorator

