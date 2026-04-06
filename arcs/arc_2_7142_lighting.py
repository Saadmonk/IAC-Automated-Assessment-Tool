"""
ARC 2.7142 — Upgrade to LED Lighting
Fixture-level inventory: calculates wattage savings, AOH-based annual kWh, IEF factors.
"""
import pandas as pd
import numpy as np


# ── IEF (Installed Efficacy Factor) lookup ─────────────────────────────────
# Source: DOE/ASHRAE typical efficacy ranges (lm/W)
LAMP_EFFICACY = {
    "Fluorescent T8 (32W)": 90,
    "Fluorescent T8 (25W)": 95,
    "Fluorescent T12": 70,
    "HID Metal Halide": 80,
    "HID HPS": 100,
    "Incandescent": 15,
    "CFL": 60,
    "LED (replacement)": 130,
    "LED A19": 100,
    "LED T8 tube": 130,
    "LED high bay": 140,
    "LED troffer": 120,
    "Other": 80,
}

DEFAULT_LED_EFFICACY_LM_W = 130  # lm/W for replacement LED


def compute_fixture_savings(
    existing_watts: float,
    proposed_watts: float,
    qty: int,
    annual_op_hours: float,
    demand_watts_per_fixture: float = None,
) -> dict:
    """
    Calculate savings for a single fixture type row.

    Returns:
        delta_w: watt reduction per fixture
        delta_kw: total demand reduction (kW)
        ann_kwh: annual kWh savings
    """
    delta_w = existing_watts - proposed_watts
    total_delta_w = delta_w * qty
    delta_kw = total_delta_w / 1000.0
    ann_kwh = total_delta_w * annual_op_hours / 1000.0

    return {
        "delta_w_per_fixture": delta_w,
        "total_delta_w": total_delta_w,
        "delta_kw": delta_kw,
        "ann_kwh": ann_kwh,
    }


def compute_lighting_savings(
    fixtures: list[dict],
    elec_rate: float,
    demand_rate: float = 0.0,
    ann_op_hours_default: float = 2000.0,
) -> dict:
    """
    Given a list of fixture dicts, compute total annual savings.

    Each fixture dict should have:
        description, qty, existing_watts, proposed_watts, annual_op_hours (optional),
        existing_lamp_type, proposed_lamp_type

    Returns aggregate savings + per-fixture breakdown.
    """
    rows = []
    total_kwh = 0.0
    total_kw  = 0.0

    for f in fixtures:
        qty     = int(f.get("qty", 1))
        ex_w    = float(f.get("existing_watts", 0))
        prop_w  = float(f.get("proposed_watts", 0))
        aoh     = float(f.get("annual_op_hours", ann_op_hours_default))

        r = compute_fixture_savings(ex_w, prop_w, qty, aoh)
        cost_savings = r["ann_kwh"] * elec_rate + r["delta_kw"] * demand_rate * 12

        rows.append({
            **f,
            **r,
            "cost_savings": cost_savings,
        })
        total_kwh += r["ann_kwh"]
        total_kw  += r["delta_kw"]

    total_cost = total_kwh * elec_rate + total_kw * demand_rate * 12

    return {
        "fixtures": rows,
        "total_ann_kwh": total_kwh,
        "total_delta_kw": total_kw,
        "total_cost_savings": total_cost,
    }
