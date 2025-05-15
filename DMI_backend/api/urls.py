from django.urls import path
from .views import (
    auth_views,
    user_views,
    semantic_views,
    helper_views,
    pda_views,
    facial_watch_views,
    community_forum_views,
    knowledge_base_views,
    public_api_views,
    donations_views,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # User authentication endpoints
    path("user/signup/", auth_views.signup, name="signup"),
    path("user/login/", auth_views.login, name="login"),
    path("user/logout/", auth_views.logout, name="logout"),
    path("user/change_password/", auth_views.change_password, name="change_password"),
    path("user/change_email/", auth_views.change_email, name="change_email"),
    path("user/forgot_password/", auth_views.forgot_password, name="forgot_password"),
    path("user/reset_password/<str:token>/", auth_views.reset_password, name="reset_password"),
    # Token related endpoints
    path("auth/refresh_token/", auth_views.refresh_token, name="refresh_token"),
    # User info endpoints
    path("user/info/", user_views.get_user_info, name="get_user_info"),
    path("user/submissions/", user_views.manage_submission_history, name="manage_submission_history"),
    path("user/submissions/<str:submission_identifier>/", user_views.manage_submission, name="manage_submission"),
    # Media processing endpoints
    path("process/df/", semantic_views.process_deepfake_media, name="process_deepfake"),
    path("process/ai/", semantic_views.process_ai_generated_media, name="process_ai_generated_media"),
    path("process/metadata/", semantic_views.process_metadata, name="process_metadata"),
    path("process/text/", semantic_views.process_ai_generated_text, name="process_ai_generated_text"),
    # Public deepfake archive endpoints
    path("pda/search/", pda_views.browse_pda, name="browse_pda"),
    path("pda/details/<str:submission_identifier>/", pda_views.get_pda_submission_detail, name="get_pda_submission_detail"),
    path("pda/submit/", pda_views.submit_existing_to_pda, name="submit_existing_to_pda"),
    path("pda/submission/<str:submission_identifier>", pda_views.delete_pda_submission, name="delete_pda_submission"),
    # path("pda/submit_direct/", pda_views.submit_to_pda, name="submit_to_pda"),  # Deprecated for now
    # Facial watch system endpoints
    path("facial-watch/register/", facial_watch_views.register_face, name="register_face"),
    path("facial-watch/status/", facial_watch_views.get_registration_status, name="get_registration_status"),
    path("facial-watch/remove/", facial_watch_views.remove_registration, name="remove_registration"),
    path("facial-watch/history/", facial_watch_views.get_match_history, name="get_match_history"),
    path("facial-watch/search", facial_watch_views.search_faces_in_pda, name="search_faces_in_pda"),
    # Response codes endpoint
    path("docs/response_codes/", helper_views.get_response_codes, name="get_response_codes"),
    # Community forum endpoints
    path("forum/threads/", community_forum_views.get_threads, name="get_threads"),
    path("forum/threads/create/", community_forum_views.create_thread, name="create_thread"),
    path("forum/threads/<int:thread_id>/", community_forum_views.get_thread_detail, name="get_thread_detail"),
    path("forum/threads/<int:thread_id>/edit/", community_forum_views.edit_thread, name="edit_thread"),
    path("forum/threads/<int:thread_id>/delete/", community_forum_views.delete_thread, name="delete_thread"),
    path("forum/threads/<int:thread_id>/reply/", community_forum_views.add_reply, name="add_reply"),
    path("forum/threads/<int:thread_id>/replies/", community_forum_views.get_thread_replies, name="get_thread_replies"),
    path("forum/threads/<int:thread_id>/reactions/", community_forum_views.get_reaction_counts, name="get_thread_reactions"),
    path("forum/replies/<int:reply_id>/edit/", community_forum_views.edit_reply, name="edit_reply"),
    path("forum/replies/<int:reply_id>/delete/", community_forum_views.delete_reply, name="delete_reply"),
    path("forum/replies/<int:reply_id>/reactions/", community_forum_views.get_reaction_counts, name="get_reply_reactions"),
    path("forum/like/", community_forum_views.toggle_like, name="toggle_like"),
    path("forum/dislike/", community_forum_views.toggle_dislike, name="toggle_dislike"),
    path("forum/reaction/", community_forum_views.add_reaction, name="add_reaction"),
    path("forum/topics/", community_forum_views.get_topics, name="get_topics"),
    path("forum/tags/", community_forum_views.get_tags, name="get_tags"),
    path("forum/search/", community_forum_views.search_threads, name="search_threads"),
    # Knowledge Base endpoints
    path("knowledge-base/articles/", knowledge_base_views.get_articles, name="knowledge_base_get_articles"),
    path("knowledge-base/articles/<int:article_id>/", knowledge_base_views.get_article_detail, name="knowledge_base_get_article_detail"),
    path("knowledge-base/articles/create/", knowledge_base_views.create_article, name="knowledge_base_create_article"),
    path("knowledge-base/articles/<int:article_id>/update/", knowledge_base_views.update_article, name="knowledge_base_update_article"),
    path("knowledge-base/articles/<int:article_id>/delete/", knowledge_base_views.delete_article, name="knowledge_base_delete_article"),
    path("knowledge-base/articles/<int:article_id>/share/", knowledge_base_views.get_share_links, name="knowledge_base_get_share_links"),
    path("knowledge-base/topics/", knowledge_base_views.get_topics, name="knowledge_base_get_topics"),
    path("knowledge-base/topics/<int:topic_id>/articles/", knowledge_base_views.get_articles_by_topic, name="knowledge_base_get_articles_by_topic"),
    path("knowledge-base/search/", knowledge_base_views.search_articles, name="knowledge_base_search_articles"),
    # Admin/Moderator Knowledge Base endpoints
    path("knowledge-base/topics/create/", knowledge_base_views.create_topic, name="knowledge_base_create_topic"),
    path("knowledge-base/topics/<int:topic_id>/update/", knowledge_base_views.update_topic, name="knowledge_base_update_topic"),
    path("knowledge-base/topics/<int:topic_id>/delete/", knowledge_base_views.delete_topic, name="knowledge_base_delete_topic"),
    # Commented out endpoint
    # path('knowledge_base/upload_image/', knowledge_base_views.upload_image, name='kb_upload_image'),
    # API key management
    path("api-keys/", public_api_views.api_key_management, name="api_key_management"),
    path("api-keys/<int:key_id>/", public_api_views.api_key_detail, name="api_key_detail"),
    # Public API endpoints    path("public-api/deepfake-detection/", public_api_views.deepfake_detection_api, name="deepfake_detection_api"),
    path("public-api/ai-text-detection/", public_api_views.ai_text_detection_api, name="ai_text_detection_api"),
    path("public-api/ai-media-detection/", public_api_views.ai_media_detection_api, name="ai_media_detection_api"),
    # Donation endpoints
    path("donations/checkout/", donations_views.create_donation_checkout, name="create_donation_checkout"),
    path("donations/webhook/", donations_views.stripe_webhook, name="stripe_webhook"),
    path("donations/verify/<str:session_id>/", donations_views.verify_donation, name="verify_donation"),
    path("donations/", donations_views.get_donations, name="get_donations"),
    path("donations/<int:donation_id>/", donations_views.get_donation_detail, name="get_donation_detail"),
    path("donations/<int:donation_id>/refund/", donations_views.refund_donation, name="refund_donation"),
    path("donations/stats/", donations_views.get_donation_stats, name="get_donation_stats"),
]
