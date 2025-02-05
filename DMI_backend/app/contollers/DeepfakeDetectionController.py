# Importing necessary libraries
import json
import torch
import torch.nn as nn
import torch.nn.functional as tnf
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image, ImageChops
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


class MediaProcessor:
    """
    A class for detecting and extracting faces from images and videos using YOLOv8.
    """

    def __init__(
        self,
        model_path=f"{settings.ML_MODELS_DIR}/yolov8n.pt",
        threshold=0.5,
        log_level=0,
        FRAMES_FILE_FORMAT="jpg",
    ):
        """
        Initialize the FaceDetector.

        Args:
            model_path (str): Path to the YOLOv8 model file.
            threshold (float): Confidence threshold for face detection.
            log_level (int): Level of logging (0: None, 1: Basic, 2: Verbose).
        """
        self.model = YOLO(model_path)
        self.threshold = threshold
        self.log_level = log_level
        self.supported_image_formats = [".jpg", ".jpeg", ".png"]
        self.supported_video_formats = [".mp4", ".avi", ".mov"]
        self.FRAMES_FILE_FORMAT = FRAMES_FILE_FORMAT
        print("Warning: frame_rate value ignored for Image media\nReason: Image input")
        print(
            "\nWarning: naming scheme: \nImage: {file_content_hash}_{file_name_hash}_{frame_index=0}_{crop_index}.{extension}\nVideo: {file_content_hash}_{file_name_hash}_{frame_index}_{crop_index}.{extension}\n"
        )

    def detect_face(self, frame):
        """
        Detect faces in a given frame.

        Args:
            frame (numpy.ndarray): Input image frame.

        Returns:
            tuple: Detected faces (dict) and a boolean indicating if faces were found.
        """
        try:
            # Run detection
            if self.log_level >= 3:
                results = self.model(frame)
            else:
                results = self.model(frame, verbose=False)

            # Extract boxes, scores, and classes
            boxes = results[0].boxes.xyxy.cpu().numpy()
            scores = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()

            detected_faces = {}
            face_detected = False

            # Filter and save boxes for persons (class ID 0)
            for index, (box, score, object_class) in enumerate(
                zip(boxes, scores, classes)
            ):
                if object_class == 0 and score > self.threshold:
                    x1, y1, x2, y2 = map(int, box)
                    detected_faces[index] = {
                        "top_left": (x1, y1),
                        "bottom_right": (x2, y2),
                        "score": score,
                    }
                    face_detected = True

            # Logging
            if self.log_level >= 2:
                print(f"{'Faces' if face_detected else 'No faces'} detected in frame")

            return detected_faces, face_detected

        except Exception as e:
            print(f"Error processing frame: {e}")
            return None, False

    def generate_crops(
        self, frame, output_dir, frame_index, detected_faces, frame_id, show_crops=False
    ):
        """
        Generate and save face crops from a frame.

        Args:
            frame (numpy.ndarray): Input image frame.
            output_dir (str): Directory to save face crops.
            frame_index (int): Index of the current frame.
            detected_faces (dict): Dictionary of detected faces.
            frame_id (str): Identifier for the frame.
            show_crops (bool): Whether to display the crops (for debugging).
        """
        for face_idx, face_data in detected_faces.items():
            top_left = face_data["top_left"]
            bottom_right = face_data["bottom_right"]

            # Crop the face from the frame
            face_crop = frame[
                top_left[1] : bottom_right[1], top_left[0] : bottom_right[0]
            ]

            if show_crops:
                # Resize and display the face crop (for debugging)
                face_crop_resized = cv2.resize(
                    face_crop, (224, 224), interpolation=cv2.INTER_CUBIC
                )
                cv2.imshow(
                    f"Face {face_idx} from Frame {frame_index}", face_crop_resized
                )
                cv2.waitKey(0)
                cv2.destroyAllWindows()

            # Generate output path for the face crop
            output_face_path = os.path.join(
                output_dir,
                f"{frame_id}_{frame_index}_{face_idx}.{self.FRAMES_FILE_FORMAT}",
            )

            # Check if the crop already exists
            if os.path.exists(output_face_path):
                if self.log_level >= 2:
                    print(f"Skipping crop {output_face_path}: already exists")
                continue
            if self.log_level>=2:
                print("Crop saved at: ", output_face_path)
            # Save the face crop
            cv2.imwrite(output_face_path, face_crop)

    def check_media_type(self, file_path):
        """
        Check the type of media file.

        Args:
            file_path (str): Path to the media file.

        Returns:
            str: Type of media ('Image', 'Video', or error message).
        """
        if not os.path.exists(file_path):
            return "File does not exist"

        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension in self.supported_image_formats:
            try:
                with Image.open(file_path) as img:
                    img.verify()
                return "Image"
            except:
                return "Invalid image file"
        elif file_extension in self.supported_video_formats:
            try:
                video = cv2.VideoCapture(file_path)
                if video.isOpened():
                    video.release()
                    return "Video"
                else:
                    return "Invalid video file"
            except:
                return "Invalid video file"
        else:
            return "Not a supported image or video format"

    def process_image(self, image_path, output_dir, frame_id, generate_crops_flag):
        """
        Process a single image and extract face crops.

        Args:
            image_path (str): Path to the input image.
            output_dir (str): Directory to save face crops.
            frame_id (str): Identifier for the frame.
        """
        try:
            frame = cv2.imread(image_path)

            detected_faces, face_found = self.detect_face(frame)

            if face_found:
                if self.log_level >= 2:
                    print(f"Face(s) detected in image {image_path}")
                if generate_crops_flag:
                    self.generate_crops(frame, output_dir, 0, detected_faces, frame_id)
                else:
                    frame_index = 0
                    # Generate output path for the face crop
                    output_face_path = os.path.join(
                        output_dir,
                        f"{frame_id}_{frame_index}.{self.FRAMES_FILE_FORMAT}",
                    )  # frame_index = 0 for all still images

                    # Check if the image already exists
                    if os.path.exists(output_face_path):
                        if self.log_level >= 2:
                            print(f"Skipping image {output_face_path}: already exists")
                        return

                    print("Frame saved at: ", output_face_path)
                    # Save the frame
                    cv2.imwrite(output_face_path, frame)
            else:
                if self.log_level >= 1:
                    print(f"No face detected in image {image_path}")
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")

    def process_video(
        self, video_path, output_dir, frame_id, frame_rate, generate_crops_flag
    ):
        """
        Process a video and extract face crops from frames.

        Args:
            video_path (str): Path to the input video.
            output_dir (str): Directory to save face crops.
            frame_id (str): Identifier for the frames.
            frame_rate (int): Rate at which to extract frames.
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps / frame_rate)
        frame_count = 0
        saved_frame_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_interval == 0:
                try:
                    detected_faces, face_found = self.detect_face(frame)
                    if face_found:
                        if self.log_level >= 2:
                            print(f"Face(s) detected in frame {frame_count}")
                        if generate_crops_flag:
                            self.generate_crops(
                                frame,
                                output_dir,
                                saved_frame_count,
                                detected_faces,
                                frame_id,
                            )
                        else:
                            # Generate output path for the face crop
                            output_face_path = os.path.join(
                                output_dir,
                                f"{frame_id}_{saved_frame_count}.{self.FRAMES_FILE_FORMAT}",
                            )

                            # Check if the frame already exists
                            if os.path.exists(output_face_path):
                                if self.log_level >= 1:
                                    print(
                                        f"Skipping frame {output_face_path}: already exists"
                                    )
                            else:
                                # Save the frame
                                cv2.imwrite(output_face_path, frame)
                        saved_frame_count += 1
                    else:
                        if self.log_level >= 2:
                            print(f"No face detected in frame {frame_count}")
                except Exception as e:
                    print(f"Error processing frame {frame_count}: {e}")
            frame_count += 1
        cap.release()
        if self.log_level >= 1:
            print(
                f"Frames with detected faces saved: {saved_frame_count}/{frame_count} from {video_path}"
            )

    def generate_6_digit_hash(self, input_string):
        # Create a hash object
        hash_object = hashlib.sha256(input_string.encode())
        # Get the hexadecimal digest of the hash
        hex_dig = hash_object.hexdigest()
        # Convert the first 6 characters of the hash to an integer
        hash_int = int(hex_dig[:6], 16)
        # Ensure the hash is 6 digits long
        hash_6_digit = str(hash_int).zfill(6)
        return hash_6_digit

    def hash_file_content(self, file_path):
        with open(file_path, "rb") as f:
            file_content = f.read()
        return self.generate_6_digit_hash(file_content.decode("latin1"))

    def hash_file_name(self, file_path):
        file_name = os.path.basename(file_path)
        return self.generate_6_digit_hash(file_name)

    def generate_combined_hash(self, file_path):
        file_content_hash = self.hash_file_content(file_path)
        file_name_hash = self.hash_file_name(file_path)
        return f"{file_content_hash}_{file_name_hash}"

    def process_media_file(
        self, media_path, output_dir, generate_crops_flag, frame_rate=2
    ):
        """
        Process a media file (image or video) and extract face crops.

        Args:
            media_path (str): Path to the input media file.
            output_dir (str): Directory to save face crops.
            frame_id (str): Identifier for the frames.
            frame_rate (int): Rate at which to extract frames (for videos).
        """
        media_type = self.check_media_type(media_path)

        if media_type == "Image":
            self.process_image(
                media_path,
                output_dir,
                frame_id=self.generate_combined_hash(media_path),
                generate_crops_flag=generate_crops_flag,
            )
        elif media_type == "Video":
            self.process_video(
                media_path,
                output_dir,
                frame_id=self.generate_combined_hash(media_path),
                frame_rate=frame_rate,
                generate_crops_flag=generate_crops_flag,
            )
        else:
            print(f"Unsupported media type: {media_type}")


class DeepfakeDetectionPipeline:
    def __init__(
        self,
        frame_model_path,
        crop_model_path,
        frames_dir,
        crops_dir,
        threshold=0.4,
        log_level=0,
        FRAMES_FILE_FORMAT="jpg",
    ):
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
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
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

    def get_crops_for_frame(self, file_id, frame_index, crops_dir):
        """
        Get all crops belonging to a specific frame using the naming scheme.

        Args:
            file_id (str): Combined hash identifier (content_hash + name_hash)
            frame_index (int): Frame index (0 for images)
            crops_dir (str): Directory containing all crops

        Returns:
            list: Paths to relevant crop files
        """
        crop_prefix = f"{file_id}_{frame_index}_"
        relevant_crops = []

        for filename in os.listdir(crops_dir):
            if filename.startswith(crop_prefix):
                crop_path = os.path.join(crops_dir, filename)
                relevant_crops.append(crop_path)

        return natsorted(relevant_crops)  # Sort to ensure consistent ordering

    def load_image_preprocessed(self, image_path, show_image=False):
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
                transforms.Resize(
                    (224, 224)
                ),  # Resize the image to the input size of the model
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

    def process_frame(self, image_path, type="frame"):
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

    def analyze_frame_with_crops(self, image_path, frame_id):
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
        frame_pred, frame_conf, gradcam_path = self.process_frame(
            image_path, type="frame"
        )
        results["frame_analysis"] = {"prediction": frame_pred, "confidence": frame_conf}
        results["gradcam_path"] = self.convert_to_public_url(gradcam_path)

        # Get crops for this frame
        frame_index = 0 if "_" not in frame_id else int(frame_id.split("_")[-1])
        file_id = frame_id.rsplit("_", 1)[0]
        crop_paths = self.get_crops_for_frame(file_id, frame_index, self.crops_dir)

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
        results["ela_path"] = self.convert_to_public_url(
            self.perform_ela_analysis(image_path)
        )

        return results

    def convert_to_public_url(self, file_path):
        """
        Convert a file path to a public URL.

        Args:
            file_path (str): The file path to convert.

        Returns:
            str: The public URL.
        """
        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
        return f"{settings.HOST_URL}{settings.MEDIA_URL}{relative_path.replace(os.sep, '/')}"

    def perform_ela_analysis(self, image_path):
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
        temp_compressed = os.path.join(
            os.path.dirname(image_path), "temp_compressed.jpg"
        )

        # Save compressed version
        quality = 95
        scale_multiplier = 50
        original_image.save(temp_compressed, "JPEG", quality=quality)
        compressed_image = Image.open(temp_compressed)

        # Calculate difference
        ela_image = ImageChops.difference(original_image, compressed_image)

        # Apply noise boost and scaling
        ela_scaled = ela_image.point(
            lambda x: np.sign(x) * (np.abs(x) ** 1.5 * scale_multiplier)
        )

        # Save ELA image
        ela_scaled.save(ela_image_path)

        # Clean up temporary file
        if os.path.exists(temp_compressed):
            os.remove(temp_compressed)

        return ela_image_path

    def process_media(self, media_path, frame_rate=2):
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
        file_id = self.media_processor.generate_combined_hash(media_path)

        # Process media file for frames using MediaProcessor
        self.media_processor.process_media_file(
            media_path,
            self.frames_dir,
            generate_crops_flag=False,
            frame_rate=frame_rate,
        )

        # Process media file for crops using MediaProcessor
        self.media_processor.process_media_file(
            media_path, self.crops_dir, generate_crops_flag=True, frame_rate=frame_rate
        )

        results = {
            "media_path": self.convert_to_public_url(media_path),
            "media_type": media_type,
            "file_id": file_id,
            "frame_results": [],
        }

        if media_type == "Image":
            media_path = os.path.join(
                self.frames_dir, f"{file_id}_0.{self.FRAMES_FILE_FORMAT}"
            )
            frame_results = self.analyze_frame_with_crops(media_path, f"{file_id}_0")
            results["media_path"] = self.convert_to_public_url(media_path)
            results["frame_results"].append(frame_results)

        elif media_type == "Video":
            frames = [
                os.path.join(self.frames_dir, f)
                for f in os.listdir(self.frames_dir)
                if (f.startswith(file_id) and ("ela" not in f and "gradcam" not in f))
            ]
            frames = natsorted(frames)
            for frame_index, frame_path in enumerate(frames):
                frame_results = self.analyze_frame_with_crops(
                    frame_path, f"{file_id}_{frame_index}"
                )
                results["frame_results"].append(frame_results)

        # Calculate overall statistics
        results["statistics"] = self._calculate_statistics(results["frame_results"])

        return results

    def _calculate_statistics(self, frame_results):
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
            sum(1 for crop in f["crop_analyses"] if crop["prediction"] == "fake")
            for f in frame_results
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
            "fake_crops_percentage": (
                (fake_crops / total_crops * 100) if total_crops > 0 else 0
            ),
        }

    # def _save_results(self, results, output_dir):
    #     """Save analysis results to output directory."""
    #     os.makedirs(output_dir, exist_ok=True)
    #     output_path = os.path.join(output_dir, f"{results['file_id']}_analysis.json")

    #     with open(output_path, "w") as f:
    #         json.dump(results, f, sort_keys=True, indent=4)
