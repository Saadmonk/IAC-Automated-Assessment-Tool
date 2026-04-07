import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session
from utils.docx_generator import generate_docx_report

st.set_page_config(page_title="Generate Word Report", layout="wide")
init_session()

st.title("Generate Word Report (.docx)")
st.caption("Produces a MALT-styled Word document that you can edit after download.")

# Show what's in session
session = dict(st.session_state)

# Completeness check
issues = []
if not session.get("report_number"): issues.append("Report number not set (Cover Info page)")
if not session.get("ar_list"): issues.append("No ARs added yet")
if not any(r.get("kwh",0) for r in session.get("elec_rows",[])): issues.append("Utility billing data empty")

if issues:
    st.warning("**Some sections are incomplete:**")
    for i in issues: st.write(f"• {i}")
    st.write("You can still generate the report — incomplete sections will be blank.")

col1, col2 = st.columns(2)
include_cyber = col1.checkbox("Include Cybersecurity section", value=True)
include_toc = col2.checkbox("Include Table of Contents", value=True)

if st.button("Generate Word Report", type="primary"):
    with st.spinner("Generating Word document..."):
        try:
            session_copy = dict(st.session_state)
            session_copy["include_cyber"] = include_cyber
            session_copy["include_toc"] = include_toc
            docx_bytes = generate_docx_report(session_copy)
            report_no = session.get("report_number", "MALT_Report")
            st.download_button(
                "⬇️ Download Word Report (.docx)",
                data=docx_bytes,
                file_name=f"{report_no}_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.success("Report generated successfully.")
        except Exception as e:
            st.error(f"Error generating report: {e}")
            import traceback; st.code(traceback.format_exc())
