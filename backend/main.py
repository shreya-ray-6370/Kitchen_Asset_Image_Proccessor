from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.routes.upload import router as upload_router
from backend.services.sqlite_service import UPLOAD_DIR, init_db

app = FastAPI(title="Kitchen Asset Image Processor")

# Include routes
app.include_router(upload_router, prefix="/api/v1/image")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="get_uploaded_image")

@app.get("/health")
def health():
    return {"status": "ok"}

# Initialize DB
@app.on_event("startup")
def startup_event():
    init_db()
