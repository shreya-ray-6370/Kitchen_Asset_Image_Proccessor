import streamlit as st
from PIL import Image
import io
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

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, use_column_width=True)

        # ✅ Step 2: Validate
        if st.button("Run Quality Check"):

            data = validate_image(uploaded_file.getvalue())

            st.session_state["grade_data"] = data


    # ✅ Step 3: Show grade
    if "grade_data" in st.session_state:

        data = st.session_state["grade_data"]
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
            allow_submit = False

        # ✅ Step 4: Submit button
        if st.button("Submit Image", disabled=not allow_submit):

            compressed = compress_image(uploaded_file)

            # ✅ Step 6: Upload
            upload_data = upload_image(compressed)

            st.session_state["scan_id"] = upload_data["scan_id"]

            st.success("✅ Uploaded successfully")
