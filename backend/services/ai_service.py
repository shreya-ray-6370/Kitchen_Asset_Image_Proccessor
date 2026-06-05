from __future__ import annotations

import cv2
import numpy as np

from backend.db.in_memory_store import condition_store
from backend.models.schemas import ConditionResponse, DefectTag, ModelConditionResult
from backend.services.sqlite_service import get_condition_payload, save_condition
from backend.services.vlm_service import run_gpt4_side_by_side


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


def _blob_ratio(mask: np.ndarray, min_blob_area: int) -> float:
	clean = cv2.morphologyEx(
		mask,
		cv2.MORPH_OPEN,
		cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
	)
	contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	if not contours:
		return 0.0

	area_sum = float(sum(cv2.contourArea(c) for c in contours if cv2.contourArea(c) >= min_blob_area))
	frame_area = float(mask.shape[0] * mask.shape[1])
	return area_sum / frame_area if frame_area else 0.0


def _crack_ratio(mask: np.ndarray, min_blob_area: int) -> float:
	clean = cv2.morphologyEx(
		mask,
		cv2.MORPH_OPEN,
		cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
	)
	contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	if not contours:
		return 0.0

	area_sum = 0.0
	for contour in contours:
		area = float(cv2.contourArea(contour))
		if area < min_blob_area:
			continue

		x, y, w, h = cv2.boundingRect(contour)
		if w == 0 or h == 0:
			continue

		elongation = max(w / h, h / w)
		fill_ratio = area / float(w * h)
		# Cracks tend to be elongated and sparse; this filters broad reflection patches.
		if elongation < 2.2 or fill_ratio > 0.42:
			continue

		area_sum += area

	frame_area = float(mask.shape[0] * mask.shape[1])
	return area_sum / frame_area if frame_area else 0.0


def _asset_mask(gray: np.ndarray) -> np.ndarray:
	blur = cv2.GaussianBlur(gray, (5, 5), 0)
	_, otsu_mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
	if float(np.mean(otsu_mask > 0)) > 0.5:
		otsu_mask = cv2.bitwise_not(otsu_mask)

	clean = cv2.morphologyEx(
		otsu_mask,
		cv2.MORPH_OPEN,
		cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
	)
	clean = cv2.morphologyEx(
		clean,
		cv2.MORPH_CLOSE,
		cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
	)
	return clean


def _score_image(scan_id: str, image_bgr: np.ndarray) -> ConditionResponse:
	denoised = cv2.bilateralFilter(image_bgr, 7, 35, 35)
	hsv = cv2.cvtColor(denoised, cv2.COLOR_BGR2HSV)
	gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
	asset_mask = _asset_mask(gray)
	asset_area = float(np.count_nonzero(asset_mask))
	if asset_area < float(gray.size) * 0.08:
		asset_mask = np.full_like(gray, 255, dtype=np.uint8)
		asset_area = float(gray.size)
	total = max(asset_area, 1.0)
	h, s, v = cv2.split(hsv)
	highlight_ratio = float(np.mean(v[asset_mask > 0] >= 245))
	mean_saturation = float(np.mean(s[asset_mask > 0]))

	# Ignore blown highlights which frequently cause false positives on metallic surfaces.
	valid = ((v < 245) & (asset_mask > 0)).astype(np.uint8) * 255

	rust_mask = cv2.inRange(hsv, (6, 100, 40), (22, 255, 200))
	rust_mask = cv2.bitwise_and(rust_mask, valid)
	rust_ratio = _blob_ratio(rust_mask, min_blob_area=180)

	blackhat = cv2.morphologyEx(
		gray,
		cv2.MORPH_BLACKHAT,
		cv2.getStructuringElement(cv2.MORPH_RECT, (13, 13)),
	)
	_, crack_mask = cv2.threshold(blackhat, 31, 255, cv2.THRESH_BINARY)
	crack_mask = cv2.bitwise_and(crack_mask, cv2.inRange(v, 0, 185))
	crack_mask = cv2.bitwise_and(crack_mask, asset_mask)

	# Ignore frame boundaries where straight appliance edges can mimic cracks.
	h_img, w_img = gray.shape
	interior = np.zeros_like(gray, dtype=np.uint8)
	pad_x = max(8, int(w_img * 0.06))
	pad_y = max(8, int(h_img * 0.06))
	interior[pad_y:h_img - pad_y, pad_x:w_img - pad_x] = 255
	crack_mask = cv2.bitwise_and(crack_mask, interior)
	crack_ratio = _crack_ratio(crack_mask, min_blob_area=110)

	smooth = cv2.GaussianBlur(gray, (15, 15), 0)
	delta = cv2.absdiff(gray, smooth)
	_, dents_mask = cv2.threshold(delta, 24, 255, cv2.THRESH_BINARY)
	dents_mask = cv2.bitwise_and(dents_mask, cv2.inRange(s, 0, 95))
	dents_mask = cv2.bitwise_and(dents_mask, cv2.inRange(v, 50, 230))
	dents_mask = cv2.bitwise_and(dents_mask, asset_mask)
	dents_ratio = _blob_ratio(dents_mask, min_blob_area=260)

	lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
	_, a_chan, b_chan = cv2.split(lab)
	med_a = float(np.median(a_chan))
	med_b = float(np.median(b_chan))
	chroma_shift = (
		(np.abs(a_chan.astype(np.float32) - med_a) > 14)
		| (np.abs(b_chan.astype(np.float32) - med_b) > 14)
	)
	dark_colored = (v < 155) & (s > 45)
	stain_mask = (chroma_shift & (s > 35) & (v > 40) & (v < 220)) | dark_colored
	stain_mask = (stain_mask.astype(np.uint8) * 255)
	stain_mask = cv2.bitwise_and(stain_mask, valid)
	stain_ratio = _blob_ratio(stain_mask, min_blob_area=320)

	edges = cv2.Canny(gray, 90, 190)
	edge_ratio = float(np.count_nonzero(cv2.bitwise_and(edges, valid))) / total
	wear_ratio = min(1.0, edge_ratio * 3.0 + float(np.std(gray)) / 400.0)

	defects: list[DefectTag] = []

	if rust_ratio >= 0.01:
		sev = _severity_from_ratio(rust_ratio, 0.025, 0.05)
		defects.append(DefectTag(tag="rust_corrosion", severity=sev, confidence=min(1.0, rust_ratio * 14)))

	crack_threshold = 0.058
	stain_threshold = 0.03
	if mean_saturation < 60 and highlight_ratio > 0.012:
		# On glossy appliances with bright reflections, demand stronger evidence.
		crack_threshold *= 1.8
		stain_threshold *= 1.5

	if crack_ratio >= crack_threshold:
		sev = _severity_from_ratio(crack_ratio, 0.08, 0.14)
		defects.append(DefectTag(tag="cracks_fractures", severity=sev, confidence=min(1.0, crack_ratio * 6.2)))

	if dents_ratio >= 0.018:
		sev = _severity_from_ratio(dents_ratio, 0.03, 0.06)
		defects.append(DefectTag(tag="dents_deformation", severity=sev, confidence=min(1.0, dents_ratio * 6)))

	if stain_ratio >= stain_threshold:
		sev = _severity_from_ratio(stain_ratio, 0.05, 0.10)
		defects.append(
			DefectTag(tag="stains_discolouration", severity=sev, confidence=min(1.0, stain_ratio * 5.2))
		)

	if wear_ratio >= 0.30:
		wear_severity = "severe" if wear_ratio >= 0.55 else "moderate"
		defects.append(
			DefectTag(tag="general_wear_ageing", severity=wear_severity, confidence=min(1.0, wear_ratio / 1.2))
		)

	# On glossy metallic surfaces, reflections can mimic stains/cracks.
	if mean_saturation < 55:
		for defect in defects:
			if defect.tag in {"stains_discolouration", "cracks_fractures"}:
				if defect.severity == "severe":
					defect.severity = "moderate"
				elif defect.severity == "moderate":
					defect.severity = "minor"
				defect.confidence = min(defect.confidence, 0.75)

	# Additional guardrail for glossy reflections: weak single finding should stay minor.
	if mean_saturation < 60 and highlight_ratio > 0.012:
		non_rust = [d for d in defects if d.tag != "rust_corrosion"]
		if len(non_rust) == 1 and non_rust[0].confidence < 0.85:
			non_rust[0].severity = "minor"

	# Non-rust findings are noisier; require multiple independent signals before escalating.
	non_rust_tags = [d for d in defects if d.tag != "rust_corrosion"]
	if len(non_rust_tags) == 1 and rust_ratio < 0.01:
		non_rust_tags[0].severity = "minor"
		non_rust_tags[0].confidence = min(non_rust_tags[0].confidence, 0.7)
	if len(non_rust_tags) <= 1 and all(d.tag != "rust_corrosion" for d in defects):
		for defect in defects:
			if defect.severity == "severe":
				defect.severity = "moderate"

	rank = {"minor": 1, "moderate": 2, "severe": 3}
	overall_severity = "minor"
	if defects:
		overall_severity = max(defects, key=lambda d: rank[d.severity]).severity

	# Safety valve: single uncertain severe finding should not collapse the whole score.
	if overall_severity == "severe":
		severe_count = sum(1 for d in defects if d.severity == "severe")
		max_conf = max((d.confidence for d in defects), default=0.0)
		if severe_count == 1 and (len(defects) <= 2 or max_conf < 0.9):
			overall_severity = "moderate"

	penalty = 0
	for defect in defects:
		if defect.severity == "minor":
			penalty += 6
		elif defect.severity == "moderate":
			penalty += 14
		else:
			penalty += 22

	condition_score = max(0, min(100, 100 - penalty))
	if defects and rust_ratio < 0.01 and len(non_rust_tags) <= 1:
		condition_score = max(condition_score, 88)

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


def _as_model_result(source: str, condition: ConditionResponse, confidence: float | None = None) -> ModelConditionResult:
	return ModelConditionResult(
		model=source,
		condition_score=condition.condition_score,
		defect_tags=condition.defect_tags,
		severity=condition.severity,
		recommended_action=condition.recommended_action,
		confidence=confidence,
	)


def _comparison_note(opencv_result: ModelConditionResult, gpt4_result: ModelConditionResult | None) -> str | None:
	if gpt4_result is None:
		return "GPT-4 side-by-side output unavailable (check ENABLE_GPT4_SIDE_BY_SIDE and OPENAI_API_KEY)."

	if opencv_result.severity != gpt4_result.severity:
		return f"Severity mismatch: OpenCV={opencv_result.severity}, GPT-4={gpt4_result.severity}."

	score_gap = abs(opencv_result.condition_score - gpt4_result.condition_score)
	if score_gap >= 20:
		return f"Large score gap detected ({score_gap} points). Review image manually."

	return "OpenCV and GPT-4 broadly agree."


def run_condition_scoring(scan_id: str, image_bytes: bytes) -> ConditionResponse:
	image = _decode_image(image_bytes)
	opencv_condition = _score_image(scan_id, image)
	opencv_result = _as_model_result("opencv", opencv_condition)
	gpt4_result = run_gpt4_side_by_side(image_bytes)

	condition = ConditionResponse(
		scan_id=scan_id,
		condition_score=opencv_condition.condition_score,
		defect_tags=opencv_condition.defect_tags,
		severity=opencv_condition.severity,
		recommended_action=opencv_condition.recommended_action,
		opencv_result=opencv_result,
		gpt4_result=gpt4_result,
		comparison_note=_comparison_note(opencv_result, gpt4_result),
	)

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
