from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path(
        "process-deepfake-media/",
        views.process_deepfake_media,
        name="process-deepfake-media",
    ),
]
