from typing import List

from pydantic import BaseModel, Field


class QualityMetrics(BaseModel):
    sharpness: float
    lighting: float
    framing: float


class QualityResponse(BaseModel):
    grade: str
    metrics: QualityMetrics
    message: str
    fix_instructions: List[str]
    metadata: "ApplianceMetadata | None" = None


class UploadResponse(BaseModel):
    scan_id: str
    image_url: str
    metadata: "ApplianceMetadata | None" = None


class ErrorResponse(BaseModel):
    error: str
    fix_instructions: List[str]


class DefectTag(BaseModel):
    tag: str
    severity: str = Field(description="minor | moderate | severe")
    confidence: float = Field(ge=0.0, le=1.0)


class ApplianceMetadata(BaseModel):
    model_config = {"protected_namespaces": ()}

    appliance_type: str
    brand: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(description="llm_vision | vision_model | opencv_heuristic | unknown")


class ModelConditionResult(BaseModel):
    model: str
    condition_score: int = Field(ge=0, le=100)
    defect_tags: list[DefectTag]
    severity: str = Field(description="minor | moderate | severe")
    recommended_action: str
    rationale: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ConditionResponse(BaseModel):
    scan_id: str
    condition_score: int = Field(ge=0, le=100)
    defect_tags: list[DefectTag]
    severity: str = Field(description="minor | moderate | severe")
    recommended_action: str
    metadata: ApplianceMetadata | None = None
    opencv_result: ModelConditionResult | None = None
    gpt4_result: ModelConditionResult | None = None
    comparison_note: str | None = None


class ScanHistoryItem(BaseModel):
    scan_id: str
    image_url: str
    created_at: str | None = None
    metadata: ApplianceMetadata | None = None
    condition: ConditionResponse | None = None


class ScanHistoryResponse(BaseModel):
    items: list[ScanHistoryItem]
