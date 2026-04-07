"""
ARC 2.2625 — Raise Chilled Water / Supply Air Temperature Setpoint
Models an AHU that draws outside air, cools it to SAT, then reheats to zone temp.
Raising the SAT setpoint reduces both cooling electricity AND reheat gas.
"""
import streamlit as st
import sys, os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from utils.weather import zip_to_latlon, get_hourly_temps
from arcs.arc_2_2625_ahu_reheat import compute_ahu_reheat_savings

NAVY = "#003366"

st.set_page_config(page_title="ARC 2.2625 — Chilled Water / SAT Reset", layout="wide")
init_session()

st.title("AR: Raise Chilled Water / Supply Air Temperature Setpoint (ARC 2.2625)")
st.caption(
    "Models an AHU drawing outdoor air, cooling it to the SAT setpoint, then reheating to zone temperature. "
    "Raising the SAT setpoint reduces both cooling electricity and reheat gas simultaneously."
)

_defs = get_defaults("2.2625")

tab1, tab2, tab3, tab4 = st.tabs(["System Inputs", "Weather", "Calculation", "Results"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — System Inputs
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    with st.expander("📝 Observation & Recommendation", expanded=True):
        c1, c2 = st.columns(2)
        obs = c1.text_area(
            "Observation",
            value=st.session_state.get("chw_obs", _defs["observation"]),
            height=110,
            key="chw_obs",
        )
        rec = c2.text_area(
            "Recommendation",
            value=st.session_state.get("chw_rec", _defs["recommendation"]),
            height=110,
            key="chw_rec",
        )
        tech = c1.text_area(
            "Technology Description",
            value=st.session_state.get("chw_tech", _defs["tech_description"]),
            height=110,
            key="chw_tech",
        )

    ar_num = st.text_input(
        "AR Number",
        value=st.session_state.get("chw_ar_num", "AR-1"),
        key="chw_ar_num",
    )

    st.subheader("AHU / Ventilation System Parameters")

    col1, col2, col3 = st.columns(3)
    sat_existing = col1.number_input(
        "Existing SAT setpoint (°F)",
        value=55.0,
        step=0.5,
        format="%.1f",
        key="chw_sat_existing",
        help="Current supply air temperature setpoint",
    )
    sat_proposed = col2.number_input(
        "Proposed SAT setpoint (°F)",
        value=56.0,
        step=0.5,
        format="%.1f",
        key="chw_sat_proposed",
        help="Proposed (raised) supply air temperature setpoint",
    )
    reheat_temp = col3.number_input(
        "Zone / reheat temperature (°F)",
        value=70.0,
        step=0.5,
        format="%.1f",
        key="chw_reheat_temp",
        help="Final zone temperature after reheat coil",
    )

    if sat_proposed <= sat_existing:
        st.warning("⚠️ Proposed SAT must be higher than existing SAT to show savings.")

    col1, col2, col3, col4 = st.columns(4)
    floor_area = col1.number_input(
        "Floor area (ft²)",
        value=100_000.0,
        step=1000.0,
        format="%.0f",
        key="chw_floor_area",
    )
    ceil_height = col2.number_input(
        "Ceiling height (ft)",
        value=10.0,
        step=0.5,
        format="%.1f",
        key="chw_ceil_height",
    )
    ach = col3.number_input(
        "Air changes per hour",
        value=2.0,
        step=0.1,
        format="%.2f",
        key="chw_ach",
    )
    oaf = col4.number_input(
        "Outside air fraction (0–1)",
        value=0.15,
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        format="%.2f",
        key="chw_oaf",
        help="Fraction of supply airflow that is outdoor air",
    )

    col1, col2 = st.columns(2)
    boiler_eff_pct = col1.number_input(
        "Boiler efficiency (%)",
        value=85.0,
        min_value=50.0,
        max_value=99.0,
        step=1.0,
        format="%.1f",
        key="chw_boiler_eff",
        help="Combustion efficiency of the reheat boiler",
    )
    boiler_eff = boiler_eff_pct / 100.0
    chiller_cop = col2.number_input(
        "Chiller COP",
        value=3.5,
        min_value=1.0,
        max_value=8.0,
        step=0.1,
        format="%.2f",
        key="chw_cop",
        help="Chiller coefficient of performance (cooling kW out / compressor kW in)",
    )

    st.subheader("Facility Area Scaling")
    col1, col2, col3 = st.columns(3)
    total_area = col1.number_input(
        "Total facility area (ft²)",
        value=float(floor_area),
        min_value=1.0,
        step=1000.0,
        format="%.0f",
        key="chw_total_area",
    )
    assessed_area = col2.number_input(
        "Assessed / served area (ft²)",
        value=float(floor_area),
        min_value=1.0,
        step=1000.0,
        format="%.0f",
        key="chw_assessed_area",
    )
    area_fraction = assessed_area / total_area if total_area > 0 else 1.0
    col3.metric("Area Fraction", f"{area_fraction:.3f}", help="assessed_area / total_area — applied to final savings")

    st.subheader("Utility Rates")
    rates = get_utility_rates()
    col1, col2 = st.columns(2)
    gas_rate = col1.number_input(
        "Natural gas rate ($/MMBtu)",
        value=round(rates["gas_rate"], 4) if rates["gas_rate"] > 0 else 8.50,
        step=0.10,
        format="%.4f",
        key="chw_gas_rate",
        help="Auto-filled from Utility Billing page; edit if needed",
    )
    elec_rate = col2.number_input(
        "Electricity rate ($/kWh)",
        value=round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.10,
        step=0.001,
        format="%.4f",
        key="chw_elec_rate",
        help="Auto-filled from Utility Billing page; edit if needed",
    )

    # Live airflow preview
    vol_cft = floor_area * ceil_height
    airflow_cfm = vol_cft * ach / 60.0
    oa_cfm = airflow_cfm * oaf
    st.info(
        f"**Airflow preview:** "
        f"Total volume = {vol_cft:,.0f} ft³ | "
        f"Supply airflow = {airflow_cfm:,.0f} CFM | "
        f"OA airflow = {oa_cfm:,.0f} CFM ({oaf*100:.0f}%)"
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Weather
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Hourly Weather Data")
    st.markdown(
        "Fetch one year of hourly outdoor air temperatures from "
        "[Open-Meteo](https://open-meteo.com/) (free, no API key required)."
    )

    zip_code = st.text_input("ZIP code", value="70501", key="chw_zip")

    end_dt = datetime.today() - timedelta(days=7)
    start_dt = end_dt - timedelta(days=365)

    if st.button("🌡️ Fetch Hourly Weather", key="chw_fetch_wx"):
        with st.spinner("Resolving ZIP code and fetching weather data…"):
            try:
                lat, lon, city = zip_to_latlon(zip_code)
                df_wx = get_hourly_temps(
                    lat, lon,
                    start_dt.strftime("%Y-%m-%d"),
                    end_dt.strftime("%Y-%m-%d"),
                )
                st.session_state["chw_hourly_weather"] = df_wx
                st.session_state["chw_city"] = city
                st.session_state["chw_lat"] = lat
                st.session_state["chw_lon"] = lon
                st.success(f"✅ Fetched {len(df_wx):,} hourly records for **{city}** (lat {lat:.3f}, lon {lon:.3f})")
            except Exception as e:
                st.error(f"Weather fetch failed: {e}")

    if "chw_hourly_weather" in st.session_state:
        df_wx = st.session_state["chw_hourly_weather"]
        city = st.session_state.get("chw_city", zip_code)
        st.caption(f"Location: **{city}** | {len(df_wx):,} hours | "
                   f"Avg OAT: {df_wx['temp_f'].mean():.1f}°F | "
                   f"Min: {df_wx['temp_f'].min():.1f}°F | "
                   f"Max: {df_wx['temp_f'].max():.1f}°F")

        # Hourly temperature line chart
        sample = df_wx.iloc[::6].copy()  # Plot every 6th hour for speed
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sample["datetime"],
            y=sample["temp_f"],
            mode="lines",
            line=dict(color=NAVY, width=1),
            name="OAT (°F)",
        ))
        fig.add_hline(y=sat_existing, line_dash="dash", line_color="red",
                      annotation_text=f"SAT existing {sat_existing}°F")
        fig.add_hline(y=sat_proposed, line_dash="dash", line_color="green",
                      annotation_text=f"SAT proposed {sat_proposed}°F")
        fig.update_layout(
            title=f"Hourly Outdoor Air Temperature — {city}",
            xaxis_title="Date",
            yaxis_title="Temperature (°F)",
            height=380,
            margin=dict(t=40, b=40),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Temperature histogram
        fig2 = px.histogram(
            df_wx, x="temp_f", nbins=40,
            title="OAT Frequency Distribution",
            labels={"temp_f": "Outdoor Air Temperature (°F)"},
            color_discrete_sequence=[NAVY],
        )
        fig2.update_layout(height=280, margin=dict(t=40, b=40))
        st.plotly_chart(fig2, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Calculation
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Calculation Details")

    # Show airflow math
    vol = floor_area * ceil_height
    af_cfh = vol * ach
    af_cfm = af_cfh / 60.0
    mass_lb_hr = af_cfh * 0.075
    oa_mass = mass_lb_hr * oaf

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Building Volume", f"{vol:,.0f} ft³")
    col2.metric("Total Airflow", f"{af_cfm:,.0f} CFM")
    col3.metric("OA Mass Flow", f"{oa_mass:,.0f} lb/hr")
    col4.metric("ΔSAT", f"{sat_proposed - sat_existing:.1f}°F")

    st.markdown(
        f"""
        **Methodology:**
        - OA mass flow = {oa_mass:,.0f} lb/hr  
        - Reheat savings/hr = ṁ_OA × Cₚ × ΔSAT / (η_boiler × 1,000,000 BTU/MMBtu)  
        - Cooling savings/hr = ṁ_OA × Cₚ × ΔSAT / (COP_chiller × 3,412 BTU/kWh) [when OAT > SAT]  
        - Area fraction applied: {area_fraction:.3f}
        """
    )

    if "chw_hourly_weather" not in st.session_state:
        st.warning("⚠️ Fetch weather data in the **Weather** tab first.")
    else:
        if st.button("▶ Run Hourly Savings Calculation", type="primary", key="chw_run"):
            df_wx = st.session_state["chw_hourly_weather"]
            with st.spinner("Running hourly simulation…"):
                try:
                    result = compute_ahu_reheat_savings(
                        df_hourly=df_wx,
                        sat_existing_f=sat_existing,
                        sat_proposed_f=sat_proposed,
                        reheat_temp_f=reheat_temp,
                        floor_area_ft2=floor_area,
                        ceiling_height_ft=ceil_height,
                        ach=ach,
                        outside_air_fraction=oaf,
                        boiler_efficiency=boiler_eff,
                        chiller_cop=chiller_cop,
                        gas_rate=gas_rate,
                        elec_rate=elec_rate,
                        facility_area_fraction=area_fraction,
                    )
                    st.session_state["chw_result"] = result
                    st.success("✅ Hourly simulation complete.")
                except Exception as e:
                    st.error(f"Calculation error: {e}")

    if "chw_result" in st.session_state:
        r = st.session_state["chw_result"]
        monthly = r.get("monthly_summary")

        if monthly is not None and not monthly.empty:
            st.subheader("Monthly Summary")
            disp = monthly[["month_name", "gas_mmbtu", "elec_kwh", "gas_cost", "elec_cost", "total_cost"]].copy()
            disp.columns = ["Month", "Gas Saved (MMBtu)", "Elec Saved (kWh)", "Gas $ Saved", "Elec $ Saved", "Total $ Saved"]
            st.dataframe(
                disp.style.format({
                    "Gas Saved (MMBtu)": "{:.2f}",
                    "Elec Saved (kWh)": "{:,.0f}",
                    "Gas $ Saved": "${:,.0f}",
                    "Elec $ Saved": "${:,.0f}",
                    "Total $ Saved": "${:,.0f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

            # Stacked bar: gas + elec savings by month
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly["month_name"],
                y=monthly["gas_cost"],
                name="Gas Cost Saved ($)",
                marker_color=NAVY,
            ))
            fig.add_trace(go.Bar(
                x=monthly["month_name"],
                y=monthly["elec_cost"],
                name="Elec Cost Saved ($)",
                marker_color="#4A90D9",
            ))
            fig.update_layout(
                barmode="stack",
                title="Monthly Cost Savings — Gas + Electricity",
                xaxis_title="Month",
                yaxis_title="Cost Saved ($)",
                height=360,
                margin=dict(t=40, b=40),
                plot_bgcolor="white",
                paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Results
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Annual Savings Summary")

    if "chw_result" not in st.session_state:
        st.info("Run the calculation in the **Calculation** tab to see results here.")
    else:
        r = st.session_state["chw_result"]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Gas Saved", f"{r['ann_gas_mmbtu_savings']:.1f} MMBtu/yr")
        c2.metric("Elec Saved", f"{r['ann_elec_kwh_savings']:,.0f} kWh/yr")
        c3.metric("Gas Cost Saved", f"${r['ann_gas_cost_savings']:,.0f}/yr")
        c4.metric("Elec Cost Saved", f"${r['ann_elec_cost_savings']:,.0f}/yr")
        c5.metric("Total Cost Saved", f"${r['ann_total_cost_savings']:,.0f}/yr")

        st.markdown(
            f"""
            **Implementation Cost:** $0 (setpoint change via BAS — no capital required)  
            **Simple Payback:** Instantaneous  
            **ΔSAT:** {r['delta_sat_f']:.1f}°F ({r['sat_existing_f']}°F → {r['sat_proposed_f']}°F)  
            **Area Fraction Applied:** {r['facility_area_fraction']:.3f}
            """
        )

        st.divider()
        if st.button("💾 Save this AR to Report", type="primary", key="chw_save"):
            ar_entry = {
                "arc_code": "2.2625",
                "ar_number": st.session_state.get("chw_ar_num", "AR-1"),
                "title": "Raise Chilled Water / Supply Air Temperature Setpoint",
                "resources": [
                    {"type": "Natural Gas", "savings": r["ann_gas_mmbtu_savings"], "unit": "MMBtu"},
                    {"type": "Electricity", "savings": r["ann_elec_kwh_savings"], "unit": "kWh"},
                ],
                "total_cost_savings": r["ann_total_cost_savings"],
                "implementation_cost": 0,
                "payback": 0,
                "observation": st.session_state.get("chw_obs", ""),
                "recommendation": st.session_state.get("chw_rec", ""),
                "tech_description": st.session_state.get("chw_tech", ""),
                "calculation_details": {
                    k: v for k, v in r.items() if k not in ("hourly_df", "monthly_summary")
                },
            }
            ar_list = st.session_state.get("ar_list", [])
            ar_num_val = ar_entry["ar_number"]
            ar_list = [
                a for a in ar_list
                if not (a.get("arc_code") == "2.2625" and a.get("ar_number") == ar_num_val)
            ]
            ar_list.append(ar_entry)
            st.session_state["ar_list"] = ar_list
            st.success(f"✅ {ar_num_val} saved to report. Total ARs: {len(ar_list)}")
