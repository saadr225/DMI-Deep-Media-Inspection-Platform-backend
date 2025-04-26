from typing import Dict, Tuple, Union
import torch
import torch.nn.functional as tnf
import torchvision.transforms as transforms
from PIL import Image
import os
import cv2
import hashlib
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image
from django.conf import settings


class AIGeneratedMediaDetectionPipeline:
    """
    Simplified AI detection for single images with GradCAM heatmap.
    """

    def __init__(
        self,
        model_path: str,
        synthetic_media_dir: str,
        threshold: float = 0.7,
        log_level: int = 0,
        FRAMES_FILE_FORMAT: str = "jpg",
    ) -> None:
        self.device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: torch.nn.Module = torch.load(model_path, map_location=self.device)
        self.model.eval()
        self.threshold: float = threshold
        self.synthetic_media_dir: str = synthetic_media_dir
        self.log_level: int = log_level
        self.FRAMES_FILE_FORMAT: str = FRAMES_FILE_FORMAT
        self.label_map: Dict[int, str] = {0: "real", 1: "fake"}
        self.transform: transforms.Compose = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

    def generate_6_digit_hash(self, input_string: str) -> str:
        hash_object = hashlib.sha256(input_string.encode())
        hex_dig = hash_object.hexdigest()
        hash_int = int(hex_dig[:6], 16)
        return str(hash_int).zfill(6)

    def hash_file_content(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            file_content = f.read()
        return self.generate_6_digit_hash(file_content.decode("latin1"))

    def hash_file_name(self, file_path: str) -> str:
        file_name = os.path.basename(file_path)
        return self.generate_6_digit_hash(file_name)

    def generate_combined_hash(self, file_path: str) -> str:
        file_content_hash = self.hash_file_content(file_path)
        file_name_hash = self.hash_file_name(file_path)
        return f"{file_content_hash}_{file_name_hash}"

    def load_image_preprocessed(self, image_path: str) -> torch.Tensor:
        image = Image.open(image_path).convert("RGB")
        image = self.transform(image)
        return image.unsqueeze(0).to(self.device)

    def process_frame(self, image_path: str) -> Tuple[str, float, str]:
        image_tensor = self.load_image_preprocessed(image_path)
        with torch.no_grad():
            output = self.model(image_tensor)
            probabilities = tnf.softmax(output, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        predicted_class: int = predicted.item()
        predicted_label: str = self.label_map[predicted_class]
        confidence_score: float = confidence.item()

        gradcam_path: str = image_path.replace(
            f".{self.FRAMES_FILE_FORMAT}", f"_gradcam.{self.FRAMES_FILE_FORMAT}"
        )
        target_layers = [self.model.layer4[-1]]
        cam = GradCAM(model=self.model, target_layers=target_layers)
        targets = [ClassifierOutputTarget(predicted_class)]
        grayscale_cam = cam(input_tensor=image_tensor, targets=targets)[0, :]
        rgb_img = cv2.imread(image_path)
        rgb_img = cv2.resize(rgb_img, (224, 224)) / 255.0
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
        cv2.imwrite(gradcam_path, visualization)

        return predicted_label, confidence_score, gradcam_path

    def convert_to_public_url(self, file_path: str) -> str:
        """
        Convert a file path to a public URL.
        """
        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
        return f"{settings.HOST_URL}{settings.MEDIA_URL}{relative_path.replace(os.sep, '/')}"

    def process_image(self, image_path: str) -> Dict[str, Union[str, float]]:
        """
        Single-image AI detection with GradCAM visualization.
        """
        file_identifier: str = self.generate_combined_hash(image_path)
        output_file: str = os.path.join(
            self.synthetic_media_dir, f"{file_identifier}_0.{self.FRAMES_FILE_FORMAT}"
        )
        if not os.path.exists(output_file):
            img = cv2.imread(image_path)
            cv2.imwrite(output_file, img)

        prediction, conf, gradcam_path = self.process_frame(output_file)
        return {
            "file_identifier": file_identifier,
            "media_path": self.convert_to_public_url(output_file),
            "prediction": prediction,
            "confidence": conf,
            "gradcam_path": self.convert_to_public_url(gradcam_path),
        }
