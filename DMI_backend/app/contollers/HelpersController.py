import os
from django.conf import settings


class URLHelper:
    def __init__(self) -> None:
        pass

    def convert_to_public_url(file_path: str) -> str:
        """
        Convert a file path to a public URL.

        Args:
            file_path (str): The file path to convert.

        Returns:
            str: The public URL.
        """
        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
        return f"{settings.HOST_URL}{settings.MEDIA_URL}{relative_path.replace(os.sep, '/')}"
