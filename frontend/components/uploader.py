import streamlit as st
from PIL import Image
import io
import hashlib
from utils.api_client import validate_image, upload_image

MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def _compression_preview(image_bytes: bytes) -> tuple[tuple[int, int], int, tuple[int, int], int]:
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    original_dims = original.size
    original_size = len(image_bytes)

    resized = original.resize((1024, 1024))
    buffer = io.BytesIO()
    resized.save(buffer, format="WEBP", quality=82)
    compressed_size = len(buffer.getvalue())

    return original_dims, original_size, resized.size, compressed_size


def _render_metadata_panel(metadata: dict):
    st.markdown(
        """
        <style>
        .meta-card {
            border: 1px solid #e6e7eb;
            border-radius: 10px;
            padding: 0.75rem 0.8rem;
            background: #fafbfc;
            min-height: 86px;
        }
        .meta-label {
            font-size: 0.98rem;
            font-weight: 700;
            color: #2a2f38;
            margin-bottom: 0.25rem;
        }
        .meta-value {
            font-size: 0.9rem;
            font-weight: 500;
            color: #1f2937;
            word-break: break-word;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    appliance_type = metadata.get("appliance_type", "unknown").replace("_", " ").title()
    brand = metadata.get("brand", "Unknown")

    col1, col2 = st.columns(2)
    col1.markdown(
        f"""
        <div class=\"meta-card\">
            <div class=\"meta-label\">Category</div>
            <div class=\"meta-value\">{appliance_type}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"""
        <div class=\"meta-card\">
            <div class=\"meta-label\">Brand</div>
            <div class=\"meta-value\">{brand}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    conf = metadata.get("confidence", 0)
    src = metadata.get("source", "")
    st.caption(f"Confidence: {round(float(conf) * 100)}%  |  Source: {src}")

def compress_image(file):
    img = Image.open(file)
    img = img.resize((1024, 1024))

    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=82)
    buffer.seek(0)

    return buffer


def uploader():

    st.markdown("### Upload Appliance Image")
    st.caption("Runs quality validation and image compression.")
    st.info("Accepted formats: JPG, JPEG, PNG, WEBP | Maximum file size: 15 MB")

    uploaded_file = st.file_uploader(
        "Drop photo or browse",
        type=["jpg", "jpeg", "png", "webp"],
        help="Supported formats: JPG, JPEG, PNG, WEBP | Max file size: 15MB"
    )

    if not uploaded_file:
        # Clear transient New Scan status so stale grade badges do not appear on tab switches.
        st.session_state.pop("grade_data", None)
        st.session_state.pop("grade_file_token", None)
        st.session_state.pop("grade_api_url", None)
        st.session_state.pop("qc_metadata", None)
        st.session_state.pop("uploaded_file_token", None)
        st.session_state.pop("uploaded_scan_id", None)
        st.session_state.pop("uploaded_metadata", None)
        st.session_state.pop("uploading_file_token", None)
        st.session_state.pop("pending_upload_file_token", None)
        return

    image_bytes = uploaded_file.getvalue()
    if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        actual_mb = len(image_bytes) / (1024 * 1024)
        st.error(
            f"❌ File is too large ({actual_mb:.2f} MB). "
            f"Maximum allowed size is {max_mb} MB. Please choose a smaller image."
        )
        return

    image = Image.open(io.BytesIO(image_bytes))
    st.image(image, use_column_width=True)

    try:
        orig_dims, orig_size, cmp_dims, cmp_size = _compression_preview(image_bytes)
        delta = max(0, orig_size - cmp_size)
        reduction_pct = (delta / orig_size * 100.0) if orig_size > 0 else 0.0

        st.markdown("#### Compression Preview")
        c1, c2, c3 = st.columns(3)
        c1.metric("Original", f"{orig_dims[0]}x{orig_dims[1]} | {_format_bytes(orig_size)}")
        c2.metric("Compressed", f"{cmp_dims[0]}x{cmp_dims[1]} | {_format_bytes(cmp_size)}")
        c3.metric("Reduced By", f"{reduction_pct:.1f}%")
        st.caption("Target format: WEBP | Quality: 82 | Target dimensions: 1024x1024")
    except Exception:
        st.info("Compression preview unavailable for this image, but upload compression rules remain unchanged.")

    file_token = hashlib.sha1(image_bytes).hexdigest()
    current_api_url = st.session_state.get("api_url", "http://localhost:8000")
    cached_token = st.session_state.get("grade_file_token")
    cached_api_url = st.session_state.get("grade_api_url")
    uploaded_token = st.session_state.get("uploaded_file_token")

    if uploaded_token != file_token:
        st.session_state.pop("uploaded_file_token", None)
        st.session_state.pop("uploaded_scan_id", None)
        st.session_state.pop("uploaded_metadata", None)
        st.session_state.pop("qc_metadata", None)

    if st.session_state.get("uploading_file_token") != file_token:
        st.session_state.pop("uploading_file_token", None)

    if st.session_state.get("pending_upload_file_token") != file_token:
        st.session_state.pop("pending_upload_file_token", None)

    # Auto-run quality checks when a new file is uploaded or API endpoint changes.
    if cached_token != file_token or cached_api_url != current_api_url:
        with st.spinner("Running quality checks and analysing appliance..."):
            data = validate_image(image_bytes)
        st.session_state["grade_data"] = data
        st.session_state["grade_file_token"] = file_token
        st.session_state["grade_api_url"] = current_api_url
        # Cache quality-check metadata separately — uses original (uncompressed) image bytes.
        if data and data.get("metadata"):
            st.session_state["qc_metadata"] = data["metadata"]
        else:
            st.session_state.pop("qc_metadata", None)

    data = st.session_state.get("grade_data")
    if data is None:
        return

    if "grade" not in data:
        st.error("❌ Invalid response from server")
        return

    grade = data["grade"]
    # Prefer quality-check metadata (uncompressed image) over upload metadata.
    metadata = st.session_state.get("qc_metadata") or data.get("metadata")
    allow_submit = False

    if grade == "Sharp":
        st.success("✅ Sharp")
        allow_submit = True
    elif grade == "Acceptable":
        st.warning("⚠ Acceptable")
        allow_submit = True
    else:
        st.error("❌ Marginal - Retake image")

    # ── Appliance metadata panel ──────────────────────────────────
    if metadata:
        with st.expander("🔍 Detected Appliance Info", expanded=True):
            _render_metadata_panel(metadata)
    else:
        st.info("ℹ️ Appliance info will appear here after quality check.")

    already_uploaded = st.session_state.get("uploaded_file_token") == file_token
    if already_uploaded:
        scan_id = st.session_state.get("uploaded_scan_id")
        st.success(f"✅ Uploaded successfully (scan_id: {scan_id})")
        st.info("This image is already uploaded. Choose a new image for another scan.")
        return

    pending_upload = st.session_state.get("pending_upload_file_token") == file_token
    if pending_upload:
        st.session_state["uploading_file_token"] = file_token
        with st.spinner("Uploading image..."):
            compressed = compress_image(uploaded_file)
            upload_data = upload_image(compressed.getvalue())

        st.session_state.pop("pending_upload_file_token", None)

        if upload_data is None:
            st.session_state.pop("uploading_file_token", None)
            st.error("Upload failed. Please retry.")
            st.rerun()
            return

        st.session_state["scan_id"] = upload_data["scan_id"]
        st.session_state["uploaded_file_token"] = file_token
        st.session_state["uploaded_scan_id"] = upload_data["scan_id"]
        # Prefer quality-check metadata (cleaner image) over upload metadata.
        st.session_state["uploaded_metadata"] = (
            st.session_state.get("qc_metadata")
            or upload_data.get("metadata")
        )
        st.session_state.pop("uploading_file_token", None)
        st.success("✅ Uploaded successfully")
        st.rerun()

    can_click = allow_submit
    if st.button("Submit Image", disabled=not can_click, key=f"submit_{file_token[:12]}"):
        st.session_state["pending_upload_file_token"] = file_token
        st.rerun()
