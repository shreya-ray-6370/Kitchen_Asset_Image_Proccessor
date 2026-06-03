from fastapi import APIRouter, HTTPException

from backend.models.schemas import ConditionResponse
from backend.services.ai_service import get_condition

router = APIRouter(prefix="/api/v1/scans", tags=["condition"])


@router.get("/{scan_id}/condition", response_model=ConditionResponse)
def fetch_condition(scan_id: str) -> ConditionResponse:
	condition = get_condition(scan_id)
	if condition is None:
		raise HTTPException(status_code=404, detail="scan_id not found")
	return condition
