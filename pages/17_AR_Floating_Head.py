"""
ARC 2.2621 — Modify Refrigeration System to Operate at Lower (Floating) Head Pressure
Calculates compressor energy savings by allowing condensing temp to float with ambient conditions.
"""
import streamlit as st
import sys, os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from utils.weather import zip_to_latlon, get_hourly_temps, build_temperature_bins
from arcs.arc_2_2621_floating_head import (
    run_floating_head_analysis,
    run_bin_analysis,
    REFRIGERANTS,
    CONDENSER_OFFSETS,
)

NAVY = "#003366"

st.set_page_config(page_title="ARC 2.2621 — Floating Head Pressure", layout="wide")
init_session()

st.title("AR: Floating Head Pressure Control (ARC 2.2621)")
st.caption(
    "Allow condensing temperature to follow ambient conditions rather than a fixed setpoint. "
    "Lower condensing temp → lower pressure ratio → less compressor work → energy savings."
)

_defs = get_defaults("2.2621")
rates = get_utility_rates()

tab1, tab2, tab3, tab4 = st.tabs(["System Design", "Weather & Bins", "Simulation", "Results"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — System Design
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    with st.expander("📝 Observation & Recommendation", expanded=True):
        c1, c2 = st.columns(2)
        obs = c1.text_area(
            "Observation",
            value=st.session_state.get("fh_obs", _defs.get("observation", "")),
            height=110,
            key="fh_obs",
        )
        rec = c2.text_area(
            "Recommendation",
            value=st.session_state.get("fh_rec", _defs.get("recommendation", "")),
            height=110,
            key="fh_rec",
        )
        tech = c1.text_area(
            "Technology Description",
            value=st.session_state.get("fh_tech", _defs.get("tech_description", "")),
            height=110,
            key="fh_tech",
        )

    ar_num = st.text_input(
        "AR Number",
        value=st.session_state.get("fh_ar_num", "AR-1"),
        key="fh_ar_num",
    )

    st.subheader("Refrigeration System")

    col1, col2, col3 = st.columns(3)
    ref_name = col1.selectbox(
        "Refrigerant",
        options=list(REFRIGERANTS.keys()),
        key="fh_ref",
    )
    condenser_type = col2.selectbox(
        "Condenser type",
        options=["Air-cooled", "Water-cooled", "Evaporative"],
        key="fh_cond_type",
        help=(
            "Air-cooled: floating T_cond = drybulb + offset. "
            "Water-cooled/Evaporative: floating T_cond = wetbulb + offset."
        ),
    )
    system_type = col3.selectbox(
        "System type",
        options=["Single-stage", "Two-stage"],
        key="fh_sys_type",
        help="Note: two-stage calculation uses same single-stage engine (engineering note only).",
    )

    # Show the offset that will be used
    offsets_info = CONDENSER_OFFSETS.get(condenser_type, CONDENSER_OFFSETS["Air-cooled"])
    st.info(
        f"**{condenser_type} offsets (ASHRAE):** "
        f"Fixed condensing = ambient + **{offsets_info['fixed_offset_f']:.0f}°F** {offsets_info['ambient_type']} | "
        f"Floating target = ambient + **{offsets_info['float_offset_f']:.0f}°F** {offsets_info['ambient_type']}"
    )

    st.subheader("Temperature Setpoints")

    # Preset helper
    preset = st.selectbox(
        "Preset application type (sets evap temp default)",
        options=["Custom", "Freezer (−23°F evap)", "Cooler (18°F evap)", "Air Conditioning (40°F evap)"],
        key="fh_preset",
    )
    preset_evap = {
        "Custom": None,
        "Freezer (−23°F evap)": -23.0,
        "Cooler (18°F evap)": 18.0,
        "Air Conditioning (40°F evap)": 40.0,
    }[preset]

    col1, col2 = st.columns(2)
    evap_temp = col1.number_input(
        "Evaporating temperature (°F)",
        value=float(preset_evap) if preset_evap is not None else 18.0,
        min_value=-80.0,
        max_value=60.0,
        step=1.0,
        key="fh_evap_temp",
        help="Fixed evaporating temperature (saturation temp at suction pressure)",
    )
    fixed_cond_temp = col2.number_input(
        "Fixed condensing temperature (°F) — current setpoint",
        value=105.0,
        min_value=60.0,
        max_value=160.0,
        step=1.0,
        key="fh_fixed_cond",
        help="Current fixed condensing temperature at rated conditions",
    )

    col1, col2 = st.columns(2)
    min_cond_temp = col1.number_input(
        "Minimum condensing temperature (°F) — safety floor",
        value=70.0,
        min_value=40.0,
        max_value=120.0,
        step=1.0,
        key="fh_min_cond",
        help="Minimum allowable condensing temp to maintain adequate head pressure for TXV/metering device",
    )
    col2.markdown(
        f"*Floating temp range: {min_cond_temp:.0f}°F (min) → {fixed_cond_temp:.0f}°F (max)*"
    )

    st.subheader("Compressor Capacity")

    col1, col2 = st.columns(2)
    comp_hp = col1.number_input(
        "Total compressor rated HP",
        value=100.0,
        min_value=1.0,
        step=5.0,
        key="fh_comp_hp",
    )
    comp_kw_meas = col2.number_input(
        "Measured compressor kW (optional — enter 0 to use rated HP)",
        value=0.0,
        min_value=0.0,
        step=1.0,
        key="fh_comp_kw_meas",
        help="If measured, used instead of rated HP for more accurate baseline power",
    )

    st.subheader("Cycle Parameters")

    col1, col2, col3 = st.columns(3)
    isen_eff = col1.number_input(
        "Isentropic efficiency (%)",
        value=70.0,
        min_value=30.0,
        max_value=95.0,
        step=1.0,
        key="fh_isen",
    )
    superheat = col2.number_input(
        "Superheat (°F)",
        value=10.0,
        min_value=0.0,
        max_value=40.0,
        step=1.0,
        key="fh_sh",
    )
    subcooling = col3.number_input(
        "Subcooling (°F)",
        value=5.0,
        min_value=0.0,
        max_value=30.0,
        step=1.0,
        key="fh_sc",
    )

    st.subheader("Utility Rates")
    col1, col2 = st.columns(2)
    elec_rate_fh = col1.number_input(
        "Electricity rate ($/kWh)",
        value=round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.10,
        step=0.001,
        format="%.4f",
        key="fh_elec_rate",
    )
    demand_rate_fh = col2.number_input(
        "Demand rate ($/kW/mo)",
        value=round(rates["demand_rate"], 2) if rates["demand_rate"] > 0 else 0.0,
        step=1.0,
        key="fh_demand_rate",
    )

    st.markdown("---")
    st.caption(
        "**Citations:** "
        "Air-cooled offset: ASHRAE 90.1-2022 §6.5.1.1 (design condensing temp ≤ ambient + 30°F; "
        "floating reset target: ambient + 15°F drybulb). "
        "Water-cooled / evaporative offset: ASHRAE Handbook of Fundamentals 2021, Ch. 39 "
        "(cooling tower approach = 7–10°F above wet-bulb; condensing temp = wet-bulb + 10°F)."
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Weather & Bins
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Hourly Weather Data")

    col1, col2, col3 = st.columns(3)
    fh_zip = col1.text_input("ZIP code", value="70501", key="fh_zip")

    end_default = datetime.today() - timedelta(days=7)
    start_default = end_default - timedelta(days=365)

    fh_start = col2.date_input(
        "Start date",
        value=start_default.date(),
        key="fh_start_date",
    )
    fh_end = col3.date_input(
        "End date",
        value=end_default.date(),
        key="fh_end_date",
    )

    if st.button("🌡️ Fetch Hourly Weather", key="fh_fetch_wx"):
        with st.spinner("Resolving ZIP and fetching weather data…"):
            try:
                lat, lon, city = zip_to_latlon(fh_zip)
                df_wx = get_hourly_temps(
                    lat, lon,
                    fh_start.strftime("%Y-%m-%d"),
                    fh_end.strftime("%Y-%m-%d"),
                )
                st.session_state["fh_hourly_weather"] = df_wx
                st.session_state["fh_city"] = city
                st.session_state["fh_bins"] = None  # reset bins on new weather fetch
                st.success(
                    f"✅ Fetched {len(df_wx):,} hourly records for **{city}** "
                    f"(lat {lat:.3f}, lon {lon:.3f})"
                )
            except Exception as e:
                st.error(f"Weather fetch failed: {e}")

    if "fh_hourly_weather" in st.session_state:
        df_wx = st.session_state["fh_hourly_weather"]
        city = st.session_state.get("fh_city", fh_zip)

        st.caption(
            f"Location: **{city}** | {len(df_wx):,} hours | "
            f"Drybulb avg: {df_wx['temp_f'].mean():.1f}°F | "
            f"Wetbulb avg: {df_wx['wetbulb_f'].mean():.1f}°F"
        )

        # Temperature frequency histogram
        fig_hist = px.histogram(
            df_wx, x="temp_f", nbins=40,
            title=f"Drybulb Temperature Frequency Distribution — {city}",
            labels={"temp_f": "Outdoor Drybulb Temperature (°F)"},
            color_discrete_sequence=[NAVY],
        )
        fig_hist.update_layout(height=320, margin=dict(t=40, b=40))
        st.plotly_chart(fig_hist, use_container_width=True)

        if st.button("🗂️ Build Temperature Bin Table", key="fh_build_bins"):
            with st.spinner("Building temperature bins…"):
                try:
                    bin_df = build_temperature_bins(df_wx, bin_size=10)
                    st.session_state["fh_bins"] = bin_df
                    st.success(f"✅ Built {len(bin_df)} temperature bins.")
                except Exception as e:
                    st.error(f"Bin build error: {e}")

    if st.session_state.get("fh_bins") is not None:
        bin_df = st.session_state["fh_bins"]
        total_hrs = bin_df["hours"].sum()
        most_common = bin_df.loc[bin_df["hours"].idxmax()]

        col1, col2 = st.columns(2)
        col1.metric("Total hours in dataset", f"{total_hrs:,}")
        col2.metric(
            "Most common temperature bin",
            f"{most_common['bin_low']:.0f}°F – {most_common['bin_high']:.0f}°F "
            f"({most_common['hours']:,} hrs)",
        )

        disp_bins = bin_df[["bin", "hours", "avg_drybulb_f", "avg_wetbulb_f"]].copy()
        disp_bins.columns = ["Bin", "Hours", "Avg Drybulb (°F)", "Avg Wetbulb (°F)"]
        st.dataframe(
            disp_bins.style.format({
                "Hours": "{:,}",
                "Avg Drybulb (°F)": "{:.1f}",
                "Avg Wetbulb (°F)": "{:.1f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Simulation
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Floating Head Pressure Simulation")

    calc_method = st.radio(
        "Calculation method:",
        options=[
            "Hourly (full hourly dataset — slower, more accurate)",
            "Bin-hour (temperature bins — faster, good for quick estimates)",
        ],
        key="fh_calc_method",
        help="Hourly uses every data point; Bin-hour averages by temperature bin.",
    )
    use_hourly = calc_method.startswith("Hourly")

    wx_ready = "fh_hourly_weather" in st.session_state
    bin_ready = st.session_state.get("fh_bins") is not None

    if use_hourly and not wx_ready:
        st.warning("⚠️ Fetch hourly weather data in the **Weather & Bins** tab first.")
    elif not use_hourly and not bin_ready:
        st.warning("⚠️ Build the temperature bin table in the **Weather & Bins** tab first.")
    else:
        if st.button("▶ Run Floating Head Simulation", type="primary", key="fh_run"):
            with st.spinner("Running simulation (may take a moment for hourly method)…"):
                try:
                    kw_meas = comp_kw_meas if comp_kw_meas > 0 else None

                    if use_hourly:
                        df_wx_run = st.session_state["fh_hourly_weather"]
                        result = run_floating_head_analysis(
                            df_hourly=df_wx_run,
                            refrigerant_name=ref_name,
                            condenser_type=condenser_type,
                            evap_temp_f=evap_temp,
                            fixed_condensing_temp_f=fixed_cond_temp,
                            min_condensing_temp_f=min_cond_temp,
                            compressor_capacity_hp=comp_hp,
                            compressor_kw_measured=kw_meas,
                            isentropic_efficiency=isen_eff / 100.0,
                            superheat_f=superheat,
                            subcooling_f=subcooling,
                            elec_rate=elec_rate_fh,
                            demand_rate=demand_rate_fh,
                        )
                    else:
                        bin_df_run = st.session_state["fh_bins"]
                        result = run_bin_analysis(
                            bin_df=bin_df_run,
                            refrigerant_name=ref_name,
                            condenser_type=condenser_type,
                            evap_temp_f=evap_temp,
                            fixed_condensing_temp_f=fixed_cond_temp,
                            min_condensing_temp_f=min_cond_temp,
                            compressor_capacity_hp=comp_hp,
                            compressor_kw_measured=kw_meas,
                            isentropic_efficiency=isen_eff / 100.0,
                            superheat_f=superheat,
                            subcooling_f=subcooling,
                            elec_rate=elec_rate_fh,
                            demand_rate=demand_rate_fh,
                        )

                    if "error" in result:
                        st.error(f"Simulation error: {result['error']}")
                    else:
                        st.session_state["fh_result"] = result
                        st.session_state["fh_used_hourly"] = use_hourly
                        st.success("✅ Simulation complete.")
                except Exception as e:
                    st.error(f"Unexpected simulation error: {e}")

    if "fh_result" in st.session_state:
        r = st.session_state["fh_result"]
        used_hourly = st.session_state.get("fh_used_hourly", False)

        # Per-bin results table
        st.subheader("Per-Bin Results")

        if used_hourly:
            # Aggregate hourly results into bins for display
            hourly_df = r.get("hourly_df")
            if hourly_df is not None and not hourly_df.empty:
                hourly_df = hourly_df.copy()
                hourly_df["bin"] = (hourly_df["temp_f"] // 10 * 10).astype(int).astype(str) + "–" + \
                                   (hourly_df["temp_f"] // 10 * 10 + 10).astype(int).astype(str)
                bin_summary = hourly_df.groupby("bin").agg(
                    hours=("kw_saved", "count"),
                    t_cond_fixed_f=("t_cond_fixed_f", "mean"),
                    t_cond_float_f=("t_cond_float_f", "mean"),
                    cop_fixed=("cop_fixed", "mean"),
                    cop_float=("cop_float", "mean"),
                    kw_fixed=("kw_fixed", "mean"),
                    kw_float=("kw_float", "mean"),
                    kw_saved=("kw_saved", "mean"),
                    kwh_saved=("kw_saved", "sum"),
                ).reset_index()
                disp_bins_r = bin_summary
            else:
                disp_bins_r = None
        else:
            disp_bins_r = r.get("bin_df")

        if disp_bins_r is not None and not disp_bins_r.empty:
            fmt_cols = {
                "t_cond_fixed_f": "{:.1f}",
                "t_cond_float_f": "{:.1f}",
                "cop_fixed": "{:.3f}",
                "cop_float": "{:.3f}",
                "kw_fixed": "{:.2f}",
                "kw_float": "{:.2f}",
                "kw_saved": "{:.2f}",
                "kwh_saved": "{:,.0f}",
            }
            st.dataframe(
                disp_bins_r.style.format(fmt_cols),
                use_container_width=True,
                hide_index=True,
            )

            # Bar chart: kWh saved per bin
            fig_bar = px.bar(
                disp_bins_r,
                x="bin",
                y="kwh_saved",
                title="kWh Saved per Temperature Bin",
                labels={"bin": "Temperature Bin (°F)", "kwh_saved": "kWh Saved"},
                color_discrete_sequence=[NAVY],
            )
            fig_bar.update_layout(height=340, margin=dict(t=40, b=40))
            st.plotly_chart(fig_bar, use_container_width=True)

            # Scatter: COP vs condensing temperature
            fig_cop = go.Figure()
            # Fixed COP line
            fig_cop.add_hline(
                y=r.get("cop_fixed", 0),
                line_dash="dash",
                line_color="red",
                annotation_text=f"Fixed COP = {r.get('cop_fixed', 0):.3f}",
                annotation_position="bottom right",
            )
            # Floating COP points
            if "t_cond_float_f" in disp_bins_r.columns:
                fig_cop.add_trace(go.Scatter(
                    x=disp_bins_r["t_cond_float_f"],
                    y=disp_bins_r["cop_float"],
                    mode="markers+lines",
                    marker=dict(color=NAVY, size=8),
                    line=dict(color=NAVY),
                    name="Floating COP",
                ))
            fig_cop.update_layout(
                title="COP vs Condensing Temperature (Fixed vs Floating)",
                xaxis_title="Condensing Temperature (°F)",
                yaxis_title="COP",
                height=340,
                margin=dict(t=40, b=40),
                plot_bgcolor="white",
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_cop, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Results
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Annual Savings Summary")

    if "fh_result" not in st.session_state:
        st.info("Run the simulation in the **Simulation** tab to see results here.")
    else:
        r = st.session_state["fh_result"]

        ann_kwh = r.get("ann_kwh_savings", 0)
        avg_kw = r.get("avg_kw_saved", 0)
        ann_cost = r.get("ann_total_cost_savings", r.get("ann_cost_savings", r.get("ann_energy_cost_savings", 0)))

        c1, c2, c3 = st.columns(3)
        c1.metric("Annual kWh Savings", f"{ann_kwh:,.0f} kWh/yr")
        c2.metric("Average kW Savings", f"{avg_kw:.2f} kW")
        c3.metric("Annual Cost Savings", f"${ann_cost:,.0f}/yr")

        st.subheader("Implementation Cost & Payback")
        impl_cost_fh = st.number_input(
            "Implementation cost ($)",
            value=50_000.0,
            step=1000.0,
            key="fh_impl_cost",
            help="Typical cost for floating head pressure controls: $30,000–$70,000",
        )

        payback_fh = impl_cost_fh / ann_cost if ann_cost > 0 else float("inf")
        col1, col2 = st.columns(2)
        col1.metric("Simple Payback", f"{payback_fh:.1f} yr" if payback_fh != float("inf") else "N/A")
        col2.metric(
            "COP Improvement",
            f"{r.get('cop_fixed',0):.3f} → {r.get('cop_float_avg', r.get('cop_fixed',0)):.3f}",
        )

        # ASHRAE citation
        citation = r.get(
            "offsets_citation",
            (
                "Air-cooled offset: ASHRAE 90.1-2022 §6.5.1.1 (design ≤ ambient+30°F; reset target: ambient+15°F). "
                "Water-cooled/evaporative offset: ASHRAE Handbook of Fundamentals 2021, Ch. 39 "
                "(cooling tower approach = 7–10°F above wet-bulb; condensing = wet-bulb + 10°F)."
            ),
        )
        st.caption(f"**Offset Reference:** {citation}")

        st.divider()
        if st.button("💾 Save this AR to Report", type="primary", key="fh_save"):
            ar_entry = {
                "arc_code": "2.2621",
                "ar_number": st.session_state.get("fh_ar_num", "AR-1"),
                "title": "Modify Refrigeration System to Operate at Lower (Floating) Head Pressure",
                "resources": [
                    {"type": "Electricity", "savings": ann_kwh, "unit": "kWh"},
                ],
                "total_cost_savings": ann_cost,
                "implementation_cost": impl_cost_fh,
                "payback": payback_fh,
                "observation": st.session_state.get("fh_obs", ""),
                "recommendation": st.session_state.get("fh_rec", ""),
                "tech_description": st.session_state.get("fh_tech", ""),
                "calculation_details": {
                    k: v
                    for k, v in r.items()
                    if k not in ("hourly_df", "bin_df")
                },
            }
            ar_list = st.session_state.get("ar_list", [])
            ar_num_val = ar_entry["ar_number"]
            ar_list = [
                a for a in ar_list
                if not (a.get("arc_code") == "2.2621" and a.get("ar_number") == ar_num_val)
            ]
            ar_list.append(ar_entry)
            st.session_state["ar_list"] = ar_list
            st.success(f"✅ {ar_num_val} saved to report. Total ARs: {len(ar_list)}")
