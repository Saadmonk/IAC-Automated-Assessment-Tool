"""
ARC 2.7221 — Lower Temperature During Winter and Vice-Versa
Streamlit UI: upload smart meter CSV → ASHRAE GL14 regression → setback savings
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from arcs.arc_2_7221_thermostat import (
    fit_all_models, compute_thermostat_savings, best_model_label,
    model_2P, model_3PC, model_3PH, model_4P, model_5P
)

st.set_page_config(page_title="ARC 2.7221 — Thermostat Setback", layout="wide")
init_session()

st.title("AR: Thermostat Setback (ARC 2.7221)")
st.caption("Lower cooling setpoint in summer, raise heating setpoint in winter using ASHRAE Guideline 14 regression on smart meter data.")

# ── Step 1: Narrative inputs ────────────────────────────────────────────────
with st.expander("📝 Observation & Recommendation", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        ar_num = st.text_input("AR Number", value=st.session_state.get("therm_ar_num", "AR-1"), key="therm_ar_num")
        observation = st.text_area(
            "Observation",
            value=st.session_state.get("therm_obs", ""),
            height=120,
            key="therm_obs",
            placeholder="Describe current thermostat settings, smart thermostat type, current schedule..."
        )
    with col2:
        recommendation = st.text_area(
            "Recommendation",
            value=st.session_state.get("therm_rec", ""),
            height=120,
            key="therm_rec",
            placeholder="Recommend raising/lowering setpoints, installing programmable thermostats..."
        )
        tech_description = st.text_area(
            "Technology Description",
            value=st.session_state.get("therm_tech", "A thermostat setback strategy adjusts HVAC setpoints during unoccupied hours to reduce conditioning loads. ASHRAE Guideline 14 change-point regression models are used to establish the relationship between outdoor air temperature and daily energy consumption, from which setpoint adjustment savings are estimated."),
            height=120,
            key="therm_tech",
        )

# ── Step 2: Smart Meter Data Upload ────────────────────────────────────────
st.subheader("Smart Meter Data")
st.markdown("Upload a CSV with **daily** outdoor temperature and energy consumption. Required columns (exact names or mapped below):")

uploaded = st.file_uploader("Upload CSV", type=["csv"], key="sm_upload")

col1, col2 = st.columns(2)
temp_col_opt   = col1.text_input("Temperature column name", value="temp_f", key="sm_temp_col")
energy_col_opt = col2.text_input("Energy column name (kWh/day)", value="kwh", key="sm_energy_col")

df_meter = None

if uploaded is not None:
    try:
        df_meter = pd.read_csv(uploaded)
        # Auto-detect columns if exact names not found
        cols_lower = {c.lower(): c for c in df_meter.columns}
        if temp_col_opt not in df_meter.columns:
            for guess in ["temp_f", "temp", "oat", "outdoor_temp", "temperature"]:
                if guess in cols_lower:
                    temp_col_opt = cols_lower[guess]
                    st.info(f"Auto-detected temperature column: **{temp_col_opt}**")
                    break
        if energy_col_opt not in df_meter.columns:
            for guess in ["kwh", "energy", "consumption", "daily_kwh", "elec"]:
                if guess in cols_lower:
                    energy_col_opt = cols_lower[guess]
                    st.info(f"Auto-detected energy column: **{energy_col_opt}**")
                    break

        if temp_col_opt in df_meter.columns and energy_col_opt in df_meter.columns:
            df_meter = df_meter[[temp_col_opt, energy_col_opt]].dropna()
            df_meter[temp_col_opt]   = pd.to_numeric(df_meter[temp_col_opt], errors="coerce")
            df_meter[energy_col_opt] = pd.to_numeric(df_meter[energy_col_opt], errors="coerce")
            df_meter = df_meter.dropna()
            st.session_state["smart_meter_df"] = df_meter
            st.success(f"Loaded {len(df_meter)} data points.")
        else:
            st.error(f"Columns '{temp_col_opt}' or '{energy_col_opt}' not found. Available: {list(df_meter.columns)}")
            df_meter = None
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        df_meter = None
elif st.session_state.get("smart_meter_df") is not None:
    df_meter = st.session_state["smart_meter_df"]
    st.info(f"Using previously loaded data ({len(df_meter)} rows).")

# ── Step 3: Run Regression ─────────────────────────────────────────────────
results = None
best_key = None

if df_meter is not None and len(df_meter) >= 10:
    if st.button("Run ASHRAE GL14 Regression", type="primary"):
        with st.spinner("Fitting 5 change-point models…"):
            results_computed = fit_all_models(df_meter, temp_col_opt, energy_col_opt)
            st.session_state["therm_results"] = results_computed
            st.session_state["therm_temp_col"] = temp_col_opt
            st.session_state["therm_energy_col"] = energy_col_opt

    if "therm_results" in st.session_state and st.session_state["therm_results"]:
        results = st.session_state["therm_results"]
        best_key = results.get("best", "2P")

        # ── Results Table ──────────────────────────────────────────────────
        st.subheader("Regression Results")
        model_names = {
            "2P":  "2-Parameter (Constant)",
            "3PC": "3-Parameter Cooling",
            "3PH": "3-Parameter Heating",
            "4P":  "4-Parameter (V-shape)",
            "5P":  "5-Parameter (Full GL14)",
        }
        rows = []
        for k, label in model_names.items():
            r = results.get(k, {})
            if r.get("success"):
                marker = " ⭐" if k == best_key else ""
                rows.append({
                    "Model": label + marker,
                    "R²": f"{r['r2']:.4f}",
                    "CV(RMSE) %": f"{r['cvrmse']:.2f}",
                    "Parameters": str(np.round(r["params"], 4).tolist()),
                })
            else:
                rows.append({"Model": label, "R²": "—", "CV(RMSE) %": "—", "Parameters": r.get("error", "failed")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── Scatter + Fit Plot ─────────────────────────────────────────────
        st.subheader("Regression Fit Plot")
        temp_col_used   = st.session_state.get("therm_temp_col", temp_col_opt)
        energy_col_used = st.session_state.get("therm_energy_col", energy_col_opt)
        T_arr = df_meter[temp_col_used].values.astype(float)
        E_arr = df_meter[energy_col_used].values.astype(float)
        T_plot = np.linspace(T_arr.min(), T_arr.max(), 300)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=T_arr, y=E_arr, mode="markers",
            marker=dict(size=5, color="#4A90D9", opacity=0.6),
            name="Measured Data"
        ))
        model_funcs = {"2P": model_2P, "3PC": model_3PC, "3PH": model_3PH, "4P": model_4P, "5P": model_5P}
        colors = {"2P": "gray", "3PC": "blue", "3PH": "red", "4P": "green", "5P": "purple"}
        for k, func in model_funcs.items():
            r = results.get(k, {})
            if r.get("success"):
                width = 3 if k == best_key else 1
                E_fit = func(T_plot, *r["params"])
                fig.add_trace(go.Scatter(
                    x=T_plot, y=E_fit, mode="lines",
                    line=dict(color=colors[k], width=width),
                    name=f"{model_names[k]} (R²={r['r2']:.3f})"
                ))
        fig.update_layout(
            xaxis_title="Outdoor Air Temperature (°F)",
            yaxis_title="Daily Energy (kWh)",
            legend=dict(orientation="h", y=-0.25),
            height=450
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Model Selection + Setback Parameters ──────────────────────────
        st.subheader("Setback Parameters")
        col1, col2, col3 = st.columns(3)
        model_opts = [k for k in ["2P","3PC","3PH","4P","5P"] if results.get(k, {}).get("success")]
        sel_model = col1.selectbox(
            "Select Model",
            options=model_opts,
            index=model_opts.index(best_key) if best_key in model_opts else 0,
            format_func=lambda k: model_names.get(k, k) + (" ⭐ Best" if k == best_key else ""),
            key="therm_sel_model"
        )
        delta_cooling = col2.number_input("Cooling setpoint increase (°F)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="therm_delta_cool")
        delta_heating = col3.number_input("Heating setpoint decrease (°F)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="therm_delta_heat")

        # ── Calculate Savings ─────────────────────────────────────────────
        rates = get_utility_rates()
        elec_rate = rates.get("elec_rate", 0.10)

        col_r, col_e = st.columns(2)
        elec_rate_in = col_r.number_input(
            "Electricity rate ($/kWh)",
            value=round(elec_rate, 4) if elec_rate > 0 else 0.10,
            step=0.001, format="%.4f", key="therm_elec_rate"
        )
        impl_cost = col_e.number_input("Implementation cost ($)", value=0.0, step=100.0, key="therm_impl_cost")

        if st.button("Calculate Savings", key="therm_calc"):
            sav = compute_thermostat_savings(
                results, sel_model, T_arr, E_arr, delta_cooling, delta_heating
            )
            st.session_state["therm_savings"] = sav
            st.session_state["therm_elec_rate_used"] = elec_rate_in
            st.session_state["therm_impl_cost_used"] = impl_cost

        if "therm_savings" in st.session_state:
            sav = st.session_state["therm_savings"]
            rate_used = st.session_state.get("therm_elec_rate_used", elec_rate_in)
            impl_used  = st.session_state.get("therm_impl_cost_used", impl_cost)

            if sav.get("success"):
                ann_kwh  = abs(sav["ann_savings_kwh"])
                ann_cost = ann_kwh * rate_used
                payback  = impl_used / ann_cost if ann_cost > 0 else float("inf")

                st.subheader("Estimated Savings")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Annual Electricity Savings", f"{ann_kwh:,.0f} kWh")
                c2.metric("Annual Cost Savings", f"${ann_cost:,.0f}")
                c3.metric("Implementation Cost", f"${impl_used:,.0f}")
                c4.metric("Simple Payback", f"{payback:.1f} yr" if payback != float('inf') else "N/A")

                st.markdown("**Model used:** " + model_names.get(sav["model"], sav["model"]))
                st.markdown(f"**R² = {sav['r2']:.4f}** | **CV(RMSE) = {sav['cvrmse']:.2f}%**")

                # ── Calculation narrative (for report) ─────────────────────
                with st.expander("Calculation Narrative (for report)"):
                    params = sav["params"]
                    model_k = sav["model"]
                    narrative = f"An ASHRAE Guideline 14 change-point regression was performed on {len(df_meter)} days of smart meter data. "
                    narrative += f"The best-fit model selected was the **{model_names[model_k]}** (R² = {sav['r2']:.4f}, CV(RMSE) = {sav['cvrmse']:.2f}%). "
                    if model_k == "3PC":
                        b0, b1, Tc = params
                        narrative += f"Parameters: baseline b₀ = {b0:.2f} kWh/day, cooling slope b₁ = {b1:.4f} kWh/day·°F, balance point Tc = {Tc:.1f}°F. "
                        cool_days = int(np.sum(T_arr > Tc))
                        narrative += f"By raising the cooling setpoint by {delta_cooling}°F, the estimated annual savings = {b1:.4f} × {delta_cooling} × {cool_days} days = **{ann_kwh:,.0f} kWh/yr**."
                    elif model_k == "3PH":
                        b0, b1, Th = params
                        narrative += f"Parameters: baseline b₀ = {b0:.2f} kWh/day, heating slope b₁ = {b1:.4f} kWh/day·°F, balance point Th = {Th:.1f}°F. "
                        heat_days = int(np.sum(T_arr < Th))
                        narrative += f"By lowering the heating setpoint by {delta_heating}°F, the estimated annual savings = {b1:.4f} × {delta_heating} × {heat_days} days = **{ann_kwh:,.0f} kWh/yr**."
                    elif model_k == "5P":
                        b0, b1c, b2h, Tc, Th = params
                        narrative += f"Parameters: b₀ = {b0:.2f}, cooling slope b₁ = {b1c:.4f} (Tc = {Tc:.1f}°F), heating slope b₂ = {b2h:.4f} (Th = {Th:.1f}°F). "
                        cool_days = int(np.sum(T_arr > Tc))
                        heat_days = int(np.sum(T_arr < Th))
                        narrative += f"Annual savings = {b1c:.4f}×{delta_cooling}×{cool_days} + {b2h:.4f}×{delta_heating}×{heat_days} = **{ann_kwh:,.0f} kWh/yr**."
                    else:
                        narrative += f"Annual savings estimated at **{ann_kwh:,.0f} kWh/yr**."
                    st.markdown(narrative)
                    st.session_state["therm_narrative"] = narrative

                # ── Save AR ────────────────────────────────────────────────
                st.divider()
                if st.button("💾 Save this AR to Report", type="primary", key="therm_save"):
                    ar_entry = {
                        "arc_code": "2.7221",
                        "ar_number": ar_num,
                        "title": "Thermostat Setback",
                        "resources": [{"type": "Electricity", "savings": ann_kwh, "unit": "kWh"}],
                        "total_cost_savings": ann_cost,
                        "implementation_cost": impl_used,
                        "payback": payback,
                        "observation": st.session_state.get("therm_obs", ""),
                        "recommendation": st.session_state.get("therm_rec", ""),
                        "tech_description": st.session_state.get("therm_tech", ""),
                        "calculation_details": {
                            "model": sel_model,
                            "r2": sav["r2"],
                            "cvrmse": sav["cvrmse"],
                            "params": sav["params"].tolist(),
                            "ann_kwh": ann_kwh,
                            "ann_cost": ann_cost,
                            "elec_rate": rate_used,
                            "delta_cooling": delta_cooling,
                            "delta_heating": delta_heating,
                            "n_days": len(df_meter),
                            "narrative": st.session_state.get("therm_narrative", ""),
                        }
                    }
                    # Replace existing entry for this AR code if present
                    ar_list = st.session_state.get("ar_list", [])
                    ar_list = [a for a in ar_list if a.get("arc_code") != "2.7221" or a.get("ar_number") != ar_num]
                    ar_list.append(ar_entry)
                    st.session_state["ar_list"] = ar_list
                    st.success(f"✅ {ar_num} saved to report. Total ARs: {len(ar_list)}")
            else:
                st.error(f"Savings calculation failed: {sav.get('error')}")
else:
    if df_meter is None:
        st.info("Upload a CSV file above to begin regression analysis.")
    else:
        st.warning("Need at least 10 data points for regression. Current count: " + str(len(df_meter)))

# ── Manual Entry Fallback ──────────────────────────────────────────────────
with st.expander("Manual Entry (if no smart meter data)"):
    st.markdown("If no smart meter CSV is available, enter savings manually:")
    c1, c2, c3 = st.columns(3)
    manual_kwh  = c1.number_input("Annual kWh savings (manual)", min_value=0.0, step=100.0, key="therm_manual_kwh")
    manual_rate = c2.number_input("Electricity rate ($/kWh)", value=0.10, step=0.001, format="%.4f", key="therm_manual_rate")
    manual_impl = c3.number_input("Implementation cost ($)", min_value=0.0, step=100.0, key="therm_manual_impl")
    manual_cost = manual_kwh * manual_rate
    manual_pb   = manual_impl / manual_cost if manual_cost > 0 else float("inf")
    st.markdown(f"**Annual cost savings:** ${manual_cost:,.0f} | **Payback:** {manual_pb:.1f} yr" if manual_cost > 0 else "")
    if st.button("Save Manual AR", key="therm_manual_save"):
        ar_entry = {
            "arc_code": "2.7221",
            "ar_number": ar_num,
            "title": "Thermostat Setback",
            "resources": [{"type": "Electricity", "savings": manual_kwh, "unit": "kWh"}],
            "total_cost_savings": manual_cost,
            "implementation_cost": manual_impl,
            "payback": manual_pb,
            "observation": st.session_state.get("therm_obs", ""),
            "recommendation": st.session_state.get("therm_rec", ""),
            "tech_description": st.session_state.get("therm_tech", ""),
            "calculation_details": {"method": "manual", "ann_kwh": manual_kwh, "ann_cost": manual_cost}
        }
        ar_list = st.session_state.get("ar_list", [])
        ar_list = [a for a in ar_list if a.get("arc_code") != "2.7221" or a.get("ar_number") != ar_num]
        ar_list.append(ar_entry)
        st.session_state["ar_list"] = ar_list
        st.success(f"✅ Manual AR saved. Total ARs: {len(ar_list)}")
