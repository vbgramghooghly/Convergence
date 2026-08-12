import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin')  # Only superadmin can access
    st.title("Master Data Management")

    supabase = get_supabase()
    user = get_current_user()

    # Available master tables
    tables = {
        "Districts": {"table": "districts", "columns": ["id","district_name","district_code","active"]},
        "Blocks": {"table": "blocks", "columns": ["id","district_id","block_name","block_code","active"]},
        "Departments": {"table": "departments", "columns": ["id","department_name","department_code","nodal_officer","active"]},
        "Themes": {"table": "themes", "columns": ["id","theme_name","description","active"]},
        "Activities": {"table": "activities", "columns": ["id","department_id","theme_id","activity_name","description","vbgramg_permissible","active"]},
        "Financial Years": {"table": "financial_years", "columns": ["id","fy_label","active"]}
    }

    tab_names = list(tables.keys())
    tabs = st.tabs(tab_names)

    for i, entity in enumerate(tab_names):
        with tabs[i]:
            st.subheader(f"Manage {entity}")
            table_info = tables[entity]

            # Fetch existing data
            data = supabase.table(table_info["table"]).select("*").execute().data
            df = pd.DataFrame(data)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No records found.")

            st.divider()
            st.subheader("Add New Record")
            with st.form(key=f"add_{entity}"):
                new_record = {}
                if entity == "Districts":
                    new_record["district_name"] = st.text_input("District Name")
                    new_record["district_code"] = st.text_input("District Code")
                elif entity == "Blocks":
                    # Populate district dropdown from database
                    districts_data = supabase.table("districts").select("id,district_name").execute().data
                    district_dict = {d['district_name']: d['id'] for d in districts_data}
                    new_record["district_id"] = st.selectbox("District", options=list(district_dict.keys()),
                                                              format_func=lambda x: x)
                    new_record["block_name"] = st.text_input("Block Name")
                    new_record["block_code"] = st.text_input("Block Code")
                elif entity == "Departments":
                    new_record["department_name"] = st.text_input("Department Name")
                    new_record["department_code"] = st.text_input("Department Code")
                    new_record["nodal_officer"] = st.text_input("Nodal Officer")
                elif entity == "Themes":
                    new_record["theme_name"] = st.text_input("Theme Name")
                    new_record["description"] = st.text_area("Description")
                elif entity == "Activities":
                    dept_data = supabase.table("departments").select("id,department_name").execute().data
                    dept_dict = {d['department_name']: d['id'] for d in dept_data}
                    theme_data = supabase.table("themes").select("id,theme_name").execute().data
                    theme_dict = {t['theme_name']: t['id'] for t in theme_data}
                    new_record["department_id"] = st.selectbox("Department", options=list(dept_dict.keys()), format_func=lambda x: x)
                    new_record["theme_id"] = st.selectbox("Theme", options=list(theme_dict.keys()), format_func=lambda x: x)
                    new_record["activity_name"] = st.text_input("Activity Name")
                    new_record["description"] = st.text_area("Description")
                    new_record["vbgramg_permissible"] = st.checkbox("Permissible under VB-G RAM G?")
                elif entity == "Financial Years":
                    new_record["fy_label"] = st.text_input("FY Label (e.g. 2026-27)")

                submitted = st.form_submit_button("Save")
                if submitted:
                    # Convert dropdown selections to IDs if applicable
                    if entity == "Blocks":
                        new_record["district_id"] = district_dict[new_record["district_id"]]
                    elif entity == "Activities":
                        new_record["department_id"] = dept_dict[new_record["department_id"]]
                        new_record["theme_id"] = theme_dict[new_record["theme_id"]]
                    # Insert
                    result = supabase.table(table_info["table"]).insert(new_record).execute()
                    if result.data:
                        st.success(f"{entity} record added successfully!")
                        log_action(user, "CREATE", table_info["table"], result.data[0]['id'], new_vals=new_record)
                        st.rerun()
                    else:
                        st.error("Failed to add record.")

            # Soft delete / deactivate record
            st.subheader("Deactivate Record")
            if not df.empty:
                record_ids = df['id'].tolist()
                del_id = st.selectbox(f"Select {entity} ID to deactivate", record_ids, key=f"del_{entity}")
                if st.button(f"Deactivate {entity}", key=f"deact_{entity}"):
                    supabase.table(table_info["table"]).update({"active": False}).eq("id", del_id).execute()
                    log_action(user, "DEACTIVATE", table_info["table"], del_id, old_vals={"active":True}, new_vals={"active":False})
                    st.success(f"Record {del_id} deactivated.")
                    st.rerun()
