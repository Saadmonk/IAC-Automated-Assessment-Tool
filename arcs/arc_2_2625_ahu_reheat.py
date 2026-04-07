"""
arcs/arc_2_2625_ahu_reheat.py
ARC 2.2625 — Raise chilled water supply temperature / supply air temperature setpoint.

Methodology matches Report LT8438 (hospital facility):
- System draws outdoor air, cools it to supply air temp (SAT), then reheats to zone temp
- Raising SAT setpoint reduces both cooling energy AND reheat gas energy
- Calculation is hourly: for each hour where OAT > existing SAT, cooling and reheat occur
- Annual savings = sum over all hours of (reheat_saved + cooling_saved)

Inputs:
- Hourly outdoor air temperature (from Open-Meteo)
- Existing SAT (supply air temperature) setpoint °F
- Proposed SAT setpoint °F (higher = less cooling + less reheat)
- Zone/reheat temperature °F (final supply temp after reheat)
- Floor area ft², ceiling height ft
- Air change rate per hour (ACH)
- Outside air fraction (OAF)
- Boiler efficiency (for gas reheat)
- Chiller COP (for cooling electricity)
"""

import numpy as np
import pandas as pd

# Constants
DENSITY_AIR_LB_CFT = 0.075        # lb/ft³ at standard conditions
CP_AIR_BTU_LB_F   = 0.24          # BTU/(lb·°F)
HV_GAS_BTU_CCF    = 1020          # BTU/ccf (natural gas higher heating value)
HV_GAS_BTU_MMBTU  = 1_000_000     # 1 MMBtu = 1,000,000 BTU
KWH_PER_BTU       = 1 / 3412.14


def compute_ahu_reheat_savings(
    df_hourly: pd.DataFrame,         # columns: datetime, temp_f
    sat_existing_f: float,           # existing supply air temp setpoint °F
    sat_proposed_f: float,           # proposed supply air temp setpoint °F  (higher)
    reheat_temp_f: float,            # zone/reheat temp setpoint °F
    floor_area_ft2: float,
    ceiling_height_ft: float,
    ach: float,                      # air changes per hour
    outside_air_fraction: float,     # fraction of supply air that is outside air (0–1)
    boiler_efficiency: float,        # fractional (0.8–0.95 for condensing boiler)
    chiller_cop: float,              # chiller COP for cooling electricity savings
    gas_rate: float,                 # $/MMBtu
    elec_rate: float,                # $/kWh
    facility_area_fraction: float = 1.0,  # fraction of total facility assessed
) -> dict:
    """
    Compute hourly savings from raising supply air temperature setpoint.
    Returns annual savings dict and per-hour DataFrame.
    """
    # Total volume and airflow
    total_volume_cft = floor_area_ft2 * ceiling_height_ft
    airflow_cft_hr = total_volume_cft * ach           # ft³/hr
    mass_flow_lb_hr = airflow_cft_hr * DENSITY_AIR_LB_CFT  # lb/hr

    # Outside air mass flow
    oa_mass_flow = mass_flow_lb_hr * outside_air_fraction   # lb/hr

    rows = []
    for _, row in df_hourly.iterrows():
        oat = float(row["temp_f"])

        # ── Reheat savings ─────────────────────────────────────────────────────
        # Existing: reheat from sat_existing to reheat_temp
        # Proposed: reheat from sat_proposed to reheat_temp (less reheat needed)
        # Reheat only occurs when OAT ≤ SAT (cooling not needed for this fraction)
        # For OAT > SAT: no reheat needed (already above SAT)

        # For heating demand: air supplied at SAT must be reheated to reheat_temp
        # existing reheat load [BTU/hr] = ṁ_oa × Cp × (reheat_temp - sat_existing)
        # proposed reheat load [BTU/hr] = ṁ_oa × Cp × (reheat_temp - sat_proposed)
        # Δreheat [BTU/hr] = ṁ_oa × Cp × (sat_proposed - sat_existing)

        delta_reheat_btu_hr = oa_mass_flow * CP_AIR_BTU_LB_F * (sat_proposed_f - sat_existing_f)
        # Only positive savings when proposed > existing (less gas needed)
        delta_reheat_btu_hr = max(delta_reheat_btu_hr, 0.0)

        # ── Cooling savings ────────────────────────────────────────────────────
        # When OAT > sat_existing: cooling is needed to bring OAT down to SAT
        # existing cooling load: cool OA from OAT to sat_existing
        # proposed cooling load: cool OA from OAT to sat_proposed (less cooling)
        # Δcooling [BTU/hr] = ṁ_oa × Cp × (sat_proposed - sat_existing)
        # Only when OAT > sat_proposed (if OAT ≤ sat_existing, cooling needed for existing but not proposed)

        if oat > sat_proposed_f:
            # Both existing and proposed need cooling, but proposed needs less
            delta_cool_btu_hr = oa_mass_flow * CP_AIR_BTU_LB_F * (sat_proposed_f - sat_existing_f)
        elif oat > sat_existing_f:
            # Only existing needs cooling; proposed does not
            delta_cool_btu_hr = oa_mass_flow * CP_AIR_BTU_LB_F * (oat - sat_existing_f)
        else:
            delta_cool_btu_hr = 0.0
        delta_cool_btu_hr = max(delta_cool_btu_hr, 0.0)

        # Gas saved [MMBtu/hr] = delta_reheat_btu / (boiler_eff × 1e6)
        gas_saved_mmbtu_hr = delta_reheat_btu_hr / (boiler_efficiency * HV_GAS_BTU_MMBTU)

        # Electricity saved [kWh/hr] = delta_cool [BTU/hr] / (COP × 3412 BTU/kWh)
        elec_saved_kwh_hr = delta_cool_btu_hr / (chiller_cop * 3412.14)

        rows.append({
            "datetime": row.get("datetime"),
            "oat_f": oat,
            "delta_reheat_btu_hr": round(delta_reheat_btu_hr, 2),
            "delta_cool_btu_hr": round(delta_cool_btu_hr, 2),
            "gas_saved_mmbtu_hr": round(gas_saved_mmbtu_hr, 6),
            "elec_saved_kwh_hr": round(elec_saved_kwh_hr, 4),
        })

    df_out = pd.DataFrame(rows)

    ann_gas_mmbtu = float(df_out["gas_saved_mmbtu_hr"].sum())
    ann_elec_kwh  = float(df_out["elec_saved_kwh_hr"].sum())

    # Apply area fraction (only assessed portion of facility)
    ann_gas_mmbtu *= facility_area_fraction
    ann_elec_kwh  *= facility_area_fraction

    ann_gas_cost  = ann_gas_mmbtu * gas_rate
    ann_elec_cost = ann_elec_kwh * elec_rate
    ann_total     = ann_gas_cost + ann_elec_cost

    return {
        "ann_gas_mmbtu_savings": round(ann_gas_mmbtu, 2),
        "ann_elec_kwh_savings": round(ann_elec_kwh, 0),
        "ann_gas_cost_savings": round(ann_gas_cost, 0),
        "ann_elec_cost_savings": round(ann_elec_cost, 0),
        "ann_total_cost_savings": round(ann_total, 0),
        "airflow_cfm": round(airflow_cft_hr / 60, 0),
        "oa_mass_flow_lb_hr": round(oa_mass_flow, 0),
        "sat_existing_f": sat_existing_f,
        "sat_proposed_f": sat_proposed_f,
        "delta_sat_f": sat_proposed_f - sat_existing_f,
        "facility_area_fraction": facility_area_fraction,
        "hourly_df": df_out,
        "monthly_summary": _monthly_summary(df_out, facility_area_fraction, gas_rate, elec_rate),
    }


def _monthly_summary(df: pd.DataFrame, area_frac: float, gas_rate: float, elec_rate: float) -> pd.DataFrame:
    if "datetime" not in df.columns or df["datetime"].isna().all():
        return pd.DataFrame()
    df2 = df.copy()
    df2["month"] = pd.to_datetime(df2["datetime"]).dt.month
    monthly = df2.groupby("month").agg(
        gas_mmbtu=("gas_saved_mmbtu_hr", "sum"),
        elec_kwh=("elec_saved_kwh_hr", "sum"),
    ).reset_index()
    monthly["gas_mmbtu"] *= area_frac
    monthly["elec_kwh"] *= area_frac
    monthly["gas_cost"] = monthly["gas_mmbtu"] * gas_rate
    monthly["elec_cost"] = monthly["elec_kwh"] * elec_rate
    monthly["total_cost"] = monthly["gas_cost"] + monthly["elec_cost"]
    month_names = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                   7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    monthly["month_name"] = monthly["month"].map(month_names)
    return monthly


def compute_ahu_sample_hours(
    oat_list: list[float],
    sat_existing_f: float,
    sat_proposed_f: float,
    reheat_temp_f: float,
    oa_mass_flow_lb_hr: float,
    boiler_efficiency: float,
    chiller_cop: float,
) -> list[dict]:
    """
    Compute savings for a list of OAT values — used for showing sample calculations.
    """
    results = []
    for oat in oat_list:
        dr = oa_mass_flow_lb_hr * CP_AIR_BTU_LB_F * (sat_proposed_f - sat_existing_f)
        dr = max(dr, 0.0)
        if oat > sat_proposed_f:
            dc = oa_mass_flow_lb_hr * CP_AIR_BTU_LB_F * (sat_proposed_f - sat_existing_f)
        elif oat > sat_existing_f:
            dc = oa_mass_flow_lb_hr * CP_AIR_BTU_LB_F * (oat - sat_existing_f)
        else:
            dc = 0.0
        dc = max(dc, 0.0)
        gas = dr / (boiler_efficiency * HV_GAS_BTU_MMBTU)
        elec = dc / (chiller_cop * 3412.14)
        results.append({
            "oat_f": oat,
            "delta_reheat_btu_hr": round(dr, 1),
            "delta_cool_btu_hr": round(dc, 1),
            "gas_saved_mmbtu_hr": round(gas, 6),
            "elec_saved_kwh_hr": round(elec, 4),
        })
    return results
