"""
ARC 2.4146 — Install VFD on Motors
Affinity laws — power scales as cube of speed ratio
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from arcs.arc_2_4146_vfd import compute_vfd_savings

st.set_page_config(page_title="ARC 2.4146 — VFD", layout="wide")
init_session()

st.title("AR: Variable Frequency Drive (ARC 2.4146)")
st.caption("Apply affinity laws to estimate energy savings from adding VFDs to motor-driven equipment.")

_defs = get_defaults("2.4146")

with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value=st.session_state.get("vfd_ar_num","AR-1"), key="vfd_ar_num")
    obs = c1.text_area("Observation", value=st.session_state.get("vfd_obs", _defs["observation"]), height=100, key="vfd_obs")
    rec = c2.text_area("Recommendation", value=st.session_state.get("vfd_rec", _defs["recommendation"]), height=100, key="vfd_rec")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("vfd_tech", _defs["tech_description"]),
                        height=100, key="vfd_tech")

rates = get_utility_rates()
col1, col2, col3 = st.columns(3)
elec_rate_in  = col1.number_input("Electricity rate ($/kWh)", value=round(rates["elec_rate"],4) if rates["elec_rate"]>0 else 0.10, step=0.001, format="%.4f", key="vfd_elec")
demand_rate_in= col2.number_input("Demand rate ($/kW/mo)", value=0.0, step=1.0, key="vfd_demand")

# ── Affinity Law Preview ─────────────────────────────────────────────────────
with st.expander("Affinity Law Calculator"):
    spd_pct = st.slider("Speed reduction (%)", 5, 50, 20)
    spd_frac = 1 - spd_pct / 100
    pwr_reduction = (1 - spd_frac**3) * 100
    st.metric(f"Power reduction at {100-spd_pct}% speed", f"{pwr_reduction:.1f}%")
    # Plot
    speeds = np.linspace(0.5, 1.0, 100)
    powers = speeds ** 3
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=(1-speeds)*100, y=(1-powers)*100, mode="lines", line=dict(color="#4A90D9", width=2)))
    fig.update_layout(xaxis_title="Speed Reduction (%)", yaxis_title="Power Reduction (%)",
                      height=300, margin=dict(t=20, b=40))
    st.plotly_chart(fig, use_container_width=True)

# ── Motor Table ──────────────────────────────────────────────────────────────
st.subheader("Motor Inventory")
if "vfd_motors" not in st.session_state:
    st.session_state["vfd_motors"] = [
        {"description": "Supply Air Fan", "hp": 20.0, "motor_eff": 0.92, "run_hours": 4000.0, "speed_fraction": 0.80, "current_kw": 0.0},
    ]

motors = st.session_state["vfd_motors"]
col_h = st.columns([3, 1.2, 1.2, 1.5, 1.5, 1.5, 0.5])
col_h[0].markdown("**Description**")
col_h[1].markdown("**HP**")
col_h[2].markdown("**Motor Eff**")
col_h[3].markdown("**Run Hrs/yr**")
col_h[4].markdown("**Speed Frac**")
col_h[5].markdown("**Curr kW** (if known)")

for i, m in enumerate(motors):
    cols = st.columns([3, 1.2, 1.2, 1.5, 1.5, 1.5, 0.5])
    m["description"]  = cols[0].text_input("d", value=m["description"], key=f"vfd_desc_{i}", label_visibility="collapsed")
    m["hp"]           = cols[1].number_input("hp", value=float(m["hp"]), min_value=0.0, step=1.0, key=f"vfd_hp_{i}", label_visibility="collapsed")
    m["motor_eff"]    = cols[2].number_input("eff", value=float(m["motor_eff"]), min_value=0.5, max_value=1.0, step=0.01, key=f"vfd_eff_{i}", label_visibility="collapsed")
    m["run_hours"]    = cols[3].number_input("hr", value=float(m["run_hours"]), min_value=0.0, step=100.0, key=f"vfd_hr_{i}", label_visibility="collapsed")
    m["speed_fraction"]= cols[4].number_input("spd", value=float(m["speed_fraction"]), min_value=0.3, max_value=1.0, step=0.01, key=f"vfd_spd_{i}", label_visibility="collapsed")
    m["current_kw"]   = cols[5].number_input("kw", value=float(m["current_kw"]), min_value=0.0, step=0.5, key=f"vfd_kw_{i}", label_visibility="collapsed")
    if cols[6].button("✕", key=f"vfd_del_{i}") and len(motors) > 1:
        motors.pop(i)
        st.rerun()

if st.button("＋ Add Motor", key="vfd_add"):
    motors.append({"description": "", "hp": 10.0, "motor_eff": 0.92, "run_hours": 2000.0, "speed_fraction": 0.80, "current_kw": 0.0})
    st.rerun()
st.session_state["vfd_motors"] = motors

impl_cost = st.number_input("Total Implementation Cost ($)", value=5000.0, step=500.0, key="vfd_impl")

if st.button("Calculate VFD Savings", type="primary", key="vfd_calc"):
    result = compute_vfd_savings(motors, elec_rate_in, demand_rate_in)
    st.session_state["vfd_result"] = result

if "vfd_result" in st.session_state:
    r = st.session_state["vfd_result"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Demand Reduction", f"{r['total_delta_kw']:.2f} kW")
    c2.metric("Annual kWh Savings", f"{r['ann_kwh_savings']:,.0f} kWh")
    c3.metric("Annual Cost Savings", f"${r['ann_cost_savings']:,.0f}")
    payback = impl_cost / r["ann_cost_savings"] if r["ann_cost_savings"] > 0 else float("inf")
    c4.metric("Simple Payback", f"{payback:.1f} yr" if payback != float("inf") else "N/A")

    df = pd.DataFrame([{
        "Motor": m.get("description",""),
        "HP": m.get("hp",0),
        "kW before": round(m.get("kw_before",0),2),
        "Speed": f"{m.get('speed_fraction',0)*100:.0f}%",
        "kW after": round(m.get("kw_after",0),2),
        "ΔkW": round(m.get("delta_kw",0),2),
        "Ann kWh": round(m.get("ann_kwh_savings",0),0),
        "Cost Savings": f"${m.get('cost_savings',0):,.0f}",
    } for m in r["motors"]])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key="vfd_save"):
        ar_entry = {
            "arc_code": "2.4146",
            "ar_number": ar_num,
            "title": "Install Variable Frequency Drives",
            "resources": [{"type": "Electricity", "savings": r["ann_kwh_savings"], "unit": "kWh"}],
            "total_cost_savings": r["ann_cost_savings"],
            "implementation_cost": impl_cost,
            "payback": payback,
            "observation": st.session_state.get("vfd_obs",""),
            "recommendation": st.session_state.get("vfd_rec",""),
            "tech_description": st.session_state.get("vfd_tech",""),
            "calculation_details": r,
        }
        ar_list = st.session_state.get("ar_list", [])
        ar_list = [a for a in ar_list if a.get("arc_code") != "2.4146" or a.get("ar_number") != ar_num]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ {ar_num} saved. Total ARs: {len(ar_list)}")
