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
from handlers.ping_handler import handle_ping_request
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
# if is_deployed_environment():
#     from firebase_functions import https_fn
# else:
#     https_fn = MockHttpsFn()
from firebase_functions import https_fn

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
def use_mock_response(req):
    """Check if mock response header is set (for testing)"""
    if hasattr(req, 'headers'):
        return req.headers.get('X-Mock-Response', 'false').lower() == 'true'
    elif hasattr(req, 'get'):
        return req.get('X-Mock-Response', 'false').lower() == 'true'
    return False

# --- Google Cloud Functions endpoints ---
@https_fn.on_request()
def ping_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /ping health check"""
    return handle_ping_request(req)

@https_fn.on_request(memory=512)
def diagnose_crop_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/diagnose-crop"""
    return handle_diagnose_request(req)

@https_fn.on_request(memory=512)
def diagnosis_history_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/diagnosis-history"""
    return handle_diagnosis_history(req)

@https_fn.on_request(memory=512)
def mandi_nearby_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/mandi-nearby"""
    return handle_mandi_nearby(req)

@https_fn.on_request(memory=512)
def mandi_crop_price_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/mandi-crop-price"""
    return handle_mandi_crop_price(req)

@https_fn.on_request(memory=512)
def mandi_crop_trend_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/mandi-crop-trend"""
    return handle_mandi_crop_trend(req)

@https_fn.on_request(memory=512)
def mandi_details_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/mandi-details"""
    return handle_mandi_details(req)

@https_fn.on_request(memory=512)
def mandi_search_entry(req: https_fn.Request) -> https_fn.Response:
    """GCF: /api/mandi-search"""
    return handle_mandi_search(req)

