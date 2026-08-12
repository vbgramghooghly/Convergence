import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action
from datetime import date

def show():
    require_role('superadmin', 'district', 'department')
    st.title("Department Targets – FY 2026-27")

    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # Fetch necessary master data
    departments = supabase.table("departments").select("id,department_name").eq("active", True).execute().data
    districts = supabase.table("districts").select("id,district_name").eq("active", True).execute().data

    # Apply role restrictions
    if role == 'department':
        allowed_dept = user.get('department_id')
        departments = [d for d in departments if d['id'] == allowed_dept]
        allowed_district = user.get('district_id')
        districts = [d for d in districts if d['id'] == allowed_district]
    elif role == 'district':
        allowed_district = user.get('district_id')
        districts = [d for d in districts if d['id'] == allowed_district]

    # Build dropdown dicts
    dept_dict = {d['department_name']: d['id'] for d in departments}
    dist_dict = {d['district_name']: d['id'] for d in districts}

    tab1, tab2 = st.tabs(["View Targets", "Add/Edit Target"])

    with tab1:
        st.subheader("Existing Targets")
        # Query with filters
        query = supabase.table("department_targets").select("*")
        if role == 'department':
            query = query.eq("department_id", allowed_dept).eq("district_id", allowed_district)
        elif role == 'district':
            query = query.eq("district_id", allowed_district)
        data = query.execute().data
        df = pd.DataFrame(data)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            # Download Excel
            from utils.excel import dataframe_to_excel
            excel_data = dataframe_to_excel(df, "department_targets")
            st.download_button(label="Download Targets Excel", data=excel_data, file_name="department_targets.xlsx")
        else:
            st.info("No targets set yet.")

    with tab2:
        st.subheader("Add / Update Department Target")
        with st.form("target_form"):
            if role == 'department':
                dept_sel = list(dept_dict.keys())[0]  # only one option
                dist_sel = list(dist_dict.keys())[0]  # only one
                st.text(f"Department: {dept_sel}")
                st.text(f"District: {dist_sel}")
            else:
                dept_sel = st.selectbox("Department", list(dept_dict.keys()))
                dist_sel = st.selectbox("District", list(dist_dict.keys()))

            # Additional fields
            activity = st.text_input("Activity (optional)")
            asset_count = st.number_input("Number of assets/works", min_value=0, value=0)
            existing_status = st.text_input("Existing Status")
            annual_plan_scope = st.text_area("Scope under Annual Plan")
            desired_target = st.number_input("Desired Target for FY", min_value=0, value=0)
            dept_fund = st.number_input("Department Fund (₹ Cr.)", min_value=0.0, format="%.2f")
            vbg_fund = st.number_input("VB-G RAM G Fund (₹ Cr.)", min_value=0.0, format="%.2f")
            tech_support = st.text_input("Technical Support Required")
            pia = st.selectbox("PIA", ["Department", "Gram Panchayat", "Panchayat Samiti", "Other"])
            expected_persondays = st.number_input("Expected Persondays", min_value=0, value=0)
            timeline_start = st.date_input("Timeline Start", date.today())
            timeline_end = st.date_input("Timeline End", date.today())

            submitted = st.form_submit_button("Save Target")
            if submitted:
                dept_id = dept_dict[dept_sel]
                dist_id = dist_dict[dist_sel]

                target_record = {
                    "department_id": dept_id,
                    "district_id": dist_id,
                    "financial_year": "2026-27",
                    "activity": activity,
                    "asset_count": asset_count,
                    "existing_status": existing_status,
                    "annual_plan_scope": annual_plan_scope,
                    "desired_target": desired_target,
                    "department_fund": dept_fund,
                    "vbgramg_fund": vbg_fund,
                    "technical_support": tech_support,
                    "pia": pia,
                    "expected_persondays": expected_persondays,
                    "timeline_start": str(timeline_start),
                    "timeline_end": str(timeline_end),
                    "created_by": user['id']
                }

                # Check if target already exists for this dept+district+fy+activity
                existing = supabase.table("department_targets").select("id") \
                    .eq("department_id", dept_id).eq("district_id", dist_id) \
                    .eq("financial_year", "2026-27").eq("activity", activity).execute().data
                if existing:
                    result = supabase.table("department_targets").update(target_record).eq("id", existing[0]['id']).execute()
                    st.success("Target updated!")
                    log_action(user, "UPDATE", "department_targets", existing[0]['id'], new_vals=target_record)
                else:
                    result = supabase.table("department_targets").insert(target_record).execute()
                    st.success("Target added!")
                    log_action(user, "CREATE", "department_targets", result.data[0]['id'], new_vals=target_record)
                st.rerun()
