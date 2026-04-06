"""
Generic ARC calculation helpers used by simpler ARCs:
  2.7135 — Occupancy sensors
  2.7134 — Photocell controls
  2.6212 — Turn off lights when unoccupied
  2.4322 — Energy-efficient motors
  2.7447 — Air curtain / strip doors
  2.9114 — Solar PV
  2.7264 — Interlock HVAC
  2.7261 — Timers / thermostats
  2.7232 — High-efficiency HVAC (SEER/EER delta)
  2.4133 — ECM motors
"""
import numpy as np


# ── Lighting-based ARCs (wattage × hours) ─────────────────────────────────

def lighting_hours_savings(
    fixtures: list[dict],
    hours_saved_per_year: float,
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    For occupancy sensors, photocells, turn-off lights.
    fixtures: list of {description, qty, watts}
    hours_saved_per_year: annual hours that lights will now be OFF
    """
    total_w = sum(int(f.get("qty", 1)) * float(f.get("watts", 0)) for f in fixtures)
    total_kw = total_w / 1000.0
    ann_kwh = total_kw * hours_saved_per_year
    ann_cost = ann_kwh * elec_rate + total_kw * demand_rate * demand_months
    return {
        "total_kw": total_kw,
        "ann_kwh_savings": ann_kwh,
        "ann_cost_savings": ann_cost,
    }


# ── Motor upgrade savings ──────────────────────────────────────────────────

def motor_efficiency_savings(
    motors: list[dict],
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    For 2.4322 / 2.4133 — replace with higher efficiency motor.
    motors: list of {description, hp, eff_existing (0-1), eff_proposed (0-1), run_hours}
    """
    rows = []
    total_kwh = 0.0
    total_dkw = 0.0
    for m in motors:
        hp   = float(m.get("hp", 0))
        eff0 = float(m.get("eff_existing", 0.88))
        eff1 = float(m.get("eff_proposed", 0.95))
        hrs  = float(m.get("run_hours", 2000))
        kw0  = hp * 0.7457 / eff0
        kw1  = hp * 0.7457 / eff1
        dkw  = kw0 - kw1
        kwh  = dkw * hrs
        cost = kwh * elec_rate + dkw * demand_rate * demand_months
        rows.append({**m, "kw_existing": kw0, "kw_proposed": kw1,
                     "delta_kw": dkw, "ann_kwh_savings": kwh, "cost_savings": cost})
        total_kwh += kwh
        total_dkw += dkw
    return {
        "motors": rows,
        "total_delta_kw": total_dkw,
        "ann_kwh_savings": total_kwh,
        "ann_cost_savings": total_kwh * elec_rate + total_dkw * demand_rate * demand_months,
    }


# ── HVAC efficiency upgrade (SEER / EER delta) ────────────────────────────

def hvac_efficiency_savings(
    units: list[dict],
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    For 2.7232 — upgrade to higher EER/SEER equipment.
    units: list of {description, tons, eer_existing, eer_proposed, run_hours}
    """
    rows = []
    total_kwh = 0.0
    total_dkw = 0.0
    for u in units:
        tons   = float(u.get("tons", 0))
        eer0   = float(u.get("eer_existing", 10.0))
        eer1   = float(u.get("eer_proposed", 14.0))
        hrs    = float(u.get("run_hours", 1500))
        # kW = (tons * 12000 BTU/hr) / (EER BTU/Wh) / 1000
        kw0    = tons * 12000 / (eer0 * 1000)
        kw1    = tons * 12000 / (eer1 * 1000)
        dkw    = kw0 - kw1
        kwh    = dkw * hrs
        cost   = kwh * elec_rate + dkw * demand_rate * demand_months
        rows.append({**u, "kw_existing": kw0, "kw_proposed": kw1,
                     "delta_kw": dkw, "ann_kwh_savings": kwh, "cost_savings": cost})
        total_kwh += kwh
        total_dkw += dkw
    return {
        "units": rows,
        "total_delta_kw": total_dkw,
        "ann_kwh_savings": total_kwh,
        "ann_cost_savings": total_kwh * elec_rate + total_dkw * demand_rate * demand_months,
    }


# ── Air curtain / strip doors ──────────────────────────────────────────────

def air_infiltration_savings(
    doors: list[dict],
    heating_deg_days: float,
    cooling_deg_days: float,
    gas_rate: float,
    elec_rate: float,
) -> dict:
    """
    Estimate infiltration heat loss savings from installing air curtains or strip doors.
    Uses simplified UA × ΔT × hours method.
    doors: list of {description, width_ft, height_ft, u_value (BTU/hr·ft²·°F),
                    reduction_fraction (0–1), open_hours_per_year}
    """
    rows = []
    total_gas_mmbtu = 0.0
    total_elec_kwh  = 0.0

    for d in doors:
        w    = float(d.get("width_ft", 8))
        h    = float(d.get("height_ft", 10))
        U    = float(d.get("u_value", 0.5))  # BTU/hr·ft²·°F for open door approx
        frac = float(d.get("reduction_fraction", 0.8))
        open_hrs = float(d.get("open_hours_per_year", 2000))
        area = w * h

        # Heat loss (BTU) ≈ U × A × HDD × 24 × fraction
        heat_loss_btu = U * area * heating_deg_days * 24 * frac
        cool_loss_btu = U * area * cooling_deg_days * 24 * frac

        gas_saved_mmbtu  = heat_loss_btu / 1e6
        elec_saved_kwh   = cool_loss_btu / 3412  # 1 kWh = 3412 BTU

        gas_cost  = gas_saved_mmbtu * gas_rate
        elec_cost = elec_saved_kwh  * elec_rate

        rows.append({**d, "area_ft2": area,
                     "gas_mmbtu_saved": gas_saved_mmbtu,
                     "elec_kwh_saved": elec_saved_kwh,
                     "cost_savings": gas_cost + elec_cost})
        total_gas_mmbtu += gas_saved_mmbtu
        total_elec_kwh  += elec_saved_kwh

    total_cost = total_gas_mmbtu * gas_rate + total_elec_kwh * elec_rate
    return {
        "doors": rows,
        "total_gas_mmbtu": total_gas_mmbtu,
        "total_elec_kwh": total_elec_kwh,
        "ann_cost_savings": total_cost,
    }


# ── Solar PV (simplified) ──────────────────────────────────────────────────

def solar_pv_savings(
    panel_area_ft2: float,
    system_efficiency: float,
    annual_peak_sun_hours: float,  # hrs/yr (e.g., ~1400 for Louisiana)
    elec_rate: float,
    installation_cost: float,
) -> dict:
    """
    Estimate annual kWh generation from solar PV.
    panel_area_ft2: total panel area in sq ft
    system_efficiency: overall system efficiency (0.14–0.22 typical)
    annual_peak_sun_hours: PSH × 365 for the location
    """
    area_m2 = panel_area_ft2 * 0.0929
    # P_rated (kW) = area_m2 × 1000 W/m² × efficiency
    rated_kw = area_m2 * 1.0 * system_efficiency  # kW DC
    # Annual kWh = rated_kW × peak_sun_hours_per_day × 365 (if given per year, just multiply)
    ann_kwh  = rated_kw * annual_peak_sun_hours
    ann_cost = ann_kwh * elec_rate
    payback  = installation_cost / ann_cost if ann_cost > 0 else float("inf")
    return {
        "rated_kw": rated_kw,
        "ann_kwh_generated": ann_kwh,
        "ann_cost_savings": ann_cost,
        "payback_years": payback,
    }


# ── Interlock HVAC (eliminate simultaneous heating & cooling) ──────────────

def interlock_hvac_savings(
    simultaneous_hours: float,
    overlap_load_tons: float,
    eer: float,
    elec_rate: float,
    demand_rate: float = 0.0,
    demand_months: int = 12,
) -> dict:
    """
    For ARC 2.7264 — prevents HVAC units from fighting each other.
    simultaneous_hours: annual hours of simultaneous heating+cooling operation
    overlap_load_tons: tons of wasted cooling (or heating)
    eer: EER of the cooling equipment
    """
    kw_wasted = overlap_load_tons * 12000 / (eer * 1000)
    ann_kwh   = kw_wasted * simultaneous_hours
    ann_cost  = ann_kwh * elec_rate + kw_wasted * demand_rate * demand_months
    return {
        "kw_wasted": kw_wasted,
        "ann_kwh_savings": ann_kwh,
        "ann_cost_savings": ann_cost,
    }
