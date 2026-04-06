"""
Page for additional ARCs:
  2.7135 — Occupancy Sensors
  2.7134 — Photocell Controls
  2.6212 — Turn Off Lights When Unoccupied
  2.4322 — Energy-Efficient Motors
  2.4133 — ECM Motors
  2.7447 — Air Curtain / Strip Doors
  2.9114 — Solar PV
  2.7264 — Interlock HVAC
  2.7232 — High-Efficiency HVAC
  2.7261 — Timers / Thermostats
"""
import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from arcs.arc_generic import (
    lighting_hours_savings,
    motor_efficiency_savings,
    hvac_efficiency_savings,
    air_infiltration_savings,
    solar_pv_savings,
    interlock_hvac_savings,
)

st.set_page_config(page_title="Additional ARCs", layout="wide")
init_session()

st.title("Additional Assessment Recommendations")
st.caption("Select an ARC code and fill in the inputs to calculate savings.")

rates = get_utility_rates()
e_rate = rates["elec_rate"] if rates["elec_rate"] > 0 else 0.10
g_rate = rates["gas_rate"]  if rates["gas_rate"] > 0 else 8.0

ARC_OPTIONS = {
    "2.7135 — Occupancy Sensors": "occ",
    "2.7134 — Photocell Controls": "photo",
    "2.6212 — Turn Off Lights When Unoccupied": "lightsoff",
    "2.4322 — Energy-Efficient Motors": "motors",
    "2.4133 — ECM Motors": "ecm",
    "2.7447 — Air Curtain / Strip Doors": "aircurtain",
    "2.9114 — Solar PV": "solar",
    "2.7264 — Interlock HVAC": "interlock",
    "2.7232 — High-Efficiency HVAC": "heff_hvac",
    "2.7261 — Timers / Thermostats": "timers",
}

selected_arc = st.selectbox("Select ARC", list(ARC_OPTIONS.keys()), key="other_arc_sel")
arc_key = ARC_OPTIONS[selected_arc]
arc_code = selected_arc.split("—")[0].strip()
arc_title= selected_arc.split("—")[1].strip()

# ── Common narrative fields ──────────────────────────────────────────────────
with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value=st.session_state.get(f"{arc_key}_ar_num","AR-1"), key=f"{arc_key}_ar_num")
    obs = c1.text_area("Observation", value=st.session_state.get(f"{arc_key}_obs",""), height=90, key=f"{arc_key}_obs")
    rec = c2.text_area("Recommendation", value=st.session_state.get(f"{arc_key}_rec",""), height=90, key=f"{arc_key}_rec")
    tech = c2.text_area("Technology Description", value=st.session_state.get(f"{arc_key}_tech",""), height=90, key=f"{arc_key}_tech")

col_r1, col_r2, col_r3 = st.columns(3)
elec_rate_in = col_r1.number_input("Electricity rate ($/kWh)", value=round(e_rate,4), step=0.001, format="%.4f", key=f"{arc_key}_er")
demand_rate_in = col_r2.number_input("Demand rate ($/kW/mo)", value=0.0, step=1.0, key=f"{arc_key}_dr")
impl_cost = col_r3.number_input("Implementation Cost ($)", value=0.0, step=100.0, key=f"{arc_key}_impl")

result = None
resource_list = []

# ════════════════════════════════════════════════════════════════════════════
# Lighting-hours ARCs: 2.7135, 2.7134, 2.6212
# ════════════════════════════════════════════════════════════════════════════
if arc_key in ("occ", "photo", "lightsoff"):
    label_map = {
        "occ":      ("Lights controlled by occupancy sensors", "Hours saved (lights OFF when unoccupied)"),
        "photo":    ("Lights controlled by photocells", "Hours saved (daylight hours)"),
        "lightsoff":("Lights turned off when area unoccupied", "Additional OFF hours per year"),
    }
    label_fix, label_hrs = label_map[arc_key]
    st.subheader("Lighting Fixtures")
    hrs_saved = st.number_input(label_hrs, value=500.0, step=50.0, key=f"{arc_key}_hrs")

    if f"{arc_key}_fixtures" not in st.session_state:
        st.session_state[f"{arc_key}_fixtures"] = [{"description": "", "qty": 10, "watts": 32.0}]
    fixtures = st.session_state[f"{arc_key}_fixtures"]
    col_h = st.columns([3, 1, 1.5, 0.5])
    col_h[0].markdown("**Description**"); col_h[1].markdown("**Qty**"); col_h[2].markdown("**Watts/fixture**")
    for i, f in enumerate(fixtures):
        cols = st.columns([3, 1, 1.5, 0.5])
        f["description"] = cols[0].text_input("d", value=f["description"], key=f"{arc_key}_fd_{i}", label_visibility="collapsed")
        f["qty"]         = cols[1].number_input("q", value=int(f["qty"]), min_value=1, step=1, key=f"{arc_key}_fq_{i}", label_visibility="collapsed")
        f["watts"]       = cols[2].number_input("w", value=float(f["watts"]), min_value=0.0, step=1.0, key=f"{arc_key}_fw_{i}", label_visibility="collapsed")
        if cols[3].button("✕", key=f"{arc_key}_fd_{i}_del") and len(fixtures) > 1:
            fixtures.pop(i); st.rerun()
    if st.button("＋ Add", key=f"{arc_key}_fadd"):
        fixtures.append({"description": "", "qty": 1, "watts": 32.0}); st.rerun()
    st.session_state[f"{arc_key}_fixtures"] = fixtures

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        result = lighting_hours_savings(fixtures, hrs_saved, elec_rate_in, demand_rate_in)
        st.session_state[f"{arc_key}_result"] = result
    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c2.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# Motor ARCs: 2.4322, 2.4133
# ════════════════════════════════════════════════════════════════════════════
elif arc_key in ("motors", "ecm"):
    st.subheader("Motor Inventory")
    if f"{arc_key}_motors" not in st.session_state:
        st.session_state[f"{arc_key}_motors"] = [{"description": "", "hp": 10.0, "eff_existing": 0.88, "eff_proposed": 0.95, "run_hours": 4000.0}]
    motors = st.session_state[f"{arc_key}_motors"]
    col_h = st.columns([3, 1.2, 1.5, 1.5, 1.5, 0.5])
    col_h[0].markdown("**Description**"); col_h[1].markdown("**HP**")
    col_h[2].markdown("**Exist Eff**"); col_h[3].markdown("**Prop Eff**"); col_h[4].markdown("**Run Hrs**")
    for i, m in enumerate(motors):
        cols = st.columns([3, 1.2, 1.5, 1.5, 1.5, 0.5])
        m["description"]  = cols[0].text_input("d", value=m["description"], key=f"{arc_key}_md_{i}", label_visibility="collapsed")
        m["hp"]           = cols[1].number_input("hp", value=float(m["hp"]), min_value=0.0, step=1.0, key=f"{arc_key}_mhp_{i}", label_visibility="collapsed")
        m["eff_existing"] = cols[2].number_input("e0", value=float(m["eff_existing"]), min_value=0.5, max_value=1.0, step=0.01, key=f"{arc_key}_me0_{i}", label_visibility="collapsed")
        m["eff_proposed"] = cols[3].number_input("e1", value=float(m["eff_proposed"]), min_value=0.5, max_value=1.0, step=0.01, key=f"{arc_key}_me1_{i}", label_visibility="collapsed")
        m["run_hours"]    = cols[4].number_input("hr", value=float(m["run_hours"]), min_value=0.0, step=100.0, key=f"{arc_key}_mhr_{i}", label_visibility="collapsed")
        if cols[5].button("✕", key=f"{arc_key}_mdel_{i}") and len(motors) > 1:
            motors.pop(i); st.rerun()
    if st.button("＋ Add Motor", key=f"{arc_key}_madd"):
        motors.append({"description": "", "hp": 10.0, "eff_existing": 0.88, "eff_proposed": 0.95, "run_hours": 4000.0}); st.rerun()
    st.session_state[f"{arc_key}_motors"] = motors

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        result = motor_efficiency_savings(motors, elec_rate_in, demand_rate_in)
        st.session_state[f"{arc_key}_result"] = result
    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("ΔkW", f"{result['total_delta_kw']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# Air Curtain / Strip Doors: 2.7447
# ════════════════════════════════════════════════════════════════════════════
elif arc_key == "aircurtain":
    st.subheader("Door Parameters")
    gas_rate_in = st.number_input("Gas rate ($/MMBtu)", value=round(g_rate,3), step=0.1, key="aircurtain_gr")
    hdd = st.number_input("Annual Heating Degree Days (HDD)", value=1400.0, step=50.0, key="aircurtain_hdd")
    cdd = st.number_input("Annual Cooling Degree Days (CDD)", value=2800.0, step=50.0, key="aircurtain_cdd")

    if "aircurtain_doors" not in st.session_state:
        st.session_state["aircurtain_doors"] = [{"description": "Loading dock door", "width_ft": 10.0, "height_ft": 10.0, "u_value": 0.5, "reduction_fraction": 0.8, "open_hours_per_year": 2000.0}]
    doors = st.session_state["aircurtain_doors"]
    col_h = st.columns([3, 1.2, 1.2, 1.2, 1.2, 0.5])
    col_h[0].markdown("**Description**"); col_h[1].markdown("**W (ft)**"); col_h[2].markdown("**H (ft)**"); col_h[3].markdown("**U-value**"); col_h[4].markdown("**Reduction**")
    for i, d in enumerate(doors):
        cols = st.columns([3, 1.2, 1.2, 1.2, 1.2, 0.5])
        d["description"]       = cols[0].text_input("d", value=d["description"], key=f"ac_dd_{i}", label_visibility="collapsed")
        d["width_ft"]          = cols[1].number_input("w", value=float(d["width_ft"]), min_value=1.0, step=0.5, key=f"ac_w_{i}", label_visibility="collapsed")
        d["height_ft"]         = cols[2].number_input("h", value=float(d["height_ft"]), min_value=1.0, step=0.5, key=f"ac_h_{i}", label_visibility="collapsed")
        d["u_value"]           = cols[3].number_input("u", value=float(d["u_value"]), min_value=0.0, step=0.05, key=f"ac_u_{i}", label_visibility="collapsed")
        d["reduction_fraction"]= cols[4].number_input("r", value=float(d["reduction_fraction"]), min_value=0.0, max_value=1.0, step=0.05, key=f"ac_r_{i}", label_visibility="collapsed")
        if cols[5].button("✕", key=f"ac_del_{i}") and len(doors) > 1:
            doors.pop(i); st.rerun()
    if st.button("＋ Add Door", key="ac_add"):
        doors.append({"description": "", "width_ft": 8.0, "height_ft": 10.0, "u_value": 0.5, "reduction_fraction": 0.8, "open_hours_per_year": 2000.0}); st.rerun()
    st.session_state["aircurtain_doors"] = doors

    if st.button("Calculate", type="primary", key="aircurtain_calc"):
        result = air_infiltration_savings(doors, hdd, cdd, gas_rate_in, elec_rate_in)
        st.session_state["aircurtain_result"] = result
    if "aircurtain_result" in st.session_state:
        result = st.session_state["aircurtain_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Gas Savings", f"{result['total_gas_mmbtu']:.2f} MMBtu/yr")
        c2.metric("Elec Savings", f"{result['total_elec_kwh']:,.0f} kWh/yr")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [
            {"type": "Electricity", "savings": result["total_elec_kwh"], "unit": "kWh"},
            {"type": "Natural Gas", "savings": result["total_gas_mmbtu"], "unit": "MMBtu"},
        ]

# ════════════════════════════════════════════════════════════════════════════
# Solar PV: 2.9114
# ════════════════════════════════════════════════════════════════════════════
elif arc_key == "solar":
    st.subheader("Solar PV Parameters")
    col1, col2, col3 = st.columns(3)
    panel_area = col1.number_input("Panel area (sq ft)", value=5000.0, step=100.0, key="solar_area")
    sys_eff    = col2.slider("System efficiency", 0.10, 0.25, 0.18, 0.01, key="solar_eff")
    psh        = col3.number_input("Peak sun hours/year (Louisiana ≈ 1460)", value=1460.0, step=50.0, key="solar_psh")

    if st.button("Calculate", type="primary", key="solar_calc"):
        result = solar_pv_savings(panel_area, sys_eff, psh, elec_rate_in, impl_cost)
        st.session_state["solar_result"] = result
    if "solar_result" in st.session_state:
        result = st.session_state["solar_result"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rated kW", f"{result['rated_kw']:.1f} kW")
        c2.metric("Annual kWh Generated", f"{result['ann_kwh_generated']:,.0f} kWh")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        c4.metric("Simple Payback", f"{result['payback_years']:.1f} yr" if result['payback_years'] != float('inf') else "N/A")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_generated"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# Interlock HVAC: 2.7264
# ════════════════════════════════════════════════════════════════════════════
elif arc_key == "interlock":
    st.subheader("Simultaneous Heating/Cooling Parameters")
    col1, col2, col3 = st.columns(3)
    sim_hours  = col1.number_input("Hours/yr of simultaneous H+C", value=1000.0, step=50.0, key="int_hrs")
    overlap_tons= col2.number_input("Overlap cooling load (tons)", value=5.0, step=0.5, key="int_tons")
    eer_val    = col3.number_input("EER of cooling equipment", value=11.0, step=0.5, key="int_eer")

    if st.button("Calculate", type="primary", key="int_calc"):
        result = interlock_hvac_savings(sim_hours, overlap_tons, eer_val, elec_rate_in, demand_rate_in)
        st.session_state["interlock_result"] = result
    if "interlock_result" in st.session_state:
        result = st.session_state["interlock_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Wasted kW eliminated", f"{result['kw_wasted']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# High-Efficiency HVAC: 2.7232
# ════════════════════════════════════════════════════════════════════════════
elif arc_key == "heff_hvac":
    st.subheader("HVAC Unit Inventory")
    if "heff_units" not in st.session_state:
        st.session_state["heff_units"] = [{"description": "Rooftop Unit", "tons": 5.0, "eer_existing": 10.0, "eer_proposed": 14.0, "run_hours": 1500.0}]
    units = st.session_state["heff_units"]
    col_h = st.columns([3, 1.2, 1.5, 1.5, 1.5, 0.5])
    col_h[0].markdown("**Description**"); col_h[1].markdown("**Tons**"); col_h[2].markdown("**EER exist**"); col_h[3].markdown("**EER prop**"); col_h[4].markdown("**Run Hrs**")
    for i, u in enumerate(units):
        cols = st.columns([3, 1.2, 1.5, 1.5, 1.5, 0.5])
        u["description"]  = cols[0].text_input("d", value=u["description"], key=f"heff_d_{i}", label_visibility="collapsed")
        u["tons"]         = cols[1].number_input("t", value=float(u["tons"]), min_value=0.0, step=0.5, key=f"heff_t_{i}", label_visibility="collapsed")
        u["eer_existing"] = cols[2].number_input("e0", value=float(u["eer_existing"]), min_value=5.0, step=0.5, key=f"heff_e0_{i}", label_visibility="collapsed")
        u["eer_proposed"] = cols[3].number_input("e1", value=float(u["eer_proposed"]), min_value=5.0, step=0.5, key=f"heff_e1_{i}", label_visibility="collapsed")
        u["run_hours"]    = cols[4].number_input("hr", value=float(u["run_hours"]), min_value=0.0, step=100.0, key=f"heff_hr_{i}", label_visibility="collapsed")
        if cols[5].button("✕", key=f"heff_del_{i}") and len(units) > 1:
            units.pop(i); st.rerun()
    if st.button("＋ Add Unit", key="heff_add"):
        units.append({"description": "", "tons": 5.0, "eer_existing": 10.0, "eer_proposed": 14.0, "run_hours": 1500.0}); st.rerun()
    st.session_state["heff_units"] = units

    if st.button("Calculate", type="primary", key="heff_calc"):
        result = hvac_efficiency_savings(units, elec_rate_in, demand_rate_in)
        st.session_state["heff_result"] = result
    if "heff_result" in st.session_state:
        result = st.session_state["heff_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("ΔkW", f"{result['total_delta_kw']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# Timers / Thermostats: 2.7261 (simplified lighting-hours approach)
# ════════════════════════════════════════════════════════════════════════════
elif arc_key == "timers":
    st.subheader("Timer-Controlled Equipment")
    st.info("Use the lighting-hours method: total controlled load × hours saved per year.")
    total_kw  = st.number_input("Total controlled load (kW)", value=5.0, step=0.5, key="tmr_kw")
    hrs_saved = st.number_input("Hours saved per year", value=500.0, step=50.0, key="tmr_hrs")
    if st.button("Calculate", type="primary", key="tmr_calc"):
        ann_kwh  = total_kw * hrs_saved
        ann_cost = ann_kwh * elec_rate_in + total_kw * demand_rate_in * 12
        result = {"ann_kwh_savings": ann_kwh, "ann_cost_savings": ann_cost, "total_kw": total_kw}
        st.session_state["timers_result"] = result
    if "timers_result" in st.session_state:
        result = st.session_state["timers_result"]
        c1, c2 = st.columns(2)
        c1.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c2.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ── Save AR ──────────────────────────────────────────────────────────────────
if result is not None:
    payback = impl_cost / result.get("ann_cost_savings", 1) if result.get("ann_cost_savings", 0) > 0 else float("inf")
    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key=f"{arc_key}_save"):
        ar_entry = {
            "arc_code": arc_code,
            "ar_number": ar_num,
            "title": arc_title,
            "resources": resource_list,
            "total_cost_savings": result.get("ann_cost_savings", 0),
            "implementation_cost": impl_cost,
            "payback": payback,
            "observation": st.session_state.get(f"{arc_key}_obs", ""),
            "recommendation": st.session_state.get(f"{arc_key}_rec", ""),
            "tech_description": st.session_state.get(f"{arc_key}_tech", ""),
            "calculation_details": result,
        }
        ar_list = st.session_state.get("ar_list", [])
        ar_list = [a for a in ar_list if a.get("arc_code") != arc_code or a.get("ar_number") != ar_num]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ {ar_num} ({arc_code}) saved. Total ARs: {len(ar_list)}")
