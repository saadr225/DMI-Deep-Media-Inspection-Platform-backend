from django.urls import path
from .views.base_views import home
from app.views.moderator_views import (
    moderation_dashboard,
    pda_moderation_view,
    user_management_view,
    forum_moderation_view,
    analytics_dashboard_view,
    moderation_settings_view,
    thread_detail_view,
    moderate_submission,
    pending_submissions,
)

urlpatterns = [
    path("", home, name="home"),
    
    # Moderation Panel URLs
    path("moderation/", moderation_dashboard, name="moderation_dashboard"),
    path("moderation/pda/", pda_moderation_view, name="pda_moderation"),
    path("moderation/users/", user_management_view, name="user_management"),
    path("moderation/forum/", forum_moderation_view, name="forum_moderation"),
    path("moderation/analytics/", analytics_dashboard_view, name="analytics_dashboard"),
    path("moderation/settings/", moderation_settings_view, name="moderation_settings"),
    path("moderation/thread/<int:thread_id>/", thread_detail_view, name="thread_detail"),
    
    # API endpoints for moderation
    path("api/moderation/submissions/pending/", pending_submissions, name="api_pending_submissions"),
    path("api/moderation/submission/<int:submission_id>/", moderate_submission, name="api_moderate_submission"),
]
