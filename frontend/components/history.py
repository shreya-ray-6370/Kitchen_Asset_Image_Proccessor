import streamlit as st

from utils.api_client import get_scan_history


def history_view():
    st.markdown("### Uploaded Scans History")
    st.caption("Shows all uploaded images and their condition analysis")

    payload = get_scan_history()
    if not payload:
        st.info("No history available yet.")
        return

    items = payload.get("items", [])
    if not items:
        st.info("No scans found.")
        return

    for item in items:
        with st.container(border=True):
            left, right = st.columns([1, 1.5])

            with left:
                st.image(item["image_url"], use_column_width=True)

            with right:
                st.markdown(f"**Scan ID:** {item['scan_id']}")
                if item.get("created_at"):
                    st.markdown(f"**Created At:** {item['created_at']}")

                condition = item.get("condition")
                if not condition:
                    st.warning("Condition analysis not available yet.")
                    continue

                st.metric("Condition Score", f"{condition['condition_score']}/100")
                st.markdown(f"**Severity:** {condition['severity']}")

                defect_tags = condition.get("defect_tags", [])
                if defect_tags:
                    st.markdown("**Defects:**")
                    for defect in defect_tags:
                        st.write(f"- {defect['tag']} ({defect['severity']})")
                else:
                    st.write("No defects detected")

                st.info(condition.get("recommended_action", "No recommendation"))
