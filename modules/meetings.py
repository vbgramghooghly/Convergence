import streamlit as st
import pandas as pd
from datetime import date, datetime
import base64
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block')
    st.markdown("<h1 style='color: #1F77B4;'>📋 Convergence Meeting & Resolution Tracker</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()

    # 1. Fetch Global Master Data
    departments = supabase.table("departments").select("id, department_name").execute().data
    dept_dict = {d['department_name']: d['id'] for d in departments}
    dept_map_reverse = {d['id']: d['department_name'] for d in departments}

    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data
    block_dict_reverse = {b['id']: b['block_name'] for b in blocks_data}

    all_users = supabase.table("users").select("id, full_name, role, department_id").execute().data
    user_map_reverse = {u['id']: f"{u['full_name']} ({dept_map_reverse.get(u['department_id'], u['role'].upper())})" for u in all_users}

    # Tab layout
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Schedule & Attendance", 
        "🎯 Resolution Tracker", 
        "🖨️ Chairperson Reports",
        "⏭️ Next Meeting Prep"
    ])

    # ======================== TAB 1: SCHEDULE & ATTENDANCE ========================
    with tab1:
        st.subheader("Schedule New Convergence Meeting")
        with st.form("meeting_form"):
            col_m1, col_m2, col_m3 = st.columns(3)
            
            # Restrict meeting type based on login role
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
                dist_sel = next((name for name, id in dist_dict.items() if id == user.get('district_id')), list(dist_dict.keys())[0])
                if user['role'] != 'district': dist_sel = st.selectbox("District", list(dist_dict.keys()))
                block_sel = None
            else:
                if user['role'] == 'block':
                    block_sel = block_dict_reverse.get(user['block_id'], "Unknown Block")
                    st.text(f"Jurisdiction: {block_sel}")
                    dist_sel = next(b['district_id'] for b in blocks_data if b['id'] == user['block_id'])
                else:
                    block_sel = st.selectbox("Block Jurisdiction", [b['block_name'] for b in blocks_data])
                    dist_sel = next(b['district_id'] for b in blocks_data if b['block_name'] == block_sel)

            col_a1, col_a2 = st.columns(2)
            chairperson = col_a1.text_input("Chairperson (Name & Designation)")
            venue = col_a2.text_input("Venue / Platform")
            
            objective = st.text_input("Meeting Objective / Schematic Discussion")
            
            # ATTENDANCE LINKED TO MASTER DATABASE
            st.markdown("#### 👥 Mark Attendance")
            selected_attendees = st.multiselect(
                "Select Participating Officers / Departments", 
                options=[u['id'] for u in all_users], 
                format_func=lambda x: user_map_reverse.get(x, "Unknown")
            )

            decisions = st.text_area("Initial Decisions / Minutes (General)")

            submitted = st.form_submit_button("Save Meeting Master Record", type="primary")
            
            if submitted:
                meeting_data = {
                    "meeting_type": meeting_type,
                    "financial_year": financial_year,
                    "meeting_date": str(meeting_date),
                    "chairperson": chairperson,
                    "venue": venue,
                    "objective": objective,
                    "decisions": decisions,
                    "attendees": selected_attendees,
                    "created_by": user['id']
                }
                
                if meeting_type == 'District':
                    meeting_data["district_id"] = dist_dict[dist_sel] if user['role'] != 'district' else user['district_id']
                else:
                    block_obj = next(b for b in blocks_data if b['block_name'] == block_sel)
                    meeting_data["block_id"] = block_obj['id']
                    meeting_data["district_id"] = block_obj['district_id']

                result = supabase.table("meetings").insert(meeting_data).execute()
                if result.data:
                    st.success("✅ Meeting and Attendance recorded successfully.")
                    log_action(user, "CREATE", "meetings", result.data[0]['id'], details=meeting_data)
                    st.rerun()

    # ======================== GLOBAL FETCH FOR TABS 2, 3, & 4 ========================
    # District users only see District meetings. Block users only see their specific Block meetings.
    query = supabase.table("meetings").select("*")
    if user['role'] == 'district':
        query = query.eq("district_id", user['district_id']).eq("meeting_type", "District")
    elif user['role'] == 'block':
        query = query.eq("block_id", user['block_id']).eq("meeting_type", "Block")
    
    meetings = query.order("meeting_date", desc=True).execute().data
    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()

    if df_meetings.empty:
        st.info("No meetings found for your assigned jurisdiction.")
        st.stop()

    # ======================== TAB 2: RESOLUTION TRACKER & CROSS-REFERENCE ========================
    with tab2:
        st.subheader("🎯 Department-wise Progress & Commitments")
        meeting_sel = st.selectbox("Select Meeting to Track", df_meetings['id'].tolist(),
                                   format_func=lambda x: f"{df_meetings[df_meetings['id']==x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id']==x]['objective'].values[0]}")
        
        sel_meeting_type = df_meetings[df_meetings['id'] == meeting_sel].iloc[0]['meeting_type']
        
        with st.expander("➕ Add New Departmental Commitment / Resolution", expanded=False):
            with st.form("add_resolution"):
                col_r1, col_r2 = st.columns([1, 2])
                assigned_dept = col_r1.selectbox("Converging Department", list(dept_dict.keys()))
                priority = col_r2.selectbox("Priority Level", ["HIGH", "MEDIUM", "LOW"])
                
                action_text = st.text_area("Resolution / New Plan (Must be specific)")
                
                col_r3, col_r4 = st.columns(2)
                target = col_r3.text_input("Desired Target / Measurable Capacity")
                responsible = col_r4.text_input("Responsible Officer")
                
                col_r5, col_r6 = st.columns(2)
                deadline = col_r5.date_input("Deadline", date.today())
                status = col_r6.selectbox("Current Status", [
                    'Not Started', 'Under Process', 'Departmental Action Pending', 
                    'Approved', 'Under Execution', 'Completed', 'Dropped'
                ])

                if st.form_submit_button("Adopt Resolution", type="primary"):
                    res_data = {
                        "meeting_id": meeting_sel,
                        "department_id": dept_dict[assigned_dept],
                        "action_point": action_text,
                        "priority": priority,
                        "target": target,
                        "responsible_officer": responsible,
                        "deadline": str(deadline),
                        "status": status
                    }
                    supabase.table("meeting_action_points").insert(res_data).execute()
                    st.success("✅ Resolution added to tracker.")
                    st.rerun()

        # Master Resolution Table
        ap_query = supabase.table("meeting_action_points").select("*").eq("meeting_id", meeting_sel).execute().data
        
        if ap_query:
            df_ap = pd.DataFrame(ap_query)
            df_ap['Department'] = df_ap['department_id'].map(dept_map_reverse)
            
            today = pd.to_datetime(date.today())
            df_ap['deadline'] = pd.to_datetime(df_ap['deadline'])
            df_ap['Days Remaining'] = (df_ap['deadline'] - today).dt.days
            
            def get_flag(row):
                if row['status'] in ['Completed', 'Dropped']: return "✅ Closed"
                if row['Days Remaining'] < 0: return "🚨 OVERDUE"
                if row['Days Remaining'] == 0: return "⚠️ Due Today"
                return "⏳ On Track"

            df_ap['Tracker Flag'] = df_ap.apply(get_flag, axis=1)
            display_cols = ['id', 'Department', 'priority', 'action_point', 'target', 'deadline', 'Tracker Flag', 'status']
            st.dataframe(df_ap[display_cols].sort_values('deadline'), use_container_width=True, hide_index=True)

            # Update Action Taken Report
            st.markdown("### ✏️ Update Progress / Action Taken Report")
            with st.form("update_atr"):
                col_u1, col_u2 = st.columns(2)
                ap_id = col_u1.selectbox("Select Resolution ID", df_ap['id'].tolist())
                new_ap_status = col_u2.selectbox("Update Status", [
                    'Not Started', 'Under Process', 'Departmental Action Pending', 
                    'Approved', 'Under Execution', 'Completed', 'Dropped'
                ])
                remarks = st.text_area("Outcome / Action Taken (Will be printed for Chairperson)")
                
                if st.form_submit_button("Update Progress"):
                    update_payload = {"status": new_ap_status, "remarks": remarks}
                    supabase.table("meeting_action_points").update(update_payload).eq("id", ap_id).execute()
                    st.success("✅ Progress updated successfully.")
                    st.rerun()
        else:
            st.info("No resolutions adopted for this meeting yet.")

        # ==============================================================================
        # NEW FEATURE: BLOCK LEVEL REFERENCE FOR DISTRICT MEETINGS
        # ==============================================================================
        if sel_meeting_type == 'District' and user['role'] in ['superadmin', 'district']:
            st.markdown("---")
            st.markdown("### 🔗 Reference Block-Level Outcomes")
            st.caption("Review recent commitments made at the Block level by a specific department for cross-tier planning.")
            
            ref_dept_name = st.selectbox("Select Department to review Block Outcomes", list(dept_dict.keys()), key="ref_dept_sel")
            ref_dept_id = dept_dict[ref_dept_name]
            
            # Fetch block meetings for this district
            bm_query = supabase.table("meetings").select("id, meeting_date, block_id").eq("meeting_type", "Block")
            if user['role'] == 'district':
                bm_query = bm_query.eq("district_id", user.get('district_id'))
            
            block_meetings = bm_query.execute().data
            if block_meetings:
                bm_ids = [m['id'] for m in block_meetings]
                bm_map = {m['id']: m for m in block_meetings}
                
                # Fetch action points for these block meetings for the selected department
                bap_query = supabase.table("meeting_action_points").select("*").eq("department_id", ref_dept_id).in_("meeting_id", bm_ids).execute().data
                
                if bap_query:
                    df_bap = pd.DataFrame(bap_query)
                    df_bap['Block'] = df_bap['meeting_id'].map(lambda x: block_dict_reverse.get(bm_map.get(x, {}).get('block_id'), "Unknown"))
                    df_bap['Meeting Date'] = df_bap['meeting_id'].map(lambda x: bm_map.get(x, {}).get('meeting_date'))
                    
                    disp_cols = ['Block', 'Meeting Date', 'action_point', 'target', 'status', 'remarks']
                    st.dataframe(df_bap[disp_cols].sort_values('Meeting Date', ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.info(f"No block-level resolutions recorded for {ref_dept_name} yet.")
            else:
                st.info("No Block meetings recorded in this district yet.")

    # ======================== TAB 3: CHAIRPERSON PRINT REPORT ========================
    with tab3:
        st.subheader("🖨️ Chairperson Progress Report")
        st.caption("Generates a formal, formatted sheet containing Attendance, Discussion, and Resolution Outcomes.")
        
        if ap_query:
            sel_meeting_data = df_meetings[df_meetings['id'] == meeting_sel].iloc[0]
            
            # Format Attendance Names
            attendee_ids = sel_meeting_data.get('attendees', [])
            if not isinstance(attendee_ids, list): attendee_ids = []
            attendee_names = [user_map_reverse.get(aid, "Unknown") for aid in attendee_ids]
            attendance_html = "<ul>" + "".join([f"<li>{name}</li>" for name in attendee_names]) + "</ul>" if attendee_names else "<p>No attendance recorded.</p>"
            
            # Format Resolution Table for Print
            print_df = df_ap[['Department', 'action_point', 'target', 'status', 'remarks']].copy()
            print_df.columns = ['Department', 'Resolution / Commitment', 'Target', 'Status', 'Outcome / Remarks']
            html_table = print_df.to_html(index=False, classes="print-table")
            
            printable_html = f"""
            <html>
            <head>
                <title>Chairperson Report - {sel_meeting_data['meeting_date']}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 30px; color: #333; }}
                    h2 {{ text-align: center; color: #1F77B4; border-bottom: 2px solid #1F77B4; padding-bottom: 10px; }}
                    .meta-info {{ margin-bottom: 20px; background: #f8f9fa; padding: 15px; border-radius: 8px; }}
                    .print-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    .print-table th, .print-table td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 13px; }}
                    .print-table th {{ background-color: #1F77B4; color: white; }}
                    @media print {{ .no-print {{ display: none; }} }}
                </style>
            </head>
            <body>
                <button class="no-print" onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background: #1F77B4; color: white; border: none; border-radius: 5px;">🖨️ Print Report for Chairperson</button>
                <h2>Convergence Meeting Progress Report</h2>
                <div class="meta-info">
                    <strong>Date:</strong> {sel_meeting_data['meeting_date']} <br>
                    <strong>Chairperson:</strong> {sel_meeting_data['chairperson']} <br>
                    <strong>Objective:</strong> {sel_meeting_data['objective']}
                </div>
                <h3>Registered Attendance</h3>
                {attendance_html}
                <h3>Department-wise Progress & Commitments</h3>
                {html_table}
            </body>
            </html>
            """
            b64_html = base64.b64encode(printable_html.encode('utf-8')).decode('utf-8')
            print_href = f'''<a href="data:text/html;base64,{b64_html}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #2B8A3E; color: white; padding: 10px 15px; border-radius: 6px; text-align: center; font-weight: bold; cursor: pointer;">
                    🖨️ Generate Chairperson Progress Report
                </div></a>'''
            st.markdown(print_href, unsafe_allow_html=True)
        else:
            st.warning("Please add resolutions in the tracker before generating a Chairperson report.")

    # ======================== TAB 4: NEXT MEETING AGENDA PREP ========================
    with tab4:
        st.subheader("⏭️ Next Meeting Agenda Preparation")
        st.caption("Automatically pulls pending and overdue resolutions to form the agenda for the upcoming meeting.")
        
        if ap_query:
            pending_df = df_ap[~df_ap['status'].isin(['Completed', 'Dropped'])]
            
            if not pending_df.empty:
                st.warning(f"⚠️ There are {len(pending_df)} pending/overdue items to be carried forward to the next meeting.")
                st.dataframe(pending_df[['Department', 'action_point', 'Tracker Flag', 'remarks']], use_container_width=True, hide_index=True)
                
                agenda_text = "AGENDA ITEMS FOR NEXT MEETING (Auto-Generated):\n\n"
                for idx, row in pending_df.iterrows():
                    agenda_text += f"- [{row['Department']}] Follow-up on: {row['action_point']} (Status: {row['Tracker Flag']})\n"
                
                st.text_area("Copy this text to paste into the 'Agenda' field of your next Meeting:", value=agenda_text, height=200)
            else:
                st.success("🎉 All resolutions for this meeting are Complete! No baggage for the next meeting.")
