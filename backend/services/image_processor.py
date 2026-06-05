import cv2
import numpy as np
from PIL import Image
import io

TARGET_SIZE = (1024, 1024)
WEBP_QUALITY = 82


def _largest_contour_ratio(mask: np.ndarray) -> float:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    largest = max(contours, key=cv2.contourArea)
    frame_area = float(mask.shape[0] * mask.shape[1])
    return float(cv2.contourArea(largest)) / frame_area if frame_area else 0.0


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


def _largest_contour_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(largest)

# ✅ QUALITY CHECK
def check_quality(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("Invalid image bytes") from exc

    img_np = np.array(img)

    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    # Sharpness
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Build an appliance-centric mask so lighting is measured on the asset, not the full scene.
    asset_mask = _asset_mask(gray)
    framing = _largest_contour_ratio(asset_mask)
    asset_area = int(np.count_nonzero(asset_mask))
    roi_pixels = gray[asset_mask > 0] if asset_area > int(gray.size * 0.08) else gray.reshape(-1)

    # Lighting: combine imbalance, dynamic range, and global over/under exposure on ROI.
    bbox = _largest_contour_bbox(asset_mask)
    if bbox is not None:
        x, y, bw, bh = bbox
        crop = gray[y:y + bh, x:x + bw]
    else:
        crop = gray

    h, w = crop.shape
    quads = [
        crop[0:h//2, 0:w//2],
        crop[0:h//2, w//2:],
        crop[h//2:, 0:w//2],
        crop[h//2:, w//2:]
    ]
    quad_means = [float(np.mean(q)) for q in quads if q.size > 0]
    quadrant_delta = max(quad_means) - min(quad_means)
    mean_luma = float(np.mean(roi_pixels))
    highlight_ratio = float(np.mean(roi_pixels >= 245))
    hot_ratio = float(np.mean(roi_pixels >= 252))
    bright_ratio = float(np.mean(roi_pixels >= 220))
    dark_ratio = float(np.mean(roi_pixels <= 35))

    highlight_mask = ((gray >= 245) & (asset_mask > 0)).astype(np.uint8) * 255
    highlight_cluster_ratio = _largest_contour_ratio(highlight_mask)
    glare_penalty = (highlight_ratio * 1300.0) + (hot_ratio * 2500.0)
    harsh_glare_penalty = max(0.0, (highlight_cluster_ratio - 0.008) * 1800.0)
    harsh_glare_penalty += max(0.0, (highlight_ratio - 0.04) * 1200.0)
    overexposure_penalty = max(0.0, (mean_luma - 170.0) * 1.0) + (bright_ratio * 170.0)
    underexposure_penalty = max(0.0, (78.0 - mean_luma) * 1.1) + (dark_ratio * 180.0)
    dynamic_spread = float(np.percentile(roi_pixels, 98) - np.percentile(roi_pixels, 30))
    spread_low_penalty = max(0.0, (34.0 - dynamic_spread) * 1.6)
    spread_high_penalty = max(0.0, (dynamic_spread - 95.0) * 0.35)
    lighting = max(
        quadrant_delta,
        glare_penalty,
        harsh_glare_penalty,
        overexposure_penalty,
        underexposure_penalty,
        spread_low_penalty,
        spread_high_penalty,
    )

    # Lighting can still pass diffuse sunlight; penalize strong top-bottom gradients within ROI.
    top_half = crop[: max(1, h // 2), :]
    bottom_half = crop[h // 2 :, :]
    vertical_gradient = abs(float(np.mean(top_half)) - float(np.mean(bottom_half))) if bottom_half.size > 0 else 0.0
    lighting = max(lighting, vertical_gradient * 1.15)

    return {
        "sharpness": float(sharpness),
        "lighting": float(lighting),
        "framing": float(framing)
    }


# ✅ IMAGE COMPRESSION
def process_image(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("Invalid image bytes") from exc

    # Resize
    img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

    # Convert to WebP
    output = io.BytesIO()
    # Rebuilding the image in-memory strips original EXIF metadata by design.
    img.save(output, format="WEBP", quality=WEBP_QUALITY, optimize=True, method=6)

    return output.getvalue()