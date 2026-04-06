"""
ARC 2.2625 — Chilled Water Reset
Uses CoolProp to calculate chiller COP at current vs. proposed supply water temperature.
Estimates kWh savings from raising chilled water supply temperature (CHWST) reset.
"""
try:
    import CoolProp.CoolProp as CP
    COOLPROP_AVAILABLE = True
except ImportError:
    COOLPROP_AVAILABLE = False

import numpy as np


def get_fluid_properties(fluid: str, T_C: float, P_Pa: float = 101325.0) -> dict:
    """
    Return basic thermodynamic properties for a fluid at given temperature.
    T_C: temperature in Celsius
    """
    if not COOLPROP_AVAILABLE:
        raise RuntimeError("CoolProp is not installed.")
    T_K = T_C + 273.15
    props = {}
    try:
        props["h"]     = CP.PropsSI("H", "T", T_K, "P", P_Pa, fluid)   # J/kg enthalpy
        props["rho"]   = CP.PropsSI("D", "T", T_K, "P", P_Pa, fluid)   # kg/m³ density
        props["Cp"]    = CP.PropsSI("C", "T", T_K, "P", P_Pa, fluid)   # J/kg·K specific heat
        props["T_C"]   = T_C
        props["T_K"]   = T_K
    except Exception as e:
        props["error"] = str(e)
    return props


def cop_from_temperatures(
    T_evap_C: float,
    T_cond_C: float,
    cop_fraction: float = 0.6,
) -> float:
    """
    Estimate chiller COP using Carnot COP scaled by a practical fraction.
    cop_fraction: typical real-world = 0.5–0.65 of Carnot
    T_evap_C: evaporator (chilled water) temperature in °C
    T_cond_C: condenser (cooling water/ambient) temperature in °C
    """
    T_evap_K = T_evap_C + 273.15
    T_cond_K = T_cond_C + 273.15
    if T_cond_K <= T_evap_K:
        return 10.0  # degenerate case
    COP_carnot = T_evap_K / (T_cond_K - T_evap_K)
    return COP_carnot * cop_fraction


def compute_chilled_water_savings(
    cooling_load_tons: float,
    hours_operation: float,
    T_chws_current_F: float,
    T_chws_proposed_F: float,
    T_condenser_F: float,
    cop_fraction: float = 0.6,
    elec_rate: float = 0.10,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    Estimate annual chiller kWh savings from raising the CHWST.

    cooling_load_tons: average cooling load in tons
    hours_operation: annual chiller run hours
    T_chws_current_F: current chilled water supply temp (°F)
    T_chws_proposed_F: proposed (higher) CHWST (°F)
    T_condenser_F: condenser water / leaving condenser temp (°F)

    Returns dict with COP values, kW difference, annual kWh savings, cost savings.
    """
    # Convert °F to °C
    def F2C(f): return (f - 32) * 5 / 9

    T_evap_curr_C = F2C(T_chws_current_F)
    T_evap_prop_C = F2C(T_chws_proposed_F)
    T_cond_C      = F2C(T_condenser_F)

    cop_curr = cop_from_temperatures(T_evap_curr_C, T_cond_C, cop_fraction)
    cop_prop = cop_from_temperatures(T_evap_prop_C, T_cond_C, cop_fraction)

    # 1 ton of refrigeration = 12,000 BTU/hr = 3.517 kW
    TONS_TO_KW = 3.517
    cooling_kw = cooling_load_tons * TONS_TO_KW

    kw_current  = cooling_kw / cop_curr
    kw_proposed = cooling_kw / cop_prop
    delta_kw    = kw_current - kw_proposed

    ann_kwh_savings  = delta_kw * hours_operation
    ann_cost_savings = ann_kwh_savings * elec_rate + delta_kw * demand_rate * demand_months

    return {
        "cop_current": cop_curr,
        "cop_proposed": cop_prop,
        "kw_current": kw_current,
        "kw_proposed": kw_proposed,
        "delta_kw": delta_kw,
        "ann_kwh_savings": ann_kwh_savings,
        "ann_cost_savings": ann_cost_savings,
        "T_evap_curr_C": T_evap_curr_C,
        "T_evap_prop_C": T_evap_prop_C,
        "T_cond_C": T_cond_C,
        "cooling_load_tons": cooling_load_tons,
        "hours_operation": hours_operation,
    }


def coolprop_fluid_demo(
    fluid: str = "Water",
    T_in_C: float = 7.0,
    T_out_C: float = 12.0,
    flow_lps: float = 2.0,
) -> dict:
    """
    Compute chilled water loop heat transfer using CoolProp fluid properties.
    T_in_C: supply temp (colder, leaving chiller)
    T_out_C: return temp (warmer, returning from building)
    flow_lps: flow rate in L/s
    Returns load in kW and tons.
    """
    if not COOLPROP_AVAILABLE:
        return {"error": "CoolProp not available"}

    props_in  = get_fluid_properties(fluid, T_in_C)
    props_out = get_fluid_properties(fluid, T_out_C)

    if "error" in props_in or "error" in props_out:
        return {"error": "CoolProp property lookup failed"}

    rho_avg = (props_in["rho"] + props_out["rho"]) / 2  # kg/m³
    Cp_avg  = (props_in["Cp"]  + props_out["Cp"])  / 2  # J/kg·K
    delta_T = T_out_C - T_in_C                           # K

    flow_kg_s = flow_lps * rho_avg / 1000.0              # kg/s (since 1 L = 0.001 m³)
    Q_kw      = flow_kg_s * Cp_avg * delta_T / 1000.0    # kW
    Q_tons    = Q_kw / 3.517

    return {
        "Q_kw": Q_kw,
        "Q_tons": Q_tons,
        "flow_kg_s": flow_kg_s,
        "rho_avg": rho_avg,
        "Cp_avg": Cp_avg,
        "delta_T": delta_T,
        "T_in_C": T_in_C,
        "T_out_C": T_out_C,
    }
