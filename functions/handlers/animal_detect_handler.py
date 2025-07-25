import logging
import traceback
from utils.response_utils import create_error_response, create_success_response
from utils.env_utils import should_import_cloud_services
import os
import base64
import requests
from firebase_admin import firestore
from utils.request_utils import get_request_id

def handle_detect_animals(req):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("detect_animals")
    logger.info("Received request for animal detection")
    # Import vision only if needed
    if should_import_cloud_services():
        from google.cloud import vision
        from main import vision_client
        from firebase_admin import firestore, db
    else:
        logger.error("Vision API not available in local/mock mode")
        return create_error_response(get_request_id(req), "ER500", "Vision API not available in local/mock mode", "", 500)

    try:
        logger.info(f"Request content type: {req.content_type}")
        if not (req.content_type and 'application/json' in req.content_type):
            logger.error("Invalid content type")
            return create_error_response(get_request_id(req), "ER105", "Invalid content type", "application/json required", 400)
        data = req.get_json(force=True, silent=True)
        logger.info(f"Request JSON: {data}")
        if not data:
            logger.error("Invalid JSON in request body")
            return create_error_response(get_request_id(req), "ER105", "Invalid JSON", "Request body must be valid JSON", 400)
        image_base64 = data.get('image_base64')
        image_url = data.get('image_url')
        lat = data.get('lat')
        lng = data.get('lng')
        timestamp = data.get('timestamp')
        camera_id = data.get('camera_id')
        farm_id = data.get('farm_id')
        logger.info(f"lat: {lat}, lng: {lng}, timestamp: {timestamp}, camera_id: {camera_id}, farm_id: {farm_id}")
        # Prepare image for Vision API
        if image_base64:
            if image_base64.startswith('data:image'):
                image_base64 = image_base64.split(',', 1)[-1]
            try:
                image_bytes = base64.b64decode(image_base64)
            except Exception as e:
                logger.error(f"Could not decode base64 image: {e}")
                return create_error_response(get_request_id(req), "ER104", "Invalid image_base64", "Could not decode base64 image", 400)
            image = vision.Image(content=image_bytes)
            logger.info("Image prepared from base64")
        elif image_url:
            image = vision.Image()
            image.source.image_uri = image_url
            logger.info(f"Image prepared from URL: {image_url}")
        else:
            logger.error("Missing image in request")
            return create_error_response(get_request_id(req), "ER106", "Missing image", "Provide image_base64 or image_url", 400)
        # Call Vision API
        logger.info("Calling Vision API for label detection")
        response = vision_client.label_detection(image=image)
        labels = response.label_annotations
        logger.info(f"Vision API labels: {[label.description for label in labels]}")
        # More flexible animal detection
        animal_keywords = [
            "cow", "buffalo", "bull", "ox", "boar", "nilgai", "goat", "pig", "deer",
            "bovinae", "livestock", "herd", "cattle", "animal"
        ]
        detected = {}
        for label in labels:
            desc = label.description.lower()
            for animal in animal_keywords:
                animal_lc = animal.lower()
                if (animal_lc in desc or desc in animal_lc) and label.score >= 0.6:
                    detected[animal] = max(detected.get(animal, 0), float(label.score))
        logger.info(f"Detected animals: {detected}")
        if detected:
            result = {
                "status": "animal_detected",
                "labels": list(detected.keys()),
                "confidence": detected,
                "alert_level": "high"
            }
        else:
            result = {
                "status": "clear",
                "labels": [],
                "alert_level": "none"
            }
        # Build event record
        label_str = ", ".join(result["labels"]) if result["labels"] else None
        # Fetch farm and farmer details from Firestore
        farm_name = None
        farm_address = None
        farmer_id = None
        farmer_language = 'en'
        farmer_name = None
        farmer_mobile = None
        farm_doc = None
        if should_import_cloud_services() and farm_id:
            try:
                # Try direct doc fetch
                farm_doc_ref = firestore.client().collection('farms').document(farm_id)
                farm_doc = farm_doc_ref.get()
                if not farm_doc.exists:
                    # Query by farm_id field if doc not found
                    farm_query = firestore.client().collection('farms').where('farm_id', '==', farm_id).limit(1).get()
                    if farm_query:
                        farm_doc = farm_query[0]
                if farm_doc and farm_doc.exists:
                    farm_data = farm_doc.to_dict()
                    farm_name = farm_data.get('name')
                    farm_address = farm_data.get('address')
                    farmer_id = farm_data.get('farmer_id')
            except Exception as e:
                logger.error(f"Could not fetch farm details: {e}")
        farmer_doc = None
        if should_import_cloud_services() and farmer_id:
            try:
                # Try direct doc fetch
                farmer_doc_ref = firestore.client().collection('farmers').document(farmer_id)
                farmer_doc = farmer_doc_ref.get()
                if not farmer_doc.exists:
                    # Query by farmer_id field if doc not found
                    farmer_query = firestore.client().collection('farmers').where('farmer_id', '==', farmer_id).limit(1).get()
                    if farmer_query:
                        farmer_doc = farmer_query[0]
                if farmer_doc and farmer_doc.exists:
                    farmer_data = farmer_doc.to_dict()
                    farmer_language = farmer_data.get('language', 'en')
                    farmer_name = farmer_data.get('name')
                    farmer_mobile = farmer_data.get('mobile')
            except Exception as e:
                logger.error(f"Could not fetch farmer details: {e}")
        notification_message = build_notification_message(
            result["status"], farm_id, camera_id, lat, lng, timestamp, farmer_language, label_str, farmer_name, farm_name, farm_address
        )
        event_record = {
            "status": result["status"],
            "labels": result["labels"],
            "confidence": result.get("confidence", {}),
            "alert_level": result["alert_level"],
            "lat": lat,
            "lng": lng,
            "timestamp": timestamp,
            "camera_id": camera_id,
            "farm_id": farm_id,
            "image_url": image_url if image_url else None,
            "notification_message": notification_message,
            "farmer_id": farmer_id,
            "farmer_language": farmer_language,
            "farmer_name": farmer_name,
            "farmer_mobile": farmer_mobile,
            "farm_name": farm_name,
            "farm_address": farm_address
        }
        logger.info(f"Event record to store: {event_record}")
        # Store in Firestore
        if should_import_cloud_services():
            db_firestore = firestore.client()
            db_firestore.collection("animal_detections").add(event_record)
            logger.info("Event stored in Firestore")
            # Push to Realtime Database for notification
            if farm_id:
                db.reference(f"/animal_alerts/{farm_id}").push(event_record)
                logger.info(f"Event pushed to /animal_alerts/{farm_id} in Realtime Database")
            elif camera_id:
                db.reference(f"/animal_alerts/{camera_id}").push(event_record)
                logger.info(f"Event pushed to /animal_alerts/{camera_id} in Realtime Database")
            else:
                db.reference(f"/animal_alerts/general").push(event_record)
                logger.info("Event pushed to /animal_alerts/general in Realtime Database")
            # Send WhatsApp and SMS notifications only if animal detected
            if result["status"] == "animal_detected":
                try:
                    user_phone = farmer_mobile or data.get('user_phone') or data.get('to') # fallback for demo
                    notify_payload = {
                        "message": notification_message,
                        "to": user_phone
                    }
                    wa_resp = requests.post(
                        "https://api-indwreiyca-uc.a.run.app/send-whatsapp-message",
                        json=notify_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    logger.info(f"WhatsApp notification sent: {wa_resp.status_code}, {wa_resp.text}")
                    sms_resp = requests.post(
                        "https://api-indwreiyca-uc.a.run.app/send-sms",
                        json=notify_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    logger.info(f"SMS notification sent: {sms_resp.status_code}, {sms_resp.text}")
                except Exception as notify_err:
                    logger.error(f"Failed to send WhatsApp/SMS notification: {notify_err}")
        return create_success_response(get_request_id(req), result)
    except Exception as e:
        logger.error(f"Exception in handle_detect_animals: {e}")
        logger.error(traceback.format_exc())
        return create_error_response(get_request_id(req), "ER500", "Internal server error", str(e), 500)

def build_notification_message(result, farm_id, camera_id, lat, lng, timestamp, lang, label_str=None, farmer_name=None, farm_name=None, farm_address=None):
    """Builds a notification message in the preferred language, with salutation, name, and farm details."""
    name_part = f"{farmer_name}, " if farmer_name else ""
    farm_name_part = f" ({farm_name})" if farm_name else ""
    address_part = f"\nAddress: {farm_address}" if farm_address else ""
    if lang == 'hi':
        if result == 'animal_detected' and label_str:
            return (
                f"प्रिय {name_part} नमस्ते!\n"
                f"🚨 पशु अलर्ट! 🚨\n"
                f"हमने आपके खेत{farm_name_part} ({farm_id or 'N/A'}) में {label_str.title()} का पता लगाया है।\n"
                f"कैमरा: {camera_id or 'N/A'}\n"
                f"स्थान: ({lat}, {lng})\n"
                f"समय: {timestamp}\n"
                f"{address_part}\n"
                f"कृपया आवश्यक कार्रवाई करें।"
            )
        else:
            return f"प्रिय {name_part}आपके खेत में कोई पशु नहीं मिला।"
    elif lang == 'kn':
        if result == 'animal_detected' and label_str:
            return (
                f"ಪ್ರಿಯ {name_part} ನಮಸ್ಕಾರ!\n"
                f"🚨 ಪ್ರಾಣಿ ಎಚ್ಚರಿಕೆ! 🚨\n"
                f"ನಾವು ನಿಮ್ಮ ಫಾರ್ಮ್{farm_name_part} ({farm_id or 'N/A'}) ನಲ್ಲಿ {label_str.title()} ಪತ್ತೆಹಚ್ಚಿದ್ದೇವೆ.\n"
                f"ಕ್ಯಾಮೆರಾ: {camera_id or 'N/A'}\n"
                f"ಸ್ಥಳ: ({lat}, {lng})\n"
                f"ಸಮಯ: {timestamp}\n"
                f"{address_part}\n"
                f"ದಯವಿಟ್ಟು ಅಗತ್ಯ ಕ್ರಮಗಳನ್ನು ಕೈಗೊಳ್ಳಿ."
            )
        else:
            return f"ಪ್ರಿಯ {name_part}ನಿಮ್ಮ ಫಾರ್ಮ್‌ನಲ್ಲಿ ಯಾವುದೇ ಪ್ರಾಣಿಗಳನ್ನು ಪತ್ತೆಹಚ್ಚಲಾಗಲಿಲ್ಲ."
    else:  # Default to English
        if result == 'animal_detected' and label_str:
            return (
                f"Dear {name_part} Hello!\n"
                f"🚨 Animal Alert! 🚨\n"
                f"We have detected {label_str.title()} in your farm{farm_name_part} ({farm_id or 'N/A'}).\n"
                f"Camera: {camera_id or 'N/A'}\n"
                f"Location: ({lat}, {lng})\n"
                f"Time: {timestamp}\n"
                f"{address_part}\n"
                f"Please take necessary action."
            )
        else:
            return f"Dear {name_part}No animals were detected in your farm." 