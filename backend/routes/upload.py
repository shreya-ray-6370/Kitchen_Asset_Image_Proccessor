from fastapi import APIRouter, File, HTTPException, Request, UploadFile
import uuid

from backend.services.image_processor import check_quality, process_image
from backend.services.sqlite_service import save_scan
from backend.models.schemas import ErrorResponse, QualityResponse, UploadResponse
from backend.utils.helpers import validate_upload

router = APIRouter()

# âœ… QUALITY CHECK
@router.post("/validate", response_model=QualityResponse)
async def quality_check(file: UploadFile = File(...)):
    contents = await file.read()

    is_valid, message = validate_upload(file.content_type or "", len(contents))
    if not is_valid:
        raise HTTPException(status_code=400, detail={"error": message, "fix_instructions": []})

    try:
        metrics = check_quality(contents)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "Invalid image", "fix_instructions": []})

    grade, message, fixes = evaluate_grade(metrics)

    return {
        "grade": grade,
        "metrics": metrics,
        "message": message,
        "fix_instructions": fixes
    }


# âœ… UPLOAD API
@router.post("/upload", response_model=UploadResponse)
async def upload_scan(request: Request, file: UploadFile = File(...)):
    contents = await file.read()

    is_valid, message = validate_upload(file.content_type or "", len(contents))
    if not is_valid:
        raise HTTPException(status_code=400, detail={"error": message, "fix_instructions": []})

    try:
        metrics = check_quality(contents)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "Invalid image", "fix_instructions": []})

    grade, message, fixes = evaluate_grade(metrics)

    if grade == "Marginal":
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(error="Image quality too poor", fix_instructions=fixes).model_dump()
        )

    processed = process_image(contents)

    scan_id = str(uuid.uuid4())
    save_scan(scan_id, processed)
    base_url = str(request.base_url).rstrip('/')
    image_url = f"{base_url}/uploads/{scan_id}.webp"

    return {
        "scan_id": scan_id,
        "image_url": image_url
    }


# âœ… GRADING LOGIC
def evaluate_grade(metrics):
    sharp = metrics["sharpness"]
    light = metrics["lighting"]
    frame = metrics["framing"]

    fixes = []

    if sharp < 100:
        fixes.append("Image is blurry. Hold camera steady.")
    if light > 60:
        fixes.append("Lighting uneven. Improve lighting.")
    if frame < 0.4:
        fixes.append("Object too small. Move closer.")

    if sharp >= 100 and light <= 60 and frame >= 0.4:
        return "Sharp", "Good quality image", []

    # Acceptable images can proceed but should show warnings in UI.
    if sharp >= 70 and light <= 75 and frame >= 0.35:
        return "Acceptable", "Minor issues", fixes

    return "Marginal", "Poor quality image", fixes


