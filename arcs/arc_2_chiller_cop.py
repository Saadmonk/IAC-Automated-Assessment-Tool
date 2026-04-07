"""
arcs/arc_2_chiller_cop.py
Chiller COP calculation engine — three input modes.
Uses CoolProp for refrigerant thermodynamic properties.

Mode A — Pressures known (suction + discharge gauge pressures)
Mode B — Water temps known (CHW supply/return + condenser water supply/return + flow rate)
Mode C — kW known (compressor kW + CHW flow + delta T)

Also computes COP_Carnot and second-law efficiency.
"""

import math
from typing import Optional

try:
    from CoolProp.CoolProp import PropsSI
    COOLPROP_OK = True
except ImportError:
    COOLPROP_OK = False


REFRIGERANTS = {
    "R-22":   "R22",
    "R-134a": "R134a",
    "R-410A": "R410A",
    "R-404A": "R404A",
    "R-407C": "R407C",
    "R-507A": "R507A",
    "R-717 (Ammonia)": "Ammonia",
}

# Convert psig → Pa absolute
PSIG_TO_PA = 6894.757
ATM_PA = 101325.0


def psig_to_pa(psig: float) -> float:
    return (psig * PSIG_TO_PA) + ATM_PA


def _enthalpy_sat_vapor(refrigerant: str, pressure_pa: float) -> float:
    """Enthalpy of saturated vapor at given pressure [J/kg]."""
    return PropsSI("H", "P", pressure_pa, "Q", 1.0, refrigerant)


def _enthalpy_sat_liquid(refrigerant: str, pressure_pa: float) -> float:
    """Enthalpy of saturated liquid at given pressure [J/kg]."""
    return PropsSI("H", "P", pressure_pa, "Q", 0.0, refrigerant)


def _sat_temp_from_pressure(refrigerant: str, pressure_pa: float) -> float:
    """Saturation temperature [°F] at given absolute pressure [Pa]."""
    T_K = PropsSI("T", "P", pressure_pa, "Q", 0.5, refrigerant)
    return (T_K - 273.15) * 9 / 5 + 32


def _isentropic_enthalpy(refrigerant: str, p_suction_pa: float, p_discharge_pa: float,
                          h1: float, s1: float) -> float:
    """Isentropic compressor exit enthalpy [J/kg]."""
    return PropsSI("H", "P", p_discharge_pa, "S", s1, refrigerant)


# ── Mode A: Pressures Known ───────────────────────────────────────────────────

def cop_from_pressures(
    refrigerant_name: str,
    suction_pressure_psig: float,
    discharge_pressure_psig: float,
    isentropic_efficiency: float = 0.70,
    superheat_f: float = 10.0,
    subcooling_f: float = 5.0,
) -> dict:
    """
    Compute actual COP and Carnot COP from refrigerant pressures.

    State points (standard vapor compression cycle):
      1 — Compressor inlet (saturated vapor + superheat)
      2s — Isentropic compressor exit
      2 — Actual compressor exit (with isentropic efficiency)
      3 — Condenser exit (saturated liquid + subcooling)
      4 — Expansion valve exit (isenthalpic)
    """
    if not COOLPROP_OK:
        return {"error": "CoolProp not installed"}

    ref = REFRIGERANTS.get(refrigerant_name, refrigerant_name)
    p1_pa = psig_to_pa(suction_pressure_psig)
    p2_pa = psig_to_pa(discharge_pressure_psig)

    try:
        # Point 1: superheated vapor at suction
        T_sat_evap_K = PropsSI("T", "P", p1_pa, "Q", 1.0, ref)
        T1_K = T_sat_evap_K + superheat_f * 5 / 9
        h1 = PropsSI("H", "T", T1_K, "P", p1_pa, ref)
        s1 = PropsSI("S", "T", T1_K, "P", p1_pa, ref)

        # Point 2s: isentropic compression
        h2s = PropsSI("H", "P", p2_pa, "S", s1, ref)

        # Point 2: actual compression
        h2 = h1 + (h2s - h1) / isentropic_efficiency

        # Point 3: subcooled liquid at condenser exit
        T_sat_cond_K = PropsSI("T", "P", p2_pa, "Q", 0.0, ref)
        T3_K = T_sat_cond_K - subcooling_f * 5 / 9
        h3 = PropsSI("H", "T", T3_K, "P", p2_pa, ref)

        # Point 4: after expansion valve (isenthalpic)
        h4 = h3

        # COP actual
        q_evap = h1 - h4       # cooling effect [J/kg]
        w_comp = h2 - h1       # compressor work [J/kg]
        cop_actual = q_evap / w_comp if w_comp > 0 else 0

        # Carnot COP
        T_evap_K = T_sat_evap_K
        T_cond_K = T_sat_cond_K
        cop_carnot = T_evap_K / (T_cond_K - T_evap_K) if (T_cond_K - T_evap_K) > 0 else 0

        T_evap_f = (T_evap_K - 273.15) * 9 / 5 + 32
        T_cond_f = (T_cond_K - 273.15) * 9 / 5 + 32

        return {
            "mode": "A — Pressures",
            "refrigerant": refrigerant_name,
            "cop_actual": round(cop_actual, 3),
            "cop_carnot": round(cop_carnot, 3),
            "second_law_efficiency": round(cop_actual / cop_carnot * 100, 1) if cop_carnot > 0 else 0,
            "T_evap_f": round(T_evap_f, 1),
            "T_cond_f": round(T_cond_f, 1),
            "h1_btu_lb": round(h1 * 0.000430, 2),
            "h2_btu_lb": round(h2 * 0.000430, 2),
            "h3_btu_lb": round(h3 * 0.000430, 2),
            "h4_btu_lb": round(h3 * 0.000430, 2),
            "w_comp_btu_lb": round(w_comp * 0.000430, 2),
            "q_evap_btu_lb": round(q_evap * 0.000430, 2),
            "suction_sat_temp_f": round(T_evap_f, 1),
            "discharge_sat_temp_f": round(T_cond_f, 1),
        }
    except Exception as e:
        return {"error": f"CoolProp error: {e}"}


# ── Mode B: Water Temperatures Known ─────────────────────────────────────────

def cop_from_water_temps(
    chw_supply_f: float,
    chw_return_f: float,
    chw_flow_gpm: float,
    cond_supply_f: float,    # condenser water supply (entering)
    cond_return_f: float,    # condenser water return (leaving)
    refrigerant_name: Optional[str] = None,
    isentropic_efficiency: float = 0.70,
) -> dict:
    """
    Compute actual COP from chilled water and condenser water measurements.
    COP = Q_cooling / W_compressor
    Q_cooling = m_dot × Cp × delta_T (water side)
    W_compressor = Q_condenser - Q_cooling (energy balance)
    Q_condenser derived from condenser water delta_T if flow known,
    otherwise from energy balance: W = Q_cond - Q_evap
    """
    # Cooling capacity from chilled water side
    rho_water = 8.334  # lb/gal
    Cp_water = 1.0     # BTU/(lb·°F)
    delta_T_chw = chw_return_f - chw_supply_f
    q_cooling_btu_hr = chw_flow_gpm * rho_water * 60 * Cp_water * delta_T_chw  # BTU/hr
    q_cooling_tons = q_cooling_btu_hr / 12000

    # Evaporator temperature ≈ CHWS - 5°F (approach temp)
    T_evap_f = chw_supply_f - 5.0
    T_evap_K = (T_evap_f - 32) * 5 / 9 + 273.15

    # Condensing temperature ≈ condenser water leaving + 5°F (approach)
    T_cond_f = cond_return_f + 5.0
    T_cond_K = (T_cond_f - 32) * 5 / 9 + 273.15

    # Carnot COP
    cop_carnot = T_evap_K / (T_cond_K - T_evap_K) if (T_cond_K - T_evap_K) > 0 else 0

    # If refrigerant known, use CoolProp for better COP estimate
    cop_actual = None
    cop_note = ""
    if refrigerant_name and COOLPROP_OK:
        ref = REFRIGERANTS.get(refrigerant_name, refrigerant_name)
        try:
            p_evap = PropsSI("P", "T", T_evap_K, "Q", 1.0, ref)
            p_cond = PropsSI("P", "T", T_cond_K, "Q", 0.0, ref)
            result = cop_from_pressures(
                refrigerant_name, (p_evap - ATM_PA) / PSIG_TO_PA,
                (p_cond - ATM_PA) / PSIG_TO_PA, isentropic_efficiency
            )
            if "error" not in result:
                cop_actual = result["cop_actual"]
                cop_note = "CoolProp state-point calculation"
        except Exception:
            pass

    if cop_actual is None:
        # Estimate using Carnot × typical second-law efficiency (~55–65% for centrifugal chillers)
        cop_actual = cop_carnot * 0.60
        cop_note = "Estimated (Carnot × 60% second-law efficiency — enter refrigerant for accuracy)"

    return {
        "mode": "B — Water Temperatures",
        "cop_actual": round(cop_actual, 3),
        "cop_carnot": round(cop_carnot, 3),
        "second_law_efficiency": round(cop_actual / cop_carnot * 100, 1) if cop_carnot > 0 else 0,
        "q_cooling_tons": round(q_cooling_tons, 1),
        "q_cooling_btu_hr": round(q_cooling_btu_hr, 0),
        "T_evap_f": round(T_evap_f, 1),
        "T_cond_f": round(T_cond_f, 1),
        "chw_delta_t": round(delta_T_chw, 1),
        "note": cop_note,
    }


# ── Mode C: Compressor kW + CHW Flow Known ────────────────────────────────────

def cop_from_kw(
    compressor_kw: float,
    chw_supply_f: float,
    chw_return_f: float,
    chw_flow_gpm: float,
    cond_supply_f: Optional[float] = None,
    cond_return_f: Optional[float] = None,
) -> dict:
    """
    COP = Q_cooling / W_compressor
    Q_cooling = CHW flow × Cp × delta_T (BTU/hr) → kW
    W_compressor = measured kW
    """
    rho_water = 8.334
    Cp_water = 1.0
    delta_T_chw = chw_return_f - chw_supply_f
    q_cooling_btu_hr = chw_flow_gpm * rho_water * 60 * Cp_water * delta_T_chw
    q_cooling_kw = q_cooling_btu_hr / 3412.14
    q_cooling_tons = q_cooling_btu_hr / 12000

    cop_actual = q_cooling_kw / compressor_kw if compressor_kw > 0 else 0

    # Carnot
    T_evap_f = chw_supply_f - 5.0
    T_evap_K = (T_evap_f - 32) * 5 / 9 + 273.15
    if cond_return_f:
        T_cond_f = cond_return_f + 5.0
    else:
        T_cond_f = T_evap_f + (q_cooling_kw + compressor_kw) / q_cooling_kw * 20
    T_cond_K = (T_cond_f - 32) * 5 / 9 + 273.15
    cop_carnot = T_evap_K / (T_cond_K - T_evap_K) if (T_cond_K - T_evap_K) > 0 else 0

    kw_per_ton = compressor_kw / q_cooling_tons if q_cooling_tons > 0 else 0

    return {
        "mode": "C — Compressor kW + CHW Flow",
        "cop_actual": round(cop_actual, 3),
        "cop_carnot": round(cop_carnot, 3),
        "second_law_efficiency": round(cop_actual / cop_carnot * 100, 1) if cop_carnot > 0 else 0,
        "q_cooling_tons": round(q_cooling_tons, 1),
        "q_cooling_kw": round(q_cooling_kw, 1),
        "kw_per_ton": round(kw_per_ton, 3),
        "T_evap_f": round(T_evap_f, 1),
        "T_cond_f": round(T_cond_f, 1),
        "chw_delta_t": round(delta_T_chw, 1),
    }


# ── Setpoint Change Savings ───────────────────────────────────────────────────

def chiller_setpoint_savings(
    cop_current: float,
    cop_proposed: float,
    compressor_kw_current: float,
    operating_hours: float,
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    Calculate savings from CHWST or setpoint change that improves COP.

    Logic (from your description):
    1. Cooling load = compressor_kw_current × COP_current  (kW cooling)
    2. New compressor kW = cooling_load / COP_proposed
    3. Savings = (kW_current - kW_proposed) × operating_hours
    """
    cooling_load_kw = compressor_kw_current * cop_current
    kw_proposed = cooling_load_kw / cop_proposed if cop_proposed > 0 else compressor_kw_current
    delta_kw = compressor_kw_current - kw_proposed

    ann_kwh = delta_kw * operating_hours
    ann_demand = delta_kw * demand_rate * demand_months
    ann_cost = ann_kwh * elec_rate + ann_demand

    return {
        "cooling_load_kw": round(cooling_load_kw, 1),
        "cooling_load_tons": round(cooling_load_kw * 3412 / 12000, 1),
        "kw_current": round(compressor_kw_current, 1),
        "kw_proposed": round(kw_proposed, 1),
        "delta_kw": round(delta_kw, 1),
        "ann_kwh_savings": round(ann_kwh, 0),
        "ann_demand_savings_kw_mo": round(delta_kw * demand_months, 1),
        "ann_cost_savings": round(ann_cost, 0),
        "pct_reduction": round(delta_kw / compressor_kw_current * 100, 1) if compressor_kw_current > 0 else 0,
    }
