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

                metadata = item.get("metadata")
                if metadata:
                    st.markdown(
                        f"**Appliance:** {metadata.get('appliance_type', 'unknown')}"
                        f" | **Brand:** {metadata.get('brand', 'Unknown')}"
                    )

                condition = item.get("condition")
                if not condition:
                    st.warning("Condition analysis not available yet.")
                    continue

                cond_metadata = condition.get("metadata")
                if not metadata and cond_metadata:
                    st.markdown(
                        f"**Appliance:** {cond_metadata.get('appliance_type', 'unknown')}"
                        f" | **Brand:** {cond_metadata.get('brand', 'Unknown')}"
                    )

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

                gpt4_result = condition.get("gpt4_result")
                st.markdown("**GPT-4 Output:**")
                if gpt4_result:
                    st.write(
                        f"{gpt4_result.get('condition_score', 0)}/100, "
                        f"{gpt4_result.get('severity', 'minor')}"
                    )
                else:
                    st.write("GPT-4 output unavailable")
