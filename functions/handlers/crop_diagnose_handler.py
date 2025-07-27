# This module supports dual registration: Flask routes for local dev, and Google Cloud Functions for deployment.
# Use register_crop_diagnose_routes(app) for Flask, and @https_fn.on_request() in main.py for GCF.
import base64
from collections import OrderedDict
from utils.request_utils import get_auth_token, validate_auth_token, get_request_id, get_field
from utils.response_utils import create_error_response, create_success_response, ordered_json_response
from utils.env_utils import is_local_environment
from collections import OrderedDict
from utils.response_utils import ordered_json_response, get_request_id
from utils.request_utils import get_field
from firebase_admin import firestore

# --- Supported languages and schema ---
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'Hindi',
    'hi-en': 'Hinglish',
    'kn': 'Kannada'
}
DEFAULT_LANGUAGE = 'en'

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

# --- Request validation ---
def validate_diagnose_request(req, is_local=False):
    try:
        if req.content_type and 'application/json' in req.content_type:
            data = req.get_json(force=True, silent=True)
            if not data:
                return False, "ER105", "Invalid JSON", "Request body must be valid JSON", 400
            if 'user_id' not in data:
                return False, "ER101", "Missing user_id", "user_id is required", 400
            if 'crop' not in data:
                return False, "ER102", "Missing crop", "crop name is required", 400
            if 'image_base64' not in data:
                return False, "ER103", "Missing image_base64", "Base64-encoded image is required", 400
            return True, None, None, None, None
        elif is_local:
            if 'user_id' not in req.form:
                return False, "ER101", "Missing user_id", "user_id is required", 400
            if 'crop' not in req.form:
                return False, "ER102", "Missing crop", "crop name is required", 400
            if 'image' not in req.files:
                return False, "ER103", "Missing image", "crop image is required", 400
            return True, None, None, None, None
        else:
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
                return False, "ER105", "Invalid content type", "multipart/form-data or application/json required", 400
    except Exception as e:
        return False, "ER500", "Validation error", str(e), 500


def extract_request_data(req, is_local=False):
    try:
        if req.content_type and 'application/json' in req.content_type:
            data = req.get_json(force=True, silent=True)
            user_id = data['user_id']
            crop_type = data['crop']
            location = data.get('location', 'Unknown')
            language = data.get('language', DEFAULT_LANGUAGE)
            image_base64 = data.get('image_base64')
            if not image_base64:
                return False, "ER104", "Invalid image_base64", "image_base64 is required", 400, None
            # Remove data URL prefix if present
            if image_base64.startswith('data:image'):
                image_base64 = image_base64.split(',', 1)[-1]
            try:
                image_bytes = base64.b64decode(image_base64)
            except Exception:
                return False, "ER104", "Invalid image_base64", "Could not decode base64 image", 400, None
        elif is_local:
            user_id = req.form['user_id']
            crop_type = req.form['crop']
            location = req.form.get('location', 'Unknown')
            image_file = req.files['image']
            image_bytes = image_file.read()
            language = req.form.get('language', DEFAULT_LANGUAGE)
        else:
            form_data = req.form
            files = req.files
            user_id = form_data['user_id']
            crop_type = form_data['crop']
            location = form_data.get('location', 'Unknown')
            image_file = files['image']
            image_bytes = image_file.read()
            language = form_data.get('language', DEFAULT_LANGUAGE)
        if not image_bytes or len(image_bytes) == 0:
            return False, "ER104", "Invalid image", "Image file is empty", 400, None
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

def to_ordered(data, schema_order):
    if isinstance(data, dict):
        ordered = OrderedDict()
        for key in schema_order:
            if key in data:
                if isinstance(schema_order[key], dict):
                    ordered[key] = to_ordered(data[key], schema_order[key])
                else:
                    ordered[key] = data[key]
        for key in data:
            if key not in ordered:
                ordered[key] = data[key]
        return ordered
    elif isinstance(data, list):
        return [to_ordered(item, schema_order if isinstance(schema_order, dict) else {}) for item in data]
    else:
        return data

def get_mock_diagnosis_result():
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
    user_id = request_data['user_id']
    crop_type = request_data['crop_type']
    location = request_data['location']
    image_bytes = request_data['image_bytes']
    language = request_data.get('language', DEFAULT_LANGUAGE)
    try:
        image_url = upload_image_to_storage(image_bytes, user_id, crop_type)
        vision_analysis = analyze_image_with_vision(image_bytes)
        diagnosis_result = get_gemini_diagnosis(image_bytes, crop_type, vision_analysis, language)
        diagnosis_result = to_ordered(diagnosis_result, DIAGNOSIS_SCHEMA_ORDER)
        nearby_dealers = get_nearby_dealers(location)
        response_data = OrderedDict([
            ("user_id", user_id),
            ("crop", crop_type),
            ("diagnosis_result", diagnosis_result),
            ("nearby_dealer", nearby_dealers),
            ("image_url", image_url),
            ("language", language)
        ])
        return response_data
    except Exception as e:
        raise

# --- Image processing and AI functions ---
def upload_image_to_storage(image_bytes, user_id, crop_type):
    import os
    import time
    if is_local_environment():
        return None
    from firebase_admin import storage
    BUCKET_NAME = os.getenv('GCS_BUCKET', 'cropmind-89afe.appspot.com')
    bucket = storage.bucket(BUCKET_NAME)
    timestamp = str(int(time.time()))
    filename = f"diagnoses/{user_id}/{crop_type}_{timestamp}.jpg"
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type='image/jpeg')
    return blob.public_url

def analyze_image_with_vision(image_bytes):
    from utils.env_utils import is_local_environment, should_import_cloud_services
    if is_local_environment():
        return []
    from google.cloud import vision
    from main import vision_client
    image = vision.Image(content=image_bytes)
    response = vision_client.label_detection(image=image)
    labels = response.label_annotations
    agricultural_labels = []
    for label in labels:
        if any(keyword in label.description.lower() for keyword in 
               ['plant', 'leaf', 'disease', 'fungus', 'spot', 'yellow', 'brown', 'white']):
            agricultural_labels.append({
                'description': label.description,
                'confidence': label.score
            })
    return agricultural_labels

def get_gemini_diagnosis(image_bytes, crop_type, vision_analysis, language=DEFAULT_LANGUAGE):
    import json
    if is_local_environment():
        return get_mock_diagnosis_result()
    import google.generativeai as genai
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
    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": image_base64}])
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    if text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    result = json.loads(text)
    return result

def save_to_firestore(user_id, request_data, response_data, image_url=None):
    from utils.env_utils import is_local_environment
    if is_local_environment():
        return None
    from firebase_admin import firestore
    db = firestore.client()
    doc_ref = db.collection('diagnoses').document()
    doc_data = {
        'user_id': user_id,
        'timestamp': firestore.SERVER_TIMESTAMP,
        'request': request_data,
        'response': response_data,
        'image_url': image_url
    }
    doc_ref.set(doc_data)
    return doc_ref.id

def use_mock_response(req):
    if hasattr(req, 'headers'):
        return req.headers.get('X-Mock-Response', 'false').lower() == 'true'
    elif hasattr(req, 'get'):
        return req.get('X-Mock-Response', 'false').lower() == 'true'
    return False

def handle_diagnose_request(req):
    request_id = get_request_id(req)
    auth_token = get_auth_token(req)
    is_local = is_local_environment()
    is_valid, error_msg = validate_auth_token(auth_token)
    if not is_valid:
        return create_error_response(request_id, "ER100", error_msg, "Auth token required in header.", 401)
    try:
        is_valid, code, message, description, status_code = validate_diagnose_request(req, is_local)
        if not is_valid:
            return create_error_response(request_id, code, message, description, status_code)
        is_valid, code, message, description, status_code, request_data = extract_request_data(req, is_local)
        if not is_valid:
            return create_error_response(request_id, code, message, description, status_code)
        mock_mode = use_mock_response(req)
        if mock_mode:
            response_data = get_mock_diagnosis_result()
            ordered_result = OrderedDict([
                ("user_id", request_data['user_id']),
                ("crop", request_data['crop_type']),
                ("diagnosis_result", response_data),
                ("nearby_dealer", get_nearby_dealers(request_data['location']))
            ])
        else:
            ordered_result = process_diagnosis_request(request_data)
        if not is_local:
            save_to_firestore(
                request_data['user_id'],
                {
                    'crop': request_data['crop_type'],
                    'location': request_data['location']
                },
                ordered_result
            )
        return create_success_response(request_id, ordered_result)
    except Exception as e:
        return create_error_response(request_id, "ER500", "Internal server error", str(e), 500)

# def register_crop_diagnose_routes(app):
#     from flask import request
#     @app.route('/api/diagnose-crop', methods=['POST'])
#     def diagnose_crop():
#         return handle_diagnose_request(request)



def handle_diagnosis_history(req):
    request_id = get_request_id(req)
    user_id = get_field('user_id')
    limit = int(get_field('limit') or 10)
    offset = int(get_field('offset') or 0)
    try:
        db = firestore.client()
        query = db.collection('diagnoses').where('user_id', '==', user_id).order_by('timestamp', direction=firestore.Query.DESCENDING)
        docs = query.offset(offset).limit(limit).stream()
        history = []
        for doc in docs:
            data = doc.to_dict()
            # Convert Firestore timestamp to ISO string if present
            if 'timestamp' in data and hasattr(data['timestamp'], 'isoformat'):
                data['timestamp'] = data['timestamp'].isoformat()
            history.append(data)
        resp = OrderedDict([
            ("status", "success"),
            ("requestId", request_id),
            ("data", OrderedDict([
                ("user_id", user_id),
                ("history", history)
            ]))
        ])
        return ordered_json_response(resp)
    except Exception as e:
        err = OrderedDict([
            ("status", "error"),
            ("requestId", request_id),
            ("error", OrderedDict([
                ("code", "ER500"),
                ("message", "Internal server error"),
                ("description", str(e))
            ]))
        ])
        return ordered_json_response(err, status=500)

def handle_diagnose_crop_json(req):
    if not (req.content_type and 'application/json' in req.content_type):
        return create_error_response(get_request_id(req), "ER105", "Invalid content type", "application/json required", 400)
    try:
        data = req.get_json(force=True, silent=True)
        if not data:
            return create_error_response(get_request_id(req), "ER105", "Invalid JSON", "Request body must be valid JSON", 400)
        user_id = data.get('user_id')
        crop_type = data.get('crop')
        location = data.get('location', 'Unknown')
        language = data.get('language', DEFAULT_LANGUAGE)
        image_base64 = data.get('image_base64')
        if not user_id or not crop_type or not image_base64:
            return create_error_response(get_request_id(req), "ER106", "Missing required fields", "user_id, crop, and image_base64 are required", 400)
        if image_base64.startswith('data:image'):
            image_base64 = image_base64.split(',', 1)[-1]
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception:
            return create_error_response(get_request_id(req), "ER104", "Invalid image_base64", "Could not decode base64 image", 400)
        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE
        request_data = {
            'user_id': user_id,
            'crop_type': crop_type,
            'location': location,
            'image_bytes': image_bytes,
            'language': language
        }
        ordered_result = process_diagnosis_request(request_data)
        return create_success_response(get_request_id(req), ordered_result)
    except Exception as e:
        return create_error_response(get_request_id(req), "ER500", "Internal server error", str(e), 500)

