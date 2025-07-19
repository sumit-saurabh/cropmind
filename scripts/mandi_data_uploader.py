import os
import sys
import json
import firebase_admin
from firebase_admin import credentials, firestore, initialize_app
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

COLLECTION_NAME = os.environ.get('MANDI_COLLECTION', 'mandis')

# Initialize Firebase Admin
if not firebase_admin._apps:
    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not cred_path or not os.path.exists(cred_path):
        print(f"[ERROR] GOOGLE_APPLICATION_CREDENTIALS not set or file does not exist: {cred_path}")
        sys.exit(1)
    cred = credentials.Certificate(cred_path)
    initialize_app(cred)
db = firestore.client()

def upload_mandi_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        mandi_data = json.load(f)
    mandi_id = mandi_data.get('mandi_id')
    if not mandi_id:
        print(f"[ERROR] mandi_id missing in {json_path}")
        return
    doc_ref = db.collection(COLLECTION_NAME).document(str(mandi_id))
    doc_ref.set(mandi_data)
    print(f"[SUCCESS] Uploaded mandi data for '{mandi_data.get('mandi_name')}' (ID: {mandi_id}) to Firestore.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python mandi_data_uploader.py <path_to_mandi_json>")
        sys.exit(1)
    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"[ERROR] File not found: {json_path}")
        sys.exit(1)
    upload_mandi_json(json_path)
