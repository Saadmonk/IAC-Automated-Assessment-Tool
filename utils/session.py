"""
Session state helpers — centralized defaults so every page sees the same schema.
"""
import streamlit as st
from copy import deepcopy

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

DEFAULT_ELEC_ROW = {"month": "", "kwh": 0.0, "elec_cost": 0.0, "kw": 0.0, "demand_cost": 0.0, "fee": 0.0, "total": 0.0}
DEFAULT_GAS_ROW  = {"month": "", "mmbtu": 0.0, "cost": 0.0, "fee": 0.0, "total": 0.0}
DEFAULT_WATER_ROW= {"month": "", "tgal": 0.0, "water_cost": 0.0, "sewer_cost": 0.0, "fee": 0.0, "total": 0.0}
DEFAULT_EQUIP_ROW= {"equipment": "", "specs": "", "qty_capacity": "", "energy_form": "Electricity"}
DEFAULT_SCHED_ROW= {"division": "", "start_time": "8:00 AM", "end_time": "5:00 PM",
                    "hours_per_day": 9, "start_day": "Mon", "end_day": "Fri",
                    "days_per_week": 5, "weeks_per_year": 52, "annual_hours": 2340}


def init_session():
    """Initialize all session state keys with defaults if not already set."""
    defaults = {
        # ── Cover / Metadata ──────────────────────────────────────────
        "report_number": "",
        "site_visit_date": None,
        "location": "",
        "principal_products": "",
        "naics_code": "",
        "sic_code": "",
        "lead_faculty": "Dr. Peng \"Solomon\" Yin",
        "lead_student": "",
        "safety_student": "",
        "other_students": "",
        "annual_sales": "",
        "num_employees": "",

        # ── Facility Background ───────────────────────────────────────
        "facility_description": "",
        "process_description": "",
        "best_practices": ["", "", ""],
        "elec_used_for": [],
        "gas_used_for": [],
        "equipment_rows": [deepcopy(DEFAULT_EQUIP_ROW)],
        "schedule_rows": [deepcopy(DEFAULT_SCHED_ROW)],

        # ── Utility Billing ───────────────────────────────────────────
        "elec_rows": [dict(DEFAULT_ELEC_ROW, month=m) for m in MONTHS],
        "gas_rows":  [dict(DEFAULT_GAS_ROW,  month=m) for m in MONTHS],
        "water_rows":[dict(DEFAULT_WATER_ROW,month=m) for m in MONTHS],
        "has_gas": True,
        "has_water": True,

        # ── ARs ───────────────────────────────────────────────────────
        "ar_list": [],          # list of AR dicts built by each ARC module

        # ── Smart meter data (for thermostat ARC) ────────────────────
        "smart_meter_df": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_utility_rates():
    """Compute average rates from billing tables. Returns dict."""
    rates = {}

    elec_rows = st.session_state.get("elec_rows", [])
    ann_kwh   = sum(r["kwh"] for r in elec_rows)
    ann_ec    = sum(r["elec_cost"] for r in elec_rows)
    ann_kw    = sum(r["kw"] for r in elec_rows)
    ann_dc    = sum(r["demand_cost"] for r in elec_rows)
    ann_efee  = sum(r["fee"] for r in elec_rows)
    rates["ann_kwh"]   = ann_kwh
    rates["ann_elec_cost"] = ann_ec
    rates["ann_kw"]    = ann_kw
    rates["ann_demand_cost"] = ann_dc
    rates["ann_elec_fee"] = ann_efee
    rates["elec_rate"] = ann_ec / ann_kwh if ann_kwh else 0.0
    rates["demand_rate"]= ann_dc / ann_kw  if ann_kw  else 0.0

    gas_rows  = st.session_state.get("gas_rows", [])
    ann_mmbtu = sum(r["mmbtu"] for r in gas_rows)
    ann_gc    = sum(r["cost"]  for r in gas_rows)
    ann_gfee  = sum(r["fee"]   for r in gas_rows)
    rates["ann_mmbtu"]  = ann_mmbtu
    rates["ann_gas_cost"]= ann_gc
    rates["ann_gas_fee"] = ann_gfee
    rates["gas_rate"]   = ann_gc / ann_mmbtu if ann_mmbtu else 0.0

    water_rows = st.session_state.get("water_rows", [])
    ann_tgal   = sum(r["tgal"]       for r in water_rows)
    ann_wc     = sum(r["water_cost"] for r in water_rows)
    ann_sc     = sum(r["sewer_cost"] for r in water_rows)
    ann_wfee   = sum(r["fee"]        for r in water_rows)
    rates["ann_tgal"]   = ann_tgal
    rates["ann_water_cost"]= ann_wc
    rates["ann_sewer_cost"]= ann_sc
    rates["ann_water_fee"] = ann_wfee
    rates["water_rate"] = ann_wc / ann_tgal if ann_tgal else 0.0
    rates["sewer_rate"] = ann_sc / ann_tgal if ann_tgal else 0.0

    total = ann_ec + ann_dc + ann_efee + ann_gc + ann_gfee + ann_wc + ann_sc + ann_wfee
    rates["total_annual_utility_cost"] = total

    return rates


def get_utility_rates_from_dict(session: dict) -> dict:
    """Same as get_utility_rates() but reads from a plain dict instead of st.session_state."""
    rates = {}

    elec_rows = session.get("elec_rows", [])
    ann_kwh   = sum(r.get("kwh", 0) for r in elec_rows)
    ann_ec    = sum(r.get("elec_cost", 0) for r in elec_rows)
    ann_kw    = sum(r.get("kw", 0) for r in elec_rows)
    ann_dc    = sum(r.get("demand_cost", 0) for r in elec_rows)
    ann_efee  = sum(r.get("fee", 0) for r in elec_rows)
    rates["ann_kwh"]   = ann_kwh
    rates["ann_elec_cost"] = ann_ec
    rates["ann_kw"]    = ann_kw
    rates["ann_demand_cost"] = ann_dc
    rates["ann_elec_fee"] = ann_efee
    rates["elec_rate"] = ann_ec / ann_kwh if ann_kwh else 0.0
    rates["demand_rate"]= ann_dc / ann_kw  if ann_kw  else 0.0

    gas_rows  = session.get("gas_rows", [])
    ann_mmbtu = sum(r.get("mmbtu", 0) for r in gas_rows)
    ann_gc    = sum(r.get("cost", 0) for r in gas_rows)
    ann_gfee  = sum(r.get("fee", 0) for r in gas_rows)
    rates["ann_mmbtu"]  = ann_mmbtu
    rates["ann_gas_cost"]= ann_gc
    rates["ann_gas_fee"] = ann_gfee
    rates["gas_rate"]   = ann_gc / ann_mmbtu if ann_mmbtu else 0.0

    water_rows = session.get("water_rows", [])
    ann_tgal   = sum(r.get("tgal", 0) for r in water_rows)
    ann_wc     = sum(r.get("water_cost", 0) for r in water_rows)
    ann_sc     = sum(r.get("sewer_cost", 0) for r in water_rows)
    ann_wfee   = sum(r.get("fee", 0) for r in water_rows)
    rates["ann_tgal"]   = ann_tgal
    rates["ann_water_cost"]= ann_wc
    rates["ann_sewer_cost"]= ann_sc
    rates["ann_water_fee"] = ann_wfee
    rates["water_rate"] = ann_wc / ann_tgal if ann_tgal else 0.0
    rates["sewer_rate"] = ann_sc / ann_tgal if ann_tgal else 0.0

    total = ann_ec + ann_dc + ann_efee + ann_gc + ann_gfee + ann_wc + ann_sc + ann_wfee
    rates["total_annual_utility_cost"] = total
    return rates
