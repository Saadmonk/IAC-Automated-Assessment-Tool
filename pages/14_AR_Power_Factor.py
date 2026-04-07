"""
ARC — Power Factor Correction
MEASUR-equivalent: Power Factor Correction Calculator
Corrects lagging power factor by adding capacitor banks.
"""
import streamlit as st
import sys, os
import plotly.graph_objects as go
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.session import init_session, get_utility_rates
from utils.arc_defaults import get_defaults
from arcs.arc_measur import power_factor_savings, power_factor_utility_penalty

st.set_page_config(page_title="AR — Power Factor Correction", layout="wide")
init_session()

st.title("AR: Power Factor Correction")
st.caption("MEASUR-equivalent capacitor bank sizing. Corrects lagging power factor to reduce kVA demand charges and reactive power penalties.")

# ── Defaults ──────────────────────────────────────────────────────────────────
# Use 2.4239 as closest ARC code; power factor is sometimes listed under electrical ARCs
# We'll define minimal defaults here inline since PF correction may not have a dedicated MALT ARC code
PF_OBS_DEFAULT = (
    "A review of the facility's utility bills indicates an average power factor of "
    "{pf_current:.2f}, which is below the utility's threshold of {pf_threshold:.2f}. "
    "The facility is being assessed a reactive power penalty on each monthly bill. "
    "The average billed real power demand is {avg_kw:.0f} kW, resulting in an "
    "apparent power draw of {kva_current:.0f} kVA and reactive demand of {kvar_current:.0f} kVAR."
)
PF_REC_DEFAULT = (
    "Install a {kvar_required:.0f} kVAR capacitor bank at the main electrical panel "
    "to correct the power factor from {pf_current:.2f} to {pf_target:.2f}. "
    "This will reduce the apparent power demand, eliminate the reactive power penalty, "
    "and reduce conductor I²R losses. Estimated installed cost: ${cap_cost:,.0f}. "
    "Estimated annual cost savings: ${ann_savings:,.0f}/yr with a simple payback of "
    "{payback:.1f} years."
)
PF_TECH_DEFAULT = (
    "Power factor (PF) is the ratio of real power (kW) to apparent power (kVA): PF = kW/kVA = cos(θ). "
    "A lagging power factor occurs when inductive loads (motors, transformers) draw reactive power (kVAR) "
    "from the grid, increasing apparent power and current draw without performing useful work. "
    "Capacitor banks supply reactive power locally, reducing current from the utility and eliminating "
    "reactive demand penalties. Required capacitor bank size: Q_C = kW × (tan θ_current − tan θ_target) [kVAR]."
)

with st.expander("📝 Observation & Recommendation", expanded=True):
    c1, c2 = st.columns(2)
    ar_num = c1.text_input("AR Number", value="AR-1", key="pf_ar_num")
    obs  = c1.text_area("Observation", value=st.session_state.get("pf_obs", PF_OBS_DEFAULT),
                        height=120, key="pf_obs")
    rec  = c2.text_area("Recommendation", value=st.session_state.get("pf_rec", PF_REC_DEFAULT),
                        height=120, key="pf_rec")
    tech = c2.text_area("Technology Description",
                        value=st.session_state.get("pf_tech", PF_TECH_DEFAULT),
                        height=120, key="pf_tech")

# ── System Parameters ─────────────────────────────────────────────────────────
st.subheader("Electrical System Parameters")
col1, col2, col3 = st.columns(3)
avg_kw     = col1.number_input("Average real power demand (kW)", value=200.0, min_value=1.0,
                                step=10.0, key="pf_kw",
                                help="Average kW from utility bills (real power, not apparent)")
pf_current = col2.slider("Current power factor", 0.60, 0.99, 0.78, 0.01, key="pf_curr",
                          help="Read from utility bill or power quality meter")
pf_target  = col3.slider("Target power factor", 0.80, 1.00, 0.95, 0.01, key="pf_target",
                          help="Most utilities consider 0.90–0.95 acceptable; 0.95 is a common target")

if pf_target <= pf_current:
    st.warning("Target power factor must be higher than current power factor.")

# ── Utility Rate Structure ─────────────────────────────────────────────────────
st.subheader("Utility Rate Structure")
st.info("💡 Power factor savings come from one or more of: (1) kVA-based demand charges, "
        "(2) kVAR reactive demand penalties, or (3) percentage-based PF surcharges. "
        "Check your utility tariff to determine which apply.")

col1, col2, col3, col4 = st.columns(4)
rate_type = col1.selectbox("Utility billing type",
                            ["kVA demand charge", "kVAR reactive penalty",
                             "PF surcharge (% of bill)", "None / Estimate only"],
                            key="pf_rate_type")

demand_rate_kva  = 0.0
demand_rate_kvar = 0.0
pf_threshold     = 0.90
penalty_pct      = 0.01
monthly_bill     = 0.0

if rate_type == "kVA demand charge":
    demand_rate_kva  = col2.number_input("kVA demand rate ($/kVA/mo)", value=8.0, step=0.5, key="pf_kva_rate")
elif rate_type == "kVAR reactive penalty":
    demand_rate_kvar = col2.number_input("kVAR demand rate ($/kVAR/mo)", value=1.50, step=0.25, key="pf_kvar_rate")
elif rate_type == "PF surcharge (% of bill)":
    pf_threshold = col2.number_input("PF threshold (below this = penalty)", value=0.90, step=0.01,
                                      min_value=0.80, max_value=1.00, key="pf_thresh")
    penalty_pct  = col3.number_input("Penalty % per 0.01 PF below threshold", value=1.0, step=0.5,
                                      min_value=0.1, max_value=5.0, key="pf_pct") / 100
    monthly_bill = col4.number_input("Average monthly utility bill ($)", value=5000.0, step=100.0,
                                      key="pf_monthly_bill")

impl_cost_per_kvar = col2.number_input("Capacitor bank cost ($/kVAR installed)",
                                        value=20.0, step=2.0, key="pf_cap_cost",
                                        help="Typical installed cost: $15–30/kVAR for fixed banks") \
    if rate_type not in ["kVA demand charge", "kVAR reactive penalty"] else \
    col3.number_input("Capacitor bank cost ($/kVAR installed)", value=20.0, step=2.0, key="pf_cap_cost2",
                       help="Typical installed cost: $15–30/kVAR for fixed banks")

# ── Calculate ────────────────────────────────────────────────────────────────
if st.button("Calculate Power Factor Savings", type="primary", key="pf_calc") and pf_target > pf_current:
    if rate_type == "PF surcharge (% of bill)":
        penalty = power_factor_utility_penalty(
            avg_kw, pf_current, pf_threshold, penalty_pct, monthly_bill
        )
        st.session_state["pf_penalty"] = penalty
        # Also compute capacitor sizing
        result = power_factor_savings(
            avg_kw, pf_current, pf_target,
            capacitor_cost_per_kvar=impl_cost_per_kvar if "pf_cap_cost" in st.session_state else 20.0
        )
        # Override savings with penalty avoidance
        result["total_ann_savings"] = penalty.get("penalty_annual", 0)
        result["payback_years"] = result["estimated_cap_cost"] / result["total_ann_savings"] \
            if result["total_ann_savings"] > 0 else float("inf")
        st.session_state["pf_result"] = result
    else:
        result = power_factor_savings(
            avg_kw, pf_current, pf_target,
            demand_rate_kva=demand_rate_kva,
            demand_rate_kvar=demand_rate_kvar,
            capacitor_cost_per_kvar=st.session_state.get("pf_cap_cost2", impl_cost_per_kvar
                                   if "pf_cap_cost" not in st.session_state else impl_cost_per_kvar),
        )
        st.session_state["pf_result"] = result
        if "pf_penalty" in st.session_state:
            del st.session_state["pf_penalty"]

if "pf_result" in st.session_state:
    r = st.session_state["pf_result"]
    if "error" in r:
        st.error(r["error"])
    else:
        st.subheader("Results")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Current kVA", f"{r['kva_current']:.1f} kVA")
        c2.metric("Proposed kVA", f"{r['kva_proposed']:.1f} kVA")
        c3.metric("kVAR Required", f"{r['kvar_required']:.1f} kVAR")
        c4.metric("Annual Savings", f"${r['total_ann_savings']:,.0f}")
        pb = r.get("payback_years", float("inf"))
        c5.metric("Simple Payback", f"{pb:.1f} yr" if pb != float("inf") else "N/A")

        # Capacitor sizing
        col1, col2, col3 = st.columns(3)
        col1.metric("Capacitor Bank Size", f"{r['kvar_required']:.0f} kVAR")
        col2.metric("Estimated Installed Cost", f"${r['estimated_cap_cost']:,.0f}")
        col3.metric("Power Factor Improvement", r["pf_improvement"])

        # Power triangle diagram
        with st.expander("Power Triangle Visualization", expanded=True):
            import math
            theta_c = math.acos(pf_current)
            theta_t = math.acos(pf_target)
            kva_c  = r["kva_current"]
            kvar_c = r["kvar_current"]
            kva_t  = r["kva_proposed"]
            kvar_t = r["kvar_proposed"]
            kw     = avg_kw

            fig = go.Figure()
            # Current triangle
            fig.add_trace(go.Scatter(
                x=[0, kw, kw, 0], y=[0, 0, kvar_c, 0],
                fill="toself", fillcolor="rgba(255,100,100,0.15)",
                line=dict(color="red", width=2), name=f"Current (PF={pf_current:.2f})",
                mode="lines"
            ))
            # Proposed triangle
            fig.add_trace(go.Scatter(
                x=[0, kw, kw, 0], y=[0, 0, kvar_t, 0],
                fill="toself", fillcolor="rgba(0,100,255,0.15)",
                line=dict(color="blue", width=2), name=f"Proposed (PF={pf_target:.2f})",
                mode="lines"
            ))
            # Capacitor reduction arrow
            fig.add_annotation(
                x=kw, y=(kvar_c + kvar_t) / 2,
                text=f"−{r['kvar_required']:.0f} kVAR<br>(capacitors)",
                showarrow=True, arrowhead=2, arrowcolor="green",
                ax=50, ay=0, font=dict(color="green", size=12)
            )
            fig.update_layout(
                xaxis_title="Real Power (kW)",
                yaxis_title="Reactive Power (kVAR)",
                title="Power Triangle: Before vs. After Capacitor Bank",
                height=350,
                legend=dict(orientation="h", y=-0.25)
            )
            st.plotly_chart(fig, use_container_width=True)

        with st.expander("Calculation Detail"):
            st.markdown(f"""
**Power Factor Analysis:**
- Real power (kW): **{avg_kw:.1f} kW**
- Current: kVA = {kw:.1f} / {pf_current:.3f} = **{r['kva_current']:.1f} kVA** | kVAR = **{r['kvar_current']:.1f} kVAR**
- Proposed: kVA = {kw:.1f} / {pf_target:.3f} = **{r['kva_proposed']:.1f} kVA** | kVAR = **{r['kvar_proposed']:.1f} kVAR**
- Capacitor bank required: Δ kVAR = **{r['kvar_required']:.1f} kVAR**

**Savings Breakdown:**
- kVA savings: {r['delta_kva']:.1f} kVA × ${demand_rate_kva:.2f}/kVA/mo × 12 = **${r['ann_kva_savings']:,.0f}/yr**
- kVAR savings: {r['delta_kvar']:.1f} kVAR × ${demand_rate_kvar:.2f}/kVAR/mo × 12 = **${r['ann_kvar_savings']:,.0f}/yr**
- **Total annual savings: ${r['total_ann_savings']:,.0f}/yr**

**Capital Cost:**
- {r['kvar_required']:.0f} kVAR × ${r['estimated_cap_cost']/r['kvar_required'] if r['kvar_required']>0 else 0:.0f}/kVAR = **${r['estimated_cap_cost']:,.0f}**
- Simple payback: ${r['estimated_cap_cost']:,.0f} / ${r['total_ann_savings']:,.0f} = **{pb:.1f} yr**
            """)

        if "pf_penalty" in st.session_state:
            pen = st.session_state["pf_penalty"]
            st.info(f"**Utility PF Surcharge:** {pen.get('message','')} "
                    f"Monthly penalty: ${pen.get('penalty_monthly',0):,.0f} → "
                    f"Annual: **${pen.get('penalty_annual',0):,.0f}/yr**")

        st.divider()
        if st.button("💾 Save this AR to Report", type="primary", key="pf_save"):
            pb_val = r.get("payback_years", float("inf"))
            ar_entry = {
                "arc_code": "PF",
                "ar_number": ar_num,
                "title": "Power Factor Correction",
                "resources": [{"type": "Demand Reduction", "savings": r["delta_kva"],
                                "unit": "kVA/mo"}],
                "total_cost_savings": r["total_ann_savings"],
                "implementation_cost": r["estimated_cap_cost"],
                "payback": pb_val if pb_val != float("inf") else 99.0,
                "observation": st.session_state.get("pf_obs", ""),
                "recommendation": st.session_state.get("pf_rec", ""),
                "tech_description": st.session_state.get("pf_tech", ""),
                "calculation_details": r,
            }
            ar_list = [a for a in st.session_state.get("ar_list", [])
                       if not (a.get("arc_code") == "PF" and a.get("ar_number") == ar_num)]
            ar_list.append(ar_entry)
            st.session_state["ar_list"] = ar_list
            st.success(f"✅ Saved. Total ARs: {len(ar_list)}")
