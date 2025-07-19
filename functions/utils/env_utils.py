
import os

def is_local_environment():
    env = os.getenv('ENV', os.getenv('ENVIRONMENT', 'production')).lower()
    print(f"[ENV_UTILS] ENV/ENVIRONMENT: {env}")
    result = env == 'local'
    print(f"[ENV_UTILS] is_local_environment: {result}")
    return result

def is_deployed_environment():
    env = os.getenv('ENV', os.getenv('ENVIRONMENT', 'production')).lower()
    print(f"[ENV_UTILS] ENV/ENVIRONMENT: {env}")
    result = env == 'production'
    print(f"[ENV_UTILS] is_deployed_environment: {result}")
    return result

def should_import_cloud_services():
    force_real_api = os.getenv('FORCE_REAL_API', 'false').lower() == 'true'
    deployed = is_deployed_environment()
    print(f"[ENV_UTILS] FORCE_REAL_API: {force_real_api}, is_deployed_environment: {deployed}")
    result = deployed or force_real_api
    print(f"[ENV_UTILS] should_import_cloud_services: {result}")
    return result

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

