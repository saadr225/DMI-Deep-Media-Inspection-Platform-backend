# Importing necessary libraries

from PIL import Image
import os, shutil
import matplotlib.pyplot as plt
import numpy as np
import cv2
from ultralytics import YOLO
import hashlib
from natsort import natsorted
from pytorch_grad_cam.utils.image import show_cam_on_image
from django.conf import settings
from typing import Optional, Dict, Tuple, Union


class MediaProcessor:
    """
    A class for detecting and extracting faces from images and videos using YOLOv8.
    """

    def __init__(
        self,
        model_path: str = f"{settings.ML_MODELS_DIR}/yolov8n.pt",
        threshold: float = 0.5,
        log_level: int = 0,
        FRAMES_FILE_FORMAT: str = "jpg",
    ) -> None:
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

    def detect_face(
        self, frame: np.ndarray
    ) -> Tuple[Optional[Dict[int, Dict[str, Union[Tuple[int, int], float]]]], bool]:
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
            for index, (box, score, object_class) in enumerate(zip(boxes, scores, classes)):
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

    def generate_crops_deprecated(
        self,
        frame: np.ndarray,
        output_dir: str,
        frame_index: int,
        detected_faces: Dict[int, Dict[str, Union[Tuple[int, int], float]]],
        frame_id: str,
        show_crops: bool = False,
    ) -> None:
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
            face_crop = frame[top_left[1] : bottom_right[1], top_left[0] : bottom_right[0]]

            if show_crops:
                # Resize and display the face crop (for debugging)
                face_crop_resized = cv2.resize(face_crop, (224, 224), interpolation=cv2.INTER_CUBIC)
                cv2.imshow(f"Face {face_idx} from Frame {frame_index}", face_crop_resized)
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
            if self.log_level >= 2:
                print("Crop saved at: ", output_face_path)
            # Save the face crop
            cv2.imwrite(output_face_path, face_crop)

    def generate_crops(
        self,
        frame: np.ndarray,
        output_dir: str,
        frame_index: int,
        detected_faces: Dict[int, Dict[str, Union[Tuple[int, int], float]]],
        frame_id: str,
        show_crops: bool = False,
    ) -> None:
        """
        Generate and save square face crops from a frame at 256x256 resolution.
        Args:
            frame (numpy.ndarray): Input image frame.
            output_dir (str): Directory to save face crops.
            frame_index (int): Index of the current frame.
            detected_faces (dict): Dictionary of detected faces.
            frame_id (str): Identifier for the frame.
            show_crops (bool): Whether to display the crops (for debugging).
        """
        frame_height, frame_width = frame.shape[:2]

        for face_idx, face_data in detected_faces.items():
            top_left = face_data["top_left"]
            bottom_right = face_data["bottom_right"]

            # Calculate width and height of the detected face
            width = bottom_right[0] - top_left[0]
            height = bottom_right[1] - top_left[1]

            # Find the center of the bounding box
            center_x = (top_left[0] + bottom_right[0]) // 2
            center_y = (top_left[1] + bottom_right[1]) // 2

            # Use the larger dimension to create a square box
            box_size = max(width, height)

            # Calculate new coordinates for square crop
            new_x1 = max(0, center_x - box_size // 2)
            new_y1 = max(0, center_y - box_size // 2)
            new_x2 = min(frame_width, center_x + box_size // 2)
            new_y2 = min(frame_height, center_y + box_size // 2)

            # Crop the face from the frame (square crop)
            face_crop = frame[new_y1:new_y2, new_x1:new_x2]

            # Resize to 256x256
            face_crop_resized = cv2.resize(face_crop, (256, 256), interpolation=cv2.INTER_CUBIC)

            if show_crops:
                # Display the face crop (for debugging)
                cv2.imshow(f"Face {face_idx} from Frame {frame_index}", face_crop_resized)
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
            if self.log_level >= 2:
                print("Crop saved at: ", output_face_path)

            # Save the face crop (256x256 square)
            cv2.imwrite(output_face_path, face_crop_resized)

    def check_media_type(self, file_path: str) -> str:
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

    def process_image(
        self, image_path: str, output_dir: str, frame_id: str, generate_crops_flag: bool
    ) -> bool:
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
                # ADD RETURN ERROR LOGIC HERE FOR NO FACE DETECTED

                if self.log_level >= 1:
                    print(f"No face detected in image {image_path}")
            return face_found

        except Exception as e:
            print(f"Error processing image {image_path}: {e}")

    def process_video(
        self,
        video_path: str,
        output_dir: str,
        frame_id: str,
        frame_rate: int,
        generate_crops_flag: bool,
    ) -> bool:
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
        frame_with_face_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_interval == 0:
                try:
                    detected_faces, face_found = self.detect_face(frame)
                    if face_found:
                        frame_with_face_count += 1
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
                                    print(f"Skipping frame {output_face_path}: already exists")
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
        return frame_with_face_count > 0  # return True if face is detected in the video

    def generate_6_digit_hash(self, input_string: str) -> str:
        # Create a hash object
        hash_object = hashlib.sha256(input_string.encode())
        # Get the hexadecimal digest of the hash
        hex_dig = hash_object.hexdigest()
        # Convert the first 6 characters of the hash to an integer
        hash_int = int(hex_dig[:6], 16)
        # Ensure the hash is 6 digits long
        hash_6_digit = str(hash_int).zfill(6)
        return hash_6_digit

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

    def process_media_file(
        self, media_path: str, output_dir: str, generate_crops_flag: bool, frame_rate: int = 2
    ) -> bool:
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
            face_found = self.process_image(
                media_path,
                output_dir,
                frame_id=self.generate_combined_hash(media_path),
                generate_crops_flag=generate_crops_flag,
            )
            return face_found
        elif media_type == "Video":
            face_found = self.process_video(
                media_path,
                output_dir,
                frame_id=self.generate_combined_hash(media_path),
                frame_rate=frame_rate,
                generate_crops_flag=generate_crops_flag,
            )
            return face_found
        else:
            print(f"Unsupported media type: {media_type}")

    def extract_single_frame_with_face(self, video_path: str, output_dir: str) -> Optional[str]:
        """
        Extract a single frame containing a face from a video.

        Args:
            video_path (str): Path to the input video.
            output_dir (str): Directory to save the extracted frame.

        Returns:
            Optional[str]: Path to the saved frame, or None if no face was found.
        """
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Get frame ID using the same hash approach
        frame_id = self.generate_combined_hash(video_path)

        # Define output path with frame index 0
        output_frame_path = os.path.join(output_dir, f"{frame_id}_0.{self.FRAMES_FILE_FORMAT}")

        # Check if the frame already exists
        if os.path.exists(output_frame_path):
            if self.log_level >= 1:
                print(f"Frame already exists at {output_frame_path}")
            return output_frame_path

        # Open the video
        cap = cv2.VideoCapture(video_path)
        frame_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Detect faces in current frame
            detected_faces, face_found = self.detect_face(frame)

            if face_found:
                # Save the frame with the specified naming scheme
                cv2.imwrite(output_frame_path, frame)

                if self.log_level >= 1:
                    print(f"Frame with face extracted and saved at: {output_frame_path}")

                cap.release()
                return output_frame_path

            frame_count += 1

            # Check frame limit (optional) to avoid processing very long videos
            if frame_count > 300:  # Check first ~10 seconds at 30fps
                break

        cap.release()

        if self.log_level >= 1:
            print(f"No frame with face found in video: {video_path}")

        return None
