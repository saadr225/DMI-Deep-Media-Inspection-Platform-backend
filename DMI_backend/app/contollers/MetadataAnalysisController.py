import json
import os
import subprocess

from django.conf import settings


class MetadataAnalysisPipeline:
    def __init__(self) -> None:
        self.excluded_keys = ["SourceFile", "ExifTool:ExifToolVersion", "ExifTool:Warning"]

    def extract_metadata(self, file_path):
        """
        Extract metadata from an image or video file using ExifTool.
        Returns a dictionary with all metadata fields, excluding certain keys.
        """

        cmd = [
            "exiftool",
            "-j",  # JSON output
            "-G",  # Show all group names
            "-a",  # Allow duplicate tags
            "-b",  # Extract binary data
            "-f",  # Force output
            "-u",  # Extract unknown tags
            "-ee",  # Extract embedded info
            "-struct",  # Show structural information
            file_path,
        ]

        try:
            # Run the command; capture output as text
            result = subprocess.run(cmd, capture_output=True, check=True, text=True)
            # ExifTool returns a JSON array with one dict per file
            data = json.loads(result.stdout)
            if data:
                metadata = data[0]
                # Exclude unwanted tags
                for key in self.excluded_keys:
                    metadata.pop(key, None)
                return metadata
            else:
                return {}
        except subprocess.CalledProcessError as e:
            print(f"Error running ExifTool: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return {}

    def convert_to_public_url(self, file_path: str) -> str:
        """
        Convert a file path to a public URL.

        Args:
            file_path (str): The file path to convert.

        Returns:
            str: The public URL.
        """
        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
        return f"{settings.HOST_URL}{settings.MEDIA_URL}{relative_path.replace(os.sep, '/')}"
