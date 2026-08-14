from datetime import date, datetime
import base64
import pandas as pd
import streamlit as st
from auth.auth import require_role, get_current_user
from utils.audit import log_action
from utils.db import get_supabase


def inject_custom_css():
    """Injects custom CSS to hide the Streamlit toolbar (Fork/GitHub buttons)."""
    st.markdown(
        """
        <style>
        /* Hide Streamlit toolbar (Fork and GitHub buttons) */
        .stAppToolbar {
            visibility: hidden !important;
        }
        .metric-card { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 4px solid #1F77B4; }
        .print-btn { background-color: #2B8A3E; color: white; padding: 10px 15px; border-radius: 6px; text-align: center; font-weight: bold; cursor: pointer; text-decoration: none; display: block; margin-top: 10px; }
        .print-btn:hover { background-color: #21702f; color: white; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def safe_int(val):
    """Safely converts floats/strings to integers to prevent Postgres 22P02 casting errors."""
    if pd.isna(val) or val is None or val == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None

def show():
    require_role("superadmin", "district", "block", "department")
    inject_custom_css()

    st.markdown(
        "<h1 style='color: #1F77B4;'>📋 Advanced Convergence Meeting & Resolution Tracker</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Manage statutory convergence meetings: Scheduling → Attendance → Target Review → Resolutions → Next Agenda.")
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()
    role = user["role"]
    today = pd.to_datetime(date.today())

    # ======================== 1. MASTER DATA FETCH & MAPPING ========================
    departments = supabase.table("departments").select("id, department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data or []
    
    activities_data = supabase.table("activities").select("id, activity_name").eq("active", True).execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("activity_id, department_id").execute().data or []

    # Fetch User Directory - removed role restrictions to ensure anyone attached to a dept shows up
    users_data = supabase.table("users").select("id, full_name, role, department_id, wing_id, district_id, block_id").execute().data or []
    user_dict = {u["id"]: u for u in users_data}

    dept_map = {d["id"]: d["department_name"] for d in departments}
    wing_map = {w["id"]: w for w in wings}
    block_dict_reverse = {b["id"]: b["block_name"] for b in blocks_data}
    act_map = {a["id"]: a["activity_name"] for a in activities_data}

    # Build Unified Department / Wing Options for clean multiselects
    unified_depts = []
    for d in departments:
        unified_depts.append({
            "uid": f"{d['id']}_main",
            "label": f"{d['department_name']} (Main Department)",
            "dept_id": d["id"],
            "wing_id": None,
        })
    for w in wings:
        p_name = dept_map.get(w["department_id"], "Unknown Department")
        unified_depts.append({
            "uid": f"{w['department_id']}_{w['id']}",
            "label": f"{p_name} ➔ {w['wing_name']} [{w['entity_type']}]",
            "dept_id": w["department_id"],
            "wing_id": w["id"],
        })

    unified_depts = sorted(unified_depts, key=lambda x: x["label"])
    unified_uid_to_label = {u["uid"]: u["label"] for u in unified_depts}
    dept_labels = [u["label"] for u in unified_depts]

    # Helper function to format Department/Wing display cleanly for dataframes
    def format_dept_display(row):
        d_name = dept_map.get(row.get("department_id"), "Unknown")
        w_id = row.get("wing_id")
        if w_id and not pd.isna(w_id) and w_id in wing_map:
            return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
        return f"{d_name} (Main)"

    # ======================== 2. CONTEXTUAL DATA FETCH ========================
    q_meetings = supabase.table("meetings").select("*")
    if role in ["district", "department"]:
        q_meetings = q_meetings.eq("district_id", user["district_id"])
    elif role == "block":
        q_meetings = q_meetings.eq("block_id", user["block_id"])

    meetings = q_meetings.order("meeting_date", desc=True).execute().data or []
    
    # Contextual Filtering for Departments (Only see meetings they were invited to)
    if role == "department" and meetings:
        user_uid_main = f"{user.get('department_id')}_main"
        user_uid_wing = f"{user.get('department_id')}_{user.get('wing_id')}" if user.get('wing_id') else user_uid_main
        filtered_meetings = []
        for m in meetings:
            attendees = m.get('attendees') or []
            if user_uid_main in attendees or user_uid_wing in attendees:
                filtered_meetings.append(m)
        meetings = filtered_meetings

    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()
    valid_meet_ids = [m['id'] for m in meetings]

    # Fetch All Relevant Action Points
    ap_data = []
    if valid_meet_ids:
        ap_data = supabase.table("meeting_action_points").select("*").in_("meeting_id", valid_meet_ids).execute().data or []
    df_ap = pd.DataFrame(ap_data) if ap_data else pd.DataFrame()

    # Apply Tracker Logic to APs
    if not df_ap.empty:
        if role == "department":
            if user.get('wing_id'):
                df_ap = df_ap[(df_ap['department_id'] == user['department_id']) & (df_ap['wing_id'] == user['wing_id'])]
            else:
                df_ap = df_ap[(df_ap['department_id'] == user['department_id']) & (df_ap['wing_id'].isna())]

        df_ap["Department / Wing"] = df_ap.apply(format_dept_display, axis=1)
        m_context_map = {m["id"]: f"{m['meeting_date']} ({m['meeting_type']})" for m in meetings}
        df_ap["Origin Meeting"] = df_ap["meeting_id"].map(m_context_map)
        df_ap["deadline"] = pd.to_datetime(df_ap["deadline"], errors="coerce")

        def get_flag(row):
            stat = str(row.get("status", "")).lower()
            if stat in ["completed", "closed", "dropped"]: return "🟢 CLOSED"
            if "feasible" in stat or "review" in stat: return "🟠 FOR REVIEW"
            if "not started" in stat: return "⚪ NOT STARTED"
            if pd.isna(row["deadline"]): return "🔵 ON TRACK"
            days_rem = (row["deadline"] - today).days
            if days_rem < 0: return "🔴 OVERDUE"
            if days_rem == 0: return "🟡 DUE TODAY"
            return "🔵 ON TRACK"

        df_ap["Tracker Flag"] = df_ap.apply(get_flag, axis=1)

    # ======================== TABS LAYOUT ========================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Performance Dashboard",
        "🗓️ Schedule Meeting",
        "✍️ Record & Print Proceedings",
        "🎯 Advanced Tracker",
        "🖨️ Master Reports",
        "⏭️ Next Agenda Prep",
    ])

    # ======================== TAB 1: RESOLUTION PERFORMANCE DASHBOARD ========================
    with tab1:
        st.subheader("Resolution Performance Dashboard")
        if df_ap.empty:
            st.info("No resolution data available for your jurisdiction.")
        else:
            total_res = len(df_ap)
            closed = len(df_ap[df_ap["Tracker Flag"] == "🟢 CLOSED"])
            on_track = len(df_ap[df_ap["Tracker Flag"] == "🔵 ON TRACK"])
            due_today = len(df_ap[df_ap["Tracker Flag"] == "🟡 DUE TODAY"])
            overdue = len(df_ap[df_ap["Tracker Flag"] == "🔴 OVERDUE"])
            for_review = len(df_ap[df_ap["Tracker Flag"] == "🟠 FOR REVIEW"])

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Total Resolutions", total_res)
            c2.metric("🟢 Closed", closed)
            c3.metric("🔵 On Track", on_track)
            c4.metric("🟡 Due Today", due_today)
            c5.metric("🔴 Overdue", overdue)
            c6.metric("🟠 For Review", for_review)

            st.markdown("---")
            col_dash1, col_dash2 = st.columns(2)

            with col_dash1:
                st.markdown("#### Department-wise View")
                dept_perf = df_ap.groupby("Department / Wing").agg(
                    Total=('id', 'count'),
                    Closed=('Tracker Flag', lambda x: (x == '🟢 CLOSED').sum()),
                    Pending=('Tracker Flag', lambda x: (x.isin(['🔵 ON TRACK', '⚪ NOT STARTED', '🟡 DUE TODAY'])).sum()),
                    Overdue=('Tracker Flag', lambda x: (x == '🔴 OVERDUE').sum())
                ).reset_index()
                dept_perf['Achievement %'] = (dept_perf['Closed'] / dept_perf['Total'] * 100).round(1).astype(str) + '%'
                st.dataframe(dept_perf, use_container_width=True, hide_index=True)

            with col_dash2:
                st.markdown("#### Meeting-wise View")
                mtg_perf = df_ap.groupby("Origin Meeting").agg(
                    Resolutions=('id', 'count'),
                    Closed=('Tracker Flag', lambda x: (x == '🟢 CLOSED').sum()),
                    Overdue=('Tracker Flag', lambda x: (x == '🔴 OVERDUE').sum())
                ).reset_index()
                st.dataframe(mtg_perf.sort_values('Origin Meeting', ascending=False), use_container_width=True, hide_index=True)

    # ======================== TAB 2: SCHEDULE MEETING ========================
    with tab2:
        st.subheader("🗓️ 1. Schedule New Convergence Meeting")
        
        if role == 'department':
            st.warning("🔒 Meeting scheduling is managed by District and Block Administration.")
        else:
            col_m1, col_m2, col_m3 = st.columns(3)
            meeting_type = col_m1.radio("Meeting Level", ["District", "Block"], horizontal=True) if role in ["superadmin", "district"] else "Block"
            financial_year = col_m2.selectbox("Financial Year", ["2026-27", "2027-28", "2028-29"])
            meeting_date = col_m3.date_input("Meeting Date", date.today())

            if meeting_type == "District":
                districts_fetch = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
                dist_dict = {d["district_name"]: d["id"] for d in districts_fetch}
                dist_sel = next((name for name, id in dist_dict.items() if id == user.get("district_id")), list(dist_dict.keys())[0])
                block_sel = None
                chair_default = "District Magistrate & District Programme Coordinator (DPC)"
                stat_users = [u for u in users_data if u['role'] == 'district' and str(u.get('district_id')) == str(dist_dict[dist_sel])]
            else:
                block_sel = block_dict_reverse.get(user["block_id"], "Unknown Block") if role == "block" else st.selectbox("Block Jurisdiction", [b["block_name"] for b in blocks_data])
                dist_sel = next(b["district_id"] for b in blocks_data if b["block_name"] == block_sel) if role != "block" else user["district_id"]
                chair_default = "Block Development Officer (BDO)"
                block_id_sel = next(b["id"] for b in blocks_data if b["block_name"] == block_sel)
                stat_users = [u for u in users_data if u['role'] == 'block' and str(u.get('block_id')) == str(block_id_sel)]

            st.markdown(f"#### 🏛️ Statutory Officials for {meeting_type} Jurisdiction")
            if stat_users:
                st.info(", ".join([f"{u['full_name']}" for u in stat_users]))
            else:
                st.warning("No statutory administrative users found for this jurisdiction in the directory.")

            with st.form("schedule_meeting_form"):
                c_a1, c_a2 = st.columns(2)
                chairperson = c_a1.text_input("Chairperson (Name & Designation)", value=chair_default)
                venue = c_a2.text_input("Venue / Platform")
                objective = st.text_input("Meeting Objective / Schematic Discussion")

                st.markdown("### 📋 Department / Wing Selection")
                st.caption("Select the Departments or Wings required for this meeting. You will assign specific officials during attendance.")
                invited_uids = st.multiselect("Invited Departments / Wings*", options=[u["uid"] for u in unified_depts], format_func=lambda x: unified_uid_to_label.get(x, x))

                if st.form_submit_button("Schedule Meeting", type="primary"):
                    if not invited_uids:
                        st.error("Please invite at least one Department/Wing.")
                    else:
                        meeting_data = {
                            "meeting_type": meeting_type,
                            "financial_year": financial_year,
                            "meeting_date": str(meeting_date),
                            "chairperson": chairperson,
                            "venue": venue,
                            "objective": objective,
                            "attendees": invited_uids, 
                            "status": "Scheduled",
                            "created_by": user["id"],
                        }
                        if meeting_type == "District":
                            meeting_data["district_id"] = dist_dict[dist_sel] if role != "district" else user["district_id"]
                        else:
                            block_obj = next(b for b in blocks_data if b["block_name"] == block_sel)
                            meeting_data["block_id"] = block_obj["id"]
                            meeting_data["district_id"] = block_obj["district_id"]

                        result = supabase.table("meetings").insert(meeting_data).execute()
                        st.success("✅ Meeting Scheduled successfully!")
                        st.rerun()

    # ======================== TAB 3: RECORD PROCEEDINGS ========================
    with tab3:
        st.subheader("✍️ 2. Record & Print Proceedings")
        
        if df_meetings.empty:
            st.info("No meetings available.")
        else:
            sched_meetings = df_meetings[df_meetings["status"] == "Scheduled"]
            proc_sel = st.selectbox(
                "Select Meeting to Record / Print",
                df_meetings["id"].tolist(),
                format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['meeting_type'].values[0]} ({df_meetings[df_meetings['id'] == x]['status'].values[0]})"
            )

            proc_mtg = df_meetings[df_meetings["id"] == proc_sel].iloc[0]
            is_locked = proc_mtg.get("status") == "Convened"
            safe_proc_sel = safe_int(proc_sel)

            # --- PRINT / DOWNLOAD PROCEEDINGS BUTTON ---
            st.markdown("---")
            
            att_data = proc_mtg.get("detailed_attendance") or []
            attendance_html = "<table class='print-table'><tr><th>Department / Wing</th><th>Registered Officials Attended</th><th>Other / Subordinate Attendees</th></tr>"
            if att_data and isinstance(att_data, list):
                for att in att_data:
                    dept_name = att.get("label", "Unknown")
                    reg_off = ", ".join([user_dict[u_id]['full_name'] for u_id in att.get("attended_users", []) if u_id in user_dict]) if att.get("attended_users") else "None"
                    sub_off = att.get("subordinate_text", "None")
                    attendance_html += f"<tr><td><b>{dept_name}</b></td><td>{reg_off}</td><td>{sub_off}</td></tr>"
                attendance_html += "</table>"
            else:
                attendance_html = "<p>No detailed attendance recorded.</p>"

            mtg_ap = df_ap[df_ap['meeting_id'] == proc_sel] if not df_ap.empty else pd.DataFrame()
            if not mtg_ap.empty:
                print_df = mtg_ap[["Department / Wing", "action_point", "target", "status", "remarks"]].copy()
                print_df.columns = ["Department / Wing", "Resolution / Commitment", "Target", "Status", "Outcome / Remarks"]
                html_table = print_df.to_html(index=False, classes="print-table")
            else:
                html_table = "<p>No resolutions recorded.</p>"

            printable_html = f"""<!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>Meeting Proceedings - {proc_mtg['meeting_date']}</title>
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
                            <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background: #1F77B4; color: white; border: none; border-radius: 5px;">🖨️ Print Proceedings Document</button>
                        </div>
                        <h2>Convergence Meeting Proceedings ({proc_mtg['status'].upper()})</h2>
                        <div class="meta-info">
                            <strong>Date:</strong> {proc_mtg['meeting_date']} <br>
                            <strong>Level:</strong> {proc_mtg['meeting_type']} Level <br>
                            <strong>Chairperson:</strong> {proc_mtg['chairperson']} <br>
                            <strong>Objective:</strong> {proc_mtg['objective']} <br>
                            <strong>General Minutes:</strong> {proc_mtg.get('decisions', 'None recorded')}
                        </div>
                        <h3>Registered Attendance</h3>
                        {attendance_html}
                        <h3>Department-wise Progress & Commitments</h3>
                        {html_table}
                    </body>
                    </html>
                    """
            b64_html = base64.b64encode(printable_html.encode("utf-8")).decode("utf-8")
            st.markdown(f'<a href="data:text/html;base64,{b64_html}" download="Proceedings_{proc_mtg["meeting_date"]}.html" class="print-btn">🖨️ Print / Download Proceedings Document</a>', unsafe_allow_html=True)
            st.markdown("---")

            # --- A. DEPARTMENT-WISE ATTENDANCE (Linked to User Directory) ---
            with st.expander("👥 A. Mark Department-Wise Attendance (Linked to Users)", expanded=not is_locked):
                invited_uids = proc_mtg.get("attendees") or []
                if not invited_uids:
                    st.warning("No departments were invited.")
                else:
                    if is_locked or role == "department":
                        st.info("Read-only Attendance View")
                        if att_data:
                            adf = pd.DataFrame(att_data)[["label", "attended_users", "subordinate_text"]]
                            adf["Registered Officials"] = adf["attended_users"].apply(lambda x: ", ".join([user_dict[i]['full_name'] for i in x if i in user_dict]) if isinstance(x, list) else "None")
                            st.dataframe(adf[["label", "Registered Officials", "subordinate_text"]], hide_index=True)
                    else:
                        detailed_attendance_payload = []
                        existing_att_map = {a['uid']: a for a in (proc_mtg.get("detailed_attendance") or [])}

                        with st.container():
                            for uid in invited_uids:
                                label = unified_uid_to_label.get(uid, "Unknown")
                                parts = str(uid).split("_")
                                d_id = safe_int(parts[0])
                                w_id = safe_int(parts[1]) if len(parts) > 1 else None
                                
                                # Fetch any user linked to this Dept/Wing, regardless of their 'role' (District Admin, Dept User, etc)
                                dept_users = [u for u in users_data if safe_int(u.get('department_id')) == d_id and safe_int(u.get('wing_id')) == w_id]
                                user_options = {u['id']: f"{u['full_name']}" for u in dept_users}

                                st.markdown(f"**🏛️ {label}**")
                                is_present = st.checkbox("Department Present?", value=True, key=f"pres_{uid}_{proc_sel}")
                                
                                att_users = []
                                sub_txt = ""
                                
                                if is_present:
                                    prev_users = existing_att_map.get(uid, {}).get("attended_users", [])
                                    valid_prev = [u for u in prev_users if u in user_options]
                                    
                                    att_users = st.multiselect("Registered Officials Attended", options=list(user_options.keys()), default=valid_prev, format_func=lambda x: user_options[x], key=f"att_users_{uid}_{proc_sel}")
                                    
                                    prev_sub = existing_att_map.get(uid, {}).get("subordinate_text", "")
                                    sub_txt = st.text_input("Other / Subordinate Attendees (Names)", value=prev_sub, key=f"sub_txt_{uid}_{proc_sel}")
                                    
                                    detailed_attendance_payload.append({
                                        "uid": uid,
                                        "label": label,
                                        "attended_users": att_users,
                                        "subordinate_text": sub_txt
                                    })
                                st.markdown("<hr style='margin: 10px 0; opacity: 0.2;'>", unsafe_allow_html=True)
                                    
                            if st.button("💾 Save Draft Attendance", type="primary"):
                                supabase.table("meetings").update({"detailed_attendance": detailed_attendance_payload}).eq("id", safe_proc_sel).execute()
                                st.success("✅ Attendance saved successfully.")
                                st.rerun()

            # --- B. REVIEW PREVIOUS RESOLUTIONS ---
            with st.expander("🔄 B. Review Previous Resolutions", expanded=False):
                if df_ap.empty:
                    st.info("No past resolutions to review.")
                else:
                    past_aps = df_ap[df_ap['meeting_id'] != proc_sel].copy()
                    if not past_aps.empty:
                        disp_cols = ["Origin Meeting", "Department / Wing", "action_point", "Tracker Flag", "status"]
                        st.dataframe(past_aps[disp_cols].sort_values('Tracker Flag'), use_container_width=True, hide_index=True)
                    else:
                        st.info("No previous meeting resolutions found.")

            # --- C. REVIEW DEPARTMENT TARGETS & PROGRESS ---
            with st.expander("📊 C. Review Department Targets & Progress", expanded=False):
                dist_id_val = safe_int(proc_mtg["district_id"])
                q_targets = supabase.table("department_targets").select("*").eq("district_id", dist_id_val)
                q_reg = supabase.table("convergence_register").select("department_id, activity_description, current_status").eq("district_id", dist_id_val)
                
                if proc_mtg["meeting_type"] == "Block":
                    block_id_val = safe_int(proc_mtg["block_id"])
                    q_reg = q_reg.eq("block_id", block_id_val)
                    
                t_data = q_targets.execute().data
                r_data = q_reg.execute().data
                
                if t_data:
                    df_t = pd.DataFrame(t_data)
                    df_r = pd.DataFrame(r_data) if r_data else pd.DataFrame()
                    comp_data = []
                    for idx, row in df_t.iterrows():
                        d_id = row['department_id']
                        act = row['activity']
                        t_val = int(row['desired_target'])
                        
                        e_count = 0
                        if not df_r.empty:
                            dept_r = df_r[df_r['department_id'] == d_id]
                            if 'activity_description' in dept_r.columns:
                                e_count = dept_r['activity_description'].apply(lambda x: str(act).lower() in str(x).lower()).sum()
                        
                        ach_pct = (e_count / t_val * 100) if t_val > 0 else 0
                        gap = t_val - e_count
                        stat = "Achieved" if gap <= 0 else "Review" if ach_pct > 50 else "Critical Delay"
                        
                        comp_data.append({
                            "Department": dept_map.get(d_id, "Unknown"),
                            "Activity / Indicator": act,
                            "Target": t_val,
                            "Achievement": e_count,
                            "% Achievement": f"{ach_pct:.1f}%",
                            "Target Gap": gap if gap > 0 else 0,
                            "Status": stat
                        })
                        
                    df_comp = pd.DataFrame(comp_data)
                    def style_targets(row):
                        if row['Status'] == "Critical Delay": return ['background-color: #ffebee; color: #b71c1c;'] * len(row)
                        if row['Status'] == "Review": return ['background-color: #fff3e0; color: #e65100;'] * len(row)
                        return ['background-color: #e8f5e9; color: #1b5e20;'] * len(row)
                    st.dataframe(df_comp.style.apply(style_targets, axis=1), use_container_width=True, hide_index=True)
                else:
                    st.info("No live targets captured in the database for this jurisdiction.")

            # --- D. MINUTES & DEPARTMENT-WISE RESOLUTIONS ---
            with st.expander("📝 D. Minutes & Department-Wise Resolutions", expanded=not is_locked):
                general_minutes = st.text_area("Meeting Minutes / Observations", value=proc_mtg.get("decisions", "") or "", disabled=is_locked or role=="department")
                
                if not is_locked and role != "department":
                    if st.button("💾 Save Draft Minutes", key=f"btn_mins_{proc_sel}"):
                        supabase.table("meetings").update({"decisions": general_minutes}).eq("id", safe_proc_sel).execute()
                        st.success("Draft Minutes saved.")

                    st.markdown("---")
                    st.markdown("#### Assign New Resolution / Action Point")

                    with st.container(border=True):
                        c_r1, c_r2 = st.columns(2)
                        res_dept_label = c_r1.selectbox("Assign to Department / Wing*", dept_labels, key=f"r_dept_{proc_sel}")
                        selected_opt = next(opt for opt in unified_depts if opt['label'] == res_dept_label)
                        res_dept_id = selected_opt['dept_id']
                        res_wing_id = selected_opt['wing_id']

                        mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == res_dept_id]
                        valid_act_names = ["General / Administrative"] + [a['activity_name'] for a in activities_data if a['id'] in mapped_act_ids]
                        
                        res_scheme = c_r2.selectbox("Scheme / Activity Linkage", valid_act_names, key=f"r_sch_{proc_sel}")
                        res_issue = st.text_input("Issue / Discussion", key=f"r_iss_{proc_sel}")
                        res_resolution = st.text_area("Resolution / Directives Given*", key=f"r_res_{proc_sel}")
                        res_outcome = st.text_input("Expected Outcome", key=f"r_out_{proc_sel}")

                        c_r3, c_r4, c_r5 = st.columns(3)
                        res_status = c_r3.selectbox("Current Status", ["Not Started", "On Track"], key=f"r_stat_{proc_sel}")
                        res_priority = c_r4.selectbox("Priority", ["High", "Medium", "Low"], index=1, key=f"r_pri_{proc_sel}")
                        res_deadline = c_r5.date_input("Target Date", date.today(), key=f"r_dl_{proc_sel}")
                        atr_req = st.checkbox("ATR Required?", value=True, key=f"r_atr_{proc_sel}")

                        if st.button("Add Resolution to Tracker", type="primary", key=f"btn_add_{proc_sel}"):
                            if not res_resolution.strip():
                                st.error("Resolution directive cannot be empty.")
                            else:
                                packed_action_point = f"[{res_scheme}] {res_resolution.strip()}"
                                packed_remarks = f"Issue: {res_issue} | Expected: {res_outcome} | ATR Req: {atr_req}"
                                
                                res_payload = {
                                    "meeting_id": safe_proc_sel,
                                    "department_id": res_dept_id,
                                    "wing_id": res_wing_id,
                                    "action_point": packed_action_point,
                                    "deadline": str(res_deadline),
                                    "status": res_status,
                                    "priority": res_priority,
                                    "remarks": packed_remarks
                                }
                                try:
                                    supabase.table("meeting_action_points").insert(res_payload).execute()
                                    st.success("✅ Resolution added successfully!")
                                    st.rerun()
                                except Exception as e:
                                    try:
                                        res_payload["status"] = res_status.lower().replace(" ", "_")
                                        res_payload["priority"] = res_priority.lower()
                                        supabase.table("meeting_action_points").insert(res_payload).execute()
                                        st.success("✅ Resolution added successfully!")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Error adding resolution: {err}")
                
                curr_mtg_aps = df_ap[df_ap['meeting_id'] == proc_sel] if not df_ap.empty else pd.DataFrame()
                if not curr_mtg_aps.empty:
                    st.markdown("##### Resolutions Recorded for this Meeting:")
                    st.dataframe(curr_mtg_aps[["Department / Wing", "action_point", "deadline", "Tracker Flag"]], use_container_width=True, hide_index=True)

            # --- E. LOCK PROCEEDINGS ---
            if not is_locked and role in ["superadmin", "district", "block"]:
                st.markdown("---")
                if st.button("🔒 Complete Proceedings & Mark as Convened", type="primary", use_container_width=True, key=f"btn_lock_{proc_sel}"):
                    supabase.table("meetings").update({"status": "Convened", "decisions": general_minutes}).eq("id", safe_proc_sel).execute()
                    st.success("Meeting locked and Convened! Proceedings are now read-only.")
                    st.rerun()

    # ======================== TAB 4: ADVANCED RESOLUTION TRACKER ========================
    with tab4:
        st.subheader("🎯 Advanced Resolution Tracker")
        if df_ap.empty:
            st.info("No action points found.")
        else:
            c_f1, c_f2 = st.columns(2)
            f_dept = c_f1.selectbox("Filter by Department", ["All"] + dept_labels)
            f_flag = c_f2.selectbox("Filter by Flag", ["All", "🟢 CLOSED", "🔴 OVERDUE", "🟡 DUE TODAY", "🔵 ON TRACK", "🟠 FOR REVIEW", "⚪ NOT STARTED"])
            
            filtered_df = df_ap.copy()
            if f_dept != "All": filtered_df = filtered_df[filtered_df["Department / Wing"] == f_dept]
            if f_flag != "All": filtered_df = filtered_df[filtered_df["Tracker Flag"] == f_flag]

            display_cols = ["Origin Meeting", "Department / Wing", "action_point", "deadline", "Tracker Flag", "status", "remarks"]
            st.dataframe(filtered_df[display_cols].sort_values("Tracker Flag"), use_container_width=True, hide_index=True)

            st.markdown("### ✏️ Action Taken Report (ATR) Update")
            with st.form("global_update_atr"):
                c_u1, c_u2 = st.columns(2)
                ap_id = c_u1.selectbox("Select Resolution ID to Update", filtered_df["id"].tolist())
                new_ap_status = c_u2.selectbox("Update Status", ["Not Started", "On Track", "Completed", "Not Feasible (Requires Review)", "Dropped"])
                atr_remarks = st.text_area("ATR / Latest Progress")
                
                safe_ap_id = safe_int(ap_id)

                if st.form_submit_button("Submit ATR Update", type="primary"):
                    try:
                        supabase.table("meeting_action_points").update({"status": new_ap_status, "remarks": atr_remarks}).eq("id", safe_ap_id).execute()
                        st.success("✅ ATR updated successfully.")
                        st.rerun()
                    except:
                        supabase.table("meeting_action_points").update({"status": new_ap_status.lower().replace(" ", "_"), "remarks": atr_remarks}).eq("id", safe_ap_id).execute()
                        st.success("✅ ATR updated successfully.")
                        st.rerun()

    # ======================== TAB 5: REPORTS ========================
    with tab5:
        st.subheader("🖨️ Reports & Registers")
        st.info("Select a meeting from Tab 3 (Record Proceedings) to view its detailed layout and trigger the Print command.")
        if not df_ap.empty:
            st.download_button("📥 Download Master Resolution Tracker (Excel)", data=df_ap.to_csv(index=False).encode('utf-8'), file_name="resolution_tracker.csv", mime="text/csv")

    # ======================== TAB 6: NEXT AGENDA PREP ========================
    with tab6:
        st.subheader("⏭️ Auto-Generated Next Meeting Agenda")
        
        agenda_text = "AGENDA FOR UPCOMING MEETING:\n\n"
        has_items = False
        
        user_dist_id = safe_int(user["district_id"])

        q_targets = supabase.table("department_targets").select("*").eq("district_id", user_dist_id)
        t_data = q_targets.execute().data
        if t_data:
            df_t = pd.DataFrame(t_data)
            q_reg = supabase.table("convergence_register").select("department_id, activity_description").eq("district_id", user_dist_id)
            df_r = pd.DataFrame(q_reg.execute().data) if q_reg.execute().data else pd.DataFrame()
            
            low_targets = ""
            for idx, row in df_t.iterrows():
                d_id = row['department_id']
                act = row['activity']
                t_val = int(row['desired_target'])
                e_count = df_r[df_r['department_id'] == d_id]['activity_description'].apply(lambda x: str(act).lower() in str(x).lower()).sum() if not df_r.empty and 'activity_description' in df_r[df_r['department_id'] == d_id].columns else 0
                
                if t_val > 0 and (e_count / t_val) < 0.5:
                    d_name = dept_map.get(d_id, 'Unknown')
                    low_targets += f"- [{d_name}] {act}: Target {t_val} | Achieved: {e_count} (Critical Deficit)\n"
            
            if low_targets:
                has_items = True
                agenda_text += "📊 1. REVIEW OF LOW TARGET ACHIEVEMENT:\n" + low_targets + "\n"

        if not df_ap.empty:
            active_df = df_ap[~df_ap["Tracker Flag"].isin(["🟢 CLOSED"])]
            unfeasible_df = active_df[active_df["Tracker Flag"] == "🟠 FOR REVIEW"]
            overdue_df = active_df[active_df["Tracker Flag"] == "🔴 OVERDUE"]
            
            if not unfeasible_df.empty:
                has_items = True
                agenda_text += "🔴 2. ITEMS FLAGGED FOR REVIEW (NOT FEASIBLE):\n"
                for idx, row in unfeasible_df.iterrows():
                    agenda_text += f"- [{row['Department / Wing']}] {row['action_point']}\n  ATR: {row.get('remarks', 'N/A')}\n\n"

            if not overdue_df.empty:
                has_items = True
                agenda_text += "🚨 3. OVERDUE COMMITMENTS:\n"
                for idx, row in overdue_df.iterrows():
                    agenda_text += f"- [{row['Department / Wing']}] {row['action_point']}\n"

        if has_items:
            st.warning("⚠️ High-priority items successfully compiled for the next agenda.")
            st.text_area("Copy Agenda Text:", value=agenda_text, height=400)
        else:
            st.success("🎉 No overdue items or severe target gaps detected for the next meeting!")
