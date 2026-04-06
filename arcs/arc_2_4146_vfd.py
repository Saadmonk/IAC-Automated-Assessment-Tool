"""
ARC 2.4146 — Install Variable Frequency Drives (VFD)
Affinity laws: power scales as cube of speed ratio.
"""
import numpy as np


def vfd_power_fraction(speed_fraction: float) -> float:
    """
    Cubic affinity law: P_new / P_old = (N_new / N_old)^3
    speed_fraction: N_new / N_old  (0–1)
    """
    return speed_fraction ** 3


def compute_vfd_savings(
    motors: list[dict],
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    motors: list of dicts with keys:
        description, hp, motor_eff (0–1), run_hours, speed_fraction,
        load_fraction (0–1, fraction of full-load time at reduced speed)
        — OR — current_kw, proposed_kw directly

    power_before = hp * 0.7457 / motor_eff
    power_after  = power_before * (speed_fraction)^3
    """
    rows = []
    total_kw_saved = 0.0
    total_kwh = 0.0

    for m in motors:
        run_hours = float(m.get("run_hours", 2000))
        if "current_kw" in m and m["current_kw"]:
            kw_before = float(m["current_kw"])
        else:
            hp = float(m.get("hp", 0))
            eff = float(m.get("motor_eff", 0.90))
            kw_before = hp * 0.7457 / eff

        spd_frac = float(m.get("speed_fraction", 0.80))
        kw_after = kw_before * vfd_power_fraction(spd_frac)
        delta_kw = kw_before - kw_after
        ann_kwh  = delta_kw * run_hours
        cost_sav = ann_kwh * elec_rate + delta_kw * demand_rate * demand_months

        rows.append({
            **m,
            "kw_before": kw_before,
            "kw_after": kw_after,
            "delta_kw": delta_kw,
            "ann_kwh_savings": ann_kwh,
            "cost_savings": cost_sav,
        })
        total_kw_saved += delta_kw
        total_kwh += ann_kwh

    ann_cost = total_kwh * elec_rate + total_kw_saved * demand_rate * demand_months

    return {
        "motors": rows,
        "total_delta_kw": total_kw_saved,
        "ann_kwh_savings": total_kwh,
        "ann_cost_savings": ann_cost,
    }
