from pydantic import BaseModel, Field


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
