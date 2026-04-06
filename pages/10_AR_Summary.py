"""
AR Summary / Management Page
View, reorder, and edit all saved ARs. Displays the Section 1.2 Summary table.
"""
import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates

st.set_page_config(page_title="AR Summary", layout="wide")
init_session()

st.title("Assessment Recommendations — Summary")
st.caption("All saved ARs appear below. This table will be printed in Section 1.2 of the report.")

ar_list = st.session_state.get("ar_list", [])

if not ar_list:
    st.info("No ARs saved yet. Go to the individual ARC pages (Thermostat, LED Lighting, etc.) and click **Save AR to Report**.")
else:
    # ── Summary Table ────────────────────────────────────────────────────────
    st.subheader("Section 1.2 — Summary of Recommendations")
    rows = []
    for i, ar in enumerate(ar_list):
        # Format resource savings
        res_str = "; ".join(
            f"{r['type']}: {r['savings']:,.0f} {r['unit']}"
            for r in ar.get("resources", [])
            if r.get("savings", 0) > 0
        )
        pb = ar.get("payback", float("inf"))
        rows.append({
            "#": i + 1,
            "AR #": ar.get("ar_number", "—"),
            "ARC Code": ar.get("arc_code", "—"),
            "Title": ar.get("title", "—"),
            "Resource Savings": res_str or "—",
            "Cost Savings ($/yr)": f"${ar.get('total_cost_savings', 0):,.0f}",
            "Impl. Cost ($)": f"${ar.get('implementation_cost', 0):,.0f}",
            "Payback (yr)": f"{pb:.1f}" if pb != float("inf") else "N/A",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Totals ────────────────────────────────────────────────────────────────
    total_cost_sav = sum(a.get("total_cost_savings", 0) for a in ar_list)
    total_impl     = sum(a.get("implementation_cost", 0) for a in ar_list)
    total_elec_kwh = sum(
        r["savings"] for a in ar_list
        for r in a.get("resources", []) if r["type"] == "Electricity"
    )
    total_gas_mmbtu= sum(
        r["savings"] for a in ar_list
        for r in a.get("resources", []) if r["type"] == "Natural Gas"
    )
    avg_payback = total_impl / total_cost_sav if total_cost_sav > 0 else float("inf")

    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total ARs", len(ar_list))
    col2.metric("Total Cost Savings/yr", f"${total_cost_sav:,.0f}")
    col3.metric("Total Elec Savings", f"{total_elec_kwh:,.0f} kWh")
    col4.metric("Total Implementation", f"${total_impl:,.0f}")
    col5.metric("Avg. Payback", f"{avg_payback:.1f} yr" if avg_payback != float("inf") else "N/A")

    if total_gas_mmbtu > 0:
        st.metric("Total Gas Savings", f"{total_gas_mmbtu:,.1f} MMBtu/yr")

    # ── AR Detail Viewer ──────────────────────────────────────────────────────
    st.subheader("AR Details")
    for i, ar in enumerate(ar_list):
        with st.expander(f"AR {ar.get('ar_number','?')} — {ar.get('title','?')} (ARC {ar.get('arc_code','?')})"):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Observation:**\n\n{ar.get('observation','—')}")
            c2.markdown(f"**Recommendation:**\n\n{ar.get('recommendation','—')}")
            st.markdown(f"**Technology Description:**\n\n{ar.get('tech_description','—')}")

            # Cost metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Annual Cost Savings", f"${ar.get('total_cost_savings',0):,.0f}")
            col2.metric("Implementation Cost", f"${ar.get('implementation_cost',0):,.0f}")
            pb = ar.get("payback", float("inf"))
            col3.metric("Simple Payback", f"{pb:.1f} yr" if pb != float("inf") else "N/A")

            # Delete button
            if st.button(f"🗑 Remove {ar.get('ar_number','AR')}", key=f"del_ar_{i}"):
                ar_list.pop(i)
                st.session_state["ar_list"] = ar_list
                st.rerun()

    # ── Move AR Up/Down ───────────────────────────────────────────────────────
    st.subheader("Reorder ARs")
    st.caption("Change the order ARs will appear in the report.")
    for i, ar in enumerate(ar_list):
        col1, col2, col3 = st.columns([4, 0.5, 0.5])
        col1.write(f"{i+1}. {ar.get('ar_number','?')} — {ar.get('title','?')}")
        if col2.button("↑", key=f"up_{i}") and i > 0:
            ar_list[i-1], ar_list[i] = ar_list[i], ar_list[i-1]
            st.session_state["ar_list"] = ar_list
            st.rerun()
        if col3.button("↓", key=f"dn_{i}") and i < len(ar_list) - 1:
            ar_list[i+1], ar_list[i] = ar_list[i], ar_list[i+1]
            st.session_state["ar_list"] = ar_list
            st.rerun()
