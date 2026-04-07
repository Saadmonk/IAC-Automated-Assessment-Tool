"""
ARC 2.9114 — Solar PV Installation
Uses NREL PySAM (PVWatts v8) for accurate simulation when available.
Falls back to simplified irradiance-based calculation if PySAM not installed.

PySAM docs: https://nrel-pysam.readthedocs.io/
Install: pip install nrel-pysam
"""
import os

# Try importing PySAM
try:
    import PySAM.Pvwattsv8 as pv
    PYSAM_AVAILABLE = True
except ImportError:
    PYSAM_AVAILABLE = False

# Try importing NREL weather API helper (requests)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ── PySAM / PVWatts calculation ───────────────────────────────────────────────

def run_pvwatts(
    system_capacity_kw: float,
    lat: float,
    lon: float,
    tilt: float = None,          # None = use latitude as tilt
    azimuth: float = 180.0,      # 180 = south-facing
    losses: float = 14.0,        # % total system losses (PVWatts default)
    dc_ac_ratio: float = 1.2,
    inv_eff: float = 96.0,       # %
    array_type: int = 1,         # 0=fixed open rack, 1=fixed roof mount, 4=1-axis tracking
    module_type: int = 0,        # 0=standard, 1=premium, 2=thin film
    weather_file: str = None,    # path to SAM weather CSV; if None, uses NREL API
    nrel_api_key: str = None,    # NREL API key for weather download
) -> dict:
    """
    Run PVWatts v8 simulation using PySAM.
    Returns annual kWh, monthly kWh, capacity factor, and other outputs.

    If weather_file is None and nrel_api_key is provided, downloads TMY data
    from NREL NSRDB API for the given lat/lon.
    If neither is available, raises RuntimeError.
    """
    if not PYSAM_AVAILABLE:
        raise RuntimeError(
            "PySAM is not installed. Install with: pip install nrel-pysam\n"
            "Falling back to simplified calculation."
        )

    pv_model = pv.new()

    # System design
    pv_model.SystemDesign.system_capacity = system_capacity_kw
    pv_model.SystemDesign.dc_ac_ratio     = dc_ac_ratio
    pv_model.SystemDesign.inv_eff         = inv_eff
    pv_model.SystemDesign.losses          = losses
    pv_model.SystemDesign.array_type      = array_type
    pv_model.SystemDesign.module_type     = module_type
    pv_model.SystemDesign.tilt            = tilt if tilt is not None else abs(lat)
    pv_model.SystemDesign.azimuth         = azimuth

    # Weather file
    if weather_file and os.path.exists(weather_file):
        pv_model.SolarResource.solar_resource_file = weather_file
    elif nrel_api_key and REQUESTS_AVAILABLE:
        # Download NSRDB PSM3 TMY for location
        weather_path = _download_nsrdb_tmy(lat, lon, nrel_api_key)
        pv_model.SolarResource.solar_resource_file = weather_path
    else:
        # Use built-in resource data if available, else error
        # Try to use the resource data API with the default NREL test key
        raise RuntimeError(
            "No weather file or NREL API key provided. "
            "Either supply a SAM weather CSV file or an NREL API key.\n"
            "Get a free NREL API key at: https://developer.nrel.gov/signup/"
        )

    pv_model.execute()

    outputs = pv_model.Outputs
    return {
        "annual_kwh": float(outputs.ac_annual),
        "monthly_kwh": list(outputs.ac_monthly),
        "capacity_factor_pct": float(outputs.capacity_factor),
        "kwh_per_kw": float(outputs.kwh_per_kw),
        "solrad_annual": float(outputs.solrad_annual),
        "lat": float(outputs.lat),
        "lon": float(outputs.lon),
        "system_capacity_kw": system_capacity_kw,
        "tilt": pv_model.SystemDesign.tilt,
        "azimuth": azimuth,
        "losses": losses,
        "dc_ac_ratio": dc_ac_ratio,
        "method": "PySAM PVWatts v8",
    }


def _download_nsrdb_tmy(lat: float, lon: float, api_key: str) -> str:
    """Download NSRDB PSM3 TMY data and save as CSV for PySAM."""
    import tempfile, csv
    url = (
        "https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv"
        f"?api_key={api_key}&lat={lat}&lon={lon}&names=tmy&interval=60"
        f"&attributes=ghi,dhi,dni,wind_speed,air_temperature&leap_day=false"
        f"&utc=false&email=iac@example.com"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
    tmp.write(r.text)
    tmp.close()
    return tmp.name


# ── Simplified fallback (no PySAM needed) ────────────────────────────────────

# Louisiana / Gulf South TMY peak sun hours by month (kWh/m²/day)
# Source: NREL PVWatts for Lafayette, LA (30.22°N, -92.02°W)
LAFAYETTE_MONTHLY_PSH = [
    3.4,  # Jan
    4.0,  # Feb
    4.8,  # Mar
    5.4,  # Apr
    5.8,  # May
    6.0,  # Jun
    5.9,  # Jul
    5.7,  # Aug
    5.2,  # Sep
    5.0,  # Oct
    3.8,  # Nov
    3.2,  # Dec
]

# Generic US city annual PSH lookup (approximate, kWh/m²/day)
CITY_PSH = {
    "Lafayette, LA": 4.83,
    "New Orleans, LA": 4.92,
    "Baton Rouge, LA": 4.83,
    "Houston, TX": 5.27,
    "Dallas, TX": 5.43,
    "Atlanta, GA": 4.74,
    "Miami, FL": 5.26,
    "Phoenix, AZ": 6.57,
    "Los Angeles, CA": 5.62,
    "Denver, CO": 5.67,
    "Chicago, IL": 4.08,
    "New York, NY": 4.08,
    "Seattle, WA": 3.57,
}


def run_pvwatts_simplified(
    system_capacity_kw: float,
    annual_psh: float = 4.83,          # peak sun hours/day (annual avg)
    losses_pct: float = 14.0,          # total losses %
    dc_ac_ratio: float = 1.2,
) -> dict:
    """
    Simplified PVWatts-equivalent calculation without PySAM.
    Uses annual average peak sun hours directly.

    annual_kwh ≈ system_kW_dc × PSH_annual_days × (1 - losses/100) / dc_ac_ratio_effect
    Standard PVWatts formula: AC_annual = P_dc × PSH_annual × derate_factor
    derate_factor = (1 - losses/100)
    """
    derate = 1.0 - losses_pct / 100.0
    annual_kwh = system_capacity_kw * annual_psh * 365 * derate

    # Approximate capacity factor
    capacity_factor = annual_kwh / (system_capacity_kw * 8760) * 100

    return {
        "annual_kwh": annual_kwh,
        "capacity_factor_pct": capacity_factor,
        "kwh_per_kw": annual_kwh / system_capacity_kw,
        "solrad_annual": annual_psh,
        "system_capacity_kw": system_capacity_kw,
        "losses": losses_pct,
        "method": "Simplified (PySAM not available)",
    }


# ── Financial calculation ─────────────────────────────────────────────────────

def solar_financial(
    annual_kwh: float,
    system_capacity_kw: float,
    elec_rate: float,
    installed_cost_per_kw: float = 2500.0,  # $/kW DC — typical commercial 2024
    federal_itc_pct: float = 30.0,           # ITC %
    state_incentive: float = 0.0,            # $ direct rebate
    om_cost_per_kw_yr: float = 15.0,         # annual O&M
    degradation_pct: float = 0.5,            # annual degradation %
    analysis_years: int = 25,
) -> dict:
    """
    Simple financial model for solar PV.
    Returns simple payback, NPV-equivalent metrics.
    """
    total_installed_cost = system_capacity_kw * installed_cost_per_kw
    itc_value     = total_installed_cost * federal_itc_pct / 100
    net_cost      = total_installed_cost - itc_value - state_incentive

    ann_savings_yr1 = annual_kwh * elec_rate
    ann_om          = system_capacity_kw * om_cost_per_kw_yr
    ann_net_yr1     = ann_savings_yr1 - ann_om

    simple_payback  = net_cost / ann_net_yr1 if ann_net_yr1 > 0 else float("inf")

    # 25-year cumulative savings (with degradation)
    cumulative_savings = 0
    for yr in range(1, analysis_years + 1):
        kwh_yr = annual_kwh * ((1 - degradation_pct / 100) ** (yr - 1))
        cumulative_savings += kwh_yr * elec_rate - ann_om

    return {
        "total_installed_cost": total_installed_cost,
        "itc_value": itc_value,
        "net_cost_after_itc": net_cost,
        "ann_savings_yr1": ann_savings_yr1,
        "ann_om": ann_om,
        "ann_net_savings_yr1": ann_net_yr1,
        "simple_payback_years": simple_payback,
        "cumulative_savings_25yr": cumulative_savings,
        "installed_cost_per_kw": installed_cost_per_kw,
    }
