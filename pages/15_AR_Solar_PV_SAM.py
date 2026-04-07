"""
ARC 2.9114 — Rooftop Solar PV Installation
Uses NREL PySAM (PVWatts v8) when available; simplified fallback otherwise.
"""
import streamlit as st
import sys, os
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from arcs.arc_2_9114_solar_pysam import (
    run_pvwatts, run_pvwatts_simplified, solar_financial,
    PYSAM_AVAILABLE, CITY_PSH, LAFAYETTE_MONTHLY_PSH
)

st.set_page_config(page_title="ARC 2.9114 — Solar PV (PVWatts)", layout="wide")
init_session()

defs = get_defaults("2.9114")

st.title("AR: Rooftop Solar PV Installation (ARC 2.9114)")
st.caption("Energy production estimated using NREL PVWatts® model. Includes 25-year financial analysis with ITC.")

# PySAM status banner
if PYSAM_AVAILABLE:
    st.success("✅ PySAM installed — full PVWatts v8 simulation available.")
else:
    st.warning(
        "⚠️ PySAM not installed. Using simplified calculation. "
        "For PVWatts v8 accuracy, run: `pip install nrel-pysam` and restart Streamlit."
    )

# ── Observation & Recommendation ─────────────────────────────────────────────
with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value="AR-1", key="pv_ar_num")
    obs  = c1.text_area("Observation",
                        value=st.session_state.get("pv_obs", defs["observation"]),
                        height=120, key="pv_obs")
    rec  = c2.text_area("Recommendation",
                        value=st.session_state.get("pv_rec", defs["recommendation"]),
                        height=120, key="pv_rec")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("pv_tech", defs["tech_description"]),
                        height=120, key="pv_tech")

# ── Location ──────────────────────────────────────────────────────────────────
st.subheader("Site Location")
col1, col2, col3 = st.columns(3)

city_list = list(CITY_PSH.keys())
city_sel  = col1.selectbox("Select city (or enter custom lat/lon below)",
                            ["Custom / Enter coordinates"] + city_list,
                            key="pv_city")

if city_sel != "Custom / Enter coordinates":
    default_lat = {"Lafayette, LA": 30.22, "New Orleans, LA": 29.95, "Baton Rouge, LA": 30.45,
                   "Houston, TX": 29.76, "Dallas, TX": 32.78, "Atlanta, GA": 33.75,
                   "Miami, FL": 25.77, "Phoenix, AZ": 33.45, "Los Angeles, CA": 34.05,
                   "Denver, CO": 39.74, "Chicago, IL": 41.85, "New York, NY": 40.71,
                   "Seattle, WA": 47.61}.get(city_sel, 30.22)
    default_lon = {"Lafayette, LA": -92.02, "New Orleans, LA": -90.07, "Baton Rouge, LA": -91.19,
                   "Houston, TX": -95.37, "Dallas, TX": -96.80, "Atlanta, GA": -84.39,
                   "Miami, FL": -80.19, "Phoenix, AZ": -112.07, "Los Angeles, CA": -118.24,
                   "Denver, CO": -104.98, "Chicago, IL": -87.65, "New York, NY": -74.01,
                   "Seattle, WA": -122.33}.get(city_sel, -92.02)
    default_psh = CITY_PSH.get(city_sel, 4.83)
else:
    default_lat, default_lon, default_psh = 30.22, -92.02, 4.83

lat = col2.number_input("Latitude (°N)", value=default_lat, step=0.01, format="%.4f", key="pv_lat")
lon = col3.number_input("Longitude (°E, negative for US)", value=default_lon, step=0.01,
                         format="%.4f", key="pv_lon")

# ── System Design ─────────────────────────────────────────────────────────────
st.subheader("PV System Design")
col1, col2, col3, col4 = st.columns(4)
system_kw   = col1.number_input("System DC capacity (kW)", value=100.0, min_value=1.0,
                                  step=5.0, key="pv_kw",
                                  help="Total nameplate DC capacity of all panels")
tilt        = col2.number_input("Tilt angle (°)", value=round(abs(lat)), min_value=0,
                                  max_value=60, step=1, key="pv_tilt",
                                  help="Optimal tilt ≈ site latitude. Roof pitch = arctan(rise/run).")
azimuth     = col3.number_input("Azimuth (°, 180=south)", value=180, min_value=0,
                                  max_value=360, step=5, key="pv_azimuth")
losses      = col4.number_input("System losses (%)", value=14.0, min_value=5.0,
                                  max_value=30.0, step=0.5, key="pv_losses",
                                  help="PVWatts default 14% covers: soiling (2%), wiring (2%), "
                                       "connections (0.5%), light-induced degradation (1.5%), "
                                       "nameplate rating (1%), mismatch (2%), availability (3%).")

col1, col2, col3 = st.columns(3)
dc_ac_ratio = col1.number_input("DC/AC ratio (inverter loading)", value=1.2, min_value=1.0,
                                  max_value=1.5, step=0.05, key="pv_dcac",
                                  help="Typical: 1.1–1.3. Higher ratio = more clipping but lower cost.")
array_type_label = col2.selectbox("Array type",
                                    ["Fixed — Open Rack", "Fixed — Roof Mount",
                                     "1-Axis Tracking", "2-Axis Tracking"],
                                    index=1, key="pv_array_type")
array_type_map  = {"Fixed — Open Rack": 0, "Fixed — Roof Mount": 1,
                    "1-Axis Tracking": 2, "2-Axis Tracking": 4}
array_type      = array_type_map[array_type_label]

module_type_label = col3.selectbox("Module type",
                                    ["Standard (crystalline Si)", "Premium (high-eff Si)",
                                     "Thin Film (CdTe/CIGS)"],
                                    index=0, key="pv_module_type")
module_type_map = {"Standard (crystalline Si)": 0, "Premium (high-eff Si)": 1, "Thin Film (CdTe/CIGS)": 2}
module_type = module_type_map[module_type_label]

# ── NREL API Key (for full PySAM) ─────────────────────────────────────────────
if PYSAM_AVAILABLE:
    with st.expander("🔑 NREL API Key (required for PVWatts weather download)"):
        st.markdown(
            "A free NREL API key is needed to download TMY weather data from NSRDB. "
            "Get yours at: [developer.nrel.gov/signup](https://developer.nrel.gov/signup/)"
        )
        nrel_key = st.text_input("NREL API Key", type="password",
                                  value=st.session_state.get("pv_nrel_key", ""),
                                  key="pv_nrel_key")
        weather_file_path = st.text_input(
            "Or upload SAM weather file path (optional)",
            value=st.session_state.get("pv_weather_file", ""),
            key="pv_weather_file",
            help="Path to a SAM-format weather CSV if you already have one downloaded."
        )
else:
    nrel_key = ""
    weather_file_path = ""
    st.subheader("Annual Peak Sun Hours (simplified method)")
    psh_manual = st.number_input(
        f"Annual average PSH (kWh/m²/day) — default for {city_sel}",
        value=float(CITY_PSH.get(city_sel, default_psh)),
        min_value=2.0, max_value=8.0, step=0.01, key="pv_psh",
        help="From NREL PVWatts for your city. Lafayette, LA = 4.83."
    )

# ── Financial Parameters ─────────────────────────────────────────────────────
st.subheader("Financial Parameters")
rates = get_utility_rates()
col1, col2, col3, col4 = st.columns(4)
elec_rate      = col1.number_input("Electricity rate ($/kWh)",
                                    value=round(rates["elec_rate"], 4) if rates["elec_rate"] > 0 else 0.095,
                                    step=0.001, format="%.4f", key="pv_elec_rate")
cost_per_kw    = col2.number_input("Installed cost ($/kW DC)", value=2500.0, step=100.0,
                                    key="pv_cost_kw",
                                    help="Typical commercial: $1,800–$3,000/kW DC (2024)")
itc_pct        = col3.number_input("Federal ITC (%)", value=30.0, min_value=0.0, max_value=50.0,
                                    step=1.0, key="pv_itc",
                                    help="30% ITC through 2032 per Inflation Reduction Act")
state_incentive= col4.number_input("State/utility incentive ($)", value=0.0, step=500.0,
                                    key="pv_state_inc")
col1b, col2b = st.columns(2)
om_per_kw      = col1b.number_input("Annual O&M cost ($/kW/yr)", value=15.0, step=1.0,
                                     key="pv_om", help="Typical: $10–20/kW/yr for commercial rooftop")
degradation    = col2b.number_input("Annual degradation (%/yr)", value=0.5, step=0.1,
                                     key="pv_degrad", help="Industry standard: 0.5%/yr")

# ── Annual kWh estimate (for facility comparison) ─────────────────────────────
st.subheader("Facility Electricity Consumption")
col_ann, col_pct = st.columns(2)
ann_facility_kwh = col_ann.number_input(
    "Annual facility electricity use (kWh)",
    value=int(sum(r.get("kwh", 0) for r in st.session_state.get("elec_rows", []))),
    step=1000, key="pv_facility_kwh",
    help="Auto-filled from Utility Billing page if available."
)

# ── Run Simulation ────────────────────────────────────────────────────────────
if st.button("Run PVWatts Simulation", type="primary", key="pv_run"):
    with st.spinner("Simulating…"):
        try:
            if PYSAM_AVAILABLE:
                wf = weather_file_path.strip() if weather_file_path.strip() else None
                nk = nrel_key.strip() if nrel_key.strip() else None
                pv_result = run_pvwatts(
                    system_capacity_kw=system_kw,
                    lat=lat, lon=lon,
                    tilt=tilt, azimuth=azimuth,
                    losses=losses,
                    dc_ac_ratio=dc_ac_ratio,
                    array_type=array_type,
                    module_type=module_type,
                    weather_file=wf,
                    nrel_api_key=nk,
                )
            else:
                pv_result = run_pvwatts_simplified(
                    system_capacity_kw=system_kw,
                    annual_psh=st.session_state.get("pv_psh", default_psh),
                    losses_pct=losses,
                    dc_ac_ratio=dc_ac_ratio,
                )
            fin_result = solar_financial(
                annual_kwh=pv_result["annual_kwh"],
                system_capacity_kw=system_kw,
                elec_rate=elec_rate,
                installed_cost_per_kw=cost_per_kw,
                federal_itc_pct=itc_pct,
                state_incentive=state_incentive,
                om_cost_per_kw_yr=om_per_kw,
                degradation_pct=degradation,
            )
            st.session_state["pv_result"] = pv_result
            st.session_state["pv_fin"] = fin_result
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Simulation error: {e}")

# ── Display Results ───────────────────────────────────────────────────────────
if "pv_result" in st.session_state and "pv_fin" in st.session_state:
    pv  = st.session_state["pv_result"]
    fin = st.session_state["pv_fin"]

    st.subheader("Simulation Results")
    pct_offset = pv["annual_kwh"] / ann_facility_kwh * 100 if ann_facility_kwh > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Annual Production", f"{pv['annual_kwh']:,.0f} kWh")
    c2.metric("Capacity Factor", f"{pv['capacity_factor_pct']:.1f}%")
    c3.metric("kWh per kW DC", f"{pv['kwh_per_kw']:.0f}")
    c4.metric("% of Facility Load", f"{pct_offset:.1f}%")
    c5.metric("Method", pv["method"])

    st.subheader("Financial Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Installed Cost", f"${fin['total_installed_cost']:,.0f}")
    c2.metric(f"Federal ITC ({itc_pct:.0f}%)", f"−${fin['itc_value']:,.0f}")
    c3.metric("Net Cost After ITC", f"${fin['net_cost_after_itc']:,.0f}")
    c4.metric("Year 1 Net Savings", f"${fin['ann_net_savings_yr1']:,.0f}/yr")

    c1b, c2b, c3b = st.columns(3)
    pb = fin["simple_payback_years"]
    c1b.metric("Simple Payback", f"{pb:.1f} yr" if pb != float("inf") else "N/A")
    c2b.metric("25-Year Cumulative Savings", f"${fin['cumulative_savings_25yr']:,.0f}")
    c3b.metric("Annual O&M Cost", f"${fin['ann_om']:,.0f}/yr")

    # Monthly production bar chart (if available from PySAM)
    if "monthly_kwh" in pv:
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        df_monthly = pd.DataFrame({"Month": months, "kWh": pv["monthly_kwh"]})
        fig_bar = px.bar(df_monthly, x="Month", y="kWh",
                         title="Estimated Monthly AC Production",
                         color="kWh", color_continuous_scale="Oranges",
                         text="kWh")
        fig_bar.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig_bar.update_layout(height=380, showlegend=False,
                               yaxis_title="AC Energy (kWh)", coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        # Generate approximate monthly from Lafayette defaults
        monthly_psh = LAFAYETTE_MONTHLY_PSH
        monthly_days = [31,28,31,30,31,30,31,31,30,31,30,31]
        derate = 1.0 - losses / 100.0
        approx_monthly = [system_kw * monthly_psh[i] * monthly_days[i] * derate
                          for i in range(12)]
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        df_monthly = pd.DataFrame({"Month": months, "kWh": approx_monthly})
        fig_bar = px.bar(df_monthly, x="Month", y="kWh",
                         title="Estimated Monthly AC Production (Approximate, Lafayette PSH)",
                         color="kWh", color_continuous_scale="Oranges",
                         text="kWh")
        fig_bar.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig_bar.update_layout(height=380, showlegend=False,
                               yaxis_title="AC Energy (kWh)", coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    # Cumulative cash flow chart
    cumulative = []
    running = -fin["net_cost_after_itc"]
    kwh_yr = pv["annual_kwh"]
    for yr in range(1, 26):
        kwh_yr_d = kwh_yr * ((1 - degradation / 100) ** (yr - 1))
        net = kwh_yr_d * elec_rate - fin["ann_om"]
        running += net
        cumulative.append({"Year": yr, "Cumulative Net Cash Flow ($)": running})

    df_cf = pd.DataFrame(cumulative)
    fig_cf = go.Figure()
    fig_cf.add_trace(go.Scatter(
        x=df_cf["Year"], y=df_cf["Cumulative Net Cash Flow ($)"],
        mode="lines+markers", fill="tozeroy",
        fillcolor="rgba(0,150,100,0.15)", line=dict(color="green", width=2),
        name="Cumulative Cash Flow"
    ))
    fig_cf.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break-even")
    fig_cf.update_layout(
        title="25-Year Cumulative Net Cash Flow (after ITC)",
        xaxis_title="Year", yaxis_title="Cumulative Cash Flow ($)",
        height=350
    )
    st.plotly_chart(fig_cf, use_container_width=True)

    with st.expander("Calculation Detail"):
        st.markdown(f"""
**PV Simulation ({pv['method']}):**
- System: **{system_kw:.1f} kW DC** | Tilt: {tilt}° | Azimuth: {azimuth}° | DC/AC: {dc_ac_ratio}
- Losses: {losses}% | Annual solar resource: {pv.get('solrad_annual', default_psh):.2f} kWh/m²/day
- AC annual production: **{pv['annual_kwh']:,.0f} kWh/yr** ({pv['kwh_per_kw']:.0f} kWh/kW)
- Capacity factor: **{pv['capacity_factor_pct']:.1f}%**

**Financial Model:**
- Installed cost: {system_kw:.1f} kW × ${cost_per_kw:,.0f}/kW = **${fin['total_installed_cost']:,.0f}**
- ITC ({itc_pct:.0f}%): −**${fin['itc_value']:,.0f}**
- State/utility incentive: −**${state_incentive:,.0f}**
- Net cost after incentives: **${fin['net_cost_after_itc']:,.0f}**
- Year 1 energy savings: {pv['annual_kwh']:,.0f} kWh × ${elec_rate:.4f}/kWh = **${fin['ann_savings_yr1']:,.0f}**
- Annual O&M: −**${fin['ann_om']:,.0f}**
- Year 1 net savings: **${fin['ann_net_savings_yr1']:,.0f}**
- Simple payback: **{pb:.1f} yr**
- 25-year cumulative savings: **${fin['cumulative_savings_25yr']:,.0f}**
        """)

    st.divider()
    if st.button("💾 Save this AR to Report", type="primary", key="pv_save"):
        pb_val = fin["simple_payback_years"]
        ar_entry = {
            "arc_code": "2.9114",
            "ar_number": ar_num,
            "title": f"Rooftop Solar PV System ({system_kw:.0f} kW)",
            "resources": [{"type": "Electricity", "savings": pv["annual_kwh"], "unit": "kWh"}],
            "total_cost_savings": fin["ann_net_savings_yr1"],
            "implementation_cost": fin["net_cost_after_itc"],
            "payback": pb_val if pb_val != float("inf") else 99.0,
            "observation": st.session_state.get("pv_obs", ""),
            "recommendation": st.session_state.get("pv_rec", ""),
            "tech_description": st.session_state.get("pv_tech", ""),
            "calculation_details": {
                **pv,
                **{f"fin_{k}": v for k, v in fin.items()},
                "system_kw": system_kw,
                "elec_rate": elec_rate,
                "itc_pct": itc_pct,
                "pct_facility_offset": pct_offset,
            },
        }
        ar_list = [a for a in st.session_state.get("ar_list", [])
                   if not (a.get("arc_code") == "2.9114" and a.get("ar_number") == ar_num)]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ Saved. Total ARs: {len(ar_list)}")
