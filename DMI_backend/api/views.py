from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from django.core.files.storage import FileSystemStorage
from app.contollers.DeepfakeDetectionController import (
    DeepfakeDetectionPipeline,
)
from django.conf import settings
import os


pipeline = DeepfakeDetectionPipeline(
    frame_model_path=f"{settings.ML_MODELS_DIR}/acc99.76_test-2.1_FRAMES_deepfake_detector_resnext50.pth",
    crop_model_path=f"{settings.ML_MODELS_DIR}/acc99.53_test-2.1_CROPS_deepfake_detector_resnext50.pth",
    frames_dir=f"{settings.MEDIA_ROOT}/temp/temp_frames/",
    crops_dir=f"{settings.MEDIA_ROOT}/temp/temp_crops/",
    threshold=0.4,
    log_level=0,
    FRAMES_FILE_FORMAT="png",
)


# Create your views here.
api_view(["GET"])


def home(request):
    return JsonResponse({"message": "Hello, World!"})


@csrf_exempt
@api_view(["GET", "POST"])
def process_deepfake_media(request):
    if request.method == "POST":
        media_file = request.FILES.get("file")
        if not media_file:
            return JsonResponse({"error": "No file uploaded"}, status=400)

        # Save the file to the media directory
        fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/submissions/")
        filename = fs.save(media_file.name, media_file)
        file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", filename)

        # Process the media file
        results = pipeline.process_media(
            media_path=file_path,
            frame_rate=2,
        )

        return JsonResponse(results)

    return JsonResponse({"message": "Send a POST request with a file."})
