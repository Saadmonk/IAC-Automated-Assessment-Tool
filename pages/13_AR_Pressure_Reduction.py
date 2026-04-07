"""
ARC 2.4239 — Reduce Compressed Air System Pressure
MEASUR-equivalent: Pressure Reduction Calculator
"""
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from arcs.arc_measur import pressure_reduction_savings, pressure_reduction_rule_of_thumb

st.set_page_config(page_title="ARC 2.4239 — Pressure Reduction", layout="wide")
init_session()

st.title("AR: Reduce Compressed Air Pressure (ARC 2.4239)")
st.caption("MEASUR-equivalent polytropic compression model. Every 2 psig reduction ≈ 1% power savings.")

# ── Defaults ─────────────────────────────────────────────────────────────────
defs = get_defaults("2.4239")

with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value="AR-1", key="pr_ar_num")
    obs = c1.text_area("Observation", value=st.session_state.get("pr_obs", defs["observation"]),
                       height=110, key="pr_obs")
    rec = c2.text_area("Recommendation", value=st.session_state.get("pr_rec", defs["recommendation"]),
                       height=110, key="pr_rec")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("pr_tech", defs["tech_description"]),
                        height=110, key="pr_tech")

st.subheader("Compressor System Parameters")
col1, col2, col3, col4 = st.columns(4)
hp          = col1.number_input("Compressor nameplate HP", value=50.0, step=5.0, key="pr_hp")
motor_eff   = col2.slider("Motor efficiency", 0.85, 0.97, 0.93, 0.01, key="pr_meff")
load_frac   = col3.slider("Average load fraction", 0.30, 1.00, 0.85, 0.01, key="pr_load")
run_hours   = col4.number_input("Annual run hours", value=4000.0, step=100.0, key="pr_hrs")

st.subheader("Pressure Settings")
col1, col2 = st.columns(2)
p_current  = col1.number_input("Current discharge pressure (psig)", value=110.0, step=5.0, key="pr_pcurr")
p_proposed = col2.number_input("Proposed pressure (psig)", value=100.0, step=5.0, key="pr_pprop")

if p_proposed >= p_current:
    st.warning("Proposed pressure must be lower than current pressure.")

rates = get_utility_rates()
c1, c2, c3 = st.columns(3)
elec_rate   = c1.number_input("Electricity rate ($/kWh)",
                               value=round(rates["elec_rate"],4) if rates["elec_rate"]>0 else 0.10,
                               step=0.001, format="%.4f", key="pr_er")
demand_rate = c2.number_input("Demand rate ($/kW/mo)", value=0.0, step=1.0, key="pr_dr")
impl_cost   = c3.number_input("Implementation Cost ($)", value=0.0, step=50.0, key="pr_impl",
                               help="Usually $0 — just a controls setpoint change.")

st.info("💡 Implementation is typically free — just adjusting the compressor pressure switch/setpoint. Verify all end uses operate at the reduced pressure first.")

# ── Calculation method ───────────────────────────────────────────────────────
method = st.radio("Calculation method", ["Polytropic (rigorous, MEASUR)", "Rule of thumb (2 psig = 1%)"],
                  horizontal=True, key="pr_method")

if st.button("Calculate Savings", type="primary", key="pr_calc") and p_proposed < p_current:
    if "Polytropic" in method:
        result = pressure_reduction_savings(
            hp, motor_eff, p_current, p_proposed, run_hours, load_frac, elec_rate, demand_rate
        )
    else:
        kw = hp * 0.7457 / motor_eff * load_frac
        result = pressure_reduction_rule_of_thumb(kw, p_current - p_proposed, run_hours, elec_rate)

    st.session_state["pr_result"] = result

if "pr_result" in st.session_state:
    r = st.session_state["pr_result"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Power", f"{r.get('kw_current', r.get('delta_kw',0)+r.get('kw_proposed',0)):.2f} kW")
    c2.metric("Power Savings", f"{r['delta_kw']:.2f} kW ({r.get('pct_power_savings',0):.1f}%)")
    c3.metric("Annual kWh Savings", f"{r['ann_kwh_savings']:,.0f} kWh")
    c4.metric("Annual Cost Savings", f"${r['ann_cost_savings']:,.0f}")
    payback = impl_cost / r["ann_cost_savings"] if r["ann_cost_savings"] > 0 else 0.0
    c5.metric("Payback", f"{payback:.1f} yr" if payback > 0 else "Immediate")

    with st.expander("Calculation Detail"):
        if "W_current" in r:
            st.markdown(f"""
- Current pressure ratio: {(p_current+14.696)/14.696:.3f} → polytropic work factor W = {r['W_current']:.4f}
- Proposed pressure ratio: {(p_proposed+14.696)/14.696:.3f} → polytropic work factor W = {r['W_proposed']:.4f}
- Power ratio: {r['power_ratio']:.4f} → **{r['pct_power_savings']:.2f}% power reduction**
- Power: {r['kw_current']:.2f} kW → {r.get('kw_proposed',0):.2f} kW = **{r['delta_kw']:.2f} kW saved**
- Annual savings: {r['delta_kw']:.2f} kW × {run_hours:.0f} hr = **{r['ann_kwh_savings']:,.0f} kWh/yr**
            """)
        else:
            st.markdown(f"Rule of thumb: {p_current-p_proposed:.0f} psig × 0.5%/psig = {r['pct_power_savings']:.1f}% reduction")

    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key="pr_save"):
        payback_val = impl_cost / r["ann_cost_savings"] if r["ann_cost_savings"] > 0 else 0.0
        ar_entry = {
            "arc_code": "2.4239",
            "ar_number": ar_num,
            "title": "Reduce Compressed Air System Pressure",
            "resources": [{"type": "Electricity", "savings": r["ann_kwh_savings"], "unit": "kWh"}],
            "total_cost_savings": r["ann_cost_savings"],
            "implementation_cost": impl_cost,
            "payback": payback_val,
            "observation": st.session_state.get("pr_obs",""),
            "recommendation": st.session_state.get("pr_rec",""),
            "tech_description": st.session_state.get("pr_tech",""),
            "calculation_details": r,
        }
        ar_list = [a for a in st.session_state.get("ar_list",[]) if not (a.get("arc_code")=="2.4239" and a.get("ar_number")==ar_num)]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ Saved. Total ARs: {len(ar_list)}")
