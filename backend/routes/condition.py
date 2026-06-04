from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from backend.models.schemas import ConditionResponse, ScanHistoryItem, ScanHistoryResponse
from backend.services.ai_service import get_condition
from backend.services.sqlite_service import list_scan_records

router = APIRouter(prefix="/api/v1/scans", tags=["condition"])


@router.get("", response_model=ScanHistoryResponse)
def fetch_scan_history(request: Request) -> ScanHistoryResponse:
	base_url = str(request.base_url).rstrip("/")
	items: list[ScanHistoryItem] = []

	for row in list_scan_records():
		filename = Path(row["image_path"]).name
		condition = (
			ConditionResponse(**row["condition_payload"]) if row.get("condition_payload") else None
		)
		items.append(
			ScanHistoryItem(
				scan_id=row["scan_id"],
				image_url=f"{base_url}/uploads/{filename}",
				created_at=row.get("created_at"),
				condition=condition,
			)
		)

	return ScanHistoryResponse(items=items)


@router.get("/{scan_id}/condition", response_model=ConditionResponse)
def fetch_condition(scan_id: str) -> ConditionResponse:
	condition = get_condition(scan_id)
	if condition is None:
		raise HTTPException(status_code=404, detail="scan_id not found")
	return condition
