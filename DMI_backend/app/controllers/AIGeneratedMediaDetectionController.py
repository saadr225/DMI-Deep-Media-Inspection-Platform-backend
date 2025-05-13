from typing import Dict, Tuple, Union, Optional
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import os
import cv2
import hashlib
from django.conf import settings
from transformers import AutoModelForImageClassification, AutoFeatureExtractor


class AIGeneratedMediaDetectionPipeline:
    """
    AI detection for single images with GradCAM heatmap using Swin V2 model.
    """

    def __init__(
        self,
        model_name: str = "haywoodsloan/ai-image-detector-deploy",
        synthetic_media_dir: str = None,
        threshold: float = 0.7,
        log_level: int = 0,
        FRAMES_FILE_FORMAT: str = "jpg",
    ) -> None:
        self.device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Loading model {model_name}... This might take a moment.")

        # Load the model and feature extractor
        self.model = AutoModelForImageClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)

        self.threshold: float = threshold
        self.synthetic_media_dir: str = synthetic_media_dir
        self.log_level: int = log_level
        self.FRAMES_FILE_FORMAT: str = FRAMES_FILE_FORMAT
        self.label_map = {0: "real", 1: "fake"}  # Will be updated based on actual model labels

        # Update label map from model config
        if hasattr(self.model.config, "id2label"):
            self.label_map = self.model.config.id2label

        print("Model loaded successfully!")

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
        """Preprocess image using the feature extractor"""
        image = Image.open(image_path).convert("RGB")
        inputs = self.feature_extractor(images=image, return_tensors="pt")
        return inputs.to(self.device)

    def get_target_layer(self):
        """Find appropriate layer for GradCAM visualization"""
        # Try to find a suitable target layer
        target_layer = None

        # Strategy 1: Check for layernorm in swinv2
        if hasattr(self.model, "swinv2"):
            if hasattr(self.model.swinv2, "layernorm"):
                return self.model.swinv2.layernorm
            elif hasattr(self.model.swinv2, "encoder") and hasattr(self.model.swinv2.encoder, "layers"):
                last_layer = self.model.swinv2.encoder.layers[-1]
                if hasattr(last_layer, "layernorm"):
                    return last_layer.layernorm
                elif hasattr(last_layer, "blocks") and len(last_layer.blocks) > 0:
                    last_block = last_layer.blocks[-1]
                    if hasattr(last_block, "layernorm"):
                        return last_block.layernorm
                    elif hasattr(last_block, "norm1"):
                        return last_block.norm1

        # Strategy 2: Check for backbone
        if hasattr(self.model, "backbone"):
            if hasattr(self.model.backbone, "norm"):
                return self.model.backbone.norm
            elif hasattr(self.model.backbone, "layers") and len(self.model.backbone.layers) > 0:
                last_layer = self.model.backbone.layers[-1]
                if hasattr(last_layer, "blocks") and len(last_layer.blocks) > 0:
                    block = last_layer.blocks[-1]
                    if hasattr(block, "norm1"):
                        return block.norm1

        # Strategy 3: Generic search
        for name, module in self.model.named_modules():
            if ("norm" in name.lower() or "layernorm" in name.lower()) and (
                "stage" in name.lower() or "block" in name.lower() or "layer" in name.lower()
            ):
                return module

        # Strategy 4: Fallback options
        if hasattr(self.model, "classifier") and self.model.classifier is not None:
            return self.model.classifier
        elif hasattr(self.model, "layernorm") and self.model.layernorm is not None:
            return self.model.layernorm
        elif hasattr(self.model, "pooler") and self.model.pooler is not None:
            return self.model.pooler

        # Last resort
        modules = list(self.model.named_children())
        if len(modules) > 1:
            _, pre_last_module = modules[-2]
            return pre_last_module

        _, last_module = modules[-1]
        return last_module

    def generate_gradcam(self, image_path: str, target_class: Optional[int] = None) -> str:
        """Generate GradCAM heatmap for visualization"""
        # Load and preprocess the image
        image = Image.open(image_path).convert("RGB")
        inputs = self.feature_extractor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Store activations and gradients
        activation = {}
        gradients = {}

        # Define hooks
        def get_activation(name):
            def hook(module, input, output):
                activation[name] = output.detach()

            return hook

        def get_gradient(name):
            def hook(module, grad_input, grad_output):
                gradients[name] = grad_output[0].detach()

            return hook

        # Find target layer
        target_layer = self.get_target_layer()

        # Register hooks
        target_layer_name = "target_layer"
        handle_forward = target_layer.register_forward_hook(get_activation(target_layer_name))
        handle_backward = target_layer.register_full_backward_hook(get_gradient(target_layer_name))

        # Forward pass
        with torch.set_grad_enabled(True):
            outputs = self.model(**inputs)
            logits = outputs.logits

            # If no target class is specified, use the one with highest probability
            if target_class is None:
                probs = F.softmax(logits, dim=1)
                target_class = logits.argmax(dim=1).item()

            # Clear gradients
            if hasattr(self.model, "zero_grad"):
                self.model.zero_grad()
            else:
                for param in self.model.parameters():
                    if param.grad is not None:
                        param.grad.zero_()

            # One-hot encoding for the target class
            one_hot = torch.zeros_like(logits)
            one_hot[0, target_class] = 1

            # Backward pass
            logits.backward(gradient=one_hot, retain_graph=True)

        # Clean up hooks
        handle_forward.remove()
        handle_backward.remove()

        # Process feature maps and gradients for GradCAM
        feature_maps = activation[target_layer_name]
        grads = gradients[target_layer_name]

        # Handle different tensor shapes
        if len(feature_maps.shape) == 2:  # [batch, features]
            feature_maps = feature_maps.unsqueeze(-1).unsqueeze(-1)  # [batch, features, 1, 1]
            grads = grads.unsqueeze(-1).unsqueeze(-1)
        elif len(feature_maps.shape) == 3:  # [batch, seq_len, hidden_dim]
            batch_size, seq_len, hidden_dim = feature_maps.shape

            # Try to convert to square spatial dimensions if possible
            side = int(np.sqrt(seq_len))
            if side * side == seq_len:
                feature_maps = feature_maps.reshape(batch_size, side, side, hidden_dim).permute(
                    0, 3, 1, 2
                )
                grads = grads.reshape(batch_size, side, side, hidden_dim).permute(0, 3, 1, 2)
            else:
                # Use 1D spatial dimension
                feature_maps = feature_maps.permute(0, 2, 1).unsqueeze(2)
                grads = grads.permute(0, 2, 1).unsqueeze(2)

        # Calculate GradCAM
        weights = torch.mean(grads, dim=(2, 3), keepdim=True)
        cam = torch.sum(weights * feature_maps, dim=1)
        cam = F.relu(cam)

        # Process CAM to create heatmap
        cam = cam.squeeze().detach().cpu().numpy()

        # Handle edge case where cam might be a scalar
        if cam.ndim == 0:
            cam = np.array([[cam]])

        # Normalize
        cam_min, cam_max = np.min(cam), np.max(cam)
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = np.zeros_like(cam)

        # Resize to match original image
        cam = cv2.resize(cam.astype(np.float32), (image.width, image.height))

        # Create heatmap
        heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # Convert PIL image to numpy array for overlay
        image_np = np.array(image)

        # Ensure same dimensions
        if len(image_np.shape) == 2:  # If grayscale
            image_np = np.stack([image_np, image_np, image_np], axis=2)

        # Create overlay
        overlay = heatmap * 0.4 + image_np * 0.6
        overlay = np.uint8(overlay)

        # Save the overlay
        gradcam_path = image_path.replace(
            f".{self.FRAMES_FILE_FORMAT}", f"_gradcam.{self.FRAMES_FILE_FORMAT}"
        )
        cv2.imwrite(gradcam_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))

        return gradcam_path

    def process_frame(self, image_path: str) -> Tuple[str, float, str]:
        """Process a single frame for AI detection"""
        # Preprocess image
        inputs = self.load_image_preprocessed(image_path)

        # Get prediction
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probabilities = F.softmax(logits, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        predicted_class = predicted.item()
        predicted_label = self.label_map[predicted_class]
        confidence_score = confidence.item()

        # Generate GradCAM visualization
        gradcam_path = self.generate_gradcam(image_path, target_class=predicted_class)

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
