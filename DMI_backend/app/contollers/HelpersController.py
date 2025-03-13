import os
import shutil
import time
import json
import socket
from urllib.error import URLError
from django.conf import settings
from huggingface_hub import HfApi, Repository, hf_hub_download, notebook_login
from huggingface_hub.utils import RepositoryNotFoundError, RevisionNotFoundError

# Fix the import error by using more general exceptions
# Instead of: from huggingface_hub.hf_api import HfConnectionError


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


class HuggingFaceHelper:
    def __init__(
        self,
        token: str = None,
        repo_name: str = None,
        repo_local_dir: str = None,
        cache_dir: str = None,
        offline_mode: bool = None,  # Changed to None to allow auto-detection
        check_updates_interval: int = 24 * 3600,  # 24 hours in seconds
    ):
        """
        Initialize HuggingFaceHelper with authentication token and repository info.

        Args:
            token (str, optional): Hugging Face authentication token
            repo_name (str, optional): Name of the repository (username/repo-name)
            repo_local_dir (str, optional): Local directory path for the repository
            cache_dir (str, optional): Directory path for caching downloaded files
            offline_mode (bool, optional): Whether to operate in offline mode when network is unavailable
                                          If None, auto-detect based on connectivity
            check_updates_interval (int, optional): Time interval (in seconds) to check for updates
        """
        self.check_updates_interval = check_updates_interval
        self.metadata_file = os.path.join(cache_dir or ".", "hf_metadata.json") if cache_dir else None
        self.metadata = self._load_metadata()

        # Auto-detect offline mode if not explicitly set
        self.offline_mode = (
            offline_mode if offline_mode is not None else not self._check_internet_connection()
        )

        if self.offline_mode:
            print("Operating in offline mode")
        else:
            print("Operating in online mode")

        if token:
            os.environ["HF_TOKEN"] = token
            self.token = token
        else:
            try:
                if not self.offline_mode:
                    notebook_login()
            except Exception as e:
                print(f"Login failed: {str(e)}")
                self.offline_mode = True
                print("Switching to offline mode")

        self.api = HfApi()
        self.repo_name = repo_name
        self.repo_local_dir = repo_local_dir
        self.cache_dir = cache_dir

        if repo_name and not self.offline_mode:
            try:
                self.api.create_repo(repo_id=repo_name, exist_ok=True)
            except Exception as e:
                print(f"Error creating or accessing repo: {str(e)}")
                self.offline_mode = True
                print("Switching to offline mode")

    def _check_internet_connection(self, host="huggingface.co", port=443, timeout=2):
        """
        Check if there is an internet connection by attempting to connect to HuggingFace.

        Args:
            host (str): Host to connect to for checking connectivity
            port (int): Port to connect to
            timeout (int): Connection timeout in seconds

        Returns:
            bool: True if internet connection is available, False otherwise
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception as e:
            print(f"Internet connectivity check failed: {str(e)}")
            return False

    def _load_metadata(self):
        """Load metadata about downloaded files."""
        if not self.metadata_file or not os.path.exists(self.metadata_file):
            return {}

        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading metadata: {str(e)}")
            return {}

    def _save_metadata(self):
        """Save metadata about downloaded files."""
        if not self.metadata_file:
            return

        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f)
        except Exception as e:
            print(f"Error saving metadata: {str(e)}")

    def download_model(self, filename: str, force_download: bool = False, timeout: int = 5) -> str:
        """
        Download a .pth PyTorch model file from the Hub with improved error handling.

        Args:
            filename (str): Name of the file to download
            force_download (bool): Whether to force download even if file exists locally
            timeout (int): Network operation timeout in seconds

        Returns:
            str: Path to the downloaded file or local file if already exists and up-to-date
        """
        repo_name = self.repo_name
        cache_dir = self.cache_dir

        if not repo_name:
            raise ValueError("Repository name must be provided")

        # First check if file exists locally in ML_MODELS_DIR
        local_path = (
            os.path.join(settings.ML_MODELS_DIR, filename)
            if hasattr(settings, "ML_MODELS_DIR")
            else None
        )
        if local_path and os.path.exists(local_path):
            print(f"Using existing local file: {local_path}")
            return local_path

        # Re-check internet connection if not in offline mode
        if not self.offline_mode and not self._check_internet_connection():
            self.offline_mode = True
            print("Internet connection unavailable. Switching to offline mode.")

        # Check if we're in offline mode
        if self.offline_mode:
            # In offline mode, look for the file in cache
            cached_path = (
                os.path.join(cache_dir, "models--" + repo_name.replace("/", "--"), "snapshots")
                if cache_dir
                else None
            )

            # Try to find it in cache
            if cached_path and os.path.exists(cached_path):
                for root, dirs, files in os.walk(cached_path):
                    for f in files:
                        if f == filename:
                            print(f"Using cached file in offline mode: {os.path.join(root, f)}")
                            return os.path.join(root, f)

            raise ValueError(f"File {filename} not found locally and cannot download in offline mode")

        # Check if an update is needed
        needs_update = force_download
        file_key = f"{repo_name}/{filename}"

        if not needs_update and file_key in self.metadata:
            last_check = self.metadata[file_key].get("last_check", 0)
            now = time.time()

            # Check if update interval has passed
            if now - last_check > self.check_updates_interval:
                needs_update = True
        else:
            needs_update = True

        try:
            if needs_update:
                print(f"Checking for updates to {filename}...")
                # Get file info from repo to check if it changed
                try:
                    file_info = self.api.file_info(repo_id=repo_name, path=filename, timeout=timeout)
                    self.file_info = file_info  # Store for later use

                    # If we have metadata and the last modified time matches, skip download
                    if (
                        file_key in self.metadata
                        and self.metadata[file_key].get("last_modified") == file_info.last_modified
                    ):
                        print(f"File {filename} is up to date")

                        # Update the last check time
                        self.metadata[file_key]["last_check"] = time.time()
                        self._save_metadata()

                        # Return the previously downloaded path
                        return self.metadata[file_key]["local_path"]

                    # Otherwise, force download
                    force_download = True
                except Exception as e:
                    print(f"Error checking file info: {str(e)}")
                    # If we can't check file info but have a local copy, use that
                    if file_key in self.metadata and os.path.exists(
                        self.metadata[file_key]["local_path"]
                    ):
                        print(f"Using existing local file: {self.metadata[file_key]['local_path']}")
                        return self.metadata[file_key]["local_path"]
                    # Otherwise we'll attempt to download anyway

            # Download the file
            downloaded_path = hf_hub_download(
                repo_id=repo_name,
                filename=filename,
                cache_dir=cache_dir,
                force_download=force_download,
                force_filename=filename,
                local_files_only=False,
                token=getattr(self, "token", None),
            )

            # Update metadata
            if hasattr(self, "file_info"):
                self.metadata[file_key] = {
                    "last_modified": self.file_info.last_modified,
                    "last_check": time.time(),
                    "local_path": downloaded_path,
                }
            else:
                self.metadata[file_key] = {"last_check": time.time(), "local_path": downloaded_path}

            self._save_metadata()
            return downloaded_path

        except (URLError, ConnectionError, TimeoutError) as e:
            # Changed from specific HfConnectionError to more general network errors
            print(f"Network error when downloading {filename}: {str(e)}")
            print("Switching to offline mode")
            self.offline_mode = True

            # Try to find local file
            if file_key in self.metadata and os.path.exists(self.metadata[file_key]["local_path"]):
                print(f"Using existing local file: {self.metadata[file_key]['local_path']}")
                return self.metadata[file_key]["local_path"]

            # Look in ML_MODELS_DIR
            local_path = (
                os.path.join(settings.ML_MODELS_DIR, filename)
                if hasattr(settings, "ML_MODELS_DIR")
                else None
            )
            if local_path and os.path.exists(local_path):
                print(f"Using local file: {local_path}")
                return local_path

            raise ValueError(
                f"File {filename} cannot be downloaded due to network issues and no local copy exists"
            )

        except (RepositoryNotFoundError, RevisionNotFoundError) as e:
            print(f"Repository or file not found: {str(e)}")
            raise

        except Exception as e:
            print(f"Error downloading {filename}: {str(e)}")
            raise
