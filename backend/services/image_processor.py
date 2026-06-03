import cv2
import numpy as np
from PIL import Image
import io

TARGET_SIZE = (1024, 1024)
WEBP_QUALITY = 82

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

    # Lighting
    h, w = gray.shape
    quads = [
        gray[0:h//2, 0:w//2],
        gray[0:h//2, w//2:],
        gray[h//2:, 0:w//2],
        gray[h//2:, w//2:]
    ]
    lighting = np.std([np.mean(q) for q in quads])

    # Framing
    thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)[1]
    framing = np.sum(thresh > 0) / thresh.size

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