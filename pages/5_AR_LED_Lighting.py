"""
ARC 2.7142 — LED Lighting Upgrade
Fixture inventory table → annual kWh savings
"""
import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from arcs.arc_2_7142_lighting import compute_lighting_savings, LAMP_EFFICACY

st.set_page_config(page_title="ARC 2.7142 — LED Lighting", layout="wide")
init_session()

st.title("AR: LED Lighting Upgrade (ARC 2.7142)")
st.caption("Replace existing inefficient lamps with energy-efficient LED alternatives.")

_defs = get_defaults("2.7142")

# ── Narrative ────────────────────────────────────────────────────────────────
with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value=st.session_state.get("led_ar_num", "AR-1"), key="led_ar_num")
    obs = c1.text_area("Observation", value=st.session_state.get("led_obs", _defs["observation"]),
                       height=100, key="led_obs")
    rec = c2.text_area("Recommendation", value=st.session_state.get("led_rec", _defs["recommendation"]),
                       height=100, key="led_rec")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("led_tech", _defs["tech_description"]),
                        height=100, key="led_tech")

# ── Global Defaults ──────────────────────────────────────────────────────────
st.subheader("Global Parameters")
col1, col2, col3, col4 = st.columns(4)
default_aoh   = col1.number_input("Default Annual Operating Hours (AOH)", value=2000, step=100, key="led_aoh")
rates = get_utility_rates()
elec_rate_in  = col2.number_input("Electricity rate ($/kWh)",
                                   value=round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.10,
                                   step=0.001, format="%.4f", key="led_elec_rate")
demand_rate_in= col3.number_input("Demand rate ($/kW/mo)", value=0.0, step=1.0, key="led_demand_rate")
impl_cost     = col4.number_input("Total Implementation Cost ($)", value=0.0, step=100.0, key="led_impl_cost")

# ── Fixture Table ────────────────────────────────────────────────────────────
st.subheader("Fixture Inventory")
st.markdown("Enter each fixture type as a row. AOH = Annual Operating Hours (leave 0 to use default above).")

# Initialize fixture rows
if "led_fixtures" not in st.session_state:
    st.session_state["led_fixtures"] = [
        {"description": "", "qty": 1, "existing_lamp_type": "Fluorescent T8 (32W)",
         "existing_watts": 32.0, "proposed_lamp_type": "LED T8 tube",
         "proposed_watts": 15.0, "annual_op_hours": 0.0},
    ]

# Render editable table
fixtures = st.session_state["led_fixtures"]

col_headers = st.columns([3, 1, 2, 1.5, 2, 1.5, 1.5])
col_headers[0].markdown("**Description**")
col_headers[1].markdown("**Qty**")
col_headers[2].markdown("**Existing Lamp**")
col_headers[3].markdown("**Exist W**")
col_headers[4].markdown("**Proposed Lamp**")
col_headers[5].markdown("**Prop W**")
col_headers[6].markdown("**AOH (hr)**")

lamp_types = list(LAMP_EFFICACY.keys())

for i, row in enumerate(fixtures):
    cols = st.columns([3, 1, 2, 1.5, 2, 1.5, 1.5, 0.5])
    row["description"]      = cols[0].text_input("desc", value=row["description"], key=f"led_desc_{i}", label_visibility="collapsed")
    row["qty"]              = cols[1].number_input("qty", value=int(row["qty"]), min_value=1, step=1, key=f"led_qty_{i}", label_visibility="collapsed")
    existing_idx = lamp_types.index(row["existing_lamp_type"]) if row["existing_lamp_type"] in lamp_types else 0
    row["existing_lamp_type"] = cols[2].selectbox("ex lamp", lamp_types, index=existing_idx, key=f"led_exlamp_{i}", label_visibility="collapsed")
    row["existing_watts"]   = cols[3].number_input("ex W", value=float(row["existing_watts"]), min_value=0.0, step=1.0, key=f"led_exw_{i}", label_visibility="collapsed")
    proposed_idx = lamp_types.index(row["proposed_lamp_type"]) if row["proposed_lamp_type"] in lamp_types else lamp_types.index("LED T8 tube")
    row["proposed_lamp_type"] = cols[4].selectbox("prop lamp", lamp_types, index=proposed_idx, key=f"led_proplamp_{i}", label_visibility="collapsed")
    row["proposed_watts"]   = cols[5].number_input("prop W", value=float(row["proposed_watts"]), min_value=0.0, step=1.0, key=f"led_propw_{i}", label_visibility="collapsed")
    row["annual_op_hours"]  = cols[6].number_input("AOH", value=float(row["annual_op_hours"]), min_value=0.0, step=100.0, key=f"led_aoh_{i}", label_visibility="collapsed")
    if cols[7].button("✕", key=f"led_del_{i}") and len(fixtures) > 1:
        fixtures.pop(i)
        st.rerun()

if st.button("＋ Add Fixture Type", key="led_add"):
    fixtures.append({"description": "", "qty": 1,
                     "existing_lamp_type": "Fluorescent T8 (32W)",
                     "existing_watts": 32.0,
                     "proposed_lamp_type": "LED T8 tube",
                     "proposed_watts": 15.0,
                     "annual_op_hours": 0.0})
    st.rerun()

st.session_state["led_fixtures"] = fixtures

# ── Calculate ────────────────────────────────────────────────────────────────
if st.button("Calculate LED Savings", type="primary", key="led_calc"):
    # Fill in default AOH for rows where 0 was left
    fixtures_calc = []
    for f in fixtures:
        fc = dict(f)
        if fc["annual_op_hours"] == 0.0:
            fc["annual_op_hours"] = default_aoh
        fixtures_calc.append(fc)

    result = compute_lighting_savings(
        fixtures_calc, elec_rate_in, demand_rate_in, ann_op_hours_default=default_aoh
    )
    st.session_state["led_result"] = result

if "led_result" in st.session_state:
    result = st.session_state["led_result"]

    st.subheader("Results")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Annual kWh Savings", f"{result['total_ann_kwh']:,.0f} kWh")
    c2.metric("Peak Demand Reduction", f"{result['total_delta_kw']:.2f} kW")
    c3.metric("Annual Cost Savings", f"${result['total_cost_savings']:,.0f}")
    payback = impl_cost / result["total_cost_savings"] if result["total_cost_savings"] > 0 else float("inf")
    c4.metric("Simple Payback", f"{payback:.1f} yr" if payback != float('inf') else "N/A")

    # Per-fixture breakdown table
    fix_rows = result["fixtures"]
    df_out = pd.DataFrame([{
        "Description":    r.get("description", "—"),
        "Qty":            r.get("qty", 1),
        "Exist W":        r.get("existing_watts", 0),
        "Prop W":         r.get("proposed_watts", 0),
        "ΔW/fixture":     round(r.get("delta_w_per_fixture", 0), 1),
        "AOH (hr)":       r.get("annual_op_hours", 0),
        "Ann kWh":        round(r.get("ann_kwh", 0), 0),
        "Cost Savings":   f"${r.get('cost_savings', 0):,.0f}",
    } for r in fix_rows])
    st.dataframe(df_out, use_container_width=True, hide_index=True)

    # Save AR
    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key="led_save"):
        ar_entry = {
            "arc_code": "2.7142",
            "ar_number": ar_num,
            "title": "LED Lighting Upgrade",
            "resources": [{"type": "Electricity", "savings": result["total_ann_kwh"], "unit": "kWh"}],
            "total_cost_savings": result["total_cost_savings"],
            "implementation_cost": impl_cost,
            "payback": payback,
            "observation": st.session_state.get("led_obs", ""),
            "recommendation": st.session_state.get("led_rec", ""),
            "tech_description": st.session_state.get("led_tech", ""),
            "calculation_details": {
                "fixtures": fixtures,
                "total_ann_kwh": result["total_ann_kwh"],
                "total_delta_kw": result["total_delta_kw"],
                "total_cost_savings": result["total_cost_savings"],
                "elec_rate": elec_rate_in,
                "demand_rate": demand_rate_in,
            }
        }
        ar_list = st.session_state.get("ar_list", [])
        ar_list = [a for a in ar_list if a.get("arc_code") != "2.7142" or a.get("ar_number") != ar_num]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ {ar_num} saved. Total ARs: {len(ar_list)}")
