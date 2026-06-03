from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles

from backend.routes.condition import router as condition_router
from backend.routes.upload import router as upload_router
from backend.services.ai_service import run_condition_scoring
from backend.services.sqlite_service import UPLOAD_DIR, init_db

app = FastAPI(title="Kitchen Asset Image Processor")

# Person 2 upload APIs
app.include_router(upload_router, prefix="/api/v1")

# Person 3 condition API
app.include_router(condition_router)

# Person 2 static file serving for uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="get_uploaded_image")


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.on_event("startup")
def startup_event() -> None:
	init_db()


@app.post("/internal/scans/{scan_id}/score")
async def internal_score(scan_id: str, file: UploadFile = File(...)) -> dict:
	# Internal endpoint for integration while Person 2 upload flow is in progress.
	image_bytes = await file.read()
	condition = run_condition_scoring(scan_id=scan_id, image_bytes=image_bytes)
	return {"scan_id": scan_id, "condition_score": condition.condition_score, "severity": condition.severity}
