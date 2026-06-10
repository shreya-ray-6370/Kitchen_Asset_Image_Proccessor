from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests

from backend.models.schemas import DefectTag, ModelConditionResult


def _vlm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def _vlm_base_url() -> str:
    if _vlm_provider() == "groq":
        return os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    return "https://api.openai.com/v1"


def _vlm_api_key() -> str:
    if _vlm_provider() == "groq":
        return os.getenv("GROQ_API_KEY", "").strip()
    return os.getenv("OPENAI_API_KEY", "").strip()


def _default_vlm_model() -> str:
    return os.getenv("GPT4_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sanitize_severity(value: Any) -> str:
    text = str(value or "minor").strip().lower()
    if text not in {"minor", "moderate", "severe"}:
        return "minor"
    return text


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")

    return json.loads(stripped[start : end + 1])


def _normalize_result(payload: dict[str, Any]) -> ModelConditionResult:
    defect_tags_raw = payload.get("defect_tags", [])
    defect_tags: list[DefectTag] = []
    if isinstance(defect_tags_raw, list):
        for item in defect_tags_raw:
            if not isinstance(item, dict):
                continue
            defect_tags.append(
                DefectTag(
                    tag=str(item.get("tag", "unknown_defect")),
                    severity=_sanitize_severity(item.get("severity")),
                    confidence=max(0.0, min(1.0, _as_float(item.get("confidence"), 0.5))),
                )
            )

    return ModelConditionResult(
        model="gpt4-vision",
        condition_score=max(0, min(100, int(_as_float(payload.get("condition_score"), 70.0)))),
        defect_tags=defect_tags,
        severity=_sanitize_severity(payload.get("severity")),
        recommended_action=str(payload.get("recommended_action", "No recommendation provided.")),
        rationale=str(payload.get("rationale", "")).strip() or None,
        confidence=max(0.0, min(1.0, _as_float(payload.get("confidence"), 0.65))),
    )


def run_gpt4_side_by_side(image_bytes: bytes) -> ModelConditionResult | None:
    enabled = os.getenv("ENABLE_GPT4_SIDE_BY_SIDE", "false").strip().lower() in {"1", "true", "yes"}
    api_key = _vlm_api_key()
    if not enabled or not api_key:
        return None

    model = _default_vlm_model()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    instruction = (
        "Analyze the appliance condition in this image. "
        "Return ONLY strict JSON with keys: "
        "condition_score (0-100 integer), severity (minor|moderate|severe), "
        "recommended_action (string), confidence (0-1 float), rationale (short string), "
        "defect_tags (array of {tag, severity, confidence}). "
        "Use empty array if no defects are visible."
    )

    body = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/webp;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }

    # Groq does not support response_format for all vision models.
    if _vlm_provider() != "groq":
        body["response_format"] = {"type": "json_object"}

    chat_url = f"{_vlm_base_url()}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(chat_url, headers=headers, json=body, timeout=45)
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = _extract_json_object(content)
        return _normalize_result(parsed)
    except Exception:
        # Side-by-side output must never block the primary OpenCV flow.
        return None
