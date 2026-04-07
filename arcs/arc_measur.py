"""
MEASUR-equivalent calculations for:
  1. Compressed Air Pressure Reduction (ARC 2.4239)
  2. Power Factor Correction (utility penalty avoidance)

These replicate the methodology used in the DOE MEASUR tool
(formerly AirMaster+ and MotorMaster+).
Reference: DOE Compressed Air Challenge Best Practices Manual
"""
import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# 1. COMPRESSED AIR PRESSURE REDUCTION (ARC 2.4239)
#    MEASUR: Compressed Air → Pressure Reduction Calculator
# ══════════════════════════════════════════════════════════════════════════════

def pressure_reduction_savings(
    hp_compressor: float,
    motor_eff: float,
    current_pressure_psig: float,
    proposed_pressure_psig: float,
    run_hours: float,
    load_fraction: float = 1.0,
    elec_rate: float = 0.10,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    Estimate energy savings from reducing compressed air system pressure.
    Methodology matches DOE MEASUR Pressure Reduction calculator.

    Uses polytropic compression formula to compute power ratio:
      Power ∝ [(P2/P1)^((k-1)/k) - 1] / [(k-1)/k]

    hp_compressor: rated compressor nameplate HP
    motor_eff: motor efficiency (0–1)
    current_pressure_psig: current discharge pressure (psig)
    proposed_pressure_psig: proposed lower discharge pressure (psig)
    run_hours: annual compressor run hours
    load_fraction: average load fraction (0–1), default 1.0 (fully loaded)
    """
    k = 1.4      # ratio of specific heats for air
    P1 = 14.696  # inlet pressure (psia)
    exp = (k - 1) / k

    P2_current  = current_pressure_psig  + 14.696  # psia
    P2_proposed = proposed_pressure_psig + 14.696  # psia

    # Polytropic work factor W = (P2/P1)^exp - 1
    W_current  = (P2_current  / P1) ** exp - 1
    W_proposed = (P2_proposed / P1) ** exp - 1

    # Power ratio
    power_ratio = W_proposed / W_current if W_current > 0 else 1.0

    # Full-load electrical power (kW)
    kw_full = hp_compressor * 0.7457 / motor_eff

    # Actual operating power at load_fraction
    kw_current  = kw_full * load_fraction
    kw_proposed = kw_current * power_ratio

    delta_kw = kw_current - kw_proposed
    ann_kwh  = delta_kw * run_hours
    ann_cost = ann_kwh * elec_rate + delta_kw * demand_rate * demand_months

    pct_savings = (1 - power_ratio) * 100

    return {
        "kw_current": kw_current,
        "kw_proposed": kw_proposed,
        "delta_kw": delta_kw,
        "power_ratio": power_ratio,
        "pct_power_savings": pct_savings,
        "ann_kwh_savings": ann_kwh,
        "ann_cost_savings": ann_cost,
        "W_current": W_current,
        "W_proposed": W_proposed,
    }


def pressure_reduction_rule_of_thumb(
    kw_compressor: float,
    delta_pressure_psig: float,
    run_hours: float,
    elec_rate: float = 0.10,
) -> dict:
    """
    Quick estimate using DOE rule of thumb:
    Every 2 psig reduction → ~1% power reduction.
    For quick calculations when full compressor data is unavailable.
    """
    pct_reduction = (delta_pressure_psig / 2.0) * 0.01
    delta_kw = kw_compressor * pct_reduction
    ann_kwh  = delta_kw * run_hours
    ann_cost = ann_kwh * elec_rate

    return {
        "delta_kw": delta_kw,
        "pct_power_savings": pct_reduction * 100,
        "ann_kwh_savings": ann_kwh,
        "ann_cost_savings": ann_cost,
        "method": "rule_of_thumb_2psig_per_1pct",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. POWER FACTOR CORRECTION
#    MEASUR: Power Factor Correction Calculator
#    Corrects lagging power factor by adding capacitor bank
# ══════════════════════════════════════════════════════════════════════════════

def power_factor_savings(
    avg_kw_demand: float,
    pf_current: float,
    pf_target: float,
    demand_rate_kva: float = 0.0,     # $/kVA/month (utility kVA demand charge)
    demand_rate_kvar: float = 0.0,    # $/kVAR/month (reactive demand penalty)
    demand_months: int = 12,
    capacitor_cost_per_kvar: float = 20.0,  # typical installed cost $/kVAR
) -> dict:
    """
    Calculate reactive power reduction and cost savings from power factor correction.

    Power factor: PF = kW / kVA = cos(θ)
    Reactive power: kVAR = kW × tan(θ)

    Savings come from:
    1. Reduced kVA demand charge (if utility bills on kVA basis)
    2. Reduced kVAR reactive demand penalty
    3. Reduced I²R losses in conductors (secondary benefit, not calculated here)

    avg_kw_demand: average real power demand (kW)
    pf_current: current power factor (e.g., 0.78)
    pf_target: target power factor (e.g., 0.95)
    demand_rate_kva: utility kVA demand charge ($/kVA/month), 0 if not applicable
    demand_rate_kvar: utility reactive demand penalty ($/kVAR/month), 0 if not applicable
    capacitor_cost_per_kvar: installed cost of capacitor bank per kVAR
    """
    import math

    if pf_current <= 0 or pf_current > 1 or pf_target <= 0 or pf_target > 1:
        return {"error": "Power factor must be between 0 and 1."}
    if pf_target <= pf_current:
        return {"error": "Target PF must be higher than current PF."}

    theta_current = math.acos(pf_current)
    theta_target  = math.acos(pf_target)

    kva_current  = avg_kw_demand / pf_current
    kva_proposed = avg_kw_demand / pf_target

    kvar_current  = avg_kw_demand * math.tan(theta_current)
    kvar_proposed = avg_kw_demand * math.tan(theta_target)
    kvar_required = kvar_current - kvar_proposed  # capacitor bank size needed

    delta_kva  = kva_current - kva_proposed
    delta_kvar = kvar_current - kvar_proposed

    # Annual savings
    ann_kva_savings  = delta_kva  * demand_rate_kva  * demand_months
    ann_kvar_savings = delta_kvar * demand_rate_kvar * demand_months
    total_ann_savings = ann_kva_savings + ann_kvar_savings

    # Capacitor bank cost
    cap_cost = kvar_required * capacitor_cost_per_kvar
    payback  = cap_cost / total_ann_savings if total_ann_savings > 0 else float("inf")

    return {
        "kva_current": kva_current,
        "kva_proposed": kva_proposed,
        "kvar_current": kvar_current,
        "kvar_proposed": kvar_proposed,
        "kvar_required": kvar_required,
        "delta_kva": delta_kva,
        "delta_kvar": delta_kvar,
        "ann_kva_savings": ann_kva_savings,
        "ann_kvar_savings": ann_kvar_savings,
        "total_ann_savings": total_ann_savings,
        "capacitor_bank_kvar": kvar_required,
        "estimated_cap_cost": cap_cost,
        "payback_years": payback,
        "pf_improvement": f"{pf_current:.3f} → {pf_target:.3f}",
    }


def power_factor_utility_penalty(
    avg_kw_demand: float,
    pf_current: float,
    pf_threshold: float = 0.90,
    penalty_pct: float = 0.01,      # 1% per 0.01 PF below threshold (typical)
    monthly_bill: float = 0.0,
) -> dict:
    """
    Estimate utility power factor penalty for utilities that apply percentage-based
    surcharges when PF falls below a threshold.

    penalty_pct: fraction added to monthly bill per 0.01 PF below threshold.
    Typical: 1–2% per 0.01 PF below 0.90 threshold.
    """
    if pf_current >= pf_threshold:
        return {
            "penalty_monthly": 0,
            "penalty_annual": 0,
            "message": f"PF {pf_current:.3f} ≥ threshold {pf_threshold:.3f}. No penalty."
        }
    pf_deficit_units = round((pf_threshold - pf_current) / 0.01)
    monthly_penalty = monthly_bill * penalty_pct * pf_deficit_units
    annual_penalty  = monthly_penalty * 12
    return {
        "pf_deficit_units": pf_deficit_units,
        "penalty_monthly": monthly_penalty,
        "penalty_annual": annual_penalty,
        "message": f"PF {pf_current:.3f} is {pf_deficit_units} units below threshold {pf_threshold:.3f}.",
    }
