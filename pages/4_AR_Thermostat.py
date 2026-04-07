"""
ARC 2.7221 — Thermostat Setback / Setpoint Optimization
ASHRAE Guideline 14 change-point regression on smart meter + Open-Meteo weather data.
"""
import streamlit as st
import sys, os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from utils.weather import zip_to_latlon, get_daily_temps
from arcs.arc_2_7221_thermostat import (
    prepare_smart_meter_data, merge_weather_and_meter,
    fit_all_models, compute_thermostat_savings, best_model_label,
    model_2P, model_3PC, model_3PH, model_4P, model_5P
)

st.set_page_config(page_title="ARC 2.7221 — Thermostat Setback", layout="wide")
init_session()

st.title("AR: Thermostat Setback / Setpoint Optimization (ARC 2.7221)")
st.caption("ASHRAE Guideline 14 change-point regression using smart meter data and Open-Meteo historical weather.")

_defs = get_defaults("2.7221")

# ── Narrative ─────────────────────────────────────────────────────────────────
with st.expander("Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value=st.session_state.get("therm_ar_num", "AR-1"), key="therm_ar_num")
    obs = c1.text_area(
        "Observation",
        value=st.session_state.get("therm_obs", _defs["observation"]),
        height=110, key="therm_obs"
    )
    rec = c2.text_area(
        "Recommendation",
        value=st.session_state.get("therm_rec", _defs["recommendation"]),
        height=110, key="therm_rec"
    )
    tech = c2.text_area(
        "Technology Description",
        value=st.session_state.get("therm_tech", _defs["tech_description"]),
        height=110, key="therm_tech"
    )

# ── Sample CSV Downloads ───────────────────────────────────────────────────────
st.subheader("Step 0 — Download Sample CSV Templates")
st.info(
    "If you don't have a smart meter CSV yet, download one of the sample templates below "
    "to see the expected format, then upload your own file in Step 1."
)

def _make_daily_sample() -> bytes:
    import random
    random.seed(42)
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    # Louisiana-style: high base ~4000 kWh/day, plus summer cooling peaks
    month_factor = {1: 0.72, 2: 0.75, 3: 0.82, 4: 0.88, 5: 1.05,
                    6: 1.18, 7: 1.25, 8: 1.22, 9: 1.10, 10: 0.90, 11: 0.78, 12: 0.74}
    rows = []
    for d in dates:
        base = 4000 * month_factor.get(d.month, 1.0)
        noise = random.gauss(0, 120)
        rows.append({"date": d.strftime("%Y-%m-%d"), "kwh": round(max(base + noise, 800), 1)})
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode()

def _make_hourly_sample() -> bytes:
    import random
    random.seed(7)
    timestamps = pd.date_range("2024-07-01", periods=48, freq="h")
    rows = []
    for ts in timestamps:
        # Hourly kWh from a ~4000 kWh/day facility — peak midday, low overnight
        hour = ts.hour
        load_shape = 0.65 + 0.45 * np.sin(np.pi * (hour - 6) / 12) if 6 <= hour <= 22 else 0.55
        base = (4000 / 24) * load_shape * 1.18  # July peak
        noise = random.gauss(0, 5)
        rows.append({"timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"), "kwh": round(max(base + noise, 50), 2)})
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode()

def _make_15min_sample() -> bytes:
    import random
    random.seed(13)
    timestamps = pd.date_range("2024-07-01", periods=192, freq="15min")
    rows = []
    for ts in timestamps:
        hour = ts.hour
        load_shape = 0.65 + 0.45 * np.sin(np.pi * (hour - 6) / 12) if 6 <= hour <= 22 else 0.55
        base = (4000 / 96) * load_shape * 1.18
        noise = random.gauss(0, 1.5)
        rows.append({"timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"), "kwh": round(max(base + noise, 10), 3)})
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode()

dl_c1, dl_c2, dl_c3 = st.columns(3)
dl_c1.download_button(
    "⬇ Sample — Daily (10 rows)",
    data=_make_daily_sample(),
    file_name="sample_daily_meter.csv",
    mime="text/csv",
    key="dl_daily",
)
dl_c2.download_button(
    "⬇ Sample — Hourly (48 rows / 2 days)",
    data=_make_hourly_sample(),
    file_name="sample_hourly_meter.csv",
    mime="text/csv",
    key="dl_hourly",
)
dl_c3.download_button(
    "⬇ Sample — 15-min (192 rows / 2 days)",
    data=_make_15min_sample(),
    file_name="sample_15min_meter.csv",
    mime="text/csv",
    key="dl_15min",
)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_raw, tab_weather, tab_regression, tab_savings = st.tabs(
    ["Raw Data", "Weather", "Regression", "Savings"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Raw Data
# ═══════════════════════════════════════════════════════════════════════════════
with tab_raw:
    st.subheader("Step 1 — Upload Smart Meter CSV")
    st.info(
        "Upload your interval meter export. The file must contain at least a timestamp column "
        "and a kWh column. Temperature is **not** required — weather data is fetched automatically "
        "in the Weather tab."
    )

    interval = st.selectbox(
        "Interval type of your meter data",
        options=["Daily", "Hourly", "15-minute"],
        index=0,
        key="therm_interval",
        help="Select the recording interval of your CSV. Sub-daily data will be aggregated to daily totals."
    )

    uploaded_file = st.file_uploader(
        "Upload smart meter CSV", type=["csv", "txt"],
        key="therm_upload",
        help="CSV file with at least two columns: timestamp/date and kWh."
    )

    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file)
            st.session_state["therm_df_raw"] = df_raw
            st.success(f"Loaded {len(df_raw):,} rows × {df_raw.shape[1]} columns.")
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            st.stop()

    df_raw = st.session_state.get("therm_df_raw")

    if df_raw is not None:
        st.markdown("**Preview (first 20 rows)**")
        st.dataframe(df_raw.head(20), use_container_width=True, hide_index=True)

        st.subheader("Step 2 — Map Columns")
        col_names = list(df_raw.columns)

        mc1, mc2 = st.columns(2)
        # Try to auto-detect reasonable defaults
        ts_default = next(
            (i for i, c in enumerate(col_names)
             if any(x in c.lower() for x in ["time", "date", "timestamp"])), 0
        )
        kwh_default = next(
            (i for i, c in enumerate(col_names)
             if any(x in c.lower() for x in ["kwh", "kw", "energy", "usage", "consumption"])), 
            min(1, len(col_names) - 1)
        )

        ts_col = mc1.selectbox(
            "Which column is the timestamp / date?",
            options=col_names,
            index=ts_default,
            key="therm_ts_col"
        )
        kwh_col = mc2.selectbox(
            "Which column is kWh?",
            options=col_names,
            index=kwh_default,
            key="therm_kwh_col"
        )

        if st.button("Aggregate to Daily", type="primary", key="therm_agg_btn"):
            interval_map = {"Daily": "daily", "Hourly": "hourly", "15-minute": "15-min"}
            try:
                df_daily = prepare_smart_meter_data(
                    df_raw, ts_col, kwh_col, interval=interval_map[interval]
                )
                st.session_state["therm_df_daily"] = df_daily
                st.session_state["therm_ts_col_used"] = ts_col
                st.session_state["therm_kwh_col_used"] = kwh_col
            except Exception as e:
                st.error(f"Aggregation failed: {e}")

        df_daily = st.session_state.get("therm_df_daily")
        if df_daily is not None:
            st.success(
                f"Aggregated to **{len(df_daily):,} daily rows** from "
                f"{df_daily['date'].min().strftime('%Y-%m-%d')} to "
                f"{df_daily['date'].max().strftime('%Y-%m-%d')}."
            )
            st.dataframe(df_daily.head(20), use_container_width=True, hide_index=True)

            # Quick time-series preview
            fig_ts = px.line(
                df_daily, x="date", y="kwh_daily",
                title="Daily kWh — Meter Data",
                labels={"date": "Date", "kwh_daily": "Daily kWh"},
                color_discrete_sequence=["#1B4F72"],
            )
            fig_ts.update_layout(
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Inter, sans-serif", size=13),
                margin=dict(l=60, r=20, t=50, b=40),
            )
            st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.info("Upload a CSV above to get started.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Weather
# ═══════════════════════════════════════════════════════════════════════════════
with tab_weather:
    st.subheader("Step 3 — Fetch Historical Weather")
    st.info(
        "Enter the facility zip code to fetch matching daily average temperature data from "
        "Open-Meteo (ERA5 reanalysis archive). The date range is pulled automatically from "
        "your uploaded meter data."
    )

    df_daily = st.session_state.get("therm_df_daily")

    if df_daily is None:
        st.warning("Complete Step 1 & 2 (Raw Data tab) first to determine the date range.")
    else:
        date_min = df_daily["date"].min()
        date_max = df_daily["date"].max()
        st.markdown(
            f"Meter data spans **{date_min.strftime('%Y-%m-%d')}** → "
            f"**{date_max.strftime('%Y-%m-%d')}** "
            f"({(date_max - date_min).days + 1} days)."
        )

        wc1, wc2 = st.columns([1, 3])
        zip_code = wc1.text_input("Facility Zip Code", value="70501", key="therm_zip")

        if wc2.button("Fetch Weather from Open-Meteo", type="primary", key="therm_fetch_wx"):
            with st.spinner("Resolving zip code and fetching weather data…"):
                try:
                    lat, lon, city = zip_to_latlon(zip_code)
                    st.session_state["therm_city"] = city
                    st.session_state["therm_lat"] = lat
                    st.session_state["therm_lon"] = lon

                    df_weather = get_daily_temps(
                        lat, lon,
                        start_date=date_min.strftime("%Y-%m-%d"),
                        end_date=date_max.strftime("%Y-%m-%d"),
                    )
                    st.session_state["therm_weather_df"] = df_weather
                    st.success(
                        f"Fetched weather for **{city}** "
                        f"(lat {lat:.4f}, lon {lon:.4f}) — "
                        f"{len(df_weather)} days returned."
                    )
                except ValueError as ve:
                    st.error(str(ve))
                except Exception as e:
                    st.error(f"Weather fetch failed: {e}")

        df_weather = st.session_state.get("therm_weather_df")

        if df_weather is not None:
            city = st.session_state.get("therm_city", zip_code)
            st.markdown(
                f"**{city}** — {len(df_weather)} daily temperature records loaded."
            )

            # Weather summary metrics
            wm1, wm2, wm3, wm4 = st.columns(4)
            wm1.metric("Mean Temp (°F)", f"{df_weather['avg_temp_f'].mean():.1f}")
            wm2.metric("Min Daily Avg (°F)", f"{df_weather['avg_temp_f'].min():.1f}")
            wm3.metric("Max Daily Avg (°F)", f"{df_weather['avg_temp_f'].max():.1f}")
            cool_days = (df_weather["avg_temp_f"] > 65).sum()
            wm4.metric("Days > 65°F", f"{cool_days}")

            fig_wx = px.line(
                df_weather, x="date", y="avg_temp_f",
                title=f"Daily Average Temperature — {city}",
                labels={"date": "Date", "avg_temp_f": "Avg Temp (°F)"},
                color_discrete_sequence=["#C0392B"],
            )
            fig_wx.add_hline(y=65, line_dash="dash", line_color="#7F8C8D",
                             annotation_text="65°F reference", annotation_position="bottom right")
            fig_wx.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                font=dict(family="Inter, sans-serif", size=13),
                margin=dict(l=60, r=20, t=50, b=40),
            )
            st.plotly_chart(fig_wx, use_container_width=True)

            # Merge with meter data
            if st.button("Merge Weather + Meter Data", type="primary", key="therm_merge_btn"):
                try:
                    df_merged = merge_weather_and_meter(df_daily, df_weather)
                    st.session_state["therm_merged_df"] = df_merged
                    if len(df_merged) < 30:
                        st.warning(
                            f"Only {len(df_merged)} matched days. Regression accuracy may be low — "
                            "at least 30 days of overlapping data is recommended."
                        )
                    else:
                        st.success(
                            f"Merged dataset: **{len(df_merged)} days** with matching "
                            "meter + weather data."
                        )
                except Exception as e:
                    st.error(f"Merge failed: {e}")

            df_merged = st.session_state.get("therm_merged_df")
            if df_merged is not None:
                st.markdown(f"**Merged rows: {len(df_merged)}**")
                st.dataframe(df_merged.head(20), use_container_width=True, hide_index=True)

                # Scatter preview
                fig_sc = px.scatter(
                    df_merged, x="avg_temp_f", y="kwh_daily",
                    title="Temp vs. Daily kWh (Scatter Preview)",
                    labels={"avg_temp_f": "Daily Avg Temp (°F)", "kwh_daily": "Daily kWh"},
                    opacity=0.65,
                    color_discrete_sequence=["#1B4F72"],
                )
                fig_sc.update_layout(
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(family="Inter, sans-serif", size=13),
                    margin=dict(l=60, r=20, t=50, b=40),
                )
                st.plotly_chart(fig_sc, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Regression
# ═══════════════════════════════════════════════════════════════════════════════
with tab_regression:
    st.subheader("Step 4 — ASHRAE GL14 Change-Point Regression")
    st.info(
        "The app fits five change-point models to the merged daily data. The best model is "
        "selected automatically by highest R², but you may override the selection below. "
        "Models: **2P** (constant), **3PC** (cooling), **3PH** (heating), "
        "**4P** (V-shape), **5P** (full GL14)."
    )

    df_merged = st.session_state.get("therm_merged_df")

    if df_merged is None:
        st.warning("Complete the Weather tab (merge step) first.")
    else:
        if st.button("Run ASHRAE GL14 Regression", type="primary", key="therm_run_reg"):
            with st.spinner("Fitting 5 models…"):
                try:
                    results = fit_all_models(
                        df_merged,
                        temp_col="avg_temp_f",
                        energy_col="kwh_daily"
                    )
                    st.session_state["therm_regression_results"] = results
                    best = results.get("best", "2P")
                    st.session_state["therm_selected_model"] = best
                    st.success(
                        f"Regression complete. Best model: **{best}** "
                        f"(R² = {results[best]['r2']:.4f})"
                    )
                except Exception as e:
                    st.error(f"Regression failed: {e}")

        results = st.session_state.get("therm_regression_results")

        if results is not None:
            # ── R² Table ──────────────────────────────────────────────────────
            MODEL_NAMES = {
                "2P":  "2-Parameter (Constant)",
                "3PC": "3-Parameter Cooling",
                "3PH": "3-Parameter Heating",
                "4P":  "4-Parameter (V-shape)",
                "5P":  "5-Parameter (Full GL14)",
            }
            best = results.get("best", "2P")
            table_rows = []
            for key in ["2P", "3PC", "3PH", "4P", "5P"]:
                r = results.get(key, {})
                if r.get("success"):
                    status = "✓ Converged"
                    r2_val = f"{r['r2']:.4f}"
                    cv_val = f"{r['cvrmse']:.2f}%"
                else:
                    status = "✗ Failed"
                    r2_val = "—"
                    cv_val = "—"
                is_best = "★ Best" if key == best else ""
                table_rows.append({
                    "Model": MODEL_NAMES[key],
                    "Key": key,
                    "R²": r2_val,
                    "CV(RMSE)": cv_val,
                    "Status": status,
                    "Selected": is_best,
                })

            df_table = pd.DataFrame(table_rows)
            st.markdown("#### Model Comparison")
            # Highlight the best row
            def _highlight_best(row):
                if row["Key"] == best:
                    return ["background-color: #D6EAF8; font-weight: bold"] * len(row)
                return [""] * len(row)

            st.dataframe(
                df_table.drop(columns=["Key"]).style.apply(_highlight_best, axis=1),
                use_container_width=True,
                hide_index=True,
            )

            # ── Model selection override ───────────────────────────────────────
            converged_models = [k for k in ["2P", "3PC", "3PH", "4P", "5P"]
                                if results.get(k, {}).get("success", False)]
            model_options = [f"{k} — {MODEL_NAMES[k]}" for k in converged_models]
            best_idx = converged_models.index(best) if best in converged_models else 0

            sel_label = st.selectbox(
                "Select model for savings calculation (default = best by R²):",
                options=model_options,
                index=best_idx,
                key="therm_model_select",
            )
            selected_model = sel_label.split(" — ")[0].strip()
            st.session_state["therm_selected_model"] = selected_model

            # ── Scatter + Model Fit Lines ──────────────────────────────────────
            T_range = np.linspace(df_merged["avg_temp_f"].min() - 2,
                                  df_merged["avg_temp_f"].max() + 2, 300)

            MODEL_COLORS = {
                "2P":  "#1B4F72",
                "3PC": "#E74C3C",
                "3PH": "#2E86C1",
                "4P":  "#27AE60",
                "5P":  "#8E44AD",
            }
            MODEL_FUNCS = {
                "2P": model_2P,
                "3PC": model_3PC,
                "3PH": model_3PH,
                "4P": model_4P,
                "5P": model_5P,
            }

            fig_reg = go.Figure()

            # Scatter data points
            fig_reg.add_trace(go.Scatter(
                x=df_merged["avg_temp_f"],
                y=df_merged["kwh_daily"],
                mode="markers",
                marker=dict(color="#1B4F72", size=6, opacity=0.55),
                name="Observed Daily kWh",
            ))

            # Model fit lines
            for key in ["2P", "3PC", "3PH", "4P", "5P"]:
                r = results.get(key, {})
                if r.get("success"):
                    E_fit = MODEL_FUNCS[key](T_range, *r["params"])
                    line_width = 3 if key == selected_model else 1.5
                    line_dash = "solid" if key == selected_model else "dot"
                    label = f"{key} (R²={r['r2']:.3f})"
                    if key == selected_model:
                        label += " ← selected"
                    fig_reg.add_trace(go.Scatter(
                        x=T_range, y=E_fit,
                        mode="lines",
                        line=dict(color=MODEL_COLORS[key], width=line_width, dash=line_dash),
                        name=label,
                    ))

            fig_reg.update_layout(
                title="ASHRAE GL14 — All Model Fits",
                xaxis_title="Daily Average Temperature (°F)",
                yaxis_title="Daily kWh",
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Inter, sans-serif", size=13),
                legend=dict(orientation="v", x=1.01, y=1),
                margin=dict(l=60, r=200, t=60, b=50),
            )
            fig_reg.update_xaxes(showgrid=True, gridcolor="#ECF0F1")
            fig_reg.update_yaxes(showgrid=True, gridcolor="#ECF0F1")
            st.plotly_chart(fig_reg, use_container_width=True)

            # ── Selected model parameters ──────────────────────────────────────
            sel_result = results.get(selected_model, {})
            if sel_result.get("success"):
                st.markdown(f"#### Selected Model: {selected_model} — {MODEL_NAMES[selected_model]}")
                param_names = {
                    "2P":  ["b0 (base kWh/day)"],
                    "3PC": ["b0 (base kWh/day)", "b1 (kWh/°F·day cooling)", "Tc (cooling CP °F)"],
                    "3PH": ["b0 (base kWh/day)", "b1 (kWh/°F·day heating)", "Th (heating CP °F)"],
                    "4P":  ["b0 (base kWh/day)", "b1 (cooling slope)", "b2 (heating slope)", "Tcp (CP °F)"],
                    "5P":  ["b0 (base kWh/day)", "b1 (cooling slope)", "b2 (heating slope)",
                            "Tc (cooling CP °F)", "Th (heating CP °F)"],
                }
                params = sel_result["params"]
                names = param_names.get(selected_model, [f"p{i}" for i in range(len(params))])
                param_df = pd.DataFrame({
                    "Parameter": names,
                    "Value": [f"{p:.4f}" for p in params],
                })
                pmc1, pmc2 = st.columns([1, 1])
                pmc1.dataframe(param_df, use_container_width=True, hide_index=True)
                pmc2.metric("R²", f"{sel_result['r2']:.4f}")
                pmc2.metric("CV(RMSE)", f"{sel_result['cvrmse']:.2f}%")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Savings
# ═══════════════════════════════════════════════════════════════════════════════
with tab_savings:
    st.subheader("Step 5 — Thermostat Setpoint Savings")
    st.info(
        "Enter the proposed setpoint adjustments and facility area details. "
        "Savings are calculated from the regression slope and scaled to the assessed area."
    )

    results = st.session_state.get("therm_regression_results")
    df_merged = st.session_state.get("therm_merged_df")
    selected_model = st.session_state.get("therm_selected_model", "2P")
    rates = get_utility_rates()

    if results is None or df_merged is None:
        st.warning("Complete the Regression tab first.")
    else:
        MODEL_NAMES = {
            "2P":  "2-Parameter (Constant)",
            "3PC": "3-Parameter Cooling",
            "3PH": "3-Parameter Heating",
            "4P":  "4-Parameter (V-shape)",
            "5P":  "5-Parameter (Full GL14)",
        }
        st.markdown(
            f"Using model: **{selected_model} — {MODEL_NAMES.get(selected_model, selected_model)}** "
            f"(R² = {results.get(selected_model, {}).get('r2', 0):.4f})"
        )

        st.markdown("#### Setpoint Adjustments")
        sp_c1, sp_c2 = st.columns(2)
        delta_T_cooling = sp_c1.number_input(
            "Cooling setpoint raise (°F)",
            min_value=0.0, max_value=20.0, value=4.0, step=0.5,
            key="therm_dT_cool",
            help="Degrees to raise the cooling setpoint during unoccupied hours (positive = savings)."
        )
        delta_T_heating = sp_c2.number_input(
            "Heating setpoint lower (°F)",
            min_value=0.0, max_value=20.0, value=4.0, step=0.5,
            key="therm_dT_heat",
            help="Degrees to lower the heating setpoint during unoccupied hours (positive = savings)."
        )

        st.markdown("#### Facility Area Scaling")
        sc_c1, sc_c2 = st.columns(2)
        total_area = sc_c1.number_input(
            "Total facility area (ft²)",
            min_value=0.0, value=50000.0, step=1000.0,
            key="therm_total_area",
            help="Gross conditioned floor area of the entire facility."
        )
        assessed_area = sc_c2.number_input(
            "Assessed / affected area (ft²)",
            min_value=0.0, value=50000.0, step=1000.0,
            key="therm_assessed_area",
            help="Area served by the thermostats being setback. Savings are scaled by assessed/total."
        )
        area_fraction = assessed_area / total_area if total_area > 0 else 1.0
        st.caption(f"Area scaling fraction: {area_fraction:.3f} ({assessed_area:,.0f} / {total_area:,.0f} ft²)")

        st.markdown("#### Utility Rate")
        default_rate = round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.10
        elec_rate = st.number_input(
            "Electricity rate ($/kWh)",
            min_value=0.0, value=default_rate, step=0.001, format="%.4f",
            key="therm_elec_rate",
        )

        if st.button("Calculate Savings", type="primary", key="therm_calc_savings"):
            T_arr = df_merged["avg_temp_f"].values.astype(float)
            E_arr = df_merged["kwh_daily"].values.astype(float)

            try:
                savings_result = compute_thermostat_savings(
                    results=results,
                    model_name=selected_model,
                    T_arr=T_arr,
                    E_arr=E_arr,
                    delta_T_cooling=delta_T_cooling,
                    delta_T_heating=delta_T_heating,
                    ann_days=365,
                )

                if not savings_result.get("success"):
                    st.error(f"Savings calculation failed: {savings_result.get('error', 'Unknown error')}")
                else:
                    whole_facility_kwh = savings_result["ann_savings_kwh"]
                    scaled_kwh = whole_facility_kwh * area_fraction
                    cost_savings = scaled_kwh * elec_rate
                    # Setpoint-only change: no capital cost → payback = 0
                    payback = 0.0

                    savings_result["scaled_kwh"] = scaled_kwh
                    savings_result["cost_savings"] = cost_savings
                    savings_result["area_fraction"] = area_fraction
                    savings_result["elec_rate"] = elec_rate
                    st.session_state["therm_savings"] = savings_result

            except Exception as e:
                st.error(f"Error: {e}")

        sav = st.session_state.get("therm_savings")
        if sav is not None and sav.get("success"):
            whole_kwh = sav["ann_savings_kwh"]
            scaled_kwh = sav["scaled_kwh"]
            cost_sav = sav["cost_savings"]
            frac = sav["area_fraction"]

            st.markdown("#### Results")
            res_c1, res_c2, res_c3, res_c4 = st.columns(4)
            res_c1.metric("Whole-Facility kWh Savings", f"{whole_kwh:,.0f} kWh/yr")
            res_c2.metric(
                f"Scaled Savings ({frac:.0%} area)",
                f"{scaled_kwh:,.0f} kWh/yr"
            )
            res_c3.metric("Annual Cost Savings", f"${cost_sav:,.0f}/yr")
            res_c4.metric("Simple Payback", "0 yr (no capital cost)")

            # Bar chart: baseline vs proposed
            df_merged_loc = st.session_state.get("therm_merged_df")
            if df_merged_loc is not None:
                baseline_ann = df_merged_loc["kwh_daily"].mean() * 365 * frac
                proposed_ann = baseline_ann - scaled_kwh

                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    x=["Baseline (Current)", "Proposed (After Setback)"],
                    y=[baseline_ann, proposed_ann],
                    marker_color=["#1B4F72", "#2E86C1"],
                    text=[f"{baseline_ann:,.0f} kWh", f"{proposed_ann:,.0f} kWh"],
                    textposition="outside",
                    width=0.4,
                ))
                fig_bar.update_layout(
                    title="Annual kWh — Baseline vs. Proposed",
                    yaxis_title="Annual kWh",
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    font=dict(family="Inter, sans-serif", size=13),
                    margin=dict(l=60, r=20, t=60, b=50),
                    showlegend=False,
                )
                fig_bar.update_yaxes(showgrid=True, gridcolor="#ECF0F1")
                st.plotly_chart(fig_bar, use_container_width=True)

            # ── Save to AR List ────────────────────────────────────────────────
            st.divider()
            if st.button("💾 Save this AR to Report", type="primary", key="therm_save"):
                sel_result = results.get(selected_model, {})
                ar_entry = {
                    "arc_code": "2.7221",
                    "ar_number": st.session_state.get("therm_ar_num", "AR-1"),
                    "title": "Thermostat Setback / Setpoint Optimization",
                    "resources": [
                        {
                            "type": "Electricity",
                            "savings": scaled_kwh,
                            "unit": "kWh",
                        }
                    ],
                    "total_cost_savings": cost_sav,
                    "implementation_cost": 0.0,
                    "payback": 0.0,
                    "observation": st.session_state.get("therm_obs", ""),
                    "recommendation": st.session_state.get("therm_rec", ""),
                    "tech_description": st.session_state.get("therm_tech", ""),
                    "calculation_details": {
                        "model": selected_model,
                        "model_label": MODEL_NAMES.get(selected_model, selected_model),
                        "params": list(sel_result.get("params", [])),
                        "r2": sel_result.get("r2", 0),
                        "cvrmse": sel_result.get("cvrmse", 0),
                        "delta_T_cooling_f": delta_T_cooling,
                        "delta_T_heating_f": delta_T_heating,
                        "whole_facility_ann_kwh_savings": whole_kwh,
                        "area_fraction": frac,
                        "scaled_ann_kwh_savings": scaled_kwh,
                        "elec_rate": elec_rate,
                        "ann_cost_savings": cost_sav,
                        "interval": st.session_state.get("therm_interval", ""),
                        "zip_code": st.session_state.get("therm_zip", ""),
                        "city": st.session_state.get("therm_city", ""),
                        "meter_days": int(len(df_merged)) if df_merged is not None else 0,
                    },
                }
                ar_list = st.session_state.get("ar_list", [])
                # Remove existing entry with same arc_code + ar_number to allow re-save
                ar_list = [
                    a for a in ar_list
                    if not (a.get("arc_code") == "2.7221"
                            and a.get("ar_number") == ar_entry["ar_number"])
                ]
                ar_list.append(ar_entry)
                st.session_state["ar_list"] = ar_list
                st.success(
                    f"✅ {ar_entry['ar_number']} saved. "
                    f"Savings: {scaled_kwh:,.0f} kWh/yr · ${cost_sav:,.0f}/yr. "
                    f"Total ARs in report: {len(ar_list)}."
                )
