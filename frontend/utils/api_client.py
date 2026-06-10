import requests
import streamlit as st
import io


def _extract_error_detail(response):
    """Safely extract error text from JSON or plain-text responses."""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "Unknown error"

    if isinstance(payload, dict):
        detail = payload.get("detail", payload)
        return str(detail)
    return str(payload)


def get_base_url():
    return st.session_state.get("api_url", "http://localhost:8000")


def validate_image(file_bytes):
    """Send file to backend for quality validation."""
    url = get_base_url()
    
    try:
        # Wrap bytes in tuple format: (filename, content, content_type)
        files = {"file": ("image.jpg", io.BytesIO(file_bytes), "image/jpeg")}
        res = requests.post(f"{url}/api/v1/image/validate", files=files, timeout=65)
        
        # Check for HTTP errors
        if res.status_code != 200:
            error_detail = _extract_error_detail(res)
            st.error(f"❌ Error: {error_detail}")
            return None
        
        return res.json()
    
    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None


def upload_image(file_bytes):
    """Send file to backend for upload and storage."""
    url = get_base_url()
    
    try:
        files = {"file": ("image.webp", io.BytesIO(file_bytes), "image/webp")}
        res = requests.post(f"{url}/api/v1/image/upload", files=files, timeout=65)
        
        # Check for HTTP errors
        if res.status_code not in [200, 201]:
            error_detail = _extract_error_detail(res)
            st.error(f"❌ Upload failed: {error_detail}")
            return None
        
        return res.json()
    
    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None


def get_condition(scan_id):
    """Fetch condition analysis for a scan."""
    url = get_base_url()
    
    try:
        res = requests.get(f"{url}/api/v1/scans/{scan_id}/condition", timeout=10)
        
        if res.status_code != 200:
            error_detail = _extract_error_detail(res)
            st.error(f"❌ Error: {error_detail}")
            return None
        
        return res.json()
    
    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None


def get_scan_history():
    """Fetch all uploaded scans with condition summary."""
    url = get_base_url()

    try:
        res = requests.get(f"{url}/api/v1/scans", timeout=15)

        if res.status_code != 200:
            error_detail = _extract_error_detail(res)
            st.error(f"❌ Error: {error_detail}")
            return None

        return res.json()

    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None
