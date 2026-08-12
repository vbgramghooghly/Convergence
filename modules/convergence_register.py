import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block', 'department')
    
    st.title("Convergence Register")
    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # ==========================================
    # 1. FETCH MASTER DATA FOR LOOKUPS & MAPPING
    # ==========================================
    fys = supabase.table("financial_years").select("*").eq("active", True).execute().data
    districts = supabase.table("districts").select("*").eq("active", True).execute().data
    blocks = supabase.table("blocks").select("*").eq("active", True).execute().data
    depts = supabase.table("departments").select("*").eq("active", True).execute().data
    themes = supabase.table("themes").select("*").eq("active", True).execute().data
    
    activities = supabase.table("activities").select("*").eq("active", True).execute().data
    act_dept_mapping = supabase.table("activity_departments").select("*").execute().data

    # Forward maps (Name -> ID) for Forms
    fy_map = {f['year_name']: f['id'] for f in fys}
    dist_map = {d['district_name']: d['id'] for d in districts}
    block_map = {b['block_name']: b['id'] for b in blocks}
    dept_map = {d['department_name']: d['id'] for d in depts}
    theme_map_id_to_name = {t['id']: t['theme_name'] for t in themes}
    
    # Reverse maps (ID -> Name) for Displaying the Dataframe safely
    fy_reverse_map = {f['id']: f['year_name'] for f in fys}
    dist_reverse_map = {d['id']: d['district_name'] for d in districts}
    block_reverse_map = {b['id']: b['block_name'] for b in blocks}
    dept_reverse_map = {d['id']: d['department_name'] for d in depts}

    CONVERGENCE_TYPES = [
        "Technical Convergence (Zero Fund/NOC)",
        "Financial (as PIA)",
        "Financial (as Non-PIA)"
    ]

    # ==========================================
    # 2. VIEW EXISTING RECORDS
    # ==========================================
    query = supabase.table("convergence_register").select("*")
    
    if role == 'district':
        query = query.eq("district_id", user['district_id'])
    elif role == 'block':
        query = query.eq("block_id", user['block_id'])
    elif role == 'department':
        query = query.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    try:
        records = query.execute().data
    except Exception as e:
        st.error(f"Database error while fetching records: {e}")
        records = []

    st.subheader(f"Convergence Activities ({len(records)} records)")
    
    if records:
        df_display = pd.DataFrame(records)
        
        df_display['FY'] = df_display['financial_year_id'].map(fy_reverse_map)
        df_display['District'] = df_display['district_id'].map(dist_reverse_map)
        df_display['Block'] = df_display['block_id'].map(block_reverse_map)
        df_display['Department'] = df_display['department_id'].map(dept_reverse_map)
        
        if 'convergence_type' not in df_display.columns:
            df_display['convergence_type'] = "Not Specified"
            
        display_cols = ['FY', 'District', 'Block', 'Department', 'activity_description', 'convergence_type', 'current_status', 'total_converged_fund']
        
        st.dataframe(df_display[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No records found.")

    st.markdown("---")

    # ==========================================
    # 3. MANUAL ENTRY FORM (Dynamic Layout, No Form Wrapper)
    # ==========================================
    with st.expander("➕ Add New Convergence Activity", expanded=True):
        col1, col2 = st.columns(2)
        
        sel_fy = col1.selectbox("Financial Year*", list(fy_map.keys()))
        
        if role == 'department':
            dept_default = next(d['department_name'] for d in depts if d['id'] == user['department_id'])
            sel_dept = col2.selectbox("Department*", [dept_default], disabled=True)
        else:
            sel_dept = col2.selectbox("Department*", list(dept_map.keys()))
            
        selected_dept_id = dept_map.get(sel_dept)

        if role in ['block', 'district', 'department']:
            dist_default = next(d['district_name'] for d in districts if d['id'] == user['district_id'])
            sel_dist = col1.selectbox("District*", [dist_default], disabled=True)
        else:
            sel_dist = col1.selectbox("District*", list(dist_map.keys()))
            
        selected_dist_id = dist_map.get(sel_dist)
        
        filtered_blocks = [b['block_name'] for b in blocks if b['district_id'] == selected_dist_id]
        if role == 'block':
            block_default = next(b['block_name'] for b in blocks if b['id'] == user['block_id'])
            sel_block = col2.selectbox("Block*", [block_default], disabled=True)
        else:
            sel_block = col2.selectbox("Block (Optional)", ["None"] + filtered_blocks)

        st.markdown("##### Activity & Convergence Type")
        
        # Dynamic filtering happens here instantly now
        mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == selected_dept_id]
        valid_activities = [a for a in activities if a['id'] in mapped_act_ids]
        valid_act_names = [a['activity_name'] for a in valid_activities]
        
        col_act1, col_act2 = st.columns(2)
        
        if not valid_act_names:
            st.warning(f"No approved activities found for {sel_dept}.")
            sel_act_name = col_act1.selectbox("Activity / Work Description*", ["No activities available"], disabled=True)
            selected_theme_name = "None"
            theme_id = None
        else:
            sel_act_name = col_act1.selectbox("Activity / Work Description*", valid_act_names)
            selected_act_record = next((a for a in valid_activities if a['activity_name'] == sel_act_name), None)
            theme_id = selected_act_record['theme_id'] if selected_act_record else None
            selected_theme_name = theme_map_id_to_name.get(theme_id, "Unassigned")
        
        col_act2.text_input("Thematic Category (Auto-filled)", value=selected_theme_name, disabled=True)
        
        sel_conv_type = st.selectbox("Type of Convergence*", CONVERGENCE_TYPES)

        st.markdown("##### Targets & Financials")
        col3, col4 = st.columns(2)
        target = col3.number_input("Physical Target (Number)", min_value=0)
        persondays = col4.number_input("Expected Persondays", min_value=0)
        
        if sel_conv_type == "Technical Convergence (Zero Fund/NOC)":
            st.info("ℹ️ Technical Convergence selected: Fund involvement is automatically set to zero.")
            dept_fund = 0.0
            vbg_fund = 0.0
        else:
            dept_fund = col3.number_input("Department Fund (₹ Lakhs)", min_value=0.0, step=0.1)
            vbg_fund = col4.number_input("MGNREGS Fund (₹ Lakhs)", min_value=0.0, step=0.1)

        # Changed to a standard button since we are no longer in an st.form
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.button("Save Convergence Activity", type="primary", use_container_width=True)
        
        if submitted:
            if not valid_act_names:
                st.error("Cannot save without a valid approved activity.")
            else:
                block_id = block_map.get(sel_block) if sel_block != "None" else None
                
                insert_data = {
                    "financial_year_id": fy_map[sel_fy],
                    "district_id": selected_dist_id,
                    "block_id": block_id,
                    "department_id": selected_dept_id,
                    "activity_description": sel_act_name, 
                    "thematic_category_id": theme_id,
                    "convergence_type": sel_conv_type,
                    "desired_target": target,
                    "expected_persondays": persondays,
                    "department_fund": dept_fund,
                    "vbgramg_fund": vbg_fund,
                    "total_converged_fund": dept_fund + vbg_fund,
                    "current_status": "Planned"
                }
                
                try:
                    res = supabase.table("convergence_register").insert(insert_data).execute()
                    log_action(user, "CREATE", "convergence_register", res.data[0]['id'], new_vals=insert_data)
                    st.success("Activity recorded successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving record: {e}")

    # ==========================================
    # 4. BULK UPLOAD MODULE
    # ==========================================
    st.markdown("---")
    st.subheader("📂 Bulk Upload Activities")
    st.caption("Upload a CSV file to create multiple convergence entries at once. **Only approved activities for the specified department will be accepted.**")
    
    with st.expander("View CSV Template Requirements"):
        st.markdown("""
        Your CSV must contain exact matches for the following column headers:
        * `Financial Year` (e.g., 2026-27)
        * `District`
        * `Block` (Leave blank or write 'None')
        * `Department` 
        * `Activity` 
        * `Convergence Type` (Must be: 'Technical Convergence (Zero Fund/NOC)', 'Financial (as PIA)', or 'Financial (as Non-PIA)')
        * `Physical Target`
        * `Expected Persondays`
        * `Department Fund` (Will be ignored if Technical Convergence)
        * `MGNREGS Fund` (Will be ignored if Technical Convergence)
        """)

    uploaded_file = st.file_uploader("Upload CSV", type="csv")
    
    if uploaded_file:
        df_upload = pd.read_csv(uploaded_file)
        st.write("Preview of Uploaded Data:")
        st.dataframe(df_upload.head(3), use_container_width=True)
        
        if st.button("Validate & Import Data", type="primary"):
            success_count = 0
            error_log = []
            
            with st.spinner("Processing records..."):
                for index, row in df_upload.iterrows():
                    try:
                        fy_str = str(row.get('Financial Year', '')).strip()
                        dist_str = str(row.get('District', '')).strip()
                        block_str = str(row.get('Block', 'None')).strip()
                        dept_str = str(row.get('Department', '')).strip()
                        act_str = str(row.get('Activity', '')).strip()
                        conv_str = str(row.get('Convergence Type', '')).strip()
                        
                        fy_id = fy_map.get(fy_str)
                        dist_id = dist_map.get(dist_str)
                        block_id = block_map.get(block_str) if block_str and block_str.lower() != 'none' else None
                        dept_id = dept_map.get(dept_str)
                        
                        if not all([fy_id, dist_id, dept_id]):
                            error_log.append(f"Row {index+2}: Invalid Master Data references.")
                            continue
                            
                        if conv_str not in CONVERGENCE_TYPES:
                            error_log.append(f"Row {index+2}: Invalid Convergence Type. Must match template exactly.")
                            continue

                        mapped_acts = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == dept_id]
                        valid_acts_for_dept = [a for a in activities if a['id'] in mapped_acts]
                        target_act = next((a for a in valid_acts_for_dept if a['activity_name'].lower() == act_str.lower()), None)
                        
                        if not target_act:
                            error_log.append(f"Row {index+2}: Activity '{act_str}' is NOT approved for {dept_str}.")
                            continue
                            
                        if conv_str == "Technical Convergence (Zero Fund/NOC)":
                            d_fund = 0.0
                            m_fund = 0.0
                        else:
                            d_fund = float(row.get('Department Fund', 0))
                            m_fund = float(row.get('MGNREGS Fund', 0))
                        
                        insert_data = {
                            "financial_year_id": fy_id,
                            "district_id": dist_id,
                            "block_id": block_id,
                            "department_id": dept_id,
                            "activity_description": target_act['activity_name'],
                            "thematic_category_id": target_act['theme_id'],
                            "convergence_type": conv_str,
                            "desired_target": int(row.get('Physical Target', 0)),
                            "expected_persondays": int(row.get('Expected Persondays', 0)),
                            "department_fund": d_fund,
                            "vbgramg_fund": m_fund,
                            "total_converged_fund": d_fund + m_fund,
                            "current_status": "Planned"
                        }
                        
                        supabase.table("convergence_register").insert(insert_data).execute()
                        success_count += 1
                        
                    except Exception as e:
                        error_log.append(f"Row {index+2}: Failed to process due to error: {str(e)}")
            
            if success_count > 0:
                st.success(f"Successfully imported {success_count} activities!")
            
            if error_log:
                st.error(f"{len(error_log)} rows failed validation and were skipped.")
                with st.expander("View Error Details"):
                    for err in error_log:
                        st.write(err)
            
            if success_count > 0 and not error_log:
                st.rerun()
