import os
from django.conf import settings

# Account for missing media directories
# List of required directories
required_directories = ["../Hugging_face/cache/", "../Hugging_face/repo/"]

# Create directories if they don't exist
for directory in required_directories:
    os.makedirs(directory, exist_ok=True)
