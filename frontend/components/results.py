import streamlit as st
from utils.api_client import get_condition


def results():

    if "scan_id" not in st.session_state:
        st.info("No scan yet")
        return

    if st.button("Get Condition Result"):

        scan_id = st.session_state["scan_id"]

        data = get_condition(scan_id)
        if not data:
            st.error("Could not fetch condition result.")
            return

        st.subheader("Condition Analysis")

        st.metric(
            "🏆 Condition Score",
            f"{data['condition_score']}/100"
        )

        st.write("### Defects")
        for d in data["defect_tags"]:
            label = d.get("tag", d.get("type", "unknown_defect"))
            st.write(f"- {label} ({d['severity']})")

        st.write("### Recommended Action")
        st.info(data["recommended_action"])