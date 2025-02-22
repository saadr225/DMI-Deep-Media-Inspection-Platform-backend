import os
import shutil
from huggingface_hub import HfApi, Repository, hf_hub_download, notebook_login

class HuggingFaceHelper:
    def upload_model(repo_name: str, local_model_path: str, repo_local_dir: str, token: str = None):
        """
        Upload a .pth PyTorch model to Hugging Face Hub.

        Args:
            repo_name: Repository name in the format "username/repo_name".
            local_model_path: Path to the .pth model file.
            repo_local_dir: Local directory to clone the repository.
            token: (Optional) Hugging Face token.
        """
        # Login to Hugging Face (will prompt for token if not provided)
        if not token:
            notebook_login()
        else:
            os.environ["HF_TOKEN"] = token

        # Create the repo if it doesn't exist
        api = HfApi()
        api.create_repo(repo_id=repo_name, exist_ok=True)

        # Remove existing local repo directory if present
        if os.path.exists(repo_local_dir):
            shutil.rmtree(repo_local_dir)

        # Clone (or initialize) the repository locally
        repo = Repository(local_dir=repo_local_dir, clone_from=repo_name)

        # Copy model file into the repository directory
        shutil.copy(local_model_path, repo_local_dir)

        # Stage, commit, and push the model file
        repo.git_add()
        repo.git_commit(f"Upload model {os.path.basename(local_model_path)}")
        repo.git_push()


    def download_model(repo_name: str, filename: str, cache_dir: str = None) -> str:
        """
        Download a .pth PyTorch model file from the Hugging Face Hub.

        Args:
            repo_name: Repository name in the format "username/repo_name".
            filename: Name of the .pth file in the repo.
            cache_dir: Directory to use for caching the downloaded file.

        Returns:
            The local file path of the downloaded model.
        """
        local_path = hf_hub_download(repo_id=repo_name, filename=filename, cache_dir=cache_dir)
        return local_path