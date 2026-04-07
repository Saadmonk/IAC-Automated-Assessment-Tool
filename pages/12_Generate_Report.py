"""
Generate PDF Report
"""
import streamlit as st
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session
from utils.pdf_generator import generate_report

st.set_page_config(page_title="Generate Report", layout="wide")
init_session()

st.title("Generate PDF Report")
st.caption("Review the report summary below, then generate the full MALT IAC PDF.")

# ── Pre-flight checklist ─────────────────────────────────────────────────────
st.subheader("Pre-flight Checklist")

def check(label, condition):
    icon = "✅" if condition else "⚠️"
    st.markdown(f"{icon} {label}")
    return condition

ok1 = check("Report number entered",      bool(st.session_state.get("report_number", "").strip()))
ok2 = check("Site visit date set",        st.session_state.get("site_visit_date") is not None)
ok3 = check("Facility location entered",  bool(st.session_state.get("location", "").strip()))
ok4 = check("Lead student entered",       bool(st.session_state.get("lead_student", "").strip()))
ok5 = check("Electricity billing data entered", any(r.get("kwh",0)>0 for r in st.session_state.get("elec_rows",[])))
ok6 = check("At least one AR saved",      len(st.session_state.get("ar_list", [])) > 0)
ok7 = check("Facility description entered", bool(st.session_state.get("facility_description","").strip()))

all_ok = all([ok1, ok2, ok3, ok4, ok5, ok6, ok7])

if not all_ok:
    st.warning("Some items above are incomplete. You can still generate the report, but it may have gaps.")

st.divider()

# ── AR Summary ────────────────────────────────────────────────────────────────
ar_list = st.session_state.get("ar_list", [])
if ar_list:
    st.subheader(f"{len(ar_list)} AR(s) to include in report:")
    for ar in ar_list:
        pb = ar.get("payback", float("inf"))
        st.markdown(
            f"- **{ar.get('ar_number','?')}** — {ar.get('title','?')} (ARC {ar.get('arc_code','?')}) "
            f"| ${ar.get('total_cost_savings',0):,.0f}/yr | Payback: {pb:.1f} yr" if pb != float('inf') else
            f"- **{ar.get('ar_number','?')}** — {ar.get('title','?')}"
        )

# ── Generate ──────────────────────────────────────────────────────────────────
st.divider()
col1, col2 = st.columns([2, 1])
include_appendix = col2.checkbox("Include appendix pages (placeholder)", value=False)

if col1.button("🖨️ Generate PDF Report", type="primary", use_container_width=True):
    with st.spinner("Building PDF — this may take a few seconds…"):
        try:
            # Build session dict for PDF generator
            session_dict = dict(st.session_state)
            pdf_bytes = generate_report(session_dict)

            report_num = st.session_state.get("report_number", "IAC-report")
            filename = f"{report_num}_{datetime.now().strftime('%Y%m%d')}.pdf"
            out_path = os.path.join("/home/user/workspace/malt_iac_tool/reports", filename)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(pdf_bytes)

            st.success(f"✅ Report generated: **{filename}**")
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")
            import traceback
            st.code(traceback.format_exc())

# ── Session export (JSON) ─────────────────────────────────────────────────────
with st.expander("💾 Export / Import Session Data (JSON)"):
    import json
    st.markdown("Export all entered data as JSON to save progress or transfer to another machine.")

    if st.button("Export Session JSON", key="exp_json"):
        import pandas as pd
        # Filter out non-serializable items (DataFrames, etc.)
        def safe_serialize(obj):
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict("records")  # serialize DataFrames as list of dicts
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

        export_keys = [
            "report_number","site_visit_date","location","principal_products",
            "naics_code","sic_code","lead_faculty","lead_student","safety_student",
            "other_students","annual_sales","num_employees",
            "facility_description","process_description","best_practices",
            "elec_used_for","gas_used_for","equipment_rows","schedule_rows",
            "elec_rows","gas_rows","water_rows","has_gas","has_water","ar_list","smart_meter_df",
        ]
        export_data = {}
        for k in export_keys:
            v = st.session_state.get(k)
            if v is not None:
                export_data[k] = safe_serialize(v)

        # Handle date serialization
        if export_data.get("site_visit_date"):
            export_data["site_visit_date"] = str(export_data["site_visit_date"])

        json_str = json.dumps(export_data, indent=2, default=str)
        st.download_button(
            "⬇️ Download session.json",
            data=json_str,
            file_name=f"session_{st.session_state.get('report_number','draft')}.json",
            mime="application/json",
        )

    st.markdown("---")
    st.markdown("Import a previously saved session:")
    uploaded_json = st.file_uploader("Upload session.json", type=["json"], key="import_json")
    if uploaded_json is not None:
        try:
            data = json.load(uploaded_json)
            for k, v in data.items():
                st.session_state[k] = v
            st.success(f"✅ Loaded session data for report: {data.get('report_number','?')}")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to load session: {e}")
