import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def safe_parse_date(date_val):
    """
    Safely parses dates from the database. 
    Returns the exact date if it exists, otherwise returns None to prevent accidental overwrites.
    """
    if pd.isna(date_val) or not date_val:
        return None
    try:
        if isinstance(date_val, str):
            return pd.to_datetime(date_val).date()
        return date_val
    except Exception:
        return None

def inject_custom_css():
    """Injects custom CSS to hide the Streamlit toolbar (Fork/GitHub buttons)."""
    st.markdown("""
        <style>
        .stAppToolbar {
            visibility: hidden !important;
        }
        </style>
        """, unsafe_allow_html=True)

def show():
    # Allow all execution and planning roles
    require_role('superadmin', 'district', 'block', 'department')
    
    inject_custom_css()
    
    st.markdown("<h1 style='color: #1F77B4;'>🚀 Implementation & Target Monitoring</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # ======================== MASTER DATA FETCH ========================
    departments = supabase.table("departments").select("id,department_name").execute().data
    districts = supabase.table("districts").select("id,district_name").execute().data
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data
    
    # Fetch Activities for dynamic dropdowns
    activities = supabase.table("activities").select("*").eq("active", True).execute().data
    act_dept_mapping = supabase.table("activity_departments").select("*").execute().data

    dept_map = {d['id']: d['department_name'] for d in departments}
    dist_map = {d['id']: d['district_name'] for d in districts}
    block_map = {b['id']: b['block_name'] for b in blocks}

    # ======================== TABS LAYOUT ========================
    tab1, tab2, tab3 = st.tabs([
        "🎯 Department Targets (Planning)", 
        "🏗️ Implementation Progress (Execution)", 
        "🤝 Meeting Commitments (Sync)"
    ])

    # =====================================================================
    # TAB 1: DEPARTMENT TARGETS (Annual Planning)
    # =====================================================================
    with tab1:
        st.subheader("Department Targets – FY 2026-27")
        st.caption("Set and view annual physical and financial targets mapped directly to approved activities.")
        
        if role == 'department':
            allowed_dept = user.get('department_id')
            allowed_district = user.get('district_id')
            t_depts = [d for d in departments if d['id'] == allowed_dept]
            t_dists = [d for d in districts if d['id'] == allowed_district]
        elif role == 'district':
            allowed_district = user.get('district_id')
            t_depts = departments
            t_dists = [d for d in districts if d['id'] == allowed_district]
        else: 
            t_depts = departments
            t_dists = districts if role == 'superadmin' else [d for d in districts if d['id'] == user.get('district_id')]

        t_dept_dict = {d['department_name']: d['id'] for d in t_depts}
        t_dist_dict = {d['district_name']: d['id'] for d in t_dists}

        col_t1, col_t2 = st.columns([1.5, 1])
        
        with col_t2:
            st.markdown("#### Add / Update Target")
            if role == 'block':
                st.info("Target setting is managed at the District/Department level. You can view targets on the left.")
            else:
                # Using a container instead of an st.form so the Activity dropdown reacts immediately to Department changes
                with st.container(border=True):
                    if role == 'department':
                        dept_sel = list(t_dept_dict.keys())[0] if t_dept_dict else None
                        dist_sel = list(t_dist_dict.keys())[0] if t_dist_dict else None
                        st.text(f"Department: {dept_sel}")
                        st.text(f"District: {dist_sel}")
                    else:
                        dept_sel = st.selectbox("Department*", list(t_dept_dict.keys()) if t_dept_dict else ["None"])
                        dist_sel = st.selectbox("District*", list(t_dist_dict.keys()) if t_dist_dict else ["None"])

                    # Editable Project Head Logic
                    project_head_options = [
                        "AWC (Anganwadi Center)",
                        "Plantation",
                        "Water Conservation & Harvesting",
                        "Solid/Liquid Waste Management",
                        "Rural Infrastructure",
                        "Livelihood & Agriculture",
                        "Other (Specify Custom)"
                    ]
                    ph_sel = st.selectbox("Convergence Project Head*", project_head_options)
                    
                    if ph_sel == "Other (Specify Custom)":
                        project_head = st.text_input("Type Custom Project Head Name*")
                    else:
                        project_head = ph_sel

                    # Dynamic Activity Dropdown based on Department Selection
                    active_dept_id = t_dept_dict.get(dept_sel) if dept_sel != "None" else None
                    mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == active_dept_id]
                    valid_activities = [a for a in activities if a['id'] in mapped_act_ids]
                    valid_act_names = [a['activity_name'] for a in valid_activities]
                    
                    if not valid_act_names:
                        st.warning(f"No approved activities mapped to {dept_sel}.")
                        activity = st.selectbox("Approved Activity / Work Category*", ["No activities available"], disabled=True)
                    else:
                        activity = st.selectbox("Approved Activity / Work Category*", valid_act_names)

                    col_tf1, col_tf2 = st.columns(2)
                    desired_target = col_tf1.number_input("Desired Target for FY*", min_value=1, value=1)
                    asset_count = col_tf2.number_input("Number of assets/works", min_value=0, value=0)
                    
                    annual_plan_scope = st.text_area("Scope under Annual Plan")
                    
                    col_tf3, col_tf4 = st.columns(2)
                    dept_fund = col_tf3.number_input("Dept Fund (₹ Lakhs)", min_value=0.0, format="%.2f")
                    vbg_fund = col_tf4.number_input("VB-G Fund (₹ Lakhs)", min_value=0.0, format="%.2f")
                    
                    expected_persondays = st.number_input("Expected Persondays*", min_value=0, value=0)

                    st.markdown("<br>", unsafe_allow_html=True)
                    submitted_target = st.button("Save Department Target", type="primary", use_container_width=True)
                    
                    if submitted_target:
                        if dept_sel == "None" or dist_sel == "None":
                            st.error("Invalid Department or District.")
                        elif not project_head or not project_head.strip():
                            st.error("Project Head name cannot be empty.")
                        elif activity == "No activities available":
                            st.error("Cannot save target without a valid approved activity.")
                        elif expected_persondays <= 0:
                            st.error("Expected Persondays is a mandatory field.")
                        else:
                            dept_id = t_dept_dict[dept_sel]
                            dist_id = t_dist_dict[dist_sel]

                            target_record = {
                                "department_id": dept_id,
                                "district_id": dist_id,
                                "financial_year": "2026-27",
                                "project_head": project_head.strip(),
                                "activity": activity,
                                "asset_count": asset_count,
                                "annual_plan_scope": annual_plan_scope,
                                "desired_target": desired_target,
                                "department_fund": dept_fund,
                                "vbgramg_fund": vbg_fund,
                                "expected_persondays": expected_persondays,
                                "created_by": user['id']
                            }

                            try:
                                existing = supabase.table("department_targets").select("id").eq("department_id", dept_id).eq("district_id", dist_id).eq("financial_year", "2026-27").eq("activity", activity).execute().data
                                if existing:
                                    target_id = existing[0]['id']
                                    supabase.table("department_targets").update(target_record).eq("id", target_id).execute()
                                    log_action(user.get('id'), f"UPDATE department_targets {target_id}")
                                    st.success("Target updated successfully!")
                                else:
                                    result = supabase.table("department_targets").insert(target_record).execute()
                                    new_target_id = result.data[0]['id']
                                    log_action(user.get('id'), f"CREATE department_targets {new_target_id}")
                                    st.success("Target added successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving target: {e}")

        with col_t1:
            st.markdown("#### Existing Targets Dashboard")
            query_t = supabase.table("department_targets").select("*")
            if role == 'department':
                query_t = query_t.eq("department_id", user.get('department_id')).eq("district_id", user.get('district_id'))
            elif role in ['district', 'block']:
                query_t = query_t.eq("district_id", user.get('district_id'))
            
            data_t = query_t.execute().data
            if data_t:
                df_t = pd.DataFrame(data_t)
                df_t['Department'] = df_t['department_id'].map(dept_map)
                
                # Check for project head safely (for backward compatibility before column was added)
                if 'project_head' not in df_t.columns:
                    df_t['project_head'] = "N/A"
                
                # Rename for professional display
                df_t.rename(columns={
                    'project_head': 'Project Head',
                    'activity': 'Approved Activity',
                    'desired_target': 'Target',
                    'department_fund': 'Dept. Fund',
                    'vbgramg_fund': 'VB-G Fund',
                    'expected_persondays': 'Persondays'
                }, inplace=True)

                disp_cols = ['Department', 'Project Head', 'Approved Activity', 'Target', 'Dept. Fund', 'VB-G Fund', 'Persondays']
                st.dataframe(df_t[disp_cols], use_container_width=True, hide_index=True)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_t[disp_cols].to_excel(writer, index=False, sheet_name='Targets')
                st.download_button(label="📥 Download Targets Excel", data=buffer.getvalue(), file_name="department_targets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("No targets set yet for your jurisdiction.")

    # =====================================================================
    # TAB 2: IMPLEMENTATION PROGRESS (Field Execution)
    # =====================================================================
    with tab2:
        st.subheader("Physical & Financial Progress Updates")
        st.caption("Update the on-ground reality of specific schemes. MIS Code is mandatory for implementation tracking.")
        
        query_reg = supabase.table("convergence_register").select("*")
        if role == 'district':
            query_reg = query_reg.eq("district_id", user['district_id'])
        elif role == 'block':
            query_reg = query_reg.eq("block_id", user['block_id'])
        elif role == 'department':
            query_reg = query_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

        activities_reg = query_reg.execute().data

        if not activities_reg:
            st.info("No convergence activities found in the register to monitor.")
        else:
            activity_map = {a['id']: f"{a.get('activity_code', a.get('id', ''))} - {a.get('activity_description', 'Unnamed Activity')[:60]}..." for a in activities_reg}

            selected_act_id = st.selectbox("Select Convergence Activity to Update", options=list(activity_map.keys()), format_func=lambda x: activity_map[x])
            selected_activity = next((a for a in activities_reg if a['id'] == selected_act_id), None)

            if selected_activity:
                st.markdown(f"**Current Status:** <span style='color: #E67E22;'>{selected_activity.get('current_status', 'Planned')}</span> | **Source:** <code>{selected_activity.get('origin_source', 'District Plan')}</code>", unsafe_allow_html=True)
                
                with st.form("update_progress_form"):
                    col_p1, col_p2 = st.columns([1, 2])
                    
                    status_options = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed", "Dropped"]
                    current_status = selected_activity.get('current_status', 'Planned')
                    status_idx = status_options.index(current_status) if current_status in status_options else 0
                    
                    new_status = col_p1.selectbox("New Status", status_options, index=status_idx)
                    phys_ach = col_p2.slider("Physical Achievement (%)", min_value=0, max_value=100, value=int(float(selected_activity.get('physical_achievement', 0.0) or 0.0)))
                    
                    st.markdown("##### Financials & MIS Registration")
                    col_p3, col_p4 = st.columns(2)
                    
                    mis_code_val = col_p3.text_input("MIS Code (e.g. 3206011003/RS...)", value=selected_activity.get('mis_code', '') or '')
                    fin_ach = col_p4.number_input("Financial Achievement (₹ Lakhs)", min_value=0.0, value=float(selected_activity.get('financial_achievement', 0.0) or 0.0))
                    
                    persondays_gen = st.number_input("Persondays Generated (Cumulative)", min_value=0, value=int(selected_activity.get('persondays_generated', 0) or 0))

                    col_p5, col_p6, col_p7 = st.columns(3)
                    
                    db_start = safe_parse_date(selected_activity.get('actual_start_date'))
                    db_exp = safe_parse_date(selected_activity.get('expected_completion_date'))
                    db_act = safe_parse_date(selected_activity.get('actual_completion_date'))

                    start_date = col_p5.date_input("Actual Start Date", value=db_start)
                    exp_date = col_p6.date_input("Expected Completion", value=db_exp)
                    act_date = col_p7.date_input("Actual Completion (If done)", value=db_act)

                    remarks = st.text_area("Remarks / Blockages", value=selected_activity.get('remarks', '') or '')

                    submitted_prog = st.form_submit_button("Save Progress", type="primary", use_container_width=True)
                    
                    if submitted_prog:
                        if new_status in ["Under Implementation", "Completed"] and not mis_code_val.strip():
                            st.error("⚠️ **Validation Error:** MIS Code is strictly mandatory when moving a scheme to 'Under Implementation' or 'Completed'. Please enter the valid MIS Code from the central portal to proceed.")
                        else:
                            update_data = {
                                "current_status": new_status,
                                "mis_code": mis_code_val.strip() if mis_code_val else None,
                                "physical_achievement": phys_ach,
                                "financial_achievement": fin_ach,
                                "persondays_generated": persondays_gen,
                                "actual_start_date": str(start_date) if start_date else None,
                                "expected_completion_date": str(exp_date) if exp_date else None,
                                "actual_completion_date": str(act_date) if act_date else None,
                                "remarks": remarks
                            }
                            
                            try:
                                supabase.table("convergence_register").update(update_data).eq("id", selected_act_id).execute()
                                
                                history_payload = {
                                    "convergence_id": selected_act_id,
                                    "status": new_status,
                                    "physical_achievement": phys_ach,
                                    "financial_achievement": fin_ach,
                                    "persondays_generated": persondays_gen,
                                    "remarks": f"MIS Code: {mis_code_val} | {remarks}"
                                }
                                supabase.table("progress_updates").insert(history_payload).execute()
                                
                                log_action(user.get('id'), f"UPDATE convergence_register {selected_act_id}")
                                
                                st.success("✅ Progress and MIS mapping updated successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving progress: {e}")

                st.markdown("#### Progress History Timeline")
                try:
                    history_query = supabase.table("progress_updates").select("*").eq("convergence_id", selected_act_id).order("created_at", desc=True).execute()
                    if history_query.data:
                        df_history = pd.DataFrame(history_query.data)
                        df_history['Date'] = pd.to_datetime(df_history['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                        st.dataframe(df_history[['Date', 'status', 'physical_achievement', 'financial_achievement', 'persondays_generated', 'remarks']], use_container_width=True, hide_index=True)
                    else:
                        st.info("No historical updates recorded for this activity yet.")
                except Exception:
                    st.warning("Could not load history timeline.")

    # =====================================================================
    # TAB 3: MEETING COMMITMENTS (Sync with Meetings Module)
    # =====================================================================
    with tab3:
        st.subheader("🤝 Departmental Meeting Commitments")
        st.caption("View and fulfill the Action Points assigned to your department across all District and Block meetings.")

        ap_query = supabase.table("meeting_action_points").select("id, meeting_id, department_id, priority, linkage_type, action_point, target, deadline, status, remarks").execute().data
        
        if ap_query:
            df_ap = pd.DataFrame(ap_query)
            
            # Filter based on department role
            if role == 'department':
                df_ap = df_ap[df_ap['department_id'] == user.get('department_id')]

            if not df_ap.empty:
                df_ap['Department'] = df_ap['department_id'].map(dept_map)
                
                meetings_data = supabase.table("meetings").select("id, meeting_date, meeting_type").execute().data
                m_map = {m['id']: m for m in meetings_data}
                
                df_ap['Meeting Context'] = df_ap['meeting_id'].map(lambda x: f"{m_map.get(x, {}).get('meeting_type', 'Unknown')} Level ({m_map.get(x, {}).get('meeting_date', 'Unknown')})")
                
                pending_ap = df_ap[~df_ap['status'].isin(['Completed', 'Dropped'])].copy()
                
                if not pending_ap.empty:
                    pending_ap['deadline'] = pd.to_datetime(pending_ap['deadline'])
                    pending_ap['Days Left'] = (pending_ap['deadline'] - pd.to_datetime(date.today())).dt.days
                    pending_ap['Linkage'] = pending_ap.get('linkage_type', 'Normative / Routine')
                    
                    st.markdown("#### Pending Actions & Meeting Origins")
                    disp_cols = ['Meeting Context', 'Department', 'action_point', 'target', 'Linkage', 'Days Left', 'status']
                    st.dataframe(pending_ap[disp_cols].sort_values('Days Left'), use_container_width=True, hide_index=True)
                    
                    st.markdown("#### Update Commitment Status")
                    with st.form("sync_atr_form"):
                        col_s1, col_s2 = st.columns(2)
                        
                        sync_id = col_s1.selectbox("Select Resolution ID", pending_ap['id'].tolist(), format_func=lambda x: f"[{pending_ap[pending_ap['id']==x]['Meeting Context'].values[0]}] {pending_ap[pending_ap['id']==x]['action_point'].values[0][:40]}...")
                        
                        sync_status = col_s2.selectbox("New Status", ['Under Process', 'Approved', 'Under Execution', 'Completed', 'Not Feasible (Requires Review)', 'Dropped'])
                        sync_remarks = st.text_area("Implementation Outcome / Remarks (If Not Feasible, state the reason clearly)")
                        
                        submitted_sync = st.form_submit_button("Sync Progress to Meeting Tracker")
                        
                        if submitted_sync:
                            if sync_status == 'Not Feasible (Requires Review)' and not sync_remarks.strip():
                                st.error("⚠️ **Validation Error:** You must provide a clear reason in 'Remarks' when flagging an activity as Not Feasible so the Chairperson can review it.")
                            else:
                                payload = {"status": sync_status, "remarks": sync_remarks}
                                supabase.table("meeting_action_points").update(payload).eq("id", sync_id).execute()
                                
                                log_action(user.get('id'), f"UPDATE meeting_action_points {sync_id}")
                                
                                st.success("✅ Meeting ATR Updated! If flagged as Not Feasible, it has been added to the next meeting's agenda.")
                                st.rerun()
                else:
                    st.success("🎉 All meeting commitments have been completed or closed!")
            else:
                st.info("No meeting commitments found for your department.")
        else:
            st.info("No resolutions found in the system.")
