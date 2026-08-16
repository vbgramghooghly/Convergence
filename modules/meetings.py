from datetime import date, datetime
import pandas as pd
import streamlit as st
from auth.auth import require_role, get_current_user
from utils.db import get_supabase
from utils.audit import log_action

def safe_int(val):
    """Safely converts empty strings, floats, booleans, and nulls to integers to prevent math/ValueError crashes."""
    if pd.isna(val) or val is None or val == '': 
        return 0
    try: 
        return int(float(val))
    except (ValueError, TypeError): 
        return 0

def show():
    # 1. ENFORCE SECURITY & ACCESS RULES
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()
    today = pd.to_datetime(date.today())
    active_fy = st.session_state.get("selected_fy", "2026-27")

    # BREADCRUMB & HEADER
    st.markdown("<div style='font-size: 0.85rem; color: #64748B; margin-bottom: 0.5rem;'>Home / Statutory Governance / Convergence Meetings</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom: 0px; color: #0F4C81;'>🤝 Statutory Meeting Governance & Resolution Tracker</h2>", unsafe_allow_html=True)
    st.caption(f"FY {active_fy} | Coordinate Committee Meetings, Record Proceedings, Synchronize ATRs, and Generate Agendas.")
    st.markdown("---")

    # MASTER DATA LOOKUPS (Unchanged)
    departments = supabase.table("departments").select("id, department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data or []
    activities_data = supabase.table("activities").select("id, activity_name").eq("active", True).execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("activity_id, department_id").execute().data or []
    
    # NEW: Fetch Official Directory (Contacts) for Meeting Integration
    contacts_query = supabase.table("contacts").select("*, designations(designation_name)").eq("active", True).execute()
    contacts_data = contacts_query.data or []

    dept_map = {d["id"]: d["department_name"] for d in departments}
    wing_map = {w["id"]: w for w in wings}
    block_dict_reverse = {b["id"]: b["block_name"] for b in blocks_data}

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
            if w_id in wing_map:
                return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
        return f"{d_name} (Main)"

    # DATA FETCHING (Meetings & Action Points - Unchanged Logic)
    q_meetings = supabase.table("meetings").select("*").eq("financial_year", active_fy)
    if role in ["district", "department"]: q_meetings = q_meetings.eq("district_id", user["district_id"])
    elif role == "block": q_meetings = q_meetings.eq("block_id", user["block_id"])
    meetings = q_meetings.order("meeting_date", desc=True).execute().data or []

    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()

    # Live pull of action points to ensure instant synchronization
    ap_data = supabase.table("meeting_action_points").select("*").execute().data or []
    df_ap = pd.DataFrame(ap_data) if ap_data else pd.DataFrame()

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

        df_ap["Department / Wing"] = df_ap.apply(format_dept_display, axis=1)
        meeting_lookup_map = {m["id"]: f"{m['meeting_date']} ({m['meeting_type']})" for m in meetings}
        df_ap["Origin Meeting"] = df_ap["meeting_id"].map(meeting_lookup_map).fillna("District/Block Meeting")
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

    # EXECUTIVE GOVERNANCE KPI BAR
    if not df_ap.empty:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Commitments", len(df_ap))
        c2.metric("🟢 Closed", len(df_ap[df_ap["Tracker Flag"] == "🟢 CLOSED"]))
        c3.metric("🔵 On Track", len(df_ap[df_ap["Tracker Flag"] == "🔵 ON TRACK"]))
        c4.metric("🟡 Due Today", len(df_ap[df_ap["Tracker Flag"] == "🟡 DUE TODAY"]))
        c5.metric("🔴 Overdue", len(df_ap[df_ap["Tracker Flag"] == "🔴 OVERDUE"]))
        c6.metric("🟠 Needs Review", len(df_ap[df_ap["Tracker Flag"] == "🟠 FOR REVIEW"]))
        st.markdown("<br>", unsafe_allow_html=True)

    # =====================================================================
    # ROLE-SPECIFIC TAB ARCHITECTURE
    # =====================================================================
    if role == "department":
        tab1, tab4, tab5 = st.tabs([
            "📈 SLA Performance", 
            "🖨️ Meeting Record Workspace",
            "🎯 Action Tracker & ATR"
        ])
    else:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📈 SLA Performance", 
            "🗓️ Schedule Meeting", 
            "✍️ Proceedings & Attendance", 
            "🖨️ Meeting Record Workspace",
            "🎯 Action Tracker & ATR", 
            "⏭️ Next Agenda Prep"
        ])

    # =====================================================================
    # TAB 1: SLA PERFORMANCE DASHBOARD (Unchanged)
    # =====================================================================
    with tab1:
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
    # TAB 2: SCHEDULE MEETING (Admin Only) - UPGRADED FOR NAME-WISE SELECTION
    # =====================================================================
    if role != "department":
        with tab2:
            st.markdown("#### 🗓️ Schedule Convergence Committee Meeting")
            st.caption("Select participating Departments, then select the specific Officials from the Master Directory. Officials will form the Name-wise Attendance Register.")
            
            with st.container(border=True):
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
                
                # 1. SELECT DEPARTMENTS & WINGS (Organizational Level)
                invited_uids = st.multiselect("1. Invite Departments & Wings*", options=[u["uid"] for u in unified_depts], format_func=lambda x: unified_uid_to_label.get(x, x))
                
                # 2. SELECT OFFICIALS DYNAMICALLY FROM DIRECTORY
                selected_contact_ids = []
                available_officials = []
                
                if invited_uids:
                    target_district_id = dist_dict[dist_sel] if meeting_type == "District" else dist_sel
                    target_block_id = next((b["id"] for b in blocks_data if b["block_name"] == block_sel), None) if meeting_type == "Block" else None
                    
                    for c in contacts_data:
                        # Match Jurisdiction Level
                        jurisdiction_match = False
                        if c.get("district_id") == target_district_id:
                            if meeting_type == "Block":
                                if c.get("office_level") in ["State / Department", "District", "Sub Division"]:
                                    jurisdiction_match = True
                                elif c.get("block_id") == target_block_id:
                                    jurisdiction_match = True
                            else:
                                jurisdiction_match = True
                                
                        if not jurisdiction_match: continue
                        
                        # Match Department/Wing exactly
                        dept_match = False
                        for uid in invited_uids:
                            opt = next((u for u in unified_depts if u["uid"] == uid), None)
                            if opt:
                                if opt["wing_id"]: # Wing level match
                                    if c.get("wing_id") == opt["wing_id"]: dept_match = True
                                else: # Main Dept match
                                    if c.get("department_id") == opt["dept_id"] and not c.get("wing_id"): dept_match = True
                        
                        if dept_match:
                            available_officials.append(c)
                            
                    if available_officials:
                        official_options = {
                            c["id"]: f"{c['full_name']} | {c.get('designations', {}).get('designation_name', 'Unknown Designation')} | {c.get('office_level')}" 
                            for c in available_officials
                        }
                        st.markdown("##### 2. Select Individual Officials from Master Directory")
                        selected_contact_ids = st.multiselect(
                            "The Attendance Register will be generated for these specific officials.", 
                            options=list(official_options.keys()), 
                            format_func=lambda x: official_options[x]
                        )
                    else:
                        st.warning("⚠️ No mapped officials found for the selected Departments in this jurisdiction. Please add them in the Official Directory.")

                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Issue Meeting Notice & Generate Attendance Register", type="primary", use_container_width=True):
                    if not invited_uids: 
                        st.error("Please select at least one Department/Wing.")
                    elif not selected_contact_ids:
                        st.error("Please select at least one Official to form the Attendance Register.")
                    else:
                        # BUILD HISTORICAL SNAPSHOT
                        invited_officials_snapshot = []
                        for cid in selected_contact_ids:
                            c = next((x for x in available_officials if x["id"] == cid), None)
                            if c:
                                wing_obj = wing_map.get(c.get("wing_id"))
                                snapshot_entry = {
                                    "contact_id": c["id"],
                                    "name": c["full_name"],
                                    "designation": c.get("designations", {}).get("designation_name", "N/A"),
                                    "posting_level": c.get("office_level", "N/A"),
                                    "department": dept_map.get(c.get("department_id"), "N/A"),
                                    "wing": wing_obj["wing_name"] if wing_obj else "",
                                    "mobile": c.get("contact_number", ""),
                                    "email": c.get("email_id", "")
                                }
                                invited_officials_snapshot.append(snapshot_entry)

                        meeting_data = {
                            "meeting_type": meeting_type, "financial_year": active_fy, "meeting_date": str(meeting_date),
                            "chairperson": chairperson, "venue": venue, "objective": objective, "attendees": invited_uids,
                            "invited_officials": invited_officials_snapshot, # New Snapshot Field
                            "status": "Scheduled", "created_by": user["id"]
                        }
                        
                        if meeting_type == "District": 
                            meeting_data["district_id"] = dist_dict[dist_sel] if role != "district" else user["district_id"]
                        else:
                            block_obj = next(b for b in blocks_data if b["block_name"] == block_sel)
                            meeting_data["block_id"] = block_obj["id"]
                            meeting_data["district_id"] = block_obj["district_id"]

                        supabase.table("meetings").insert(meeting_data).execute()
                        st.success("✅ Meeting notice dispatched successfully! Name-wise attendance and print packages are auto-generated.")
                        st.rerun()

    # =====================================================================
    # TAB 3: PROCEEDINGS & ATTENDANCE (Admin Only) - UPGRADED
    # =====================================================================
    if role != "department":
        with tab3:
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

                with st.expander("👥 A. Statutory Attendance Register (Name-Wise)", expanded=not is_locked):
                    invited_officials = proc_mtg.get("invited_officials") or []
                    
                    if not invited_officials: 
                        st.warning("Legacy Meeting Format: No individual officials were attached to this notice. Attendance cannot be taken name-wise.")
                    else:
                        detailed_attendance_payload = []
                        st.markdown("Mark official attendance. Status auto-saves on submission.")
                        with st.container(border=True):
                            for off in invited_officials:
                                c1, c2 = st.columns([3, 1])
                                # Formatting the display text purely from snapshot data
                                display_text = f"**{off['name']}** — {off['designation']} | {off['department']}"
                                if off['wing']: display_text += f" ({off['wing']})"
                                
                                is_present = c1.checkbox(display_text, value=True, key=f"att_{off['contact_id']}_{proc_sel}", disabled=is_locked)
                                
                                detailed_attendance_payload.append({
                                    **off, # Inherit all snapshot data (Sl No context)
                                    "attendance": "Present" if is_present else "Absent"
                                })
                                
                            if not is_locked:
                                if st.button("Save Name-wise Attendance Register", type="primary"):
                                    supabase.table("meetings").update({"detailed_attendance": detailed_attendance_payload}).eq("id", proc_sel).execute()
                                    st.success("✅ Attendance saved successfully.")
                                    st.rerun()

                with st.expander("📝 B. Minutes & Resolution Directives (Auto-Syncs to Department)", expanded=not is_locked):
                    st.caption("Targets and Commitments remain mapped to the Department/Wing Level.")
                    general_minutes = st.text_area("Meeting Minutes / Deliberations", value=proc_mtg.get("decisions", "") or "", disabled=is_locked)
                    
                    if not is_locked:
                        if st.button("Save Draft Minutes", key=f"btn_mins_{proc_sel}"):
                            supabase.table("meetings").update({"decisions": general_minutes}).eq("id", proc_sel).execute()
                            st.success("Draft minutes committed.")

                        st.markdown("##### Assign Action Point / Directives")
                        with st.container(border=True):
                            c_r1, c_r2 = st.columns(2)
                            res_dept_label = c_r1.selectbox("Assign Responsibility to (Department/Wing)*", dept_labels, key=f"r_dept_{proc_sel}")
                            selected_opt = next(opt for opt in unified_depts if opt['label'] == res_dept_label)
                            
                            mapped_act_ids = [m['activity_id'] for m in act_dept_mapping if m['department_id'] == selected_opt['dept_id']]
                            valid_act_names = ["General / Administrative"] + [a['activity_name'] for a in activities_data if a['id'] in mapped_act_ids]
                            res_scheme = c_r2.selectbox("Scheme Linkage", valid_act_names, key=f"r_sch_{proc_sel}")

                            res_issue = st.text_input("Discussion Point / Agenda Subject", key=f"r_iss_{proc_sel}")
                            res_resolution = st.text_area("Resolution / Mandated Directive*", key=f"r_res_{proc_sel}")
                            res_outcome = st.text_input("Expected Milestone Outcome", key=f"r_out_{proc_sel}")

                            c_r3, c_r4, c_r5 = st.columns(3)
                            res_status = c_r3.selectbox("Initial Status", ["Not Started", "On Track"], key=f"r_stat_{proc_sel}")
                            res_priority = c_r4.selectbox("Priority", ["High", "Medium", "Low"], index=1, key=f"r_pri_{proc_sel}")
                            res_deadline = c_r5.date_input("Target Deadline", date.today(), key=f"r_dl_{proc_sel}")
                            atr_req = st.checkbox("ATR Submission Required?", value=True, key=f"r_atr_{proc_sel}")

                            if st.button("Commit Action Point & Sync", type="primary", key=f"btn_add_{proc_sel}"):
                                if not res_resolution.strip(): st.error("Resolution directive is mandatory.")
                                else:
                                    res_payload = {
                                        "meeting_id": proc_sel, "department_id": selected_opt['dept_id'],
                                        "wing_id": selected_opt['wing_id'], "action_point": f"[{res_scheme}] {res_resolution.strip()}",
                                        "deadline": str(res_deadline), "status": res_status, "priority": res_priority,
                                        "remarks": f"Issue: {res_issue} | Expected: {res_outcome} | ATR Req: {atr_req}"
                                    }
                                    try:
                                        supabase.table("meeting_action_points").insert(res_payload).execute()
                                        st.success("✅ Directive recorded & automatically synced to Department login!")
                                        st.rerun()
                                    except Exception:
                                        res_payload["status"], res_payload["priority"] = res_status.lower().replace(" ", "_"), res_priority.lower()
                                        supabase.table("meeting_action_points").insert(res_payload).execute()
                                        st.success("✅ Directive recorded & automatically synced to Department login!")
                                        st.rerun()

                if not is_locked:
                    st.markdown("---")
                    if st.button("🔒 Complete Proceedings & Lock Meeting Register", type="primary", use_container_width=True, key=f"btn_lock_{proc_sel}"):
                        supabase.table("meetings").update({"status": "Convened", "decisions": general_minutes}).eq("id", proc_sel).execute()
                        st.success("Meeting proceedings locked! Record is now legally convened and read-only.")
                        st.rerun()

    # =====================================================================
    # TAB 4: MEETING RECORD WORKSPACE & PRINTING PACKAGE (UPGRADED)
    # =====================================================================
    workspace_tab = tab4 if role == "department" else tab4
    with workspace_tab:
        st.markdown("#### 🖨️ Meeting Record Workspace & Print Packages")
        st.caption("Select any historical or active meeting to generate instant print-ready documents with Name-wise structures. Zero duplicate entry.")

        if df_meetings.empty:
            st.info("No meetings available for printing.")
        else:
            print_sel = st.selectbox(
                "Select Meeting Record for Printing",
                df_meetings["id"].tolist(),
                format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['meeting_type'].values[0]} ({df_meetings[df_meetings['id'] == x]['status'].values[0]})",
                key="print_meeting_selector"
            )

            p_mtg = df_meetings[df_meetings["id"] == print_sel].iloc[0]
            p_aps = df_ap[df_ap['meeting_id'] == print_sel] if not df_ap.empty else pd.DataFrame()
            org_label = "District Administration" if p_mtg.get('meeting_type') == 'District' else f"Block Development Office"
            
            # --- HTML FORMATTERS ---
            base_css = """
            body { font-family: 'Times New Roman', Times, serif; padding: 20px; font-size: 13px; color: #000; line-height: 1.5; }
            .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th, td { border: 1px solid #000; padding: 6px; text-align: left; font-size: 11px; }
            th { background-color: #f2f2f2; }
            .page-break { page-break-after: always; }
            """

            # 1. NOTICE
            notice_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Meeting Notice</title><style>{base_css}@page {{ size: A4 portrait; margin: 20mm; }}</style></head><body>
            <div class="header"><h3>VB-G RAM G CONVERGENCE PORTAL<br>{org_label}</h3><div>Financial Year: {active_fy}</div></div>
            <h4 style="text-align: center; text-decoration: underline;">MEETING NOTICE</h4>
            <p><b>Date:</b> {p_mtg.get('meeting_date', 'Not Recorded')}</p><p><b>Venue:</b> {p_mtg.get('venue', 'Not Recorded')}</p>
            <p><b>Chairperson:</b> {p_mtg.get('chairperson', 'Not Recorded')}</p><p><b>Objective:</b> {p_mtg.get('objective', 'Standard Convergence Review')}</p>
            <br><p>The undersigned is directed to invite the nominated officials to attend the statutory meeting at the scheduled venue and time.</p>
            <div style="margin-top: 40px; text-align: right;"><b>Chairperson / Nodal Officer</b></div>
            </body></html>"""

            # 2. INVITED OFFICIALS LIST
            invited_rows = ""
            invited_officials = p_mtg.get("invited_officials") or []
            if invited_officials:
                for idx, off in enumerate(invited_officials, 1):
                    invited_rows += f"<tr><td>{idx}</td><td>{off['name']}</td><td>{off['designation']}</td><td>{off['posting_level']}</td><td>{off['department']}</td><td>{off['wing']}</td><td>{off['mobile']}</td><td>{off['email']}</td></tr>"
            else:
                invited_rows = "<tr><td colspan='8' style='text-align:center;'>Legacy Record: Specific officials were not attached.</td></tr>"

            invited_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Invited Officials</title><style>{base_css}@page {{ size: A4 landscape; margin: 15mm; }}</style></head><body>
            <div class="header"><h3>INVITED OFFICIALS LIST</h3><div>Meeting Date: {p_mtg.get('meeting_date')} | Venue: {p_mtg.get('venue')}</div></div>
            <table><thead><tr><th>Sl. No.</th><th>Name</th><th>Designation</th><th>Posting Level</th><th>Department</th><th>Wing</th><th>Mobile</th><th>Email</th></tr></thead><tbody>{invited_rows}</tbody></table>
            </body></html>"""

            # 3. ATTENDANCE REGISTER (No Signature)
            att_rows = ""
            att_data = p_mtg.get("detailed_attendance") or []
            if att_data:
                for idx, att in enumerate(att_data, 1):
                    att_status = att.get("attendance", "Unknown")
                    att_rows += f"<tr><td>{idx}</td><td>{att.get('name', '')}</td><td>{att.get('designation', '')}</td><td>{att.get('posting_level', '')}</td><td>{att.get('department', '')}</td><td>{att.get('wing', '')}</td><td>{att.get('mobile', '')}</td><td>{att.get('email', '')}</td><td><b>{att_status}</b></td></tr>"
            else:
                if invited_officials: # Blank register for printing before meeting
                    for idx, off in enumerate(invited_officials, 1):
                        att_rows += f"<tr><td>{idx}</td><td>{off['name']}</td><td>{off['designation']}</td><td>{off['posting_level']}</td><td>{off['department']}</td><td>{off['wing']}</td><td>{off['mobile']}</td><td>{off['email']}</td><td></td></tr>"
                else:
                    att_rows = "<tr><td colspan='9' style='text-align:center;'>Legacy Record.</td></tr>"

            attendance_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Attendance Register</title><style>{base_css}@page {{ size: A4 landscape; margin: 15mm; }}</style></head><body>
            <div class="header"><h3>ATTENDANCE REGISTER</h3><div>Meeting Date: {p_mtg.get('meeting_date')} | Chairperson: {p_mtg.get('chairperson')}</div></div>
            <table><thead><tr><th>Sl. No.</th><th>Name</th><th>Designation</th><th>Posting Level</th><th>Department</th><th>Wing</th><th>Mobile</th><th>Email</th><th>Attendance</th></tr></thead><tbody>{att_rows}</tbody></table>
            </body></html>"""

            # 4. PROCEEDINGS
            proc_rows = ""
            if not p_aps.empty:
                for idx, row in enumerate(p_aps.to_dict(orient="records"), 1):
                    proc_rows += f"<tr><td>{idx}</td><td>{row.get('Department / Wing')}</td><td>{row.get('action_point')}</td><td>{row.get('deadline').strftime('%Y-%m-%d') if pd.notna(row.get('deadline')) else 'N/A'}</td><td>{row.get('status')}</td><td>{row.get('remarks', '')}</td></tr>"
            else:
                proc_rows = "<tr><td colspan='6' style='text-align:center;'>No resolutions recorded for this meeting.</td></tr>"

            proceedings_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Proceedings</title><style>{base_css}@page {{ size: A4 portrait; margin: 20mm; }}</style></head><body>
            <div class="header"><h3>PROCEEDINGS OF THE STATUTORY CONVERGENCE MEETING</h3><div>Date: {p_mtg.get('meeting_date')} | Chairperson: {p_mtg.get('chairperson')}</div></div>
            <p><b>Minutes:</b><br>{p_mtg.get('decisions', 'Not Recorded / Draft')}</p>
            <h4>Mandated Resolutions (Department-Wise):</h4>
            <table><thead><tr><th>No.</th><th>Department / Wing</th><th>Directive / Action Point</th><th>Deadline</th><th>Status</th><th>Remarks</th></tr></thead><tbody>{proc_rows}</tbody></table>
            </body></html>"""

            complete_file_html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Complete Meeting File</title><style>{base_css}</style></head><body>{notice_html}<div class='page-break'></div>{invited_html}<div class='page-break'></div>{attendance_html}<div class='page-break'></div>{proceedings_html}</body></html>"

            c_p1, c_p2, c_p3, c_p4 = st.columns(4)
            c_p1.download_button("🖨️ Notice & Invited", data=f"<!DOCTYPE html><html><head><style>{base_css}</style></head><body>{notice_html}<div class='page-break'></div>{invited_html}</body></html>", file_name=f"Notice_{print_sel}.html", mime="text/html", use_container_width=True)
            c_p2.download_button("🖨️ Print Attendance", data=attendance_html, file_name=f"Attendance_{print_sel}.html", mime="text/html", use_container_width=True)
            c_p3.download_button("🖨️ Print Proceedings", data=proceedings_html, file_name=f"Proceedings_{print_sel}.html", mime="text/html", use_container_width=True)
            c_p4.download_button("📦 Complete Meeting File", data=complete_file_html, file_name=f"Meeting_File_{print_sel}.html", mime="text/html", use_container_width=True, type="primary")

    # =====================================================================
    # TAB 5: ADVANCED ACTION TRACKER & ATR (Unchanged Logic)
    # =====================================================================
    tracker_tab = tab5 if role == "department" else tab5
    with tracker_tab:
        st.markdown("#### 🎯 Resolution Tracker & Action Taken Reports (ATR)")
        st.caption("Centralized synchronization feed. District/Block administrators can correct commitment text, while Departments submit real-time ATR progress.")
        
        if df_ap.empty:
            st.info("No action items available.")
        else:
            c_f1, c_f2 = st.columns(2)
            f_dept = c_f1.selectbox("Filter Department", ["All"] + dept_labels)
            f_flag = c_f2.selectbox("Filter SLA Flag", ["All", "🟢 CLOSED", "🔴 OVERDUE", "🟡 DUE TODAY", "🔵 ON TRACK", "🟠 FOR REVIEW", "⚪ NOT STARTED"])

            filtered_df = df_ap.copy()
            if f_dept != "All": filtered_df = filtered_df[filtered_df["Department / Wing"] == f_dept]
            if f_flag != "All": filtered_df = filtered_df[filtered_df["Tracker Flag"] == f_flag]

            st.dataframe(filtered_df[["Origin Meeting", "Department / Wing", "action_point", "deadline", "Tracker Flag", "status", "remarks"]].sort_values("Tracker Flag"), use_container_width=True, hide_index=True)

            # CONTROLLED EDIT WORKFLOW
            if role in ["superadmin", "district", "block"]:
                st.markdown("---")
                st.markdown("##### ✏️ Authorized Correction of Original Commitment")
                with st.form("edit_commitment_form"):
                    edit_ap_id = st.selectbox("Select Commitment to Correct", filtered_df['id'].tolist(), format_func=lambda x: f"[{filtered_df[filtered_df['id']==x]['Origin Meeting'].values[0]}] {filtered_df[filtered_df['id']==x]['action_point'].values[0][:50]}...", key="edit_commit_sel")
                    target_row = filtered_df[filtered_df['id'] == edit_ap_id].iloc[0]
                    new_action_text = st.text_area("Corrected Action Point / Directive*", value=target_row.get('action_point', ''))
                    new_deadline = st.date_input("Corrected Deadline", value=pd.to_datetime(target_row.get('deadline')).date() if pd.notna(target_row.get('deadline')) else date.today())
                    correction_reason = st.text_input("Reason for Correction (Audited)*", placeholder="e.g. Corrected as per signed physical proceedings file.")

                    if st.form_submit_button("Confirm Commitment Correction", type="primary"):
                        if not correction_reason.strip():
                            st.error("⚠️ Mandatory Audit Reason: You must state why this commitment is being corrected.")
                        else:
                            update_payload = {
                                "action_point": new_action_text,
                                "deadline": str(new_deadline),
                                "remarks": f"[Corrected by {role.upper()}: {correction_reason}] | {target_row.get('remarks', '')}"
                            }
                            supabase.table("meeting_action_points").update(update_payload).eq("id", edit_ap_id).execute()
                            log_action(user.get('id'), f"CORRECTED meeting_action_points {edit_ap_id} - Reason: {correction_reason}")
                            st.success("✅ Commitment successfully corrected and audited in real-time!")
                            st.rerun()

            # DEPARTMENT ATR SUBMISSION WORKFLOW
            st.markdown("---")
            st.markdown("##### 📝 Submit Department ATR Update")
            with st.form("global_update_atr"):
                c_u1, c_u2 = st.columns(2)
                ap_id = c_u1.selectbox("Select Resolution", filtered_df["id"].tolist(), key="atr_res_sel")
                new_ap_status = c_u2.selectbox("Update Status", ["Not Started", "On Track", "Completed", "Not Feasible (Requires Review)", "Dropped"])
                atr_remarks = st.text_area("ATR Findings / Justification (Required if Not Feasible)")

                if st.form_submit_button("Submit ATR Update", type="primary"):
                    if new_ap_status == "Not Feasible (Requires Review)" and not atr_remarks.strip():
                        st.error("⚠️ Mandatory Justification: State why this item is Not Feasible for Chairperson review.")
                    else:
                        try: supabase.table("meeting_action_points").update({"status": new_ap_status, "remarks": atr_remarks}).eq("id", ap_id).execute()
                        except: supabase.table("meeting_action_points").update({"status": new_ap_status.lower().replace(" ", "_"), "remarks": atr_remarks}).eq("id", ap_id).execute()
                        log_action(user.get('id'), f"UPDATE ATR meeting_action_points {ap_id}")
                        st.success("✅ ATR submitted successfully.")
                        st.rerun()

    # =====================================================================
    # TAB 6: AUTOMATED NEXT AGENDA PREP (Admin Only - Unchanged Logic)
    # =====================================================================
    if role != "department":
        with tab6:
            st.markdown("#### ⏭️ Auto-Generated Next Meeting Agenda")
            district_id = user.get("district_id")
            if not district_id:
                st.info("Select district context to compile automated agenda.")
            else:
                agenda_text = "STATUTORY CONVERGENCE COMMITTEE — UPCOMING AGENDA:\n\n"
                has_items = False

                q_targets = supabase.table("department_targets").select("*").eq("district_id", district_id)
                try: q_targets = q_targets.eq("financial_year", active_fy)
                except: pass
                t_data = q_targets.execute().data

                if t_data:
                    df_t = pd.DataFrame(t_data)
                    q_reg = supabase.table("convergence_register").select("department_id, activity_description").eq("district_id", district_id)
                    df_r = pd.DataFrame(q_reg.execute().data) if q_reg.execute().data else pd.DataFrame()
                    low_targets = ""
                    for idx, row in df_t.iterrows():
                        d_id, act = row['department_id'], row['activity']
                        t_val = safe_int(row.get('desired_target', 0))
                        
                        e_count = 0
                        if not df_r.empty and 'department_id' in df_r.columns and 'activity_description' in df_r.columns:
                            dept_r = df_r[df_r['department_id'] == d_id]
                            if not dept_r.empty:
                                mask = dept_r['activity_description'].apply(lambda x: str(act).lower() in str(x).lower() if pd.notna(x) else False)
                                e_count = safe_int(mask.sum())

                        if t_val > 0 and (e_count / t_val) < 0.5:
                            low_targets += f"- [{dept_map.get(d_id, 'Unknown')}] {act}: Target {t_val} | Achieved {e_count} (Deficit > 50%)\n"

                    if low_targets:
                        has_items = True
                        agenda_text += "📊 1. REVIEW OF CRITICAL TARGET GAPS (<50% Achieved):\n" + low_targets + "\n"

                if not df_ap.empty:
                    active_df = df_ap[~df_ap["Tracker Flag"].isin(["🟢 CLOSED"])]
                    unfeasible_df = active_df[active_df["Tracker Flag"] == "🟠 FOR REVIEW"]
                    overdue_df = active_df[active_df["Tracker Flag"] == "🔴 OVERDUE"]

                    if not unfeasible_df.empty:
                        has_items = True
                        agenda_text += "🟠 2. ITEMS FLAGGED AS NOT FEASIBLE (FOR CHAIRPERSON REVIEW):\n"
                        for idx, row in unfeasible_df.iterrows():
                            agenda_text += f"- [{row['Department / Wing']}] {row['action_point']}\n  Reason: {row.get('remarks', 'N/A')}\n\n"

                    if not overdue_df.empty:
                        has_items = True
                        agenda_text += "🔴 3. OVERDUE COMMITMENTS (SLA BREACH):\n"
                        for idx, row in overdue_df.iterrows():
                            agenda_text += f"- [{row['Department / Wing']}] {row['action_point']}\n"

                if has_items:
                    st.warning("⚠️ High-priority governance exceptions identified for next meeting notice.")
                    st.text_area("Compiled Agenda Text:", value=agenda_text, height=350)
                else:
                    st.success("🎉 No overdue items or severe target gaps detected.")
