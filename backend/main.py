from fastapi import FastAPI, File, UploadFile

from backend.routes.condition import router as condition_router
from backend.services.ai_service import run_condition_scoring

app = FastAPI(title="Kitchen Asset Image Processor")
app.include_router(condition_router)


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/internal/scans/{scan_id}/score")
async def internal_score(scan_id: str, file: UploadFile = File(...)) -> dict:
	# Internal endpoint for integration while Person 2 upload flow is in progress.
	image_bytes = await file.read()
	condition = run_condition_scoring(scan_id=scan_id, image_bytes=image_bytes)
	return {"scan_id": scan_id, "condition_score": condition.condition_score, "severity": condition.severity}
