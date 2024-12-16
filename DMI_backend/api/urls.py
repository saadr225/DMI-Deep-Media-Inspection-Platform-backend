from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("process/df/", views.process_deepfake_media, name="process-deepfake"),
    path("refresh_token/", views.refresh_token, name="refresh_token"),
]
