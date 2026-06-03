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


class UploadResponse(BaseModel):
	scan_id: str
	image_url: str


class ErrorResponse(BaseModel):
	error: str
	fix_instructions: List[str]


class DefectTag(BaseModel):
	tag: str
	severity: str = Field(description="minor | moderate | severe")
	confidence: float = Field(ge=0.0, le=1.0)


class ConditionResponse(BaseModel):
	scan_id: str
	condition_score: int = Field(ge=0, le=100)
	defect_tags: list[DefectTag]
	severity: str = Field(description="minor | moderate | severe")
	recommended_action: str
