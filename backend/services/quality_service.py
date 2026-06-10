from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

from backend.services.image_processor import check_quality


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _enable_yolo_quality() -> bool:
    return _env_flag("ENABLE_YOLO_QUALITY", "true")


def _allow_opencv_fallback() -> bool:
    return _env_flag("ALLOW_OPENCV_QUALITY_FALLBACK", "true")


def _quality_model_path() -> str:
    configured = os.getenv("YOLO_QUALITY_MODEL_PATH", "runs/classify/yolo_quality_classifier/weights/best.pt").strip()
    configured_path = Path(configured)
    if configured_path.exists():
        return str(configured_path)

    # Training output can differ by Ultralytics project settings; use latest best.pt.
    candidates = sorted(Path("runs").glob("**/weights/best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return str(candidates[0])

    return configured


def _quality_img_size() -> int:
    raw = os.getenv("YOLO_QUALITY_IMGSZ", "640").strip()
    try:
        parsed = int(raw)
    except ValueError:
        return 640
    return max(160, min(1280, parsed))


@lru_cache(maxsize=1)
def _quality_classifier() -> Any:
    from ultralytics import YOLO  # type: ignore

    return YOLO(_quality_model_path())


def _canonical_grade(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "sharp": "Sharp",
        "acceptable": "Acceptable",
        "marginal": "Marginal",
        "poor": "Marginal",
        "bad": "Marginal",
        "good": "Sharp",
    }
    return aliases.get(normalized, "Marginal")


def _message_for_grade(grade: str) -> tuple[str, list[str]]:
    if grade == "Sharp":
        return "Good quality image", []
    if grade == "Acceptable":
        return "Minor issues", ["Image has minor quality issues but is acceptable."]
    return "Poor quality image", ["Image quality too low. Retake with steadier framing and better lighting."]


def _evaluate_opencv_grade(metrics: dict[str, float]) -> tuple[str, str, list[str]]:
    sharp = metrics["sharpness"]
    light = metrics["lighting"]
    frame = metrics["framing"]

    fixes: list[str] = []

    if sharp < 40:
        fixes.append("Image is blurry. Hold camera steady.")
    if light > 95:
        fixes.append("Lighting uneven or strong glare detected. Reduce direct sunlight/reflections.")
    if frame < 0.26:
        fixes.append("Object too small. Move closer.")

    if sharp >= 45 and light <= 95 and frame >= 0.26:
        return "Sharp", "Good quality image", []
    if sharp >= 10 and light <= 230 and frame >= 0.15:
        return "Acceptable", "Minor issues", fixes
    return "Marginal", "Poor quality image", fixes


def _predict_yolo_grade(image_bytes: bytes) -> tuple[str, float, str]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result = _quality_classifier().predict(source=image, imgsz=_quality_img_size(), verbose=False)[0]
    probs = getattr(result, "probs", None)
    if probs is None:
        raise RuntimeError("YOLO classifier did not return class probabilities")

    top_idx = int(probs.top1)
    top_conf_raw = probs.top1conf
    top_conf = float(top_conf_raw.item() if hasattr(top_conf_raw, "item") else top_conf_raw)

    names = getattr(result, "names", {})
    if isinstance(names, dict):
        raw_label = str(names.get(top_idx, top_idx))
    else:
        raw_label = str(names[top_idx])

    return _canonical_grade(raw_label), top_conf, raw_label


def assess_image_quality(image_bytes: bytes) -> dict[str, Any]:
    try:
        if _enable_yolo_quality():
            grade, confidence, raw_label = _predict_yolo_grade(image_bytes)
            message, fixes = _message_for_grade(grade)
            # Keep existing response schema stable. These fields now carry model confidence context.
            metrics = {
                "sharpness": round(confidence * 100.0, 4),
                "lighting": 0.0,
                "framing": 0.0,
            }
            return {
                "grade": grade,
                "metrics": metrics,
                "message": message,
                "fix_instructions": fixes,
                "source": f"yolo_cls:{raw_label}",
                "confidence": confidence,
            }
    except Exception:
        if not _allow_opencv_fallback():
            raise

    metrics = check_quality(image_bytes)
    grade, message, fixes = _evaluate_opencv_grade(metrics)
    return {
        "grade": grade,
        "metrics": metrics,
        "message": message,
        "fix_instructions": fixes,
        "source": "opencv_heuristic",
        "confidence": None,
    }
