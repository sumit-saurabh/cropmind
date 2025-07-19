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
- The API supports the following languages (via the `language` form field):
  - `en` : English
  - `hi` : Hindi
  - `hi-en` : Hinglish
  - `kn` : Kannada
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