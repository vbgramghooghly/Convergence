import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import base64
import json
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block')
    st.markdown("<h1 style='color: #1F77B4;'>📋 Convergence Meeting & Resolution Tracker</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()

    # 1. Fetch Global Master Data & Contacts Directory
    departments = supabase.table("departments").select("id, department_name").execute().data
    dept_dict = {d['department_name']: d['id'] for d in departments}
    dept_map_reverse = {d['id']: d['department_name'] for d in departments}

    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data
    block_dict_reverse = {b['id']: b['block_name'] for b in blocks_data}

    # Fetch from Contacts Directory (Not Users) to get full details
    contacts_data = supabase.table("contacts").select("id, full_name, contact_number, email_id, designations(designation_name)").execute().data
    contact_map = {}
    for c in contacts_data:
        desig = c.get('designations', {})
        desig_name = desig.get('designation_name', 'No Designation') if isinstance(desig, dict) else 'No Designation'
        contact_map[c['id']] = {
            "name": c.get('full_name', 'Unknown'),
            "designation": desig_name,
            "phone": c.get('contact_number', 'N/A'),
            "email": c.get('email_id', 'N/A')
        }

    # Global Meeting Fetch based on role
    query = supabase.table("meetings").select("*")
    if user['role'] == 'district':
        query = query.eq("district_id", user['district_id']).eq("meeting_type", "District")
    elif user['role'] == 'block':
        query = query.eq("block_id", user['block_id']).eq("meeting_type", "Block")
    
    meetings = query.order("meeting_date", desc=True).execute().data
    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()

    # Tab layout
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Meeting Dashboard",
        "📝 Schedule & Mark Attendance", 
        "🎯 Resolution Tracker", 
        "🖨️ Print & Reports",
        "⏭️ Next Meeting Prep"
    ])

    # ======================== TAB 1: MEETING DASHBOARD & DETAILS ========================
    with tab1:
        st.subheader("Meeting Dashboard")
        if not df_meetings.empty:
            st.dataframe(df_meetings[['meeting_date', 'meeting_type', 'venue', 'chairperson', 'objective']], use_container_width=True, hide_index=True)
            
            st.markdown("### 🔍 View Detailed Proceedings & Attendance")
            detail_sel = st.selectbox("Select Meeting Date to view details", df_meetings['id'].tolist(),
                                       format_func=lambda x: f"{df_meetings[df_meetings['id']==x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id']==x]['meeting_type'].values[0]} Level")
            
            sel_meeting_data = df_meetings[df_meetings['id'] == detail_sel].iloc[0]
            
            with st.container(border=True):
                st.markdown(f"<h3 style='color: #2B8A3E;'>Meeting Details: {sel_meeting_data['meeting_date']}</h3>", unsafe_allow_html=True)
                col_d1, col_d2 = st.columns(2)
                col_d1.write(f"**Chairperson:** {sel_meeting_data['chairperson']}")
                col_d1.write(f"**Level:** {sel_meeting_data['meeting_type']}")
                col_d2.write(f"**Venue:** {sel_meeting_data['venue']}")
                col_d2.write(f"**Financial Year:** {sel_meeting_data['financial_year']}")
                
                st.write(f"**Objective:** {sel_meeting_data['objective']}")
                st.write(f"**General Decisions:** {sel_meeting_data['decisions']}")
                
                st.markdown("#### 👥 Detailed Attendance Register")
                att_data = sel_meeting_data.get('detailed_attendance')
                if att_data and isinstance(att_data, list) and len(att_data) > 0:
                    att_df = pd.DataFrame(att_data)
                    disp_att_df = att_df[['official_name', 'official_designation', 'official_phone', 'official_email', 'attended_by_subordinate', 'subordinate_name', 'subordinate_designation', 'subordinate_phone']]
                    disp_att_df.columns = ['Official Name', 'Official Designation', 'Official Phone', 'Official Email', 'Subordinate Attended?', 'Subordinate Name', 'Subordinate Designation', 'Subordinate Phone']
                    
                    def highlight_subs(row):
                        if row['Subordinate Attended?']:
                            return ['background-color: #FFF3CD'] * len(row)
                        return [''] * len(row)
                        
                    st.dataframe(disp_att_df.style.apply(highlight_subs, axis=1), use_container_width=True, hide_index=True)
                else:
                    st.info("No detailed attendance captured for this meeting.")
        else:
            st.info("No meetings found for your assigned jurisdiction.")

    # ======================== TAB 2: SCHEDULE & ATTENDANCE BUILDER ========================
    with tab2:
        st.subheader("Schedule New Convergence Meeting")
        st.caption("Statutory requirement for District and Block Level convergence planning.")
        
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
        decisions = st.text_area("Initial Decisions / Minutes (General)")
        
        st.markdown("---")
        st.markdown("### 👥 Dynamic Attendance Register")
        st.caption("Select registered officials from the Contacts Directory. If a subordinate attended, check the box and enter their details temporarily.")
        
        selected_contact_ids = st.multiselect(
            "Select Invited Officials from Contact Directory", 
            options=list(contact_map.keys()), 
            format_func=lambda x: f"{contact_map[x]['name']} ({contact_map[x]['designation']})"
        )

        detailed_attendance_payload = []
        
        if selected_contact_ids:
            st.markdown("#### Verify Attendance & Representatives")
            for cid in selected_contact_ids:
                contact = contact_map[cid]
                with st.container(border=True):
                    st.markdown(f"**{contact['name']}** | {contact['designation']} | {contact['phone']} | {contact['email']}")
                    
                    is_sub = st.checkbox(f"Attended by Subordinate/Representative instead of {contact['name']}?", key=f"chk_{cid}")
                    
                    sub_name, sub_desig, sub_phone = "", "", ""
                    if is_sub:
                        sc1, sc2, sc3 = st.columns(3)
                        sub_name = sc1.text_input("Subordinate Name", key=f"s_name_{cid}")
                        sub_desig = sc2.text_input("Subordinate Designation", key=f"s_desig_{cid}")
                        sub_phone = sc3.text_input("Subordinate Phone", key=f"s_phone_{cid}")

                    detailed_attendance_payload.append({
                        "contact_id": cid,
                        "official_name": contact['name'],
                        "official_designation": contact['designation'],
                        "official_phone": contact['phone'],
                        "official_email": contact['email'],
                        "attended_by_subordinate": is_sub,
                        "subordinate_name": sub_name if is_sub else None,
                        "subordinate_designation": sub_desig if is_sub else None,
                        "subordinate_phone": sub_phone if is_sub else None
                    })

        if st.button("Save Meeting & Attendance Record", type="primary"):
            meeting_data = {
                "meeting_type": meeting_type,
                "financial_year": financial_year,
                "meeting_date": str(meeting_date),
                "chairperson": chairperson,
                "venue": venue,
                "objective": objective,
                "decisions": decisions,
                "attendees": selected_contact_ids, 
                "detailed_attendance": detailed_attendance_payload, 
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
                st.success("✅ Meeting and Detailed Attendance recorded successfully.")
                log_action(user, "CREATE", "meetings", result.data[0]['id'], details=meeting_data)
                st.rerun()

    # ======================== TAB 3: RESOLUTION TRACKER & CROSS-REFERENCE ========================
    with tab3:
        st.subheader("🎯 Department-wise Progress & Commitments")
        if df_meetings.empty:
            st.info("No meetings found. Please schedule a meeting first.")
        else:
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

            # CROSS-REFERENCE (Block Outcomes for District)
            if sel_meeting_type == 'District' and user['role'] in ['superadmin', 'district']:
                st.markdown("---")
                st.markdown("### 🔗 Reference Block-Level Outcomes")
                st.caption("Review recent commitments made at the Block level by a specific department.")
                
                ref_dept_name = st.selectbox("Select Department to review Block Outcomes", list(dept_dict.keys()), key="ref_dept_sel")
                ref_dept_id = dept_dict[ref_dept_name]
                
                bm_query = supabase.table("meetings").select("id, meeting_date, block_id").eq("meeting_type", "Block")
                if user['role'] == 'district':
                    bm_query = bm_query.eq("district_id", user.get('district_id'))
                
                block_meetings = bm_query.execute().data
                if block_meetings:
                    bm_ids = [m['id'] for m in block_meetings]
                    bm_map = {m['id']: m for m in block_meetings}
                    
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

    # ======================== TAB 4: PRINT & REPORTS ========================
    with tab4:
        st.subheader("🖨️ Meeting & Resolution Reports")
        
        report_type = st.radio("Select Report Type", ["By Specific Meeting (Chairperson Report)", "Date-Wise Resolution Register"], horizontal=True)
        st.markdown("---")
        
        if report_type == "By Specific Meeting (Chairperson Report)":
            if not df_meetings.empty and 'meeting_sel' in locals() and 'ap_query' in locals() and ap_query:
                sel_meeting_data = df_meetings[df_meetings['id'] == meeting_sel].iloc[0]
                
                # Format Detailed Attendance for Print
                att_data = sel_meeting_data.get('detailed_attendance')
                attendance_html = ""
                if att_data and isinstance(att_data, list):
                    attendance_html += "<table class='print-table'><tr><th>Official Name</th><th>Designation</th><th>Attended By</th><th>Contact</th></tr>"
                    for att in att_data:
                        off_name = att.get('official_name', '')
                        off_desig = att.get('official_designation', '')
                        if att.get('attended_by_subordinate'):
                            att_by = f"<b>Subordinate:</b> {att.get('subordinate_name', '')}<br><i>({att.get('subordinate_designation', '')})</i>"
                            contact_info = att.get('subordinate_phone', '')
                            row_style = "background-color: #fff3cd;"
                        else:
                            att_by = "Self"
                            contact_info = att.get('official_phone', '')
                            row_style = ""
                        attendance_html += f"<tr style='{row_style}'><td>{off_name}</td><td>{off_desig}</td><td>{att_by}</td><td>{contact_info}</td></tr>"
                    attendance_html += "</table>"
                else:
                    attendance_html = "<p>No detailed attendance recorded.</p>"
                
                # Format Resolution Table for Print
                print_df = df_ap[['Department', 'action_point', 'target', 'status', 'remarks']].copy()
                print_df.columns = ['Department', 'Resolution / Commitment', 'Target', 'Status', 'Outcome / Remarks']
                html_table = print_df.to_html(index=False, classes="print-table")
                
                printable_html = f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Chairperson Report - {sel_meeting_data['meeting_date']}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; padding: 20px; color: #333; font-size: 12px; }}
                        h2 {{ text-align: center; color: #1F77B4; border-bottom: 2px solid #1F77B4; padding-bottom: 10px; }}
                        .meta-info {{ margin-bottom: 20px; background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e9ecef; }}
                        .print-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; page-break-inside: auto; }}
                        .print-table tr {{ page-break-inside: avoid; page-break-after: auto; }}
                        .print-table th, .print-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
                        .print-table th {{ background-color: #1F77B4; color: white; }}
                        @page {{ size: A4 landscape; margin: 15mm; }}
                        @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}
                    </style>
                </head>
                <body onload="window.print()">
                    <div class="no-print" style="text-align: center; margin-bottom: 20px;">
                        <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background: #1F77B4; color: white; border: none; border-radius: 5px;">🖨️ Print Report for Chairperson</button>
                    </div>
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
                print_href = f'''<a href="data:text/html;base64,{b64_html}" download="Meeting_Report_{sel_meeting_data['meeting_date']}.html" style="text-decoration: none;">
                    <div style="background-color: #2B8A3E; color: white; padding: 10px 15px; border-radius: 6px; text-align: center; font-weight: bold; cursor: pointer;">
                        📥 Download & Print Chairperson Report
                    </div></a>'''
                st.markdown(print_href, unsafe_allow_html=True)
            else:
                st.warning("Please select a meeting in Tab 3 with active resolutions to generate a report.")
                
        elif report_type == "Date-Wise Resolution Register":
            st.markdown("#### Select Date Range for Resolutions")
            col_dt1, col_dt2 = st.columns(2)
            start_date = col_dt1.date_input("Start Date", value=date.today().replace(day=1))
            end_date = col_dt2.date_input("End Date", value=date.today())
            
            if not df_meetings.empty:
                # Filter meetings by date range
                mask = (pd.to_datetime(df_meetings['meeting_date']).dt.date >= start_date) & (pd.to_datetime(df_meetings['meeting_date']).dt.date <= end_date)
                filtered_meetings = df_meetings.loc[mask]
                
                if not filtered_meetings.empty:
                    meeting_ids = filtered_meetings['id'].tolist()
                    m_map = {m['id']: m for m in filtered_meetings.to_dict('records')}
                    
                    # Fetch resolutions for these meeting IDs
                    date_ap_query = supabase.table("meeting_action_points").select("*").in_("meeting_id", meeting_ids).execute().data
                    if date_ap_query:
                        df_date_ap = pd.DataFrame(date_ap_query)
                        df_date_ap['Department'] = df_date_ap['department_id'].map(dept_map_reverse)
                        df_date_ap['Meeting Date'] = df_date_ap['meeting_id'].map(lambda x: m_map.get(x, {}).get('meeting_date', 'Unknown'))
                        df_date_ap['Meeting Level'] = df_date_ap['meeting_id'].map(lambda x: m_map.get(x, {}).get('meeting_type', 'Unknown'))
                        
                        disp_cols = ['Meeting Date', 'Meeting Level', 'Department', 'action_point', 'target', 'status']
                        st.dataframe(df_date_ap[disp_cols].sort_values(['Meeting Date', 'Department']), use_container_width=True, hide_index=True)
                        
                        # Generate Date-Wise Print HTML
                        print_df = df_date_ap[disp_cols].copy()
                        print_df.columns = ['Date', 'Level', 'Department', 'Resolution / Commitment', 'Target', 'Status']
                        html_table = print_df.to_html(index=False, classes="print-table")
                        
                        date_printable_html = f"""<!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>Date-Wise Resolution Register</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; padding: 20px; color: #333; font-size: 12px; }}
                                h2 {{ text-align: center; color: #1F77B4; border-bottom: 2px solid #1F77B4; padding-bottom: 10px; }}
                                .meta-info {{ margin-bottom: 20px; background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e9ecef; text-align: center; font-size: 14px; }}
                                .print-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }}
                                .print-table tr {{ page-break-inside: avoid; page-break-after: auto; }}
                                .print-table th, .print-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
                                .print-table th {{ background-color: #1F77B4; color: white; }}
                                @page {{ size: A4 landscape; margin: 15mm; }}
                                @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}
                            </style>
                        </head>
                        <body onload="window.print()">
                            <div class="no-print" style="text-align: center; margin-bottom: 20px;">
                                <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background: #1F77B4; color: white; border: none; border-radius: 5px;">🖨️ Print Date-Wise Register</button>
                            </div>
                            <h2>Date-Wise Resolution Register</h2>
                            <div class="meta-info">
                                <strong>Period:</strong> {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')} <br>
                                <strong>Total Resolutions:</strong> {len(df_date_ap)}
                            </div>
                            {html_table}
                        </body>
                        </html>
                        """
                        b64_html_date = base64.b64encode(date_printable_html.encode('utf-8')).decode('utf-8')
                        date_print_href = f'''<a href="data:text/html;base64,{b64_html_date}" download="Resolution_Register_{start_date}_to_{end_date}.html" style="text-decoration: none;">
                            <div style="background-color: #1F77B4; color: white; padding: 10px 15px; border-radius: 6px; text-align: center; font-weight: bold; cursor: pointer; margin-top: 15px;">
                                📥 Download & Print Date-Wise Register
                            </div></a>'''
                        st.markdown(date_print_href, unsafe_allow_html=True)
                    else:
                        st.info("No resolutions found in the selected date range.")
                else:
                    st.info("No meetings found in the selected date range.")
            else:
                st.info("No meeting data available.")

    # ======================== TAB 5: NEXT MEETING AGENDA PREP ========================
    with tab5:
        st.subheader("⏭️ Next Meeting Agenda Preparation")
        if not df_meetings.empty and 'meeting_sel' in locals() and 'ap_query' in locals() and ap_query:
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
