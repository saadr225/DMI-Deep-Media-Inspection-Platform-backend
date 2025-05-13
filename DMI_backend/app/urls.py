from django.urls import path, include
from .views.base_views import home
from app.views import custom_admin_views
from app.views import custom_moderation_views

urlpatterns = [
    path("", home, name="home"),
    # Custom Admin Panel URLs
    path(
        "custom-admin/",
        include(
            [
                path("", custom_admin_views.custom_admin_dashboard_view, name="custom_admin_dashboard"),
                path("login/", custom_admin_views.custom_admin_login_view, name="custom_admin_login"),
                path(
                    "logout/", custom_admin_views.custom_admin_logout_view, name="custom_admin_logout"
                ),
                path("users/", custom_admin_views.custom_admin_users_view, name="custom_admin_users"),
                path(
                    "users/<int:user_id>/",
                    custom_admin_views.custom_admin_user_detail_view,
                    name="custom_admin_user_detail",
                ),
                path(
                    "users/add/",
                    custom_admin_views.custom_admin_user_add_view,
                    name="custom_admin_user_add",
                ),
                path(
                    "pda/", custom_admin_views.custom_admin_pda_list_view, name="custom_admin_pda_list"
                ),
                path(
                    "pda/<int:pda_id>/",
                    custom_admin_views.custom_admin_pda_detail_view,
                    name="custom_admin_pda_detail",
                ),
                path(
                    "pda/<int:pda_id>/approve/",
                    custom_admin_views.custom_admin_pda_approve_view,
                    name="custom_admin_pda_approve",
                ),
                path(
                    "pda/<int:pda_id>/reject/",
                    custom_admin_views.custom_admin_pda_reject_view,
                    name="custom_admin_pda_reject",
                ),
                path("forum/", custom_admin_views.custom_admin_forum_view, name="custom_admin_forum"),
                path(
                    "forum/<int:thread_id>/",
                    custom_admin_views.custom_admin_forum_thread_view,
                    name="custom_admin_forum_thread",
                ),
                path(
                    "forum/<int:thread_id>/approve/",
                    custom_admin_views.custom_admin_forum_approve_view,
                    name="custom_admin_forum_approve",
                ),
                path(
                    "forum/<int:thread_id>/reject/",
                    custom_admin_views.custom_admin_forum_reject_view,
                    name="custom_admin_forum_reject",
                ),
                path(
                    "analytics/",
                    custom_admin_views.custom_admin_analytics_view,
                    name="custom_admin_analytics",
                ),
                path("logs/", custom_admin_views.custom_admin_logs_view, name="custom_admin_logs"),
                path(
                    "settings/",
                    custom_admin_views.custom_admin_settings_view,
                    name="custom_admin_settings",
                ),
                path(
                    "profile/",
                    custom_admin_views.custom_admin_profile_view,
                    name="custom_admin_profile",
                ),
                path(
                    "moderators/",
                    custom_admin_views.custom_admin_moderators_view,
                    name="custom_admin_moderators",
                ),
                path(
                    "pending/",
                    custom_admin_views.custom_admin_pending_view,
                    name="custom_admin_pending",
                ),
            ]
        ),
    ),
    # Custom Moderation Panel URLs
    path(
        "moderation/",
        include(
            [
                path(
                    "", custom_moderation_views.moderation_dashboard_view, name="moderation_dashboard"
                ),
                path("login/", custom_moderation_views.moderation_login_view, name="moderation_login"),
                path(
                    "logout/", custom_moderation_views.moderation_logout_view, name="moderation_logout"
                ),
                path("pda/", custom_moderation_views.pda_moderation_view, name="pda_moderation"),
                path("pda/<int:pda_id>/", custom_moderation_views.pda_detail_view, name="pda_detail"),
                path(
                    "pda/<int:pda_id>/approve/",
                    custom_moderation_views.pda_approve_view,
                    name="pda_approve",
                ),
                path(
                    "pda/<int:pda_id>/reject/",
                    custom_moderation_views.pda_reject_view,
                    name="pda_reject",
                ),
                path("forum/", custom_moderation_views.forum_moderation_view, name="forum_moderation"),
                path(
                    "forum/<int:thread_id>/",
                    custom_moderation_views.thread_detail_view,
                    name="thread_detail",
                ),
                path(
                    "forum/<int:thread_id>/approve/",
                    custom_moderation_views.thread_approve_view,
                    name="thread_approve",
                ),
                path(
                    "forum/<int:thread_id>/reject/",
                    custom_moderation_views.thread_reject_view,
                    name="thread_reject",
                ),
                path(
                    "reported/", custom_moderation_views.reported_content_view, name="reported_content"
                ),
                path(
                    "analytics/",
                    custom_moderation_views.analytics_dashboard_view,
                    name="analytics_dashboard",
                ),
                path(
                    "settings/",
                    custom_moderation_views.moderation_settings_view,
                    name="moderation_settings",
                ),
                path(
                    "profile/",
                    custom_moderation_views.moderation_profile_view,
                    name="moderation_profile",
                ),
                path(
                    "search/", custom_moderation_views.moderation_search_view, name="moderation_search"
                ),
                path(
                    "chart-data/",
                    custom_moderation_views.moderation_chart_data_api,
                    name="moderation_chart_data",
                ),
            ]
        ),
    ),
    # Add to the custom admin panel URLs
    path(
        "knowledge-base/",
        custom_admin_views.custom_admin_knowledge_base_list_view,
        name="custom_admin_knowledge_base_list",
    ),
    path(
        "knowledge-base/create/",
        custom_admin_views.custom_admin_knowledge_base_create_view,
        name="custom_admin_knowledge_base_create",
    ),
    path(
        "knowledge-base/<int:article_id>/",
        custom_admin_views.custom_admin_knowledge_base_detail_view,
        name="custom_admin_knowledge_base_detail",
    ),
    path(
        "knowledge-base/<int:article_id>/edit/",
        custom_admin_views.custom_admin_knowledge_base_edit_view,
        name="custom_admin_knowledge_base_edit",
    ),
    path(
        "knowledge-base/<int:article_id>/delete/",
        custom_admin_views.custom_admin_knowledge_base_delete_view,
        name="custom_admin_knowledge_base_delete",
    ),
    path(
        "knowledge-base/topics/",
        custom_admin_views.custom_admin_knowledge_base_topics_view,
        name="custom_admin_knowledge_base_topics",
    ),
    path(
        "knowledge-base/tags/",
        custom_admin_views.custom_admin_knowledge_base_tags_view,
        name="custom_admin_knowledge_base_tags",
    ),
]
