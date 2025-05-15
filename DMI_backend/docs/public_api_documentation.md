# DMI Public API Documentation

This documentation covers the public API endpoints offered by the Deep Media Inspection (DMI) platform, which allow external applications to integrate DMI's AI detection capabilities.

## Base URL

All API endpoints are accessible under the base URL:

```
https://your-domain.com/api/public-api/
```

## Authentication

All public API endpoints require authentication using an API key:

- Authentication method: API Key
- Required header: `X-API-Key: <your_api_key>`
- Keys can be created and managed through the DMI web interface

API keys have customizable permissions and rate limits. Each key can be configured to access specific endpoints and has a daily request limit.

## Rate Limiting

- Each API key has a configurable daily request limit (default: 1000 requests per day)
- When the limit is reached, requests will be rejected with a 403 Forbidden response
- The current usage count resets at midnight UTC

## Public API Endpoints

### 1. Deepfake Detection API

Analyzes images or videos to detect potential deepfake manipulation.

**Endpoint:** `POST /api/public-api/deepfake-detection/`

**Authentication:** API Key (`X-API-Key` header)

**Content-Type:** `multipart/form-data`

**Request Parameters:**

- `file`: (Required) Image or video file to analyze
  - Supported image formats: JPEG, PNG, GIF, BMP
  - Supported video formats: MP4, MOV, AVI, WMV
  - Maximum file size: 25MB

**Example Request:**

```
curl -X POST "https://your-domain.com/api/public-api/deepfake-detection/" \
  -H "X-API-Key: your_api_key" \
  -F "file=@/path/to/your/image.jpg"
```

**Success Response (200 OK):**

```json
{
  "success": true,
  "code": "SUC001",
  "result": {
    "is_deepfake": true,
    "confidence_score": 0.94,
    "file_type": "Video",
    "frames_analyzed": 25,
    "fake_frames": 21,
    "fake_frames_percentage": 84.0
  },
  "metadata": {
    "width": 1920,
    "height": 1080,
    "format": "mp4",
    "duration": 15.5,
    "codec": "h264"
  }
}
```

**For Images:**

```json
{
  "success": true,
  "code": "SUC001",
  "result": {
    "is_deepfake": false,
    "confidence_score": 0.12,
    "file_type": "Image"
  },
  "metadata": {
    "width": 800,
    "height": 600,
    "format": "jpeg"
  }
}
```

**Error Responses:**

1. Missing API Key (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT001",
  "message": "Missing API key. Please provide your API key in the X-API-Key header."
}
```

2. Invalid API Key (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT001",
  "message": "Invalid API key. Please check your API key and try again."
}
```

3. Permission Denied (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT004",
  "message": "This API key does not have permission to access the deepfake detection endpoint."
}
```

4. Missing File (400 Bad Request):

```json
{
  "success": false,
  "code": "FIL001",
  "message": "No file was provided. Please upload a file."
}
```

5. File Too Large (400 Bad Request):

```json
{
  "success": false,
  "code": "FIL002",
  "message": "File too large. Maximum file size is 25MB."
}
```

6. Unsupported File Type (400 Bad Request):

```json
{
  "success": false,
  "code": "FIL003",
  "message": "Unsupported file type: application/pdf. Allowed types: image/jpeg, image/png, image/gif, image/bmp, video/mp4, video/quicktime, video/x-msvideo, video/x-ms-wmv"
}
```

7. Processing Error (500 Internal Server Error):

```json
{
  "success": false,
  "code": "SYS001",
  "message": "An error occurred: [error details]"
}
```

### 2. AI-Generated Text Detection API

Analyzes text to determine if it was written by AI or a human.

**Endpoint:** `POST /api/public-api/ai-text-detection/`

**Authentication:** API Key (`X-API-Key` header)

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "text": "Text to analyze (minimum 50 characters)",
  "highlight": true|false  (optional, default: false)
}
```

**Example Request:**

```
curl -X POST "https://your-domain.com/api/public-api/ai-text-detection/" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"text": "This is some text that I want to analyze to determine if it was written by an AI. The text should be long enough to provide a reliable analysis.", "highlight": true}'
```

**Success Response (200 OK):**

```json
{
  "success": true,
  "code": "SUC001",
  "result": {
    "is_ai_generated": true,
    "source_prediction": "GPT-3",
    "confidence_scores": {
      "Human": 0.12,
      "AI": 0.88
    },
    "highlighted_text": "This is some text that I want to analyze..." (included if highlight=true)
  }
}
```

**Error Responses:**

1. Missing API Key (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT001",
  "message": "Missing API key. Please provide your API key in the X-API-Key header."
}
```

2. Invalid API Key (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT001",
  "message": "Invalid API key. Please check your API key and try again."
}
```

3. Permission Denied (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT004",
  "message": "This API key does not have permission to access the AI text detection endpoint."
}
```

4. Invalid JSON (400 Bad Request):

```json
{
  "success": false,
  "code": "SYS003",
  "message": "Invalid JSON data"
}
```

5. Missing Text (400 Bad Request):

```json
{
  "success": false,
  "code": "TXT001",
  "message": "No text was provided. Please provide text for analysis."
}
```

6. Text Too Short (400 Bad Request):

```json
{
  "success": false,
  "code": "TXT002",
  "message": "Text too short. Please provide at least 50 characters for reliable analysis."
}
```

7. Processing Error (500 Internal Server Error):

```json
{
  "success": false,
  "code": "SYS001",
  "message": "An error occurred: [error details]"
}
```

### 3. AI-Generated Media Detection API

Detects if an image was generated by AI tools (e.g., DALL-E, Midjourney, Stable Diffusion).

**Endpoint:** `POST /api/public-api/ai-media-detection/`

**Authentication:** API Key (`X-API-Key` header)

**Content-Type:** `multipart/form-data`

**Request Parameters:**

- `file`: (Required) Image file to analyze
  - Supported formats: JPEG, PNG, GIF, BMP
  - Maximum file size: 25MB

**Example Request:**

```
curl -X POST "https://your-domain.com/api/public-api/ai-media-detection/" \
  -H "X-API-Key: your_api_key" \
  -F "file=@/path/to/your/image.jpg"
```

**Success Response (200 OK):**

```json
{
  "success": true,
  "code": "SUC001",
  "result": {
    "is_ai_generated": true,
    "prediction": "fake",
    "confidence_scores": {
      "ai_generated": 0.92,
      "real": 0.08
    }
  },
  "metadata": {
    "width": 1024,
    "height": 1024,
    "format": "png"
  }
}
```

**Error Responses:**

1. Missing API Key (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT001",
  "message": "Missing API key. Please provide your API key in the X-API-Key header."
}
```

2. Invalid API Key (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT001",
  "message": "Invalid API key. Please check your API key and try again."
}
```

3. Permission Denied (403 Forbidden):

```json
{
  "success": false,
  "code": "AUT004",
  "message": "This API key does not have permission to access the AI media detection endpoint."
}
```

4. Missing File (400 Bad Request):

```json
{
  "success": false,
  "code": "FIL001",
  "message": "No file was provided. Please upload a file."
}
```

5. File Too Large (400 Bad Request):

```json
{
  "success": false,
  "code": "FIL002",
  "message": "File too large. Maximum file size is 25MB."
}
```

6. Unsupported File Type (400 Bad Request):

```json
{
  "success": false,
  "code": "FIL003",
  "message": "Unsupported file type: video/mp4. Allowed types: image/jpeg, image/png, image/gif, image/bmp"
}
```

7. Processing Error (500 Internal Server Error):

```json
{
  "success": false,
  "code": "SYS001",
  "message": "An error occurred: [error details]"
}
```

## API Key Management

The following endpoints allow users to manage their API keys (available only to authenticated users):

### 1. List and Create API Keys

**Endpoint:** `GET/POST /api/api-keys/`

**Authentication:** JWT Token (Frontend authentication)

**GET: List user's API keys**

- Returns list of API keys owned by the user

**Example GET Request:**

```
curl -X GET "https://your-domain.com/api/api-keys/" \
  -H "Authorization: Bearer your_jwt_token"
```

**GET Response:**

```json
{
  "success": true,
  "code": "SUC001",
  "api_keys": [
    {
      "id": 1,
      "name": "My API Key",
      "key": "3bce9e131b60dc7bcc7433228a69d46fdb086e8d03f8fa8976ffaae9e09441eb" (64 characters)
      "created_at": "2023-05-15T13:45:30Z",
      "expires_at": "2024-05-15T13:45:30Z",
      "daily_limit": 1000,
      "daily_usage": 42,
      "can_use_deepfake_detection": true,
      "can_use_ai_text_detection": true,
      "can_use_ai_media_detection": false
    },
    ...
  ]
}
```

**POST: Create new API key**

**Example POST Request:**

```
curl -X POST "https://your-domain.com/api/api-keys/" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Key",
    "expires_at": "2024-12-31",
    "daily_limit": 1000,
    "can_use_deepfake_detection": true,
    "can_use_ai_text_detection": true,
    "can_use_ai_media_detection": true
  }'
```

**POST Response:**

```json
{
  "success": true,
  "code": "SUC001",
  "api_key": {
    "id": 2,
    "name": "My API Key",
    "key": "d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7",  (full key, only shown once)
    "created_at": "2023-05-15T13:46:30Z",
    "expires_at": "2024-12-31T00:00:00Z",
    "daily_limit": 1000,
    "can_use_deepfake_detection": true,
    "can_use_ai_text_detection": true,
    "can_use_ai_media_detection": true
  }
}
```

### 2. Get or Revoke API Key

**Endpoint:** `GET/DELETE /api/api-keys/{key_id}/`

**Authentication:** JWT Token (Frontend authentication)

**GET: Retrieve API key details**

**Example GET Request:**

```
curl -X GET "https://your-domain.com/api/api-keys/1/" \
  -H "Authorization: Bearer your_jwt_token"
```

**GET Response:**

```json
{
  "success": true,
  "code": "SUC001",
  "api_key": {
    "id": 1,
    "name": "My API Key",
    "key": "3bce9e131b60dc7bcc7433228a69d46fdb086e8d03f8fa8976ffaae9e09441eb",  (first 64 chars only)
    "created_at": "2023-05-15T13:45:30Z",
    "expires_at": "2024-05-15T13:45:30Z",
    "daily_limit": 1000,
    "daily_usage": 42,
    "last_used_at": "2023-05-15T14:20:15Z",
    "can_use_deepfake_detection": true,
    "can_use_ai_text_detection": true,
    "can_use_ai_media_detection": false
  }
}
```

**DELETE: Revoke API key**

**Example DELETE Request:**

```
curl -X DELETE "https://your-domain.com/api/api-keys/1/" \
  -H "Authorization: Bearer your_jwt_token"
```

**DELETE Response:**

```json
{
  "success": true,
  "code": "SUC001",
  "message": "API key \"My API Key\" has been revoked"
}
```

## Implementation Notes

1. API keys should be securely stored and never exposed publicly
2. All API requests are logged for audit and billing purposes
3. Large files may take longer to process (especially videos)
4. For AI text detection, provide at least 50 characters for reliable analysis
5. API responses follow a consistent format with a success flag, code, and result/message

## Status Codes

The API uses conventional HTTP response codes:

- 200 OK: Request succeeded
- 400 Bad Request: Invalid input parameters
- 403 Forbidden: Authentication or permission issues
- 404 Not Found: Resource not found
- 415 Unsupported Media Type: File type not supported
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Server-side error

## Client Libraries

### Python

```python
import requests

def detect_ai_text(api_key, text, highlight=False):
    url = "https://your-domain.com/api/public-api/ai-text-detection/"
    headers = {"X-API-Key": api_key}
    data = {"text": text, "highlight": highlight}

    response = requests.post(url, headers=headers, json=data)
    return response.json()

def detect_deepfake(api_key, file_path):
    url = "https://your-domain.com/api/public-api/deepfake-detection/"
    headers = {"X-API-Key": api_key}

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(url, headers=headers, files=files)

    return response.json()

def detect_ai_media(api_key, file_path):
    url = "https://your-domain.com/api/public-api/ai-media-detection/"
    headers = {"X-API-Key": api_key}

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(url, headers=headers, files=files)

    return response.json()
```

### JavaScript

```javascript
// Deepfake detection example
async function detectDeepfake(apiKey, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("https://your-domain.com/api/public-api/deepfake-detection/", {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
    },
    body: formData,
  });

  return await response.json();
}

// AI text detection example
async function detectAIText(apiKey, text, highlight = false) {
  const response = await fetch("https://your-domain.com/api/public-api/ai-text-detection/", {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text: text,
      highlight: highlight,
    }),
  });

  return await response.json();
}

// AI media detection example
async function detectAIMedia(apiKey, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("https://your-domain.com/api/public-api/ai-media-detection/", {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
    },
    body: formData,
  });

  return await response.json();
}
```

## Contact and Support

For API support, bug reports, or feature requests, please contact:

- Email: api-support@your-domain.com
- Documentation website: https://your-domain.com/api-docs
