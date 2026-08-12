import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import get_supabase
from auth.auth import require_role, get_current_user

def show():
    require_role('superadmin', 'district', 'block', 'department')
    st.title("Convergence Dashboard – FY 2026-27")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        districts = get_supabase().table("districts").select("id,district_name").execute().data
        district_sel = st.selectbox("District", ["All"] + [d['district_name'] for d in districts])
    with col2:
        departments = get_supabase().table("departments").select("id,department_name").execute().data
        dept_sel = st.selectbox("Department", ["All"] + [d['department_name'] for d in departments])
    with col3:
        statuses = ["All", "Planned", "Approved", "Under Implementation", "Completed", "Delayed"]
        status_sel = st.selectbox("Status", statuses)

    # Fetch data from Supabase with role-based restrictions
    query = get_supabase().table("convergence_register").select("*", count="exact")
    # Apply role restrictions (RLS already handles, but we can add client-side filtering for performance)
    user = get_current_user()
    if user['role'] == 'district':
        query = query.eq("district_id", user['district_id'])
    elif user['role'] == 'block':
        query = query.eq("block_id", user['block_id'])
    elif user['role'] == 'department':
        query = query.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    # Apply filters
    if district_sel != "All":
        dist_id = next(d['id'] for d in districts if d['district_name'] == district_sel)
        query = query.eq("district_id", dist_id)
    if dept_sel != "All":
        dept_id = next(d['id'] for d in departments if d['department_name'] == dept_sel)
        query = query.eq("department_id", dept_id)
    if status_sel != "All":
        query = query.eq("current_status", status_sel)

    data = query.execute().data
    df = pd.DataFrame(data)
    
    # KPI cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Activities", len(df))
    col2.metric("Total Converged Fund (₹ Cr.)", f"{df['total_converged_fund'].sum():.2f}" if not df.empty else "0")
    col3.metric("Expected Persondays", f"{df['expected_persondays'].sum():,}" if not df.empty else "0")
    col4.metric("Actual Persondays", f"{df['persondays_generated'].sum():,}" if not df.empty else "0")

    # Charts
    st.subheader("Department-wise Fund Allocation")
    if not df.empty:
        dept_fig = px.bar(df.groupby("department_id")[["department_fund","vbgramg_fund"]].sum().reset_index(),
                          x="department_id", y=["department_fund","vbgramg_fund"],
                          barmode="stack", labels={"value":"Fund (₹ Cr.)", "variable":"Source"})
        st.plotly_chart(dept_fig, use_container_width=True)

    # More charts as per specification...
    # (Add similar calls for district, status, etc.)
