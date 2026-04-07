"""
Enhanced Other ARCs page — MALT IAC Tool
Supports:
  2.7135 — Occupancy Sensors
  2.7134 — Photocell Controls
  2.4133 — ECM Motors
  2.4322 — High-Efficiency Refrigeration Equipment
  2.7232 — High-Efficiency HVAC (SEER/EER upgrade)
  2.7447 — Air Curtains / Strip Doors
  2.2511 — Insulate Bare Equipment
  2.7224 — Reduce Space Conditioning (Unoccupied Hours)
  2.1321 — Replace Fuel Equipment with Electric
  2.6212 — Turn Off Lights (narrative-only default)
  2.7261 — Timers / Thermostats
  2.7264 — Interlock HVAC
  2.7312 — Minimize Outdoor Air
  2.9114 — Solar PV (links to page 15)
  2.3212 — Power Factor Correction (links to page 14)

Each ARC type offers two modes:
  - Calculation Mode: pre-filled calculation form matching MALT report style
  - Narrative-Only Mode: obs/rec/tech text fields only
"""
import sys
import os
import math

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from arcs.arc_generic import (
    lighting_hours_savings,
    motor_efficiency_savings,
    hvac_efficiency_savings,
    air_infiltration_savings,
)

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Other ARCs", layout="wide")
init_session()

st.title("Other Assessment Recommendations")
st.caption("Select an ARC, choose Calculation Mode or Narrative-Only Mode, fill in the fields, and save to report.")

rates = get_utility_rates()
e_rate = rates["elec_rate"] if rates["elec_rate"] > 0 else 0.10
g_rate = rates["gas_rate"]  if rates["gas_rate"]  > 0 else 8.0

# ── ARC Options ───────────────────────────────────────────────────────────────
ARC_OPTIONS = [
    "2.7135 — Occupancy Sensors",
    "2.7134 — Photocell Controls",
    "2.4133 — ECM Motors",
    "2.4322 — High-Efficiency Refrigeration Equipment",
    "2.7232 — High-Efficiency HVAC (SEER/EER Upgrade)",
    "2.7447 — Air Curtains / Strip Doors",
    "2.2511 — Insulate Bare Equipment",
    "2.7224 — Reduce Space Conditioning (Unoccupied Hours)",
    "2.1321 — Replace Fuel Equipment with Electric",
    "2.6212 — Turn Off Lights When Unoccupied",
    "2.7261 — Timers / Thermostats",
    "2.7264 — Interlock HVAC (Prevent Simultaneous H+C)",
    "2.7312 — Minimize Outdoor Air",
    "2.9114 — Solar PV",
    "2.3212 — Power Factor Correction",
]

# ARCs that are purely narrative (no built-in calculation)
NARRATIVE_ONLY_ARCS = {"2.6212", "2.7261", "2.7264", "2.7312", "2.9114", "2.3212"}

# ARCs that link to dedicated pages
LINKED_ARCS = {
    "2.9114": "page 15 (Solar PV)",
    "2.3212": "page 14 (Power Factor Correction)",
}

col_sel, col_custom = st.columns([3, 2])
with col_sel:
    selected_label = st.selectbox("Select ARC", ARC_OPTIONS, key="other_arc_sel")
with col_custom:
    custom_code = st.text_input("Or enter custom ARC code (e.g. 2.9999)", value="", key="other_custom_code")

# Resolve arc_code and arc_title
if custom_code.strip():
    arc_code = custom_code.strip()
    arc_title = f"ARC {arc_code}"
else:
    arc_code  = selected_label.split("—")[0].strip()
    arc_title = selected_label.split("—", 1)[1].strip()

arc_key  = arc_code.replace(".", "_") + "_other"
_defs    = get_defaults(arc_code)

# ── Mode Selection ────────────────────────────────────────────────────────────
has_calc = arc_code not in NARRATIVE_ONLY_ARCS and not custom_code.strip()

if has_calc:
    mode = st.radio(
        "Mode",
        ["📊 Use Calculation Preset", "📝 Narrative Only"],
        horizontal=True,
        key=f"{arc_key}_mode",
    )
    use_calc = (mode == "📊 Use Calculation Preset")
else:
    use_calc = False
    if arc_code in LINKED_ARCS:
        st.info(f"ARC {arc_code} has a dedicated page: see **{LINKED_ARCS[arc_code]}**. "
                f"You can still add narrative notes here.")

# ── Observation & Recommendation (always shown) ───────────────────────────────
with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input(
        "AR Number",
        value=st.session_state.get(f"{arc_key}_ar_num", "AR-1"),
        key=f"{arc_key}_ar_num",
    )
    obs = c1.text_area(
        "Observation",
        value=st.session_state.get(f"{arc_key}_obs", _defs.get("observation", "")),
        height=100,
        key=f"{arc_key}_obs",
    )
    rec = c2.text_area(
        "Recommendation",
        value=st.session_state.get(f"{arc_key}_rec", _defs.get("recommendation", "")),
        height=100,
        key=f"{arc_key}_rec",
    )
    tech = c2.text_area(
        "Technology Description",
        value=st.session_state.get(f"{arc_key}_tech", _defs.get("tech_description", "")),
        height=100,
        key=f"{arc_key}_tech",
    )

# ── Rate inputs (always shown) ────────────────────────────────────────────────
col_r1, col_r2, col_r3 = st.columns(3)
elec_rate_in   = col_r1.number_input("Electricity rate ($/kWh)", value=round(e_rate, 4), step=0.001, format="%.4f", key=f"{arc_key}_er")
demand_rate_in = col_r2.number_input("Demand rate ($/kW/mo)",    value=0.0,              step=1.0,   key=f"{arc_key}_dr")
impl_cost      = col_r3.number_input("Implementation Cost ($)",  value=0.0,              step=100.0, key=f"{arc_key}_impl")

result       = None
resource_list = []

# ════════════════════════════════════════════════════════════════════════════
# NARRATIVE-ONLY path (no calculation)
# ════════════════════════════════════════════════════════════════════════════
if not use_calc:
    st.info("📝 Narrative-Only Mode — enter savings manually if known, then save.")
    col_n1, col_n2, col_n3 = st.columns(3)
    manual_kwh  = col_n1.number_input("Estimated kWh Savings/yr",    value=0.0, step=100.0, key=f"{arc_key}_man_kwh")
    manual_mmbtu= col_n2.number_input("Estimated MMBtu Savings/yr",  value=0.0, step=0.1,   key=f"{arc_key}_man_mmbtu")
    manual_cost = col_n3.number_input("Estimated Annual Cost Savings ($)", value=0.0, step=100.0, key=f"{arc_key}_man_cost")

    if manual_cost > 0 or manual_kwh > 0 or manual_mmbtu > 0:
        result = {
            "ann_kwh_savings":  manual_kwh,
            "ann_mmbtu_savings": manual_mmbtu,
            "ann_cost_savings": manual_cost,
        }
        if manual_kwh > 0:
            resource_list.append({"type": "Electricity", "savings": manual_kwh, "unit": "kWh"})
        if manual_mmbtu > 0:
            resource_list.append({"type": "Natural Gas", "savings": manual_mmbtu, "unit": "MMBtu"})

# ════════════════════════════════════════════════════════════════════════════
# 2.7135 — Occupancy Sensors
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.7135":
    st.subheader("Occupancy Sensor — Lighting Calculation")
    st.markdown(
        "**Formula:** E_savings = kW_total × (1 − PAF) × AOH × IEF_E  \n"
        "**Demand:** ΔkW = kW_total × CF × IEF_D"
    )

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    paf    = col_p1.number_input("PAF — Power Adjustment Factor", value=0.70, min_value=0.0, max_value=1.0, step=0.01, key=f"{arc_key}_paf",
                                  help="Fraction of time lights are OFF due to sensor (default 0.70)")
    aoh    = col_p2.number_input("AOH — Annual Operating Hours", value=2000.0, step=50.0, key=f"{arc_key}_aoh")
    ief_e  = col_p3.number_input("IEF_E — Interactive Effects (energy)", value=1.09, step=0.01, key=f"{arc_key}_ief_e",
                                  help="Accounts for reduced HVAC cooling when lights are off (default 1.09)")
    ief_d  = col_p4.number_input("IEF_D — Interactive Effects (demand)", value=1.20, step=0.01, key=f"{arc_key}_ief_d")
    cf     = col_p1.number_input("CF — Coincidence Factor", value=0.26, min_value=0.0, max_value=1.0, step=0.01, key=f"{arc_key}_cf")

    st.markdown("##### Fixture Inventory")
    default_fixtures = pd.DataFrame([
        {"Building Type": "Warehouse", "Description": "T8 Fluorescent 4-lamp", "Qty": 10, "Lamps/Fixture": 4, "Watts/Lamp": 32.0},
    ])
    if f"{arc_key}_fixtures_df" not in st.session_state:
        st.session_state[f"{arc_key}_fixtures_df"] = default_fixtures

    fixtures_df = st.data_editor(
        st.session_state[f"{arc_key}_fixtures_df"],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{arc_key}_fixtures_editor",
        column_config={
            "Qty":           st.column_config.NumberColumn("Qty", min_value=0, step=1),
            "Lamps/Fixture": st.column_config.NumberColumn("Lamps/Fixture", min_value=1, step=1),
            "Watts/Lamp":    st.column_config.NumberColumn("Watts/Lamp (W)", min_value=0.0, step=1.0),
        },
    )
    st.session_state[f"{arc_key}_fixtures_df"] = fixtures_df

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        total_kw = sum(
            int(row["Qty"]) * int(row["Lamps/Fixture"]) * float(row["Watts/Lamp"]) / 1000.0
            for _, row in fixtures_df.iterrows()
        )
        kwh_saved   = total_kw * (1 - paf) * aoh * ief_e
        delta_kw    = total_kw * cf * ief_d
        ann_cost    = kwh_saved * elec_rate_in + delta_kw * demand_rate_in * 12
        result = {
            "total_kw":        total_kw,
            "kwh_saved":       kwh_saved,
            "delta_kw_demand": delta_kw,
            "ann_kwh_savings": kwh_saved,
            "ann_cost_savings": ann_cost,
        }
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Fixture kW", f"{result['total_kw']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Demand Reduction", f"{result['delta_kw_demand']:.2f} kW")
        c4.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# 2.7134 — Photocell Controls
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.7134":
    st.subheader("Photocell Controls — Exterior Lighting Calculation")
    st.markdown(
        "Same formula as occupancy sensors with exterior-lighting defaults:  \n"
        "PAF = 0.50 (lights off during daylight), AOH = 4,380 hr/yr, CF = 0.22"
    )

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    paf   = col_p1.number_input("PAF — Power Adjustment Factor", value=0.50, min_value=0.0, max_value=1.0, step=0.01, key=f"{arc_key}_paf")
    aoh   = col_p2.number_input("AOH — Annual Operating Hours (total)", value=4380.0, step=50.0, key=f"{arc_key}_aoh",
                                  help="Hours exterior lights are ON (default 4380 = 12 hr/day × 365)")
    ief_e = col_p3.number_input("IEF_E (energy)", value=1.00, step=0.01, key=f"{arc_key}_ief_e",
                                 help="Exterior lighting: no HVAC interaction, set to 1.0")
    cf    = col_p4.number_input("CF — Coincidence Factor", value=0.22, min_value=0.0, max_value=1.0, step=0.01, key=f"{arc_key}_cf")
    ief_d = col_p1.number_input("IEF_D (demand)", value=1.00, step=0.01, key=f"{arc_key}_ief_d")

    st.markdown("##### Exterior Fixture Inventory")
    default_ext = pd.DataFrame([
        {"Description": "Parking Lot HPS", "Qty": 8, "Watts/Fixture": 400.0},
    ])
    if f"{arc_key}_fixtures_df" not in st.session_state:
        st.session_state[f"{arc_key}_fixtures_df"] = default_ext

    fixtures_df = st.data_editor(
        st.session_state[f"{arc_key}_fixtures_df"],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{arc_key}_fixtures_editor",
        column_config={
            "Qty":           st.column_config.NumberColumn("Qty", min_value=0, step=1),
            "Watts/Fixture": st.column_config.NumberColumn("Watts/Fixture (W)", min_value=0.0, step=10.0),
        },
    )
    st.session_state[f"{arc_key}_fixtures_df"] = fixtures_df

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        total_kw  = sum(int(row["Qty"]) * float(row["Watts/Fixture"]) / 1000.0
                        for _, row in fixtures_df.iterrows())
        kwh_saved = total_kw * (1 - paf) * aoh * ief_e
        delta_kw  = total_kw * cf * ief_d
        ann_cost  = kwh_saved * elec_rate_in + delta_kw * demand_rate_in * 12
        result = {
            "total_kw": total_kw,
            "kwh_saved": kwh_saved,
            "delta_kw_demand": delta_kw,
            "ann_kwh_savings": kwh_saved,
            "ann_cost_savings": ann_cost,
        }
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Fixture kW", f"{result['total_kw']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Demand Reduction", f"{result['delta_kw_demand']:.2f} kW")
        c4.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# 2.4133 — ECM Motors
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.4133":
    st.subheader("ECM (Electronically Commutated) Motors — Calculation")
    st.markdown(
        "**Formula:** E_savings = (W_base − W_ECM) × Op_Hours × Duty_Cycle × (1 + 1/COP) / 1000  \n"
        "The (1 + 1/COP) term accounts for refrigeration system interaction "
        "(motor heat absorbed by refrigerated space adds load to compressor)."
    )

    default_ecm = pd.DataFrame([
        {"Unit": "Evaporator Fan 1", "W_base": 250.0, "W_ECM": 60.0,
         "Op_Hours": 8760.0, "Duty_Cycle": 0.94, "COP": 2.5},
    ])
    if f"{arc_key}_motors_df" not in st.session_state:
        st.session_state[f"{arc_key}_motors_df"] = default_ecm

    motors_df = st.data_editor(
        st.session_state[f"{arc_key}_motors_df"],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{arc_key}_motors_editor",
        column_config={
            "W_base":     st.column_config.NumberColumn("W_base (existing, W)", min_value=0.0, step=10.0),
            "W_ECM":      st.column_config.NumberColumn("W_ECM (proposed, W)",  min_value=0.0, step=5.0),
            "Op_Hours":   st.column_config.NumberColumn("Op Hours/yr",          min_value=0.0, step=100.0),
            "Duty_Cycle": st.column_config.NumberColumn("Duty Cycle (0–1)",     min_value=0.0, max_value=1.0, step=0.01),
            "COP":        st.column_config.NumberColumn("Refrig COP",           min_value=0.5, step=0.1,
                                                         help="COP of refrigeration system (set high/irrelevant if not in refrigerated space)"),
        },
    )
    st.session_state[f"{arc_key}_motors_df"] = motors_df

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        rows_out = []
        total_kwh = 0.0
        for _, row in motors_df.iterrows():
            w0   = float(row["W_base"])
            w1   = float(row["W_ECM"])
            hrs  = float(row["Op_Hours"])
            dc   = float(row["Duty_Cycle"])
            cop  = float(row["COP"])
            kwh  = (w0 - w1) * hrs * dc * (1 + 1 / cop) / 1000.0
            rows_out.append({**row.to_dict(), "kWh_saved": kwh})
            total_kwh += kwh
        ann_cost = total_kwh * elec_rate_in
        result = {
            "motors": rows_out,
            "ann_kwh_savings": total_kwh,
            "ann_cost_savings": ann_cost,
            "total_delta_kw": total_kwh / 8760,  # approximate average kW
        }
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2 = st.columns(2)
        c1.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c2.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        st.dataframe(
            pd.DataFrame(result["motors"])[["Unit", "W_base", "W_ECM", "Duty_Cycle", "COP", "kWh_saved"]],
            use_container_width=True,
        )
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# 2.4322 — High-Efficiency Refrigeration Equipment
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.4322":
    st.subheader("High-Efficiency Refrigeration Equipment")
    ref_sub = st.radio(
        "Sub-type",
        ["🌡️ Compressor Upgrade (COP method)", "🚪 Display Case / Walk-in Doors (kWh/ft lookup)"],
        horizontal=True,
        key=f"{arc_key}_submode",
    )

    if ref_sub.startswith("🌡️"):
        st.markdown("**Formula:** ΔkWh = Q_tons × 12,000 × (1/COP_exist − 1/COP_prop) / 1,000 × hours")
        col_a, col_b, col_c, col_d = st.columns(4)
        cop_exist = col_a.number_input("Existing COP",         value=2.0, min_value=0.5, step=0.1, key=f"{arc_key}_cop0")
        cop_prop  = col_b.number_input("Proposed COP",         value=3.0, min_value=0.5, step=0.1, key=f"{arc_key}_cop1")
        q_tons    = col_c.number_input("Cooling Load (tons)",  value=10.0, min_value=0.0, step=0.5, key=f"{arc_key}_tons")
        run_hrs   = col_d.number_input("Annual Run Hours",     value=6000.0, step=100.0, key=f"{arc_key}_hrs")

        if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
            kwh_saved = q_tons * 12000.0 * (1.0 / cop_exist - 1.0 / cop_prop) / 1000.0 * run_hrs
            ann_cost  = kwh_saved * elec_rate_in
            result = {"ann_kwh_savings": kwh_saved, "ann_cost_savings": ann_cost}
            st.session_state[f"{arc_key}_result"] = result

        if f"{arc_key}_result" in st.session_state:
            result = st.session_state[f"{arc_key}_result"]
            c1, c2 = st.columns(2)
            c1.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
            c2.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
            resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

    else:  # display case / walk-in doors lookup
        st.markdown("**kWh/linear-ft/yr lookup table** (from MALT report defaults):")
        CASE_LOOKUP = {
            "Vertical Open MT Remote Condensing":   112.0,
            "Vertical Open LT Remote Condensing":   209.0,
            "Vertical Open MT Self-Contained":      182.0,
            "Horizontal Open MT Remote":             42.0,
            "Horizontal Open LT Remote":             94.0,
        }
        lookup_df = pd.DataFrame(
            [{"Case Type": k, "kWh/ft/yr": v} for k, v in CASE_LOOKUP.items()]
        )
        st.dataframe(lookup_df, use_container_width=True, hide_index=True)

        default_cases = pd.DataFrame([
            {"Case Type": "Vertical Open MT Remote Condensing", "Linear Feet": 10.0},
        ])
        if f"{arc_key}_cases_df" not in st.session_state:
            st.session_state[f"{arc_key}_cases_df"] = default_cases

        cases_df = st.data_editor(
            st.session_state[f"{arc_key}_cases_df"],
            num_rows="dynamic",
            use_container_width=True,
            key=f"{arc_key}_cases_editor",
            column_config={
                "Case Type":   st.column_config.SelectboxColumn(
                    "Case Type", options=list(CASE_LOOKUP.keys())
                ),
                "Linear Feet": st.column_config.NumberColumn("Linear Feet", min_value=0.0, step=1.0),
            },
        )
        st.session_state[f"{arc_key}_cases_df"] = cases_df

        if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
            total_kwh = 0.0
            for _, row in cases_df.iterrows():
                ct   = row["Case Type"]
                lft  = float(row["Linear Feet"])
                rate = CASE_LOOKUP.get(ct, 0.0)
                total_kwh += lft * rate
            ann_cost = total_kwh * elec_rate_in
            result = {"ann_kwh_savings": total_kwh, "ann_cost_savings": ann_cost}
            st.session_state[f"{arc_key}_result"] = result

        if f"{arc_key}_result" in st.session_state:
            result = st.session_state[f"{arc_key}_result"]
            c1, c2 = st.columns(2)
            c1.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
            c2.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
            resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# 2.7232 — High-Efficiency HVAC (SEER/EER Upgrade)
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.7232":
    st.subheader("High-Efficiency HVAC — EER/SEER Upgrade Calculation")
    st.markdown(
        "**Formula:** kW = tons × 12,000 / (EER × 1,000)  \n"
        "ΔkWh = (kW_existing − kW_proposed) × run_hours"
    )

    default_hvac = pd.DataFrame([
        {"Description": "Rooftop Unit 1", "Tons": 5.0, "EER_Existing": 10.0, "EER_Proposed": 14.0, "Run_Hours": 1500.0},
    ])
    if f"{arc_key}_units_df" not in st.session_state:
        st.session_state[f"{arc_key}_units_df"] = default_hvac

    units_df = st.data_editor(
        st.session_state[f"{arc_key}_units_df"],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{arc_key}_units_editor",
        column_config={
            "Tons":         st.column_config.NumberColumn("Tons",        min_value=0.0, step=0.5),
            "EER_Existing": st.column_config.NumberColumn("EER Existing",min_value=5.0, step=0.5),
            "EER_Proposed": st.column_config.NumberColumn("EER Proposed",min_value=5.0, step=0.5),
            "Run_Hours":    st.column_config.NumberColumn("Run Hours/yr",min_value=0.0, step=100.0),
        },
    )
    st.session_state[f"{arc_key}_units_df"] = units_df

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        units_list = [
            {
                "description": row["Description"],
                "tons":        row["Tons"],
                "eer_existing":row["EER_Existing"],
                "eer_proposed":row["EER_Proposed"],
                "run_hours":   row["Run_Hours"],
            }
            for _, row in units_df.iterrows()
        ]
        result = hvac_efficiency_savings(units_list, elec_rate_in, demand_rate_in)
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total ΔkW", f"{result['total_delta_kw']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# 2.7447 — Air Curtains / Strip Doors
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.7447":
    st.subheader("Air Curtains / Strip Doors — Infiltration Savings Calculation")
    st.markdown(
        "**Formula:** Q_heating = U × A × HDD × 24 × reduction_fraction [BTU/yr]  \n"
        "Gas savings = Q_heating / (boiler_eff × 1e6) [MMBtu]  \n"
        "Elec savings (cooling) = U × A × CDD × 24 × fraction / 3,412 [kWh]"
    )

    col_loc1, col_loc2, col_loc3 = st.columns(3)
    hdd      = col_loc1.number_input("Annual HDD (Heating Degree Days)", value=int(st.session_state.get("hdd", 1400)), step=50, key=f"{arc_key}_hdd")
    cdd      = col_loc2.number_input("Annual CDD (Cooling Degree Days)", value=int(st.session_state.get("cdd", 2800)), step=50, key=f"{arc_key}_cdd")
    boil_eff = col_loc3.number_input("Boiler / heater efficiency", value=0.82, min_value=0.5, max_value=1.0, step=0.01, key=f"{arc_key}_beff")
    gas_rate_in = col_loc1.number_input("Gas rate ($/MMBtu)", value=round(g_rate, 3), step=0.1, key=f"{arc_key}_gr")

    st.markdown("##### Door Inventory")
    default_doors = pd.DataFrame([
        {"Description": "Loading Dock Door", "Width_ft": 10.0, "Height_ft": 10.0,
         "U_value": 0.5, "Reduction_Fraction": 0.80, "Open_Hours_yr": 2000.0},
    ])
    if f"{arc_key}_doors_df" not in st.session_state:
        st.session_state[f"{arc_key}_doors_df"] = default_doors

    doors_df = st.data_editor(
        st.session_state[f"{arc_key}_doors_df"],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{arc_key}_doors_editor",
        column_config={
            "Width_ft":          st.column_config.NumberColumn("Width (ft)",    min_value=1.0, step=0.5),
            "Height_ft":         st.column_config.NumberColumn("Height (ft)",   min_value=1.0, step=0.5),
            "U_value":           st.column_config.NumberColumn("U-value",       min_value=0.0, step=0.05,
                                                                help="BTU/hr·ft²·°F for open door (≈0.5)"),
            "Reduction_Fraction":st.column_config.NumberColumn("Reduction (0–1)", min_value=0.0, max_value=1.0, step=0.05,
                                                                help="Fraction of infiltration eliminated by curtain (≈0.80)"),
            "Open_Hours_yr":     st.column_config.NumberColumn("Open Hours/yr", min_value=0.0, step=100.0),
        },
    )
    st.session_state[f"{arc_key}_doors_df"] = doors_df

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        total_gas_mmbtu = 0.0
        total_elec_kwh  = 0.0
        for _, row in doors_df.iterrows():
            area  = float(row["Width_ft"]) * float(row["Height_ft"])
            U     = float(row["U_value"])
            frac  = float(row["Reduction_Fraction"])
            heat_btu = U * area * float(hdd) * 24.0 * frac
            cool_btu = U * area * float(cdd) * 24.0 * frac
            total_gas_mmbtu += heat_btu / (boil_eff * 1e6)
            total_elec_kwh  += cool_btu / 3412.0
        ann_cost = total_gas_mmbtu * gas_rate_in + total_elec_kwh * elec_rate_in
        result = {
            "total_gas_mmbtu": total_gas_mmbtu,
            "total_elec_kwh":  total_elec_kwh,
            "ann_cost_savings": ann_cost,
        }
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Gas Savings", f"{result['total_gas_mmbtu']:.2f} MMBtu/yr")
        c2.metric("Elec Savings", f"{result['total_elec_kwh']:,.0f} kWh/yr")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [
            {"type": "Electricity", "savings": result["total_elec_kwh"],  "unit": "kWh"},
            {"type": "Natural Gas", "savings": result["total_gas_mmbtu"], "unit": "MMBtu"},
        ]

# ════════════════════════════════════════════════════════════════════════════
# 2.2511 — Insulate Bare Equipment
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.2511":
    st.subheader("Insulate Bare Equipment — Heat Loss Savings Calculation")
    st.markdown(
        "**Formula:** Q_loss = U_bare × A × ΔT [BTU/hr]  \n"
        "Gas savings = Q_loss × (1 − ins_fraction) × hours / (boiler_eff × 1e6) [MMBtu]  \n"
        "*(Use electricity savings instead if system is electric.)*"
    )

    col_s1, col_s2, col_s3 = st.columns(3)
    system_type = col_s1.selectbox("System Type", ["Natural Gas (Steam/HW)", "Electric"], key=f"{arc_key}_systype")
    boil_eff    = col_s2.number_input("Boiler/System Efficiency", value=0.82, min_value=0.5, max_value=1.0, step=0.01, key=f"{arc_key}_beff")
    gas_rate_in = col_s3.number_input("Gas rate ($/MMBtu)", value=round(g_rate, 3), step=0.1, key=f"{arc_key}_gr")

    st.markdown("##### Equipment Inventory")
    default_equip = pd.DataFrame([
        {"Description": "Steam pipe section", "Surface_Area_ft2": 50.0, "U_bare": 2.0, "Temp_Diff_F": 150.0,
         "Annual_Hours": 8760.0, "Insulated_Fraction": 0.90},
    ])
    if f"{arc_key}_equip_df" not in st.session_state:
        st.session_state[f"{arc_key}_equip_df"] = default_equip

    equip_df = st.data_editor(
        st.session_state[f"{arc_key}_equip_df"],
        num_rows="dynamic",
        use_container_width=True,
        key=f"{arc_key}_equip_editor",
        column_config={
            "Surface_Area_ft2":   st.column_config.NumberColumn("Surface Area (ft²)", min_value=0.0, step=1.0),
            "U_bare":             st.column_config.NumberColumn("U_bare (BTU/hr·ft²·°F)", min_value=0.0, step=0.1),
            "Temp_Diff_F":        st.column_config.NumberColumn("ΔT (°F)", min_value=0.0, step=5.0),
            "Annual_Hours":       st.column_config.NumberColumn("Annual Hours", min_value=0.0, step=100.0),
            "Insulated_Fraction": st.column_config.NumberColumn("Insulation Effectiveness (0–1)",
                                                                  min_value=0.0, max_value=1.0, step=0.01),
        },
    )
    st.session_state[f"{arc_key}_equip_df"] = equip_df

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        total_mmbtu = 0.0
        total_kwh   = 0.0
        for _, row in equip_df.iterrows():
            q_btu_hr = float(row["U_bare"]) * float(row["Surface_Area_ft2"]) * float(row["Temp_Diff_F"])
            q_saved  = q_btu_hr * float(row["Insulated_Fraction"]) * float(row["Annual_Hours"])
            if system_type.startswith("Natural"):
                total_mmbtu += q_saved / (boil_eff * 1e6)
            else:
                total_kwh   += q_saved / 3412.0

        if system_type.startswith("Natural"):
            ann_cost = total_mmbtu * gas_rate_in
            result = {"total_gas_mmbtu": total_mmbtu, "total_elec_kwh": 0.0,
                      "ann_kwh_savings": 0.0, "ann_cost_savings": ann_cost}
        else:
            ann_cost = total_kwh * elec_rate_in
            result = {"total_gas_mmbtu": 0.0, "total_elec_kwh": total_kwh,
                      "ann_kwh_savings": total_kwh, "ann_cost_savings": ann_cost}
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3 = st.columns(3)
        if result["total_gas_mmbtu"] > 0:
            c1.metric("Gas Savings", f"{result['total_gas_mmbtu']:.2f} MMBtu/yr")
            resource_list = [{"type": "Natural Gas", "savings": result["total_gas_mmbtu"], "unit": "MMBtu"}]
        if result["total_elec_kwh"] > 0:
            c2.metric("Elec Savings", f"{result['total_elec_kwh']:,.0f} kWh/yr")
            resource_list.append({"type": "Electricity", "savings": result["total_elec_kwh"], "unit": "kWh"})
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")

# ════════════════════════════════════════════════════════════════════════════
# 2.7224 — Reduce Space Conditioning (Unoccupied Hours)
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.7224":
    st.subheader("Reduce Space Conditioning — Unoccupied Hours Setback")
    st.markdown(
        "**Formula:** ΔkWh = tons × 12,000 / (EER × 1,000) × setback_hours × setback_fraction  \n"
        "*(setback_fraction = fraction of full load avoided during setback)*"
    )

    col_a, col_b, col_c, col_d = st.columns(4)
    hvac_tons      = col_a.number_input("HVAC Capacity (tons)",           value=10.0, min_value=0.0, step=0.5,   key=f"{arc_key}_tons")
    eer_val        = col_b.number_input("EER of Equipment",               value=11.0, min_value=5.0, step=0.5,   key=f"{arc_key}_eer")
    setback_hours  = col_c.number_input("Setback Hours per Year",         value=2000.0, step=50.0,              key=f"{arc_key}_sethrs")
    setback_frac   = col_d.number_input("Load Reduction Fraction (0–1)",  value=0.50, min_value=0.0, max_value=1.0, step=0.05, key=f"{arc_key}_setfrac")

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        kw_full   = hvac_tons * 12000.0 / (eer_val * 1000.0)
        kwh_saved = kw_full * setback_hours * setback_frac
        ann_cost  = kwh_saved * elec_rate_in + kw_full * setback_frac * demand_rate_in * 12
        result = {
            "kw_full": kw_full,
            "ann_kwh_savings": kwh_saved,
            "ann_cost_savings": ann_cost,
        }
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Full Load kW", f"{result['kw_full']:.2f} kW")
        c2.metric("Annual kWh Savings", f"{result['ann_kwh_savings']:,.0f} kWh")
        c3.metric("Annual Cost Savings", f"${result['ann_cost_savings']:,.0f}")
        resource_list = [{"type": "Electricity", "savings": result["ann_kwh_savings"], "unit": "kWh"}]

# ════════════════════════════════════════════════════════════════════════════
# 2.1321 — Replace Fuel Equipment with Electric
# ════════════════════════════════════════════════════════════════════════════
elif arc_code == "2.1321":
    st.subheader("Replace Fuel Equipment with Electric — Net Cost Analysis")
    st.markdown(
        "Calculates net annual cost delta: fuel cost avoided minus new electricity cost.  \n"
        "*(Positive = saves money; negative = electrification costs more at current rates)*"
    )

    FUEL_HEAT_CONTENT = {
        "Natural Gas (MMBtu)": 1.0,
        "Propane (gallons)":   0.09150,   # MMBtu/gal
        "Diesel (gallons)":    0.13800,   # MMBtu/gal
        "Fuel Oil #2 (gallons)": 0.13800,
    }

    col_f1, col_f2, col_f3 = st.columns(3)
    fuel_type  = col_f1.selectbox("Fuel Type", list(FUEL_HEAT_CONTENT.keys()), key=f"{arc_key}_fuel")
    fuel_qty   = col_f2.number_input("Annual Fuel Consumption (in fuel units)",  value=1000.0, step=50.0, key=f"{arc_key}_fqty")
    fuel_price = col_f3.number_input("Fuel Price ($/fuel unit)",                 value=round(g_rate, 3),  step=0.1,  key=f"{arc_key}_fprice")

    st.markdown("**Electric Replacement:**")
    col_e1, col_e2, col_e3 = st.columns(3)
    elec_eff  = col_e1.number_input("Electric equipment efficiency (COP or fraction)", value=3.5, min_value=0.5, step=0.1, key=f"{arc_key}_eeff",
                                     help="COP for heat pumps (>1 ok), or fraction for resistance (≈1.0)")
    elec_kw   = col_e2.number_input("Electric equipment peak kW demand",               value=10.0, step=0.5, key=f"{arc_key}_ekw")
    fuel_mmbtu= FUEL_HEAT_CONTENT[fuel_type] * fuel_qty

    if st.button("Calculate", type="primary", key=f"{arc_key}_calc"):
        fuel_mmbtu_val = FUEL_HEAT_CONTENT[fuel_type] * fuel_qty
        fuel_cost      = fuel_qty * fuel_price
        # electric kWh needed = fuel_mmbtu * 293.07 kWh/MMBtu / elec_eff
        elec_kwh_new   = fuel_mmbtu_val * 293.07 / elec_eff
        elec_cost_new  = elec_kwh_new * elec_rate_in + elec_kw * demand_rate_in * 12
        net_savings    = fuel_cost - elec_cost_new
        result = {
            "fuel_mmbtu":     fuel_mmbtu_val,
            "fuel_cost":      fuel_cost,
            "elec_kwh_new":   elec_kwh_new,
            "elec_cost_new":  elec_cost_new,
            "ann_cost_savings": net_savings,
            # For resource tracking: electrification adds kWh, no "savings" in traditional sense
            "ann_kwh_savings": 0.0,
        }
        st.session_state[f"{arc_key}_result"] = result

    if f"{arc_key}_result" in st.session_state:
        result = st.session_state[f"{arc_key}_result"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fuel MMBtu/yr",      f"{result['fuel_mmbtu']:.1f} MMBtu")
        c2.metric("Fuel Cost Avoided",  f"${result['fuel_cost']:,.0f}/yr")
        c3.metric("New Electricity Cost",f"${result['elec_cost_new']:,.0f}/yr")
        net = result["ann_cost_savings"]
        c4.metric("Net Savings", f"${net:,.0f}/yr",
                  delta="savings" if net > 0 else "net cost",
                  delta_color="normal" if net > 0 else "inverse")
        if result["fuel_cost"] > 0:
            resource_list = [{"type": "Natural Gas", "savings": result["fuel_mmbtu"], "unit": "MMBtu"}]

# ════════════════════════════════════════════════════════════════════════════
# Fallback for custom/unrecognized ARC codes (narrative-only was already set)
# This branch is reached only if use_calc=True but arc_code is unknown
# ════════════════════════════════════════════════════════════════════════════
# (All calc-capable ARCs handled above; anything else fell to narrative-only)

# ── Save AR to Report ─────────────────────────────────────────────────────────
st.divider()
payback = (
    impl_cost / result["ann_cost_savings"]
    if result is not None and result.get("ann_cost_savings", 0) > 0
    else float("inf")
)

if st.button("💾 Save this AR to Report", type="primary", key=f"{arc_key}_save"):
    if result is None:
        # Narrative-only with no manual savings entered → create empty result
        result = {"ann_cost_savings": 0.0, "ann_kwh_savings": 0.0}

    ar_entry = {
        "arc_code":          arc_code,
        "ar_number":         st.session_state.get(f"{arc_key}_ar_num", ar_num),
        "title":             arc_title,
        "resources":         resource_list,
        "total_cost_savings":result.get("ann_cost_savings", 0),
        "implementation_cost": impl_cost,
        "payback":           payback,
        "observation":       st.session_state.get(f"{arc_key}_obs", ""),
        "recommendation":    st.session_state.get(f"{arc_key}_rec", ""),
        "tech_description":  st.session_state.get(f"{arc_key}_tech", ""),
        "calculation_details": result,
    }
    ar_list = st.session_state.get("ar_list", [])
    # Replace existing entry with same arc_code + ar_number
    ar_list = [
        a for a in ar_list
        if not (a.get("arc_code") == arc_code and a.get("ar_number") == ar_entry["ar_number"])
    ]
    ar_list.append(ar_entry)
    st.session_state["ar_list"] = ar_list
    st.success(
        f"✅ {ar_entry['ar_number']} ({arc_code} — {arc_title}) saved. "
        f"Total ARs in report: {len(ar_list)}"
    )

# ── Show saved ARs for this ARC code ─────────────────────────────────────────
existing = [a for a in st.session_state.get("ar_list", []) if a.get("arc_code") == arc_code]
if existing:
    with st.expander(f"📋 Saved ARs for {arc_code}", expanded=False):
        for a in existing:
            cost = a.get("total_cost_savings", 0)
            pb   = a.get("payback", float("inf"))
            pb_str = f"{pb:.1f} yr" if pb != float("inf") else "N/A"
            st.markdown(
                f"**{a['ar_number']}** — {a['title']}  \n"
                f"Annual savings: ${cost:,.0f}/yr | Payback: {pb_str}"
            )
