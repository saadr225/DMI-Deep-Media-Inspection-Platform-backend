from django.urls import path
from .views.base_views import home
from app.views import moderator_views

urlpatterns = [
    path("", home, name="home"),
]
