from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view

from DMI_backend.app.contollers.DeepfakeDetectionController import (
    DeepfakeDetectionPipeline,
)

pipeline = DeepfakeDetectionPipeline(
    frame_model_path="../ML_Models/acc99.76_test-2.1_FRAMES_deepfake_detector_resnext50.pth",
    crop_model_path="../ML_Models/acc99.53_test-2.1_CROPS_deepfake_detector_resnext50.pth",
    frames_dir="/kaggle/working/temp_dataset",
    crops_dir="/kaggle/working/temp_face_crops",
    threshold=0.4,
    log_level=0,
    FRAMES_FILE_FORMAT="png",
)

# Process media file
results = pipeline.process_media(
    media_path="/kaggle/input/test-images-for-face-detection-pipeline-samples/test_images_for_face_detection_pipeline/img_1247.jpg",
    frame_rate=2,
)

# Create your views here.
api_view(["GET"])


def home(request):
    return JsonResponse({"message": "Hello, World!"})


api_view(["GET", "POST"])


def process_media(request):

    if request.method == "GET":
        return JsonResponse({"message": "GET request received"})
    elif request.method == "POST":
        return JsonResponse({"message": "POST request received"})
    else:
        return JsonResponse({"message": "Invalid request method"})
