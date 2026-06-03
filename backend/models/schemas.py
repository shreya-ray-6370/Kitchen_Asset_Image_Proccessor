from typing import List

from pydantic import BaseModel

class QualityMetrics(BaseModel):
    sharpness: float
    lighting: float
    framing: float

class QualityResponse(BaseModel):
    grade: str
    metrics: QualityMetrics
    message: str
    fix_instructions: List[str]


class UploadResponse(BaseModel):
    scan_id: str
    image_url: str


class ErrorResponse(BaseModel):
    error: str
    fix_instructions: List[str]