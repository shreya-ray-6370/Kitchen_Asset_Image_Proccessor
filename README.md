# Kitchen Asset Image Processor (POC)

## Package Manager And Environment

This project uses standard Python `pip` with a virtual environment.

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Target API Contracts

- `POST /api/v1/quality-check`
- `POST /api/v1/scans`
- `GET /api/v1/scans/{scan_id}/condition`

## Team Branching Plan

- Person 1 (Frontend): `feature/frontend-streamlit-ui`
- Person 2 (Backend Upload): `feature/backend-upload-pipeline`
- Person 3 (AI + Condition): `feature/ai-condition-api`

All branches should be created from the latest `main`.

## Ownership Split

### Person 1

- `frontend/app.py`
- `frontend/components/uploader.py`
- `frontend/components/results.py`
- `frontend/utils/api_client.py`

### Person 2

- `backend/routes/upload.py`
- `backend/services/image_processor.py`
- `backend/services/sqlite_service.py`

### Person 3

- `backend/routes/condition.py`
- `backend/services/ai_service.py`
- `backend/db/in_memory_store.py`

## Note On Storage

This scaffold is currently SQLite-oriented (`backend/services/sqlite_service.py`) instead of S3 for faster POC setup.
