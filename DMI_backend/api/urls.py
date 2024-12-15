from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="api-home"),
    path("process-deepfake-media/", views.process_deepfake_media, name="api-process-deepfake-media"),
]
