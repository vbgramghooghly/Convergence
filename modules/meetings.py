import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block')
    st.markdown("<h1 style='color: #1F77B4;'>📋 Convergence Meeting & Resolution Tracker</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()

    # Fetch global master data for mapping
    departments = supabase.table("departments").select("id, department_name").execute().data
    dept_dict = {d['department_name']: d['id'] for d in departments}
    dept_map_reverse = {d['id']: d['department_name'] for d in departments}

    # Tab layout
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Schedule Meeting", 
        "📂 Meeting Proceedings", 
        "🎯 Resolution Tracker", 
        "📊 Dashboard & Reminders"
    ])

    # ======================== 1. Schedule Meeting ========================
    with tab1:
        st.subheader("Schedule New Convergence Meeting")
        with st.form("meeting_form"):
            col_m1, col_m2, col_m3 = st.columns(3)
            
            if user['role'] in ['superadmin', 'district']:
                meeting_type = col_m1.radio("Meeting Level", ['District', 'Block'], horizontal=True)
            else:  
                meeting_type = 'Block'
                col_m1.info("Meeting Level: Block")

            financial_year = col_m2.selectbox("Financial Year", ["2026-27", "2027-28", "2028-29"])
            meeting_date = col_m3.date_input("Meeting Date", date.today())

            if meeting_type == 'District':
                districts = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
                dist_dict = {d['district_name']: d['id'] for d in districts}
                if user['role'] == 'district':
                    dist_sel = next((name for name, id in dist_dict.items() if id == user['district_id']), None)
                    st.text(f"Jurisdiction: {dist_sel} District")
                else:
                    dist_sel = st.selectbox("District", list(dist_dict.keys()))
                block_sel = None
            else:
                blocks = supabase.table("blocks").select("id,block_name,district_id").eq("active", True).execute().data
                if user['role'] == 'block':
                    block_sel_list = [b for b in blocks if b['id'] == user['block_id']]
                    if block_sel_list:
                        block_sel = block_sel_list[0]['block_name']
                    else:
                        block_sel = None
                    dist_sel = None
                else:
                    block_sel = st.selectbox("Block Jurisdiction", [b['block_name'] for b in blocks])
                    selected_block = next(b for b in blocks if b['block_name'] == block_sel)
                    dist_sel = selected_block['district_id'] 

            col_a1, col_a2 = st.columns(2)
            chairperson = col_a1.text_input("Chairperson (Name & Designation)")
            venue = col_a2.text_input("Venue / Platform")
            
            objective = st.text_input("Meeting Objective / Purpose")
            agenda = st.text_area("Agenda Items")
            decisions = st.text_area("Decisions / Minutes (General)")

            submitted = st.form_submit_button("Save Meeting Master Record", type="primary")
            
            if submitted:
                meeting_data = {
                    "meeting_type": meeting_type,
                    "financial_year": financial_year,
                    "meeting_date": str(meeting_date),
                    "chairperson": chairperson,
                    "venue": venue,
                    "objective": objective,
                    "agenda": agenda,
                    "decisions": decisions,
                    "created_by": user['id']
                }
                
                if meeting_type == 'District':
                    meeting_data["district_id"] = dist_dict[dist_sel] if user['role'] != 'district' else user['district_id']
                else:
                    if user['role'] == 'block':
                        meeting_data["block_id"] = user['block_id']
                    else:
                        block_obj = next(b for b in blocks if b['block_name'] == block_sel)
                        meeting_data["block_id"] = block_obj['id']
                        meeting_data["district_id"] = block_obj['district_id']

                result = supabase.table("meetings").insert(meeting_data).execute()
                if result.data:
                    st.success("✅ Meeting recorded successfully.")
                    log_action(user, "CREATE", "meetings", result.data[0]['id'], details=meeting_data)
                    st.rerun()
                else:
                    st.error("Failed to save meeting.")

    # ======================== Common Fetch for Tabs 2, 3, & 4 ========================
    query = supabase.table("meetings").select("*")
    if user['role'] == 'district':
        query = query.eq("district_id", user['district_id']).eq("meeting_type", "District")
    elif user['role'] == 'block':
        query = query.eq("block_id", user['block_id'])
    
    meetings = query.order("meeting_date", desc=True).execute().data
    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()

    # ======================== 2. Meeting Proceedings ========================
    with tab2:
        st.subheader("📂 Meeting Register & Proceedings")
        if not df_meetings.empty:
            st.dataframe(df_meetings[['meeting_date', 'meeting_type', 'venue', 'chairperson', 'objective']], use_container_width=True)
            
            st.markdown("### Generate Action Taken Report (ATR)")
            meeting_sel = st.selectbox("Select Meeting to view resolutions", df_meetings['id'].tolist(),
                                       format_func=lambda x: f"{df_meetings[df_meetings['id']==x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id']==x]['objective'].values[0]}")
            st.session_state['selected_meeting_id'] = meeting_sel
        else:
            st.info("No meetings found for your jurisdiction.")

    # ======================== 3. Resolution Tracker ========================
    with tab3:
        st.subheader("🎯 Department-wise Resolution Matrix")
        selected_meeting = st.session_state.get('selected_meeting_id', None)
        if not selected_meeting and not df_meetings.empty:
            selected_meeting = df_meetings.iloc[0]['id']

        if selected_meeting:
            with st.expander("➕ Add New Resolution / Action Point", expanded=False):
                with st.form("add_resolution"):
                    col_r1, col_r2 = st.columns([1, 2])
                    assigned_dept = col_r1.selectbox("Converging Department", list(dept_dict.keys()))
                    priority = col_r2.selectbox("Priority Level", ["HIGH", "MEDIUM", "LOW"])
                    
                    action_text = st.text_area("Resolution / Action Point (Must be specific & actionable)")
                    
                    col_r3, col_r4 = st.columns(2)
                    target = col_r3.text_input("Desired Target / Measurable Capacity")
                    responsible = col_r4.text_input("Responsible Officer / Agency")
                    
                    col_r5, col_r6 = st.columns(2)
                    deadline = col_r5.date_input("Deadline", date.today())
                    status = col_r6.selectbox("Current Status", [
                        'Not Started', 'Under Process', 'Departmental Action Pending', 
                        'Data Awaited', 'Approved', 'Under Execution', 'Completed', 'Dropped'
                    ])

                    if st.form_submit_button("Adopt Resolution", type="primary"):
                        res_data = {
                            "meeting_id": selected_meeting,
                            "department_id": dept_dict[assigned_dept],
                            "action_point": action_text,
                            "priority": priority,
                            "target": target,
                            "responsible_officer": responsible,
                            "deadline": str(deadline),
                            "status": status
                        }
                        res = supabase.table("meeting_action_points").insert(res_data).execute()
                        if res.data:
                            st.success("✅ Resolution added to tracker.")
                            log_action(user, "CREATE", "meeting_action_points", res.data[0]['id'], details=res_data)
                            st.rerun()

            # Master Resolution Table
            st.markdown("### 📋 Master Resolution Register")
            ap_query = supabase.table("meeting_action_points").select("*").eq("meeting_id", selected_meeting).execute().data
            
            if ap_query:
                df_ap = pd.DataFrame(ap_query)
                df_ap['Department'] = df_ap['department_id'].map(dept_map_reverse)
                
                # Calculate Tracker Fields
                today = pd.to_datetime(date.today())
                df_ap['deadline'] = pd.to_datetime(df_ap['deadline'])
                df_ap['Days Remaining'] = (df_ap['deadline'] - today).dt.days
                
                # Generate Reminders/Flags
                def get_flag(row):
                    if row['status'] in ['Completed', 'Dropped']:
                        return "✅ Closed"
                    if row['Days Remaining'] < 0:
                        return "🚨 OVERDUE"
                    if row['Days Remaining'] == 0:
                        return "⚠️ Due Today (R3)"
                    if row['Days Remaining'] <= 3:
                        return "⚠️ Urgent (R2)"
                    if row['Days Remaining'] <= 7:
                        return "🔔 Upcoming (R1)"
                    return "⏳ On Track"

                df_ap['Tracker Flag'] = df_ap.apply(get_flag, axis=1)
                
                # Display Clean Dataframe
                display_cols = ['id', 'Department', 'priority', 'action_point', 'target', 'deadline', 'Tracker Flag', 'status']
                st.dataframe(df_ap[display_cols].sort_values('deadline'), use_container_width=True, hide_index=True)

                # Update Existing Resolution Form
                st.markdown("---")
                st.markdown("### ✏️ Update Action Taken Report (ATR)")
                with st.form("update_atr"):
                    col_u1, col_u2 = st.columns(2)
                    ap_id = col_u1.selectbox("Select Resolution ID to Update", df_ap['id'].tolist())
                    new_ap_status = col_u2.selectbox("Update Status", [
                        'Not Started', 'Under Process', 'Departmental Action Pending', 
                        'Data Awaited', 'Approved', 'Under Execution', 'Completed', 'Dropped'
                    ])
                    remarks = st.text_area("Action Taken / Remarks / Evidence (Provide details for closure)")
                    
                    if st.form_submit_button("Update ATR Status"):
                        update_payload = {"status": new_ap_status, "remarks": remarks}
                        supabase.table("meeting_action_points").update(update_payload).eq("id", ap_id).execute()
                        log_action(user, "UPDATE", "meeting_action_points", ap_id, details=update_payload)
                        st.success("✅ Action Taken Report updated successfully.")
                        st.rerun()
            else:
                st.info("No resolutions adopted for this meeting yet.")

    # ======================== 4. Dashboard & Reminders ========================
    with tab4:
        st.subheader("📊 Performance Dashboard & Reminder Engine")
        
        if selected_meeting and ap_query:
            # Metrics
            total_res = len(df_ap)
            completed = len(df_ap[df_ap['status'] == 'Completed'])
            overdue = len(df_ap[df_ap['Tracker Flag'] == '🚨 OVERDUE'])
            pending = total_res - completed - len(df_ap[df_ap['status'] == 'Dropped'])
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Resolutions", total_res)
            c2.metric("✅ Completed", completed)
            c3.metric("⏳ Pending Action", pending)
            c4.metric("🚨 Overdue", overdue, delta_color="inverse")
            
            st.markdown("---")
            st.markdown("### 🔔 Automated Follow-up Engine")
            st.caption("Generate official communication for pending and overdue items.")
            
            pending_df = df_ap[~df_ap['status'].isin(['Completed', 'Dropped'])]
            
            if not pending_df.empty:
                selected_reminder = st.selectbox("Select Resolution to Generate Official Reminder", pending_df['id'].tolist(),
                                                 format_func=lambda x: f"[{pending_df[pending_df['id']==x]['Department'].values[0]}] - {pending_df[pending_df['id']==x]['action_point'].values[0][:50]}...")
                
                rem_row = pending_df[pending_df['id'] == selected_reminder].iloc[0]
                
                reminder_text = f"""
**Subject: Follow-up on Resolution No. {rem_row['id']} – VB-G RAM G Convergence Meeting**

Reference is invited to the resolution adopted in the VB-G RAM G Convergence Meeting.
The **{rem_row['Department']}** was requested to: *{rem_row['action_point']}*
**Target:** {rem_row['target']}

*   **Responsible Authority:** {rem_row['responsible_officer']}
*   **Stipulated Deadline:** {rem_row['deadline'].strftime('%Y-%m-%d')}
*   **Current Status:** {rem_row['status']} ({rem_row['Tracker Flag']})

The concerned authority is requested to take necessary action and furnish the updated Action Taken Report immediately. 
The matter may be treated as **{rem_row['priority']} Priority**.
                """
                
                st.info(reminder_text)
                st.button("📋 Copy to Clipboard (Coming Soon)", disabled=True)
            else:
                st.success("All resolutions for this meeting are closed. No reminders pending.")
        else:
            st.info("No data available to generate dashboard.")
