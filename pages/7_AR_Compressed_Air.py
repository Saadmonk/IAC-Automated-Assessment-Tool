"""
ARC 2.4236 — Fix Compressed Air Leaks
"""
import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from arcs.arc_2_4236_compressed_air import compute_leak_savings, leak_flow_cfm

st.set_page_config(page_title="ARC 2.4236 — Compressed Air Leaks", layout="wide")
init_session()

st.title("AR: Fix Compressed Air Leaks (ARC 2.4236)")
st.caption("Estimate compressor energy wasted through unrepaired leaks using orifice flow equations.")

with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value=st.session_state.get("ca_ar_num","AR-1"), key="ca_ar_num")
    obs = c1.text_area("Observation", value=st.session_state.get("ca_obs",""), height=100, key="ca_obs",
                       placeholder="Number of leaks found, survey method (ultrasonic detector), locations…")
    rec = c2.text_area("Recommendation", value=st.session_state.get("ca_rec",""), height=100, key="ca_rec",
                       placeholder="Repair/replace leaking fittings, implement periodic leak survey…")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("ca_tech","Compressed air leaks represent one of the largest energy wastes in industrial facilities. A leak the size of a 1/8\" hole at 100 psig wastes approximately 25 CFM of air. Using an ultrasonic leak detector, all significant leaks can be tagged and repaired. The energy cost of the leak is calculated from the compressor power required to generate the lost airflow."),
                        height=100, key="ca_tech")

st.subheader("System Parameters")
col1, col2, col3, col4 = st.columns(4)
pressure  = col1.number_input("System pressure (psig)", value=100.0, step=5.0, key="ca_psi")
run_hours = col2.number_input("Compressor run hours/yr", value=4000.0, step=100.0, key="ca_hours")
comp_eff  = col3.slider("Compressor efficiency", 0.60, 0.95, 0.80, 0.01, key="ca_comp_eff")
motor_eff = col4.slider("Motor efficiency", 0.85, 0.97, 0.93, 0.01, key="ca_motor_eff")

rates = get_utility_rates()
col1, col2, col3 = st.columns(3)
elec_rate_in  = col1.number_input("Electricity rate ($/kWh)", value=round(rates["elec_rate"],4) if rates["elec_rate"]>0 else 0.10, step=0.001, format="%.4f", key="ca_elec")
demand_rate_in= col2.number_input("Demand rate ($/kW/mo)", value=0.0, step=1.0, key="ca_demand")
impl_cost     = col3.number_input("Implementation Cost ($)", value=1000.0, step=100.0, key="ca_impl")

# ── Leak Table ───────────────────────────────────────────────────────────────
st.subheader("Leak Inventory")
st.markdown("Enter each leak location. Use **hole diameter** OR **measured CFM**.")

if "ca_leaks" not in st.session_state:
    st.session_state["ca_leaks"] = [
        {"description": "Fitting/coupler", "qty": 3, "hole_diameter_in": 0.0625, "cfm_each": 0.0, "pressure_psig": 0.0},
    ]

leaks = st.session_state["ca_leaks"]
col_h = st.columns([3, 1, 1.5, 1.5, 1.5, 0.5])
col_h[0].markdown("**Description**")
col_h[1].markdown("**Qty**")
col_h[2].markdown("**Hole Dia (in)**")
col_h[3].markdown("**Meas CFM ea**")
col_h[4].markdown("**PSI override**")

for i, lk in enumerate(leaks):
    cols = st.columns([3, 1, 1.5, 1.5, 1.5, 0.5])
    lk["description"]     = cols[0].text_input("d", value=lk["description"], key=f"ca_desc_{i}", label_visibility="collapsed")
    lk["qty"]             = cols[1].number_input("q", value=int(lk["qty"]), min_value=1, step=1, key=f"ca_qty_{i}", label_visibility="collapsed")
    lk["hole_diameter_in"]= cols[2].number_input("h", value=float(lk["hole_diameter_in"]), min_value=0.0, step=0.01, format="%.4f", key=f"ca_hd_{i}", label_visibility="collapsed")
    lk["cfm_each"]        = cols[3].number_input("c", value=float(lk["cfm_each"]), min_value=0.0, step=0.5, key=f"ca_cfm_{i}", label_visibility="collapsed")
    lk["pressure_psig"]   = cols[4].number_input("p", value=float(lk["pressure_psig"]), min_value=0.0, step=5.0, key=f"ca_psi_{i}", label_visibility="collapsed")
    if cols[5].button("✕", key=f"ca_del_{i}") and len(leaks) > 1:
        leaks.pop(i)
        st.rerun()

if st.button("＋ Add Leak", key="ca_add"):
    leaks.append({"description": "", "qty": 1, "hole_diameter_in": 0.0625, "cfm_each": 0.0, "pressure_psig": 0.0})
    st.rerun()
st.session_state["ca_leaks"] = leaks

# Quick preview of estimated CFM per row
with st.expander("CFM Preview"):
    for lk in leaks:
        psi = lk["pressure_psig"] if lk["pressure_psig"] > 0 else pressure
        if lk["cfm_each"] > 0:
            cfm = lk["cfm_each"] * int(lk["qty"])
            st.write(f"  {lk['description']} — {cfm:.2f} CFM total (measured)")
        elif lk["hole_diameter_in"] > 0:
            cfm_ea = leak_flow_cfm(lk["hole_diameter_in"], psi)
            st.write(f"  {lk['description']} — {cfm_ea:.2f} CFM/leak × {lk['qty']} = {cfm_ea*lk['qty']:.2f} CFM total (calculated)")

if st.button("Calculate Leak Savings", type="primary", key="ca_calc"):
    result = compute_leak_savings(
        leaks=leaks,
        run_hours=run_hours,
        elec_rate=elec_rate_in,
        demand_rate=demand_rate_in,
        pressure_psig=pressure,
        comp_eff=comp_eff,
        motor_eff=motor_eff,
    )
    st.session_state["ca_result"] = result

if "ca_result" in st.session_state:
    r = st.session_state["ca_result"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total CFM Lost", f"{r['total_cfm_lost']:.1f} CFM")
    c2.metric("Compressor kW Lost", f"{r['total_kw_lost']:.2f} kW")
    c3.metric("Annual kWh Savings", f"{r['ann_kwh_savings']:,.0f} kWh")
    c4.metric("Annual Cost Savings", f"${r['ann_cost_savings']:,.0f}")
    payback = impl_cost / r["ann_cost_savings"] if r["ann_cost_savings"] > 0 else float("inf")
    st.metric("Simple Payback", f"{payback:.1f} yr" if payback != float("inf") else "N/A")

    # Detail table
    df = pd.DataFrame([{
        "Location": row.get("description",""),
        "Qty": row.get("qty",1),
        "CFM/leak": round(row.get("cfm_each",0),2),
        "Total CFM": round(row.get("total_cfm",0),2),
        "kW lost": round(row.get("kw_lost",0),3),
        "Ann kWh": round(row.get("ann_kwh_lost",0),0),
        "Cost Savings": f"${row.get('cost_savings',0):,.0f}",
    } for row in r["leaks"]])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key="ca_save"):
        payback = impl_cost / r["ann_cost_savings"] if r["ann_cost_savings"] > 0 else float("inf")
        ar_entry = {
            "arc_code": "2.4236",
            "ar_number": ar_num,
            "title": "Fix Compressed Air Leaks",
            "resources": [{"type": "Electricity", "savings": r["ann_kwh_savings"], "unit": "kWh"}],
            "total_cost_savings": r["ann_cost_savings"],
            "implementation_cost": impl_cost,
            "payback": payback,
            "observation": st.session_state.get("ca_obs",""),
            "recommendation": st.session_state.get("ca_rec",""),
            "tech_description": st.session_state.get("ca_tech",""),
            "calculation_details": r,
        }
        ar_list = st.session_state.get("ar_list", [])
        ar_list = [a for a in ar_list if a.get("arc_code") != "2.4236" or a.get("ar_number") != ar_num]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ {ar_num} saved. Total ARs: {len(ar_list)}")
