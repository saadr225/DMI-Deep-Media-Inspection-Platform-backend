import os
import time
import numpy as np
from django.conf import settings
from django.core.mail import send_mail
from deepface import DeepFace
from scipy.spatial.distance import cosine
from api.models import UserData, FacialWatchRegistration, FacialWatchMatch


class FacialWatchAndRecognitionPipleine:
    def __init__(
        self,
        recognition_threshold: float = 0.3,  # Lower is more strict (closer match)
        log_level: int = 0,
        model_path: str = None,  # New parameter to specify model location
    ) -> None:
        """
        Initialize the FacialWatchSystem.

        Args:
            recognition_threshold: Similarity threshold for face matching.
            log_level: Level of logging (0: None, 1: Basic, 2: Verbose).
            model_path: Custom path to store DeepFace models. If None, uses default location.
        """
        self.recognition_threshold = recognition_threshold
        self.log_level = log_level

        # Set model path if provided
        if model_path:
            # Set DEEPFACE_HOME environment variable to control model download location
            os.environ["DEEPFACE_HOME"] = model_path
            if self.log_level >= 1:
                print(f"DeepFace models will be stored in: {model_path}")

        # DeepFace configuration for best accuracy
        self.model_name = "ArcFace"  # Most accurate model for recognition
        self.detector_backend = "retinaface"  # Best face detector

        # Pre-load models for better performance
        if self.log_level >= 1:
            print("Loading face detection models...")
        DeepFace.build_model(self.model_name)

        if self.log_level >= 1:
            print("FacialWatchSystem initialized")

    def register_user_face(self, user_id: int, image_path: str) -> bool:
        """
        Register a user's face for the watch system.

        Args:
            user_id: User ID to associate with the face
            image_path: Path to the image containing the user's face

        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            # Detect faces in the image
            face_objs = DeepFace.extract_faces(
                img_path=image_path,
                detector_backend=self.detector_backend,
                enforce_detection=True,
                align=True,
            )

            if len(face_objs) == 0:
                if self.log_level >= 1:
                    print(f"No face detected in image {image_path}")
                return False

            if len(face_objs) > 1:
                if self.log_level >= 1:
                    print(f"Multiple faces detected in image {image_path}, using the first one")

            # Extract face embedding (feature vector)
            embedding_objs = DeepFace.represent(
                img_path=image_path,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=True,
                align=True,
            )

            face_embedding = embedding_objs[0]["embedding"]

            # Store in database
            registration = FacialWatchRegistration(
                user_id=user_id,
                face_embedding=face_embedding,  # DeepFace already returns as a list
                registration_date=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            registration.save()

            if self.log_level >= 1:
                print(f"User {user_id} registered for facial watch")

            return True

        except Exception as e:
            if self.log_level >= 1:
                print(f"Error registering user face: {e}")
            return False

    def check_uploaded_image(self, image_path: str) -> list:
        """
        Check if any registered faces appear in the uploaded image.

        Args:
            image_path: Path to the uploaded image

        Returns:
            List of matched user IDs
        """
        try:
            # Get all registered face embeddings
            registered_faces = FacialWatchRegistration.objects.all()

            if not registered_faces.exists():
                return []

            # Detect and extract faces from the uploaded image
            try:
                extracted_faces = DeepFace.extract_faces(
                    img_path=image_path,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,  # Don't throw error if no face found
                    align=True,
                )

                if len(extracted_faces) == 0:
                    if self.log_level >= 1:
                        print(f"No faces detected in uploaded image {image_path}")
                    return []

                # Get embeddings for the extracted faces
                embeddings = DeepFace.represent(
                    img_path=image_path,
                    model_name=self.model_name,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                    align=True,
                )

            except:
                if self.log_level >= 1:
                    print(f"No faces detected in uploaded image {image_path}")
                return []

            matches = []

            # Check each detected face against registered faces
            for i, face_data in enumerate(embeddings):
                upload_embedding = np.array(face_data["embedding"])
                face_region = extracted_faces[i]["facial_area"]

                bbox = [
                    face_region["x"],
                    face_region["y"],
                    face_region["x"] + face_region["w"],
                    face_region["y"] + face_region["h"],
                ]

                for registered_face in registered_faces:
                    # Convert stored embedding to numpy array
                    registered_embedding = np.array(registered_face.face_embedding)

                    # Calculate similarity (1 - cosine distance)
                    similarity = 1 - cosine(upload_embedding, registered_embedding)

                    if similarity > (1 - self.recognition_threshold):
                        matches.append(
                            {
                                "user_id": registered_face.user_id,
                                "similarity": float(similarity),
                                "bbox": bbox,  # Face location in the image
                            }
                        )

            return matches

        except Exception as e:
            if self.log_level >= 1:
                print(f"Error checking uploaded image: {e}")
            return []

    def notify_matched_users(self, matches: list, image_upload_id: int) -> None:
        """
        Notify users that their face has been detected in an upload.

        Args:
            matches: List of user ID matches
            image_upload_id: ID of the uploaded image
        """
        for match in matches:
            try:
                user_id = match["user_id"]
                user_data = UserData.objects.get(id=user_id)

                # Log the match in the database
                facial_match = FacialWatchMatch(
                    user=user_data,
                    media_upload_id=image_upload_id,
                    match_confidence=match["similarity"],
                    face_location=match["bbox"],
                    notification_sent=True,
                )
                facial_match.save()

                # Send email notification
                send_mail(
                    subject="Your face was detected in an uploaded image",
                    message=f"Hello {user_data.user.username},\n\nYour face was detected in an image uploaded to our platform. You are receiving this notification because you registered for our Facial Watch service.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user_data.user.email],
                    fail_silently=False,
                )

                if self.log_level >= 1:
                    print(f"Notification sent to user {user_id}")

            except Exception as e:
                if self.log_level >= 1:
                    print(f"Error sending notification to user {user_id}: {e}")

    def remove_user_registration(self, user_id: int) -> bool:
        """
        Remove a user's face from the watch system.

        Args:
            user_id: User ID to remove

        Returns:
            bool: True if removal successful, False otherwise
        """
        try:
            registrations = FacialWatchRegistration.objects.filter(user_id=user_id)
            count = registrations.count()
            registrations.delete()

            if self.log_level >= 1:
                print(f"Removed {count} facial watch registrations for user {user_id}")

            return count > 0

        except Exception as e:
            if self.log_level >= 1:
                print(f"Error removing user registration: {e}")
            return False
