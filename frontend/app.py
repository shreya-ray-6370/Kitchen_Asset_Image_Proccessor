import streamlit as st

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Kitchen Intelligence",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# GLOBAL STYLES
# -----------------------------
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

.stApp {
    background: linear-gradient(to right, #F7F7F7, #F2F6F3);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0F3D2E;
}

[data-testid="stSidebar"] * {
    color: white;
}

/* Ensure input visibility */
[data-testid="stTextInput"] input {
    color: #000000 !important;
    background-color: #ffffff !important;
}

/* Cards */
.card {
    background: white;
    padding: 22px;
    border-radius: 14px;
    box-shadow: 0px 4px 14px rgba(0,0,0,0.08);
    margin-bottom: 18px;
}

/* Buttons */
.stButton > button {
    width: 100%;
    background: linear-gradient(90deg, #FFC72C, #FFB000);
    color: black;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    height: 45px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# IMPORTS
# -----------------------------
from components.uploader import uploader
from components.results import results
from components.history import history_view

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.markdown("## 🍳 Kitchen Asset Processor")

menu = st.sidebar.radio(
    "Navigation",
    ["New Scan", "Results", "History"],
    key="nav_menu"   # ✅ FIX: prevents duplicate widget error
)

st.sidebar.markdown("---")

api_url = st.sidebar.text_input(
    "API Endpoint",
    value="http://localhost:8000",
    key="api_input"  # ✅ safe key
)

st.session_state["api_url"] = api_url

# -----------------------------
# HEADER
# -----------------------------
col1, col2 = st.columns([8, 2])

with col1:
    st.title("Kitchen Intelligence Dashboard")

with col2:
    st.markdown(
        "<div style='text-align:right;color:#0F3D2E;font-weight:600;'>Live Scanner</div>",
        unsafe_allow_html=True
    )

# -----------------------------
# MAIN LAYOUT
# -----------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)

if menu == "New Scan":
    uploader()

elif menu == "Results":
    results()

elif menu == "History":
    history_view()

st.markdown('</div>', unsafe_allow_html=True)