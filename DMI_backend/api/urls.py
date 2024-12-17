from django.urls import path
from .views import signup, login, logout, process_deepfake_media, refresh_token

urlpatterns = [
    path("signup/", signup, name="signup"),
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("process/df/", process_deepfake_media, name="process-deepfake"),
    path("refresh_token/", refresh_token, name="refresh_token"),
]
