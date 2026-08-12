import streamlit as st
import pandas as pd
from datetime import date
import io
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    # Allow all execution and planning roles
    require_role('superadmin', 'district', 'block', 'department')
    
    st.markdown("<h1 style='color: #1F77B4;'>🚀 Implementation & Target Monitoring</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # ======================== MASTER DATA FETCH ========================
    departments = supabase.table("departments").select("id,department_name").execute().data
    districts = supabase.table("districts").select("id,district_name").execute().data
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data

    dept_map = {d['id']: d['department_name'] for d in departments}
    dist_map = {d['id']: d['district_name'] for d in districts}
    block_map = {b['id']: b['block_name'] for b in blocks}

    # ======================== TABS LAYOUT ========================
    tab1, tab2, tab3 = st.tabs([
        "🎯 1. Department Targets (Planning)", 
        "🏗️ 2. Implementation Progress (Execution)", 
        "🤝 3. Meeting Commitments (Sync)"
    ])

    # =====================================================================
    # TAB 1: DEPARTMENT TARGETS (Annual Planning)
    # =====================================================================
    with tab1:
        st.subheader("Department Targets – FY 2026-27")
        st.caption("Set and view annual physical and financial targets.")
        
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
                with st.form("target_form"):
                    if role == 'department':
                        dept_sel = list(t_dept_dict.keys())[0] if t_dept_dict else None
                        dist_sel = list(t_dist_dict.keys())[0] if t_dist_dict else None
                        st.text(f"Department: {dept_sel}")
                        st.text(f"District: {dist_sel}")
                    else:
                        dept_sel = st.selectbox("Department", list(t_dept_dict.keys()) if t_dept_dict else ["None"])
                        dist_sel = st.selectbox("District", list(t_dist_dict.keys()) if t_dist_dict else ["None"])

                    activity = st.text_input("Activity (optional)")
                    col_tf1, col_tf2 = st.columns(2)
                    desired_target = col_tf1.number_input("Desired Target for FY", min_value=0, value=0)
                    asset_count = col_tf2.number_input("Number of assets/works", min_value=0, value=0)
                    
                    annual_plan_scope = st.text_area("Scope under Annual Plan")
                    
                    col_tf3, col_tf4 = st.columns(2)
                    dept_fund = col_tf3.number_input("Dept Fund (₹ Lakhs)", min_value=0.0, format="%.2f")
                    vbg_fund = col_tf4.number_input("VB-G Fund (₹ Lakhs)", min_value=0.0, format="%.2f")
                    
                    expected_persondays = st.number_input("Expected Persondays", min_value=0, value=0)

                    submitted_target = st.form_submit_button("Save Target", type="primary", use_container_width=True)
                    if submitted_target and dept_sel != "None" and dist_sel != "None":
                        dept_id = t_dept_dict[dept_sel]
                        dist_id = t_dist_dict[dist_sel]

                        target_record = {
                            "department_id": dept_id,
                            "district_id": dist_id,
                            "financial_year": "2026-27",
                            "activity": activity,
                            "asset_count": asset_count,
                            "annual_plan_scope": annual_plan_scope,
                            "desired_target": desired_target,
                            "department_fund": dept_fund,
                            "vbgramg_fund": vbg_fund,
                            "expected_persondays": expected_persondays,
                            "created_by": user['id']
                        }

                        existing = supabase.table("department_targets").select("id").eq("department_id", dept_id).eq("district_id", dist_id).eq("financial_year", "2026-27").eq("activity", activity).execute().data
                        if existing:
                            supabase.table("department_targets").update(target_record).eq("id", existing[0]['id']).execute()
                            log_action(user, "UPDATE", "department_targets", existing[0]['id'], details=target_record)
                            st.success("Target updated!")
                        else:
                            result = supabase.table("department_targets").insert(target_record).execute()
                            log_action(user, "CREATE", "department_targets", result.data[0]['id'], details=target_record)
                            st.success("Target added!")
                        st.rerun()

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
                disp_cols = ['Department', 'activity', 'desired_target', 'department_fund', 'vbgramg_fund', 'expected_persondays']
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

        activities = query_reg.execute().data

        if not activities:
            st.info("No convergence activities found in the register to monitor.")
        else:
            activity_map = {a['id']: f"{a.get('activity_code', a.get('id', ''))} - {a.get('activity_description', 'Unnamed Activity')[:60]}..." for a in activities}

            selected_act_id = st.selectbox("Select Convergence Activity to Update", options=list(activity_map.keys()), format_func=lambda x: activity_map[x])
            selected_activity = next((a for a in activities if a['id'] == selected_act_id), None)

            if selected_activity:
                st.markdown(f"**Current Status:** `<span style='color: #E67E22;'>{selected_activity.get('current_status', 'Planned')}</span>` | **Source:** `{selected_activity.get('origin_source', 'Normative / Routine')}`", unsafe_allow_html=True)
                
                with st.form("update_progress_form"):
                    col_p1, col_p2 = st.columns([1, 2])
                    
                    status_options = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed", "Dropped"]
                    current_status = selected_activity.get('current_status', 'Planned')
                    status_idx = status_options.index(current_status) if current_status in status_options else 0
                    
                    new_status = col_p1.selectbox("New Status", status_options, index=status_idx)
                    phys_ach = col_p2.slider("Physical Achievement (%)", min_value=0, max_value=100, value=int(float(selected_activity.get('physical_achievement', 0.0) or 0.0)))
                    
                    st.markdown("##### Financials & MIS Registration")
                    col_p3, col_p4 = st.columns(2)
                    
                    # NEW: MIS CODE INPUT
                    mis_code_val = col_p3.text_input("MIS Code (e.g. 3206011003/RS/YD/3210020...)", value=selected_activity.get('mis_code', '') or '')
                    fin_ach = col_p4.number_input("Financial Achievement (₹ Lakhs)", min_value=0.0, value=float(selected_activity.get('financial_achievement', 0.0) or 0.0))
                    
                    persondays_gen = st.number_input("Persondays Generated (Cumulative)", min_value=0, value=int(selected_activity.get('persondays_generated', 0) or 0))

                    col_p5, col_p6, col_p7 = st.columns(3)
                    start_date = col_p5.date_input("Actual Start Date", value=date.today())
                    exp_date = col_p6.date_input("Expected Completion", value=date.today())
                    act_date = col_p7.date_input("Actual Completion (If done)", value=None)

                    remarks = st.text_area("Remarks / Blockages", value=selected_activity.get('remarks', '') or '')

                    submitted_prog = st.form_submit_button("Save Progress", type="primary", use_container_width=True)
                    
                    if submitted_prog:
                        # MANDATORY MIS CODE VALIDATION FOR IMPLEMENTATION
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
                                log_action(user, "UPDATE", "convergence_register", selected_act_id, details=update_data)
                                
                                st.success("✅ Progress and MIS mapping updated successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving progress: {e}")

                # History Viewer
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
        st.caption("Fulfill the Action Points promised in District & Block Convergence Meetings.")

        # Fetch resolutions relevant to this user
        ap_query = supabase.table("meeting_action_points").select("id, meeting_id, department_id, priority, linkage_type, action_point, target, deadline, status, remarks").execute().data
        
        if ap_query:
            df_ap = pd.DataFrame(ap_query)
            
            if role == 'department':
                df_ap = df_ap[df_ap['department_id'] == user.get('department_id')]

            if not df_ap.empty:
                df_ap['Department'] = df_ap['department_id'].map(dept_map)
                
                meetings_data = supabase.table("meetings").select("id, meeting_date, meeting_type").execute().data
                m_map = {m['id']: m for m in meetings_data}
                
                df_ap['Meeting Date'] = df_ap['meeting_id'].map(lambda x: m_map.get(x, {}).get('meeting_date', 'Unknown'))
                df_ap['Level'] = df_ap['meeting_id'].map(lambda x: m_map.get(x, {}).get('meeting_type', 'Unknown'))
                
                pending_ap = df_ap[~df_ap['status'].isin(['Completed', 'Dropped'])].copy()
                
                if not pending_ap.empty:
                    pending_ap['deadline'] = pd.to_datetime(pending_ap['deadline'])
                    pending_ap['Days Left'] = (pending_ap['deadline'] - pd.to_datetime(date.today())).dt.days
                    
                    # Provide visual context to the linkage type
                    pending_ap['Linkage'] = pending_ap.get('linkage_type', 'Normative / Routine')
                    
                    st.markdown("#### Pending Actions & Origination")
                    disp_cols = ['Level', 'Meeting Date', 'Department', 'action_point', 'target', 'Linkage', 'Days Left', 'status']
                    st.dataframe(pending_ap[disp_cols].sort_values('Days Left'), use_container_width=True, hide_index=True)
                    
                    st.markdown("#### Update Commitment Status")
                    with st.form("sync_atr_form"):
                        col_s1, col_s2 = st.columns(2)
                        sync_id = col_s1.selectbox("Select Resolution ID", pending_ap['id'].tolist(), format_func=lambda x: f"[{pending_ap[pending_ap['id']==x]['Level'].values[0]}] {pending_ap[pending_ap['id']==x]['action_point'].values[0][:40]}...")
                        sync_status = col_s2.selectbox("New Status", ['Under Process', 'Approved', 'Under Execution', 'Completed', 'Dropped'])
                        sync_remarks = st.text_area("Implementation Outcome / Remarks (Updates the Meeting ATR directly)")
                        
                        if st.form_submit_button("Sync Progress to Meeting Tracker"):
                            payload = {"status": sync_status, "remarks": sync_remarks}
                            supabase.table("meeting_action_points").update(payload).eq("id", sync_id).execute()
                            log_action(user, "UPDATE", "meeting_action_points", sync_id, details=payload)
                            st.success("✅ Meeting ATR Updated Successfully!")
                            st.rerun()
                else:
                    st.success("🎉 All meeting commitments have been completed or closed!")
            else:
                st.info("No meeting commitments found for your department.")
        else:
            st.info("No resolutions found in the system.")
