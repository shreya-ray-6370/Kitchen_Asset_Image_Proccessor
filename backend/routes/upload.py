from fastapi import APIRouter, File, HTTPException, Request, UploadFile
import uuid

from backend.services.image_processor import process_image
from backend.services.ai_service import run_condition_scoring
from backend.services.metadata_service import extract_appliance_metadata
from backend.services.quality_service import assess_image_quality
from backend.services.sqlite_service import save_metadata, save_scan
from backend.models.schemas import ApplianceMetadata, ErrorResponse, QualityResponse, UploadResponse
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
        quality = assess_image_quality(contents)
        metadata = extract_appliance_metadata(contents)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "Invalid image", "fix_instructions": []})

    return {
        "grade": quality["grade"],
        "metrics": quality["metrics"],
        "message": quality["message"],
        "fix_instructions": quality["fix_instructions"],
        "metadata": metadata.model_dump(),
    }


# âœ… UPLOAD API
@router.post("/upload", response_model=UploadResponse)
async def upload_scan(request: Request, file: UploadFile = File(...)):
    contents = await file.read()

    is_valid, message = validate_upload(file.content_type or "", len(contents))
    if not is_valid:
        raise HTTPException(status_code=400, detail={"error": message, "fix_instructions": []})

    try:
        quality = assess_image_quality(contents)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "Invalid image", "fix_instructions": []})

    if quality["grade"] == "Marginal":
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(
                error="Image quality too poor",
                fix_instructions=quality["fix_instructions"],
            ).model_dump()
        )

    processed = process_image(contents)

    scan_id = str(uuid.uuid4())
    save_scan(scan_id, processed)
    metadata = extract_appliance_metadata(processed)
    save_metadata(scan_id, metadata.model_dump())
    # Run condition scoring immediately after successful upload so GET condition can fetch by scan_id.
    run_condition_scoring(scan_id=scan_id, image_bytes=processed)
    base_url = str(request.base_url).rstrip('/')
    image_url = f"{base_url}/uploads/{scan_id}.webp"

    return {
        "scan_id": scan_id,
        "image_url": image_url,
        "metadata": ApplianceMetadata(**metadata.model_dump()).model_dump(),
    }


