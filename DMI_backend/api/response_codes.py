# DMI_backend/api/response_codes.py

RESPONSE_CODES = {
    # Success codes
    "SUCCESS": {"code": "S01", "message": "Request was successful."},
    "PASSWORD_CHANGE_SUCCESS": {"code": "S02", "message": "Password changed successfully."},
    "FILE_UPLOAD_SUCCESS": {"code": "S03", "message": "File uploaded successfully."},
    "USER_CREATION_SUCCESS": {"code": "S04", "message": "User created successfully."},
    "LOGOUT_SUCCESS": {"code": "S05", "message": "Successfully logged out."},
    # Error codes
    "INVALID_CREDENTIALS": {"code": "E01", "message": "Invalid credentials."},
    "TOKEN_INVALID_OR_EXPIRED": {"code": "E02", "message": "Token is invalid or expired."},
    "REFRESH_TOKEN_REQUIRED": {"code": "E03", "message": "Refresh token is required."},
    "USER_DATA_NOT_FOUND": {"code": "E04", "message": "User data not found."},
    "OLD_PASSWORD_INCORRECT": {"code": "E05", "message": "Old password is not correct."},
    "FILE_UPLOAD_ERROR": {"code": "E06", "message": "Error uploading file."},
    "MEDIA_PROCESSING_ERROR": {"code": "E07", "message": "Error processing media file."},
    "USER_CREATION_ERROR": {"code": "E08", "message": "Error creating user."},
}


def get_response_code(code_key):
    return RESPONSE_CODES.get(code_key, {"code": "E00", "message": "Unknown error."})
