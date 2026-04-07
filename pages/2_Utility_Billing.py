"""
Page 2 — Utility Billing (Electricity, Natural Gas, Water)
12-month data entry with auto-computed totals and average rates.
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.session import init_session, get_utility_rates, MONTHS

st.set_page_config(page_title="Utility Billing", page_icon="⚡", layout="wide")
init_session()

st.title("⚡ Utility Billing Data")
st.caption("Enter 12 months of billing data. Totals and average rates are calculated automatically.")

# ── Helper: render an editable billing table ──────────────────────────────────
def billing_table(rows_key, columns, display_names, format_map=None):
    """Render an editable dataframe for billing rows. Returns updated rows."""
    rows = st.session_state[rows_key]
    df = pd.DataFrame(rows)
    # Keep only the columns we want
    df = df[columns]
    df.columns = display_names

    edited = st.data_editor(
        df,
        num_rows="fixed",
        use_container_width=True,
        key=f"editor_{rows_key}",
        column_config={
            display_names[0]: st.column_config.TextColumn("Month", disabled=True, width="small"),
        }
    )
    # Write back + validate
    has_negatives = False
    for i, row in enumerate(rows):
        for col_key, col_name in zip(columns[1:], display_names[1:]):
            try:
                val = float(edited.iloc[i][col_name])
                if val < 0:
                    has_negatives = True
                rows[i][col_key] = val
            except Exception:
                pass
    if has_negatives:
        st.warning("⚠️ Negative values detected in billing table. Please verify — billing amounts should be ≥ 0.")
    st.session_state[rows_key] = rows
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: ELECTRICITY
# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["⚡ Electricity", "🔥 Natural Gas", "💧 Water"])

with tab1:
    st.subheader("Electricity Billing")
    st.caption("Enter monthly electricity consumption and cost. Demand charges are separate.")

    rows = billing_table(
        "elec_rows",
        ["month", "kwh", "elec_cost", "kw", "demand_cost", "fee"],
        ["Month", "Usage [kWh]", "Elec Cost [$]", "Demand [kW]", "Demand Cost [$]", "Fees [$]"]
    )

    # Compute totals
    ann_kwh  = sum(r["kwh"] for r in rows)
    ann_ec   = sum(r["elec_cost"] for r in rows)
    ann_kw   = sum(r["kw"] for r in rows)
    ann_dc   = sum(r["demand_cost"] for r in rows)
    ann_fee  = sum(r["fee"] for r in rows)
    ann_tot  = ann_ec + ann_dc + ann_fee
    elec_rate   = ann_ec / ann_kwh if ann_kwh else 0.0
    demand_rate = ann_dc / ann_kw  if ann_kw  else 0.0

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Annual kWh", f"{ann_kwh:,.0f}")
    c2.metric("Avg Elec Rate", f"${elec_rate:.4f}/kWh")
    c3.metric("Annual kW-months", f"{ann_kw:,.0f}")
    c4.metric("Avg Demand Rate", f"${demand_rate:.3f}/kW")
    c5.metric("Annual Elec Total", f"${ann_tot:,.2f}")

    st.info(f"📊 **Average Electricity Rate** = ${elec_rate:.4f} /kWh  |  "
            f"**Average Demand Rate** = ${demand_rate:.3f} /kW")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: NATURAL GAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Natural Gas Billing")
    has_gas = st.checkbox("This facility uses natural gas", value=st.session_state["has_gas"])
    st.session_state["has_gas"] = has_gas

    if has_gas:
        rows_g = billing_table(
            "gas_rows",
            ["month", "mmbtu", "cost", "fee"],
            ["Month", "Usage [MMBtu]", "Cost [$]", "Fees [$]"]
        )

        ann_mmbtu = sum(r["mmbtu"] for r in rows_g)
        ann_gc    = sum(r["cost"]  for r in rows_g)
        ann_gfee  = sum(r["fee"]   for r in rows_g)
        ann_gtot  = ann_gc + ann_gfee
        gas_rate  = ann_gc / ann_mmbtu if ann_mmbtu else 0.0

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Annual MMBtu", f"{ann_mmbtu:,.2f}")
        c2.metric("Avg Gas Rate", f"${gas_rate:.3f}/MMBtu")
        c3.metric("Annual Gas Total", f"${ann_gtot:,.2f}")

        # UAT Bug Fix: warn if values look like therms instead of MMBtu
        # 1 therm = 0.1 MMBtu, so annual usage >20,000 MMBtu is suspicious
        if ann_mmbtu > 0:
            avg_monthly = ann_mmbtu / 12
            if avg_monthly > 500:
                st.info(f"📊 **Average Natural Gas Rate** = ${gas_rate:.3f} /MMBtu")
            elif 0 < avg_monthly < 5:
                st.warning(
                    "⚠️ **Gas unit check:** Monthly average is {:.1f} MMBtu, which seems low. "
                    "If your bill is in **therms**, convert: 1 therm = 0.1 MMBtu. "
                    "10 therms = 1 MMBtu.".format(avg_monthly)
                )
                st.info(f"📊 **Average Natural Gas Rate** = ${gas_rate:.3f} /MMBtu")
            else:
                st.info(f"📊 **Average Natural Gas Rate** = ${gas_rate:.3f} /MMBtu")
        else:
            st.info(f"📊 **Average Natural Gas Rate** = ${gas_rate:.3f} /MMBtu")
    else:
        st.info("No natural gas data to enter.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: WATER
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Water / Sewer Billing")
    has_water = st.checkbox("This facility has water billing", value=st.session_state["has_water"])
    st.session_state["has_water"] = has_water

    if has_water:
        rows_w = billing_table(
            "water_rows",
            ["month", "tgal", "water_cost", "sewer_cost", "fee"],
            ["Month", "Water [Tgal]", "Water Cost [$]", "Sewer Cost [$]", "Fees [$]"]
        )

        ann_tgal = sum(r["tgal"] for r in rows_w)
        ann_wc   = sum(r["water_cost"] for r in rows_w)
        ann_sc   = sum(r["sewer_cost"] for r in rows_w)
        ann_wfee = sum(r["fee"] for r in rows_w)
        water_rate = ann_wc / ann_tgal if ann_tgal else 0.0
        sewer_rate = ann_sc / ann_tgal if ann_tgal else 0.0

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Annual Tgal", f"{ann_tgal:,.3f}")
        c2.metric("Avg Water Rate", f"${water_rate:.2f}/Tgal")
        c3.metric("Avg Sewer Rate", f"${sewer_rate:.2f}/Tgal")
        c4.metric("Annual Water Total", f"${ann_wc + ann_sc + ann_wfee:,.2f}")

        st.info(f"📊 **Water Rate** = ${water_rate:.2f}/Tgal  |  **Sewer Rate** = ${sewer_rate:.2f}/Tgal")
    else:
        st.info("No water data to enter.")

# ── Grand total ───────────────────────────────────────────────────────────────
st.divider()
rates = get_utility_rates()
st.metric("💰 Total Annual Utility Cost", f"${rates['total_annual_utility_cost']:,.2f}")
