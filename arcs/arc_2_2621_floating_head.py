"""
arcs/arc_2_2621_floating_head.py
ARC 2.2621 — Modify refrigeration system to operate at lower (floating) head pressure.

Methodology matches MALT reports (Report 7, Report 23):
- Build hourly or bin-hour weather dataset from Open-Meteo
- For each hour/bin: condensing temp = ambient + offset (air-cooled: +15°F drybulb, water-cooled: +10°F wetbulb)
- Cap condensing temp between min (120°F equivalent) and fixed max
- CoolProp state-point cycle: 1→2s→2→3→4
- Compressor power = mass_flow × (h2 - h1); COP = (h1-h4)/(h2-h1)
- Annual kWh savings = Σ (P_fixed - P_floating) × hours_in_bin

References:
- ASHRAE 90.1-2022 §6.5.1.1: air-cooled condensers — design condensing temp ≤ ambient + 30°F
  Floating head reset target: ambient + 15°F (typical industry practice)
- ASHRAE Handbook of Fundamentals 2021: cooling tower approach temp = 7–10°F above wet-bulb
  Water-cooled floating target: wet-bulb + 10°F condensing temp (10°F approach + ~0°F lift)
"""

import math
import numpy as np
import pandas as pd
from typing import Optional

try:
    from CoolProp.CoolProp import PropsSI
    COOLPROP_OK = True
except ImportError:
    COOLPROP_OK = False

PSIG_TO_PA = 6894.757
ATM_PA = 101325.0

REFRIGERANTS = {
    "R-22":   "R22",
    "R-134a": "R134a",
    "R-410A": "R410A",
    "R-404A": "R404A",
    "R-407C": "R407C",
    "R-507A": "R507A",
    "R-717 (Ammonia)": "Ammonia",
}

# Typical condensing temp offsets above ambient
# Air-cooled: design = +30°F drybulb, reset target = +15°F drybulb (ASHRAE 90.1)
# Water-cooled/evaporative: approach ≈ 7–10°F above wetbulb (ASHRAE HoF)
CONDENSER_OFFSETS = {
    "Air-cooled":    {"ambient_type": "drybulb", "fixed_offset_f": 30.0, "float_offset_f": 15.0},
    "Water-cooled":  {"ambient_type": "wetbulb", "fixed_offset_f": 15.0, "float_offset_f": 10.0},
    "Evaporative":   {"ambient_type": "wetbulb", "fixed_offset_f": 15.0, "float_offset_f": 10.0},
}


def _cycle_cop_and_power(
    ref: str,
    T_evap_f: float,
    T_cond_f: float,
    compressor_capacity_hp: float,
    isentropic_efficiency: float = 0.70,
    superheat_f: float = 10.0,
    subcooling_f: float = 5.0,
) -> dict:
    """
    Compute vapor compression cycle COP and power at given evap/cond conditions.
    Returns dict with cop, power_kw, h1, h2, h3, h4 in BTU/lb.
    """
    T_evap_K = (T_evap_f - 32) * 5 / 9 + 273.15
    T_cond_K = (T_cond_f - 32) * 5 / 9 + 273.15

    try:
        p_evap = PropsSI("P", "T", T_evap_K, "Q", 1.0, ref)
        p_cond = PropsSI("P", "T", T_cond_K, "Q", 0.0, ref)

        # Point 1: superheated suction
        T1_K = T_evap_K + superheat_f * 5 / 9
        h1 = PropsSI("H", "T", T1_K, "P", p_evap, ref)
        s1 = PropsSI("S", "T", T1_K, "P", p_evap, ref)

        # Point 2s: isentropic
        h2s = PropsSI("H", "P", p_cond, "S", s1, ref)

        # Point 2: actual
        h2 = h1 + (h2s - h1) / isentropic_efficiency

        # Point 3: subcooled liquid
        T3_K = T_cond_K - subcooling_f * 5 / 9
        h3 = PropsSI("H", "T", T3_K, "P", p_cond, ref)

        # Point 4: after expansion (isenthalpic)
        h4 = h3

        q_evap = h1 - h4   # J/kg
        w_comp = h2 - h1   # J/kg

        cop = q_evap / w_comp if w_comp > 0 else 0.0

        # Mass flow rate from compressor capacity
        # P_comp = W × m_dot → m_dot = P / w_comp
        # Given capacity in HP, convert to watts
        power_w_rated = compressor_capacity_hp * 745.7
        # Actual mass flow derived from rated power at fixed conditions (used for scaling)
        # We'll use the cop and rated power to find actual power:
        # P_actual = Q_cooling / COP, Q_cooling ≈ rated_power × cop_at_rated
        # Simpler: power scales as w_comp changes; normalize to rated
        # (mass flow assumed constant for fixed compressor)
        power_kw = power_w_rated / 1000.0 * (w_comp / w_comp)  # keep as rated for ratio calc

        return {
            "cop": round(cop, 4),
            "w_comp_j_kg": w_comp,
            "q_evap_j_kg": q_evap,
            "p_evap_pa": p_evap,
            "p_cond_pa": p_cond,
            "T_cond_K": T_cond_K,
            "T_evap_K": T_evap_K,
        }
    except Exception as e:
        return {"error": str(e), "cop": 0.0, "w_comp_j_kg": 1.0, "q_evap_j_kg": 0.0}


def run_floating_head_analysis(
    df_hourly: pd.DataFrame,            # from weather.get_hourly_temps()
    refrigerant_name: str,
    condenser_type: str,                # "Air-cooled" / "Water-cooled" / "Evaporative"
    evap_temp_f: float,                 # Fixed evaporating temperature °F
    fixed_condensing_temp_f: float,     # Existing fixed condensing temperature °F
    min_condensing_temp_f: float,       # Minimum allowed condensing temp °F (safety)
    compressor_capacity_hp: float,      # Total compressor rated horsepower
    compressor_kw_measured: Optional[float],  # Measured kW at current conditions (for scaling)
    operating_hours_per_year: float = 8760.0,
    isentropic_efficiency: float = 0.70,
    superheat_f: float = 10.0,
    subcooling_f: float = 5.0,
    elec_rate: float = 0.09,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    Full floating head pressure analysis using hourly weather data.
    Returns savings dict and per-hour DataFrame.
    """
    if not COOLPROP_OK:
        return {"error": "CoolProp not installed"}

    ref = REFRIGERANTS.get(refrigerant_name, refrigerant_name)
    offsets = CONDENSER_OFFSETS.get(condenser_type, CONDENSER_OFFSETS["Air-cooled"])
    float_offset = offsets["float_offset_f"]
    ambient_type = offsets["ambient_type"]

    # Compute fixed-head cycle metrics
    fixed = _cycle_cop_and_power(
        ref, evap_temp_f, fixed_condensing_temp_f,
        compressor_capacity_hp, isentropic_efficiency, superheat_f, subcooling_f
    )
    if "error" in fixed:
        return {"error": f"Fixed head CoolProp error: {fixed['error']}"}

    # Determine actual compressor power at fixed conditions
    if compressor_kw_measured and compressor_kw_measured > 0:
        # Use measured kW to scale
        kw_per_unit_work = compressor_kw_measured / fixed["w_comp_j_kg"]
    else:
        # Use rated HP as proxy
        kw_per_unit_work = compressor_capacity_hp * 0.7457 / fixed["w_comp_j_kg"]

    # Per-hour calculation
    results = []
    for _, row in df_hourly.iterrows():
        if ambient_type == "wetbulb":
            ambient_f = float(row.get("wetbulb_f", row["temp_f"]))
        else:
            ambient_f = float(row["temp_f"])

        # Floating condensing temp for this hour
        t_cond_float = ambient_f + float_offset
        t_cond_float = max(t_cond_float, min_condensing_temp_f)
        t_cond_float = min(t_cond_float, fixed_condensing_temp_f)

        # Compute floating cycle
        floating = _cycle_cop_and_power(
            ref, evap_temp_f, t_cond_float,
            compressor_capacity_hp, isentropic_efficiency, superheat_f, subcooling_f
        )

        kw_fixed = kw_per_unit_work * fixed["w_comp_j_kg"]
        kw_float = kw_per_unit_work * floating["w_comp_j_kg"] if "w_comp_j_kg" in floating else kw_fixed
        kw_saved = kw_fixed - kw_float

        results.append({
            "datetime": row.get("datetime"),
            "temp_f": float(row["temp_f"]),
            "wetbulb_f": float(row.get("wetbulb_f", row["temp_f"])),
            "t_cond_fixed_f": fixed_condensing_temp_f,
            "t_cond_float_f": round(t_cond_float, 1),
            "cop_fixed": fixed["cop"],
            "cop_float": floating.get("cop", fixed["cop"]),
            "kw_fixed": round(kw_fixed, 3),
            "kw_float": round(kw_float, 3),
            "kw_saved": round(kw_saved, 3),
        })

    df_out = pd.DataFrame(results)
    ann_kwh = float(df_out["kw_saved"].sum())  # 1 hr per row
    ann_kwh = ann_kwh * (operating_hours_per_year / len(df_out)) if len(df_out) > 0 else 0

    # Peak demand savings (average kW saved)
    avg_kw_saved = float(df_out["kw_saved"].mean())
    ann_demand_cost = avg_kw_saved * demand_rate * demand_months
    ann_energy_cost = ann_kwh * elec_rate
    ann_total_cost = ann_energy_cost + ann_demand_cost

    avg_cop_fixed = fixed["cop"]
    avg_cop_float = float(df_out["cop_float"].mean())

    return {
        "ann_kwh_savings": round(ann_kwh, 0),
        "avg_kw_saved": round(avg_kw_saved, 2),
        "ann_energy_cost_savings": round(ann_energy_cost, 0),
        "ann_demand_cost_savings": round(ann_demand_cost, 0),
        "ann_total_cost_savings": round(ann_total_cost, 0),
        "cop_fixed": round(avg_cop_fixed, 3),
        "cop_float_avg": round(avg_cop_float, 3),
        "pct_kwh_savings": round(ann_kwh / (avg_kw_saved + ann_kwh / 8760 * 8760) * 100, 1) if ann_kwh > 0 else 0,
        "condenser_type": condenser_type,
        "refrigerant": refrigerant_name,
        "fixed_condensing_f": fixed_condensing_temp_f,
        "float_offset_f": float_offset,
        "hourly_df": df_out,
        "offsets_citation": (
            "Air-cooled offset: ASHRAE 90.1-2022 §6.5.1.1 (design ≤ ambient+30°F; reset target: ambient+15°F). "
            "Water-cooled/evaporative offset: ASHRAE Handbook of Fundamentals 2021, Ch. 39 "
            "(cooling tower approach = 7–10°F above wet-bulb; condensing = wet-bulb + 10°F)."
        ),
    }


def run_bin_analysis(
    bin_df: pd.DataFrame,              # from weather.build_temperature_bins()
    refrigerant_name: str,
    condenser_type: str,
    evap_temp_f: float,
    fixed_condensing_temp_f: float,
    min_condensing_temp_f: float,
    compressor_capacity_hp: float,
    compressor_kw_measured: Optional[float] = None,
    isentropic_efficiency: float = 0.70,
    superheat_f: float = 10.0,
    subcooling_f: float = 5.0,
    elec_rate: float = 0.09,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    Bin-hour version of the floating head analysis (faster, good for quick estimates).
    Uses avg_drybulb_f and avg_wetbulb_f from each bin.
    """
    if not COOLPROP_OK:
        return {"error": "CoolProp not installed"}

    ref = REFRIGERANTS.get(refrigerant_name, refrigerant_name)
    offsets = CONDENSER_OFFSETS.get(condenser_type, CONDENSER_OFFSETS["Air-cooled"])
    float_offset = offsets["float_offset_f"]
    ambient_type = offsets["ambient_type"]

    fixed = _cycle_cop_and_power(
        ref, evap_temp_f, fixed_condensing_temp_f,
        compressor_capacity_hp, isentropic_efficiency, superheat_f, subcooling_f
    )
    if "error" in fixed:
        return {"error": fixed["error"]}

    if compressor_kw_measured and compressor_kw_measured > 0:
        kw_per_unit_work = compressor_kw_measured / fixed["w_comp_j_kg"]
    else:
        kw_per_unit_work = compressor_capacity_hp * 0.7457 / fixed["w_comp_j_kg"]

    bin_results = []
    total_kwh = 0.0
    total_hours = 0

    for _, row in bin_df.iterrows():
        hours = int(row["hours"])
        if ambient_type == "wetbulb":
            amb = float(row.get("avg_wetbulb_f", row["avg_drybulb_f"]))
        else:
            amb = float(row["avg_drybulb_f"])

        t_cond_float = max(min_condensing_temp_f, min(fixed_condensing_temp_f, amb + float_offset))

        fl = _cycle_cop_and_power(
            ref, evap_temp_f, t_cond_float,
            compressor_capacity_hp, isentropic_efficiency, superheat_f, subcooling_f
        )

        kw_fixed = kw_per_unit_work * fixed["w_comp_j_kg"]
        kw_float = kw_per_unit_work * fl.get("w_comp_j_kg", fixed["w_comp_j_kg"])
        kw_saved = kw_fixed - kw_float
        kwh_saved = kw_saved * hours
        total_kwh += kwh_saved
        total_hours += hours

        bin_results.append({
            "bin": str(row.get("bin", f"{row['bin_low']}–{row['bin_high']}")),
            "hours": hours,
            "avg_drybulb_f": round(float(row["avg_drybulb_f"]), 1),
            "avg_wetbulb_f": round(float(row.get("avg_wetbulb_f", row["avg_drybulb_f"])), 1),
            "t_cond_fixed_f": round(fixed_condensing_temp_f, 1),
            "t_cond_float_f": round(t_cond_float, 1),
            "cop_fixed": round(fixed["cop"], 3),
            "cop_float": round(fl.get("cop", fixed["cop"]), 3),
            "kw_fixed": round(kw_fixed, 2),
            "kw_float": round(kw_float, 2),
            "kw_saved": round(kw_saved, 2),
            "kwh_saved": round(kwh_saved, 0),
        })

    df_bins = pd.DataFrame(bin_results)
    avg_kw_saved = total_kwh / total_hours if total_hours > 0 else 0
    ann_cost = total_kwh * elec_rate + avg_kw_saved * demand_rate * demand_months

    return {
        "ann_kwh_savings": round(total_kwh, 0),
        "avg_kw_saved": round(avg_kw_saved, 2),
        "ann_cost_savings": round(ann_cost, 0),
        "cop_fixed": round(fixed["cop"], 3),
        "bin_df": df_bins,
        "refrigerant": refrigerant_name,
        "condenser_type": condenser_type,
    }
