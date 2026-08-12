import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action
from utils.excel import dataframe_to_excel

def show():
    require_role('superadmin', 'district', 'block', 'department')
    st.title("Convergence Register")
    
    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # ---------- Filters (sidebar) ----------
    st.sidebar.subheader("Filter Register")
    districts = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
    departments = supabase.table("departments").select("id,department_name").eq("active", True).execute().data
    themes = supabase.table("themes").select("id,theme_name").eq("active", True).execute().data

    # Role restrictions
    if role == 'district':
        districts = [d for d in districts if d['id'] == user['district_id']]
    elif role == 'block':
        districts = [d for d in districts if d['id'] == user['district_id']]  # block user sees only parent district
    elif role == 'department':
        departments = [d for d in departments if d['id'] == user['department_id']]
        districts = [d for d in districts if d['id'] == user['district_id']]

    dist_sel = st.sidebar.selectbox("District", ["All"] + [d['district_name'] for d in districts])
    dept_sel = st.sidebar.selectbox("Department", ["All"] + [d['department_name'] for d in departments])
    theme_sel = st.sidebar.selectbox("Theme", ["All"] + [t['theme_name'] for t in themes])
    status_sel = st.sidebar.selectbox("Status", ["All", "Planned", "Approved", "Under Implementation", "Completed", "Delayed"])
    search_term = st.sidebar.text_input("Search (activity, PIA, etc.)")

    # ---------- Build query ----------
    query = supabase.table("convergence_register").select("*")
    if role == 'district':
        query = query.eq("district_id", user['district_id'])
    elif role == 'block':
        query = query.eq("block_id", user['block_id'])
    elif role == 'department':
        query = query.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    if dist_sel != "All":
        dist_id = next(d['id'] for d in districts if d['district_name'] == dist_sel)
        query = query.eq("district_id", dist_id)
    if dept_sel != "All":
        dept_id = next(d['id'] for d in departments if d['department_name'] == dept_sel)
        query = query.eq("department_id", dept_id)
    if theme_sel != "All":
        theme_id = next(t['id'] for t in themes if t['theme_name'] == theme_sel)
        query = query.eq("thematic_category_id", theme_id)
    if status_sel != "All":
        query = query.eq("current_status", status_sel)

    # Execute and filter by search term (client-side)
    data = query.execute().data
    df = pd.DataFrame(data)
    if search_term and not df.empty:
        mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)
        df = df[mask]

    # ---------- Display records ----------
    st.subheader(f"Convergence Activities ({len(df)} records)")
    if not df.empty:
        # Convert ID columns to names for readability
        dist_names = {d['id']: d['district_name'] for d in districts}
        dept_names = {d['id']: d['department_name'] for d in departments}
        theme_names = {t['id']: t['theme_name'] for t in themes}
        df_display = df.copy()
        df_display['district_id'] = df_display['district_id'].map(dist_names)
        df_display['department_id'] = df_display['department_id'].map(dept_names)
        df_display['thematic_category_id'] = df_display['thematic_category_id'].map(theme_names)
        st.dataframe(df_display, use_container_width=True)
        
        # Download button
        excel = dataframe_to_excel(df, "Convergence_Register")
        st.download_button("📥 Download Excel", excel, "convergence_register.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No records found.")

    # ---------- Add / Edit Record ----------
    with st.expander("➕ Add New Convergence Activity"):
        with st.form("add_convergence", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fy = st.text_input("Financial Year", value="2026-27")
                district = st.selectbox("District*", [d['district_name'] for d in districts])
                block_list = supabase.table("blocks").select("id,block_name").eq("active", True).execute().data
                block = st.selectbox("Block", ["None"] + [b['block_name'] for b in block_list])
                gp = st.text_input("Gram Panchayat")
            with col2:
                dept = st.selectbox("Department*", [d['department_name'] for d in departments])
                activity_desc = st.text_area("Activity / Work Description*")
                theme = st.selectbox("Thematic Category", [t['theme_name'] for t in themes])
                vbgramg = st.checkbox("Permissible under VB-G RAM G?")
            col3, col4 = st.columns(2)
            with col3:
                number_status = st.text_input("Number / Status")
                scope = st.text_area("Scope under Annual Plan")
                desired_target = st.number_input("Desired Target", min_value=0, value=0)
                convergence_type = st.selectbox("Type of Convergence", ["Financial", "Technical", "Financial + Technical"])
            with col4:
                dept_fund = st.number_input("Department Fund (₹ Cr.)", min_value=0.0, format="%.2f")
                vbg_fund = st.number_input("VB-G RAM G Fund (₹ Cr.)", min_value=0.0, format="%.2f")
                pia = st.selectbox("PIA", ["Department", "Gram Panchayat", "Panchayat Samiti", "Other"])
                expected_pd = st.number_input("Expected Persondays", min_value=0, value=0)
                start_date = st.date_input("Target Start Date", date.today())
                end_date = st.date_input("Target Completion Date", date.today())
            remarks = st.text_area("Remarks")
            submitted = st.form_submit_button("Save")

            if submitted:
                if not activity_desc or not district or not dept:
                    st.error("Please fill all required fields (District, Department, Activity).")
                else:
                    dist_id = next(d['id'] for d in districts if d['district_name'] == district)
                    dept_id = next(d['id'] for d in departments if d['department_name'] == dept)
                    block_id = None
                    if block != "None":
                        block_id = next(b['id'] for b in block_list if b['block_name'] == block)
                    theme_id = next(t['id'] for t in themes if t['theme_name'] == theme) if theme else None

                    record = {
                        "financial_year": fy,
                        "district_id": dist_id,
                        "block_id": block_id,
                        "gram_panchayat": gp,
                        "department_id": dept_id,
                        "activity_description": activity_desc,
                        "thematic_category_id": theme_id,
                        "vbgramg_permissible": vbgramg,
                        "number_status": number_status,
                        "annual_plan_scope": scope,
                        "desired_target": desired_target,
                        "convergence_type": convergence_type,
                        "department_fund": dept_fund,
                        "vbgramg_fund": vbg_fund,
                        "pia": pia,
                        "expected_persondays": expected_pd,
                        "target_start_date": str(start_date),
                        "target_completion_date": str(end_date),
                        "duration_days": (end_date - start_date).days if end_date > start_date else 0,
                        "current_status": "Planned",
                        "remarks": remarks,
                        "created_by": user['id']
                    }
                    result = supabase.table("convergence_register").insert(record).execute()
                    if result.data:
                        log_action(user, "CREATE", "convergence_register", result.data[0]['id'], new_vals=record)
                        st.success("Activity added successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to save record.")
