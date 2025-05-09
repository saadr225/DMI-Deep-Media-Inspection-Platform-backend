"""
URL configuration for DMI_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from app.views.moderator_views import (
    moderation_dashboard,
    forum_moderation_view,
    pda_moderation_view,
    user_management_view,
    analytics_dashboard_view,
    moderation_settings_view,
    thread_detail_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("app.urls")),
    path("api/", include("api.urls")),
    # Moderation panel URLs
    path("moderation/", moderation_dashboard, name="moderation_dashboard"),
    path("moderation/forum/", forum_moderation_view, name="forum_moderation"),
    path("moderation/pda/", pda_moderation_view, name="pda_moderation"),
    path("moderation/users/", user_management_view, name="user_management"),
    path("moderation/analytics/", analytics_dashboard_view, name="analytics_dashboard"),
    path("moderation/settings/", moderation_settings_view, name="moderation_settings"),
    path("moderation/thread/<int:thread_id>/", thread_detail_view, name="thread_detail"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
