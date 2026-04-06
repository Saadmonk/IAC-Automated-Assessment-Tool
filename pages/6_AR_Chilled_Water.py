"""
ARC 2.2625 — Chilled Water Reset
CoolProp-based COP comparison: current vs. proposed CHWST
"""
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from arcs.arc_2_2625_chilled_water import compute_chilled_water_savings, coolprop_fluid_demo, COOLPROP_AVAILABLE

st.set_page_config(page_title="ARC 2.2625 — Chilled Water Reset", layout="wide")
init_session()

st.title("AR: Chilled Water Reset (ARC 2.2625)")
st.caption("Raise chilled water supply temperature (CHWST) during mild weather to improve chiller COP.")

if not COOLPROP_AVAILABLE:
    st.warning("⚠️ CoolProp not found. Install with `pip install CoolProp`. Using Carnot-based COP estimation only.")

# ── Narrative ────────────────────────────────────────────────────────────────
with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value=st.session_state.get("chw_ar_num", "AR-1"), key="chw_ar_num")
    obs = c1.text_area("Observation", value=st.session_state.get("chw_obs", ""),
                       height=100, key="chw_obs",
                       placeholder="Describe current chiller controls, fixed CHWST, load profile…")
    rec = c2.text_area("Recommendation", value=st.session_state.get("chw_rec", ""),
                       height=100, key="chw_rec",
                       placeholder="Recommend CHWST reset control strategy, expected reset range…")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("chw_tech", "Chilled water reset (CHWST reset) raises the chilled water supply temperature setpoint during periods of reduced cooling demand or mild outdoor conditions. As the evaporator temperature increases, the refrigeration cycle COP improves approximately 2–4% per °F of reset, reducing compressor electrical consumption."),
                        height=100, key="chw_tech")

# ── System Parameters ────────────────────────────────────────────────────────
st.subheader("Chiller System Parameters")
col1, col2, col3 = st.columns(3)
cooling_tons = col1.number_input("Average cooling load (tons)", value=100.0, step=5.0, key="chw_tons")
run_hours    = col2.number_input("Annual chiller run hours", value=2000.0, step=100.0, key="chw_hours")
cop_frac     = col3.slider("COP fraction of Carnot (0.5–0.7)", min_value=0.40, max_value=0.80, value=0.60, step=0.01, key="chw_cop_frac")

st.subheader("Temperature Setpoints")
col1, col2, col3 = st.columns(3)
t_current  = col1.number_input("Current CHWST (°F)", value=44.0, step=0.5, key="chw_t_curr")
t_proposed = col2.number_input("Proposed CHWST (°F)", value=48.0, step=0.5, key="chw_t_prop")
t_cond     = col3.number_input("Condenser leaving temp (°F)", value=95.0, step=1.0, key="chw_t_cond")

if t_proposed <= t_current:
    st.error("Proposed CHWST must be higher than current CHWST for savings.")

st.subheader("Rates")
rates = get_utility_rates()
col1, col2, col3, col4 = st.columns(4)
elec_rate_in  = col1.number_input("Electricity rate ($/kWh)",
                                   value=round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.10,
                                   step=0.001, format="%.4f", key="chw_elec_rate")
demand_rate_in= col2.number_input("Demand rate ($/kW/mo)", value=0.0, step=1.0, key="chw_demand_rate")
impl_cost     = col3.number_input("Implementation Cost ($)", value=5000.0, step=500.0, key="chw_impl_cost")
col4.write("")  # spacer

# ── Optional: CoolProp loop calculation ──────────────────────────────────────
with st.expander("CoolProp Loop Verification (optional)"):
    st.markdown("Verify loop heat transfer using CoolProp fluid properties.")
    cp_col1, cp_col2, cp_col3 = st.columns(3)
    cp_fluid   = cp_col1.selectbox("Fluid", ["Water", "EthyleneGlycol", "MPG", "MEG"], key="chw_fluid")
    cp_t_supply= cp_col2.number_input("Supply temp (°C)", value=7.0, step=0.5, key="chw_cp_tsup")
    cp_t_return= cp_col3.number_input("Return temp (°C)", value=12.0, step=0.5, key="chw_cp_tret")
    cp_flow    = cp_col1.number_input("Flow rate (L/s)", value=5.0, step=0.5, key="chw_cp_flow")
    if st.button("Calculate Loop Load", key="chw_cp_calc"):
        if COOLPROP_AVAILABLE:
            loop = coolprop_fluid_demo(cp_fluid, cp_t_supply, cp_t_return, cp_flow)
            if "error" not in loop:
                st.success(f"**Loop load: {loop['Q_kw']:.1f} kW ({loop['Q_tons']:.1f} tons)**")
                st.markdown(f"Flow = {loop['flow_kg_s']:.2f} kg/s | ρ_avg = {loop['rho_avg']:.1f} kg/m³ | Cp_avg = {loop['Cp_avg']:.0f} J/kg·K | ΔT = {loop['delta_T']}°C")
            else:
                st.error(loop["error"])
        else:
            st.error("CoolProp not available.")

# ── Calculate ────────────────────────────────────────────────────────────────
if st.button("Calculate Savings", type="primary", key="chw_calc") and t_proposed > t_current:
    result = compute_chilled_water_savings(
        cooling_load_tons=cooling_tons,
        hours_operation=run_hours,
        T_chws_current_F=t_current,
        T_chws_proposed_F=t_proposed,
        T_condenser_F=t_cond,
        cop_fraction=cop_frac,
        elec_rate=elec_rate_in,
        demand_rate=demand_rate_in,
    )
    st.session_state["chw_result"] = result
    st.session_state["chw_impl_used"] = impl_cost

if "chw_result" in st.session_state:
    result = st.session_state["chw_result"]
    impl_used = st.session_state.get("chw_impl_used", impl_cost)

    st.subheader("Results")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current COP", f"{result['cop_current']:.2f}")
    c2.metric("Proposed COP", f"{result['cop_proposed']:.2f}")
    c3.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
    c4.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
    payback = impl_used / result["ann_cost_savings"] if result["ann_cost_savings"] > 0 else float("inf")
    c5.metric("Simple Payback", f"{payback:.1f} yr" if payback != float("inf") else "N/A")

    st.markdown(f"""
    **Calculation Summary:**
    - Current CHWST = **{t_current}°F** ({result['T_evap_curr_C']:.1f}°C) → COP = **{result['cop_current']:.3f}**
    - Proposed CHWST = **{t_proposed}°F** ({result['T_evap_prop_C']:.1f}°C) → COP = **{result['cop_proposed']:.3f}**
    - Condenser temp = **{t_cond}°F** ({result['T_cond_C']:.1f}°C)
    - Chiller load = **{cooling_tons} tons** × 3.517 kW/ton = {cooling_tons*3.517:.1f} kW cooling
    - Power reduction: {result['kw_current']:.2f} kW → {result['kw_proposed']:.2f} kW = **{result['delta_kw']:.2f} kW savings**
    - Annual savings: {result['delta_kw']:.2f} kW × {run_hours:.0f} hr = **{result['ann_kwh_savings']:,.0f} kWh/yr**
    """)

    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key="chw_save"):
        ar_entry = {
            "arc_code": "2.2625",
            "ar_number": ar_num,
            "title": "Chilled Water Reset",
            "resources": [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}],
            "total_cost_savings": result["ann_cost_savings"],
            "implementation_cost": impl_used,
            "payback": payback,
            "observation": st.session_state.get("chw_obs", ""),
            "recommendation": st.session_state.get("chw_rec", ""),
            "tech_description": st.session_state.get("chw_tech", ""),
            "calculation_details": result,
        }
        ar_list = st.session_state.get("ar_list", [])
        ar_list = [a for a in ar_list if a.get("arc_code") != "2.2625" or a.get("ar_number") != ar_num]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ {ar_num} saved. Total ARs: {len(ar_list)}")
