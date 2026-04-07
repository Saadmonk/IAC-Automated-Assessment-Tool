"""
ARC 2.7221 — Lower Temperature During Winter and Vice-Versa
ASHRAE Guideline 14 change-point regression on smart meter data.

Supports:
  - 2P  (constant baseline)
  - 3PC (3-param cooling)
  - 3PH (3-param heating)
  - 4P  (4-param V-shape)
  - 5P  (5-param with separate heating and cooling slopes)

Returns regression coefficients, R², CVRMSE, savings estimate.
"""
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import t as t_dist
import warnings
warnings.filterwarnings("ignore")


# ── Smart meter data preparation ──────────────────────────────────────────────

def prepare_smart_meter_data(
    df_raw: pd.DataFrame,
    time_col: str,
    kwh_col: str,
    interval: str,             # "daily" | "hourly" | "15-min"
) -> pd.DataFrame:
    """
    Aggregate smart meter CSV to daily kWh.
    Returns DataFrame with columns: date (datetime), kwh_daily
    """
    df = df_raw[[time_col, kwh_col]].copy()
    df.columns = ["timestamp", "kwh"]
    df["kwh"] = pd.to_numeric(df["kwh"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], infer_datetime_format=True, errors="coerce")
    df = df.dropna(subset=["timestamp", "kwh"])
    df["date"] = df["timestamp"].dt.normalize()

    if interval == "daily":
        # Already daily — just sum in case of duplicates
        daily = df.groupby("date")["kwh"].sum().reset_index()
    else:
        # hourly or 15-min: sum up to daily totals
        daily = df.groupby("date")["kwh"].sum().reset_index()

    daily.columns = ["date", "kwh_daily"]
    daily = daily.sort_values("date").reset_index(drop=True)
    return daily


def merge_weather_and_meter(
    df_meter: pd.DataFrame,    # from prepare_smart_meter_data: date, kwh_daily
    df_weather: pd.DataFrame,  # from weather.get_daily_temps: date, avg_temp_f
) -> pd.DataFrame:
    """
    Inner-join meter data with weather on date.
    Returns DataFrame with: date, kwh_daily, avg_temp_f
    """
    df_weather = df_weather.copy()
    df_weather["date"] = pd.to_datetime(df_weather["date"]).dt.normalize()
    df_meter = df_meter.copy()
    df_meter["date"] = pd.to_datetime(df_meter["date"]).dt.normalize()
    merged = pd.merge(df_meter, df_weather[["date", "avg_temp_f"]], on="date", how="inner")
    merged = merged.dropna().reset_index(drop=True)
    return merged


# ── Model functions ────────────────────────────────────────────────────────────

def model_2P(T, b0):
    """2-parameter: constant (no weather dependence)."""
    return np.full_like(T, b0, dtype=float)


def model_3PC(T, b0, b1, Tc):
    """3-parameter cooling: flat below Tc, linear above."""
    return b0 + b1 * np.maximum(T - Tc, 0)


def model_3PH(T, b0, b1, Th):
    """3-parameter heating: linear below Th, flat above."""
    return b0 + b1 * np.maximum(Th - T, 0)


def model_4P(T, b0, b1, b2, Tcp):
    """4-parameter: V-shape with single change point."""
    return b0 + b1 * np.maximum(T - Tcp, 0) + b2 * np.maximum(Tcp - T, 0)


def model_5P(T, b0, b1, b2, Tc, Th):
    """5-parameter: separate heating and cooling change points."""
    return (b0
            + b1 * np.maximum(T - Tc, 0)
            + b2 * np.maximum(Th - T, 0))


# ── Fit helper ────────────────────────────────────────────────────────────────

def _fit_model(func, T, E, p0, bounds=(-np.inf, np.inf)):
    try:
        popt, pcov = curve_fit(func, T, E, p0=p0, bounds=bounds, maxfev=10000)
        E_pred = func(T, *popt)
        residuals = E - E_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((E - E.mean())**2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        n = len(E)
        p = len(popt)
        rmse  = np.sqrt(ss_res / (n - p)) if n > p else 0.0
        cvrmse = rmse / E.mean() * 100 if E.mean() > 0 else 0.0
        return {"params": popt, "r2": float(r2), "cvrmse": float(cvrmse),
                "E_pred": E_pred, "success": True}
    except Exception as ex:
        return {"success": False, "error": str(ex), "r2": -999}


def fit_all_models(df: pd.DataFrame, temp_col: str, energy_col: str) -> dict:
    """
    Fit all 5 ASHRAE Guideline 14 models to the data.
    df must have daily rows with temperature and energy columns.
    Returns dict of model_name -> fit_result.
    """
    T = df[temp_col].values.astype(float)
    E = df[energy_col].values.astype(float)
    mean_T = T.mean()
    mean_E = E.mean()

    results = {}

    # 2P
    results["2P"] = _fit_model(model_2P, T, E, p0=[mean_E])

    # 3PC — cooling
    results["3PC"] = _fit_model(
        model_3PC, T, E,
        p0=[mean_E, 1.0, mean_T],
        bounds=([-np.inf, 0, T.min()], [np.inf, np.inf, T.max()])
    )

    # 3PH — heating
    results["3PH"] = _fit_model(
        model_3PH, T, E,
        p0=[mean_E, 1.0, mean_T],
        bounds=([-np.inf, 0, T.min()], [np.inf, np.inf, T.max()])
    )

    # 4P
    results["4P"] = _fit_model(
        model_4P, T, E,
        p0=[mean_E, 0.5, 0.5, mean_T],
        bounds=([-np.inf, 0, 0, T.min()], [np.inf, np.inf, np.inf, T.max()])
    )

    # 5P
    results["5P"] = _fit_model(
        model_5P, T, E,
        p0=[mean_E, 0.5, 0.5, mean_T + 5, mean_T - 5],
        bounds=([-np.inf, 0, 0, T.min(), T.min()],
                [np.inf, np.inf, np.inf, T.max(), T.max()])
    )

    # Tag best model by R²
    best = max((k for k in results if results[k]["success"]),
               key=lambda k: results[k]["r2"], default=None)
    if best:
        results["best"] = best

    return results


# ── Savings calculation ────────────────────────────────────────────────────────

def compute_thermostat_savings(
    results: dict,
    model_name: str,
    T_arr: np.ndarray,
    E_arr: np.ndarray,
    delta_T_cooling: float,   # °F increase in cooling setpoint (positive = savings)
    delta_T_heating: float,   # °F decrease in heating setpoint (positive = savings)
    ann_days: int = 365,
) -> dict:
    """
    Estimate annual energy savings from thermostat setback using regression slope.

    For 3PC model:  savings = b1 * delta_T_cooling * cooling_days
    For 3PH model:  savings = b1 * delta_T_heating * heating_days
    For 5P model:   both slopes applied
    """
    fit = results.get(model_name)
    if not fit or not fit["success"]:
        return {"success": False, "error": f"Model {model_name} did not converge."}

    params = fit["params"]
    savings_kwh_day = 0.0

    if model_name == "3PC":
        b0, b1, Tc = params
        # Days above balance point (cooling season)
        cool_days = np.sum(T_arr > Tc)
        savings_kwh_day = b1 * delta_T_cooling * cool_days

    elif model_name == "3PH":
        b0, b1, Th = params
        heat_days = np.sum(T_arr < Th)
        savings_kwh_day = b1 * delta_T_heating * heat_days

    elif model_name == "4P":
        b0, b1_cool, b2_heat, Tcp = params
        cool_days = np.sum(T_arr > Tcp)
        heat_days = np.sum(T_arr < Tcp)
        savings_kwh_day = (b1_cool * delta_T_cooling * cool_days +
                           b2_heat * delta_T_heating * heat_days)

    elif model_name == "5P":
        b0, b1_cool, b2_heat, Tc, Th = params
        cool_days = np.sum(T_arr > Tc)
        heat_days = np.sum(T_arr < Th)
        savings_kwh_day = (b1_cool * delta_T_cooling * cool_days +
                           b2_heat * delta_T_heating * heat_days)

    elif model_name == "2P":
        savings_kwh_day = 0.0

    ann_savings_kwh = float(savings_kwh_day)  # already summed over days

    return {
        "success": True,
        "model": model_name,
        "ann_savings_kwh": ann_savings_kwh,
        "params": params,
        "r2": fit["r2"],
        "cvrmse": fit["cvrmse"],
    }


def best_model_label(results: dict) -> str:
    """Return a human-readable name for the best model."""
    names = {
        "2P":  "2-Parameter (Constant Baseline)",
        "3PC": "3-Parameter Cooling",
        "3PH": "3-Parameter Heating",
        "4P":  "4-Parameter (Heating + Cooling)",
        "5P":  "5-Parameter (Full ASHRAE GL14)",
    }
    best = results.get("best", "—")
    return names.get(best, best)
