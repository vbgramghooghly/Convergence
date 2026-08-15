import streamlit as st
import pandas as pd
from datetime import date
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def safe_parse_date(date_val):
    if pd.isna(date_val) or not date_val: return None
    try:
        if isinstance(date_val, str): return pd.to_datetime(date_val).date()
        return date_val
    except Exception:
        return None

def show():
    require_role('superadmin', 'district', 'block', 'department')
    
    # --- PAGE HEADER ---
    st.markdown("<h2 style='margin-bottom: 0px;'>🚀 Progress & Target Monitoring</h2>", unsafe_allow_html=True)
    st.caption("Manage Annual Targets, Execution Progress, and Sync Meeting Action Points.")

    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # Master Data
    departments = supabase.table("departments").select("id,department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name").execute().data or []
    districts = supabase.table("districts").select("id,district_name").execute().data or []
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data or []
    activities = supabase.table("activities").select("*").eq("active", True).execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("*").execute().data or []

    dept_map = {d['id']: d['department_name'] for d in departments}
    wing_map = {w['id']: w for w in wings}
    t_dist_dict = {d['district_name']: d['id'] for d in (districts if role in ['superadmin', 'district'] else [d for d in districts if d['id'] == user.get('district_id')])}

    # --- SECONDARY NAVIGATION (SLIM TABS) ---
    tab1, tab2, tab3 = st.tabs(["🎯 Department Targets", "🏗️ Implementation Progress", "🤝 Meeting Commitments"])

    with tab1:
        col_t1, col_t2 = st.columns([1.5, 1])
        
        with col_t2:
            st.markdown("#### Set Target")
            if role == 'block':
                st.info("Target setting is managed at the District/Department level.")
            else:
                with st.container(border=True):
                    active_dept_id, active_wing_id, dist_id = None, None, None

                    if role == 'department':
                        active_dept_id = user.get('department_id')
                        active_wing_id = user.get('wing_id')
                        dept_name = dept_map.get(active_dept_id, "Unknown")
                        display_text = f"{dept_name} ➔ {wing_map[active_wing_id]['wing_name']}" if active_wing_id and active_wing_id in wing_map else f"{dept_name} (Main)"
                        
                        st.markdown(f"**Department:** {display_text}")
                        dist_sel = list(t_dist_dict.keys())[0] if t_dist_dict else None
                        dist_id = user.get('district_id')
                    else:
                        dept_opts = [{"label": f"{d['department_name']} (Main)", "dept_id": d['id'], "wing_id": None} for d in departments]
                        dept_opts += [{"label": f"{dept_map.get(w['department_id'], 'Unknown')} ➔ {w['wing_name']}", "dept_id": w['department_id'], "wing_id": w['id']} for w in wings]
                        dept_opts = sorted(dept_opts, key=lambda x: x['label'])
                        
                        sel_dept_label = st.selectbox("Department / Wing*", [opt['label'] for opt in dept_opts])
                        selected_opt = next(opt for opt in dept_opts if opt['label'] == sel_dept_label)
                        active_dept_id, active_wing_id = selected_opt['dept_id'], selected_opt['wing_id']
                        
                        dist_sel = st.selectbox("District*", list(t_dist_dict.keys()) if t_dist_dict else ["None"])
                        dist_id = t_dist_dict.get(dist_sel)

                    ph_options = ["AWC", "Plantation", "Water Conservation", "Solid/Liquid Waste", "Rural Infrastructure", "Livelihood", "Other"]
                    ph_sel = st.selectbox("Project Head*", ph_options)
                    project_head = st.text_input("Custom Head*") if ph_sel == "Other" else ph_sel

                    mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == active_dept_id]
                    valid_act_names = [a['activity_name'] for a in activities if a['id'] in mapped_act_ids]
                    
                    activity = st.selectbox("Approved Activity*", valid_act_names) if valid_act_names else st.selectbox("Approved Activity*", ["No activities available"], disabled=True)

                    col_tf1, col_tf2 = st.columns(2)
                    desired_target = col_tf1.number_input("Target Count*", min_value=1, value=1)
                    asset_count = col_tf2.number_input("Asset Count", min_value=0, value=0)
                    
                    annual_plan_scope = st.text_area("Scope")
                    
                    col_tf3, col_tf4 = st.columns(2)
                    dept_fund = col_tf3.number_input("Dept Fund (₹L)", min_value=0.0)
                    vbg_fund = col_tf4.number_input("VB-G Fund (₹L)", min_value=0.0)
                    expected_persondays = st.number_input("Persondays*", min_value=0, value=0)

                    if st.button("Save Target", type="primary", use_container_width=True):
                        if not active_dept_id or not dist_id: st.error("Invalid Dept/District.")
                        elif not project_head: st.error("Project Head required.")
                        elif activity == "No activities available": st.error("Activity required.")
                        elif expected_persondays <= 0: st.error("Persondays required.")
                        else:
                            target_record = {
                                "department_id": active_dept_id, "wing_id": active_wing_id, "district_id": dist_id,
                                "financial_year": "2026-27", "project_head": project_head.strip(), "activity": activity,
                                "asset_count": asset_count, "annual_plan_scope": annual_plan_scope, "desired_target": desired_target,
                                "department_fund": dept_fund, "vbgramg_fund": vbg_fund, "expected_persondays": expected_persondays, "created_by": user['id']
                            }
                            try:
                                q_existing = supabase.table("department_targets").select("id").eq("department_id", active_dept_id).eq("district_id", dist_id).eq("financial_year", "2026-27").eq("activity", activity)
                                q_existing = q_existing.eq("wing_id", active_wing_id) if active_wing_id else q_existing.is_("wing_id", "null")
                                existing = q_existing.execute().data
                                
                                if existing:
                                    supabase.table("department_targets").update(target_record).eq("id", existing[0]['id']).execute()
                                    st.success("Updated successfully!")
                                else:
                                    supabase.table("department_targets").insert(target_record).execute()
                                    st.success("Added successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        with col_t1:
            st.markdown("#### Existing Targets")
            query_t = supabase.table("department_targets").select("*")
            if role == 'department':
                query_t = query_t.eq("department_id", user.get('department_id')).eq("district_id", user.get('district_id'))
                query_t = query_t.eq("wing_id", user.get('wing_id')) if user.get('wing_id') else query_t.is_("wing_id", "null")
            elif role in ['district', 'block']:
                query_t = query_t.eq("district_id", user.get('district_id'))
            
            data_t = query_t.execute().data
            if data_t:
                df_t = pd.DataFrame(data_t)
                df_t['Department'] = df_t.apply(lambda r: f"{dept_map.get(r['department_id'], 'Unknown')} ➔ {wing_map[r['wing_id']]['wing_name']}" if pd.notna(r.get('wing_id')) and r.get('wing_id') in wing_map else f"{dept_map.get(r['department_id'], 'Unknown')} (Main)", axis=1)
                
                df_t.rename(columns={'project_head': 'Project Head', 'activity': 'Activity', 'desired_target': 'Target', 'department_fund': 'Dept Fund', 'vbgramg_fund': 'VB-G Fund', 'expected_persondays': 'Persondays'}, inplace=True)
                st.dataframe(df_t[['Department', 'Project Head', 'Activity', 'Target', 'Dept Fund', 'VB-G Fund', 'Persondays']], use_container_width=True, hide_index=True)
            else:
                st.info("No targets mapped for your jurisdiction.")

    with tab2:
        st.markdown("#### Physical & Financial Progress")
        
        query_reg = supabase.table("convergence_register").select("*")
        if role == 'district': query_reg = query_reg.eq("district_id", user['district_id'])
        elif role == 'block': query_reg = query_reg.eq("block_id", user['block_id'])
        elif role == 'department': query_reg = query_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

        activities_reg = query_reg.execute().data
        if not activities_reg:
            st.info("No activities found in the register.")
        else:
            activity_map = {a['id']: f"{a.get('activity_description', 'Unnamed')} [{a.get('current_status', 'Planned')}]" for a in activities_reg}
            selected_act_id = st.selectbox("Select Activity to Update", options=list(activity_map.keys()), format_func=lambda x: activity_map[x])
            selected_act = next((a for a in activities_reg if a['id'] == selected_act_id), None)

            if selected_act:
                with st.form("update_progress_form"):
                    col_p1, col_p2 = st.columns([1, 2])
                    status_options = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed", "Dropped"]
                    current_status = selected_act.get('current_status', 'Planned')
                    
                    new_status = col_p1.selectbox("Status", status_options, index=status_options.index(current_status) if current_status in status_options else 0)
                    phys_ach = col_p2.slider("Physical %", 0, 100, int(float(selected_act.get('physical_achievement', 0) or 0)))
                    
                    col_p3, col_p4, col_p5 = st.columns(3)
                    mis_code_val = col_p3.text_input("MIS Code", value=selected_act.get('mis_code', '') or '')
                    fin_ach = col_p4.number_input("Financial (₹L)", min_value=0.0, value=float(selected_act.get('financial_achievement', 0) or 0))
                    persondays_gen = col_p5.number_input("Persondays Gen.", min_value=0, value=int(selected_act.get('persondays_generated', 0) or 0))

                    col_p6, col_p7, col_p8 = st.columns(3)
                    start_date = col_p6.date_input("Start Date", value=safe_parse_date(selected_act.get('actual_start_date')))
                    exp_date = col_p7.date_input("Exp. Completion", value=safe_parse_date(selected_act.get('expected_completion_date')))
                    act_date = col_p8.date_input("Actual Completion", value=safe_parse_date(selected_act.get('actual_completion_date')))

                    remarks = st.text_input("Remarks / Blockages", value=selected_act.get('remarks', '') or '')

                    if st.form_submit_button("Save Progress", type="primary", use_container_width=True):
                        if new_status in ["Under Implementation", "Completed"] and not mis_code_val.strip():
                            st.error("⚠️ MIS Code is mandatory when moving to 'Under Implementation' or 'Completed'.")
                        else:
                            update_data = {
                                "current_status": new_status, "mis_code": mis_code_val.strip() if mis_code_val else None,
                                "physical_achievement": phys_ach, "financial_achievement": fin_ach, "persondays_generated": persondays_gen,
                                "actual_start_date": str(start_date) if start_date else None, "expected_completion_date": str(exp_date) if exp_date else None,
                                "actual_completion_date": str(act_date) if act_date else None, "remarks": remarks
                            }
                            try:
                                supabase.table("convergence_register").update(update_data).eq("id", selected_act_id).execute()
                                history_payload = {"convergence_id": selected_act_id, "status": new_status, "physical_achievement": phys_ach, "financial_achievement": fin_ach, "persondays_generated": persondays_gen, "remarks": f"MIS: {mis_code_val} | {remarks}"}
                                supabase.table("progress_updates").insert(history_payload).execute()
                                st.success("✅ Progress saved.")
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")

    with tab3:
        st.markdown("#### Departmental Meeting Commitments (Sync)")
        ap_query = supabase.table("meeting_action_points").select("id, meeting_id, department_id, linkage_type, action_point, deadline, status").execute().data
        
        if ap_query:
            df_ap = pd.DataFrame(ap_query)
            if role == 'department': df_ap = df_ap[df_ap['department_id'] == user.get('department_id')]

            if not df_ap.empty:
                meetings_data = supabase.table("meetings").select("id, meeting_date, meeting_type").execute().data
                m_map = {m['id']: m for m in meetings_data}
                
                df_ap['Meeting Context'] = df_ap['meeting_id'].map(lambda x: f"{m_map.get(x, {}).get('meeting_type', 'Unknown')} ({m_map.get(x, {}).get('meeting_date', 'Unknown')})")
                pending_ap = df_ap[~df_ap['status'].isin(['Completed', 'Dropped'])].copy()
                
                if not pending_ap.empty:
                    pending_ap['deadline'] = pd.to_datetime(pending_ap['deadline'])
                    pending_ap['Days Left'] = (pending_ap['deadline'] - pd.to_datetime(date.today())).dt.days
                    
                    st.dataframe(pending_ap[['Meeting Context', 'action_point', 'Days Left', 'status']].sort_values('Days Left'), use_container_width=True, hide_index=True)
                    
                    with st.form("sync_atr_form"):
                        col_s1, col_s2 = st.columns(2)
                        sync_id = col_s1.selectbox("Select Resolution", pending_ap['id'].tolist(), format_func=lambda x: f"[{pending_ap[pending_ap['id']==x]['Meeting Context'].values[0]}] {pending_ap[pending_ap['id']==x]['action_point'].values[0][:40]}...")
                        sync_status = col_s2.selectbox("New Status", ['Under Process', 'Approved', 'Under Execution', 'Completed', 'Not Feasible', 'Dropped'])
                        sync_remarks = st.text_input("Remarks (Required if Not Feasible)")
                        
                        if st.form_submit_button("Update Status"):
                            if sync_status == 'Not Feasible' and not sync_remarks.strip():
                                st.error("⚠️ Remarks required for Not Feasible status.")
                            else:
                                supabase.table("meeting_action_points").update({"status": sync_status, "remarks": sync_remarks}).eq("id", sync_id).execute()
                                st.success("✅ Updated!")
                                st.rerun()
                else: st.success("🎉 All meeting commitments are complete.")
            else: st.info("No commitments assigned.")
        else: st.info("No resolutions recorded globally.")
