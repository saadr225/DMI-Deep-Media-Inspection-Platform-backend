"""
Response Code System
-------------------
This file defines all response codes used throughout the application.

NAMING CONVENTION:
- Each code consists of a 3-letter prefix followed by a 3-digit number (e.g., SUC001)
- The prefix identifies the category of the code
- The 3-digit number provides unique identification within that category

PREFIX MEANINGS:
SUC - Success codes
AUT - Authentication-related codes
USR - User account management codes
FIL - File and media processing codes
SUB - Submission and history management codes (currently using HIS prefix)
TXT - AI text analysis codes
IMG - Image analysis and face recognition codes (currently using FCE prefix)
SYS - General system codes
USE - User submission specific codes

Notes:
- For consistency, some prefixes should be updated (HIS→SUB, FCE→IMG, USE→IMG)
- The 3-digit numbering starts at 001 within each category
"""

# Success Codes
SUCCESS_CODES = {
    "SUCCESS": {"code": "SUC001", "message": "Success"},
    "LOGIN_SUCCESS": {"code": "SUC002", "message": "Login successful."},
    "LOGOUT_SUCCESS": {"code": "SUC003", "message": "Logout successful."},
    "PASSWORD_CHANGE_SUCCESS": {"code": "SUC004", "message": "Password changed successfully."},
    "EMAIL_CHANGE_SUCCESS": {"code": "SUC005", "message": "Email changed successfully."},
}

# Authentication Error Codes
AUTH_ERROR_CODES = {
    "TOKEN_INVALID_OR_EXPIRED": {"code": "AUT001", "message": "Invalid or expired token."},
    "LOGIN_REQUIRED": {"code": "AUT002", "message": "Login required."},
    "INVALID_CREDENTIALS": {"code": "AUT003", "message": "Invalid credentials."},
    "ACCESS_DENIED": {
        "code": "AUT004",
        "message": "You don't have permission to access this resource.",
    },
}

# User and Account Error Codes
USER_ACCOUNT_ERROR_CODES = {
    "USER_NOT_FOUND": {"code": "USR001", "message": "User not found."},
    "OLD_PASSWORD_INCORRECT": {"code": "USR002", "message": "Old password is not correct."},
    "PASSWORD_CHANGE_ERROR": {"code": "USR003", "message": "Error changing password."},
    "EMAIL_CHANGE_ERROR": {"code": "USR004", "message": "Error changing email."},
    "USER_CREATION_ERROR": {"code": "USR005", "message": "Error creating user."},
    "EMAIL_REQUIRED": {"code": "USR006", "message": "Email is required."},
    "USERNAME_REQUIRED": {"code": "USR007", "message": "Username is required."},
    "NEW_PASSWORD_REQUIRED": {"code": "USR008", "message": "New password is required."},
    "RESET_TOKEN_NOT_FOUND": {"code": "USR009", "message": "Reset token not found."},
    "EMAIL_ALREADY_IN_USE": {"code": "USR010", "message": "This email is already in use."},
    "USER_WITH_EMAIL_NOT_FOUND": {"code": "USR011", "message": "User with this email does not exist."},
    "FORGOT_PASSWORD_ERROR": {"code": "USR012", "message": "Error sending forgot password email."},
    "PASSWORDS_DONT_MATCH": {"code": "USR013", "message": "Passwords do not match."},
    "USER_DATA_NOT_FOUND": {"code": "USR014", "message": "User data not found."},
}

# File and Media Processing Error Codes
FILE_MEDIA_ERROR_CODES = {
    "FILE_UPLOAD_ERROR": {"code": "FIL001", "message": "Error uploading file."},
    "MEDIA_PROCESSING_ERROR": {"code": "FIL002", "message": "Error processing media file."},
    "FILE_IDENTIFIER_REQUIRED": {"code": "FIL003", "message": "File identifier is required."},
    "METADATA_ANALYSIS_ERROR": {"code": "FIL004", "message": "Error analyzing metadata."},
    "DELETE_ERROR": {"code": "FIL005", "message": "Error deleting submission."},
    "UNSUPPORTED_FILE_TYPE": {"code": "FIL006", "message": "This file type is not supported."},
}

# History and Submission Error Codes
HISTORY_ERROR_CODES = {
    "HISTORY_FETCH_ERROR": {"code": "HIS001", "message": "Error fetching submission history."},
    "HISTORY_DELETE_ERROR": {"code": "HIS002", "message": "Error deleting submission history."},
    "SUBMISSION_FETCH_ERROR": {"code": "HIS003", "message": "Error fetching submission details."},
    "SUBMISSION_NOT_FOUND": {"code": "HIS004", "message": "The specified submission was not found."},
    "INVALID_SUBMISSION": {"code": "HIS005", "message": "The submission is invalid or incomplete."},
    "DUPLICATE_SUBMISSION": {"code": "HIS006", "message": "This content has already been submitted."},
}

# General Error Codes
GENERAL_ERROR_CODES = {
    "INVALID_REQUEST": {"code": "SYS001", "message": "Invalid request parameters."},
    "SERVER_ERROR": {"code": "SYS002", "message": "An unexpected server error occurred."},
    "NOT_FOUND": {"code": "SYS003", "message": "The requested resource was not found."},
    "INVALID_CATEGORY": {"code": "SYS004", "message": "Invalid category selected."},
}

# User Submission Specific Error Codes
USER_SUBMISSION_ERROR_CODES = {
    "MEDIA_CONTAINS_NO_FACES": {"code": "USE001", "message": "Media file contains no faces."},
    "FILE_NOT_FOUND": {"code": "USE007", "message": "File not found."},
}

# AI Text Analysis Error Codes
AI_TEXT_ERROR_CODES = {
    "TEXT_MISSING": {"code": "TXT001", "message": "No text provided for analysis."},
    "TEXT_PROCESSING_ERROR": {"code": "TXT002", "message": "Error processing text for AI analysis."},
    "TEXT_TOO_SHORT": {
        "code": "TXT003",
        "message": "Provided text is too short for reliable analysis.",
    },
    "HIGHLIGHT_MISSING": {"code": "TXT004", "message": "No highlight parameter provided."},
}

# Face Watch Error Codes
FACE_WATCH_ERROR_CODES = {
    "FACE_REGISTRATION_ERROR": {"code": "FCE002", "message": "Error registering face."},
    "FACE_DETECTION_ERROR": {"code": "FCE003", "message": "Error detecting face in image."},
    "FACE_REMOVAL_ERROR": {"code": "FCE004", "message": "Error removing face from watch list."},
    "FACE_NOT_FOUND": {"code": "FCE005", "message": "Face not found in watch list."},
    "MULTIPLE_FACES_DETECTED": {"code": "FCE006", "message": "Multiple faces detected in the image."},
}

# Combine all response codes into one dictionary for lookup
RESPONSE_CODES = {
    **SUCCESS_CODES,
    **AUTH_ERROR_CODES,
    **USER_ACCOUNT_ERROR_CODES,
    **FILE_MEDIA_ERROR_CODES,
    **USER_SUBMISSION_ERROR_CODES,
    **HISTORY_ERROR_CODES,
    **AI_TEXT_ERROR_CODES,
    **GENERAL_ERROR_CODES,
    **FACE_WATCH_ERROR_CODES,  # Added this as it was missing from the combined dictionary
}


def get_response_code(code_key: str) -> dict:
    """
    Get response code by key.
    Args:
        code_key (str): Key for response code.
    Returns:
        dict: Response code dictionary.
    """
    if code_key in RESPONSE_CODES:
        return RESPONSE_CODES[code_key]
    else:
        return {"code": "ERR000", "message": "Unknown error code."}
