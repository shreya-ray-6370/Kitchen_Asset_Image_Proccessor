from __future__ import annotations

import base64
from functools import lru_cache
import json
import os
from typing import Any

import cv2
import numpy as np
from PIL import Image
import requests

from backend.models.schemas import ApplianceMetadata

_CANDIDATE_LABELS = {
    "refrigerator": "refrigerator",
    "microwave oven": "microwave",
    "coffee machine": "coffee_machine",
    "air fryer": "air_fryer",
    "electric kettle": "kettle",
    "toaster": "toaster",
    "blender": "mixer_grinder",
    "mixer grinder": "mixer_grinder",
    "dishwasher": "dishwasher",
    "washing machine": "washing_machine",
    "chimney hood": "kitchen_chimney",
    "induction cooktop": "induction_cooktop",
    "oven": "oven",
    "water purifier": "water_purifier",
    "food processor": "food_processor",
    "rice cooker": "rice_cooker",
    "sandwich maker": "sandwich_maker",
    "coffee maker": "coffee_machine",
    "espresso machine": "coffee_machine",
}


# ─── Provider routing ────────────────────────────────────────

def _llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def _llm_base_url() -> str:
    if _llm_provider() == "groq":
        return os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    return "https://api.openai.com/v1"


def _llm_api_key() -> str:
    if _llm_provider() == "groq":
        return os.getenv("GROQ_API_KEY", "").strip()
    return os.getenv("OPENAI_API_KEY", "").strip()


def _metadata_model() -> str:
    if _llm_provider() == "groq":
        return os.getenv("METADATA_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    return os.getenv("METADATA_VISION_MODEL", "gpt-4o-mini")


def _decode_image(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Invalid image bytes for metadata extraction")
    return image


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in metadata response")
    return json.loads(stripped[start: end + 1])


def _sanitize_category(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_")
    allowed = set(_CANDIDATE_LABELS.values()) | {"unknown"}
    if raw in allowed:
        return raw
    # partial match against display names
    for label, slug in _CANDIDATE_LABELS.items():
        if raw in label.replace(" ", "_") or label.replace(" ", "_") in raw:
            return slug
    return "unknown"


def _sanitize_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "n/a", "not mentioned", "not visible", "unknown"}:
        return fallback
    return text


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _encode_image_for_llm(image_bytes: bytes) -> str:
    """Resize to <=1024px wide and return base64 JPEG string."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return base64.b64encode(image_bytes).decode("ascii")
    h, w = img.shape[:2]
    if w > 1024:
        img = cv2.resize(img, (1024, int(h * 1024.0 / w)))
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _to_pil_image(image_bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


@lru_cache(maxsize=1)
def _vision_classifier() -> Any | None:
    """Optional local CLIP zero-shot classifier. Returns None if unavailable."""
    try:
        from transformers import pipeline  # type: ignore
    except Exception:
        return None
    try:
        return pipeline(
            task="zero-shot-image-classification",
            model="openai/clip-vit-base-patch32",
        )
    except Exception:
        return None


def _run_llm_metadata(image_bytes: bytes) -> tuple[str, str, float] | None:
    enabled = os.getenv("ENABLE_METADATA_LLM", "false").strip().lower() in {"1", "true", "yes"}
    api_key = _llm_api_key()
    if not enabled or not api_key:
        return None

    model = _metadata_model()
    image_b64 = _encode_image_for_llm(image_bytes)
    allowed_categories = ", ".join(sorted(set(_CANDIDATE_LABELS.values())))

    instruction = (
        "You are an expert at identifying kitchen electrical appliances from images.\n"
        "Carefully examine this image and return ONLY a strict JSON object with exactly these keys:\n"
        "  appliance_type  - one of: " + allowed_categories + ", unknown\n"
        "  brand           - brand/manufacturer name visible on the appliance (e.g. Samsung, LG, Philips). "
        "Return 'Unknown' if not clearly visible.\n"
        "  confidence      - float 0-1 representing overall extraction confidence.\n\n"
        "Return ONLY the JSON object. No explanation, no extra text."
    )

    body: dict[str, Any] = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }

    # Groq does not support response_format for all models; skip it.
    if _llm_provider() != "groq":
        body["response_format"] = {"type": "json_object"}

    chat_url = f"{_llm_base_url()}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(chat_url, headers=headers, json=body, timeout=40)
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = _extract_json_object(content)

        appliance_type = _sanitize_category(parsed.get("appliance_type"))
        brand = _sanitize_text(parsed.get("brand"), "Unknown")
        confidence = max(0.0, min(1.0, _as_float(parsed.get("confidence"), 0.6)))
        return appliance_type, brand, confidence
    except Exception:
        return None


def _largest_appliance_bbox(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if float(np.mean(mask > 0)) > 0.5:
        mask = cv2.bitwise_not(mask)

    clean = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < gray.size * 0.05:
        return None
    return cv2.boundingRect(largest)


def _classify_appliance(roi_gray: np.ndarray) -> tuple[str, float]:
    h, w = roi_gray.shape
    if h == 0 or w == 0:
        return "unknown", 0.2

    aspect = h / float(w)
    canny = cv2.Canny(roi_gray, 70, 160)
    edge_density = float(np.count_nonzero(canny)) / float(roi_gray.size)

    # Heuristics tuned for common front-view captures.
    # Raised aspect threshold to avoid misclassifying wide appliances as fridge.
    if aspect >= 1.5:
        return "refrigerator", 0.62

    upper = roi_gray[: max(1, h // 2), :]
    dark_upper_ratio = float(np.mean(upper < 85))
    right_strip = roi_gray[:, int(w * 0.78) :]
    right_edge_density = float(np.count_nonzero(cv2.Canny(right_strip, 70, 160))) / max(1.0, float(right_strip.size))

    if 0.55 <= aspect <= 1.2 and dark_upper_ratio > 0.18 and right_edge_density > 0.06:
        return "microwave", 0.68

    lower = roi_gray[int(h * 0.55) :, :]
    lower_edges = float(np.count_nonzero(cv2.Canny(lower, 70, 160))) / max(1.0, float(lower.size))
    if 0.65 <= aspect <= 1.25 and lower_edges > 0.12 and edge_density > 0.10:
        return "air_fryer", 0.62

    return "unknown", 0.25


def _classify_with_vision_model(roi_bgr: np.ndarray) -> tuple[str, float, str]:
    classifier = _vision_classifier()
    if classifier is None:
        return "unknown", 0.0, "opencv_heuristic"

    candidate_labels = list(_CANDIDATE_LABELS.keys())
    try:
        results = classifier(_to_pil_image(roi_bgr), candidate_labels=candidate_labels)
    except Exception:
        return "unknown", 0.0, "opencv_heuristic"

    if not results:
        return "unknown", 0.0, "opencv_heuristic"

    top = results[0]
    raw_label = str(top.get("label", "")).lower().strip()
    score = float(top.get("score", 0.0))
    mapped = _CANDIDATE_LABELS.get(raw_label, "unknown")

    # Avoid confident but wrong labels by falling back when confidence is weak.
    if mapped == "unknown" or score < 0.35:
        return "unknown", max(0.1, score), "vision_model"

    return mapped, min(0.98, score), "vision_model"


def extract_appliance_metadata(image_bytes: bytes) -> ApplianceMetadata:
    image = _decode_image(image_bytes)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    bbox = _largest_appliance_bbox(gray)
    if bbox is None:
        roi = image
        roi_gray = gray
    else:
        x, y, w, h = bbox
        roi = image[y : y + h, x : x + w]
        roi_gray = gray[y : y + h, x : x + w]

    appliance_type, type_conf, source = _classify_with_vision_model(roi)
    if appliance_type == "unknown":
        # Fallback path keeps the API responsive when vision model is unavailable.
        appliance_type, type_conf = _classify_appliance(roi_gray)
        source = "opencv_heuristic"

    brand = "Unknown"
    confidence = float(max(0.1, min(0.98, type_conf)))

    llm_meta = _run_llm_metadata(image_bytes)
    if llm_meta is not None:
        llm_type, llm_brand, llm_conf = llm_meta

        # Only override local category when LLM is confident enough.
        if llm_type != "unknown" and llm_conf >= 0.40:
            appliance_type = llm_type
        brand = llm_brand
        confidence = float(max(0.1, min(0.98, max(confidence, llm_conf))))
        source = f"llm_vision:{_llm_provider()}"

    return ApplianceMetadata(
        appliance_type=appliance_type,
        brand=brand,
        confidence=confidence,
        source=source,
    )
