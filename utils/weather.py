"""
utils/weather.py
Open-Meteo historical weather fetcher — no API key required.

Public API: https://archive-api.open-meteo.com/v1/archive
Zip→lat/lon: US Census Geocoding API (free, no key)
Fallback zip lookup: hardcoded common Louisiana/Texas/Mississippi cities
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional


# ── Zip → Lat/Lon ─────────────────────────────────────────────────────────────

def zip_to_latlon(zip_code: str) -> tuple[float, float, str]:
    """
    Convert US zip code to (lat, lon, city_name).
    Uses Census Geocoding API first, falls back to hard-coded table.
    Returns (lat, lon, city) or raises ValueError.
    """
    zip_code = str(zip_code).strip().zfill(5)

    # Try Census Geocoding API
    try:
        url = (
            f"https://geocoding.geo.census.gov/geocoder/locations/address"
            f"?benchmark=2020&format=json&zip={zip_code}"
        )
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            matches = data.get("result", {}).get("addressMatches", [])
            if matches:
                coords = matches[0]["coordinates"]
                city = matches[0].get("addressComponents", {}).get("city", zip_code)
                return float(coords["y"]), float(coords["x"]), city
    except Exception:
        pass

    # Fallback: Open-Meteo geocoding by zip (different endpoint)
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={zip_code}&count=1&language=en&format=json"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                res = results[0]
                return float(res["latitude"]), float(res["longitude"]), res.get("name", zip_code)
    except Exception:
        pass

    # Hard-coded fallback for common MALT service area zip codes
    FALLBACK = {
        "70501": (30.2241, -92.0198, "Lafayette, LA"),
        "70503": (30.1697, -92.0796, "Lafayette, LA"),
        "70506": (30.2580, -92.0748, "Lafayette, LA"),
        "70508": (30.1533, -91.9957, "Lafayette, LA"),
        "70433": (30.4760, -90.1021, "Covington, LA"),
        "70601": (30.2266, -93.2174, "Lake Charles, LA"),
        "70301": (29.6911, -91.2018, "Thibodaux, LA"),
        "70001": (29.9745, -90.1210, "Metairie, LA"),
        "70112": (29.9547, -90.0770, "New Orleans, LA"),
        "70806": (30.4418, -91.1373, "Baton Rouge, LA"),
        "70401": (30.5210, -90.4729, "Hammond, LA"),
        "71201": (32.5093, -92.1193, "Monroe, LA"),
        "71301": (31.3082, -92.4457, "Alexandria, LA"),
        "70458": (30.3993, -89.7853, "Slidell, LA"),
        "77001": (29.7604, -95.3698, "Houston, TX"),
        "75201": (32.7767, -96.7970, "Dallas, TX"),
        "39401": (31.3271, -89.2903, "Hattiesburg, MS"),
        "39201": (32.2988, -90.1848, "Jackson, MS"),
        "36104": (32.3617, -86.2792, "Montgomery, AL"),
        "72201": (34.7465, -92.2896, "Little Rock, AR"),
    }
    if zip_code in FALLBACK:
        return FALLBACK[zip_code]

    raise ValueError(
        f"Could not resolve zip code {zip_code}. "
        "Check internet connection or enter lat/lon manually."
    )


# ── Open-Meteo Historical Weather ─────────────────────────────────────────────

def fetch_hourly_temperature(
    lat: float,
    lon: float,
    start_date: str,   # "YYYY-MM-DD"
    end_date: str,     # "YYYY-MM-DD"
) -> pd.DataFrame:
    """
    Fetch hourly dry-bulb temperature (°F) and dew point (°F) from Open-Meteo ERA5.
    Returns DataFrame with columns: datetime (UTC), temp_f, dewpoint_f, wetbulb_f
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,dewpoint_2m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "auto",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    hourly = data["hourly"]
    df = pd.DataFrame({
        "datetime": pd.to_datetime(hourly["time"]),
        "temp_f": hourly["temperature_2m"],
        "dewpoint_f": hourly["dewpoint_2m"],
    })

    # Compute approximate wet-bulb temperature (Stull 2011 approximation)
    # Tw ≈ T × arctan(0.151977 × (RH + 8.313659)^0.5) + arctan(T + RH)
    #        − arctan(RH − 1.676331) + 0.00391838 × RH^1.5 × arctan(0.023101 × RH) − 4.686035
    # Using simpler Magnus-based approximation: Tw ≈ T_c × (0.99 - (T_c - Tdp_c)^0.45 / 16.7)
    T_c = (df["temp_f"] - 32) * 5 / 9
    Td_c = (df["dewpoint_f"] - 32) * 5 / 9
    # Stull (2011) simplified:
    Tw_c = (
        T_c * np.arctan(0.151977 * np.sqrt(
            np.clip(
                100 - 5 / 9 * (T_c - Td_c) * 100 / (0.6108 * np.exp(17.27 * T_c / (T_c + 237.3)) /
                                (0.6108 * np.exp(17.27 * Td_c / (Td_c + 237.3)))),
                0, 100
            ) + 8.313659
        ))
        + np.arctan(T_c + np.clip(
            100 - 5 / 9 * (T_c - Td_c) * 100 / (0.6108 * np.exp(17.27 * T_c / (T_c + 237.3)) /
                            (0.6108 * np.exp(17.27 * Td_c / (Td_c + 237.3)))),
            0, 100
        ))
        - np.arctan(np.clip(
            100 - 5 / 9 * (T_c - Td_c) * 100 / (0.6108 * np.exp(17.27 * T_c / (T_c + 237.3)) /
                            (0.6108 * np.exp(17.27 * Td_c / (Td_c + 237.3)))),
            0, 100
        ) - 1.676331)
        - 4.686035
    )
    df["wetbulb_f"] = Tw_c * 9 / 5 + 32
    df["date"] = df["datetime"].dt.date
    return df


def get_daily_temps(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Returns daily average temperature DataFrame:
    date, avg_temp_f, avg_wetbulb_f, min_temp_f, max_temp_f
    """
    df_hourly = fetch_hourly_temperature(lat, lon, start_date, end_date)
    daily = df_hourly.groupby("date").agg(
        avg_temp_f=("temp_f", "mean"),
        avg_wetbulb_f=("wetbulb_f", "mean"),
        min_temp_f=("temp_f", "min"),
        max_temp_f=("temp_f", "max"),
    ).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    return daily


def get_hourly_temps(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Returns full hourly DataFrame with temp_f and wetbulb_f."""
    return fetch_hourly_temperature(lat, lon, start_date, end_date)


def build_temperature_bins(
    df_hourly: pd.DataFrame,
    bin_size: int = 10,
) -> pd.DataFrame:
    """
    Build temperature bin table from hourly data.
    Returns DataFrame: bin_label, bin_low, bin_high, hours, avg_drybulb_f, avg_wetbulb_f
    """
    bins = list(range(0, 120, bin_size))
    labels = [f"{b}–{b+bin_size}" for b in bins[:-1]]
    df_hourly = df_hourly.copy()
    df_hourly["bin"] = pd.cut(
        df_hourly["temp_f"],
        bins=bins,
        labels=labels,
        right=False
    )
    bin_df = (
        df_hourly.groupby("bin", observed=True)
        .agg(
            hours=("temp_f", "count"),
            avg_drybulb_f=("temp_f", "mean"),
            avg_wetbulb_f=("wetbulb_f", "mean"),
        )
        .reset_index()
    )
    bin_df["bin_low"] = [int(str(b).split("–")[0]) for b in bin_df["bin"]]
    bin_df["bin_high"] = [int(str(b).split("–")[1]) for b in bin_df["bin"]]
    return bin_df[bin_df["hours"] > 0].reset_index(drop=True)
