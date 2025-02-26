from django.urls import path
from .views import auth_views, user_views, semantic_views, helper_views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # user related endpoints
    path("user/signup/", auth_views.signup, name="signup"),
    path("user/login/", auth_views.login, name="login"),
    path("user/logout/", auth_views.logout, name="logout"),
    path("user/change_password/", auth_views.change_password, name="change_password"),
    path("user/change_email/", auth_views.change_email, name="change_email"),
    path("user/forgot_password/", auth_views.forgot_password, name="forgot_password"),
    path("user/reset_password/<str:token>/", auth_views.reset_password, name="reset_password"),
    # token related endpoints
    path("auth/refresh_token/", auth_views.refresh_token, name="refresh_token"),
    # user info endpoints
    path("user/info/", user_views.get_user_info, name="get_user_info"),
    path(
        "user/submissions/",
        user_views.get_user_submissions_history,
        name="get_user_submissions_history",
    ),
    path(
        "user/submissions/<str:submission_identifier>",
        user_views.manage_submission,
        name="manage_submission",
    ),
    # media processing endpoints
    path("process/df/", semantic_views.process_deepfake_media, name="process_deepfake"),
    path("process/ai/", semantic_views.process_ai_generated_media, name="process_ai_generated_media"),
    path("process/metadata/", semantic_views.process_metadata, name="process_metadata"),
    # response codes endpoint
    path("docs/response_codes/", helper_views.get_response_codes, name="get_response_codes"),
]
