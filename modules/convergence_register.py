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
    
    UNIT_OPTIONS = [
        "None", "Sq. Meter", "Cu. Meter", "Running Meter", "Kilometer", 
        "Hectare", "Acre", "Number (Nos.)", "Other"
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
        if not user.get('department_id'):
            st.error("🚨 Your user account is missing a Department Assignment. Please contact Superadmin.")
            st.stop()
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
            
        display_cols = ['FY', 'District', 'Block', 'Department', 'activity_description']
        if 'scheme_name' in df_display.columns: display_cols.append('scheme_name')
        if 'geo_location' in df_display.columns: display_cols.append('geo_location')
        
        display_cols.extend(['convergence_type', 'current_status', 'total_converged_fund'])
        
        st.dataframe(df_display[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No records found.")

    # ==========================================
    # 2.5 MANAGE (EDIT/DELETE) SAVED ENTRIES
    # ==========================================
    if role in ['superadmin', 'district'] and records:
        st.markdown("---")
        st.subheader("🛠️ Manage (Edit / Delete) Saved Entries")
        
        with st.expander("✏️ Edit or 🗑️ Delete an Activity", expanded=False):
            display_options = {
                r['id']: f"{r['activity_description']} - {dept_reverse_map.get(r['department_id'], 'Unknown')} (₹{r.get('total_converged_fund', 0)} Lakhs)" 
                for r in records
            }
            
            selected_edit_id = st.selectbox("Select Activity to Manage", options=list(display_options.keys()), format_func=lambda x: display_options[x])
            
            if selected_edit_id:
                rec = next(r for r in records if r['id'] == selected_edit_id)
                
                # Delete Button
                if st.button("🗑️ Permanently Delete Activity", type="primary"):
                    try:
                        supabase.table("convergence_register").delete().eq("id", selected_edit_id).execute()
                        # FIXED: Passed within 2-3 positional arguments limit
                        log_action(user, f"DELETE convergence_register {selected_edit_id}")
                        st.success("Activity deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting record: {e}")
                
                st.markdown("#### Edit Details")
                with st.form("edit_conv_form"):
                    col_e1, col_e2 = st.columns(2)
                    
                    status_opts = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed"]
                    current_status = rec.get('current_status', 'Planned')
                    new_status = col_e1.selectbox("Update Status", status_opts, index=status_opts.index(current_status) if current_status in status_opts else 0)
                    
                    current_conv = rec.get('convergence_type', CONVERGENCE_TYPES[0])
                    new_conv_type = col_e2.selectbox("Convergence Type", CONVERGENCE_TYPES, index=CONVERGENCE_TYPES.index(current_conv) if current_conv in CONVERGENCE_TYPES else 0)
                    
                    # New Detailed Fields
                    st.markdown("##### Detailed Work Specifications")
                    col_det1, col_det2, col_det3, col_det4 = st.columns([2, 2, 1, 1])
                    new_scheme = col_det1.text_input("Scheme Name", value=rec.get('scheme_name', '') or '')
                    new_geo = col_det2.text_input("Geo Location (Village/GP/Lat-Long)", value=rec.get('geo_location', '') or '')
                    new_dim = col_det3.text_input("Dimension Value", value=rec.get('work_dimensions', '') or '')
                    
                    curr_unit = rec.get('dimension_unit', 'None')
                    new_unit = col_det4.selectbox("Unit", UNIT_OPTIONS, index=UNIT_OPTIONS.index(curr_unit) if curr_unit in UNIT_OPTIONS else 0)

                    st.markdown("##### Targets & Financials")
                    col_t1, col_t2 = st.columns(2)
                    new_target = col_t1.number_input("Physical Target", value=int(rec.get('desired_target', 0)))
                    new_pd = col_t2.number_input("Expected Persondays", value=int(rec.get('expected_persondays', 0)))
                    
                    new_d_fund = col_t1.number_input("Department Fund (₹ Lakhs)", value=float(rec.get('department_fund', 0.0)))
                    new_v_fund = col_t2.number_input("VB-G RAM G Fund (₹ Lakhs)", value=float(rec.get('vbgramg_fund', 0.0)))
                    
                    if st.form_submit_button("Update Activity Details"):
                        if new_conv_type == "Technical Convergence (Zero Fund/NOC)":
                            new_d_fund = 0.0
                            new_v_fund = 0.0
                            
                        update_payload = {
                            "current_status": new_status,
                            "convergence_type": new_conv_type,
                            "scheme_name": new_scheme,
                            "geo_location": new_geo,
                            "work_dimensions": new_dim,
                            "dimension_unit": new_unit if new_unit != "None" else None,
                            "desired_target": new_target,
                            "expected_persondays": new_pd,
                            "department_fund": new_d_fund,
                            "vbgramg_fund": new_v_fund
                        }
                        try:
                            supabase.table("convergence_register").update(update_payload).eq("id", selected_edit_id).execute()
                            # FIXED: Passed within 2-3 positional arguments limit
                            log_action(user, f"UPDATE convergence_register {selected_edit_id}")
                            st.success("Activity updated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating record: {e}")

    st.markdown("---")

    # ==========================================
    # 3. MANUAL ENTRY FORM (Dynamic Layout)
    # ==========================================
    with st.expander("➕ Add New Convergence Activity", expanded=True):
        col1, col2 = st.columns(2)
        
        sel_fy = col1.selectbox("Financial Year*", list(fy_map.keys()))
        
        if role == 'department':
            dept_default = next((d['department_name'] for d in depts if d['id'] == user.get('department_id')), None)
            if not dept_default:
                st.error("🚨 Your account is not mapped to any specific department. Please contact the Superadmin.")
                st.stop()
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

        st.markdown("##### Detailed Work Specifications")
        col_det1, col_det2, col_det3, col_det4 = st.columns([2, 2, 1, 1])
        inp_scheme = col_det1.text_input("Scheme Name (Optional)")
        inp_geo = col_det2.text_input("Geo Location (Village/GP/Lat-Long) (Optional)")
        inp_dim = col_det3.text_input("Dimension Value (Optional)", placeholder="e.g. 500")
        inp_unit = col_det4.selectbox("Unit", UNIT_OPTIONS)

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
            vbg_fund = col4.number_input("VB-G RAM G Fund (₹ Lakhs)", min_value=0.0, step=0.1) 

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
                    "scheme_name": inp_scheme,
                    "geo_location": inp_geo,
                    "work_dimensions": inp_dim,
                    "dimension_unit": inp_unit if inp_unit != "None" else None,
                    "desired_target": target,
                    "expected_persondays": persondays,
                    "department_fund": dept_fund,
                    "vbgramg_fund": vbg_fund,
                    "current_status": "Planned"
                }
                
                try:
                    res = supabase.table("convergence_register").insert(insert_data).execute()
                    # FIXED: Passed within 2-3 positional arguments limit
                    log_action(user, f"CREATE convergence_register {res.data[0]['id']}")
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
        * `Scheme Name` (Optional)
        * `Geo Location` (Optional)
        * `Work Dimensions` (Optional)
        * `Dimension Unit` (Optional)
        * `Physical Target`
        * `Expected Persondays`
        * `Department Fund`
        * `VB-G RAM G Fund`
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
                            m_fund = float(row.get('VB-G RAM G Fund', 0)) 
                        
                        insert_data = {
                            "financial_year_id": fy_id,
                            "district_id": dist_id,
                            "block_id": block_id,
                            "department_id": dept_id,
                            "activity_description": target_act['activity_name'],
                            "thematic_category_id": target_act['theme_id'],
                            "convergence_type": conv_str,
                            "scheme_name": str(row.get('Scheme Name', '')).strip(),
                            "geo_location": str(row.get('Geo Location', '')).strip(),
                            "work_dimensions": str(row.get('Work Dimensions', '')).strip(),
                            "dimension_unit": str(row.get('Dimension Unit', '')).strip(),
                            "desired_target": int(row.get('Physical Target', 0)),
                            "expected_persondays": int(row.get('Expected Persondays', 0)),
                            "department_fund": d_fund,
                            "vbgramg_fund": m_fund,
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
