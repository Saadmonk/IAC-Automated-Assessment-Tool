"""
Chiller COP Analysis
Measures actual chiller COP vs Carnot COP using three input modes.
Also calculates energy savings from setpoint improvements that raise COP.
"""
import streamlit as st
import sys, os
import pandas as pd
import plotly.graph_objects as go
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from arcs.arc_2_chiller_cop import (
    cop_from_pressures,
    cop_from_water_temps,
    cop_from_kw,
    chiller_setpoint_savings,
    REFRIGERANTS,
)

NAVY = "#003366"

st.set_page_config(page_title="Chiller COP Analysis", layout="wide")
init_session()

st.title("Chiller COP Analysis")
st.caption(
    "**COP_actual** = cooling capacity ÷ compressor power | "
    "**COP_Carnot** = T_evap / (T_cond − T_evap) [Kelvin] — theoretical maximum | "
    "**2nd-law efficiency** = COP_actual / COP_Carnot × 100%"
)

st.info(
    "This page measures existing chiller performance. "
    "To calculate savings from CHWST reset or setpoint changes, "
    "enter current and proposed COP in the **Setpoint Change Savings** section below."
)

rates = get_utility_rates()

# ─────────────────────────────────────────────────────────────────────────────
# Input Mode Selection
# ─────────────────────────────────────────────────────────────────────────────
mode = st.radio(
    "Select available measurements:",
    options=[
        "Mode A — Refrigerant pressures (suction + discharge gauge)",
        "Mode B — Water temperatures (CHW supply/return + condenser water)",
        "Mode C — Compressor kW + chilled water flow",
    ],
    key="cop_mode",
)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# MODE A — Refrigerant Pressures
# ─────────────────────────────────────────────────────────────────────────────
if mode.startswith("Mode A"):
    st.subheader("Mode A — Refrigerant Pressure Inputs")

    col1, col2 = st.columns(2)
    ref_name_a = col1.selectbox(
        "Refrigerant",
        options=list(REFRIGERANTS.keys()),
        key="cop_a_ref",
    )
    col2.markdown("")  # spacer

    col1, col2, col3 = st.columns(3)
    suction_psig = col1.number_input(
        "Suction pressure (psig)",
        value=65.0,
        min_value=0.0,
        step=1.0,
        key="cop_a_suction",
    )
    discharge_psig = col2.number_input(
        "Discharge pressure (psig)",
        value=220.0,
        min_value=0.0,
        step=1.0,
        key="cop_a_discharge",
    )
    isen_eff_a = col3.number_input(
        "Isentropic efficiency (%)",
        value=70.0,
        min_value=30.0,
        max_value=95.0,
        step=1.0,
        key="cop_a_isen",
    )

    col1, col2 = st.columns(2)
    superheat_a = col1.number_input(
        "Superheat (°F)",
        value=10.0,
        min_value=0.0,
        max_value=40.0,
        step=1.0,
        key="cop_a_sh",
    )
    subcooling_a = col2.number_input(
        "Subcooling (°F)",
        value=5.0,
        min_value=0.0,
        max_value=30.0,
        step=1.0,
        key="cop_a_sc",
    )

    cop_inputs_a = dict(
        refrigerant_name=ref_name_a,
        suction_pressure_psig=suction_psig,
        discharge_pressure_psig=discharge_psig,
        isentropic_efficiency=isen_eff_a / 100.0,
        superheat_f=superheat_a,
        subcooling_f=subcooling_a,
    )

# ─────────────────────────────────────────────────────────────────────────────
# MODE B — Water Temperatures
# ─────────────────────────────────────────────────────────────────────────────
elif mode.startswith("Mode B"):
    st.subheader("Mode B — Water Temperature Inputs")

    col1, col2, col3 = st.columns(3)
    chw_supply_b = col1.number_input("CHW supply temp (°F)", value=44.0, step=0.5, key="cop_b_chws")
    chw_return_b = col2.number_input("CHW return temp (°F)", value=54.0, step=0.5, key="cop_b_chwr")
    chw_flow_b = col3.number_input("CHW flow rate (GPM)", value=500.0, min_value=1.0, step=10.0, key="cop_b_gpm")

    col1, col2 = st.columns(2)
    cond_supply_b = col1.number_input(
        "Condenser water supply (entering, °F)",
        value=85.0, step=0.5, key="cop_b_cws",
    )
    cond_return_b = col2.number_input(
        "Condenser water return (leaving, °F)",
        value=95.0, step=0.5, key="cop_b_cwr",
    )

    col1, col2 = st.columns(2)
    ref_name_b = col1.selectbox(
        "Refrigerant (optional — improves COP accuracy)",
        options=["— None —"] + list(REFRIGERANTS.keys()),
        key="cop_b_ref",
    )
    isen_eff_b = col2.number_input(
        "Isentropic efficiency (%)",
        value=70.0,
        min_value=30.0,
        max_value=95.0,
        step=1.0,
        key="cop_b_isen",
    )

    cop_inputs_b = dict(
        chw_supply_f=chw_supply_b,
        chw_return_f=chw_return_b,
        chw_flow_gpm=chw_flow_b,
        cond_supply_f=cond_supply_b,
        cond_return_f=cond_return_b,
        refrigerant_name=None if ref_name_b == "— None —" else ref_name_b,
        isentropic_efficiency=isen_eff_b / 100.0,
    )

# ─────────────────────────────────────────────────────────────────────────────
# MODE C — Compressor kW + CHW Flow
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.subheader("Mode C — Compressor kW + Chilled Water Flow Inputs")

    col1, col2, col3 = st.columns(3)
    comp_kw_c = col1.number_input(
        "Compressor kW (measured)",
        value=150.0,
        min_value=0.1,
        step=1.0,
        key="cop_c_kw",
    )
    chw_supply_c = col2.number_input("CHW supply temp (°F)", value=44.0, step=0.5, key="cop_c_chws")
    chw_return_c = col3.number_input("CHW return temp (°F)", value=54.0, step=0.5, key="cop_c_chwr")

    col1, col2 = st.columns(2)
    chw_flow_c = col1.number_input("CHW flow rate (GPM)", value=500.0, min_value=1.0, step=10.0, key="cop_c_gpm")
    cond_return_c = col2.number_input(
        "Condenser water return temp (°F, optional — enter 0 to skip)",
        value=95.0,
        min_value=0.0,
        step=0.5,
        key="cop_c_cwr",
        help="Used for Carnot COP calculation. Leave 0 to auto-estimate.",
    )

    cop_inputs_c = dict(
        compressor_kw=comp_kw_c,
        chw_supply_f=chw_supply_c,
        chw_return_f=chw_return_c,
        chw_flow_gpm=chw_flow_c,
        cond_return_f=cond_return_c if cond_return_c > 0 else None,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Calculate COP Button
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
if st.button("⚙️ Calculate COP", type="primary", key="cop_calc"):
    try:
        if mode.startswith("Mode A"):
            result = cop_from_pressures(**cop_inputs_a)
        elif mode.startswith("Mode B"):
            result = cop_from_water_temps(**cop_inputs_b)
        else:
            result = cop_from_kw(**cop_inputs_c)

        if "error" in result:
            st.error(f"Calculation error: {result['error']}")
        else:
            st.session_state["cop_result"] = result
            # Store compressor kW for savings section pre-fill
            if mode.startswith("Mode C"):
                st.session_state["cop_comp_kw_measured"] = comp_kw_c
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Results — 4 Metric Cards + Gauge
# ─────────────────────────────────────────────────────────────────────────────
if "cop_result" in st.session_state:
    r = st.session_state["cop_result"]

    st.subheader("COP Results")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("COP Actual", f"{r['cop_actual']:.3f}")
    c2.metric("COP Carnot", f"{r['cop_carnot']:.3f}")
    c3.metric("2nd Law Efficiency", f"{r['second_law_efficiency']:.1f}%")
    cooling_tons = r.get("q_cooling_tons", 0)
    c4.metric("Cooling Capacity", f"{cooling_tons:.1f} tons" if cooling_tons else "—")

    # Gauge chart
    sl_eff = r["second_law_efficiency"]
    gauge_color = "#4A90D9" if sl_eff >= 60 else ("#FFA500" if sl_eff >= 45 else "#D9534F")
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=sl_eff,
        number={"suffix": "%"},
        delta={"reference": 60, "increasing": {"color": "#2ECC71"}, "decreasing": {"color": "#E74C3C"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": gauge_color},
            "steps": [
                {"range": [0, 40], "color": "#FDECEA"},
                {"range": [40, 60], "color": "#FFF3CD"},
                {"range": [60, 80], "color": "#D4EDDA"},
                {"range": [80, 100], "color": "#C3E6CB"},
            ],
            "threshold": {
                "line": {"color": NAVY, "width": 3},
                "thickness": 0.75,
                "value": 60,
            },
        },
        title={"text": "2nd Law Efficiency (% of Carnot)"},
    ))
    fig_gauge.update_layout(height=300, margin=dict(t=40, b=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Mode A: state-point table
    if r.get("mode", "").startswith("A") and "h1_btu_lb" in r:
        st.subheader("Vapor Compression Cycle State Points")
        sp_df = pd.DataFrame([
            {"State": "1 — Compressor inlet (superheated vapor)", "h (BTU/lb)": r["h1_btu_lb"], "Notes": f"Suction sat. temp = {r.get('suction_sat_temp_f',0):.1f}°F + {cop_inputs_a.get('superheat_f',10):.0f}°F superheat"},
            {"State": "2 — Compressor exit (actual)", "h (BTU/lb)": r["h2_btu_lb"], "Notes": f"W_comp = {r.get('w_comp_btu_lb',0):.2f} BTU/lb"},
            {"State": "3 — Condenser exit (subcooled liquid)", "h (BTU/lb)": r["h3_btu_lb"], "Notes": f"Condensing sat. temp = {r.get('discharge_sat_temp_f',0):.1f}°F − {cop_inputs_a.get('subcooling_f',5):.0f}°F subcooling"},
            {"State": "4 — Expansion valve exit", "h (BTU/lb)": r["h4_btu_lb"], "Notes": "Isenthalpic expansion (h4 = h3)"},
        ])
        st.dataframe(sp_df, use_container_width=True, hide_index=True)
        st.caption(
            f"Cooling effect (q_evap) = h1 − h4 = {r.get('q_evap_btu_lb',0):.2f} BTU/lb | "
            f"Compressor work = h2 − h1 = {r.get('w_comp_btu_lb',0):.2f} BTU/lb"
        )

    # Note for Mode B
    if r.get("note"):
        st.info(f"ℹ️ {r['note']}")

    # ─────────────────────────────────────────────────────────────────────────
    # Setpoint Change Savings
    # ─────────────────────────────────────────────────────────────────────────
    st.divider()
    with st.expander("💡 Setpoint Change Savings — Calculate kWh & Cost Reduction", expanded=False):
        st.markdown(
            "Enter the current (existing) COP and a proposed COP from a setpoint or operational improvement. "
            "The calculator determines compressor kW reduction and annual cost savings."
        )

        sc1, sc2 = st.columns(2)
        cop_current_in = sc1.number_input(
            "Current COP (auto-filled)",
            value=float(r["cop_actual"]),
            min_value=0.1,
            step=0.1,
            format="%.3f",
            key="cop_sav_current",
        )
        cop_proposed_in = sc2.number_input(
            "Proposed COP",
            value=float(r["cop_actual"]) * 1.10,  # 10% improvement as starting default
            min_value=0.1,
            step=0.1,
            format="%.3f",
            key="cop_sav_proposed",
        )

        sc3, sc4 = st.columns(2)
        # Pre-fill kW from Mode C measurement if available
        kw_prefill = st.session_state.get("cop_comp_kw_measured", 100.0)
        comp_kw_in = sc3.number_input(
            "Compressor kW (current)",
            value=float(kw_prefill),
            min_value=0.1,
            step=1.0,
            key="cop_sav_kw",
            help="Auto-filled from Mode C measurement; enter manually for Modes A & B",
        )
        op_hours_in = sc4.number_input(
            "Operating hours / year",
            value=4000.0,
            min_value=100.0,
            max_value=8760.0,
            step=100.0,
            key="cop_sav_hours",
        )

        sc5, sc6 = st.columns(2)
        elec_rate_sav = sc5.number_input(
            "Electricity rate ($/kWh)",
            value=round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.10,
            step=0.001,
            format="%.4f",
            key="cop_sav_elec",
        )
        demand_rate_sav = sc6.number_input(
            "Demand rate ($/kW/mo)",
            value=round(rates["demand_rate"], 2) if rates["demand_rate"] > 0 else 0.0,
            step=1.0,
            key="cop_sav_demand",
        )

        impl_cost_cop = st.number_input(
            "Implementation cost ($)",
            value=5000.0,
            step=500.0,
            key="cop_sav_impl",
            help="Cost for setpoint control upgrades (often $0 if BAS-based)",
        )
        ar_num_cop = st.text_input(
            "AR Number",
            value=st.session_state.get("cop_ar_num", "AR-COP"),
            key="cop_ar_num",
        )

        if st.button("Calculate Savings", type="primary", key="cop_sav_calc"):
            try:
                sav = chiller_setpoint_savings(
                    cop_current=cop_current_in,
                    cop_proposed=cop_proposed_in,
                    compressor_kw_current=comp_kw_in,
                    operating_hours=op_hours_in,
                    elec_rate=elec_rate_sav,
                    demand_rate=demand_rate_sav,
                    demand_months=12,
                )
                st.session_state["cop_sav_result"] = sav
            except Exception as e:
                st.error(f"Savings calculation error: {e}")

        if "cop_sav_result" in st.session_state:
            sav = st.session_state["cop_sav_result"]

            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Cooling Load", f"{sav['cooling_load_tons']:.1f} tons")
            s2.metric("kW Reduction", f"{sav['delta_kw']:.1f} kW ({sav['pct_reduction']:.1f}%)")
            s3.metric("Annual kWh Saved", f"{sav['ann_kwh_savings']:,.0f} kWh")
            s4.metric("Annual Cost Saved", f"${sav['ann_cost_savings']:,.0f}")
            payback_cop = impl_cost_cop / sav["ann_cost_savings"] if sav["ann_cost_savings"] > 0 else float("inf")
            s5.metric(
                "Simple Payback",
                f"{payback_cop:.1f} yr" if payback_cop != float("inf") else "N/A",
            )

            if st.button("💾 Save this AR to Report", type="primary", key="cop_save"):
                ar_entry = {
                    "arc_code": "COP",
                    "ar_number": ar_num_cop,
                    "title": "Chiller COP Improvement — Setpoint Reset",
                    "resources": [
                        {"type": "Electricity", "savings": sav["ann_kwh_savings"], "unit": "kWh"},
                    ],
                    "total_cost_savings": sav["ann_cost_savings"],
                    "implementation_cost": impl_cost_cop,
                    "payback": payback_cop,
                    "observation": f"Measured COP = {r['cop_actual']:.3f} ({r['second_law_efficiency']:.1f}% of Carnot).",
                    "recommendation": (
                        f"Raise chilled water supply temperature setpoint to improve chiller COP "
                        f"from {cop_current_in:.3f} to {cop_proposed_in:.3f}."
                    ),
                    "tech_description": (
                        "COP improvement calculated from compressor power reduction: "
                        "Q_cooling = kW_current × COP_current; "
                        "kW_proposed = Q_cooling / COP_proposed; "
                        "ΔkW = kW_current − kW_proposed."
                    ),
                    "calculation_details": {**sav, "cop_result": r},
                }
                ar_list = st.session_state.get("ar_list", [])
                ar_list = [
                    a for a in ar_list
                    if not (a.get("arc_code") == "COP" and a.get("ar_number") == ar_num_cop)
                ]
                ar_list.append(ar_entry)
                st.session_state["ar_list"] = ar_list
                st.success(f"✅ {ar_num_cop} saved. Total ARs: {len(ar_list)}")



