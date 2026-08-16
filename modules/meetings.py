from datetime import date, datetime
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from auth.auth import require_role, get_current_user
from utils.db import get_supabase
from utils.audit import log_action

def sanitize_payload(obj):
    """Deeply sanitizes payloads to convert NumPy types to native Python types, preventing JSON serialization crashes."""
    if isinstance(obj, dict):
        return {k: sanitize_payload(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_payload(i) for i in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif pd.isna(obj):
        return None
    return obj

def safe_int(val):
    if pd.isna(val) or val is None or val == '': 
        return 0
    try: 
        return int(float(val))
    except (ValueError, TypeError): 
        return 0

def generate_res_no(row):
    """Generates a stable, unique resolution number based on the DB ID."""
    val = str(row.get('id', ''))
    if "-" in val: # UUID format
        return f"RES-{val.split('-')[0].upper()}"
    else: # Integer format or unexpected string
        try: return f"RES-{int(val):04d}"
        except: return f"RES-{val.upper()[:8]}"

def render_print_preview(html_content):
    """Renders HTML inside an iframe with a native print button, bypassing all download requirements."""
    wrapped_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Print Document</title>
        <style>
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0 !important; margin: 0 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                .page-break {{ page-break-after: always; }}
            }}
            body {{ font-family: 'Times New Roman', Times, serif; padding: 20px; font-size: 13px; color: #000; line-height: 1.5; }}
            .print-toolbar {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; text-align: center; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .print-btn {{ padding: 10px 24px; font-size: 16px; font-weight: bold; background-color: #0F4C81; color: white; border: none; border-radius: 6px; cursor: pointer; transition: background 0.3s; }}
            .print-btn:hover {{ background-color: #0b3960; }}
            .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }}
            tr {{ page-break-inside: avoid; page-break-after: auto; }}
            th, td {{ border: 1px solid #000; padding: 8px; text-align: left; font-size: 12px; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            h3, h4 {{ margin-bottom: 5px; }}
        </style>
    </head>
    <body>
        <div class="no-print print-toolbar">
            <h4 style="margin-top: 0; color: #333; font-family: Arial, sans-serif;">📄 Document Print Preview</h4>
            <button class="print-btn" onclick="window.print()">🖨️ Print Document directly</button>
        </div>
        <div id="print-content">
            {html_content}
        </div>
    </body>
    </html>
    """
    components.html(wrapped_html, height=800, scrolling=True)

def show():
    # 1. ENFORCE SECURITY & ACCESS RULES
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()
    today = pd.to_datetime(date.today())
    active_fy = st.session_state.get("selected_fy", "2026-27")

    # SESSION STATE MANAGEMENT FOR RELIABLE VERIFIED NOTIFICATIONS
    if "temp_officials" not in st.session_state: st.session_state.temp_officials = []
    if "mtg_msg" not in st.session_state: st.session_state.mtg_msg = None
    if "mtg_msg_type" not in st.session_state: st.session_state.mtg_msg_type = None

    def set_msg(msg_type, msg_text):
        st.session_state.mtg_msg_type = msg_type
        st.session_state.mtg_msg = msg_text

    def display_persisted_msg():
        if st.session_state.mtg_msg:
            if st.session_state.mtg_msg_type == "success": st.success(st.session_state.mtg_msg)
            elif st.session_state.mtg_msg_type == "error": st.error(st.session_state.mtg_msg)
            elif st.session_state.mtg_msg_type == "warning": st.warning(st.session_state.mtg_msg)
            st.session_state.mtg_msg = None
            st.session_state.mtg_msg_type = None

    # BREADCRUMB & HEADER
    st.markdown("<div style='font-size: 0.85rem; color: #64748B; margin-bottom: 0.5rem;'>Home / Statutory Governance / Convergence Meetings</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom: 0px; color: #0F4C81;'>🤝 Statutory Meeting Governance & Resolution Tracker</h2>", unsafe_allow_html=True)
    st.caption(f"FY {active_fy} | Coordinate Committee Meetings, Record Proceedings, Synchronize ATRs, and Generate Agendas.")
    st.markdown("---")

    # MASTER DATA LOOKUPS
    departments = supabase.table("departments").select("id, department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data or []
    activities_data = supabase.table("activities").select("id, activity_name").eq("active", True).execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("activity_id, department_id").execute().data or []
    designations_data = supabase.table("designations").select("id, designation_name").eq("active", True).execute().data or []
    contacts_query = supabase.table("contacts").select("*, designations(designation_name)").eq("active", True).execute()
    contacts_data = contacts_query.data or []

    dept_map = {d["id"]: d["department_name"] for d in departments}
    wing_map = {w["id"]: w for w in wings}
    block_dict_reverse = {b["id"]: b["block_name"] for b in blocks_data}
    designation_map = {d["designation_name"]: d["id"] for d in designations_data}

    unified_depts = []
    for d in departments:
        unified_depts.append({"uid": f"{d['id']}_main", "label": f"{d['department_name']} (Main Department)", "dept_id": d["id"], "wing_id": None})
    for w in wings:
        unified_depts.append({"uid": f"{w['department_id']}_{w['id']}", "label": f"{dept_map.get(w['department_id'])} ➔ {w['wing_name']} [{w['entity_type']}]", "dept_id": w["department_id"], "wing_id": w["id"]})

    unified_depts = sorted(unified_depts, key=lambda x: x["label"])
    unified_uid_to_label = {u["uid"]: u["label"] for u in unified_depts}
    dept_labels = [u["label"] for u in unified_depts]

    def format_dept_display(row):
        d_name = dept_map.get(row.get("department_id"), "Unknown")
        w_id = row.get("wing_id")
        if w_id and not pd.isna(w_id) and str(w_id).strip() != '' and str(w_id).lower() != 'none':
            if w_id in wing_map: return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
        return f"{d_name} (Main)"

    # DATA FETCHING
    q_meetings = supabase.table("meetings").select("*").eq("financial_year", active_fy)
    if role in ["district", "department"]: q_meetings = q_meetings.eq("district_id", user["district_id"])
    elif role == "block": q_meetings = q_meetings.eq("block_id", user["block_id"])
    meetings = q_meetings.order("meeting_date", desc=True).execute().data or []
    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()

    ap_data = supabase.table("meeting_action_points").select("*").execute().data or []
    df_ap = pd.DataFrame(ap_data) if ap_data else pd.DataFrame()

    if not df_ap.empty:
        # VISUAL HARD-DELETE: Purge Dropped/Cancelled commitments from the Global Feed entirely.
        df_ap = df_ap[~df_ap['status'].astype(str).str.lower().isin(['dropped', 'cancelled', 'deleted'])]

    if not df_ap.empty:
        if role == "department":
            dep_id = user.get('department_id')
            w_id = user.get('wing_id')
            if dep_id:
                df_ap = df_ap[df_ap['department_id'].astype(str) == str(dep_id)]
                if w_id and str(w_id).strip() != '' and str(w_id).lower() != 'none':
                    df_ap = df_ap[
                        (df_ap['wing_id'].astype(str) == str(w_id)) | 
                        (df_ap['wing_id'].isna()) | 
                        (df_ap['wing_id'] == '') | 
                        (df_ap['wing_id'].astype(str).str.lower() == 'none')
                    ]
        elif role == "block" and user.get("block_id"):
            block_meet_ids = [m['id'] for m in meetings if m.get('block_id') == user["block_id"]]
            df_ap = df_ap[df_ap['meeting_id'].isin(block_meet_ids)]
        elif role == "district" and user.get("district_id"):
            dist_meet_ids = [m['id'] for m in meetings if m.get('district_id') == user["district_id"]]
            df_ap = df_ap[df_ap['meeting_id'].isin(dist_meet_ids)]

        if not df_ap.empty:
            df_ap["Department / Wing"] = df_ap.apply(format_dept_display, axis=1)
            meeting_lookup_map = {m["id"]: f"{m['meeting_date']} ({m['meeting_type']})" for m in meetings}
            df_ap["Origin Meeting"] = df_ap["meeting_id"].map(meeting_lookup_map).fillna("District/Block Meeting")
            df_ap["deadline"] = pd.to_datetime(df_ap["deadline"], errors="coerce")
            df_ap["Resolution No."] = df_ap.apply(generate_res_no, axis=1)

            # Duplicate Flagging
            dupes = df_ap.duplicated(subset=['meeting_id', 'department_id', 'action_point'], keep=False)
            if dupes.any(): df_ap.loc[dupes, "Resolution No."] = "⚠️ " + df_ap.loc[dupes, "Resolution No."]

            def get_flag(row):
                stat = str(row.get("status", "")).lower()
                if stat in ["completed", "closed"]: return "🟢 CLOSED"
                if "feasible" in stat or "review" in stat: return "🟠 FOR REVIEW"
                if "not started" in stat: return "⚪ NOT STARTED"
                if pd.isna(row["deadline"]): return "🔵 ON TRACK"
                days_rem = (row["deadline"] - today).days
                if days_rem < 0: return "🔴 OVERDUE"
                if days_rem == 0: return "🟡 DUE TODAY"
                return "🔵 ON TRACK"

            df_ap["Tracker Flag"] = df_ap.apply(get_flag, axis=1)

    # HTML GENERATOR HELPER FOR REUSABILITY
    def generate_meeting_html(p_mtg, p_aps, doc_type):
        org_label = "District Administration" if p_mtg.get('meeting_type') == 'District' else f"Block Development Office"
        def get_header(title):
            return f"""<div class="header"><h3>VB-G RAM G CONVERGENCE PORTAL<br>{org_label}</h3><h4>{title}</h4><div>Financial Year: {active_fy} | Meeting Date: {p_mtg.get('meeting_date', '')}</div></div>"""

        att_data = p_mtg.get("detailed_attendance") or []
        indiv_att = [a for a in att_data if a.get("type", "individual") == "individual"]
        dept_att = [a for a in att_data if a.get("type") == "department"]

        # Notice HTML
        notice_html = get_header('MEETING NOTICE') + f"<p><b>Venue:</b> {p_mtg.get('venue', 'Not Recorded')}</p><p><b>Chairperson:</b> {p_mtg.get('chairperson', 'Not Recorded')}</p><p><b>Objective:</b> {p_mtg.get('objective', 'Standard Convergence Review')}</p><p style='margin-top:20px;'>The undersigned is directed to invite the following officials and departments to attend the statutory meeting at the scheduled venue and time.</p>"
        if indiv_att:
            notice_html += "<h4>INVITED OFFICIALS</h4><table><thead><tr><th>Sl. No.</th><th>Name</th><th>Designation</th><th>Posting Level</th><th>Department</th><th>Wing</th><th>Mobile</th><th>Email</th></tr></thead><tbody>"
            for idx, off in enumerate(indiv_att, 1):
                if off.get('posting_level') == "Substitute": continue
                notice_html += f"<tr><td>{idx}</td><td>{off.get('name','')}</td><td>{off.get('designation','')}</td><td>{off.get('posting_level','')}</td><td>{off.get('department','')}</td><td>{off.get('wing','')}</td><td>{off.get('mobile','')}</td><td>{off.get('email','')}</td></tr>"
            notice_html += "</tbody></table>"
        if dept_att:
            notice_html += "<h4 style='margin-top:20px;'>DEPARTMENT / WING INVITATIONS</h4><table><thead><tr><th>Sl. No.</th><th>Department</th><th>Wing / Division</th></tr></thead><tbody>"
            for idx, dept in enumerate(dept_att, 1): notice_html += f"<tr><td>{idx}</td><td>{dept.get('department', '')}</td><td>{dept.get('wing', '')}</td></tr>"
            notice_html += "</tbody></table>"
        notice_html += '<div style="margin-top: 50px; text-align: right;"><b>Chairperson / Nodal Officer</b></div>'

        # Attendance HTML
        att_html = get_header('ATTENDANCE REGISTER')
        if indiv_att:
            att_html += "<h4>NAME-WISE ATTENDANCE</h4><table><thead><tr><th>Sl. No.</th><th>Name</th><th>Designation</th><th>Department</th><th>Wing</th><th>Attendance Status</th></tr></thead><tbody>"
            for idx, att in enumerate(indiv_att, 1): att_html += f"<tr><td>{idx}</td><td>{att.get('name', '')}</td><td>{att.get('designation', '')}</td><td>{att.get('department', '')}</td><td>{att.get('wing', '')}</td><td><b>{att.get('attendance', '') if att.get('attendance') != 'Pending' else ''}</b></td></tr>"
            att_html += "</tbody></table>"
        if dept_att:
            att_html += "<h4 style='margin-top:20px;'>DEPARTMENT-WISE ATTENDANCE</h4><table><thead><tr><th>Sl. No.</th><th>Department</th><th>Wing</th><th>Attendance Status</th></tr></thead><tbody>"
            for idx, att in enumerate(dept_att, 1): att_html += f"<tr><td>{idx}</td><td>{att.get('department', '')}</td><td>{att.get('wing', '')}</td><td><b>{att.get('attendance', '') if att.get('attendance') != 'Pending' else ''}</b></td></tr>"
            att_html += "</tbody></table>"

        # Proceedings HTML
        proc_html = get_header('PROCEEDINGS & RESOLUTIONS') + f"<p><b>Chairperson:</b> {p_mtg.get('chairperson')}</p><p><b>Minutes:</b><br>{p_mtg.get('decisions', 'Not Recorded / Draft')}</p><h4>Mandated Resolutions (Department-Wise):</h4>"
        if not p_aps.empty:
            proc_html += "<table><thead><tr><th>No.</th><th>Res No.</th><th>Department / Wing</th><th>Directive / Action Point</th><th>Deadline</th><th>Status</th></tr></thead><tbody>"
            for idx, row in enumerate(p_aps.to_dict(orient="records"), 1): 
                row_res_no = generate_res_no(row)
                proc_html += f"<tr><td>{idx}</td><td><b>{row_res_no}</b></td><td>{row.get('Department / Wing')}</td><td>{row.get('action_point')}</td><td>{row.get('deadline').strftime('%Y-%m-%d') if pd.notna(row.get('deadline')) else 'N/A'}</td><td>{row.get('status')}</td></tr>"
            proc_html += "</tbody></table>"
        else: proc_html += "<p>No resolutions recorded.</p>"

        if doc_type == "Meeting Notice & Invited List": return notice_html
        elif doc_type == "Attendance Register": return att_html
        elif doc_type == "Proceedings & Resolutions": return proc_html
        elif doc_type == "Complete Meeting File": return f"{notice_html}<div class='page-break'></div>{att_html}<div class='page-break'></div>{proc_html}"
        return ""

    # =====================================================================
    # TAB ARCHITECTURE: EXPLICIT MAPPING
    # =====================================================================
    if role == "department":
        tab_sla, tab_tracker, tab_print = st.tabs(["📈 SLA Performance", "🎯 Action Tracker & ATR", "🖨️ Print Centre"])
        tab_sched = tab_proc = tab_agenda = None
    else:
        tab_sla, tab_sched, tab_proc, tab_tracker, tab_agenda, tab_print = st.tabs([
            "📈 SLA Performance", "🗓️ Schedule Notice", "✍️ Attendance & Proceedings", 
            "🎯 Action Tracker & ATR", "⏭️ Next Agenda Prep", "🖨️ Print Centre"
        ])

    # =====================================================================
    # TAB 1: SLA PERFORMANCE DASHBOARD
    # =====================================================================
    with tab_sla:
        if df_ap.empty:
            st.info(f"No meeting commitments recorded for FY {active_fy}.")
        else:
            col_dash1, col_dash2 = st.columns(2, gap="large")
            with col_dash1:
                st.markdown("#### 🏢 Department Compliance Matrix")
                dept_perf = df_ap.groupby("Department / Wing").agg(Total=('id', 'count'), Closed=('Tracker Flag', lambda x: (x == '🟢 CLOSED').sum())).reset_index()
                dept_perf['Total'] = pd.to_numeric(dept_perf['Total'], errors='coerce').fillna(0)
                dept_perf['Closed'] = pd.to_numeric(dept_perf['Closed'], errors='coerce').fillna(0)
                dept_perf['Achievement %'] = (dept_perf['Closed'] / dept_perf['Total'].replace(0, 1) * 100).round(1).astype(str) + '%'
                st.dataframe(dept_perf, use_container_width=True, hide_index=True)
            with col_dash2:
                st.markdown("#### 📑 Meeting Execution Log")
                mtg_perf = df_ap.groupby("Origin Meeting").agg(Resolutions=('id', 'count'), Closed=('Tracker Flag', lambda x: (x == '🟢 CLOSED').sum())).reset_index()
                st.dataframe(mtg_perf, use_container_width=True, hide_index=True)

    # =====================================================================
    # TAB 2: SCHEDULE MEETING
    # =====================================================================
    if tab_sched:
        with tab_sched:
            st.markdown("#### 🗓️ Schedule Convergence Committee Meeting")
            st.caption("Mixed-Mode: Invite specific officials if registered, or generally invite the Department/Wing. You can also add first-time officials on the fly.")
            
            col_m1, col_m2, col_m3 = st.columns(3)
            meeting_type = col_m1.radio("Meeting Tier", ["District", "Block"], horizontal=True) if role in ["superadmin", "district"] else "Block"
            col_m2.text_input("Financial Year", value=active_fy, disabled=True)
            meeting_date = col_m3.date_input("Scheduled Date", date.today())

            if meeting_type == "District":
                districts_fetch = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
                dist_dict = {d["district_name"]: d["id"] for d in districts_fetch}
                dist_sel = next((name for name, id in dist_dict.items() if id == user.get("district_id")), list(dist_dict.keys())[0])
                chair_default = "District Magistrate & District Programme Coordinator (DPC)"
            else:
                block_sel = block_dict_reverse.get(user["block_id"], "Unknown Block") if role == "block" else st.selectbox("Block Jurisdiction", [b["block_name"] for b in blocks_data])
                dist_sel = next(b["district_id"] for b in blocks_data if b["block_name"] == block_sel) if role != "block" else user["district_id"]
                chair_default = "Block Development Officer (BDO)"
                
            c_a1, c_a2 = st.columns(2)
            chairperson = c_a1.text_input("Chairperson*", value=chair_default)
            venue = c_a2.text_input("Venue / Meeting Platform*")
            objective = st.text_input("Agenda / Schematic Objective*")
            
            st.markdown("##### 1. Select Participating Departments / Wings")
            invited_uids = st.multiselect("Select all departments mandated to attend", options=[u["uid"] for u in unified_depts], format_func=lambda x: unified_uid_to_label.get(x, x))
            
            final_named_officials = []
            final_general_depts = []
            target_district_id = dist_dict[dist_sel] if meeting_type == "District" else dist_sel
            target_block_id = next((b["id"] for b in blocks_data if b["block_name"] == block_sel), None) if meeting_type == "Block" else None

            if invited_uids:
                st.markdown("##### 2. Configure Invitations (Name-Wise & Department-Wise)")
                
                for uid in invited_uids:
                    st.markdown(f"**🔹 {unified_uid_to_label[uid]}**")
                    opt = next((u for u in unified_depts if u["uid"] == uid))
                    
                    matched_db = [c for c in contacts_data if c.get("department_id") == opt["dept_id"] and c.get("wing_id") == opt["wing_id"] and c.get("district_id") == target_district_id]
                    matched_temp = [t for t in st.session_state.temp_officials if t["dept_uid"] == uid]
                    all_matched = matched_db + matched_temp
                    
                    c_sel, c_gen = st.columns([2, 1])
                    selected_contacts = []
                    invite_dept_only = False

                    if all_matched:
                        options = {c["id"]: f"{c['full_name']} | {c.get('designations', {}).get('designation_name', c.get('designation',''))}" for c in all_matched}
                        selected_contacts = c_sel.multiselect(f"Select Registered Officials", options=list(options.keys()), format_func=lambda x: options[x], key=f"sel_{uid}")
                        if not selected_contacts:
                            invite_dept_only = c_gen.checkbox("Invite Department Generally instead", value=True, key=f"gen_{uid}")
                    else:
                        c_sel.warning("⚠️ No registered officials found. You may invite the department directly.")
                        invite_dept_only = c_gen.checkbox("Invite Department Generally", value=True, key=f"gen_{uid}")

                    if selected_contacts:
                        for cid in selected_contacts:
                            c = next((x for x in all_matched if x["id"] == cid))
                            wing_obj = wing_map.get(c.get("wing_id"))
                            final_named_officials.append({
                                "dept_uid": uid, "contact_id": c["id"], "name": c.get("full_name", ""),
                                "designation": c.get("designations", {}).get("designation_name", c.get("designation", "")),
                                "posting_level": c.get("office_level", "N/A"), "department": dept_map.get(c.get("department_id"), "N/A"),
                                "wing": wing_obj["wing_name"] if isinstance(wing_obj, dict) else (wing_obj if wing_obj else ""),
                                "mobile": c.get("contact_number", ""), "email": c.get("email_id", "")
                            })
                    elif invite_dept_only:
                        final_general_depts.append(uid)

                with st.expander("➕ Add First-Time Official (If not registered)"):
                    st.caption("Quickly add an official to participate in this meeting.")
                    if not designations_data:
                        st.error("⚠️ No active designations are available in Master Data. Please configure Designation Master before adding an official.")
                    else:
                        with st.form("new_off_form", clear_on_submit=True):
                            c_n1, c_n2 = st.columns(2)
                            n_dept_uid = c_n1.selectbox("Assign to Selected Department*", invited_uids, format_func=lambda x: unified_uid_to_label.get(x, x))
                            n_name = c_n2.text_input("Official Name*")
                            
                            c_n3, c_n4 = st.columns(2)
                            n_desig_name = c_n3.selectbox("Designation*", list(designation_map.keys()))
                            n_level = c_n4.selectbox("Posting Level*", ["State / Department", "District", "Sub Division", "Block", "Gram Panchayat"])
                            
                            c_n5, c_n6 = st.columns(2)
                            n_mobile = c_n5.text_input("Mobile Number")
                            n_email = c_n6.text_input("Email ID")
                            save_to_db = st.checkbox("☑ Save this official to Official Directory for future use", value=True)
                            
                            if st.form_submit_button("Add Official to Meeting", type="secondary"):
                                if not n_name: st.error("Official Name is required.")
                                else:
                                    opt = next((u for u in unified_depts if u["uid"] == n_dept_uid))
                                    temp_id = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                    new_off = {
                                        "id": temp_id, "dept_uid": n_dept_uid, "full_name": n_name, "designation": n_desig_name,
                                        "office_level": n_level, "department_id": opt["dept_id"], "wing_id": opt["wing_id"],
                                        "district_id": target_district_id, "block_id": target_block_id if n_level in ["Block", "Gram Panchayat"] else None,
                                        "contact_number": n_mobile, "email_id": n_email
                                    }
                                    if save_to_db:
                                        try:
                                            payload = {
                                                "full_name": n_name, "designation_id": designation_map[n_desig_name],
                                                "department_id": opt["dept_id"], "wing_id": opt["wing_id"], "office_level": n_level, 
                                                "district_id": target_district_id, "block_id": new_off["block_id"], 
                                                "contact_number": n_mobile, "email_id": n_email, "active": True
                                            }
                                            supabase.table("contacts").insert(sanitize_payload(payload)).execute()
                                            set_msg("success", f"Official {n_name} saved to directory and added to meeting.")
                                        except Exception as e:
                                            set_msg("warning", f"Could not save to directory ({e}), but official added to this meeting successfully.")
                                    st.session_state.temp_officials.append(new_off)
                                    st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Issue Meeting Notice", type="primary", use_container_width=True):
                    if not final_named_officials and not final_general_depts:
                        st.error("You must either select officials or invite departments generally.")
                    else:
                        initial_attendance = []
                        for off in final_named_officials: initial_attendance.append({**off, "type": "individual", "attendance": "Pending"})
                        for uid in final_general_depts:
                            opt = next((u for u in unified_depts if u["uid"] == uid), None)
                            d_name = dept_map.get(opt["dept_id"]) if opt else "Unknown"
                            w_name = wing_map.get(opt["wing_id"]) if opt and opt["wing_id"] else "Main Department"
                            if isinstance(w_name, dict): w_name = w_name.get("wing_name", "Main")
                            initial_attendance.append({"type": "department", "dept_uid": uid, "department": d_name, "wing": w_name, "attendance": "Pending"})

                        meeting_data = {
                            "meeting_type": meeting_type, "financial_year": active_fy, "meeting_date": str(meeting_date),
                            "chairperson": chairperson, "venue": venue, "objective": objective, "attendees": invited_uids,
                            "detailed_attendance": initial_attendance, "status": "Scheduled", "created_by": user["id"],
                            "district_id": target_district_id, "block_id": target_block_id
                        }
                        try:
                            supabase.table("meetings").insert(sanitize_payload(meeting_data)).execute()
                            st.session_state.temp_officials = [] 
                            set_msg("success", "✅ Meeting notice dispatched successfully! Packages auto-generated.")
                        except Exception as e:
                            set_msg("error", f"🚨 Failed to issue meeting notice. Database Error: {e}")
                        st.rerun()

    # =====================================================================
    # TAB 3: PROCEEDINGS, ATTENDANCE & VERIFIED LOCKING
    # =====================================================================
    if tab_proc:
        with tab_proc:
            display_persisted_msg() # Render robust session messages
            
            st.markdown("#### ✍️ Record Minutes, Attendance & Assign Directives")
            if df_meetings.empty:
                st.info(f"No meetings recorded for FY {active_fy}.")
            else:
                sched_meetings = df_meetings[df_meetings["status"] == "Scheduled"]
                proc_sel = st.selectbox(
                    "Select Meeting Workspace",
                    df_meetings["id"].tolist() if sched_meetings.empty else sched_meetings["id"].tolist(),
                    format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['meeting_type'].values[0]} ({df_meetings[df_meetings['id'] == x]['status'].values[0]})"
                )

                proc_mtg = df_meetings[df_meetings["id"] == proc_sel].iloc[0]
                is_locked = proc_mtg.get("status") == "Convened"
                p_aps_locked = df_ap[df_ap['meeting_id'] == proc_sel] if not df_ap.empty else pd.DataFrame()

                if is_locked:
                    # ---------------- LOCKED DASHBOARD ----------------
                    st.markdown("### 🔒 MEETING FINALIZED")
                    st.markdown(f"**Meeting ID:** {proc_mtg['id']} &nbsp;&nbsp;|&nbsp;&nbsp; **Date:** {proc_mtg['meeting_date']} &nbsp;&nbsp;|&nbsp;&nbsp; **Status:** Convened")
                    st.markdown("Attendance &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✓ Saved<br>Proceedings &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✓ Finalized<br>Action Points &nbsp;&nbsp;&nbsp;✓ Saved<br>Department Sync  ✓ Completed<br>Meeting Register ✓ Locked", unsafe_allow_html=True)
                    st.markdown("---")
                    st.markdown("##### 🖨️ Direct Print Options")
                    c_pr1, c_pr2, c_pr3 = st.columns(3)
                    if c_pr1.button("🖨 Print Proceedings", use_container_width=True): st.session_state.preview_html = generate_meeting_html(proc_mtg, p_aps_locked, "Proceedings & Resolutions")
                    if c_pr2.button("🖨 Print Attendance", use_container_width=True): st.session_state.preview_html = generate_meeting_html(proc_mtg, p_aps_locked, "Attendance Register")
                    if c_pr3.button("📦 Complete Meeting Record", type="primary", use_container_width=True): st.session_state.preview_html = generate_meeting_html(proc_mtg, p_aps_locked, "Complete Meeting File")
                    
                    if st.session_state.get("preview_html"):
                        render_print_preview(st.session_state.preview_html)
                        if st.button("Close Print Preview"):
                            st.session_state.preview_html = None
                            st.rerun()
                else:
                    # ---------------- UNLOCKED WORKFLOW ----------------
                    with st.expander("👥 A. Statutory Attendance Register (Mixed-Mode)", expanded=True):
                        att_data = proc_mtg.get("detailed_attendance") or []
                        
                        if not att_data:
                            st.warning("Legacy Meeting Record. No detailed snapshot available.")
                        else:
                            updated_attendance_payload = []
                            indiv_att = [a for a in att_data if a.get("type", "individual") == "individual" and a.get("posting_level") != "Substitute"]
                            dept_att = [a for a in att_data if a.get("type") == "department"]
                            sub_att = [a for a in att_data if a.get("posting_level") == "Substitute"]
                            
                            if indiv_att:
                                st.markdown("##### Individual Officials")
                                for off in indiv_att:
                                    display_text = f"**{off.get('name')}** — {off.get('designation')} | {off.get('department')}"
                                    if off.get('wing'): display_text += f" ({off['wing']})"
                                    is_present = st.checkbox(display_text, value=(off.get("attendance") != "Absent"), key=f"att_{off.get('contact_id', off.get('name'))}_{proc_sel}")
                                    updated_attendance_payload.append({**off, "attendance": "Present" if is_present else "Absent"})
                            
                            if dept_att:
                                st.markdown("##### General Department Invitations")
                                for dept in dept_att:
                                    display_text = f"🏢 {dept.get('department')}"
                                    if dept.get('wing') and dept.get('wing') != "Main Department": display_text += f" ({dept['wing']})"
                                    is_present = st.checkbox(display_text, value=(dept.get("attendance") != "Absent"), key=f"att_gen_{dept.get('dept_uid')}_{proc_sel}")
                                    updated_attendance_payload.append({**dept, "attendance": "Present" if is_present else "Absent"})
                                    
                            if sub_att:
                                st.markdown("##### Substitutes / Unplanned Attendees")
                                for sub in sub_att:
                                    display_text = f"**{sub.get('name')}** — {sub.get('designation')} | {sub.get('department')}"
                                    is_present = st.checkbox(display_text, value=(sub.get("attendance") != "Absent"), key=f"att_sub_{sub.get('name')}_{proc_sel}")
                                    updated_attendance_payload.append({**sub, "attendance": "Present (Substitute)" if is_present else "Absent"})

                            with st.popover("➕ Add Substitute / Unexpected Attendee"):
                                st.caption("Record attendance for someone who wasn't originally invited.")
                                with st.form(f"sub_{proc_sel}", clear_on_submit=True):
                                    s_dept = st.selectbox("Department", [unified_uid_to_label.get(u, u) for u in proc_mtg.get("attendees", [])])
                                    s_name = st.text_input("Name*")
                                    s_desig = st.selectbox("Designation*", list(designation_map.keys()))
                                    if st.form_submit_button("Add Attendee"):
                                        if s_name:
                                            updated_attendance_payload.append({
                                                "type": "individual", "name": s_name, "designation": s_desig, "department": s_dept,
                                                "posting_level": "Substitute", "wing": "", "mobile": "", "email": "", "attendance": "Present (Substitute)"
                                            })
                                            try:
                                                supabase.table("meetings").update({"detailed_attendance": sanitize_payload(updated_attendance_payload)}).eq("id", proc_sel).execute()
                                                st.rerun()
                                            except Exception as sub_err:
                                                set_msg("error", f"🔴 Failed to add substitute. Error: {str(sub_err)}")
                                                st.rerun()

                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("Save Combined Attendance Register", type="primary"):
                                try:
                                    supabase.table("meetings").update({"detailed_attendance": sanitize_payload(updated_attendance_payload)}).eq("id", proc_sel).execute()
                                    verify = supabase.table("meetings").select("detailed_attendance").eq("id", proc_sel).execute()
                                    if verify.data and verify.data[0].get("detailed_attendance"):
                                        # Strict validation: Only "Present", "Absent", "Present (Substitute)" are allowed.
                                        valid_statuses = ["Present", "Absent", "Present (Substitute)"]
                                        has_pending = any(a.get("attendance") not in valid_statuses for a in verify.data[0]["detailed_attendance"])
                                        if not has_pending: 
                                            set_msg("success", "🟢 Attendance Register saved successfully.")
                                        else: 
                                            set_msg("warning", "🟡 Attendance saved, but some entries lack valid status. Please re-verify.")
                                    else: 
                                        set_msg("error", "🔴 Attendance Register could not be verified after saving.")
                                except Exception as e:
                                    set_msg("error", f"🔴 Failed to save attendance: {str(e)}")
                                st.rerun()

                    st.markdown("---")
                    st.markdown("#### B. MINUTES & RESOLUTION DIRECTIVES")
                    st.markdown("────────────────────────────────────────────────────")
                    general_minutes = st.text_area("Meeting Minutes / Deliberations", value=proc_mtg.get("decisions", "") or "", height=150)
                    if st.button("Save Draft Minutes", key=f"btn_mins_{proc_sel}"):
                        try:
                            supabase.table("meetings").update({"decisions": sanitize_payload(general_minutes)}).eq("id", proc_sel).execute()
                            verify = supabase.table("meetings").select("decisions").eq("id", proc_sel).execute()
                            if verify.data and verify.data[0].get("decisions") == general_minutes:
                                set_msg("success", f"🟢 Meeting minutes saved successfully.\nStatus: Draft. You may continue editing the proceedings.")
                            else: set_msg("error", "🔴 Proceedings save verification failed.")
                        except Exception as e:
                            set_msg("error", f"🔴 Proceedings could not be saved: {str(e)}")
                        st.rerun()

                    st.markdown("────────────────────────────────────────────────────")
                    st.markdown("#### ASSIGN ACTION POINT / DIRECTIVE")
                    
                    current_aps = p_aps_locked
                    if not current_aps.empty:
                        st.markdown("**Existing Action Points for this Meeting:**")
                        st.dataframe(current_aps[["Resolution No.", "Department / Wing", "action_point", "deadline", "status"]], use_container_width=True, hide_index=True)
                        st.markdown("**+ Add Another Action Point**")

                    with st.container(border=True):
                        c_r1, c_r2 = st.columns(2)
                        res_dept_label = c_r1.selectbox("Responsibility Department / Wing *", dept_labels, key=f"r_dept_{proc_sel}")
                        selected_opt = next(opt for opt in unified_depts if opt['label'] == res_dept_label)
                        
                        mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == selected_opt['dept_id']]
                        valid_act_names = ["General / Administrative"] + [a['activity_name'] for a in activities_data if a['id'] in mapped_act_ids]
                        res_scheme = c_r2.selectbox("Scheme Linkage", valid_act_names, key=f"r_sch_{proc_sel}")

                        res_issue = st.text_input("Discussion Point / Agenda Subject *", key=f"r_iss_{proc_sel}")
                        res_resolution = st.text_area("Resolution / Mandated Directive *", key=f"r_res_{proc_sel}")
                        res_outcome = st.text_input("Expected Milestone Outcome", key=f"r_out_{proc_sel}")

                        c_r3, c_r4, c_r5 = st.columns(3)
                        res_status = c_r3.selectbox("Initial Status *", ["Not Started", "On Track"], key=f"r_stat_{proc_sel}")
                        res_priority = c_r4.selectbox("Priority", ["High", "Medium", "Low"], index=1, key=f"r_pri_{proc_sel}")
                        res_deadline = c_r5.date_input("Target Deadline *", date.today(), key=f"r_dl_{proc_sel}")
                        atr_req = st.checkbox("ATR Submission Required?", value=True, key=f"r_atr_{proc_sel}")

                        if st.button("COMMIT & AUTO-SYNC", type="primary", key=f"btn_add_{proc_sel}"):
                            if not res_resolution.strip() or not res_issue.strip(): 
                                set_msg("error", "🔴 Resolution directive and Discussion Point are mandatory.")
                            else:
                                res_payload = {
                                    "meeting_id": safe_int(proc_sel), 
                                    "department_id": safe_int(selected_opt['dept_id']),
                                    "wing_id": safe_int(selected_opt['wing_id']) if selected_opt['wing_id'] else None,
                                    "district_id": safe_int(proc_mtg.get("district_id")) if pd.notna(proc_mtg.get("district_id")) else None, 
                                    "block_id": safe_int(proc_mtg.get("block_id")) if pd.notna(proc_mtg.get("block_id")) else None,
                                    "action_point": f"[{res_scheme}] {res_resolution.strip()}", 
                                    "deadline": str(res_deadline), 
                                    "status": res_status, "priority": res_priority,
                                    "remarks": f"Issue: {res_issue} | Expected: {res_outcome} | ATR Req: {atr_req}"
                                }
                                try:
                                    # Use the deep sanitizer to fix int64 serialization issues
                                    clean_payload = sanitize_payload(res_payload)
                                    res = supabase.table("meeting_action_points").insert(clean_payload).execute()
                                    if res.data and len(res.data) > 0:
                                        v_id = res.data[0]['id']
                                        v_check_query = supabase.table("meeting_action_points").select("id").eq("id", v_id).eq("department_id", safe_int(selected_opt['dept_id']))
                                        if selected_opt['wing_id']: v_check_query = v_check_query.eq("wing_id", safe_int(selected_opt['wing_id']))
                                        else: v_check_query = v_check_query.is_("wing_id", "null")
                                        
                                        v_check = v_check_query.execute()
                                        if v_check.data: set_msg("success", f"🟢 Action Point recorded and successfully synchronized to {selected_opt['label']}.")
                                        else: set_msg("error", "🔴 Action Point was not synchronized to the concerned Department/Wing.\nCommitment: ✓ Saved\nDepartment Sync: ✗ Failed")
                                    else: set_msg("error", "🔴 Action Point could not be saved.")
                                except Exception as e:
                                    set_msg("error", f"🔴 Action Point could not be saved. Database Error: {str(e)}")
                            st.rerun()

                    st.markdown("---")
                    
                    # ---------------- VERIFIED MEETING LOCK ----------------
                    if st.session_state.get(f"confirm_lock_{proc_sel}", False):
                        st.warning("⚠️ Are you sure you want to finalize this meeting? After finalization, the proceedings and meeting register will become read-only.")
                        col_c1, col_c2 = st.columns(2)
                        if col_c1.button("Cancel"):
                            st.session_state[f"confirm_lock_{proc_sel}"] = False
                            st.rerun()
                        if col_c2.button("Confirm & Lock", type="primary"):
                            fresh_mtg = supabase.table("meetings").select("*").eq("id", proc_sel).execute().data[0]
                            att_check = fresh_mtg.get("detailed_attendance") or []
                            proceedings_check = fresh_mtg.get("decisions") or ""
                            
                            valid_statuses = ["Present", "Absent", "Present (Substitute)"]
                            has_pending = any(a.get("attendance") not in valid_statuses for a in att_check)
                                    
                            if not att_check or has_pending:
                                set_msg("error", "🔴 Attendance register has pending items or has not been saved. Please save attendance before completing proceedings.")
                            elif not proceedings_check.strip():
                                set_msg("error", "🔴 Meeting proceedings are required before finalization. Do not lock an empty meeting.")
                            else:
                                try:
                                    supabase.table("meetings").update({"status": "Convened", "decisions": sanitize_payload(proceedings_check)}).eq("id", proc_sel).execute()
                                    verify = supabase.table("meetings").select("status").eq("id", proc_sel).execute().data
                                    if verify and verify[0]["status"] == "Convened":
                                        set_msg("success", "🟢 Meeting proceedings completed successfully.\n🔒 Meeting Register locked successfully.")
                                        st.session_state[f"confirm_lock_{proc_sel}"] = False
                                    else: set_msg("error", "🔴 Meeting could not be finalized. Database verification failed. No lock applied.")
                                except Exception as e:
                                    set_msg("error", f"🔴 Meeting could not be finalized. Please verify the record and try again. Error: {str(e)}")
                            st.rerun()
                    else:
                        if st.button("🔒 Complete Proceedings & Lock Meeting Register", type="primary", use_container_width=True):
                            st.session_state[f"confirm_lock_{proc_sel}"] = True
                            st.rerun()

    # =====================================================================
    # TAB 4: ADVANCED ACTION TRACKER & ATR
    # =====================================================================
    if tab_tracker:
        with tab_tracker:
            st.markdown("#### 🎯 Resolution Tracker & Action Taken Reports (ATR)")
            display_persisted_msg()

            if df_ap.empty:
                st.info("No action items available.")
            else:
                search_query = st.text_input("🔍 Search Resolution No, Action Point, Department, etc.", "")

                c_f1, c_f2 = st.columns(2)
                f_dept = c_f1.selectbox("Filter Department", ["All"] + dept_labels)
                f_flag = c_f2.selectbox("Filter SLA Flag", ["All", "🟢 CLOSED", "🔴 OVERDUE", "🟡 DUE TODAY", "🔵 ON TRACK", "🟠 FOR REVIEW", "⚪ NOT STARTED"])

                filtered_df = df_ap.copy()
                if f_dept != "All": filtered_df = filtered_df[filtered_df["Department / Wing"] == f_dept]
                if f_flag != "All": filtered_df = filtered_df[filtered_df["Tracker Flag"] == f_flag]
                if search_query:
                    search_mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
                    filtered_df = filtered_df[search_mask]

                display_df = filtered_df[["Resolution No.", "Origin Meeting", "Department / Wing", "action_point", "deadline", "Tracker Flag", "status", "remarks"]].sort_values("Tracker Flag")
                
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "action_point": st.column_config.TextColumn("Action Point / Directive", width="large"),
                        "Resolution No.": st.column_config.TextColumn("Resolution No.", width="medium")
                    }
                )

                if role in ["superadmin", "district", "block"]:
                    st.markdown("---")
                    st.markdown("##### ⚙️ Authorized Correction & Cancellation Workspace")
                    st.caption("Identify, correct, or cancel a resolution. All actions are strictly audited and synced.")

                    res_options = filtered_df['id'].tolist()
                    def format_res_label(x):
                        row = filtered_df[filtered_df['id'] == x].iloc[0]
                        return f"{row['Resolution No.']} | {row['Origin Meeting']} | {row['Department / Wing']} | {str(row['action_point'])[:60]}..."

                    selected_ap_id = st.selectbox("Step 1 — Identify Resolution", res_options, format_func=format_res_label)

                    if selected_ap_id:
                        target_row = filtered_df[filtered_df['id'] == selected_ap_id].iloc[0]

                        with st.container(border=True):
                            st.markdown(f"**Selected Resolution Details**")
                            st.markdown(f"**Resolution No.:** {target_row['Resolution No.']}")
                            st.markdown(f"**Origin Meeting:** {target_row['Origin Meeting']}")
                            st.markdown(f"**Department/Wing:** {target_row['Department / Wing']}")
                            st.markdown(f"**Original Action Point:**\n> {target_row['action_point']}")
                            st.markdown(f"**Original Deadline:** {target_row['deadline'].strftime('%d-%m-%Y') if pd.notna(target_row['deadline']) else 'N/A'}")
                            st.markdown(f"**Current Status:** {target_row['status']}")

                        action_type = st.radio("Step 2 — Select Action", ["✏️ Correct Commitment", "🗑️ Cancel / Delete Commitment"], horizontal=True)

                        if action_type == "✏️ Correct Commitment":
                            with st.form("edit_commitment_form"):
                                st.markdown("Step 3 — Correct")
                                new_dept_label = st.selectbox("Department/Wing", dept_labels, index=dept_labels.index(target_row['Department / Wing']) if target_row['Department / Wing'] in dept_labels else 0)
                                new_action_text = st.text_area("Corrected Action Point / Directive*", value=target_row.get('action_point', ''))
                                new_deadline = st.date_input("Corrected Deadline", value=pd.to_datetime(target_row.get('deadline')).date() if pd.notna(target_row.get('deadline')) else date.today())
                                correction_reason = st.text_input("Reason for Correction (Audited)*", placeholder="e.g. Typographical error, Correction as per proceeding")

                                if st.form_submit_button("Confirm Correction", type="primary"):
                                    if not correction_reason.strip():
                                        st.error("⚠️ Mandatory Audit Reason is required to modify a convened resolution.")
                                    elif not new_action_text.strip():
                                        st.error("⚠️ Action point text cannot be empty.")
                                    else:
                                        selected_opt = next(opt for opt in unified_depts if opt['label'] == new_dept_label)
                                        update_payload = {
                                            "department_id": safe_int(selected_opt['dept_id']),
                                            "wing_id": safe_int(selected_opt['wing_id']) if selected_opt['wing_id'] else None,
                                            "action_point": new_action_text,
                                            "deadline": str(new_deadline),
                                            "remarks": f"[Corrected by {role.upper()} on {datetime.now().strftime('%d-%m-%Y %H:%M')} - Reason: {correction_reason}] | {target_row.get('remarks', '')}"
                                        }
                                        try:
                                            supabase.table("meeting_action_points").update(sanitize_payload(update_payload)).eq("id", selected_ap_id).execute()
                                            log_action(user.get('id'), f"CORRECTED meeting_action_points {selected_ap_id} (Res No: {target_row['Resolution No.']}) - Reason: {correction_reason}")
                                            set_msg("success", f"✅ Resolution {target_row['Resolution No.']} successfully corrected and synchronized!")
                                        except Exception as e:
                                            set_msg("error", f"❌ Failed to correct resolution: {str(e)}")
                                        st.rerun()

                        elif action_type == "🗑️ Cancel / Delete Commitment":
                            with st.form("delete_commitment_form"):
                                st.markdown("Step 3 — Delete")
                                st.warning(f"⚠️ This action will cancel Resolution **{target_row['Resolution No.']}** and remove it from active tracking. The Department will no longer see it.")
                                delete_reason = st.text_input("Reason for Cancellation (Audited)*", placeholder="e.g. Duplicate entry, Administrative cancellation")
                                
                                if st.form_submit_button("Confirm Delete", type="primary"):
                                    if not delete_reason.strip():
                                        st.error("⚠️ Mandatory Audit Reason is required to delete a resolution.")
                                    else:
                                        try:
                                            update_payload = {
                                                "status": "Dropped",
                                                "remarks": f"[Cancelled by {role.upper()} on {datetime.now().strftime('%d-%m-%Y %H:%M')} - Reason: {delete_reason}] | {target_row.get('remarks', '')}"
                                            }
                                            supabase.table("meeting_action_points").update(sanitize_payload(update_payload)).eq("id", selected_ap_id).execute()
                                            log_action(user.get('id'), f"CANCELLED meeting_action_points {selected_ap_id} (Res No: {target_row['Resolution No.']}) | Reason: {delete_reason}")
                                            set_msg("success", f"✅ Resolution {target_row['Resolution No.']} deleted successfully and removed from Department view.")
                                        except Exception as e:
                                            set_msg("error", f"❌ Failed to delete resolution: {str(e)}")
                                        st.rerun()

                st.markdown("---")
                st.markdown("##### 📝 Submit Department ATR Update")
                with st.form("global_update_atr"):
                    c_u1, c_u2 = st.columns(2)
                    ap_id = c_u1.selectbox("Select Resolution", filtered_df["id"].tolist(), format_func=lambda x: f"{filtered_df[filtered_df['id'] == x].iloc[0]['Resolution No.']} | {str(filtered_df[filtered_df['id'] == x].iloc[0]['action_point'])[:50]}...")
                    new_ap_status = c_u2.selectbox("Update Status", ["Not Started", "On Track", "Completed", "Not Feasible (Requires Review)", "Dropped"])
                    atr_remarks = st.text_area("ATR Findings / Justification")

                    if st.form_submit_button("Submit ATR Update", type="primary"):
                        if new_ap_status == "Not Feasible (Requires Review)" and not atr_remarks.strip():
                            st.error("⚠️ Mandatory Justification required for Not Feasible.")
                        else:
                            try: supabase.table("meeting_action_points").update({"status": sanitize_payload(new_ap_status), "remarks": sanitize_payload(atr_remarks)}).eq("id", ap_id).execute()
                            except: supabase.table("meeting_action_points").update({"status": sanitize_payload(new_ap_status.lower().replace(" ", "_")), "remarks": sanitize_payload(atr_remarks)}).eq("id", ap_id).execute()
                            log_action(user.get('id'), f"UPDATE ATR meeting_action_points {ap_id}")
                            set_msg("success", "✅ ATR submitted successfully.")
                            st.rerun()

    # =====================================================================
    # TAB 5: AUTOMATED NEXT AGENDA PREP
    # =====================================================================
    if tab_agenda:
        with tab_agenda:
            st.markdown("#### ⏭️ Auto-Generated Next Meeting Agenda")
            district_id = user.get("district_id")
            if not district_id:
                st.info("Select district context to compile automated agenda.")
            else:
                agenda_text = "STATUTORY CONVERGENCE COMMITTEE — UPCOMING AGENDA:\n\n"
                has_items = False
                if not df_ap.empty:
                    active_df = df_ap[~df_ap["Tracker Flag"].isin(["🟢 CLOSED"])]
                    unfeasible_df = active_df[active_df["Tracker Flag"] == "🟠 FOR REVIEW"]
                    overdue_df = active_df[active_df["Tracker Flag"] == "🔴 OVERDUE"]
                    if not unfeasible_df.empty:
                        has_items = True
                        agenda_text += "🟠 ITEMS FLAGGED AS NOT FEASIBLE (FOR REVIEW):\n"
                        for idx, row in unfeasible_df.iterrows(): agenda_text += f"- [{row['Resolution No.']}] [{row['Department / Wing']}] {row['action_point']}\n"
                    if not overdue_df.empty:
                        has_items = True
                        agenda_text += "🔴 OVERDUE COMMITMENTS (SLA BREACH):\n"
                        for idx, row in overdue_df.iterrows(): agenda_text += f"- [{row['Resolution No.']}] [{row['Department / Wing']}] {row['action_point']}\n"
                if has_items:
                    st.warning("⚠️ High-priority governance exceptions identified.")
                    st.text_area("Compiled Agenda Text:", value=agenda_text, height=350)
                else:
                    st.success("🎉 No overdue items detected.")

    # =====================================================================
    # TAB 6: DIRECT PRINT CENTRE (NATIVE PRINT DIALOG) - ALWAYS LAST
    # =====================================================================
    if tab_print:
        with tab_print:
            st.markdown("#### 🖨️ Meeting Print Centre")
            st.caption("Select a meeting and the document type. The system generates an immediate preview and opens your browser's native print dialog.")

            if df_meetings.empty:
                st.info("No meetings available for printing.")
            else:
                c_p1, c_p2 = st.columns([2, 1])
                print_sel = c_p1.selectbox(
                    "1. Select Meeting Record",
                    df_meetings["id"].tolist(),
                    format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['meeting_type'].values[0]} ({df_meetings[df_meetings['id'] == x]['status'].values[0]})"
                )
                doc_type = c_p2.selectbox(
                    "2. Select Document to Print",
                    ["Meeting Notice & Invited List", "Attendance Register", "Proceedings & Resolutions", "Complete Meeting File"]
                )

                p_mtg = df_meetings[df_meetings["id"] == print_sel].iloc[0]
                p_aps = df_ap[df_ap['meeting_id'] == print_sel] if not df_ap.empty else pd.DataFrame()
                
                html_output = generate_meeting_html(p_mtg, p_aps, doc_type)
                if html_output: render_print_preview(html_output)
