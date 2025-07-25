from flask import Flask, request
from dotenv import load_dotenv
from handlers.ping_handler import handle_ping_request
from handlers.mandi_handler import (
    handle_mandi_nearby,
    handle_mandi_crop_price,
    handle_mandi_crop_trend,
    handle_mandi_details,
    handle_mandi_search
)
from handlers.crop_diagnose_handler import (
    handle_diagnose_request, 
    handle_diagnosis_history,
    handle_detect_animals
    )

from handlers.animal_detect_handler import handle_detect_animals
from handlers.weather_handler import handle_weather_request
from handlers.insurance_handler import handle_insurance_options
from handlers.govt_insurance_handler import handle_govt_schemes 

import os
import firebase_admin

from firebase_admin import initialize_app

BUCKET_NAME = os.getenv('GCS_BUCKET', 'cropmind-89afe.appspot.com')

if not firebase_admin._apps:
    initialize_app(options={
        "storageBucket": BUCKET_NAME,
        "databaseURL": "https://cropmind-89afe-default-rtdb.asia-southeast1.firebasedatabase.app"
    })

load_dotenv()
app = Flask(__name__)

@app.route('/ping', methods=['GET'])
def ping():
    return handle_ping_request(request)

@app.route('/api/diagnose-crop', methods=['POST'])
def diagnose_crop():
    return handle_diagnose_request(request)

@app.route('/api/mandi-nearby', methods=['POST'])
def mandi_nearby():
    return handle_mandi_nearby(request)

@app.route('/api/mandi-crop-price', methods=['POST'])
def mandi_crop_price():
    return handle_mandi_crop_price(request)

@app.route('/api/mandi-crop-trend', methods=['POST'])
def mandi_crop_trend():
    return handle_mandi_crop_trend(request)

@app.route('/api/mandi-details', methods=['POST'])
def mandi_details():
    return handle_mandi_details(request)

@app.route('/api/mandi-search', methods=['POST'])
def mandi_search():
    return handle_mandi_search(request)

@app.route('/api/diagnosis-history', methods=['POST'])
def diagnosis_history():
    return handle_diagnosis_history(request)

@app.route('/api/detect-animal', methods=['POST'])
def detect_animals_entry():
    return handle_detect_animals(request)

@app.route('/api/weather', methods=['GET', 'POST'])
def weather():
    return handle_weather_request(request)

@app.route('/api/govt-schemes', methods=['GET'])
def govt_schemes():
    return handle_govt_schemes(request)

@app.route('/api/insurance-options', methods=['GET'])
def insurance_options():
    return handle_insurance_options(request)

if __name__ == '__main__':
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
