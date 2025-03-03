# Success Codes
SUCCESS_CODES = {
    "SUCCESS": {"code": "S01", "message": "Success"},
    "LOGIN_SUCCESS": {"code": "S02", "message": "Login successful."},
    "LOGOUT_SUCCESS": {"code": "S03", "message": "Logout successful."},
    "PASSWORD_CHANGE_SUCCESS": {"code": "S04", "message": "Password changed successfully."},
    "EMAIL_CHANGE_SUCCESS": {"code": "S05", "message": "Email changed successfully."},
}

# Authentication Error Codes
AUTH_ERROR_CODES = {
    "TOKEN_INVALID_OR_EXPIRED": {"code": "E01", "message": "Invalid or expired token."},
    "LOGIN_REQUIRED": {"code": "E02", "message": "Login required."},
    "INVALID_CREDENTIALS": {"code": "E03", "message": "Invalid credentials."},
}

# User and Account Error Codes
USER_ACCOUNT_ERROR_CODES = {
    "USER_NOT_FOUND": {"code": "E04", "message": "User not found."},
    "OLD_PASSWORD_INCORRECT": {"code": "E05", "message": "Old password is not correct."},
    "PASSWORD_CHANGE_ERROR": {"code": "E06", "message": "Error changing password."},
    "EMAIL_CHANGE_ERROR": {"code": "E07", "message": "Error changing email."},
    "USER_CREATION_ERROR": {"code": "E10", "message": "Error creating user."},
    "EMAIL_REQUIRED": {"code": "E11", "message": "Email is required."},
    "USERNAME_REQUIRED": {"code": "E12", "message": "Username is required."},
    "NEW_PASSWORD_REQUIRED": {"code": "E13", "message": "New password is required."},
    "RESET_TOKEN_NOT_FOUND": {"code": "E14", "message": "Reset token not found."},
    "EMAIL_ALREADY_IN_USE": {"code": "E15", "message": "This email is already in use."},
    "USER_WITH_EMAIL_NOT_FOUND": {"code": "E16", "message": "User with this email does not exist."},
    "FORGOT_PASSWORD_ERROR": {"code": "E17", "message": "Error sending forgot password email."},
    "PASSWORDS_DONT_MATCH": {"code": "E20", "message": "Passwords do not match."},
    "USER_DATA_NOT_FOUND": {"code": "E21", "message": "User data not found."},
}

# File and Media Processing Error Codes
FILE_MEDIA_ERROR_CODES = {
    "FILE_UPLOAD_ERROR": {"code": "E08", "message": "Error uploading file."},
    "MEDIA_PROCESSING_ERROR": {"code": "E09", "message": "Error processing media file."},
    "FILE_IDENTIFIER_REQUIRED": {"code": "E22", "message": "File identifier is required."},
    "METADATA_ANALYSIS_ERROR": {"code": "E23", "message": "Error analyzing metadata."},
    "DELETE_ERROR": {"code": "E26", "message": "Error deleting submission."},
}

# History and Submission Error Codes
HISTORY_ERROR_CODES = {
    "HISTORY_FETCH_ERROR": {"code": "E24", "message": "Error fetching submission history."},
    "HISTORY_DELETE_ERROR": {"code": "E25", "message": "Error deleting submission history."},
    "SUBMISSION_FETCH_ERROR": {"code": "E27", "message": "Error fetching submission details."},
}

# User Submission Specific Error Codes
USER_SUBMISSION_ERROR_CODES = {
    "MEDIA_CONTAINS_NO_FACES": {"code": "USE01", "message": "Media file contains no faces."},
    "FILE_NOT_FOUND": {"code": "USE02", "message": "File not found."},
}

# AI Text Analysis Error Codes
AI_TEXT_ERROR_CODES = {
    "TEXT_MISSING": {"code": "ATE01", "message": "No text provided for analysis."},
    "TEXT_PROCESSING_ERROR": {"code": "ATE02", "message": "Error processing text for AI analysis."},
    "TEXT_TOO_SHORT": {"code": "ATE03", "message": "Provided text is too short for reliable analysis."},
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
        return {"code": "E999", "message": "Unknown error code."}
