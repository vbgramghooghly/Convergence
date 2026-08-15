import pandas as pd
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.db import get_supabase
from utils.audit import log_action

def show():
    require_role("superadmin", "district", "block", "department")
    st.markdown("<h2 style='margin-bottom: 0px;'>📋 Work Entry & Convergence Register</h2>", unsafe_allow_html=True)
    st.caption("Plan, Register, and Bulk Upload Convergence Works.")
    
    supabase = get_supabase()
    user = get_current_user()
    role = user["role"]

    # Basic fetch
    fys = supabase.table("financial_years").select("*").execute().data
    districts = supabase.table("districts").select("*").execute().data
    blocks = supabase.table("blocks").select("*").execute().data
    depts = supabase.table("departments").select("*").execute().data

    fy_map = {f["year_name"]: f["id"] for f in fys}
    dist_reverse_map = {d["id"]: d["district_name"] for d in districts}
    block_reverse_map = {b["id"]: b["block_name"] for b in blocks}
    dept_reverse_map = {d["id"]: d["department_name"] for d in depts}

    query = supabase.table("convergence_register").select("*")
    if role == "district": query = query.eq("district_id", user["district_id"])
    elif role == "block": query = query.eq("block_id", user["block_id"])
    elif role == "department": query = query.eq("department_id", user["department_id"]).eq("district_id", user["district_id"])

    records = query.execute().data or []
    
    tab1, tab2 = st.tabs(["📋 Activity Register", "➕ Add / Bulk Upload"])
    
    with tab1:
        st.markdown(f"#### Saved Activities ({len(records)})")
        if records:
            df = pd.DataFrame(records)
            df["District"] = df["district_id"].map(dist_reverse_map)
            df["Block"] = df["block_id"].map(block_reverse_map)
            df["Department"] = df["department_id"].map(dept_reverse_map)
            df.rename(columns={"activity_description": "Work Name", "current_status": "Status", "total_converged_fund": "Total Fund (Lakhs)"}, inplace=True)
            st.dataframe(df[["District", "Block", "Department", "Work Name", "Status", "Total Fund (Lakhs)"]], use_container_width=True, hide_index=True)
        else:
            st.info("No records found.")
            
    with tab2:
        st.markdown("#### Data Entry operations are fully handled through the master spreadsheet templates to ensure MIS Code compliance.")
        st.info("Please refer to the District Nodal Officer for current CSV ingestion formats.")
