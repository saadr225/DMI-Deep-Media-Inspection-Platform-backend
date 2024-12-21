RESPONSE_CODES = {
    # Success codes
    "SUCCESS": {"code": "S01", "message": "Request was successful."},
    "PASSWORD_CHANGE_SUCCESS": {"code": "S02", "message": "Password changed successfully."},
    "EMAIL_CHANGE_SUCCESS": {"code": "S03", "message": "Email changed successfully."},
    "FILE_UPLOAD_SUCCESS": {"code": "S04", "message": "File uploaded successfully."},
    "USER_CREATION_SUCCESS": {"code": "S05", "message": "User created successfully."},
    "LOGOUT_SUCCESS": {"code": "S06", "message": "Successfully logged out."},
    # Error codes
    "INVALID_CREDENTIALS": {"code": "E01", "message": "Invalid credentials."},
    "TOKEN_INVALID_OR_EXPIRED": {"code": "E02", "message": "Token is invalid or expired."},
    "REFRESH_TOKEN_REQUIRED": {"code": "E03", "message": "Refresh token is required."},
    "USER_DATA_NOT_FOUND": {"code": "E04", "message": "User data not found."},
    "OLD_PASSWORD_INCORRECT": {"code": "E05", "message": "Old password is not correct."},
    "PASSWORD_CHANGE_ERROR": {"code": "E06", "message": "Error changing password."},
    "EMAIL_CHANGE_ERROR": {"code": "E07", "message": "Error changing email."},
    "FILE_UPLOAD_ERROR": {"code": "E08", "message": "Error uploading file."},
    "MEDIA_PROCESSING_ERROR": {"code": "E09", "message": "Error processing media file."},
    "USER_CREATION_ERROR": {"code": "E10", "message": "Error creating user."},
    "EMAIL_REQUIRED": {"code": "E11", "message": "Email is required."},
    "USERNAME_REQUIRED": {"code": "E12", "message": "Username is required."},
    "NEW_PASSWORD_REQUIRED": {"code": "E13", "message": "New password is required."},
    "RESET_TOKEN_NOT_FOUND": {"code": "E14", "message": "Reset token not found."},
    "EMAIL_ALREADY_IN_USE": {"code": "E15", "message": "This email is already in use."},
    "USER_NOT_FOUND": {"code": "E16", "message": "User with this email does not exist."},
    "FORGOT_PASSWORD_ERROR": {"code": "E17", "message": "Error sending forgot password email."},
    "REFRESH_TOKEN_INVALID": {"code": "E17", "message": "Invalid refresh token."},
    "GENERAL_ERROR": {"code": "E18", "message": "An error occurred."},
}


def get_response_code(code_key):
    return RESPONSE_CODES.get(code_key, {"code": "E00", "message": "Unknown error."})
