# Kitchen Asset Image Processor (POC)

## Package Manager And Environment

This project uses standard Python `pip` with a virtual environment.

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Vision Metadata (Step 1)

Metadata extraction now prioritizes a vision classifier for appliance category prediction and falls back to OpenCV heuristics if model dependencies are unavailable.

Current step-1 scope:

1. Appliance category prediction at quality-check and upload time.
2. Brand/model-number extraction is intentionally deferred to step-2.

### Vision Metadata (Step 2)

Brand/model extraction now uses optional LLM vision enrichment with safe local fallback.

Environment flags:

1. `ENABLE_METADATA_LLM=true` to enable LLM metadata extraction.
2. `OPENAI_API_KEY=...` required when LLM metadata is enabled.
3. `METADATA_VISION_MODEL=gpt-4o-mini` optional override.

Behavior:

1. If LLM metadata is unavailable, appliance type falls back to local vision model and then OpenCV heuristic.
2. Brand/model fall back to `Unknown` / `Not detected`.

### Quality Classification Training (Step 3)

The image quality gate is now intended to be trained as a YOLO classification model using the dataset classes:

1. `sharp`
2. `acceptable`
3. `marginal`

Recommended workflow:

1. Audit the dataset counts:

```powershell
python scripts/audit_quality_dataset.py C:\projects\data_set_creation\dataset
```

2. Train the classifier after splitting the dataset into train/val/test:

```powershell
python scripts/train_quality_classifier.py --dataset-root C:\projects\data_set_creation\dataset --model yolo26n-cls.pt
```

Notes:

1. The training scripts use only the `sharp`, `acceptable`, and `marginal` folders.
2. The `originals` folder is ignored by the classifier pipeline.
3. A demo image that is not part of the dataset can still work correctly after training, as long as it is similar to the real-world distribution the model was trained on.
4. If the demo image is very different from the training data, the prediction can still be wrong, which is normal for any classifier.

### Quality Classification Evaluation (Step 4)

After training, validate the classifier on held-out data and a few fresh demo images:

```powershell
python scripts/evaluate_quality_classifier.py --data-root data/quality_split
```

Optional demo image check:

```powershell
python scripts/evaluate_quality_classifier.py --data-root data/quality_split --demo-image C:\path\to\new_image.jpg
```

What this gives you:

1. Validation and test-set top-1/top-5 accuracy.
2. Prediction output on new images outside the dataset.
3. A quick check that the trained classifier is learning the quality categories instead of just memorizing training samples.

### Runtime Quality Gate (Step 5)

Use the trained classifier in backend quality checks:

1. Set `ENABLE_YOLO_QUALITY=true`.
2. Optional: set `YOLO_QUALITY_MODEL_PATH` to a specific `best.pt` path.
3. If the configured path is missing, the backend auto-selects the most recent `runs/**/weights/best.pt`.

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
