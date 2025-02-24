from django.apps import AppConfig
import os
from django.conf import settings


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        """
        Initialize app-specific requirements when Django starts
        """
        # Media directories
        media_directories = [
            os.path.join(settings.MEDIA_ROOT, "submissions"),
            os.path.join(settings.MEDIA_ROOT, "temp/temp_frames"),
            os.path.join(settings.MEDIA_ROOT, "temp/temp_crops"),
            os.path.join(settings.MEDIA_ROOT, "temp/temp_synthetic_media"),
        ]

        # Hugging Face helper directories
        hf_directories = ["./hf_helper_files/", "./hf_helper_files/cache/", "./hf_helper_files/repo/"]

        # Create all required directories
        for directory in media_directories + hf_directories:
            os.makedirs(directory, exist_ok=True)
