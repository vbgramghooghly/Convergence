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
        </style>
        """,
        unsafe_allow_html=True,
    )


def show():
    require_role("superadmin", "district", "block", "department")
    inject_custom_css()

    st.markdown(
        "<h1 style='color: #1F77B4;'>📋 Convergence Meeting & Resolution Tracker</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()
    role = user["role"]

    # ======================== 1. MASTER DATA FETCH ========================
    departments = supabase.table("departments").select("id, department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data or []

    dept_map = {d["id"]: d["department_name"] for d in departments}
    wing_map = {w["id"]: w for w in wings}
    block_dict_reverse = {b["id"]: b["block_name"] for b in blocks_data}

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
    unified_label_to_uid = {u["label"]: u["uid"] for u in unified_depts}

    # Helper function to format Department/Wing display cleanly for dataframes
    def format_dept_display(row):
        d_name = dept_map.get(row.get("department_id"), "Unknown")
        w_id = row.get("wing_id")
        if w_id and not pd.isna(w_id) and w_id in wing_map:
            return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
        return f"{d_name} (Main)"

    # Global Meeting Fetch for the Jurisdiction
    query = supabase.table("meetings").select("*")
    if role in ["district", "department"]:
        query = query.eq("district_id", user["district_id"])
    elif role == "block":
        query = query.eq("block_id", user["block_id"])

    meetings = query.order("meeting_date", desc=True).execute().data
    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()

    # ======================== TABS LAYOUT ========================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📅 Dashboard",
        "🗓️ Schedule Meeting",
        "✍️ Record Proceedings",
        "🎯 Resolution Tracker",
        "🖨️ Reports & Registers",
        "⏭️ Next Agenda Prep",
    ])

    # ======================== TAB 1: MEETING DASHBOARD ========================
    with tab1:
        st.subheader("Meeting Dashboard")
        if not df_meetings.empty:
            df_m = df_meetings.copy()
            df_m["Block"] = df_m["block_id"].map(block_dict_reverse).fillna("District Level")
            disp_df = df_m[["meeting_date", "meeting_type", "Block", "venue", "chairperson"]].copy()
            disp_df["status"] = df_m.get("status", "Convened").fillna("Convened")

            st.dataframe(disp_df, use_container_width=True, hide_index=True)

            st.markdown("### 🔍 View Detailed Proceedings & Attendance")
            detail_sel = st.selectbox(
                "Select Meeting Date to view details",
                df_meetings["id"].tolist(),
                format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['meeting_type'].values[0]} Level",
            )

            sel_meeting_data = df_meetings[df_meetings["id"] == detail_sel].iloc[0]

            with st.container(border=True):
                st.markdown(
                    f"<h3 style='color: #2B8A3E;'>Meeting Details: {sel_meeting_data['meeting_date']}</h3>",
                    unsafe_allow_html=True,
                )
                col_d1, col_d2 = st.columns(2)
                col_d1.write(f"**Chairperson:** {sel_meeting_data.get('chairperson', 'None')}")
                col_d1.write(f"**Level:** {sel_meeting_data.get('meeting_type', 'None')}")
                col_d2.write(f"**Venue:** {sel_meeting_data.get('venue', 'None')}")
                col_d2.write(f"**Financial Year:** {sel_meeting_data.get('financial_year', 'None')}")

                st.write(f"**Objective / Agenda:** {sel_meeting_data.get('objective', 'None')}")
                st.write(f"**General Decisions:** {sel_meeting_data.get('decisions', 'None')}")

                st.markdown("#### 👥 Department-Wise Attendance")
                att_data = sel_meeting_data.get("detailed_attendance")
                if att_data and isinstance(att_data, list) and len(att_data) > 0:
                    att_df = pd.DataFrame(att_data)
                    disp_att_df = att_df[["label", "attended_by_subordinate"]]
                    disp_att_df.columns = ["Department / Wing", "Attended by Subordinate?"]

                    def highlight_subs(row):
                        return ["background-color: #FFF3CD"] * len(row) if row["Attended by Subordinate?"] else [""] * len(row)

                    st.dataframe(disp_att_df.style.apply(highlight_subs, axis=1), use_container_width=True, hide_index=True)
                else:
                    st.info("No detailed attendance captured for this meeting yet. Please record proceedings in Tab 3.")

        else:
            st.info("No meetings found for your assigned jurisdiction.")

    # ======================== TAB 2: SCHEDULE MEETING ========================
    with tab2:
        st.subheader("Step 1: Schedule New Convergence Meeting")
        st.caption("Plan the meeting details and select invited departments. Proceedings will be recorded after convening.")

        if role == 'department':
            st.warning("🔒 Meeting scheduling and administrative controls are managed by the District and Block administration.")
        else:
            col_m1, col_m2, col_m3 = st.columns(3)
            if role in ["superadmin", "district"]:
                meeting_type = col_m1.radio("Meeting Level", ["District", "Block"], horizontal=True)
            else:
                meeting_type = "Block"
                col_m1.info("Meeting Level: Block")

            financial_year = col_m2.selectbox("Financial Year", ["2026-27", "2027-28", "2028-29"])
            meeting_date = col_m3.date_input("Meeting Date", date.today())

            if meeting_type == "District":
                districts_fetch = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
                dist_dict = {d["district_name"]: d["id"] for d in districts_fetch}
                dist_sel = next((name for name, id in dist_dict.items() if id == user.get("district_id")), list(dist_dict.keys())[0])
                if role != "district":
                    dist_sel = st.selectbox("District", list(dist_dict.keys()))
                block_sel = None
                chair_default = "District Magistrate & District Programme Coordinator (DPC)"
            else:
                if role == "block":
                    block_sel = block_dict_reverse.get(user["block_id"], "Unknown Block")
                    st.text(f"Jurisdiction: {block_sel}")
                    dist_sel = next(b["district_id"] for b in blocks_data if b["id"] == user["block_id"])
                else:
                    block_sel = st.selectbox("Block Jurisdiction", [b["block_name"] for b in blocks_data])
                    dist_sel = next(b["district_id"] for b in blocks_data if b["block_name"] == block_sel)
                chair_default = "Block Development Officer (BDO)"

            with st.form("schedule_meeting_form"):
                col_a1, col_a2 = st.columns(2)
                chairperson = col_a1.text_input("Chairperson (Name & Designation)", value=chair_default)
                venue = col_a2.text_input("Venue / Platform")
                objective = st.text_input("Meeting Objective / Schematic Discussion")

                st.markdown("---")
                st.markdown("### 📋 Select Invited Departments")
                st.caption("Select the Departments or Wings expected to attend this meeting.")
                
                invited_uids = st.multiselect(
                    "Invited Departments / Wings*",
                    options=[u["uid"] for u in unified_depts],
                    format_func=lambda x: unified_uid_to_label.get(x, x),
                )

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
                            "attendees": invited_uids, # Saving list of dept UIDs
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
                        if result.data:
                            st.success("✅ Meeting Scheduled successfully! Proceed to Tab 3 after convening.")
                            log_action(user.get("id"), f"CREATE meeting {result.data[0]['id']}")
                            st.rerun()

    # ======================== TAB 3: RECORD PROCEEDINGS ========================
    with tab3:
        st.subheader("Step 2: Record Meeting Proceedings")
        st.caption("Mark department-wise attendance, review targets, add minutes, and assign new resolutions.")

        if df_meetings.empty:
            st.info("No meetings available to record.")
        else:
            if "status" not in df_meetings.columns:
                df_meetings["status"] = "Convened"

            sched_meetings = df_meetings[df_meetings["status"] == "Scheduled"]

            if sched_meetings.empty:
                st.info("No active 'Scheduled' meetings. Showing all meetings for retroactive recording.")
                proc_sel = st.selectbox(
                    "Select Meeting to Record",
                    df_meetings["id"].tolist(),
                    format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['objective'].values[0]} ({df_meetings[df_meetings['id'] == x]['status'].values[0]})",
                )
            else:
                proc_sel = st.selectbox(
                    "Select Scheduled Meeting to Convene",
                    sched_meetings["id"].tolist(),
                    format_func=lambda x: f"{sched_meetings[sched_meetings['id'] == x]['meeting_date'].values[0]} | {sched_meetings[sched_meetings['id'] == x]['objective'].values[0]}",
                )

            proc_meeting_data = df_meetings[df_meetings["id"] == proc_sel].iloc[0]

            # --- A. MARK ACTUAL ATTENDANCE (DEPARTMENT-WISE) ---
            with st.expander("👥 A. Mark Department-Wise Attendance", expanded=True):
                invited_uids = proc_meeting_data.get("attendees") or []
                
                if not invited_uids:
                    st.warning("No departments were invited to this meeting.")
                else:
                    st.markdown("Check the box if the department was present. If a subordinate represented the department head, check the Subordinate box.")
                    detailed_attendance_payload = []
                    
                    with st.container():
                        for uid in invited_uids:
                            label = unified_uid_to_label.get(uid, "Unknown Department")
                            
                            col_a1, col_a2 = st.columns([2, 1])
                            is_present = col_a1.checkbox(f"✅ {label}", value=True, key=f"pres_{uid}_{proc_sel}")
                            
                            is_sub = False
                            if is_present:
                                is_sub = col_a2.checkbox("Attended by Subordinate?", key=f"sub_{uid}_{proc_sel}")
                                
                                detailed_attendance_payload.append({
                                    "uid": uid,
                                    "label": label,
                                    "attended_by_subordinate": is_sub
                                })
                                
                        if st.button("Save Attendance Register", type="primary"):
                            supabase.table("meetings").update({
                                "detailed_attendance": detailed_attendance_payload
                            }).eq("id", proc_sel).execute()
                            st.success("✅ Department-wise attendance saved.")
                            st.rerun()

            # --- B. REVIEW TARGETS & PAST PROGRESS ---
            with st.expander("📊 B. Review Department Targets & Past Progress", expanded=False):
                st.markdown("#### 1. Live Implementation Target Compliance")
                st.caption("Review how departments are performing against their annual physical targets to guide the meeting agenda.")
                
                q_targets = supabase.table("department_targets").select("*").eq("district_id", proc_meeting_data["district_id"])
                q_reg = supabase.table("convergence_register").select("department_id, activity_description").eq("district_id", proc_meeting_data["district_id"])
                
                if proc_meeting_data["meeting_type"] == "Block":
                    q_reg = q_reg.eq("block_id", proc_meeting_data["block_id"])
                    
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
                        
                        gap = e_count - t_val
                        stat = "Less Entered" if gap < 0 else "Target Matched" if gap == 0 else "Extra Entered"
                        
                        comp_data.append({
                            "Department": dept_map.get(d_id, "Unknown"),
                            "Target Activity": act,
                            "Target": t_val,
                            "Captured": e_count,
                            "Status": stat
                        })
                        
                    df_comp = pd.DataFrame(comp_data)
                    def style_comp(row):
                        return ['background-color: #ffebee; color: #b71c1c;'] * len(row) if row['Status'] != "Target Matched" else [''] * len(row)
                    st.dataframe(df_comp.style.apply(style_comp, axis=1), use_container_width=True, hide_index=True)
                else:
                    st.info("No targets set for this jurisdiction.")

                st.markdown("#### 2. Previous Meeting Resolutions")
                past_ap_query = supabase.table("meeting_action_points").select("*, meetings!inner(district_id, block_id, meeting_type)").neq("status", "Completed").neq("status", "Dropped").execute().data
                
                if past_ap_query:
                    df_past = pd.DataFrame(past_ap_query)
                    if proc_meeting_data["meeting_type"] == "District":
                        df_past = df_past[df_past["meetings"].apply(lambda x: x.get("district_id") == proc_meeting_data["district_id"])]
                    else:
                        df_past = df_past[df_past["meetings"].apply(lambda x: x.get("block_id") == proc_meeting_data["block_id"])]

                    if not df_past.empty:
                        df_past["Department / Wing"] = df_past.apply(format_dept_display, axis=1)
                        st.dataframe(df_past[["Department / Wing", "action_point", "status", "remarks"]], use_container_width=True, hide_index=True)
                    else:
                        st.info("No pending resolutions for this jurisdiction.")
                else:
                    st.info("No past action points found.")

            # --- C. GENERAL MINUTES & NEW RESOLUTIONS ---
            with st.expander("📝 C. General Minutes & New Resolutions", expanded=True):
                general_minutes = st.text_area("General Discussion / Meeting Minutes", value=proc_meeting_data.get("decisions", "") or "", height=100)
                
                if st.button("Save General Minutes"):
                    supabase.table("meetings").update({"decisions": general_minutes}).eq("id", proc_sel).execute()
                    st.success("Minutes saved.")

                st.markdown("---")
                st.markdown("#### Assign New Resolutions")

                with st.form("add_new_resolution"):
                    # Use Unified Department / Wing Dropdown
                    res_dept_label = st.selectbox("Assign to Department / Wing*", dept_labels)
                    selected_opt = next(opt for opt in unified_depts if opt['label'] == res_dept_label)
                    res_dept_id = selected_opt['dept_id']
                    res_wing_id = selected_opt['wing_id']

                    res_action = st.text_area("Resolution / Action Point Required*")

                    col_r3, col_r4, col_r5 = st.columns([1, 1, 1])
                    res_target = col_r3.text_input("Desired Target (Optional)")
                    has_deadline = col_r4.checkbox("Set Target Date?", value=True)
                    res_deadline = col_r5.date_input("Target Date", date.today())

                    if st.form_submit_button("Add Resolution to Tracker", type="primary"):
                        if not res_action.strip():
                            st.error("Action point cannot be empty.")
                        else:
                            res_payload = {
                                "meeting_id": proc_sel,
                                "department_id": res_dept_id,
                                "wing_id": res_wing_id,
                                "action_point": res_action.strip(),
                                "target": res_target if res_target.strip() else None,
                                "responsible_officer": "Department Representative", # Generic fallback to satisfy DB constraints
                                "deadline": str(res_deadline) if has_deadline else None,
                                "status": "Under Process",
                                "priority": "Medium",
                            }
                            try:
                                supabase.table("meeting_action_points").insert(res_payload).execute()
                                st.success("✅ Resolution added successfully!")
                                st.rerun()
                            except Exception as e:
                                if "wing_id" in str(e):
                                    st.error("🚨 Database Check: Make sure you added `wing_id` to `meeting_action_points` table in Supabase.")
                                else:
                                    try:
                                        res_payload["status"] = "under_process"
                                        res_payload["priority"] = "medium"
                                        supabase.table("meeting_action_points").insert(res_payload).execute()
                                        st.success("✅ Resolution added successfully!")
                                        st.rerun()
                                    except Exception as err2:
                                        st.error(f"Database Check Constraint Error: {err2}.")

            # --- D. FINALIZE MEETING ---
            st.markdown("---")
            if proc_meeting_data.get("status") == "Scheduled":
                if st.button("🔒 Complete Proceedings & Mark as Convened", type="primary", use_container_width=True):
                    supabase.table("meetings").update({"status": "Convened"}).eq("id", proc_sel).execute()
                    st.success("Meeting locked and Convened! Resolutions synced to Department Dashboards.")
                    st.rerun()

    # ======================== TAB 4: RESOLUTION TRACKER ========================
    with tab4:
        st.subheader("🎯 Master Resolution Tracker")
        if df_meetings.empty:
            st.info("No meetings found. Please schedule a meeting first.")
        else:
            tr_meeting_sel = st.selectbox(
                "Select Meeting to Track",
                ["All"] + df_meetings["id"].tolist(),
                format_func=lambda x: "All Meetings" if x == "All" else f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['objective'].values[0]}",
            )

            ap_query = supabase.table("meeting_action_points").select("*")
            if tr_meeting_sel != "All":
                ap_query = ap_query.eq("meeting_id", tr_meeting_sel)

            ap_data = ap_query.execute().data

            if ap_data:
                df_ap = pd.DataFrame(ap_data)
                
                # Filter by jurisdiction/role
                if role == 'department':
                    df_ap = df_ap[df_ap['department_id'] == user['department_id']]
                else:
                    valid_meet_ids = [m['id'] for m in meetings]
                    df_ap = df_ap[df_ap['meeting_id'].isin(valid_meet_ids)]
                    
                if not df_ap.empty:
                    df_ap["Department / Wing"] = df_ap.apply(format_dept_display, axis=1)

                    m_context_map = {m["id"]: f"{m['meeting_date']} ({m['meeting_type']})" for m in meetings}
                    df_ap["Origin Meeting"] = df_ap["meeting_id"].map(m_context_map)

                    today = pd.to_datetime(date.today())
                    df_ap["deadline"] = pd.to_datetime(df_ap["deadline"], errors="coerce")

                    def get_flag(row):
                        stat = str(row.get("status", "")).lower()
                        if stat in ["completed", "dropped"]: return "✅ Closed"
                        if "feasible" in stat or "review" in stat: return "🔴 FOR REVIEW"
                        if pd.isna(row["deadline"]): return "⏳ No Deadline"
                        days_rem = (row["deadline"] - today).days
                        if days_rem < 0: return "🚨 OVERDUE"
                        if days_rem == 0: return "⚠️ Due Today"
                        return "⏳ On Track"

                    df_ap["Tracker Flag"] = df_ap.apply(get_flag, axis=1)

                    display_cols = ["id", "Department / Wing", "action_point", "target", "deadline", "Tracker Flag", "status"]
                    st.dataframe(df_ap[display_cols].sort_values("Tracker Flag"), use_container_width=True, hide_index=True)

                    st.markdown("### ✏️ Update Progress / Action Taken Report")
                    with st.form("global_update_atr"):
                        col_u1, col_u2 = st.columns(2)
                        ap_id = col_u1.selectbox("Select Resolution ID", df_ap["id"].tolist())

                        new_ap_status = col_u2.selectbox("Update Status", ["Under Process", "Approved", "Under Execution", "Completed", "Not Feasible (Requires Review)", "Dropped"])
                        remarks = st.text_area("Outcome / Action Taken")

                        if st.form_submit_button("Update Progress"):
                            try:
                                supabase.table("meeting_action_points").update({"status": new_ap_status, "remarks": remarks}).eq("id", ap_id).execute()
                                log_action(user.get("id"), f"UPDATE resolution {ap_id}")
                                st.success("✅ Progress updated successfully.")
                                st.rerun()
                            except Exception as e:
                                try:
                                    supabase.table("meeting_action_points").update({"status": new_ap_status.lower().replace(" ", "_"), "remarks": remarks}).eq("id", ap_id).execute()
                                    st.success("✅ Progress updated successfully.")
                                    st.rerun()
                                except Exception as e2:
                                    st.error(f"Error updating status: {e2}")
                else:
                    st.info("No actionable resolutions found for your purview.")
            else:
                st.info("No action points have been recorded in the system yet.")

    # ======================== TAB 5: PRINT & REPORTS ========================
    with tab5:
        st.subheader("🖨️ Meeting & Resolution Reports")
        report_type = st.radio("Select Report Type", ["By Specific Meeting (Chairperson Report)", "Date-Wise Resolution Register"], horizontal=True)
        st.markdown("---")

        if report_type == "By Specific Meeting (Chairperson Report)":
            if not df_meetings.empty:
                rep_mtg_sel = st.selectbox(
                    "Select Meeting for Report",
                    df_meetings["id"].tolist(),
                    format_func=lambda x: f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]} | {df_meetings[df_meetings['id'] == x]['objective'].values[0]}",
                )
                sel_meeting_data = df_meetings[df_meetings["id"] == rep_mtg_sel].iloc[0]

                att_data = sel_meeting_data.get("detailed_attendance")
                attendance_html = ""
                if att_data and isinstance(att_data, list):
                    attendance_html += "<table class='print-table'><tr><th>Department / Wing</th><th>Attended By</th></tr>"
                    for att in att_data:
                        dept_name = att.get("label", "Unknown")
                        att_by = "Subordinate Representative" if att.get("attended_by_subordinate") else "Department Head / Nodal"
                        row_style = "background-color: #fff3cd;" if att.get("attended_by_subordinate") else ""
                        attendance_html += f"<tr style='{row_style}'><td>{dept_name}</td><td>{att_by}</td></tr>"
                    attendance_html += "</table>"
                else:
                    attendance_html = "<p>No detailed attendance recorded.</p>"

                mtg_ap = supabase.table("meeting_action_points").select("*").eq("meeting_id", rep_mtg_sel).execute().data
                if mtg_ap:
                    df_rep_ap = pd.DataFrame(mtg_ap)
                    df_rep_ap["Department / Wing"] = df_rep_ap.apply(format_dept_display, axis=1)
                    
                    print_df = df_rep_ap[["Department / Wing", "action_point", "target", "status", "remarks"]].copy()
                    print_df.columns = ["Department / Wing", "Resolution / Commitment", "Target", "Status", "Outcome / Remarks"]
                    html_table = print_df.to_html(index=False, classes="print-table")
                else:
                    html_table = "<p>No resolutions recorded.</p>"

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
                b64_html = base64.b64encode(printable_html.encode("utf-8")).decode("utf-8")
                print_href = f"""<a href="data:text/html;base64,{b64_html}" download="Meeting_Report_{sel_meeting_data['meeting_date']}.html" style="text-decoration: none;">
                            <div style="background-color: #2B8A3E; color: white; padding: 10px 15px; border-radius: 6px; text-align: center; font-weight: bold; cursor: pointer;">
                                📥 Download & Print Chairperson Report
                            </div></a>"""
                st.markdown(print_href, unsafe_allow_html=True)
            else:
                st.warning("Please schedule a meeting first.")

        elif report_type == "Date-Wise Resolution Register":
            st.markdown("#### Select Date Range for Resolutions")
            col_dt1, col_dt2 = st.columns(2)
            start_date = col_dt1.date_input("Start Date", value=date.today().replace(day=1))
            end_date = col_dt2.date_input("End Date", value=date.today())

            if not df_meetings.empty:
                mask = (pd.to_datetime(df_meetings["meeting_date"]).dt.date >= start_date) & (pd.to_datetime(df_meetings["meeting_date"]).dt.date <= end_date)
                filtered_meetings = df_meetings.loc[mask]

                if not filtered_meetings.empty:
                    meeting_ids = filtered_meetings["id"].tolist()
                    m_map = {m["id"]: m for m in filtered_meetings.to_dict("records")}

                    date_ap_query = supabase.table("meeting_action_points").select("*").in_("meeting_id", meeting_ids).execute().data
                    if date_ap_query:
                        df_date_ap = pd.DataFrame(date_ap_query)
                        df_date_ap["Department / Wing"] = df_date_ap.apply(format_dept_display, axis=1)
                        df_date_ap["Meeting Date"] = df_date_ap["meeting_id"].map(lambda x: m_map.get(x, {}).get("meeting_date", "Unknown"))
                        df_date_ap["Meeting Level"] = df_date_ap["meeting_id"].map(lambda x: m_map.get(x, {}).get("meeting_type", "Unknown"))

                        disp_cols = ["Meeting Date", "Meeting Level", "Department / Wing", "action_point", "target", "status"]
                        st.dataframe(df_date_ap[disp_cols].sort_values(["Meeting Date", "Department / Wing"]), use_container_width=True, hide_index=True)

                        print_df = df_date_ap[disp_cols].copy()
                        print_df.columns = ["Date", "Level", "Department / Wing", "Resolution / Commitment", "Target", "Status"]
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
                        b64_html_date = base64.b64encode(date_printable_html.encode("utf-8")).decode("utf-8")
                        date_print_href = f"""<a href="data:text/html;base64,{b64_html_date}" download="Resolution_Register_{start_date}_to_{end_date}.html" style="text-decoration: none;">
                                        <div style="background-color: #1F77B4; color: white; padding: 10px 15px; border-radius: 6px; text-align: center; font-weight: bold; cursor: pointer; margin-top: 15px;">
                                            📥 Download & Print Date-Wise Register
                                        </div></a>"""
                        st.markdown(date_print_href, unsafe_allow_html=True)
                    else:
                        st.info("No resolutions found in the selected date range.")
                else:
                    st.info("No meetings found in the selected date range.")
            else:
                st.info("No meeting data available.")

    # ======================== TAB 6: NEXT MEETING AGENDA PREP ========================
    with tab6:
        st.subheader("⏭️ Next Meeting Agenda Preparation")

        agenda_text = "AGENDA FOR UPCOMING MEETING:\n\n"
        has_items = False

        # 1. Fetch Target Data for the jurisdiction
        q_targets = supabase.table("department_targets").select("*").eq("district_id", user["district_id"])
        if role == "block": # Targets are district wide, but to keep consistent, fetch district targets
            pass 
        t_data = q_targets.execute().data
        
        if t_data:
            has_items = True
            agenda_text += "📊 DEPARTMENT TARGETS PROGRESS REVIEW:\n"
            df_t = pd.DataFrame(t_data)
            
            # Fetch Register to calculate live progress
            q_reg = supabase.table("convergence_register").select("department_id, activity_description").eq("district_id", user["district_id"])
            if role == "block":
                q_reg = q_reg.eq("block_id", user["block_id"])
            df_r = pd.DataFrame(q_reg.execute().data) if q_reg.execute().data else pd.DataFrame()
            
            for idx, row in df_t.iterrows():
                d_id = row['department_id']
                act = row['activity']
                t_val = int(row['desired_target'])
                
                e_count = 0
                if not df_r.empty:
                    dept_r = df_r[df_r['department_id'] == d_id]
                    if 'activity_description' in dept_r.columns:
                        e_count = dept_r['activity_description'].apply(lambda x: str(act).lower() in str(x).lower()).sum()
                
                gap = e_count - t_val
                stat = "Needs Update" if gap < 0 else "Matched" if gap == 0 else "Mismatch/Extra"
                d_name = dept_map.get(d_id, 'Unknown')
                
                agenda_text += f"- [{d_name}] {act}: Target {t_val} | Captured: {e_count} ({stat})\n"
            agenda_text += "\n"

        # 2. Fetch Pending Resolutions
        all_ap = supabase.table("meeting_action_points").select("*").execute().data
        if all_ap:
            df_all_ap = pd.DataFrame(all_ap)
            
            # Filter to relevant meetings
            valid_meet_ids = [m['id'] for m in meetings]
            df_all_ap = df_all_ap[df_all_ap['meeting_id'].isin(valid_meet_ids)]
            
            if not df_all_ap.empty:
                df_all_ap["Department"] = df_all_ap.apply(format_dept_display, axis=1)

                df_all_ap["is_completed"] = df_all_ap["status"].apply(lambda x: str(x).lower() in ["completed", "dropped"])
                active_df = df_all_ap[~df_all_ap["is_completed"]]

                unfeasible_df = active_df[active_df["status"].apply(lambda x: "feasible" in str(x).lower() or "review" in str(x).lower())]
                pending_df = active_df[~active_df["status"].apply(lambda x: "feasible" in str(x).lower() or "review" in str(x).lower())]

                if not unfeasible_df.empty or not pending_df.empty:
                    has_items = True

                    if not unfeasible_df.empty:
                        agenda_text += "🔴 ITEMS FLAGGED AS NOT FEASIBLE (FOR REVIEW):\n"
                        for idx, row in unfeasible_df.iterrows():
                            agenda_text += f"- [{row['Department']}] {row['action_point']}\n  Reason: {row.get('remarks', 'N/A')}\n\n"

                    if not pending_df.empty:
                        agenda_text += "⏳ PENDING / OVERDUE COMMITMENTS:\n"
                        for idx, row in pending_df.iterrows():
                            agenda_text += f"- [{row['Department']}] {row['action_point']}\n"

        if has_items:
            st.warning("⚠️ Items found ready for the next agenda.")
            st.text_area("Copy Agenda Text:", value=agenda_text, height=400)
        else:
            st.success("🎉 No pending items or targets for the next meeting!")
