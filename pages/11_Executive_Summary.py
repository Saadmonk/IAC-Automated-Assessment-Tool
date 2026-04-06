"""
Section 1: Executive Summary
Auto-assembled from billing data + AR list.
"""
import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates

st.set_page_config(page_title="Executive Summary", layout="wide")
init_session()

st.title("Section 1 — Executive Summary")
st.caption("Auto-assembled from Utility Billing (Section 2.6) and saved ARs.")

rates = get_utility_rates()
ar_list = st.session_state.get("ar_list", [])

# ── 1.1 Annual Utility Usage & Cost ──────────────────────────────────────────
st.subheader("1.1  Annual Utility Usage and Cost")

elec_rows  = st.session_state.get("elec_rows", [])
gas_rows   = st.session_state.get("gas_rows", [])
water_rows = st.session_state.get("water_rows", [])

ann_kwh   = rates.get("ann_kwh", 0)
ann_kw    = max(r.get("kw", 0) for r in elec_rows) if elec_rows else 0
ann_ec    = rates.get("ann_elec_cost", 0)
ann_dc    = rates.get("ann_demand_cost", 0)
ann_efee  = rates.get("ann_elec_fee", 0)
ann_elec_total = ann_ec + ann_dc + ann_efee

ann_mmbtu = rates.get("ann_mmbtu", 0)
ann_gc    = rates.get("ann_gas_cost", 0)
ann_gfee  = rates.get("ann_gas_fee", 0)
ann_gas_total = ann_gc + ann_gfee

ann_tgal  = rates.get("ann_tgal", 0)
ann_wc    = rates.get("ann_water_cost", 0)
ann_sc    = rates.get("ann_sewer_cost", 0)
ann_wfee  = rates.get("ann_water_fee", 0)
ann_water_total = ann_wc + ann_sc + ann_wfee

total_util = ann_elec_total + ann_gas_total + ann_water_total

# Build table in MALT IAC format
utility_data = []

if ann_kwh > 0:
    utility_data.append({
        "Utility": "Electricity",
        "Consumption": f"{ann_kwh:,.0f} kWh",
        "Peak Demand": f"{ann_kw:,.0f} kW",
        "Energy Cost": f"${ann_ec:,.0f}",
        "Demand Cost": f"${ann_dc:,.0f}",
        "Other Fees": f"${ann_efee:,.0f}",
        "Total Cost": f"${ann_elec_total:,.0f}",
    })

if st.session_state.get("has_gas", True) and ann_mmbtu > 0:
    utility_data.append({
        "Utility": "Natural Gas",
        "Consumption": f"{ann_mmbtu:,.1f} MMBtu",
        "Peak Demand": "—",
        "Energy Cost": f"${ann_gc:,.0f}",
        "Demand Cost": "—",
        "Other Fees": f"${ann_gfee:,.0f}",
        "Total Cost": f"${ann_gas_total:,.0f}",
    })

if st.session_state.get("has_water", True) and ann_tgal > 0:
    utility_data.append({
        "Utility": "Water/Sewer",
        "Consumption": f"{ann_tgal:,.3f} Tgal",
        "Peak Demand": "—",
        "Energy Cost": f"${ann_wc+ann_sc:,.0f}",
        "Demand Cost": "—",
        "Other Fees": f"${ann_wfee:,.0f}",
        "Total Cost": f"${ann_water_total:,.0f}",
    })

if utility_data:
    utility_data.append({
        "Utility": "**TOTAL**",
        "Consumption": "—",
        "Peak Demand": "—",
        "Energy Cost": "—",
        "Demand Cost": "—",
        "Other Fees": "—",
        "Total Cost": f"**${total_util:,.0f}**",
    })
    df_util = pd.DataFrame(utility_data)
    st.dataframe(df_util, use_container_width=True, hide_index=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Annual Electricity Use", f"{ann_kwh:,.0f} kWh")
    col2.metric("Total Utility Cost", f"${total_util:,.0f}/yr")
    if ann_mmbtu > 0:
        col3.metric("Annual Gas Use", f"{ann_mmbtu:,.1f} MMBtu")
else:
    st.info("No utility billing data entered yet. Go to **Utility Billing** to enter 12-month data.")

# ── 1.2 Summary of Recommendations ──────────────────────────────────────────
st.subheader("1.2  Summary of Recommended Energy-Saving Measures")

if not ar_list:
    st.info("No ARs saved yet. Complete the ARC input pages and click **Save AR to Report**.")
else:
    rows = []
    total_elec_sav = 0
    total_gas_sav  = 0
    total_cost_sav = 0
    total_impl     = 0

    for i, ar in enumerate(ar_list):
        elec_sav = sum(r["savings"] for r in ar.get("resources",[]) if r["type"]=="Electricity")
        gas_sav  = sum(r["savings"] for r in ar.get("resources",[]) if r["type"]=="Natural Gas")
        cost_sav = ar.get("total_cost_savings", 0)
        impl     = ar.get("implementation_cost", 0)
        pb       = ar.get("payback", float("inf"))
        total_elec_sav += elec_sav
        total_gas_sav  += gas_sav
        total_cost_sav += cost_sav
        total_impl     += impl

        res_parts = []
        if elec_sav > 0: res_parts.append(f"{elec_sav:,.0f} kWh")
        if gas_sav  > 0: res_parts.append(f"{gas_sav:,.1f} MMBtu")

        rows.append({
            "AR #": ar.get("ar_number","—"),
            "ARC": ar.get("arc_code","—"),
            "Recommendation": ar.get("title","—"),
            "Resource Savings": "\n".join(res_parts) if res_parts else "—",
            "Cost Savings ($/yr)": f"${cost_sav:,.0f}",
            "Impl. Cost ($)": f"${impl:,.0f}",
            "Payback (yr)": f"{pb:.1f}" if pb != float("inf") else "N/A",
        })

    avg_pb = total_impl / total_cost_sav if total_cost_sav > 0 else float("inf")
    rows.append({
        "AR #": "—",
        "ARC": "—",
        "Recommendation": "**TOTALS**",
        "Resource Savings": f"Elec: {total_elec_sav:,.0f} kWh" + (f"\nGas: {total_gas_sav:,.1f} MMBtu" if total_gas_sav > 0 else ""),
        "Cost Savings ($/yr)": f"**${total_cost_sav:,.0f}**",
        "Impl. Cost ($)": f"**${total_impl:,.0f}**",
        "Payback (yr)": f"**{avg_pb:.1f}**" if avg_pb != float("inf") else "—",
    })

    df_ar = pd.DataFrame(rows)
    st.dataframe(df_ar, use_container_width=True, hide_index=True)

    # Key metrics
    pct_savings = total_cost_sav / total_util * 100 if total_util > 0 else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Annual Savings", f"${total_cost_sav:,.0f}")
    col2.metric("Total Implementation Cost", f"${total_impl:,.0f}")
    col3.metric("Average Payback", f"{avg_pb:.1f} yr" if avg_pb != float("inf") else "N/A")
    col4.metric("Savings as % of Utility Bill", f"{pct_savings:.1f}%")

    # ── Savings Breakdown Chart ────────────────────────────────────────────
    import plotly.graph_objects as go
    fig = go.Figure(go.Bar(
        x=[ar.get("ar_number","?") for ar in ar_list],
        y=[ar.get("total_cost_savings",0) for ar in ar_list],
        text=[f"${ar.get('total_cost_savings',0):,.0f}" for ar in ar_list],
        textposition="auto",
        marker_color="#2E86AB",
    ))
    fig.update_layout(
        title="Annual Cost Savings by Recommendation",
        xaxis_title="AR Number",
        yaxis_title="Annual Cost Savings ($/yr)",
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Narrative Summary ─────────────────────────────────────────────────────
st.subheader("Narrative Summary")
if ar_list and total_util > 0:
    loc = st.session_state.get("location", "the facility")
    report_num = st.session_state.get("report_number", "")
    visit_date = st.session_state.get("site_visit_date", "")
    narrative = (
        f"The MALT IAC team conducted an energy assessment of {loc} on {visit_date}. "
        f"A total of {len(ar_list)} energy-saving recommendation{'s' if len(ar_list)!=1 else ''} {'were' if len(ar_list)!=1 else 'was'} identified "
        f"with a combined annual savings potential of **${total_cost_sav:,.0f}**. "
    )
    if total_elec_sav > 0:
        narrative += f"Annual electricity savings are estimated at **{total_elec_sav:,.0f} kWh** "
    if total_gas_sav > 0:
        narrative += f"and natural gas savings at **{total_gas_sav:,.1f} MMBtu**. "
    narrative += (
        f"The total estimated implementation cost is **${total_impl:,.0f}** "
        f"with an average simple payback period of **{avg_pb:.1f} years**. "
        f"These savings represent approximately **{pct_savings:.1f}%** of the facility's total annual utility cost of **${total_util:,.0f}**."
    )
    st.markdown(narrative)
    st.session_state["exec_narrative"] = narrative
