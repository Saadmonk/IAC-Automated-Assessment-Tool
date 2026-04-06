"""
Page 1 — Cover / Report Metadata
"""
import streamlit as st
import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.session import init_session

st.set_page_config(page_title="Cover Info", page_icon="📋", layout="wide")
init_session()

st.title("📋 Report Cover Information")
st.caption("Fill in the basic metadata that appears on the cover page and title block.")

col1, col2 = st.columns(2)
with col1:
    st.session_state["report_number"] = st.text_input(
        "Report Number", value=st.session_state["report_number"],
        placeholder="e.g. LT8438")
    st.session_state["location"] = st.text_input(
        "Location (City, State)", value=st.session_state["location"],
        placeholder="e.g. Covington, LA")
    st.session_state["principal_products"] = st.text_input(
        "Principal Products / Industry", value=st.session_state["principal_products"],
        placeholder="e.g. General Medical and Surgical Hospitals")
    st.session_state["naics_code"] = st.text_input(
        "NAICS Code", value=st.session_state["naics_code"], placeholder="e.g. 622110")
    st.session_state["sic_code"] = st.text_input(
        "SIC Code", value=st.session_state["sic_code"], placeholder="e.g. 8062")

with col2:
    date_val = st.session_state["site_visit_date"] or datetime.date.today()
    st.session_state["site_visit_date"] = st.date_input(
        "Site Visit Date", value=date_val)
    st.session_state["annual_sales"] = st.text_input(
        "Annual Sales (optional)", value=st.session_state["annual_sales"],
        placeholder="e.g. $50 million")
    st.session_state["num_employees"] = st.text_input(
        "Number of Employees (optional)", value=st.session_state["num_employees"],
        placeholder="e.g. 150")

st.divider()
st.subheader("Assessment Team")

col3, col4, col5 = st.columns(3)
with col3:
    st.session_state["lead_faculty"] = st.text_input(
        "Lead Faculty", value=st.session_state["lead_faculty"])
with col4:
    st.session_state["lead_student"] = st.text_input(
        "Lead Student", value=st.session_state["lead_student"],
        placeholder="e.g. Md Mainuddin Khaled")
with col5:
    st.session_state["safety_student"] = st.text_input(
        "Safety Student", value=st.session_state["safety_student"],
        placeholder="e.g. Imtiaz Taimoor")

st.session_state["other_students"] = st.text_input(
    "Other Team Members (comma separated)", value=st.session_state["other_students"],
    placeholder="e.g. Md Rakibul Islam, Jane Doe")

st.divider()
st.success("✅ Complete this page, then continue to **Utility Billing** in the sidebar.")
