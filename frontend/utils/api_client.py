import requests
import streamlit as st


def get_base_url():
    return st.session_state.get("api_url", "http://localhost:8000")


def validate_image(file):
    url = get_base_url()
    files = {"file": file}
    res = requests.post(f"{url}/api/v1/image/validate", files=files)
    return res.json()


def upload_image(file):
    url = get_base_url()
    files = {"file": file}
    res = requests.post(f"{url}/api/v1/image/upload", files=files)
    return res.json()


def get_condition(scan_id):
    url = get_base_url()
    res = requests.get(f"{url}/api/v1/scans/{scan_id}/condition")
    return res.json()
