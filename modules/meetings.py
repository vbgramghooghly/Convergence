from datetime import date
import base64
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
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()
    today = pd.to_datetime(date.today())
    active_fy = st.session_state.get("selected_fy", "2026-27")

    # BREADCRUMB & HEADER
    st.markdown("<div style='font-size: 0.85rem; color: #64748B; margin-bottom: 0.5rem;'>Home / Statutory Governance / Convergence Meetings</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom: 0px; color: #0F4C81;'>🤝 Statutory Meeting Governance & Resolution Tracker</h2>", unsafe_allow_html=True)
    st.caption(f"FY {active_fy} | Coordinate Committee Meetings, Record Proceedings, Track ATRs, and Generate Agendas.")
    st.markdown("---")

    # MASTER DATA LOOKUPS (Preserved)
    departments = supabase.table("departments").select("id, department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    blocks_data = supabase.table("blocks").select("id, block_name, district_id").execute().data or []
    activities_data = supabase.table("activities").select("id, activity_name").eq("active", True).execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("activity_id, department_id").execute().data or []

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
        if w_id and not pd.isna(w_id) and w_id in wing_map: return f"{d_name} ➔ {wing_map[w_id]['wing_name']}"
        return f"{d_name} (Main)"

    # DATA FETCHING (Preserved)
    q_meetings = supabase.table("meetings").select("*").eq("financial_year", active_fy)
    if role in ["district", "department"]: q_meetings = q_meetings.eq("district_id", user["district_id"])
    elif role == "block": q_meetings = q_meetings.eq("block_id", user["block_id"])
    meetings = q_meetings.order("meeting_date", desc=True).execute().data or []

    if role == "department" and meetings:
        user_uid_main = f"{user.get('department_id')}_main"
        user_uid_wing = f"{user.get('department_id')}_{user.get('wing_id')}" if user.get('wing_id') else user_uid_main
        meetings = [m for m in meetings if (user_uid_main in (m.get('attendees') or [])) or (user_uid_wing in (m.get('attendees') or []))]

    df_meetings = pd.DataFrame(meetings) if meetings else pd.DataFrame()
    valid_meet_ids = [m['id'] for m in meetings]

    ap_data = supabase.table("meeting_action_points").select("*").in_("meeting_id", valid_meet_ids).execute().data if valid_meet_ids else []
    df_ap = pd.DataFrame(ap_data) if ap_data else pd.DataFrame()

    if not df_ap.empty:
        if role == "department":
            if user.get('wing_id'): df_ap = df_ap[(df_ap['department_id'] == user['department_id']) & (df_ap['wing_id'] == user['wing_id'])]
            else: df_ap = df_ap[(df_ap['department_id'] == user['department_id']) & (df_ap['wing_id'].isna())]

        df_ap["Department / Wing"] = df_ap.apply(format_dept_display, axis=1)
        df_ap["Origin Meeting"] = df_ap["meeting_id"].map({m["id"]: f"{m['meeting_date']} ({m['meeting_type']})" for m in meetings})
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
        c1.metric("Total Resolutions", len(df_ap))
        c2.metric("🟢 Closed", len(df_ap[df_ap["Tracker Flag"] == "🟢 CLOSED"]))
        c3.metric("🔵 On Track", len(df_ap[df_ap["Tracker Flag"] == "🔵 ON TRACK"]))
        c4.metric("🟡 Due Today", len(df_ap[df_ap["Tracker Flag"] == "🟡 DUE TODAY"]))
        c5.metric("🔴 Overdue", len(df_ap[df_ap["Tracker Flag"] == "🔴 OVERDUE"]))
        c6.metric("🟠 Needs Review", len(df_ap[df_ap["Tracker Flag"] == "🟠 FOR REVIEW"]))
        st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 SLA Performance", 
        "🗓️ Schedule Meeting", 
        "✍️ Proceedings & Attendance", 
        "🎯 Action Tracker & ATR", 
        "🖨️ Master Export", 
        "⏭️ Next Agenda Prep"
    ])

    # =====================================================================
    # TAB 1: SLA PERFORMANCE DASHBOARD
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
    # TAB 2: SCHEDULE MEETING
    # =====================================================================
    with tab2:
        st.markdown("#### 🗓️ Schedule Convergence Committee Meeting")
        if role == 'department':
            st.warning("🔒 Meeting scheduling is restricted to District and Block Administrations.")
        else:
            with st.container(border=True):
                col_m1, col_m2, col_m3 = st.columns(3)
                meeting_type = col_m1.radio("Meeting Tier", ["District", "Block"], horizontal=True) if role in ["superadmin", "district"] else "Block"
                col_m2.text_input("Financial Year", value=active_fy, disabled=True)
                meeting_date = col_m3.date_input("Scheduled Date", date.today())

                if meeting_type == "District":
                    districts_fetch = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
                    dist_dict = {d["district_name"]: d["id"] for d in districts_fetch}
                    dist_sel = next((name for name, id in dist_dict.items() if id == user.get("district_id")), list(dist_dict.keys())[0])
                    block_sel = None
                    chair_default = "District Magistrate & District Programme Coordinator (DPC)"
                else:
                    block_sel = block_dict_reverse.get(user["block_id"], "Unknown Block") if role == "block" else st.selectbox("Block Jurisdiction", [b["block_name"] for b in blocks_data])
                    dist_sel = next(b["district_id"] for b in blocks_data if b["block_name"] == block_sel) if role != "block" else user["district_id"]
                    chair_default = "Block Development Officer (BDO)"

                with st.form("schedule_meeting_form"):
                    c_a1, c_a2 = st.columns(2)
                    chairperson = c_a1.text_input("Chairperson*", value=chair_default)
                    venue = c_a2.text_input("Venue / Meeting Platform*")
                    objective = st.text_input("Agenda / Schematic Objective*")
                    invited_uids = st.multiselect("Invite Departments & Wings*", options=[u["uid"] for u in unified_depts], format_func=lambda x: unified_uid_to_label.get(x, x))

                    if st.form_submit_button("Issue Meeting Notice", type="primary", use_container_width=True):
                        if not invited_uids: st.error("Please invite at least one Department/Wing.")
                        else:
                            meeting_data = {
                                "meeting_type": meeting_type, "financial_year": active_fy, "meeting_date": str(meeting_date),
                                "chairperson": chairperson, "venue": venue, "objective": objective, "attendees": invited_uids,
                                "status": "Scheduled", "created_by": user["id"]
                            }
                            if meeting_type == "District": meeting_data["district_id"] = dist_dict[dist_sel] if role != "district" else user["district_id"]
                            else:
                                block_obj = next(b for b in blocks_data if b["block_name"] == block_sel)
                                meeting_data["block_id"] = block_obj["id"]
                                meeting_data["district_id"] = block_obj["district_id"]

                            supabase.table("meetings").insert(meeting_data).execute()
                            st.success("✅ Meeting notice dispatched successfully!")
                            st.rerun()

    # =====================================================================
    # TAB 3: PROCEEDINGS & ATTENDANCE
    # =====================================================================
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

            # ATTENDANCE
            with st.expander("👥 A. Statutory Attendance Register", expanded=not is_locked):
                invited_uids = proc_mtg.get("attendees") or []
                if not invited_uids:
                    st.warning("No departments invited.")
                else:
                    if is_locked or role == "department":
                        att_data = proc_mtg.get("detailed_attendance") or []
                        if att_data:
                            adf = pd.DataFrame(att_data)[["label", "attended_by_subordinate"]]
                            adf.columns = ["Department / Wing", "Subordinate Represented?"]
                            st.dataframe(adf, hide_index=True)
                        else: st.info("Attendance not marked.")
                    else:
                        detailed_attendance_payload = []
                        with st.container():
                            for uid in invited_uids:
                                label = unified_uid_to_label.get(uid, "Unknown")
                                ca1, ca2 = st.columns([2, 1])
                                is_present = ca1.checkbox(f"✅ {label}", value=True, key=f"pres_{uid}_{proc_sel}")
                                is_sub = ca2.checkbox("Subordinate Attended?", key=f"sub_{uid}_{proc_sel}") if is_present else False
                                if is_present:
                                    detailed_attendance_payload.append({"uid": uid, "label": label, "attended_by_subordinate": is_sub})
                                    
                            if st.button("Save Attendance Register", type="primary"):
                                supabase.table("meetings").update({"detailed_attendance": detailed_attendance_payload}).eq("id", proc_sel).execute()
                                st.success("✅ Attendance saved.")
                                st.rerun()

            # TARGET PROGRESS REVIEW
            with st.expander("📊 B. Real-Time Target vs. Actual Progress Review", expanded=False):
                q_targets = supabase.table("department_targets").select("*").eq("district_id", proc_mtg["district_id"])
                try: q_targets = q_targets.eq("financial_year", active_fy)
                except: pass

                q_reg = supabase.table("convergence_register").select("department_id, activity_description, current_status").eq("district_id", proc_mtg["district_id"])
                if proc_mtg["meeting_type"] == "Block": q_reg = q_reg.eq("block_id", proc_mtg["block_id"])
                t_data = q_targets.execute().data
                r_data = q_reg.execute().data

                if t_data:
                    df_t, df_r = pd.DataFrame(t_data), pd.DataFrame(r_data) if r_data else pd.DataFrame()
                    comp_data = []
                    for idx, row in df_t.iterrows():
                        d_id, act = row['department_id'], row['activity']
                        t_val = safe_int(row.get('desired_target', 0))
                        
                        e_count = 0
                        if not df_r.empty:
                            dept_r = df_r[df_r['department_id'] == d_id]
                            if 'activity_description' in dept_r.columns and not dept_r.empty:
                                mask = dept_r['activity_description'].apply(lambda x: str(act).lower() in str(x).lower() if pd.notna(x) else False)
                                e_count = safe_int(mask.sum())

                        ach_pct = (e_count / t_val * 100) if t_val > 0 else 0
                        gap = t_val - e_count
                        stat = "Achieved" if gap <= 0 else "Review" if ach_pct > 50 else "Critical Delay"
                        comp_data.append({"Department": dept_map.get(d_id, "Unknown"), "Activity": act, "Target": t_val, "Achievement": e_count, "% Achieved": f"{ach_pct:.1f}%", "Status": stat})
                    st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

            # MINUTES & ASSIGN NEW ACTION POINTS
            with st.expander("📝 C. Minutes & Resolution Directives", expanded=not is_locked):
                general_minutes = st.text_area("Meeting Minutes / Deliberations", value=proc_mtg.get("decisions", "") or "", disabled=is_locked or role=="department")
                if not is_locked and role != "department":
                    if st.button("Save Draft Minutes", key=f"btn_mins_{proc_sel}"):
                        supabase.table("meetings").update({"decisions": general_minutes}).eq("id", proc_sel).execute()
                        st.success("Draft minutes committed.")

                    st.markdown("##### Assign Action Point / Directives")
                    with st.container(border=True):
                        c_r1, c_r2 = st.columns(2)
                        res_dept_label = c_r1.selectbox("Assign Responsibility to*", dept_labels, key=f"r_dept_{proc_sel}")
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

                        if st.button("Commit Action Point", type="primary", key=f"btn_add_{proc_sel}"):
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
                                    st.success("✅ Directive recorded!")
                                    st.rerun()
                                except Exception:
                                    res_payload["status"], res_payload["priority"] = res_status.lower().replace(" ", "_"), res_priority.lower()
                                    supabase.table("meeting_action_points").insert(res_payload).execute()
                                    st.success("✅ Directive recorded!")
                                    st.rerun()

            # PROCEEDINGS LOCK (Preserved)
            if not is_locked and role in ["superadmin", "district", "block"]:
                st.markdown("---")
                if st.button("🔒 Complete Proceedings & Lock Meeting Register", type="primary", use_container_width=True, key=f"btn_lock_{proc_sel}"):
                    supabase.table("meetings").update({"status": "Convened", "decisions": general_minutes}).eq("id", proc_sel).execute()
                    st.success("Meeting proceedings locked! Record is now legally convened and read-only.")
                    st.rerun()

    # =====================================================================
    # TAB 4: ADVANCED ACTION TRACKER & ATR
    # =====================================================================
    with tab4:
        st.markdown("#### 🎯 Resolution Tracker & Action Taken Reports (ATR)")
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

            st.markdown("##### ✏️ Submit ATR Update")
            with st.form("global_update_atr"):
                c_u1, c_u2 = st.columns(2)
                ap_id = c_u1.selectbox("Select Resolution", filtered_df["id"].tolist())
                new_ap_status = c_u2.selectbox("Update Status", ["Not Started", "On Track", "Completed", "Not Feasible (Requires Review)", "Dropped"])
                atr_remarks = st.text_area("ATR Findings / Justification (Required if Not Feasible)")

                if st.form_submit_button("Submit ATR Update", type="primary"):
                    if new_ap_status == "Not Feasible (Requires Review)" and not atr_remarks.strip():
                        st.error("⚠️ Mandatory Justification: State why this item is Not Feasible for Chairperson review.")
                    else:
                        try: supabase.table("meeting_action_points").update({"status": new_ap_status, "remarks": atr_remarks}).eq("id", ap_id).execute()
                        except: supabase.table("meeting_action_points").update({"status": new_ap_status.lower().replace(" ", "_"), "remarks": atr_remarks}).eq("id", ap_id).execute()
                        st.success("✅ ATR submitted successfully.")
                        st.rerun()

    # =====================================================================
    # TAB 5: MASTER EXPORT
    # =====================================================================
    with tab5:
        st.markdown("#### 🖨️ Export Resolution Register")
        if not df_ap.empty:
            st.download_button("📥 Download Master Tracker (Excel/CSV)", data=df_ap.to_csv(index=False).encode('utf-8'), file_name="meeting_resolutions_tracker.csv", mime="text/csv")
        else:
            st.info("No records available to export.")

    # =====================================================================
    # TAB 6: AUTOMATED NEXT AGENDA PREP
    # =====================================================================
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
