import os
from django.conf import settings

# Account for missing media directories
# List of required directories
required_directories = [
    os.path.join(settings.MEDIA_ROOT, "submissions"),
    os.path.join(settings.MEDIA_ROOT, "temp/temp_frames"),
    os.path.join(settings.MEDIA_ROOT, "temp/temp_crops"),
    os.path.join(settings.MEDIA_ROOT, "temp/temp_synthetic_media"),
]

# Create directories if they don't exist
for directory in required_directories:
    os.makedirs(directory, exist_ok=True)

# Account for missing media directories
# List of required directories
required_directories = ["./hf_helper_files/", "./hf_helper_files/cache/", "./hf_helper_files/repo/"]

# Create directories if they don't exist
for directory in required_directories:
    os.makedirs(directory, exist_ok=True)
