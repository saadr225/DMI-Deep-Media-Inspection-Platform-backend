from django.urls import path
from .views import (
    signup,
    login,
    logout,
    process_deepfake_media,
    refresh_token,
    change_email,
    forgot_password,
    reset_password,
    change_password,
    get_user_info,
    get_response_codes,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # user related endpoints
    path("user/signup/", signup, name="signup"),
    path("user/login/", login, name="login"),
    path("user/logout/", logout, name="logout"),
    path("user/change_password/", change_password, name="change_password"),
    path("user/change_email/", change_email, name="change_email"),
    path("user/forgot_password/", forgot_password, name="forgot_password"),
    path("user/reset_password/<str:token>/", reset_password, name="reset_password"),
    path("user/info/", get_user_info, name="get_user_info"),
    # token related endpoints
    path("auth/refresh_token/", refresh_token, name="refresh_token"),
    # media processing endpoints
    path("process/df/", process_deepfake_media, name="process_deepfake"),
    # response codes endpoint
    path("docs/response_codes/", get_response_codes, name="get_response_codes"),
]
