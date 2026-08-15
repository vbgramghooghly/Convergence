import streamlit as st
import pandas as pd
from datetime import date
import io
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

# ==========================================
# PERFORMANCE OPTIMIZATION: CACHE MASTER DATA
# ==========================================
@st.cache_data(ttl=600)
def fetch_master_data():
    """Caches static master data to improve enterprise performance."""
    supabase = get_supabase()
    departments = supabase.table("departments").select("id,department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    districts = supabase.table("districts").select("id,district_name").execute().data or []
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data or []
    activities = supabase.table("activities").select("*").eq("active", True).execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("*").execute().data or []
    return departments, wings, districts, blocks, activities, act_dept_mapping

def safe_parse_date(date_val):
    """Safely parses dates from the database without overwriting."""
    if pd.isna(date_val) or not date_val:
        return None
    try:
        if isinstance(date_val, str):
            return pd.to_datetime(date_val).date()
        return date_val
    except Exception:
        return None

def show():
    # 1. ENFORCE SECURITY & ACCESS RULES (Unchanged)
    require_role('superadmin', 'district', 'block', 'department')
    user = get_current_user()
    role = user['role']
    supabase = get_supabase()
    
    # 2. GLOBAL HEADER & BREADCRUMB
    st.markdown("<div style='font-size: 0.85rem; color: #64748B; margin-bottom: 0.5rem;'>Home / Execution & Governance / Progress Monitoring</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom: 0px; color: #0F4C81;'>🚀 Implementation & Target Monitoring</h2>", unsafe_allow_html=True)
    st.caption("Enterprise Workspace: Plan annual targets, execute physical progress, and resolve statutory meeting commitments.")
    st.markdown("---")

    # 3. LOAD OPTIMIZED DATA
    departments, wings, districts, blocks, activities, act_dept_mapping = fetch_master_data()
    
    dept_map = {d['id']: d['department_name'] for d in departments}
    wing_map = {w['id']: w for w in wings}
    t_dists = districts if role in ['superadmin', 'district'] else [d for d in districts if d['id'] == user.get('district_id')]
    t_dist_dict = {d['district_name']: d['id'] for d in t_dists}

    # ======================== SECONDARY CONTEXTUAL NAVIGATION ========================
    tab1, tab2, tab3 = st.tabs([
        "🎯 Department Targets (Planning)", 
        "🏗️ Implementation Progress (Execution)", 
        "🤝 Meeting Commitments (Sync)"
    ])

    # =====================================================================
    # TAB 1: DEPARTMENT TARGETS (Annual Planning)
    # =====================================================================
    with tab1:
        # Fetch Target Data for KPIs and Tables (Unchanged Logic)
        query_t = supabase.table("department_targets").select("*")
        if role == 'department':
            query_t = query_t.eq("department_id", user.get('department_id')).eq("district_id", user.get('district_id'))
            if user.get('wing_id'): query_t = query_t.eq("wing_id", user.get('wing_id'))
            else: query_t = query_t.is_("wing_id", "null")
        elif role in ['district', 'block']:
            query_t = query_t.eq("district_id", user.get('district_id'))
        
        data_t = query_t.execute().data
        df_t = pd.DataFrame(data_t) if data_t else pd.DataFrame()

        # KPI SUMMARY CARDS
        if not df_t.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Activities Targeted", len(df_t))
            k2.metric("Total Planned Assets", int(pd.to_numeric(df_t['asset_count'], errors='coerce').sum()))
            k3.metric("Converged Dept Fund (₹L)", f"₹{pd.to_numeric(df_t['department_fund'], errors='coerce').sum():,.2f}")
            k4.metric("Total Persondays Planned", f"{int(pd.to_numeric(df_t['expected_persondays'], errors='coerce').sum()):,}")
            st.markdown("<br>", unsafe_allow_html=True)

        col_t1, col_t2 = st.columns([1.6, 1], gap="large")
        
        with col_t2:
            st.markdown("#### 📝 Add / Update Target")
            if role == 'block':
                st.info("Target setting is managed at the District/Department level. You can view targets on the left.")
            else:
                with st.container(border=True):
                    # --- DEPARTMENT / WING CONTEXT LOGIC (Unchanged) ---
                    active_dept_id, active_wing_id, dist_id = None, None, None

                    if role == 'department':
                        active_dept_id = user.get('department_id')
                        active_wing_id = user.get('wing_id')
                        dept_name = dept_map.get(active_dept_id, "Unknown Department")
                        if active_wing_id and active_wing_id in wing_map:
                            display_text = f"{dept_name} ➔ {wing_map[active_wing_id]['wing_name']}"
                        else:
                            display_text = f"{dept_name} (Main Department)"
                            
                        st.markdown(f"<span style='color:#64748B; font-size:12px;'>DEPARTMENT / WING</span><br>**{display_text}**", unsafe_allow_html=True)
                        dist_sel = list(t_dist_dict.keys())[0] if t_dist_dict else None
                        dist_id = user.get('district_id')
                        st.markdown(f"<span style='color:#64748B; font-size:12px;'>DISTRICT</span><br>**{dist_sel}**<br><br>", unsafe_allow_html=True)
                    else:
                        dept_options = [{"label": f"{d['department_name']} (Main Department)", "dept_id": d['id'], "wing_id": None} for d in departments]
                        for w in wings:
                            p_name = dept_map.get(w['department_id'], "Unknown Department")
                            dept_options.append({"label": f"{p_name} ➔ {w['wing_name']} [{w['entity_type']}]", "dept_id": w['department_id'], "wing_id": w['id']})
                        
                        dept_options = sorted(dept_options, key=lambda x: x['label'])
                        dept_labels = [opt['label'] for opt in dept_options]
                        
                        sel_dept_label = st.selectbox("Department / Wing*", dept_labels)
                        selected_opt = next(opt for opt in dept_options if opt['label'] == sel_dept_label)
                        active_dept_id, active_wing_id = selected_opt['dept_id'], selected_opt['wing_id']
                        dist_sel = st.selectbox("District*", list(t_dist_dict.keys()) if t_dist_dict else ["None"])
                        dist_id = t_dist_dict.get(dist_sel)

                    # Form Inputs
                    project_head_options = [
                        "AWC (Anganwadi Center)", "Plantation", "Water Conservation & Harvesting",
                        "Solid/Liquid Waste Management", "Rural Infrastructure", "Livelihood & Agriculture", "Other (Specify Custom)"
                    ]
                    ph_sel = st.selectbox("Convergence Project Head*", project_head_options)
                    project_head = st.text_input("Type Custom Project Head Name*") if ph_sel == "Other (Specify Custom)" else ph_sel

                    mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == active_dept_id]
                    valid_activities = [a for a in activities if a['id'] in mapped_act_ids]
                    valid_act_names = [a['activity_name'] for a in valid_activities]
                    
                    if not valid_act_names:
                        st.warning("No approved activities mapped to this parent department.")
                        activity = st.selectbox("Approved Activity / Work Category*", ["No activities available"], disabled=True)
                    else:
                        activity = st.selectbox("Approved Activity / Work Category*", valid_act_names)

                    col_tf1, col_tf2 = st.columns(2)
                    desired_target = col_tf1.number_input("Desired Target (FY)*", min_value=1, value=1)
                    asset_count = col_tf2.number_input("Number of assets/works", min_value=0, value=0)
                    
                    annual_plan_scope = st.text_area("Scope under Annual Plan")
                    
                    col_tf3, col_tf4 = st.columns(2)
                    dept_fund = col_tf3.number_input("Dept Fund (₹ Lakhs)", min_value=0.0, format="%.2f")
                    vbg_fund = col_tf4.number_input("VB-G Fund (₹ Lakhs)", min_value=0.0, format="%.2f")
                    
                    expected_persondays = st.number_input("Expected Persondays*", min_value=0, value=0)

                    if st.button("Save Target Record", type="primary", use_container_width=True):
                        if not active_dept_id or not dist_id: st.error("Invalid Department or District.")
                        elif not project_head or not project_head.strip(): st.error("Project Head name cannot be empty.")
                        elif activity == "No activities available": st.error("Cannot save target without a valid approved activity.")
                        elif expected_persondays <= 0: st.error("Expected Persondays is a mandatory field.")
                        else:
                            target_record = {
                                "department_id": active_dept_id, "wing_id": active_wing_id, "district_id": dist_id,
                                "financial_year": "2026-27", "project_head": project_head.strip(), "activity": activity,
                                "asset_count": asset_count, "annual_plan_scope": annual_plan_scope, "desired_target": desired_target,
                                "department_fund": dept_fund, "vbgramg_fund": vbg_fund, "expected_persondays": expected_persondays, "created_by": user['id']
                            }
                            # Exact Original Logic Maintained
                            try:
                                q_existing = supabase.table("department_targets").select("id").eq("department_id", active_dept_id).eq("district_id", dist_id).eq("financial_year", "2026-27").eq("activity", activity)
                                if active_wing_id: q_existing = q_existing.eq("wing_id", active_wing_id)
                                else: q_existing = q_existing.is_("wing_id", "null")
                                
                                existing = q_existing.execute().data
                                
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
                                if "wing_id" in str(e):
                                    st.error("🚨 Database Error: The `wing_id` column is missing from your `department_targets` table in Supabase.")
                                else:
                                    st.error(f"Error saving target: {e}")

        with col_t1:
            st.markdown("#### 📊 Target Analytics Dashboard")
            if not df_t.empty:
                # Format Department Display
                def format_dept_display(row):
                    d_name = dept_map.get(row.get('department_id'), 'Unknown')
                    w_id = row.get('wing_id')
                    if w_id and not pd.isna(w_id) and w_id in wing_map:
                        return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
                    return f"{d_name} (Main)"
                    
                df_t['Department / Wing'] = df_t.apply(format_dept_display, axis=1)
                if 'project_head' not in df_t.columns: df_t['project_head'] = "N/A"
                
                df_t.rename(columns={
                    'project_head': 'Project Head', 'activity': 'Approved Activity', 'desired_target': 'Target',
                    'department_fund': 'Dept. Fund', 'vbgramg_fund': 'VB-G Fund', 'expected_persondays': 'Persondays'
                }, inplace=True)

                disp_cols = ['Department / Wing', 'Project Head', 'Approved Activity', 'Target', 'Dept. Fund', 'VB-G Fund', 'Persondays']
                
                # Enterprise Data Grid
                st.dataframe(df_t[disp_cols], use_container_width=True, hide_index=True)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_t[disp_cols].to_excel(writer, index=False, sheet_name='Targets')
                st.download_button("📥 Export Target Plan to Excel", data=buffer.getvalue(), file_name="department_targets.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("No targets mapped for your jurisdiction. Use the form to plan annual targets.")


    # =====================================================================
    # TAB 2: IMPLEMENTATION PROGRESS (Field Execution)
    # =====================================================================
    with tab2:
        st.markdown("#### 🏗️ Execution & Progress Controller")
        
        # Unchanged Data Fetch Logic
        query_reg = supabase.table("convergence_register").select("*")
        if role == 'district': query_reg = query_reg.eq("district_id", user['district_id'])
        elif role == 'block': query_reg = query_reg.eq("block_id", user['block_id'])
        elif role == 'department': query_reg = query_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

        activities_reg = query_reg.execute().data

        if not activities_reg:
            st.info("No convergence activities found in the register. Please add activities in the Work Entry module first.")
        else:
            # --- MANAGEMENT EXCEPTION ENGINE ---
            missing_mis = [a for a in activities_reg if a.get('current_status') in ["Under Implementation", "Completed"] and not a.get('mis_code')]
            delayed = [a for a in activities_reg if a.get('current_status') == "Delayed"]
            
            if missing_mis or delayed:
                st.markdown("<div style='background-color:#FFF4E5; padding:12px; border-left:4px solid #ED6C02; border-radius:4px; margin-bottom:15px;'><b>⚠️ Management Exceptions Detected:</b></div>", unsafe_allow_html=True)
                e1, e2 = st.columns(2)
                if missing_mis: e1.error(f"🚨 {len(missing_mis)} activities are under implementation/completed but **Missing MIS Codes**.")
                if delayed: e2.warning(f"⏳ {len(delayed)} activities are officially flagged as **Delayed**.")

            # Selection
            activity_map = {a['id']: f"[{a.get('current_status', 'Planned').upper()}] {a.get('activity_description', 'Unnamed Activity')}" for a in activities_reg}
            selected_act_id = st.selectbox("🔍 Search & Select Specific Work to Update", options=list(activity_map.keys()), format_func=lambda x: activity_map[x])
            selected_act = next((a for a in activities_reg if a['id'] == selected_act_id), None)

            if selected_act:
                # 360° RECORD VIEW (Read Only Summary)
                st.markdown(f"""
                <div style="background:#F8FAFC; padding:16px; border-radius:8px; border:1px solid #E2E8F0; margin-bottom: 20px;">
                    <div style="color:#0F4C81; font-weight:700; font-size:16px; margin-bottom:8px;">{selected_act.get('activity_description')}</div>
                    <div style="display:flex; gap:20px; font-size:13px; color:#475569;">
                        <div><b>Source:</b> {selected_act.get('origin_source', 'N/A')}</div>
                        <div><b>Type:</b> {selected_act.get('convergence_type', 'N/A')}</div>
                        <div><b>Location:</b> {selected_act.get('geo_location', 'N/A')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col_p_left, col_p_right = st.columns([1.5, 1], gap="large")
                
                with col_p_left:
                    st.markdown("##### 📝 Update Progress Status")
                    with st.form("update_progress_form"):
                        col_p1, col_p2 = st.columns(2)
                        
                        status_options = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed", "Dropped"]
                        current_status = selected_act.get('current_status', 'Planned')
                        new_status = col_p1.selectbox("New Status*", status_options, index=status_options.index(current_status) if current_status in status_options else 0)
                        
                        phys_ach = col_p2.slider("Physical Achievement (%)*", min_value=0, max_value=100, value=int(float(selected_act.get('physical_achievement', 0.0) or 0.0)))
                        
                        st.markdown("##### 💰 Financials & MIS Registration")
                        col_p3, col_p4 = st.columns(2)
                        mis_code_val = col_p3.text_input("MIS Code (Mandatory if Active/Done)", value=selected_act.get('mis_code', '') or '')
                        fin_ach = col_p4.number_input("Financial Achievement (₹ Lakhs)", min_value=0.0, value=float(selected_act.get('financial_achievement', 0.0) or 0.0))
                        
                        persondays_gen = st.number_input("Persondays Generated (Cumulative)", min_value=0, value=int(selected_activity.get('persondays_generated', 0) if 'selected_activity' in locals() else selected_act.get('persondays_generated', 0) or 0))

                        st.markdown("##### 📅 Schedule & Blockages")
                        col_p5, col_p6, col_p7 = st.columns(3)
                        start_date = col_p5.date_input("Actual Start", value=safe_parse_date(selected_act.get('actual_start_date')))
                        exp_date = col_p6.date_input("Expected End", value=safe_parse_date(selected_act.get('expected_completion_date')))
                        act_date = col_p7.date_input("Actual End", value=safe_parse_date(selected_act.get('actual_completion_date')))

                        remarks = st.text_area("Remarks / Blockage Details", value=selected_act.get('remarks', '') or '')

                        if st.form_submit_button("Commit Progress Update", type="primary", use_container_width=True):
                            # EXACT ORIGINAL VALIDATION RULE PRESERVED
                            if new_status in ["Under Implementation", "Completed"] and not mis_code_val.strip():
                                st.error("⚠️ **Validation Error:** MIS Code is strictly mandatory when moving a scheme to 'Under Implementation' or 'Completed'. Please enter the valid MIS Code from the central portal to proceed.")
                            else:
                                update_data = {
                                    "current_status": new_status, "mis_code": mis_code_val.strip() if mis_code_val else None,
                                    "physical_achievement": phys_ach, "financial_achievement": fin_ach, "persondays_generated": persondays_gen,
                                    "actual_start_date": str(start_date) if start_date else None, "expected_completion_date": str(exp_date) if exp_date else None,
                                    "actual_completion_date": str(act_date) if act_date else None, "remarks": remarks
                                }
                                try:
                                    supabase.table("convergence_register").update(update_data).eq("id", selected_act_id).execute()
                                    
                                    # EXACT ORIGINAL AUDIT TRAIL LOGIC PRESERVED
                                    history_payload = {
                                        "convergence_id": selected_act_id, "status": new_status, 
                                        "physical_achievement": phys_ach, "financial_achievement": fin_ach, 
                                        "persondays_generated": persondays_gen, "remarks": f"MIS Code: {mis_code_val} | {remarks}"
                                    }
                                    supabase.table("progress_updates").insert(history_payload).execute()
                                    log_action(user.get('id'), f"UPDATE convergence_register {selected_act_id}")
                                    
                                    st.success("✅ Progress and MIS mapping updated successfully!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error saving progress: {e}")

                with col_p_right:
                    st.markdown("#### ⏳ Activity Audit Timeline")
                    try:
                        history_query = supabase.table("progress_updates").select("*").eq("convergence_id", selected_act_id).order("created_at", desc=True).execute()
                        if history_query.data:
                            for idx, h in enumerate(history_query.data):
                                h_date = pd.to_datetime(h['created_at']).strftime('%d %b %Y, %H:%M')
                                st.markdown(f"""
                                <div style="border-left: 2px solid #CBD5E1; padding-left: 15px; margin-bottom: 15px; margin-left: 5px;">
                                    <div style="font-size: 11px; color: #64748B;">{h_date}</div>
                                    <div style="font-weight: 600; color: #1E293B;">State changed to: {h.get('status')}</div>
                                    <div style="font-size: 13px; color: #475569;">Physical: {h.get('physical_achievement')}% | Financial: ₹{h.get('financial_achievement')}L</div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("No historical updates recorded for this activity yet.")
                    except Exception:
                        st.warning("Could not load history timeline.")

    # =====================================================================
    # TAB 3: MEETING COMMITMENTS (Sync with Meetings Module)
    # =====================================================================
    with tab3:
        st.markdown("#### 🤝 Resolution Tracking & Action Taken Reports (ATR)")
        st.caption("Fulfill the Action Points legally mandated and assigned to your department from statutory meetings.")

        ap_query = supabase.table("meeting_action_points").select("id, meeting_id, department_id, priority, linkage_type, action_point, target, deadline, status, remarks").execute().data
        
        if ap_query:
            df_ap = pd.DataFrame(ap_query)
            if role == 'department': 
                df_ap = df_ap[df_ap['department_id'] == user.get('department_id')]

            if not df_ap.empty:
                df_ap['Department'] = df_ap['department_id'].map(dept_map)
                
                meetings_data = supabase.table("meetings").select("id, meeting_date, meeting_type").execute().data
                m_map = {m['id']: m for m in meetings_data}
                
                df_ap['Meeting Context'] = df_ap['meeting_id'].map(lambda x: f"{m_map.get(x, {}).get('meeting_type', 'Unknown')} ({m_map.get(x, {}).get('meeting_date', 'Unknown')})")
                
                # Active Statuses
                pending_ap = df_ap[~df_ap['status'].isin(['Completed', 'Dropped'])].copy()
                
                if not pending_ap.empty:
                    # SLA ENGINE
                    pending_ap['deadline'] = pd.to_datetime(pending_ap['deadline'])
                    today_dt = pd.to_datetime(date.today())
                    pending_ap['Days Left'] = (pending_ap['deadline'] - today_dt).dt.days
                    pending_ap['Linkage'] = pending_ap.get('linkage_type', 'Routine')
                    
                    # Custom SLA Badging
                    def get_sla_badge(days):
                        if pd.isna(days): return "⚪ Unscheduled"
                        if days < 0: return "🔴 Overdue"
                        if days == 0: return "🟡 Due Today"
                        if days <= 3: return "🟠 Due Soon"
                        return "🔵 On Track"
                        
                    pending_ap['SLA Status'] = pending_ap['Days Left'].apply(get_sla_badge)

                    # Quick KPIs
                    sk1, sk2, sk3, sk4 = st.columns(4)
                    sk1.metric("Open Resolutions", len(pending_ap))
                    sk2.metric("Overdue / Breach", len(pending_ap[pending_ap['Days Left'] < 0]))
                    sk3.metric("Due Today", len(pending_ap[pending_ap['Days Left'] == 0]))
                    sk4.metric("Requires Review", len(pending_ap[pending_ap['status'] == 'Not Feasible (Requires Review)']))
                    
                    st.markdown("<br>##### 📑 Pending Action Registry", unsafe_allow_html=True)
                    disp_cols = ['SLA Status', 'Meeting Context', 'Department', 'action_point', 'Days Left', 'status']
                    st.dataframe(pending_ap[disp_cols].sort_values('Days Left'), use_container_width=True, hide_index=True)
                    
                    st.markdown("##### ✏️ Update ATR Status")
                    with st.form("sync_atr_form"):
                        col_s1, col_s2 = st.columns(2)
                        
                        sync_id = col_s1.selectbox("Select Resolution Issue", pending_ap['id'].tolist(), format_func=lambda x: f"[{pending_ap[pending_ap['id']==x]['Meeting Context'].values[0]}] {pending_ap[pending_ap['id']==x]['action_point'].values[0][:50]}...")
                        sync_status = col_s2.selectbox("New Resolution Status*", ['Under Process', 'Approved', 'Under Execution', 'Completed', 'Not Feasible (Requires Review)', 'Dropped'])
                        sync_remarks = st.text_area("Implementation Outcome / Remarks (Required if Not Feasible)")
                        
                        submitted_sync = st.form_submit_button("Submit ATR Update", type="primary")
                        
                        if submitted_sync:
                            # EXACT ORIGINAL BUSINESS RULE PRESERVED
                            if sync_status == 'Not Feasible (Requires Review)' and not sync_remarks.strip():
                                st.error("⚠️ **Validation Error:** You must provide a clear reason in 'Remarks' when flagging an activity as Not Feasible so the Chairperson can review it.")
                            else:
                                payload = {"status": sync_status, "remarks": sync_remarks}
                                supabase.table("meeting_action_points").update(payload).eq("id", sync_id).execute()
                                log_action(user.get('id'), f"UPDATE meeting_action_points {sync_id}")
                                
                                st.success("✅ Meeting ATR Updated! It is now synced with the master Meeting tracker.")
                                st.rerun()
                else:
                    st.success("🎉 All meeting commitments have been fully completed or closed!")
            else:
                st.info("No meeting commitments found for your department.")
        else:
            st.info("No resolutions recorded in the global governance system.")
