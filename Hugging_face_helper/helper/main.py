import os
import shutil
from huggingface_hub import HfApi, Repository, hf_hub_download, notebook_login


class HuggingFaceHelper:
    def __init__(
        self,
        token: str = None,
        repo_name: str = None,
        repo_local_dir: str = None,
        cache_dir: str = None,
    ):
        """
        Initialize HuggingFaceHelper with authentication token and repository info.

        Args:
            token (str, optional): Hugging Face authentication token
            repo_name (str, optional): Name of the repository (username/repo-name)
            repo_local_dir (str, optional): Local directory path for the repository
            cache_dir (str, optional): Directory path for caching downloaded files
        """
        if token:
            os.environ["HF_TOKEN"] = token
            self.token = token
        else:
            notebook_login()

        self.api = HfApi()
        self.repo_name = repo_name
        self.repo_local_dir = repo_local_dir
        self.cache_dir = cache_dir

        if repo_name:
            self.api.create_repo(repo_id=repo_name, exist_ok=True)

    def upload_model(self, local_model_path: str):
        """Upload a .pth PyTorch model to Hugging Face Hub."""
        repo_name = self.repo_name
        repo_local_dir = self.repo_local_dir

        if not repo_name or not repo_local_dir:
            raise ValueError("Repository name and local directory must be provided")

        # Create the repo if it doesn't exist
        self.api.create_repo(repo_id=repo_name, exist_ok=True)

        # Remove existing local repo directory if present
        if os.path.exists(repo_local_dir):
            shutil.rmtree(repo_local_dir)

        # Clone repository locally
        repo = Repository(local_dir=repo_local_dir, clone_from=repo_name)

        # Copy model file into repository directory
        shutil.copy(local_model_path, repo_local_dir)

        # Stage, commit, and push
        repo.git_add()
        repo.git_commit(f"Upload model {os.path.basename(local_model_path)}")
        repo.git_push()

    def download_model(self, filename: str) -> str:
        """Download a .pth PyTorch model file from the Hub."""
        repo_name = self.repo_name
        cache_dir = self.cache_dir

        if not repo_name:
            raise ValueError("Repository name must be provided")

        return hf_hub_download(repo_id=repo_name, filename=filename, cache_dir=cache_dir)

    def get_repo_files(self) -> list:
        """Get a list of files from a Hugging Face repository."""
        repo_name = self.repo_name

        if not repo_name:
            raise ValueError("Repository name must be provided")

        try:
            files = self.api.list_repo_files(repo_id=repo_name)
            return files
        except Exception as e:
            print(f"Error accessing repository: {str(e)}")
            return []

    def sync_repo(self) -> bool:
        """Synchronize local repository with remote Hugging Face repository."""
        repo_name = self.repo_name
        repo_local_dir = self.repo_local_dir

        if not repo_name or not repo_local_dir:
            raise ValueError("Repository name and local directory must be provided")

        try:
            # Get or create repository
            repo = Repository(local_dir=repo_local_dir, clone_from=repo_name)

            # Pull latest changes
            repo.git_pull()

            # Check if there are any local changes
            if repo.is_repo_clean():
                print(f"Repository {repo_name} is up to date")
                return True

            # Push any local changes
            repo.push_to_hub()
            print(f"Repository {repo_name} successfully synchronized")
            return True

        except Exception as e:
            print(f"Error synchronizing repository: {str(e)}")
            return False
