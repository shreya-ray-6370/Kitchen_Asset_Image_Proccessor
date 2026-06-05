import streamlit as st
from utils.api_client import get_condition


def _render_gpt_block(payload: dict):
    st.markdown("### GPT-4 Output")
    st.metric("Condition Score", f"{payload.get('condition_score', 0)}/100")
    st.write(f"Severity: {payload.get('severity', 'minor')}")

    tags = payload.get("defect_tags", [])
    if tags:
        st.write("Defects:")
        for tag in tags:
            label = tag.get("tag", "unknown_defect")
            sev = tag.get("severity", "minor")
            st.write(f"- {label} ({sev})")
    else:
        st.write("Defects: none")

    st.info(payload.get("recommended_action", "No recommendation"))

    rationale = payload.get("rationale")
    if rationale:
        st.caption(f"Rationale: {rationale}")


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

        gpt4_result = data.get("gpt4_result")
        if gpt4_result:
            _render_gpt_block(gpt4_result)
        else:
            st.markdown("### GPT-4 Output")
            st.warning("GPT-4 output unavailable")