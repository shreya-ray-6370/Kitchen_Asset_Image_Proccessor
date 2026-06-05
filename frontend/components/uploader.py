import streamlit as st
from PIL import Image
import io
import hashlib
from utils.api_client import validate_image, upload_image

def compress_image(file):
    img = Image.open(file)
    img = img.resize((1024, 1024))

    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=82)
    buffer.seek(0)

    return buffer


def uploader():

    st.markdown("### Upload Appliance Image")
    st.caption("Runs quality validation and image compression")

    uploaded_file = st.file_uploader(
        "Drop photo or browse",
        type=["jpg", "jpeg", "png", "webp"]
    )

    if not uploaded_file:
        # Clear transient New Scan status so stale grade badges do not appear on tab switches.
        st.session_state.pop("grade_data", None)
        st.session_state.pop("grade_file_token", None)
        st.session_state.pop("grade_api_url", None)
        st.session_state.pop("uploaded_file_token", None)
        st.session_state.pop("uploaded_scan_id", None)
        st.session_state.pop("uploading_file_token", None)
        st.session_state.pop("pending_upload_file_token", None)
        return

    image_bytes = uploaded_file.getvalue()
    image = Image.open(io.BytesIO(image_bytes))
    st.image(image, use_column_width=True)

    file_token = hashlib.sha1(image_bytes).hexdigest()
    current_api_url = st.session_state.get("api_url", "http://localhost:8000")
    cached_token = st.session_state.get("grade_file_token")
    cached_api_url = st.session_state.get("grade_api_url")
    uploaded_token = st.session_state.get("uploaded_file_token")

    if uploaded_token != file_token:
        st.session_state.pop("uploaded_file_token", None)
        st.session_state.pop("uploaded_scan_id", None)

    if st.session_state.get("uploading_file_token") != file_token:
        st.session_state.pop("uploading_file_token", None)

    if st.session_state.get("pending_upload_file_token") != file_token:
        st.session_state.pop("pending_upload_file_token", None)

    # Auto-run quality checks when a new file is uploaded or API endpoint changes.
    if cached_token != file_token or cached_api_url != current_api_url:
        with st.spinner("Running quality checks..."):
            data = validate_image(image_bytes)
        st.session_state["grade_data"] = data
        st.session_state["grade_file_token"] = file_token
        st.session_state["grade_api_url"] = current_api_url

    data = st.session_state.get("grade_data")
    if data is None:
        return

    if "grade" not in data:
        st.error("❌ Invalid response from server")
        return

    grade = data["grade"]
    allow_submit = False

    if grade == "Sharp":
        st.success("✅ Sharp")
        allow_submit = True
    elif grade == "Acceptable":
        st.warning("⚠ Acceptable")
        allow_submit = True
    else:
        st.error("❌ Marginal - Retake image")

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
        st.session_state.pop("uploading_file_token", None)
        st.success("✅ Uploaded successfully")
        st.rerun()

    can_click = allow_submit
    if st.button("Submit Image", disabled=not can_click, key=f"submit_{file_token[:12]}"):
        st.session_state["pending_upload_file_token"] = file_token
        st.rerun()
