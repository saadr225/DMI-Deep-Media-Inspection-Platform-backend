from typing import Dict, List, Tuple, Union, Optional
import torch
import torch.nn as nn
import torch.nn.functional as tnf
from transformers import BertTokenizer, BertModel
import os
import hashlib
import numpy as np
from django.conf import settings


class LLMDetector(nn.Module):
    """BERT-based model for detecting if text is human or AI-generated"""

    def __init__(self, num_classes, model_name="bert-base-uncased"):
        super().__init__()
        self.bert = BertModel.from_pretrained(model_name)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_classes)
        self.dropout = nn.Dropout(0.1)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids, attention_mask=attention_mask)
        pooled = outputs.pooler_output
        pooled = self.dropout(pooled)
        return self.classifier(pooled)


class TextDetectionPipeline:
    """
    Pipeline for detecting if text is human-written or AI-generated.
    Can differentiate between human, GPT-3, and Claude-generated text.
    """

    def __init__(
        self,
        model_path: str,
        threshold: float = 0.5,
        log_level: int = 0,
    ) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load the model
        num_classes = 3  # Human, GPT-3, Claude
        self.model = LLMDetector(num_classes=num_classes)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()

        self.threshold = threshold
        self.log_level = log_level
        self.label_map = {0: "Human", 1: "GPT-3", 2: "Claude"}

        # Initialize the tokenizer
        self.tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
        self.max_length = 512

    def generate_6_digit_hash(self, input_string: str) -> str:
        """Generate a 6-digit hash from an input string"""
        hash_object = hashlib.sha256(input_string.encode())
        hex_dig = hash_object.hexdigest()
        hash_int = int(hex_dig[:6], 16)
        return str(hash_int).zfill(6)

    def preprocess_text(self, text: str) -> Dict[str, torch.Tensor]:
        """Tokenize and prepare text for the model"""
        encoding = self.tokenizer(
            text, truncation=True, padding="max_length", max_length=self.max_length, return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].to(self.device),
            "attention_mask": encoding["attention_mask"].to(self.device),
        }

    def detect_text_source(self, text: str) -> Dict[str, Union[str, Dict[str, float]]]:
        """
        Detect if text is human-written or AI-generated

        Args:
            text (str): The text to analyze

        Returns:
            dict: Contains the prediction and confidence scores
        """
        if not text or text.strip() == "":
            return {
                "prediction": "Unknown",
                "confidence": {source: 0.0 for source in self.label_map.values()},
                "error": "Empty text provided",
            }

        # Preprocess the text
        encoding = self.preprocess_text(text)

        # Make prediction
        with torch.no_grad():
            outputs = self.model(encoding["input_ids"], encoding["attention_mask"])
            probabilities = tnf.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        predicted_class = predicted.item()
        predicted_label = self.label_map[predicted_class]
        confidence_score = confidence.item()

        # Get all class probabilities
        probabilities_dict = {
            self.label_map[i]: float(probabilities[0][i]) for i in range(len(self.label_map))
        }

        return {
            "prediction": predicted_label,
            "confidence": probabilities_dict,
        }

    def detect_text_source_with_highlights(
        self,
        text: str,
        window_size: int = 100,
        stride: int = 50,
        probability_threshold: Optional[float] = 0.5,
        score_multiplier: Optional[float] = 100,
    ) -> Dict[str, Union[str, Dict[str, float], List[float]]]:
        """
        Analyze text for AI-generated content using sliding windows.
        Words with averaged AI probability above threshold are highlighted.

        Args:
            text (str): Text to analyze
            window_size (int): Size of sliding window
            stride (int): Step size for window sliding

        Returns:
            dict: Contains prediction, confidence, and highlighted text
        """
        # Overall full-text prediction
        full_prediction = self.detect_text_source(text)

        if "error" in full_prediction:
            return full_prediction

        # Split text into words and create overlapping chunks
        words = text.split()
        chunks = []
        chunk_indices = []
        current_chunk = []
        current_length = 0
        start_idx = 0

        for i, word in enumerate(words):
            current_chunk.append(word)
            current_length += len(word) + 1  # account for space
            if current_length >= window_size:
                chunks.append(" ".join(current_chunk))
                chunk_indices.append((start_idx, i))
                # Slide window by removing words until the remaining length is <= stride
                while current_length > stride and current_chunk:
                    removed_word = current_chunk.pop(0)
                    current_length -= len(removed_word) + 1
                    start_idx += 1

        # Include any remaining words as a chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            chunk_indices.append((start_idx, len(words) - 1))

        # Analyze each chunk for prediction confidence
        chunk_predictions = []
        for chunk in chunks:
            if chunk.strip():  # Only process non-empty chunks
                chunk_pred = self.detect_text_source(chunk)
                chunk_predictions.append(chunk_pred)

        # Compute AI probability for each word (sum all probabilities except 'Human')
        word_scores = np.zeros(len(words))
        word_counts = np.zeros(len(words))

        for (s_idx, e_idx), pred in zip(chunk_indices, chunk_predictions):
            ai_prob = sum(prob for label, prob in pred["confidence"].items() if label != "Human")
            word_scores[s_idx : e_idx + 1] += ai_prob * score_multiplier
            word_counts[s_idx : e_idx + 1] += 1

        # Average the scores where available
        word_scores = np.divide(word_scores, word_counts, where=word_counts != 0)

        if probability_threshold:
            # Update the threshold and log the change
            self.threshold = probability_threshold
            print(f"Threshold for AI generated text highlighting updated to {self.threshold}")

        # Create highlighted text by wrapping words with {} if their score > threshold
        highlighted_text = []
        for word, score in zip(words, word_scores):
            if score * score_multiplier > self.threshold:
                highlighted_text.append("{" + word + "}")
            else:
                highlighted_text.append(word)

        # Create an HTML version with similar highlighting
        html_text = ""
        current_pos = 0
        for i, (word, score) in enumerate(zip(words, word_scores)):
            word_pos = text.find(word, current_pos)
            if word_pos != -1:
                # Add text before the word
                html_text += text[current_pos:word_pos]

                # Add the word with highlighting if needed
                if score * score_multiplier > self.threshold:
                    html_text += f'<span class="ai-generated">{word}</span>'
                else:
                    html_text += word

                current_pos = word_pos + len(word)

        # Add any remaining text
        html_text += text[current_pos:]

        return {
            "prediction": full_prediction["prediction"],
            "confidence": full_prediction["confidence"],
            "highlighted_text": " ".join(highlighted_text),
            "html_text": html_text,
        }

    def process_text(
        self,
        text: str,
        highlight: bool = True,
        probability_threshold: Optional[float] = 1,
        score_multiplier: Optional[float] = 10,
    ) -> Dict[str, Union[str, Dict[str, float]]]:
        """
        Process a text through the pipeline, optionally with word highlighting.

        Args:
            text (str): Text to analyze
            highlight (bool): Whether to provide highlighted output

        Returns:
            dict: Analysis results for the text
        """
        if highlight:
            return self.detect_text_source_with_highlights(
                text, probability_threshold=probability_threshold, score_multiplier=score_multiplier
            )
        else:
            return self.detect_text_source(text)
