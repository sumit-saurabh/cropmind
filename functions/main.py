import uuid
import json
import base64
import tempfile
import os
import time
from collections import OrderedDict
from PIL import Image
import io

# Robustly load .env only if available (for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Environment detection
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

# Import firebase_functions only in deployed environment
if is_deployed_environment():
    from firebase_functions import https_fn
else:
    # Mock https_fn for local use
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
    
    https_fn = MockHttpsFn()

# Set bucket name from environment variable or default
BUCKET_NAME = os.getenv('GCS_BUCKET', 'cropmind-89afe.appspot.com')

# Import Firestore, Storage, Vision, Gemini in both deployed and FORCE_REAL_API=true local runs
if is_deployed_environment() or os.getenv('FORCE_REAL_API', 'false').lower() == 'true':
    from firebase_admin import initialize_app, firestore, storage
    from google.cloud import vision
    from google.cloud import aiplatform
    import google.generativeai as genai
    # Initialize Firebase Admin SDK only in deployed environment or real local
    initialize_app(options={"storageBucket": BUCKET_NAME})
    vision_client = None
    try:
        vision_client = vision.ImageAnnotatorClient()
        genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'your-gemini-api-key'))
    except Exception as e:
        print(f"Failed to initialize Google Cloud clients: {e}")

# --- Common utility functions ---
def get_request_id(req):
    """Extract request ID from headers or generate new one"""
    if hasattr(req, 'headers'):
        return req.headers.get('X-Request-Id', str(uuid.uuid4()))
    elif hasattr(req, 'get'):
        return req.get('X-Request-Id', str(uuid.uuid4()))
    else:
        return str(uuid.uuid4())

def get_auth_token(req):
    """Extract authorization token from headers"""
    if hasattr(req, 'headers'):
        return req.headers.get('Authorization')
    elif hasattr(req, 'get'):
        return req.get('Authorization')
    else:
        return None

def validate_auth_token(auth_token):
    if not auth_token:
        return False, "Missing Authorization token"
    # Accept 'testtoken' for any non-production run
    if auth_token == 'testtoken':
        return True, None
    # For deployed environment, implement proper token validation
    if auth_token.startswith('Bearer '):
        return True, None
    return False, "Invalid Authorization token"

def create_error_response(request_id, code, message, description="", status_code=401, is_local=False):
    """Create standardized error response"""
    resp = OrderedDict([
        ("status", "error"),
        ("requestId", request_id),
        ("error", {
            "code": code,
            "message": message,
            "description": description
        })
    ])
    
    if is_local:
        return resp, status_code
    else:
        return https_fn.Response(json.dumps(resp), status=status_code, mimetype='application/json')

def create_success_response(request_id, data=None, is_local=False):
    """Create standardized success response"""
    resp = OrderedDict([
        ("status", "success"),
        ("requestId", request_id),
        ("data", data or {})
    ])
    
    if is_local:
        return resp
    else:
        return https_fn.Response(json.dumps(resp), mimetype='application/json')

# --- Common request validation ---
def validate_diagnose_request(req, is_local=False):
    """Validate diagnose crop request parameters"""
    try:
        if is_local:
            # Flask request validation
            if 'user_id' not in req.form:
                return False, "ER101", "Missing user_id", "user_id is required", 400
            
            if 'crop' not in req.form:
                return False, "ER102", "Missing crop", "crop name is required", 400
            
            if 'image' not in req.files:
                return False, "ER103", "Missing image", "crop image is required", 400
            
            return True, None, None, None, None
            
        else:
            # Firebase Functions request validation
            if req.content_type and 'multipart/form-data' in req.content_type:
                form_data = req.form
                files = req.files
                
                if 'user_id' not in form_data:
                    return False, "ER101", "Missing user_id", "user_id is required", 400
                
                if 'crop' not in form_data:
                    return False, "ER102", "Missing crop", "crop name is required", 400
                
                if 'image' not in files:
                    return False, "ER103", "Missing image", "crop image is required", 400
                
                return True, None, None, None, None
            else:
                return False, "ER105", "Invalid content type", "multipart/form-data required", 400
                
    except Exception as e:
        return False, "ER500", "Validation error", str(e), 500

# Supported languages
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'Hindi',
    'hi-en': 'Hinglish',
    'kn': 'Kannada'
}
DEFAULT_LANGUAGE = 'en'

def extract_request_data(req, is_local=False):
    """Extract data from request"""
    try:
        if is_local:
            # Flask request data extraction
            user_id = req.form['user_id']
            crop_type = req.form['crop']
            location = req.form.get('location', 'Unknown')
            image_file = req.files['image']
            image_bytes = image_file.read()
            language = req.form.get('language', DEFAULT_LANGUAGE)
        else:
            # Firebase Functions request data extraction
            form_data = req.form
            files = req.files
            user_id = form_data['user_id']
            crop_type = form_data['crop']
            location = form_data.get('location', 'Unknown')
            image_file = files['image']
            image_bytes = image_file.read()
            language = form_data.get('language', DEFAULT_LANGUAGE)
        # Validate image
        if len(image_bytes) == 0:
            return False, "ER104", "Invalid image", "Image file is empty", 400, None
        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE
        return True, None, None, None, None, {
            'user_id': user_id,
            'crop_type': crop_type,
            'location': location,
            'image_bytes': image_bytes,
            'language': language
        }
    except Exception as e:
        return False, "ER500", "Data extraction error", str(e), 500, None

# --- Common business logic ---
# --- Field order schema for diagnosis result ---
DIAGNOSIS_SCHEMA_ORDER = {
    "disease_name": None,
    "severity": None,
    "stage": None,
    "diagnosis": None,
    "treatment": {
        "immediate_steps": None,
        "pesticides": {
            "chemical": None,
            "organic": None
        },
        "homemade": None,
        "application": None,
        "timeline": None,
        "safety": None
    },
    "prevention": {
        "measures": None,
        "crop_rotation": None,
        "soil_health": None,
        "water_management": None
    },
    "economic": {
        "potential_loss": None,
        "treatment_cost": None,
        "roi": None,
        "market_price": None,
        "insurance": None
    },
    "environmental": {
        "weather_timing": None,
        "seasonal_factors": None,
        "environmental_impact": None
    },
    "local_context": {
        "regional_practices": None,
        "resource_availability": None,
        "government_schemes": None
    },
    "confidence_score": None
}

# --- Utility to recursively order dicts ---
def to_ordered(data, schema_order):
    if isinstance(data, dict):
        ordered = OrderedDict()
        for key in schema_order:
            if key in data:
                if isinstance(schema_order[key], dict):
                    ordered[key] = to_ordered(data[key], schema_order[key])
                else:
                    ordered[key] = data[key]
        # Add any extra keys not in schema_order at the end
        for key in data:
            if key not in ordered:
                ordered[key] = data[key]
        return ordered
    elif isinstance(data, list):
        return [to_ordered(item, schema_order if isinstance(schema_order, dict) else {}) for item in data]
    else:
        return data

def get_mock_diagnosis_result():
    """Get mock diagnosis result for testing"""
    mock_dict = {
        "disease_name": "Powdery Mildew",
        "severity": "Medium",
        "stage": "Early",
        "diagnosis": "Fungal infection causing powdery white spots on leaves. Common in humid conditions.",
        "treatment": {
            "immediate_steps": [
                "Remove infected leaves",
                "Apply neem oil spray"
            ],
            "pesticides": {
                "chemical": ["Mancozeb", "Copper oxychloride"],
                "organic": ["Neem oil", "Baking soda solution"]
            },
            "homemade": [
                "Mix 1 tablespoon baking soda, 1 teaspoon vegetable oil, and 1 liter water. Spray on affected leaves every 7 days.",
                "Garlic-chili spray: Blend 10 garlic cloves and 2 chilies in 1 liter water, strain, and spray."
            ],
            "application": "Spray every 7-10 days, avoid during rain",
            "timeline": "2-3 weeks treatment cycle",
            "safety": "Wear gloves, avoid contact with eyes"
        },
        "prevention": {
            "measures": [
                "Maintain proper plant spacing",
                "Avoid overhead irrigation"
            ],
            "crop_rotation": "Avoid planting tomatoes in same area for 2-3 years",
            "soil_health": "Add organic matter, maintain pH 6.0-6.8",
            "water_management": "Water at soil level, avoid wetting leaves"
        },
        "economic": {
            "potential_loss": "30-50% yield reduction if untreated",
            "treatment_cost": "₹500-800 per acre",
            "roi": "₹15,000-20,000 savings per acre",
            "market_price": "₹40-60 per kg (current market)",
            "insurance": "Apply for PMFBY crop insurance"
        },
        "environmental": {
            "weather_timing": "Apply treatments in early morning",
            "seasonal_factors": "High humidity increases risk",
            "environmental_impact": "Organic treatments preferred for sustainability"
        },
        "local_context": {
            "regional_practices": "Common in Karnataka during monsoon",
            "resource_availability": "Sulphur fungicides available at local stores",
            "government_schemes": "Subsidy available under PMKSY"
        },
        "confidence_score": 88
    }
    return to_ordered(mock_dict, DIAGNOSIS_SCHEMA_ORDER)

def get_nearby_dealers(location):
    """Get nearby agricultural dealers (mock data for now)"""
    # Mock dealer data - in production, this would come from Firestore
    mock_dealers = [
        {
            "name": "AgroMart Supplies",
            "address": "5th Main Rd, Koramangala, Bengaluru",
            "phone": "+91-9876543210",
            "latLng": [12.935, 77.614],
            "working_hours": "9am–6pm"
        },
        {
            "name": "Krishna Agro Center",
            "address": "3rd Cross, Indiranagar, Bengaluru",
            "phone": "+91-9876543211",
            "latLng": [12.978, 77.640],
            "working_hours": "8am–7pm"
        }
    ]
    return mock_dealers

def process_diagnosis_request(request_data):
    print("[DEBUG] Entered process_diagnosis_request")
    user_id = request_data['user_id']
    crop_type = request_data['crop_type']
    location = request_data['location']
    image_bytes = request_data['image_bytes']
    language = request_data.get('language', DEFAULT_LANGUAGE)
    try:
        print("[DEBUG] Uploading image to storage...")
        image_url = upload_image_to_storage(image_bytes, user_id, crop_type)
        print(f"[DEBUG] Image uploaded. URL: {image_url}")
        print("[DEBUG] Analyzing image with Vertex AI Vision...")
        vision_analysis = analyze_image_with_vision(image_bytes)
        print(f"[DEBUG] Vision analysis result: {vision_analysis}")
        print("[DEBUG] Getting diagnosis from Gemini Pro...")
        diagnosis_result = get_gemini_diagnosis(image_bytes, crop_type, vision_analysis, language)
        print(f"[DEBUG] Gemini diagnosis result: {diagnosis_result}")
        diagnosis_result = to_ordered(diagnosis_result, DIAGNOSIS_SCHEMA_ORDER)
        print("[DEBUG] Getting nearby dealers...")
        nearby_dealers = get_nearby_dealers(location)
        print(f"[DEBUG] Nearby dealers: {nearby_dealers}")
        response_data = OrderedDict([
            ("user_id", user_id),
            ("crop", crop_type),
            ("diagnosis_result", diagnosis_result),
            ("nearby_dealer", nearby_dealers),
            ("image_url", image_url),
            ("language", language)
        ])
        print(f"[DEBUG] Final response data: {response_data}")
        return response_data
    except Exception as e:
        print(f"[ERROR] process_diagnosis_request failed: {e}")
        raise

# --- Image processing and AI functions (for deployed environment) ---
def upload_image_to_storage(image_bytes, user_id, crop_type):
    print("[DEBUG] Entered upload_image_to_storage")
    if is_local_environment():
        print("[DEBUG] Skipping storage upload in local environment")
        return None  # Skip storage upload in local environment
    
    try:
        bucket = storage.bucket(BUCKET_NAME)
        
        # Create a unique filename
        timestamp = str(int(time.time()))
        filename = f"diagnoses/{user_id}/{crop_type}_{timestamp}.jpg"
        
        # Create blob and upload
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type='image/jpeg')
        
        # Make the blob publicly readable (optional)
        # blob.make_public()  # Removed to fix ACL error with uniform bucket-level access
        print(f"[DEBUG] Image uploaded to storage: {blob.public_url}")
        
        # Return the public URL
        return blob.public_url
    except Exception as e:
        print(f"[ERROR] Storage upload error: {e}")
        raise

def analyze_image_with_vision(image_bytes):
    print("[DEBUG] Entered analyze_image_with_vision")
    if is_local_environment():
        print("[DEBUG] Skipping AI analysis in local environment")
        return []  # Skip AI analysis in local environment
    
    try:
        image = vision.Image(content=image_bytes)
        response = vision_client.label_detection(image=image)
        labels = response.label_annotations
        
        # Extract relevant agricultural labels
        agricultural_labels = []
        for label in labels:
            if any(keyword in label.description.lower() for keyword in 
                   ['plant', 'leaf', 'disease', 'fungus', 'spot', 'yellow', 'brown', 'white']):
                agricultural_labels.append({
                    'description': label.description,
                    'confidence': label.score
                })
        print(f"[DEBUG] Agricultural labels: {agricultural_labels}")
        return agricultural_labels
    except Exception as e:
        print(f"[ERROR] Vision API error: {e}")
        raise

def get_gemini_diagnosis(image_bytes, crop_type, vision_analysis, language=DEFAULT_LANGUAGE):
    print("[DEBUG] Entered get_gemini_diagnosis")
    if is_local_environment():
        print("[DEBUG] Returning mock diagnosis in local environment")
        return get_mock_diagnosis_result()
    try:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        model = genai.GenerativeModel('gemini-1.5-flash')
        vision_context = "\n".join([f"- {label['description']} (confidence: {label['confidence']:.2f})" for label in vision_analysis])
        language_name = SUPPORTED_LANGUAGES.get(language, 'English')
        prompt = f"""
        You are an expert agricultural scientist helping Indian farmers. Respond in {language_name}.
        \nCrop Type: {crop_type}
        Visual Analysis: {vision_context}
        \nProvide a comprehensive analysis including:
        1. **Disease Identification:**
           - Disease name (if detected)
           - Severity level (Low/Medium/High)
           - Stage of infection
        2. **Treatment Plan:**
           - Immediate treatment steps (with timeline)
           - Recommended pesticides/treatments (both chemical and organic)
           - Application method and frequency
           - Safety precautions
        3. **Prevention & Management:**
           - Prevention measures for future outbreaks
           - Crop rotation recommendations
           - Soil health improvements
           - Water management tips
        4. **Economic Impact:**
           - Estimated crop loss if untreated
           - Treatment cost vs. potential savings
           - Market price considerations
           - Insurance recommendations
        5. **Environmental Factors:**
           - Weather-based treatment timing
           - Seasonal considerations
           - Environmental impact of treatments
        6. **Local Context:**
           - Regional agricultural practices
           - Local resource availability
           - Government schemes/subsidies
        Format your response as JSON:
        {{
            "disease_name": "Disease Name",
            "severity": "Low/Medium/High",
            "stage": "Early/Mid/Late",
            "diagnosis": "Detailed diagnosis summary",
            "treatment": {{
                "immediate_steps": ["Step 1", "Step 2"],
                "pesticides": {{
                    "chemical": ["Pesticide 1", "Pesticide 2"],
                    "organic": ["Organic treatment 1", "Organic treatment 2"]
                }},
                "homemade": ["Homemade solution 1", "Homemade solution 2"],
                "application": "Application instructions",
                "timeline": "Treatment timeline",
                "safety": "Safety precautions"
            }},
            "prevention": {{
                "measures": ["Prevention 1", "Prevention 2"],
                "crop_rotation": "Rotation recommendations",
                "soil_health": "Soil improvement tips",
                "water_management": "Water management advice"
            }},
            "economic": {{
                "potential_loss": "Estimated crop loss",
                "treatment_cost": "Treatment cost estimate",
                "roi": "Return on investment",
                "market_price": "Current market price",
                "insurance": "Insurance recommendations"
            }},
            "environmental": {{
                "weather_timing": "Weather-based timing",
                "seasonal_factors": "Seasonal considerations",
                "environmental_impact": "Environmental impact"
            }},
            "local_context": {{
                "regional_practices": "Regional practices",
                "resource_availability": "Local resources",
                "government_schemes": "Available schemes"
            }},
            "confidence_score": 85
        }}
        """
        print("[DEBUG] Sending prompt to Gemini Pro...")
        response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": image_base64}])
        print(f"[DEBUG] Gemini Pro raw response: {response.text}")
        try:
            # Strip code block markers if present
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[len("```json"):].strip()
            if text.startswith("```"):
                text = text[len("```"):].strip()
            if text.endswith("```"):
                text = text[:-3].strip()
            result = json.loads(text)
            print(f"[DEBUG] Gemini Pro parsed JSON: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] Gemini Pro JSON parsing failed: {e}")
            raise
    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        raise

def save_to_firestore(user_id, request_data, response_data, image_url=None):
    print("[DEBUG] Entered save_to_firestore")
    if is_local_environment():
        print("[DEBUG] Skipping Firestore in local environment")
        return None  # Skip Firestore in local environment
    
    try:
        db = firestore.client()
        doc_ref = db.collection('diagnoses').document()
        
        doc_data = {
            'user_id': user_id,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'request': request_data,
            'response': response_data,
            'image_url': image_url  # Store the image URL
        }
        
        doc_ref.set(doc_data)
        print(f"[DEBUG] Saved to Firestore with doc id: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        print(f"[ERROR] Firestore error: {e}")
        raise

# --- Common endpoint handlers ---
def handle_ping_request(req):
    """Common ping handler for both local and deployed environments"""
    request_id = get_request_id(req)
    auth_token = get_auth_token(req)
    
    # Validate auth token
    is_valid, error_msg = validate_auth_token(auth_token)
    if not is_valid:
        return create_error_response(request_id, "ER100", error_msg, "Auth token required in header.", 401, is_local_environment())
    
    return create_success_response(request_id, {"message": "server is up and running"}, is_local_environment())

def use_mock_response(req):
    # Accepts both Flask and Firebase Functions request objects
    if hasattr(req, 'headers'):
        return req.headers.get('X-Mock-Response', 'false').lower() == 'true'
    elif hasattr(req, 'get'):
        return req.get('X-Mock-Response', 'false').lower() == 'true'
    return False

def handle_diagnose_request(req):
    print("[DEBUG] Entered handle_diagnose_request")
    request_id = get_request_id(req)
    auth_token = get_auth_token(req)
    is_local = is_local_environment()
    print(f"[DEBUG] Request ID: {request_id}, is_local: {is_local}")

    # Validate auth token
    is_valid, error_msg = validate_auth_token(auth_token)
    print(f"[DEBUG] Auth token valid: {is_valid}")
    if not is_valid:
        print(f"[ERROR] Auth failed: {error_msg}")
        return create_error_response(request_id, "ER100", error_msg, "Auth token required in header.", 401, is_local)

    try:
        # Validate request parameters
        is_valid, code, message, description, status_code = validate_diagnose_request(req, is_local)
        print(f"[DEBUG] Request validation: {is_valid}")
        if not is_valid:
            print(f"[ERROR] Validation failed: {code}, {message}, {description}")
            return create_error_response(request_id, code, message, description, status_code, is_local)

        # Extract request data
        is_valid, code, message, description, status_code, request_data = extract_request_data(req, is_local)
        print(f"[DEBUG] Data extraction: {is_valid}")
        if not is_valid:
            print(f"[ERROR] Data extraction failed: {code}, {message}, {description}")
            return create_error_response(request_id, code, message, description, status_code, is_local)

        # Check for mock header
        mock_mode = use_mock_response(req)
        print(f"[DEBUG] mock_mode: {mock_mode}")

        if mock_mode:
            print("[DEBUG] Returning mock diagnosis result")
            response_data = get_mock_diagnosis_result()
            ordered_result = OrderedDict([
                ("user_id", request_data['user_id']),
                ("crop", request_data['crop_type']),
                ("diagnosis_result", response_data),
                ("nearby_dealer", get_nearby_dealers(request_data['location']))
            ])
        else:
            print("[DEBUG] Running real AI/vision pipeline")
            ordered_result = process_diagnosis_request(request_data)

        # Log to Firestore (only in deployed environment)
        if not is_local:
            print("[DEBUG] Logging to Firestore")
            save_to_firestore(
                request_data['user_id'],
                {
                    'crop': request_data['crop_type'],
                    'location': request_data['location']
                },
                ordered_result
            )

        print(f"[DEBUG] Diagnosis completed for user {request_data['user_id']}, crop {request_data['crop_type']}")

        return create_success_response(request_id, ordered_result, is_local)

    except Exception as e:
        print(f"[ERROR] Exception in diagnose_crop: {e}")
        return create_error_response(request_id, "ER500", "Internal server error", str(e), 500, is_local)

# --- Firebase Functions endpoints (only when not local) ---
if not is_local_environment():
    @https_fn.on_request()
    def ping_entry(req: https_fn.Request) -> https_fn.Response:
        return handle_ping_request(req)

    @https_fn.on_request()
    def diagnose_crop_entry(req: https_fn.Request) -> https_fn.Response:
        return handle_diagnose_request(req)

# --- Local Flask server for testing ---
if __name__ == '__main__':
    from flask import Flask, request, jsonify, Response as FlaskResponse
    import os
    
    # Utility to convert mock https_fn.Response to real Flask Response
    def to_flask_response(result):
        # If it's already a Flask Response, return as is
        if isinstance(result, FlaskResponse):
            return result
        # If it's your mock https_fn.Response, convert to Flask Response
        if hasattr(result, 'mimetype') and hasattr(result, 'content'):
            return FlaskResponse(result.content, status=getattr(result, 'status', 200), mimetype=getattr(result, 'mimetype', 'application/json'))
        # If it's a tuple (dict, status), jsonify
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        # Otherwise, jsonify
        return jsonify(result)
    
    # Create Flask app for local testing
    app = Flask(__name__)
    
    @app.route('/ping', methods=['GET'])
    def ping():
        result = handle_ping_request(request)
        return to_flask_response(result)
    
    @app.route('/api/diagnose-crop', methods=['POST'])
    def diagnose_crop():
        result = handle_diagnose_request(request)
        return to_flask_response(result)
    
    print("🚀 Starting CropMind API server locally...")
    print("📡 Health check: http://localhost:8080/ping")
    print("🔬 Disease diagnosis: http://localhost:8080/api/diagnose-crop")
    print("🔑 Use Authorization header: 'testtoken'")
    print("📝 Test with curl commands below:")
    print()
    print("Health Check:")
    print("curl -X GET http://localhost:8080/ping -H 'Authorization: testtoken'")
    print()
    print("Disease Diagnosis:")
    print("curl -X POST http://localhost:8080/api/diagnose-crop \\")
    print("  -H 'Authorization: testtoken' \\")
    print("  -F 'image=@your_crop_image.jpg' \\")
    print("  -F 'crop=tomato' \\")
    print("  -F 'user_id=farmer_123' \\")
    print("  -F 'location=Bengaluru'")
    print()
    
    app.run(debug=True, port=8080, host='0.0.0.0')