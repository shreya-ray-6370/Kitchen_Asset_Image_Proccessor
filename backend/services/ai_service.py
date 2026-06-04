from __future__ import annotations

import cv2
import numpy as np

from backend.db.in_memory_store import condition_store
from backend.models.schemas import ConditionResponse, DefectTag
from backend.services.sqlite_service import get_condition_payload, save_condition


def _severity_from_ratio(ratio: float, medium_cutoff: float, high_cutoff: float) -> str:
	if ratio >= high_cutoff:
		return "severe"
	if ratio >= medium_cutoff:
		return "moderate"
	return "minor"


def _decode_image(image_bytes: bytes) -> np.ndarray:
	arr = np.frombuffer(image_bytes, dtype=np.uint8)
	image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
	if image is None:
		raise ValueError("Invalid image bytes for condition scoring")
	return image


def _score_image(scan_id: str, image_bgr: np.ndarray) -> ConditionResponse:
	hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
	gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
	total = float(gray.size)

	rust_mask = cv2.inRange(hsv, (5, 80, 40), (25, 255, 230))
	rust_ratio = float(np.count_nonzero(rust_mask)) / total

	edges = cv2.Canny(gray, 80, 170)
	crack_ratio = float(np.count_nonzero(edges)) / total

	grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
	grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
	dents_ratio = float(np.count_nonzero(cv2.magnitude(grad_x, grad_y) > 90)) / total

	stain_mask = cv2.inRange(hsv, (0, 0, 20), (180, 45, 145))
	stain_ratio = float(np.count_nonzero(stain_mask)) / total

	wear_ratio = float(np.std(gray)) / 255.0 + float(np.mean(gray < 60))

	defects: list[DefectTag] = []

	if rust_ratio >= 0.015:
		sev = _severity_from_ratio(rust_ratio, 0.03, 0.06)
		defects.append(DefectTag(tag="rust_corrosion", severity=sev, confidence=min(1.0, rust_ratio * 14)))

	if crack_ratio >= 0.035:
		sev = _severity_from_ratio(crack_ratio, 0.06, 0.11)
		defects.append(DefectTag(tag="cracks_fractures", severity=sev, confidence=min(1.0, crack_ratio * 7)))

	if dents_ratio >= 0.045:
		sev = _severity_from_ratio(dents_ratio, 0.07, 0.13)
		defects.append(DefectTag(tag="dents_deformation", severity=sev, confidence=min(1.0, dents_ratio * 6)))

	if stain_ratio >= 0.02:
		sev = _severity_from_ratio(stain_ratio, 0.04, 0.09)
		defects.append(
			DefectTag(tag="stains_discolouration", severity=sev, confidence=min(1.0, stain_ratio * 10))
		)

	if wear_ratio >= 0.5:
		wear_severity = "severe" if wear_ratio >= 0.85 else "moderate"
		defects.append(
			DefectTag(tag="general_wear_ageing", severity=wear_severity, confidence=min(1.0, wear_ratio / 1.2))
		)

	rank = {"minor": 1, "moderate": 2, "severe": 3}
	overall_severity = "minor"
	if defects:
		overall_severity = max(defects, key=lambda d: rank[d.severity]).severity

	penalty = 0
	for defect in defects:
		if defect.severity == "minor":
			penalty += 8
		elif defect.severity == "moderate":
			penalty += 18
		else:
			penalty += 30

	condition_score = max(0, min(100, 100 - penalty))

	if overall_severity == "severe":
		recommendation = "Immediate attention required. Escalate for urgent maintenance."
	elif overall_severity == "moderate":
		recommendation = "Plan maintenance within 7 days."
	elif defects:
		recommendation = "Monitor during next routine check."
	else:
		recommendation = "No immediate action needed."

	return ConditionResponse(
		scan_id=scan_id,
		condition_score=condition_score,
		defect_tags=defects,
		severity=overall_severity,
		recommended_action=recommendation,
	)


def run_condition_scoring(scan_id: str, image_bytes: bytes) -> ConditionResponse:
	image = _decode_image(image_bytes)
	condition = _score_image(scan_id, image)
	condition_store.upsert(condition)
	save_condition(scan_id=scan_id, condition_payload=condition.model_dump())
	return condition


def get_condition(scan_id: str) -> ConditionResponse | None:
	cached = condition_store.get(scan_id)
	if cached is not None:
		return cached

	payload = get_condition_payload(scan_id)
	if payload is None:
		return None

	condition = ConditionResponse(**payload)
	condition_store.upsert(condition)
	return condition
