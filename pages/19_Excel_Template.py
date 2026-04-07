import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session
from utils.excel_template import generate_excel_template, read_excel_template

st.set_page_config(page_title="Excel Template", layout="wide")
init_session()

st.title("Excel Data Template")
st.caption("Download the Excel template, fill it offline, then upload to populate all fields in the tool.")

tab1, tab2 = st.tabs(["📥 Download Template", "📤 Upload Filled Template"])

with tab1:
    st.subheader("Download Blank Template")
    st.write("The template contains sheets for: Cover Info, Utility Billing, Facility Background, and AR entries.")
    
    prefill = st.checkbox("Pre-fill with current session data", value=True)
    session_data = dict(st.session_state) if prefill else None
    
    if st.button("Generate Template", type="primary"):
        with st.spinner("Generating Excel template..."):
            try:
                xl_bytes = generate_excel_template(session_data)
                st.download_button(
                    "⬇️ Download Excel Template (.xlsx)",
                    data=xl_bytes,
                    file_name="MALT_IAC_Template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Upload Filled Template")
    st.info("Upload your completed Excel template to populate all input fields in the tool.")
    
    uploaded = st.file_uploader("Choose Excel file (.xlsx)", type=["xlsx"])
    
    if uploaded:
        st.write(f"File: **{uploaded.name}** ({uploaded.size:,} bytes)")
        
        if st.button("Import Data from Excel", type="primary"):
            with st.spinner("Reading Excel data..."):
                try:
                    data = read_excel_template(uploaded.read())
                    count = 0
                    for key, value in data.items():
                        if value is not None and value != "":
                            st.session_state[key] = value
                            count += 1
                    st.success(f"Imported {count} fields from Excel. Navigate to any page to see the data.")
                    
                    # Show preview
                    with st.expander("Preview imported data"):
                        for key, value in data.items():
                            if value:
                                st.write(f"**{key}:** {str(value)[:100]}")
                except Exception as e:
                    st.error(f"Error reading template: {e}")
                    import traceback; st.code(traceback.format_exc())
