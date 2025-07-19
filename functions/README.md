# CropMind Functions Backend

## Local Development & Real Pipeline Setup

### 1. **Service Account Key**
- Download your service account key JSON from Google Cloud Console.
- Place it **outside** the `functions/` folder, e.g.:
  ```
  /Users/sumitsaurabh/data/workspace/crop_mind/keys/cropmind-89afe-a6a8ae700527.json
  ```

### 2. **Create and Set Up Google Cloud Resources**
- **Firestore:**
  - Go to https://console.cloud.google.com/datastore/setup?project=YOUR_PROJECT_ID
  - Create a Firestore database in **Native mode** with the default name (`default`).
- **Cloud Storage:**
  - Go to https://console.cloud.google.com/storage/browser?project=YOUR_PROJECT_ID
  - Create a bucket (e.g., `cropmind-team`).
  - Make the bucket public (Permissions tab → Grant access to `allUsers` as `Storage Object Viewer`).
- **Enable APIs:**
  - Enable Firestore, Cloud Storage, Vertex AI, Vision API, and Generative Language API in your project.

### 3. **Set Environment Variables**

#### **For local real pipeline runs:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/Users/sumitsaurabh/data/workspace/crop_mind/keys/cropmind-89afe-a6a8ae700527.json"
export FORCE_REAL_API=true
export GCS_BUCKET="cropmind-team"
python main.py
```
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your service account key JSON.
- `FORCE_REAL_API=true`: Enables real Google Cloud API calls locally.
- `GCS_BUCKET`: Name of your Cloud Storage bucket (e.g., `cropmind-team`).

#### **(Optional) Use a `.env` file**
If you use `python-dotenv`, you can put these in a `.env` file:
```
GOOGLE_APPLICATION_CREDENTIALS=/Users/sumitsaurabh/data/workspace/crop_mind/keys/cropmind-89afe-a6a8ae700527.json
FORCE_REAL_API=true
GCS_BUCKET=cropmind-team
```

### 4. **Install Requirements**
```bash
pip install -r requirements.txt
```

### 5. **Run Locally**
```bash
python main.py
```

### 6. **Multi-language Support**
- The API supports the following languages via the **`language` form field** (required for diagnosis):
  - `en` : English
  - `hi` : Hindi
  - `hi-en` : Hinglish
  - `kn` : Kannada
- **How to use:**
  - Add `--form 'language=<code>'` to your curl or API request (see below).
  - If omitted or invalid, defaults to English (`en`).
- To add more languages, update the `SUPPORTED_LANGUAGES` dictionary in `main.py`.

### 7. **Test the API (with language selection)**

#### **English**
```bash
curl --location 'http://localhost:8080/api/diagnose-crop' \
  --header 'Authorization: testtoken' \
  --form 'image=@"/path/to/sample_disease_image.jpg"' \
  --form 'crop=potato' \
  --form 'user_id=farmer_123' \
  --form 'location=Bengaluru' \
  --form 'language=en'
```

#### **Hindi**
```bash
curl --location 'http://localhost:8080/api/diagnose-crop' \
  --header 'Authorization: testtoken' \
  --form 'image=@"/path/to/sample_disease_image.jpg"' \
  --form 'crop=potato' \
  --form 'user_id=farmer_123' \
  --form 'location=Bengaluru' \
  --form 'language=hi'
```

#### **Hinglish**
```bash
curl --location 'http://localhost:8080/api/diagnose-crop' \
  --header 'Authorization: testtoken' \
  --form 'image=@"/path/to/sample_disease_image.jpg"' \
  --form 'crop=potato' \
  --form 'user_id=farmer_123' \
  --form 'location=Bengaluru' \
  --form 'language=hi-en'
```

#### **Kannada**
```bash
curl --location 'http://localhost:8080/api/diagnose-crop' \
  --header 'Authorization: testtoken' \
  --form 'image=@"/path/to/sample_disease_image.jpg"' \
  --form 'crop=potato' \
  --form 'user_id=farmer_123' \
  --form 'location=Bengaluru' \
  --form 'language=kn'
```

- **Do NOT** use `X-Mock-Response: true` if you want the real pipeline.
- Change the path to your image as needed.

---

### 8. **Available API Endpoints**

| Endpoint                       | Method | Description                                 |
|--------------------------------|--------|---------------------------------------------|
| `/ping`                        | GET    | Health check, requires `Authorization`      |
| `/api/diagnose-crop`           | POST   | Diagnose crop disease from image            |
| `/api/mandi-nearby`            | POST   | Find nearby mandis by lat/lng               |
| `/api/mandi-crop-price`        | POST   | Find crop prices in nearby mandis           |
| `/api/mandi-crop-trend`        | POST   | Get price trend/history for a crop/mandi    |
| `/api/mandi-details`           | POST   | Get full mandi info by mandi_id             |
| `/api/mandi-search`            | POST   | Search mandis by pincode or name            |
| `/api/diagnosis-history`       | POST   | Fetch a user's diagnosis history            |

**All endpoints require an `Authorization` header.**

---

#### **Example: /api/mandi-nearby**
```bash
curl -X POST http://localhost:8080/api/mandi-nearby \
  -H 'Authorization: testtoken' \
  -F 'user_id=farmer_123' \
  -F 'lat=12.9716' \
  -F 'lng=77.5946' \
  -F 'limit=3' \
  -F 'language=en'
```

#### **Example: /api/diagnosis-history**
```bash
curl -X POST http://localhost:8080/api/diagnosis-history \
  -H 'Authorization: testtoken' \
  -F 'user_id=farmer_123' \
  -F 'limit=5' \
  -F 'offset=0'
```

---

### **Endpoint Field Reference**

| Endpoint                  | Required Fields                                 |
|---------------------------|------------------------------------------------|
| `/api/diagnose-crop`      | `user_id`, `crop`, `image`, `location` (opt), `language` |
| `/api/mandi-nearby`       | `user_id`, `lat`, `lng`, `limit` (opt), `language` |
| `/api/mandi-crop-price`   | `user_id`, `lat`, `lng`, `crop`, `limit` (opt), `language` |
| `/api/mandi-crop-trend`   | `user_id`, `mandi_id`, `crop`, `language`      |
| `/api/mandi-details`      | `user_id`, `mandi_id`, `language`              |
| `/api/mandi-search`       | `user_id`, `pincode` or `name`, `limit` (opt), `language` |
| `/api/diagnosis-history`  | `user_id`, `limit` (opt), `offset` (opt)       |

---

### **Dual Environment Note**

- The same codebase works for both local Flask and Google Cloud Functions.
- All endpoints are registered for both environments; use the same curl commands for local and deployed testing.

---

### **Startup Log**

- When you run `python main.py`, the server prints all available endpoints and example curl commands.

---

### 9. **Uploading Mandi Data to Firestore**

To upload mandi data from a JSON file to Firestore:

1. **Ensure your `.env` file is set up** (see above for required variables).
2. **Run the uploader script:**
   ```bash
   python scripts/mandi_data_uploader.py sample_data/yeshwanthpur_mandi.json
   ```
   - Replace the path with your mandi JSON file as needed.
   - On success, you will see:
     ```
     [SUCCESS] Uploaded mandi data for 'Yeshwanthpur Mandi' (ID: 86313) to Firestore.
     ```

You can use this script for any mandi JSON file. The script will use the `mandi_id` as the document ID in the `mandis` collection.

---

## **Production/Deployment**
- You do **not** need to upload your service account key to Google Cloud Functions.
- The deployed function will use the default or specified service account for authentication.
- Make sure the service account has the necessary roles:
  - Cloud Datastore User (Firestore)
  - Storage Object Admin (Cloud Storage)
  - Vertex AI User (Vision, Gemini, etc.)

---

## **.gitignore**
- Your `.gitignore` should include:
  ```
  keys/
  *.json
  ```
  to prevent accidental commits of credentials.

---

## **Troubleshooting**
- **Firestore 404:** Make sure you created a Firestore database in Native mode with the default name.
- **Storage 404:** Make sure your bucket exists and matches `GCS_BUCKET`.
- **Permission errors:** Check your service account roles and key file path.
- **API not enabled:** Enable required APIs in the Google Cloud Console.
- **Gemini JSON parsing:** The backend strips code block markers from Gemini responses for robust parsing.

---

For any issues, check your logs for `[ERROR]` and `[DEBUG]` messages for detailed troubleshooting. 