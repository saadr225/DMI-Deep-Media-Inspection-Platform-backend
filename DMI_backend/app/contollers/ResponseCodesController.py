# Success Codes
SUCCESS_CODES = {
    "SUCCESS": {"code": "S01", "message": "Request was successful."},
    "PASSWORD_CHANGE_SUCCESS": {"code": "S02", "message": "Password changed successfully."},
    "EMAIL_CHANGE_SUCCESS": {"code": "S03", "message": "Email changed successfully."},
    "FILE_UPLOAD_SUCCESS": {"code": "S04", "message": "File uploaded successfully."},
    "USER_CREATION_SUCCESS": {"code": "S05", "message": "User created successfully."},
    "LOGOUT_SUCCESS": {"code": "S06", "message": "Successfully logged out."},
}

# Authentication Error Codes
AUTH_ERROR_CODES = {
    "INVALID_CREDENTIALS": {"code": "E01", "message": "Invalid credentials."},
    "TOKEN_INVALID_OR_EXPIRED": {"code": "E02", "message": "Token is invalid or expired."},
    "REFRESH_TOKEN_REQUIRED": {"code": "E03", "message": "Refresh token is required."},
    "REFRESH_TOKEN_INVALID": {"code": "E18", "message": "Invalid refresh token."},
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
}

# New Error Code for history fetch issues
NEW_ERROR_CODES = {
    "HISTORY_FETCH_ERROR": {"code": "E24", "message": "Error fetching submission history."},
}

# User Submission Specific Error Codes
USER_SUBMISSION_ERROR_CODES = {
    "MEDIA_CONTAINS_NO_FACES": {"code": "USE01", "message": "Media file contains no faces."},
    "FILE_NOT_FOUND": {"code": "USE02", "message": "File not found."},
}

# Combine all response codes into one dictionary for lookup
RESPONSE_CODES = {
    **SUCCESS_CODES,
    **AUTH_ERROR_CODES,
    **USER_ACCOUNT_ERROR_CODES,
    **FILE_MEDIA_ERROR_CODES,
    **USER_SUBMISSION_ERROR_CODES,
    **NEW_ERROR_CODES,
}


def get_response_code(code_key: str) -> dict:
    return RESPONSE_CODES.get(code_key, {"code": "E00", "message": "Unknown error."})
