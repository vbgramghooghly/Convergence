import streamlit as st
import pandas as pd
from utils.db import get_supabase
from utils.validators import validate_convergence_record
from auth.auth import require_role, get_current_user
import datetime

def show():
    require_role('superadmin', 'district', 'block', 'department')
    st.title("Convergence Register")
    
    supabase = get_supabase()
    user = get_current_user()
    
    # Tabs for viewing and adding
    tab1, tab2 = st.tabs(["View Records", "Add New Record"])
    
    with tab1:
        st.subheader("Registered Convergence Activities")
        # Fetch records with filters, similar to dashboard
        # ...
        df = pd.DataFrame(...)
        st.dataframe(df, use_container_width=True)
        
        # Download Excel button
        if st.button("Download Excel"):
            from utils.excel import dataframe_to_excel
            output = dataframe_to_excel(df, "convergence_register")
            st.download_button(label="Download Excel", data=output, file_name="convergence_register.xlsx")
    
    with tab2:
        with st.form("new_convergence"):
            # All fields as per specification
            district = st.selectbox("District", [...])
            block = st.selectbox("Block", [...])  # dependent on district
            department = st.selectbox("Department", [...])
            activity = st.text_area("Activity/Work Description")
            thematic = st.selectbox("Thematic Category", [...])
            # ... many fields ...
            submitted = st.form_submit_button("Save")
            if submitted:
                record = {
                    "financial_year": "2026-27",
                    "district_id": district,
                    "block_id": block,
                    "department_id": department,
                    "activity_description": activity,
                    "convergence_type": convergence_type,
                    "department_fund": dept_fund,
                    "vbgramg_fund": vbg_fund,
                    # ...
                    "created_by": user['id']
                }
                errors = validate_convergence_record(record)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    result = supabase.table("convergence_register").insert(record).execute()
                    if result.data:
                        st.success("Record added successfully")
                        # Audit log
                        from utils.audit import log_action
                        log_action(user, "CREATE", "convergence_register", result.data[0]['id'], new_vals=record)
                    else:
                        st.error("Failed to save record")
