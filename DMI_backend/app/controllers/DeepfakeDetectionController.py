# Importing necessary libraries
import json
import torch
import torch.nn as nn
import torch.nn.functional as tnf
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image, ImageChops, ImageEnhance
import os, shutil
import matplotlib.pyplot as plt
import numpy as np
import cv2
from ultralytics import YOLO
import hashlib
from natsort import natsorted
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image
from django.conf import settings
from typing import List, Optional, Dict, Tuple, Union

from app.controllers.MediaProcessorController import MediaProcessor

class DeepfakeDetectionPipeline:
    def __init__(
        self,
        frame_model_path: str,
        crop_model_path: str,
        frames_dir: str,
        crops_dir: str,
        threshold: float = 0.4,
        log_level: int = 0,
        FRAMES_FILE_FORMAT: str = "jpg",
    ) -> None:
        """
        Initialize the pipeline with both frame and crop models.

        Args:
            frame_model_path (str): Path to the frame analysis model
            crop_model_path (str): Path to the crop analysis model
            frames_dir (str): Directory containing all frames
            crops_dir (str): Directory containing all crops
            threshold (float): Confidence threshold for face detection
            log_level (int): Logging verbosity level
        """
        # Load models and move to appropriate device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.frame_model = torch.load(frame_model_path, map_location=self.device)
        self.crop_model = torch.load(crop_model_path, map_location=self.device)
        self.frame_model.eval()
        self.crop_model.eval()

        # Set up image transformation
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

        self.log_level = log_level
        self.label_map = {0: "real", 1: "fake"}
        self.frames_dir = frames_dir
        self.crops_dir = crops_dir
        self.FRAMES_FILE_FORMAT = FRAMES_FILE_FORMAT

        # Initialize MediaProcessor for face detection
        self.media_processor = MediaProcessor(
            threshold=threshold,
            log_level=log_level,
            FRAMES_FILE_FORMAT=self.FRAMES_FILE_FORMAT,
        )

    def get_crops_for_frame(self, file_identifier: str, frame_index: int, crops_dir: str) -> List[str]:
        """
        Get all crops belonging to a specific frame using the naming scheme.

        Args:
            file_identifier (str): Combined hash identifier (content_hash + name_hash)
            frame_index (int): Frame index (0 for images)
            crops_dir (str): Directory containing all crops

        Returns:
            list: Paths to relevant crop files
        """
        crop_prefix = f"{file_identifier}_{frame_index}_"
        relevant_crops = []

        for filename in os.listdir(crops_dir):
            if filename.startswith(crop_prefix):
                crop_path = os.path.join(crops_dir, filename)
                relevant_crops.append(crop_path)

        return natsorted(relevant_crops)  # Sort to ensure consistent ordering

    def load_image_preprocessed(self, image_path: str, show_image: bool = False) -> torch.Tensor:
        if show_image:
            cv_img = cv2.imread(image_path)

            # Convert the image from BGR to RGB for displaying with matplotlib
            cv_img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)

            # Display the image with detected faces
            plt.figure(figsize=(8, 6))
            plt.imshow(cv_img_rgb)
            plt.axis("off")  # Hide axis
            plt.title(f"Test image")
            plt.show()

        #  Define the transformations (should be the same as used in training)
        transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),  # Resize the image to the input size of the model
                transforms.ToTensor(),  # Convert image to tensor
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),  # Normalize as per the pre-trained model's requirements
            ]
        )

        # Load the image
        image = Image.open(image_path).convert("RGB")

        # Apply the transformations
        image = transform(image)

        # Add a batch dimension (models expect a batch of images, even if it's just one image)
        image = image.unsqueeze(0)

        return image

    def process_frame(self, image_path: str, type: str = "frame") -> Tuple[str, float, Optional[str]]:
        """
        Process a single frame through frame-level model with integrated GradCAM for frames only.

        Args:
            image_path (str): Path to the image file
            type (str): Type of processing, either "frame" or "crop"

        Returns:
            tuple: (predicted_label, confidence_score, gradcam_path if type=="frame" else None)
        """
        if type not in ["frame", "crop"]:
            raise ValueError("Invalid type. Expected 'frame' or 'crop'.")

        model = self.frame_model if type == "frame" else self.crop_model
        gradcam_path = None

        # Load and preprocess image
        image = self.load_image_preprocessed(image_path, show_image=False)
        image = image.to(self.device)

        # Make prediction
        with torch.no_grad():
            output = model(image)
            probabilities = tnf.softmax(output, dim=1)
            confidence, predicted = torch.max(probabilities, 1)
            predicted_class = predicted.item()

        predicted_label = self.label_map[predicted_class]
        confidence_score = confidence.item()

        # Generate GradCAM only for frame-level analysis
        if type == "frame":
            gradcam_path = image_path.replace(
                f".{self.FRAMES_FILE_FORMAT}", f"_gradcam.{self.FRAMES_FILE_FORMAT}"
            )

            # Target the last convolutional layer
            target_layers = [model.layer4[-1]]

            # Create GradCAM object
            cam = GradCAM(model=model, target_layers=target_layers)

            # Define target for GradCAM
            targets = [ClassifierOutputTarget(predicted_class)]

            # Generate grayscale CAM
            grayscale_cam = cam(input_tensor=image, targets=targets)
            grayscale_cam = grayscale_cam[0, :]

            # Load and prepare original image for overlay
            rgb_img = cv2.imread(image_path)
            rgb_img = cv2.resize(rgb_img, (224, 224))
            # rgb_img = cv2.cvtColor(rgb_img, cv2.COLOR_BGR2RGB) #convert BGR to RGB color space
            rgb_img = rgb_img / 255.0

            # Create visualization
            visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
            # visualization = cv2.cvtColor(visualization, cv2.COLOR_BGR2RGB) #convert BGR to RGB color space

            # plt.imshow(visualization)

            # Save visualization
            cv2.imwrite(gradcam_path, visualization)

            if self.log_level >= 2:
                print(f"GradCAM saved to: {gradcam_path}")

        if self.log_level >= 2:
            print(f"Type: {type}")
            print(f"Predicted label: {predicted_label}")
            print(f"Confidence score: {confidence_score*100:.2f}")

        return (
            predicted_label,
            confidence_score,
            gradcam_path if type == "frame" else None,
        )

    def analyze_frame_with_crops(
        self, image_path: str, frame_id: str
    ) -> Dict[str, Union[str, List[Dict[str, Union[int, str, float]]], Optional[str]]]:
        """
        Analyze a frame both at frame-level and crop-level.

        Args:
            image_path (str): Path to the image file
            frame_id (str): Identifier for the frame

        Returns:
            dict: Analysis results including frame and crop predictions
        """
        results = {
            "frame_id": frame_id,
            "frame_analysis": None,
            "crop_analyses": [],
            "final_verdict": None,
            "frame_path": self.convert_to_public_url(image_path),
            "crop_paths": [],
            "ela_path": None,
            "gradcam_path": None,
        }

        # Frame-level analysis with GradCAM
        frame_pred, frame_conf, gradcam_path = self.process_frame(image_path, type="frame")
        results["frame_analysis"] = {"prediction": frame_pred, "confidence": frame_conf}
        results["gradcam_path"] = self.convert_to_public_url(gradcam_path)

        # Get crops for this frame
        frame_index = 0 if "_" not in frame_id else int(frame_id.split("_")[-1])
        file_identifier = frame_id.rsplit("_", 1)[0]
        crop_paths = self.get_crops_for_frame(file_identifier, frame_index, self.crops_dir)

        # Analyze each crop (without GradCAM)
        for crop_path in crop_paths:
            crop_pred, crop_conf, _ = self.process_frame(crop_path, type="crop")

            crop_index = int(os.path.splitext(crop_path)[0].split("_")[-1])

            results["crop_analyses"].append(
                {
                    "face_index": crop_index,
                    "prediction": crop_pred,
                    "confidence": crop_conf,
                }
            )
            results["crop_paths"].append(self.convert_to_public_url(crop_path))

        # Determine final verdict
        if len(results["crop_analyses"]) > 0:
            frame_is_fake = frame_pred == "fake"
            crops_fake_count = sum(
                1 for crop in results["crop_analyses"] if crop["prediction"] == "fake"
            )
            crops_total = len(results["crop_analyses"])

            if frame_is_fake and crops_fake_count > crops_total / 2:
                results["final_verdict"] = "fake"
            else:
                results["final_verdict"] = "real"
        else:
            results["final_verdict"] = frame_pred

        # Perform ELA analysis
        results["ela_path"] = self.convert_to_public_url(self.perform_ela_analysis(image_path))

        return results

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

    # def perform_ela_analysis(self, image_path: str) -> str:
    #     """
    #     Perform Error Level Analysis (ELA) on the image using the new practical logic.

    #     Args:
    #         image_path (str): Path to the image file

    #     Returns:
    #         str: Path to the ELA image
    #     """
    #     ela_image_path = image_path.replace(
    #         f".{self.FRAMES_FILE_FORMAT}", f"_ela.{self.FRAMES_FILE_FORMAT}"
    #     )
    #     quality = 90  # quality parameter for JPEG compression
    #     temp_filename = os.path.join(os.path.dirname(image_path), "temp_file_name.jpg")

    #     # Open the original image and convert to RGB
    #     original_image = Image.open(image_path).convert("RGB")
    #     # Save as JPEG with defined quality
    #     original_image.save(temp_filename, "JPEG", quality=quality)
    #     temp_image = Image.open(temp_filename)

    #     # Calculate ELA: difference between original and compressed image
    #     ela_image = ImageChops.difference(original_image, temp_image)
    #     extrema = ela_image.getextrema()
    #     max_diff = sum([ex[1] for ex in extrema]) / 3
    #     if max_diff == 0:
    #         max_diff = 1
    #     scale = 255.0 / max_diff
    #     ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)

    #     # Save the ELA image to the target path
    #     ela_image.save(ela_image_path)

    #     # Clean up the temporary file
    #     if os.path.exists(temp_filename):
    #         os.remove(temp_filename)

    #     return ela_image_path

    def perform_ela_analysis(self, image_path: str) -> str:
        """
        Perform Error Level Analysis (ELA) on the image.

        Args:
            image_path (str): Path to the image file

        Returns:
            str: Path to the ELA image
        """
        ela_image_path = image_path.replace(
            f".{self.FRAMES_FILE_FORMAT}", f"_ela.{self.FRAMES_FILE_FORMAT}"
        )

        # # Skip if ELA image already exists
        # if os.path.exists(ela_image_path):
        #     if self.log_level >= 1:
        #         print(f"Skipping frame {ela_image_path}: already exists")
        #     return ela_image_path

        # Open image using PIL
        original_image = Image.open(image_path)
        temp_compressed = os.path.join(os.path.dirname(image_path), "temp_compressed.jpg")

        # Save compressed version
        quality = 90
        scale_multiplier = 50
        original_image.save(temp_compressed, "JPEG", quality=quality)
        compressed_image = Image.open(temp_compressed)

        # Calculate difference
        ela_image = ImageChops.difference(original_image, compressed_image)

        # Apply noise boost and scaling
        ela_scaled = ela_image.point(lambda x: np.sign(x) * (np.abs(x) ** 1.5 * scale_multiplier))

        # Save ELA image
        ela_scaled.save(ela_image_path)

        # Clean up temporary file
        if os.path.exists(temp_compressed):
            os.remove(temp_compressed)

        return ela_image_path

    def process_media(self, media_path: str, frame_rate: int = 2) -> (
        Dict[
            str,
            Union[
                str,
                List[Dict[str, Union[str, List[Dict[str, Union[int, str, float]]], Optional[str]]]],
                Dict[str, Union[int, float, bool]],
            ],
        ]
        | bool
    ):
        """
        Process a media file (image or video) through the pipeline.

        Args:
            media_path (str): Path to the media file
            frame_rate (int): Frame rate for video processing

        Returns:
            dict: Analysis results for the entire media file
        """
        media_type = self.media_processor.check_media_type(media_path)

        # Generate file identifier using MediaProcessor's hash functions
        file_identifier = self.media_processor.generate_combined_hash(media_path)

        face_found = False

        # Process media file for frames using MediaProcessor
        face_found = self.media_processor.process_media_file(
            media_path,
            self.frames_dir,
            generate_crops_flag=False,
            frame_rate=frame_rate,
        )
        if face_found:
            # Process media file for crops using MediaProcessor
            self.media_processor.process_media_file(
                media_path, self.crops_dir, generate_crops_flag=True, frame_rate=frame_rate
            )

            results = {
                "media_path": self.convert_to_public_url(media_path),
                "media_type": media_type,
                "file_identifier": file_identifier,
                "frame_results": [],
            }

            if media_type == "Image":
                media_path = os.path.join(
                    self.frames_dir, f"{file_identifier}_0.{self.FRAMES_FILE_FORMAT}"
                )
                frame_results = self.analyze_frame_with_crops(media_path, f"{file_identifier}_0")
                results["media_path"] = self.convert_to_public_url(media_path)
                results["frame_results"].append(frame_results)

            elif media_type == "Video":
                frames = [
                    os.path.join(self.frames_dir, f)
                    for f in os.listdir(self.frames_dir)
                    if (f.startswith(file_identifier) and ("ela" not in f and "gradcam" not in f))
                ]
                frames = natsorted(frames)
                for frame_index, frame_path in enumerate(frames):
                    frame_results = self.analyze_frame_with_crops(
                        frame_path, f"{file_identifier}_{frame_index}"
                    )
                    results["frame_results"].append(frame_results)

            # Calculate overall statistics
            results["statistics"] = self._calculate_statistics(results["frame_results"])

            return results
        else:
            return False

    def _calculate_statistics(
        self,
        frame_results: List[
            Dict[str, Union[str, List[Dict[str, Union[int, str, float]]], Optional[str]]]
        ],
    ) -> Dict[str, Union[int, float, bool]]:
        """Calculate overall statistics from frame results."""
        total_frames = len(frame_results)
        if total_frames == 0:
            return {
                "confidence": 0,
                "is_deepfake": False,
                "total_frames": 0,
                "fake_frames": 0,
                "fake_frames_percentage": 0,
                "total_crops": 0,
                "fake_crops": 0,
                "fake_crops_percentage": 0,
            }

        confidence_scores = [f["frame_analysis"]["confidence"] for f in frame_results]
        confidence_score = np.mean(confidence_scores)

        fake_frames = sum(1 for f in frame_results if f["final_verdict"] == "fake")
        real_frames = total_frames - fake_frames

        total_crops = sum(len(f["crop_analyses"]) for f in frame_results)
        fake_crops = sum(
            sum(1 for crop in f["crop_analyses"] if crop["prediction"] == "fake") for f in frame_results
        )

        is_deepfake = fake_frames > real_frames

        return {
            "confidence": confidence_score,
            "is_deepfake": is_deepfake,
            "total_frames": total_frames,
            "fake_frames": fake_frames,
            "fake_frames_percentage": (fake_frames / total_frames * 100),
            "total_crops": total_crops,
            "fake_crops": fake_crops,
            "fake_crops_percentage": ((fake_crops / total_crops * 100) if total_crops > 0 else 0),
        }

    # def _save_results(self, results, output_dir):
    #     """Save analysis results to output directory."""
    #     os.makedirs(output_dir, exist_ok=True)
    #     output_path = os.path.join(output_dir, f"{results['file_identifier']}_analysis.json")

    #     with open(output_path, "w") as f:
    #         json.dump(results, f, sort_keys=True, indent=4)
