import uuid
import json
import base64
import tempfile
import os
import time
from collections import OrderedDict
from PIL import Image
import io
from handlers.mandi_handler import (
    handle_mandi_nearby,
    handle_mandi_crop_price,
    handle_mandi_crop_trend,
    handle_mandi_details,
    handle_mandi_search
)
from handlers.crop_diagnose_handler import (handle_diagnose_request, handle_diagnosis_history)
from utils.request_utils import (get_auth_token, validate_auth_token, get_request_id, get_field)
from utils.response_utils import (create_error_response, create_success_response, ordered_json_response)
from utils.env_utils import is_local_environment, is_deployed_environment, should_import_cloud_services, MockHttpsFn

# Load .env for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import firebase_functions only in deployed environment
if is_deployed_environment():
    from firebase_functions import https_fn
else:
    https_fn = MockHttpsFn()

# Set bucket name from environment variable or default
BUCKET_NAME = os.getenv('GCS_BUCKET', 'cropmind-89afe.appspot.com')

# Import Firestore, Storage, Vision, Gemini in both deployed and FORCE_REAL_API=true local runs
if should_import_cloud_services():
    from firebase_admin import initialize_app, firestore, storage
    from google.cloud import vision
    from google.cloud import aiplatform
    import google.generativeai as genai
    # Initialize Firebase Admin SDK only in deployed environment or real local
    import firebase_admin
    if not firebase_admin._apps:
        initialize_app(options={"storageBucket": BUCKET_NAME})
    vision_client = None
    try:
        vision_client = vision.ImageAnnotatorClient()
        genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'your-gemini-api-key'))
    except Exception as e:
        print(f"Failed to initialize Google Cloud clients: {e}")

# --- Common endpoint handlers ---
def handle_ping_request(req):
    """Health check endpoint handler (shared by Flask and GCF)"""
    request_id = get_request_id(req)
    auth_token = get_auth_token(req)
    is_valid, error_msg = validate_auth_token(auth_token)
    if not is_valid:
        return create_error_response(request_id, "ER100", error_msg, "Auth token required in header.", 401)
    return create_success_response(request_id, {"message": "server is up and running"})

def use_mock_response(req):
    """Check if mock response header is set (for testing)"""
    if hasattr(req, 'headers'):
        return req.headers.get('X-Mock-Response', 'false').lower() == 'true'
    elif hasattr(req, 'get'):
        return req.get('X-Mock-Response', 'false').lower() == 'true'
    return False

# --- Google Cloud Functions endpoints (only when not local) ---
if not is_local_environment():
    @https_fn.on_request()
    def ping_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /ping health check"""
        return handle_ping_request(req)

    @https_fn.on_request()
    def diagnose_crop_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/diagnose-crop"""
        return handle_diagnose_request(req)

    @https_fn.on_request()
    def mandi_nearby_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/mandi-nearby"""
        return handle_mandi_nearby(req)

    @https_fn.on_request()
    def mandi_crop_price_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/mandi-crop-price"""
        return handle_mandi_crop_price(req)

    @https_fn.on_request()
    def mandi_crop_trend_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/mandi-crop-trend"""
        return handle_mandi_crop_trend(req)

    @https_fn.on_request()
    def mandi_details_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/mandi-details"""
        return handle_mandi_details(req)

    @https_fn.on_request()
    def mandi_search_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/mandi-search"""
        return handle_mandi_search(req)

    @https_fn.on_request()
    def diagnosis_history_entry(req: https_fn.Request) -> https_fn.Response:
        """GCF: /api/diagnosis-history"""
        return handle_diagnosis_history(req)

# --- Local Flask server for development/testing ---
if __name__ == '__main__':
    from flask import Flask, request, jsonify, Response as FlaskResponse
    import os
    import json
    from collections import OrderedDict

    def to_flask_response(result):
        """Convert handler result to Flask Response if needed."""
        if isinstance(result, FlaskResponse):
            return result
        if hasattr(result, 'mimetype') and hasattr(result, 'content'):
            return FlaskResponse(result.content, status=getattr(result, 'status', 200), mimetype=getattr(result, 'mimetype', 'application/json'))
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result)

    app = Flask(__name__)

    # --- Flask route registrations ---
    @app.route('/ping', methods=['GET'])
    def ping():
        """Flask: /ping health check"""
        result = handle_ping_request(request)
        return to_flask_response(result)

    @app.route('/api/diagnose-crop', methods=['POST'])
    def diagnose_crop():
        """Flask: /api/diagnose-crop"""
        return handle_diagnose_request(request)

    @app.route('/api/mandi-nearby', methods=['POST'])
    def mandi_nearby():
        """Flask: /api/mandi-nearby"""
        return handle_mandi_nearby(request)

    @app.route('/api/mandi-crop-price', methods=['POST'])
    def mandi_crop_price():
        """Flask: /api/mandi-crop-price"""
        return handle_mandi_crop_price(request)

    @app.route('/api/mandi-crop-trend', methods=['POST'])
    def mandi_crop_trend():
        """Flask: /api/mandi-crop-trend"""
        return handle_mandi_crop_trend(request)

    @app.route('/api/mandi-details', methods=['POST'])
    def mandi_details():
        """Flask: /api/mandi-details"""
        return handle_mandi_details(request)

    @app.route('/api/mandi-search', methods=['POST'])
    def mandi_search():
        """Flask: /api/mandi-search"""
        return handle_mandi_search(request)

    @app.route('/api/diagnosis-history', methods=['POST'])
    def diagnosis_history():
        """Flask: /api/diagnosis-history"""
        return handle_diagnosis_history(request)

    # --- Startup log ---
    print("🚀 Starting CropMind API server locally...")
    print(" Health check: http://localhost:8080/ping")
    print(" Disease diagnosis: http://localhost:8080/api/diagnose-crop")
    print(" Mandi endpoints:")
    print("   - Nearby: http://localhost:8080/api/mandi-nearby")
    print("   - Crop price: http://localhost:8080/api/mandi-crop-price")
    print("   - Crop trend: http://localhost:8080/api/mandi-crop-trend")
    print("   - Details: http://localhost:8080/api/mandi-details")
    print("   - Search: http://localhost:8080/api/mandi-search")
    print(" Diagnosis history: http://localhost:8080/api/diagnosis-history")
    print("🔑 Use Authorization header: 'testtoken'")
    print("📝 Test with curl commands below:")
    print()
    print("Health Check:")
    print("curl -X GET http://localhost:8080/ping -H 'Authorization: testtoken'")
    print()
    print("Disease Diagnosis:")
    print("curl -X POST http://localhost:8080/api/diagnose-crop")
    print("  -H 'Authorization: testtoken' ")
    print("  -F 'image=@your_crop_image.jpg' ")
    print("  -F 'crop=tomato' ")
    print("  -F 'user_id=farmer_123' ")
    print("  -F 'location=Bengaluru'")
    print()
    app.run(debug=True, port=8080, host='0.0.0.0')