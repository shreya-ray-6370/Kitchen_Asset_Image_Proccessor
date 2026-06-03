import streamlit as st
from frontend.components.uploader import uploader
from frontend.components.results import results

st.set_page_config(layout="wide")

# ✅ Sidebar
st.sidebar.title("Kitchen Intelligence")

page = st.sidebar.radio("Menu", ["New Scan", "Results"])

if page == "New Scan":
    uploader()

elif page == "Results":
    results()