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
        return create_success_response(get_request_id(req), result)
    except Exception as e:
        logger.error(f"Exception in handle_detect_animals: {e}")
        logger.error(traceback.format_exc())
        return create_error_response(get_request_id(req), "ER500", "Internal server error", str(e), 500) 