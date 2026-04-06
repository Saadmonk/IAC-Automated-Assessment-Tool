"""
Page 3 — General Facility Background
Covers sections 2.1–2.6 of the MALT IAC report.
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.session import init_session, DEFAULT_EQUIP_ROW, DEFAULT_SCHED_ROW
from copy import deepcopy

st.set_page_config(page_title="Facility Background", page_icon="🏭", layout="wide")
init_session()

st.title("🏭 General Facility Background")

# ── 2.1 Facility Description ──────────────────────────────────────────────────
st.subheader("2.1 Facility Description")
st.session_state["facility_description"] = st.text_area(
    "Describe the facility (location, size, floors, departments assessed, etc.)",
    value=st.session_state["facility_description"],
    height=120,
    placeholder="This facility, located in Covington, LA 70433, has a total gross floor area of approximately..."
)

# Operating Schedule
st.markdown("**Operating Schedule**")
sched_rows = st.session_state["schedule_rows"]
sched_df = pd.DataFrame(sched_rows)
days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
edited_sched = st.data_editor(
    sched_df,
    num_rows="dynamic",
    use_container_width=True,
    key="sched_editor",
    column_config={
        "division":       st.column_config.TextColumn("Division"),
        "start_time":     st.column_config.TextColumn("Start Time"),
        "end_time":       st.column_config.TextColumn("End Time"),
        "hours_per_day":  st.column_config.NumberColumn("Hrs/Day", min_value=0, max_value=24),
        "start_day":      st.column_config.SelectboxColumn("Start Day", options=days),
        "end_day":        st.column_config.SelectboxColumn("End Day", options=days),
        "days_per_week":  st.column_config.NumberColumn("Days/Wk", min_value=1, max_value=7),
        "weeks_per_year": st.column_config.NumberColumn("Wks/Yr", min_value=1, max_value=52),
        "annual_hours":   st.column_config.NumberColumn("Annual Hrs", disabled=True),
    }
)
# Recompute annual hours
for i in range(len(edited_sched)):
    try:
        edited_sched.at[i, "annual_hours"] = (
            float(edited_sched.at[i, "hours_per_day"]) *
            float(edited_sched.at[i, "days_per_week"]) *
            float(edited_sched.at[i, "weeks_per_year"])
        )
    except Exception:
        pass
st.session_state["schedule_rows"] = edited_sched.to_dict("records")

st.divider()

# ── 2.2 Process Description ───────────────────────────────────────────────────
st.subheader("2.2 Process Description")
st.session_state["process_description"] = st.text_area(
    "Describe the facility's main processes and operations",
    value=st.session_state["process_description"],
    height=120,
    placeholder="The facility provides a full range of clinical and diagnostic services..."
)

st.divider()

# ── 2.3 Best Practices ────────────────────────────────────────────────────────
st.subheader("2.3 Best Practices Already in Place")
bps = st.session_state["best_practices"]
new_bps = []
n_bp = st.number_input("Number of best practices", min_value=1, max_value=10,
                        value=max(len(bps), 1), step=1)
for i in range(int(n_bp)):
    val = bps[i] if i < len(bps) else ""
    new_bps.append(st.text_input(f"Best Practice #{i+1}", value=val,
                                  key=f"bp_{i}", placeholder="e.g. All interior lighting upgraded to LED"))
st.session_state["best_practices"] = new_bps

st.divider()

# ── 2.4 Forms of Energy Usage ─────────────────────────────────────────────────
st.subheader("2.4 Forms of Energy Usage")
col1, col2 = st.columns(2)
elec_options = ["Chilled Water Systems", "HVAC / Air Handling Units", "Lighting", "Motors",
                 "Compressed Air", "Refrigeration", "Pumps", "Fans", "Other"]
gas_options  = ["Hot Water Boiler", "Steam Boiler", "Space Heating", "Process Heat",
                 "Cooking", "Absorption Chiller", "Other"]
with col1:
    st.session_state["elec_used_for"] = st.multiselect(
        "Electricity Used For", elec_options, default=st.session_state["elec_used_for"])
with col2:
    st.session_state["gas_used_for"] = st.multiselect(
        "Natural Gas Used For", gas_options, default=st.session_state["gas_used_for"])

st.divider()

# ── 2.5 Major Energy Consuming Equipment ──────────────────────────────────────
st.subheader("2.5 Major Energy Consuming Equipment")
equip_rows = st.session_state["equipment_rows"]
equip_df = pd.DataFrame(equip_rows)
edited_equip = st.data_editor(
    equip_df,
    num_rows="dynamic",
    use_container_width=True,
    key="equip_editor",
    column_config={
        "equipment":    st.column_config.TextColumn("Equipment"),
        "specs":        st.column_config.TextColumn("Specifications"),
        "qty_capacity": st.column_config.TextColumn("Qty / Capacity"),
        "energy_form":  st.column_config.SelectboxColumn(
            "Energy Form",
            options=["Electricity", "Natural Gas", "Both", "Other"]
        ),
    }
)
st.session_state["equipment_rows"] = edited_equip.to_dict("records")

st.divider()
st.success("✅ Facility background complete. Continue to **Assessment Recommendations** in the sidebar.")
