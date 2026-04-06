"""
ARC 2.4236 — Fix Compressed Air Leaks
Estimate compressor energy loss from unrepaired air leaks.
"""
import numpy as np


def leak_flow_cfm(
    hole_diameter_in: float,
    pressure_psig: float,
    discharge_coeff: float = 0.65,
) -> float:
    """
    Estimate air leak flow rate (CFM) through an orifice.
    Based on isentropic orifice flow (choked flow assumption for typical shop air > 15 psig).

    hole_diameter_in: equivalent orifice diameter (inches)
    pressure_psig: line pressure (gauge)
    discharge_coeff: orifice discharge coefficient (0.6–0.7 typical)
    """
    P_abs_psia = pressure_psig + 14.696  # absolute pressure
    area_in2   = np.pi * (hole_diameter_in / 2) ** 2
    area_ft2   = area_in2 / 144.0

    # Choked flow: Q = Cd * A * sqrt(k * P * rho_upstream) ... simplified for air
    # Practical formula from CAGI/Compressed Air Challenge:
    # CFM = 0.7854 * D² * Cd * P_abs (psia) / 14.696 * sqrt(T/530) [T in Rankine, ~530R at 70°F]
    # Simplified (T ≈ 530 R):
    cfm = 0.7854 * (hole_diameter_in ** 2) * discharge_coeff * (P_abs_psia / 14.696)
    return cfm


def compressor_power_for_flow(
    flow_cfm: float,
    pressure_psig: float,
    comp_eff: float = 0.80,
    motor_eff: float = 0.93,
) -> float:
    """
    Estimate shaft power (kW) required to compress flow_cfm of air to pressure_psig.
    Uses isentropic compression formula for air (k=1.4).

    comp_eff: isentropic efficiency of compressor (0.7–0.85)
    motor_eff: motor electrical efficiency
    """
    k = 1.4
    P1 = 14.696  # inlet pressure (psia)
    P2 = pressure_psig + 14.696
    T1_R = 530.0  # inlet temperature (°R, ~70°F)
    R_air = 1545 / 28.97  # ft·lbf / (lb·°R)  [universal gas / MW_air]

    # Mass flow: ideal gas, density at inlet
    rho_in_lb_ft3 = P1 * 144 / (R_air * T1_R)  # lb/ft³ (using P in lbf/ft²)
    mass_flow_lbs = flow_cfm * rho_in_lb_ft3    # lb/min

    # Isentropic work per unit mass (BTU/lb):
    cp_air = 0.24  # BTU / (lb·°F)
    T2_is  = T1_R * (P2 / P1) ** ((k - 1) / k)
    W_is   = cp_air * (T2_is - T1_R)  # BTU/lb

    # Power (BTU/min → kW):
    power_btu_min = mass_flow_lbs * W_is / comp_eff
    power_kw = power_btu_min * 0.01757  # 1 BTU/min = 0.01757 kW
    power_kw_elec = power_kw / motor_eff

    return power_kw_elec


def compute_leak_savings(
    leaks: list[dict],
    run_hours: float,
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
    pressure_psig: float = 100.0,
    comp_eff: float = 0.80,
    motor_eff: float = 0.93,
) -> dict:
    """
    leaks: list of dicts with keys:
        description, qty, hole_diameter_in (or cfm_each), pressure_psig (optional override)
    run_hours: compressor annual run hours
    """
    rows = []
    total_cfm = 0.0
    total_kw  = 0.0

    for lk in leaks:
        qty  = int(lk.get("qty", 1))
        psi_raw = float(lk.get("pressure_psig", 0.0))
        psi = psi_raw if psi_raw > 0 else pressure_psig
        if "cfm_each" in lk and lk["cfm_each"]:
            cfm_each = float(lk["cfm_each"])
        elif "hole_diameter_in" in lk and lk["hole_diameter_in"]:
            cfm_each = leak_flow_cfm(float(lk["hole_diameter_in"]), psi)
        else:
            cfm_each = 0.0
        total_cfm_row = cfm_each * qty
        kw_row = compressor_power_for_flow(total_cfm_row, psi, comp_eff, motor_eff)
        ann_kwh_row = kw_row * run_hours
        cost_row = ann_kwh_row * elec_rate + kw_row * demand_rate * demand_months

        rows.append({
            **lk,
            "cfm_each": cfm_each,
            "total_cfm": total_cfm_row,
            "kw_lost": kw_row,
            "ann_kwh_lost": ann_kwh_row,
            "cost_savings": cost_row,
        })
        total_cfm += total_cfm_row
        total_kw  += kw_row

    ann_kwh = total_kw * run_hours
    ann_cost = ann_kwh * elec_rate + total_kw * demand_rate * demand_months

    return {
        "leaks": rows,
        "total_cfm_lost": total_cfm,
        "total_kw_lost": total_kw,
        "ann_kwh_savings": ann_kwh,
        "ann_cost_savings": ann_cost,
    }
