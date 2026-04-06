"""
MALT IAC Report Generator — Main Entry Point
Run with: streamlit run app.py
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from utils.session import init_session, get_utility_rates

st.set_page_config(
    page_title="MALT IAC Report Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session()

# ── Sidebar info ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://www.ucs.edu/assets/images/logo-placeholder.png", width=120) if False else None
    st.markdown("## ⚡ MALT IAC")
    st.markdown("**Report Generator**")
    st.markdown("*University of Louisiana at Lafayette*")
    st.divider()

    # Quick status
    report_num = st.session_state.get("report_number", "")
    location   = st.session_state.get("location", "")
    ar_count   = len(st.session_state.get("ar_list", []))
    rates      = get_utility_rates()

    st.markdown(f"**Report:** {report_num or '*(not set)*'}")
    st.markdown(f"**Facility:** {location or '*(not set)*'}")
    st.markdown(f"**ARs saved:** {ar_count}")
    if rates.get("total_annual_utility_cost", 0) > 0:
        st.markdown(f"**Total utility cost:** ${rates['total_annual_utility_cost']:,.0f}/yr")

    st.divider()
    st.markdown("""
**Workflow:**
1. [Cover Info](1_Cover_Info)
2. [Utility Billing](2_Utility_Billing)
3. [Facility Background](3_Facility_Background)
4. [Thermostat ARC](4_AR_Thermostat) 
5. [LED Lighting ARC](5_AR_LED_Lighting)
6. [Chilled Water ARC](6_AR_Chilled_Water)
7. [Compressed Air ARC](7_AR_Compressed_Air)
8. [VFD ARC](8_AR_VFD)
9. [Other ARCs](9_AR_Other)
10. [AR Summary](10_AR_Summary)
11. [Executive Summary](11_Executive_Summary)
12. [Generate Report](12_Generate_Report)
""")

# ── Home page ─────────────────────────────────────────────────────────────────
st.title("⚡ MALT IAC Report Generator")
st.markdown(
    "**MALT Industrial Assessment Center** | University of Louisiana at Lafayette  \n"
    "Funded by the U.S. Department of Energy"
)

st.divider()

# Status dashboard
col1, col2, col3, col4 = st.columns(4)
col1.metric("Report #", report_num or "—")
col2.metric("ARs Saved", ar_count)
rates = get_utility_rates()
col3.metric("Annual Utility Cost", f"${rates.get('total_annual_utility_cost',0):,.0f}" if rates.get('total_annual_utility_cost',0) > 0 else "—")
total_savings = sum(a.get("total_cost_savings",0) for a in st.session_state.get("ar_list",[]))
col4.metric("Total Potential Savings", f"${total_savings:,.0f}/yr" if total_savings > 0 else "—")

st.divider()

# Quick-start guide
st.subheader("Getting Started")
steps = [
    ("1️⃣", "Cover Info", "Enter report number, site visit date, facility info, and team members.", "pages/1_Cover_Info"),
    ("2️⃣", "Utility Billing", "Enter 12 months of electricity, gas, and water bills to auto-calculate rates.", "pages/2_Utility_Billing"),
    ("3️⃣", "Facility Background", "Describe the facility, process, best practices, and major equipment.", "pages/3_Facility_Background"),
    ("4️⃣", "ARC Pages", "Fill in each applicable ARC page. Run calculations and save each AR.", "pages/4_AR_Thermostat"),
    ("5️⃣", "AR Summary", "Review all saved ARs, reorder them, and verify totals.", "pages/10_AR_Summary"),
    ("6️⃣", "Executive Summary", "Auto-generated summary table. Review narratives.", "pages/11_Executive_Summary"),
    ("7️⃣", "Generate Report", "Generate and download the full MALT IAC PDF report.", "pages/12_Generate_Report"),
]

for icon, title, desc, _ in steps:
    with st.container():
        col1, col2 = st.columns([0.4, 5])
        col1.markdown(f"## {icon}")
        col2.markdown(f"**{title}**  \n{desc}")

st.divider()
st.markdown(
    "Use the **sidebar navigation** (or the pages list above) to move between sections.  \n"
    "All data is stored in your browser session — use **Generate Report → Export JSON** to save progress."
)

# ── Reset ─────────────────────────────────────────────────────────────────────
with st.expander("⚠️ Reset Session (start new report)"):
    st.warning("This will clear ALL entered data and start a fresh report.")
    if st.button("🗑 Clear all data and start new report", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
