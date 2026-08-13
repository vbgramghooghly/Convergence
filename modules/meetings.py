from datetime import date, datetime, timedelta
import base64
import json
import io
from auth.auth import require_role, get_current_user
import pandas as pd
import streamlit as st
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
  require_role("superadmin", "district", "block")

  # Apply custom UI styling to hide top-right toolbar elements
  inject_custom_css()

  st.markdown(
      "<h1 style='color: #1F77B4;'>📋 Convergence Meeting & Resolution"
      " Tracker</h1>",
      unsafe_allow_html=True,
  )
  st.markdown("---")

  supabase = get_supabase()
  user = get_current_user()

  # ======================== 1. MASTER DATA FETCH ========================
  departments = (
      supabase.table("departments")
      .select("id, department_name")
      .execute()
      .data
  )
  dept_dict = {d["department_name"]: d["id"] for d in departments}
  dept_map_reverse = {d["id"]: d["department_name"] for d in departments}

  blocks_data = (
      supabase.table("blocks")
      .select("id, block_name, district_id")
      .execute()
      .data
  )
  block_dict_reverse = {b["id"]: b["block_name"] for b in blocks_data}

  # Fetch contacts dynamically pulling all fields
  contacts_data = (
      supabase.table("contacts")
      .select("*, designations(designation_name)")
      .execute()
      .data
  )
  contact_map = {}

  for c in contacts_data:
    desig = c.get("designations", {})
    desig_name = (
        desig.get("designation_name", "No Designation")
        if isinstance(desig, dict)
        else "No Designation"
    )

    t_blocks = c.get("tagged_blocks")
    if not t_blocks:
      t_blocks = []
    elif isinstance(t_blocks, str):
      try:
        t_blocks = json.loads(t_blocks)
      except:
        t_blocks = [t_blocks]

    contact_map[c["id"]] = {
        "name": c.get("full_name", "Unknown"),
        "designation": desig_name,
        "designation_id": c.get("designation_id"),
        "phone": c.get("contact_number", "N/A"),
        "email": c.get("email_id", "N/A"),
        "district_id": c.get("district_id"),
        "block_id": c.get("block_id"),
        "tagged_blocks": [str(x) for x in t_blocks],
        "district_committee_role": str(
            c.get("district_committee_role", "")
        ),
        "block_committee_role": str(c.get("block_committee_role", "")),
    }

  # Global Meeting Fetch for the Jurisdiction
  query = supabase.table("meetings").select("*")
  if user["role"] == "district":
    query = (
        query.eq("district_id", user["district_id"])
        .eq("meeting_type", "District")
    )
  elif user["role"] == "block":
    query = query.eq("block_id", user["block_id"]).eq("meeting_type", "Block")

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
      disp_df = df_meetings[
          ["meeting_date", "meeting_type", "venue", "chairperson"]
      ].copy()
      disp_df["status"] = (
          df_meetings.get("status", "Convened").fillna("Convened")
      )

      st.dataframe(disp_df, use_container_width=True, hide_index=True)

      st.markdown("### 🔍 View Detailed Proceedings & Attendance")
      detail_sel = st.selectbox(
          "Select Meeting Date to view details",
          df_meetings["id"].tolist(),
          format_func=lambda x: (
              f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]}"
              f" | {df_meetings[df_meetings['id'] == x]['meeting_type'].values[0]}"
              " Level"
          ),
      )

      sel_meeting_data = df_meetings[df_meetings["id"] == detail_sel].iloc[0]

      with st.container(border=True):
        st.markdown(
            f"<h3 style='color: #2B8A3E;'>Meeting Details:"
            f" {sel_meeting_data['meeting_date']}</h3>",
            unsafe_allow_html=True,
        )
        col_d1, col_d2 = st.columns(2)
        col_d1.write(
            f"**Chairperson:** {sel_meeting_data.get('chairperson', 'None')}"
        )
        col_d1.write(
            f"**Level:** {sel_meeting_data.get('meeting_type', 'None')}"
        )
        col_d2.write(f"**Venue:** {sel_meeting_data.get('venue', 'None')}")
        col_d2.write(
            f"**Financial Year:**"
            f" {sel_meeting_data.get('financial_year', 'None')}"
        )

        st.write(f"**Objective:** {sel_meeting_data.get('objective', 'None')}")
        st.write(
            f"**General Decisions:**"
            f" {sel_meeting_data.get('decisions', 'None')}"
        )

        st.markdown("#### 👥 Detailed Attendance Register")
        att_data = sel_meeting_data.get("detailed_attendance")
        if att_data and isinstance(att_data, list) and len(att_data) > 0:
          att_df = pd.DataFrame(att_data)
          disp_att_df = att_df[[
              "official_name",
              "official_designation",
              "official_phone",
              "official_email",
              "attended_by_subordinate",
              "subordinate_name",
              "subordinate_designation",
              "subordinate_phone",
          ]]
          disp_att_df.columns = [
              "Official Name",
              "Official Designation",
              "Official Phone",
              "Official Email",
              "Subordinate Attended?",
              "Subordinate Name",
              "Subordinate Designation",
              "Subordinate Phone",
          ]

          def highlight_subs(row):
            return (
                ["background-color: #FFF3CD"] * len(row)
                if row["Subordinate Attended?"]
                else [""] * len(row)
            )

          st.dataframe(
              disp_att_df.style.apply(highlight_subs, axis=1),
              use_container_width=True,
              hide_index=True,
          )
        else:
          st.info(
              "No detailed attendance captured for this meeting yet. Please"
              " record proceedings in Tab 3."
          )

        if user["role"] in ["superadmin", "district", "block"]:
          st.markdown("---")
          with st.expander("✏️ Edit Past Meeting Data & Attendance"):
            st.markdown("### Update Meeting Record")

            curr_fy = (
                sel_meeting_data.get("financial_year", "2026-27") or "2026-27"
            )
            fy_options = ["2026-27", "2027-28", "2028-29"]
            fy_idx = (
                fy_options.index(curr_fy) if curr_fy in fy_options else 0
            )

            e_fy = st.selectbox(
                "Financial Year",
                fy_options,
                index=fy_idx,
                key=f"e_fy_{detail_sel}",
            )

            col_e1, col_e2 = st.columns(2)
            e_chair = col_e1.text_input(
                "Chairperson",
                value=sel_meeting_data.get("chairperson", "") or "",
                key=f"e_ch_{detail_sel}",
            )
            e_venue = col_e2.text_input(
                "Venue",
                value=sel_meeting_data.get("venue", "") or "",
                key=f"e_ve_{detail_sel}",
            )

            e_obj = st.text_input(
                "Objective",
                value=sel_meeting_data.get("objective", "") or "",
                key=f"e_ob_{detail_sel}",
            )
            e_dec = st.text_area(
                "Decisions",
                value=sel_meeting_data.get("decisions", "") or "",
                key=f"e_de_{detail_sel}",
            )

            st.markdown("#### 👥 Update Attendance")
            curr_att = sel_meeting_data.get("attendees") or []
            if not isinstance(curr_att, list):
              curr_att = []
            valid_curr_att = [cid for cid in curr_att if cid in contact_map]

            e_attendees = st.multiselect(
                "Select Invited Officials",
                options=list(contact_map.keys()),
                default=valid_curr_att,
                format_func=lambda x: (
                    f"{contact_map[x]['name']} ({contact_map[x]['designation']})"
                ),
                key=f"e_ms_{detail_sel}",
            )

            existing_det_att = sel_meeting_data.get("detailed_attendance") or []
            if not isinstance(existing_det_att, list):
              existing_det_att = []
            existing_subs = {
                item.get("contact_id"): item
                for item in existing_det_att
                if isinstance(item, dict)
            }

            e_detailed_attendance_payload = []
            if e_attendees:
              st.markdown("##### Verify Attendance & Representatives")
              for cid in e_attendees:
                contact = contact_map[cid]
                prev_data = existing_subs.get(cid, {})
                prev_is_sub = prev_data.get("attended_by_subordinate", False)

                with st.container(border=True):
                  st.markdown(
                      f"**{contact['name']}** | {contact['designation']} |"
                      f" {contact['phone']} | {contact['email']}"
                  )
                  is_sub = st.checkbox(
                      "Attended by Subordinate/Representative?",
                      value=prev_is_sub,
                      key=f"e_chk_{cid}_{detail_sel}",
                  )

                  sub_name, sub_desig, sub_phone = (
                      prev_data.get("subordinate_name", ""),
                      prev_data.get("subordinate_designation", ""),
                      prev_data.get("subordinate_phone", ""),
                  )

                  if is_sub:
                    sc1, sc2, sc3 = st.columns(3)
                    sub_name = sc1.text_input(
                        "Subordinate Name",
                        value=sub_name or "",
                        key=f"e_sn_{cid}_{detail_sel}",
                    )
                    sub_desig = sc2.text_input(
                        "Subordinate Designation",
                        value=sub_desig or "",
                        key=f"e_sd_{cid}_{detail_sel}",
                    )
                    sub_phone = sc3.text_input(
                        "Subordinate Phone",
                        value=sub_phone or "",
                        key=f"e_sp_{cid}_{detail_sel}",
                    )

                  e_detailed_attendance_payload.append({
                      "contact_id": cid,
                      "official_name": contact["name"],
                      "official_designation": contact["designation"],
                      "official_phone": contact["phone"],
                      "official_email": contact["email"],
                      "attended_by_subordinate": is_sub,
                      "subordinate_name": sub_name if is_sub else None,
                      "subordinate_designation": sub_desig if is_sub else None,
                      "subordinate_phone": sub_phone if is_sub else None,
                  })

            if st.button(
                "💾 Save Updates to Meeting",
                type="primary",
                key=f"btn_save_{detail_sel}",
            ):
              update_payload = {
                  "financial_year": e_fy,
                  "chairperson": e_chair,
                  "venue": e_venue,
                  "objective": e_obj,
                  "decisions": e_dec,
                  "attendees": e_attendees,
                  "detailed_attendance": e_detailed_attendance_payload,
              }
              try:
                (
                    supabase.table("meetings")
                    .update(update_payload)
                    .eq("id", detail_sel)
                    .execute()
                )
                log_action(user.get("id"), f"UPDATE meeting {detail_sel}")
                st.success("✅ Meeting updated successfully!")
                st.rerun()
              except Exception as e:
                st.error(f"Error updating meeting: {e}")
    else:
      st.info("No meetings found for your assigned jurisdiction.")

  # ======================== TAB 2: SCHEDULE MEETING ========================
  with tab2:
    st.subheader("Step 1: Schedule New Convergence Meeting")
    st.caption(
        "Plan the meeting details and select invitees. Proceedings will be"
        " recorded after convening."
    )

    col_m1, col_m2, col_m3 = st.columns(3)
    if user["role"] in ["superadmin", "district"]:
      meeting_type = col_m1.radio(
          "Meeting Level", ["District", "Block"], horizontal=True
      )
    else:
      meeting_type = "Block"
      col_m1.info("Meeting Level: Block")

    financial_year = col_m2.selectbox(
        "Financial Year", ["2026-27", "2027-28", "2028-29"]
    )
    meeting_date = col_m3.date_input("Meeting Date", date.today())

    if meeting_type == "District":
      districts = (
          supabase.table("districts")
          .select("id,district_name")
          .eq("active", True)
          .execute()
          .data
      )
      dist_dict = {d["district_name"]: d["id"] for d in districts}
      dist_sel = next(
          (
              name
              for name, id in dist_dict.items()
              if id == user.get("district_id")
          ),
          list(dist_dict.keys())[0],
      )
      if user["role"] != "district":
        dist_sel = st.selectbox("District", list(dist_dict.keys()))
      block_sel = None
    else:
      if user["role"] == "block":
        block_sel = block_dict_reverse.get(user["block_id"], "Unknown Block")
        st.text(f"Jurisdiction: {block_sel}")
        dist_sel = next(
            b["district_id"] for b in blocks_data if b["id"] == user["block_id"]
        )
      else:
        block_sel = st.selectbox(
            "Block Jurisdiction", [b["block_name"] for b in blocks_data]
        )
        dist_sel = next(
            b["district_id"]
            for b in blocks_data
            if b["block_name"] == block_sel
        )

    if meeting_type == "District":
      st.info("""
            **🏛️ Statutory District-Level Convergence Committee**
            * **Chairperson:** District Magistrate & District Programme Coordinator (DPC)
            * **Member-Convener:** Nodal Officer (DNO), VB-G RAM G
            * **Members:** Statutory district heads and engineers.
            """)
      chair_default = (
          "District Magistrate & District Programme Coordinator (DPC)"
      )
    else:
      st.info("""
            **🏛️ Statutory Block-Level Convergence Committee**
            * **Chairperson:** Block Development Officer (BDO)
            * **Member-Convener:** Joint Block Development Officer (Jt. BDO)
            * **Members:** Block level statutory officers.
            """)
      chair_default = "Block Development Officer (BDO)"

    with st.form("schedule_meeting_form"):
      col_a1, col_a2 = st.columns(2)
      chairperson = col_a1.text_input(
          "Chairperson (Name & Designation)", value=chair_default
      )
      venue = col_a2.text_input("Venue / Platform")
      objective = st.text_input("Meeting Objective / Schematic Discussion")

      st.markdown("---")
      st.markdown("### 📋 Select Attendees")

      statutory_desigs = (
          supabase.table("designations")
          .select("id")
          .eq("is_committee_member", True)
          .eq("committee_level", meeting_type)
          .execute()
          .data
      )
      statutory_desig_ids = [d["id"] for d in statutory_desigs]

      target_dist_id = (
          str(dist_dict.get(dist_sel))
          if meeting_type == "District"
          else str(
              next(b for b in blocks_data if b["block_name"] == block_sel)[
                  "district_id"
              ]
          )
      )
      target_block_id = (
          None
          if meeting_type == "District"
          else str(
              next(b for b in blocks_data if b["block_name"] == block_sel)[
                  "id"
              ]
          )
      )

      statutory_officials, other_officials = {}, {}

      for cid, info in contact_map.items():
        is_statutory = False
        belongs_to_jurisdiction = False

        c_dist_id = str(info.get("district_id"))
        c_block_id = str(info.get("block_id"))
        tagged_blocks = info.get("tagged_blocks", [])

        has_explicit_dist_role = (
            info["district_committee_role"]
            and info["district_committee_role"].lower()
            not in ["none", "", "null"]
        )
        has_explicit_blk_role = (
            info["block_committee_role"]
            and info["block_committee_role"].lower() not in ["none", "", "null"]
        )

        if meeting_type == "District":
          if c_dist_id == target_dist_id:
            belongs_to_jurisdiction = True
            legacy_statutory = (info.get("block_id") is None) and (
                info.get("designation_id") in statutory_desig_ids
            )
            if legacy_statutory or has_explicit_dist_role:
              is_statutory = True
        elif meeting_type == "Block":
          if c_block_id == target_block_id or (
              target_block_id in tagged_blocks
          ):
            belongs_to_jurisdiction = True
            legacy_statutory = info.get("designation_id") in statutory_desig_ids
            if legacy_statutory or has_explicit_blk_role:
              is_statutory = True

        if is_statutory:
          statutory_officials[cid] = info
        elif belongs_to_jurisdiction or (c_dist_id == target_dist_id):
          other_officials[cid] = info

      selected_contact_ids = []

      if statutory_officials:
        cols = st.columns(2)
        idx = 0
        for cid, info in statutory_officials.items():
          if cols[idx % 2].checkbox(
              f"{info['name']} - {info['designation']}", key=f"stat_{cid}"
          ):
            selected_contact_ids.append(cid)
          idx += 1
      else:
        st.warning(
            "No statutory members found in the directory for this jurisdiction."
        )

      st.markdown("#### Other Invitees / Special Guests")
      other_selections = st.multiselect(
          "Select additional officials:",
          options=list(other_officials.keys()),
          format_func=lambda x: (
              f"{other_officials[x]['name']}"
              f" ({other_officials[x]['designation']})"
          ),
      )

      final_attendees = selected_contact_ids + other_selections

      if st.form_submit_button("Schedule Meeting", type="primary"):
        meeting_data = {
            "meeting_type": meeting_type,
            "financial_year": financial_year,
            "meeting_date": str(meeting_date),
            "chairperson": chairperson,
            "venue": venue,
            "objective": objective,
            "attendees": final_attendees,
            "status": "Scheduled",
            "created_by": user["id"],
        }
        if meeting_type == "District":
          meeting_data["district_id"] = (
              dist_dict[dist_sel]
              if user["role"] != "district"
              else user["district_id"]
          )
        else:
          block_obj = next(
              b for b in blocks_data if b["block_name"] == block_sel
          )
          meeting_data["block_id"] = block_obj["id"]
          meeting_data["district_id"] = block_obj["district_id"]

        result = supabase.table("meetings").insert(meeting_data).execute()
        if result.data:
          st.success(
              "✅ Meeting Scheduled successfully! Proceed to Tab 3 after"
              " convening."
          )
          log_action(user.get("id"), f"CREATE meeting {result.data[0]['id']}")
          st.rerun()

  # ======================== TAB 3: RECORD PROCEEDINGS ========================
  with tab3:
    st.subheader("Step 2: Record Meeting Proceedings")
    st.caption(
        "Mark actual attendance, review past progress, add minutes, and assign"
        " new resolutions."
    )

    if df_meetings.empty:
      st.info("No meetings available to record.")
    else:
      if "status" not in df_meetings.columns:
        df_meetings["status"] = "Convened"

      sched_meetings = df_meetings[df_meetings["status"] == "Scheduled"]

      if sched_meetings.empty:
        st.info(
            "No active 'Scheduled' meetings. Showing all meetings for"
            " retroactive recording."
        )
        proc_sel = st.selectbox(
            "Select Meeting to Record",
            df_meetings["id"].tolist(),
            format_func=lambda x: (
                f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]}"
                f" | {df_meetings[df_meetings['id'] == x]['objective'].values[0]}"
                f" ({df_meetings[df_meetings['id'] == x]['status'].values[0]})"
            ),
        )
      else:
        proc_sel = st.selectbox(
            "Select Scheduled Meeting to Convene",
            sched_meetings["id"].tolist(),
            format_func=lambda x: (
                f"{sched_meetings[sched_meetings['id'] == x]['meeting_date'].values[0]}"
                f" | {sched_meetings[sched_meetings['id'] == x]['objective'].values[0]}"
            ),
        )

      proc_meeting_data = df_meetings[df_meetings["id"] == proc_sel].iloc[0]

      # --- A. MARK ACTUAL ATTENDANCE ---
      with st.expander("👥 A. Mark Actual Attendance", expanded=True):
        curr_att = proc_meeting_data.get("attendees") or []
        if not isinstance(curr_att, list):
          curr_att = []

        with st.form("actual_attendance_form"):
          actual_attendees = st.multiselect(
              "Confirm Attending Officials",
              options=list(contact_map.keys()),
              default=curr_att,
              format_func=lambda x: (
                  f"{contact_map[x]['name']} ({contact_map[x]['designation']})"
              ),
          )

          st.markdown("##### Subordinate Representation Check")
          detailed_attendance_payload = []

          if actual_attendees:
            for cid in actual_attendees:
              contact = contact_map[cid]
              is_sub = st.checkbox(
                  f"Did a subordinate attend instead of {contact['name']}?",
                  key=f"sub_{cid}_{proc_sel}",
              )
              sub_name, sub_desig, sub_phone = "", "", ""
              if is_sub:
                sc1, sc2, sc3 = st.columns(3)
                sub_name = st.text_input(
                    "Subordinate Name", key=f"s_n_{cid}_{proc_sel}"
                )
                sub_desig = st.text_input(
                    "Subordinate Designation", key=f"s_d_{cid}_{proc_sel}"
                )
                sub_phone = st.text_input(
                    "Subordinate Phone", key=f"s_p_{cid}_{proc_sel}"
                )

              detailed_attendance_payload.append({
                  "contact_id": cid,
                  "official_name": contact["name"],
                  "official_designation": contact["designation"],
                  "official_phone": contact["phone"],
                  "official_email": contact["email"],
                  "attended_by_subordinate": is_sub,
                  "subordinate_name": sub_name if is_sub else None,
                  "subordinate_designation": sub_desig if is_sub else None,
                  "subordinate_phone": sub_phone if is_sub else None,
              })

          if st.form_submit_button("Save Attendance Register"):
            (
                supabase.table("meetings")
                .update({
                    "detailed_attendance": detailed_attendance_payload,
                    "attendees": actual_attendees,
                })
                .eq("id", proc_sel)
                .execute()
            )
            st.success("✅ Attendance saved.")
            st.rerun()

      # --- B. REVIEW PREVIOUS DECISIONS ---
      with st.expander("⏳ B. Review Past Decisions & Progress", expanded=False):
        past_ap_query = (
            supabase.table("meeting_action_points")
            .select("*, meetings!inner(district_id, block_id, meeting_type)")
            .neq("status", "Completed")
            .neq("status", "Dropped")
            .execute()
            .data
        )
        if past_ap_query:
          df_past = pd.DataFrame(past_ap_query)
          if proc_meeting_data["meeting_type"] == "District":
            df_past = df_past[
                df_past["meetings"].apply(
                    lambda x: x.get("district_id")
                    == proc_meeting_data["district_id"]
                )
            ]
          else:
            df_past = df_past[
                df_past["meetings"].apply(
                    lambda x: x.get("block_id")
                    == proc_meeting_data["block_id"]
                )
            ]

          if not df_past.empty:
            df_past["Department"] = df_past["department_id"].map(
                dept_map_reverse
            )
            st.dataframe(
                df_past[[
                    "Department",
                    "action_point",
                    "responsible_officer",
                    "status",
                    "remarks",
                ]],
                use_container_width=True,
                hide_index=True,
            )

            with st.form("quick_update_form"):
              col_u1, col_u2 = st.columns(2)
              u_id = col_u1.selectbox(
                  "Select Resolution",
                  df_past["id"].tolist(),
                  format_func=lambda x: (
                      f"{df_past[df_past['id'] == x]['action_point'].values[0][:40]}..."
                  ),
              )
              u_stat = col_u2.selectbox(
                  "Update Status",
                  [
                      "Under Process",
                      "Approved",
                      "Under Execution",
                      "Completed",
                      "Not Feasible (Requires Review)",
                      "Dropped",
                  ],
              )
              u_rem = st.text_input("Latest Progress / Remarks")
              if st.form_submit_button("Update Past Progress"):
                (
                    supabase.table("meeting_action_points")
                    .update({"status": u_stat, "remarks": u_rem})
                    .eq("id", u_id)
                    .execute()
                )
                st.success("Updated successfully.")
                st.rerun()
          else:
            st.info("No pending resolutions for this jurisdiction.")
        else:
          st.info("No past action points found.")

      # --- C. GENERAL MINUTES & NEW RESOLUTIONS ---
      with st.expander("📝 C. General Minutes & New Resolutions", expanded=True):
        general_minutes = st.text_area(
            "General Discussion / Meeting Minutes",
            value=proc_meeting_data.get("decisions", "") or "",
            height=100,
        )
        if st.button("Save General Minutes"):
          (
              supabase.table("meetings")
              .update({"decisions": general_minutes})
              .eq("id", proc_sel)
              .execute()
          )
          st.success("Minutes saved.")

        st.markdown("---")
        st.markdown("#### Assign New Resolutions")

        current_att_data = proc_meeting_data.get("detailed_attendance", [])

        # Validation barrier: Must complete attendance first
        if not current_att_data:
          st.warning(
              "⚠️ Please mark and save actual attendance in Step A before"
              " assigning resolutions."
          )
        else:
          att_options = []
          for att in current_att_data:
            if att.get("attended_by_subordinate"):
              name_str = (
                  f"{att.get('subordinate_name', 'Subordinate')} (Rep. for"
                  f" {att.get('official_name')})"
              )
            else:
              name_str = (
                  f"{att.get('official_name')}"
                  f" ({att.get('official_designation')})"
              )
            att_options.append(name_str)

          with st.form("add_new_resolution"):
            col_r1, col_r2 = st.columns([1, 1])
            res_dept = col_r1.selectbox(
                "Converging Department", list(dept_dict.keys())
            )
            res_officer = col_r2.selectbox(
                "Responsible Attending Officer", att_options
            )

            res_action = st.text_area("Resolution / Action Point")

            col_r3, col_r4, col_r5 = st.columns([1, 1, 1])
            res_target = col_r3.text_input("Desired Target (Optional)")
            has_deadline = col_r4.checkbox("Set Target Date?", value=True)
            res_deadline = col_r5.date_input("Target Date", date.today())

            if st.form_submit_button(
                "Add Resolution to Tracker", type="primary"
            ):
              # Robust Try-Catch to handle Postgres Check Constraint
              res_payload = {
                  "meeting_id": proc_sel,
                  "department_id": dept_dict[res_dept],
                  "action_point": res_action,
                  "target": res_target if res_target.strip() else None,
                  "responsible_officer": res_officer,
                  "deadline": str(res_deadline) if has_deadline else None,
                  "status": "Under Process",
                  "priority": "Medium",
              }
              try:
                (
                    supabase.table("meeting_action_points")
                    .insert(res_payload)
                    .execute()
                )
                st.success("✅ Resolution added successfully!")
                st.rerun()
              except Exception as e:
                # Fallback if constraint requires lowercase strings
                try:
                  res_payload["status"] = "under_process"
                  res_payload["priority"] = "medium"
                  (
                      supabase.table("meeting_action_points")
                      .insert(res_payload)
                      .execute()
                  )
                  st.success("✅ Resolution added successfully!")
                  st.rerun()
                except Exception as err2:
                  st.error(
                      f"Database Check Constraint Error: {err2}. Please"
                      " contact Superadmin to verify allowed Database status"
                      " strings."
                  )

      # --- D. FINALIZE MEETING ---
      st.markdown("---")
      if proc_meeting_data.get("status") == "Scheduled":
        if st.button(
            "🔒 Complete Proceedings & Mark as Convened",
            type="primary",
            use_container_width=True,
        ):
          (
              supabase.table("meetings")
              .update({"status": "Convened"})
              .eq("id", proc_sel)
              .execute()
          )
          st.success(
              "Meeting locked and Convened! Resolutions synced to Department"
              " Dashboards."
          )
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
          format_func=lambda x: (
              "All Meetings"
              if x == "All"
              else (
                  f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]}"
                  f" | {df_meetings[df_meetings['id'] == x]['objective'].values[0]}"
              )
          ),
      )

      ap_query = supabase.table("meeting_action_points").select("*")
      if tr_meeting_sel != "All":
        ap_query = ap_query.eq("meeting_id", tr_meeting_sel)

      ap_data = ap_query.execute().data

      if ap_data:
        df_ap = pd.DataFrame(ap_data)
        df_ap["Department"] = df_ap["department_id"].map(dept_map_reverse)

        today = pd.to_datetime(date.today())
        df_ap["deadline"] = pd.to_datetime(df_ap["deadline"], errors="coerce")

        def get_flag(row):
          stat = str(row.get("status", "")).lower()
          if stat in ["completed", "dropped"]:
            return "✅ Closed"
          if "feasible" in stat or "review" in stat:
            return "🔴 FOR REVIEW"
          if pd.isna(row["deadline"]):
            return "⏳ No Deadline"
          days_rem = (row["deadline"] - today).days
          if days_rem < 0:
            return "🚨 OVERDUE"
          if days_rem == 0:
            return "⚠️ Due Today"
          return "⏳ On Track"

        df_ap["Tracker Flag"] = df_ap.apply(get_flag, axis=1)

        display_cols = [
            "id",
            "Department",
            "action_point",
            "target",
            "deadline",
            "Tracker Flag",
            "status",
        ]
        if "responsible_officer" in df_ap.columns:
          display_cols.insert(3, "responsible_officer")

        st.dataframe(
            df_ap[display_cols].sort_values("Tracker Flag"),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### ✏️ Update Progress / Action Taken Report")
        with st.form("global_update_atr"):
          col_u1, col_u2 = st.columns(2)
          ap_id = col_u1.selectbox("Select Resolution ID", df_ap["id"].tolist())

          new_ap_status = col_u2.selectbox(
              "Update Status",
              [
                  "Under Process",
                  "Approved",
                  "Under Execution",
                  "Completed",
                  "Not Feasible (Requires Review)",
                  "Dropped",
              ],
          )
          remarks = st.text_area("Outcome / Action Taken")

          if st.form_submit_button("Update Progress"):
            update_payload = {"status": new_ap_status, "remarks": remarks}
            try:
              (
                  supabase.table("meeting_action_points")
                  .update(update_payload)
                  .eq("id", ap_id)
                  .execute()
              )
              log_action(user.get("id"), f"UPDATE resolution {ap_id}")
              st.success("✅ Progress updated successfully.")
              st.rerun()
            except Exception as e:
              # Fallback casing for postgres updates
              try:
                update_payload["status"] = (
                    new_ap_status.lower().replace(" ", "_")
                )
                (
                    supabase.table("meeting_action_points")
                    .update(update_payload)
                    .eq("id", ap_id)
                    .execute()
                )
                st.success("✅ Progress updated successfully.")
                st.rerun()
              except Exception as e2:
                st.error(f"Error updating status: {e2}")
      else:
        st.info("No resolutions adopted yet.")

      # CROSS-REFERENCE (Block Outcomes for District)
      if user["role"] in ["superadmin", "district"]:
        st.markdown("---")
        st.markdown("### 🔗 Reference Block-Level Outcomes")

        ref_dept_name = st.selectbox(
            "Select Department to review Block Outcomes",
            list(dept_dict.keys()),
            key="ref_dept_sel",
        )
        ref_dept_id = dept_dict[ref_dept_name]

        bm_query = (
            supabase.table("meetings")
            .select("id, meeting_date, block_id")
            .eq("meeting_type", "Block")
        )
        if user["role"] == "district":
          bm_query = bm_query.eq("district_id", user.get("district_id"))

        block_meetings = bm_query.execute().data
        if block_meetings:
          bm_ids = [m["id"] for m in block_meetings]
          bm_map = {m["id"]: m for m in block_meetings}

          bap_query = (
              supabase.table("meeting_action_points")
              .select("*")
              .eq("department_id", ref_dept_id)
              .in_("meeting_id", bm_ids)
              .execute()
              .data
          )

          if bap_query:
            df_bap = pd.DataFrame(bap_query)
            df_bap["Block"] = df_bap["meeting_id"].map(
                lambda x: block_dict_reverse.get(
                    bm_map.get(x, {}).get("block_id"), "Unknown"
                )
            )
            df_bap["Meeting Date"] = df_bap["meeting_id"].map(
                lambda x: bm_map.get(x, {}).get("meeting_date")
            )

            disp_cols = [
                "Block",
                "Meeting Date",
                "action_point",
                "target",
                "status",
                "remarks",
            ]
            st.dataframe(
                df_bap[disp_cols].sort_values("Meeting Date", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
          else:
            st.info(
                f"No block-level resolutions recorded for {ref_dept_name} yet."
            )
        else:
          st.info("No Block meetings recorded in this district yet.")

  # ======================== TAB 5: PRINT & REPORTS ========================
  with tab5:
    st.subheader("🖨️ Meeting & Resolution Reports")
    report_type = st.radio(
        "Select Report Type",
        [
            "By Specific Meeting (Chairperson Report)",
            "Date-Wise Resolution Register",
        ],
        horizontal=True,
    )
    st.markdown("---")

    if report_type == "By Specific Meeting (Chairperson Report)":
      if not df_meetings.empty:
        rep_mtg_sel = st.selectbox(
            "Select Meeting for Report",
            df_meetings["id"].tolist(),
            format_func=lambda x: (
                f"{df_meetings[df_meetings['id'] == x]['meeting_date'].values[0]}"
                f" | {df_meetings[df_meetings['id'] == x]['objective'].values[0]}"
            ),
        )
        sel_meeting_data = df_meetings[df_meetings["id"] == rep_mtg_sel].iloc[0]

        att_data = sel_meeting_data.get("detailed_attendance")
        attendance_html = ""
        if att_data and isinstance(att_data, list):
          attendance_html += (
              "<table class='print-table'><tr><th>Official"
              " Name</th><th>Designation</th><th>Attended"
              " By</th><th>Contact</th></tr>"
          )
          for att in att_data:
            off_name = att.get("official_name", "")
            off_desig = att.get("official_designation", "")
            if att.get("attended_by_subordinate"):
              att_by = (
                  f"<b>Subordinate:</b>"
                  f" {att.get('subordinate_name', '')}<br><i>({att.get('subordinate_designation', '')})</i>"
              )
              contact_info = att.get("subordinate_phone", "")
              row_style = "background-color: #fff3cd;"
            else:
              att_by = "Self"
              contact_info = att.get("official_phone", "")
              row_style = ""
            attendance_html += (
                f"<tr style='{row_style}'><td>{off_name}</td><td>{off_desig}</td><td>{att_by}</td><td>{contact_info}</td></tr>"
            )
          attendance_html += "</table>"
        else:
          attendance_html = "<p>No detailed attendance recorded.</p>"

        mtg_ap = (
            supabase.table("meeting_action_points")
            .select("*")
            .eq("meeting_id", rep_mtg_sel)
            .execute()
            .data
        )
        if mtg_ap:
          df_rep_ap = pd.DataFrame(mtg_ap)
          df_rep_ap["Department"] = df_rep_ap["department_id"].map(
              dept_map_reverse
          )
          print_df = df_rep_ap[
              ["Department", "action_point", "target", "status", "remarks"]
          ].copy()
          print_df.columns = [
              "Department",
              "Resolution / Commitment",
              "Target",
              "Status",
              "Outcome / Remarks",
          ]
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
        b64_html = base64.b64encode(printable_html.encode("utf-8")).decode(
            "utf-8"
        )
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
      start_date = col_dt1.date_input(
          "Start Date", value=date.today().replace(day=1)
      )
      end_date = col_dt2.date_input("End Date", value=date.today())

      if not df_meetings.empty:
        mask = (
            pd.to_datetime(df_meetings["meeting_date"]).dt.date >= start_date
        ) & (pd.to_datetime(df_meetings["meeting_date"]).dt.date <= end_date)
        filtered_meetings = df_meetings.loc[mask]

        if not filtered_meetings.empty:
          meeting_ids = filtered_meetings["id"].tolist()
          m_map = {
              m["id"]: m for m in filtered_meetings.to_dict("records")
          }

          date_ap_query = (
              supabase.table("meeting_action_points")
              .select("*")
              .in_("meeting_id", meeting_ids)
              .execute()
              .data
          )
          if date_ap_query:
            df_date_ap = pd.DataFrame(date_ap_query)
            df_date_ap["Department"] = df_date_ap["department_id"].map(
                dept_map_reverse
            )
            df_date_ap["Meeting Date"] = df_date_ap["meeting_id"].map(
                lambda x: m_map.get(x, {}).get("meeting_date", "Unknown")
            )
            df_date_ap["Meeting Level"] = df_date_ap["meeting_id"].map(
                lambda x: m_map.get(x, {}).get("meeting_type", "Unknown")
            )

            disp_cols = [
                "Meeting Date",
                "Meeting Level",
                "Department",
                "action_point",
                "target",
                "status",
            ]
            st.dataframe(
                df_date_ap[disp_cols].sort_values(
                    ["Meeting Date", "Department"]
                ),
                use_container_width=True,
                hide_index=True,
            )

            print_df = df_date_ap[disp_cols].copy()
            print_df.columns = [
                "Date",
                "Level",
                "Department",
                "Resolution / Commitment",
                "Target",
                "Status",
            ]
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
            b64_html_date = base64.b64encode(
                date_printable_html.encode("utf-8")
            ).decode("utf-8")
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

    all_ap = supabase.table("meeting_action_points").select("*").execute().data
    if all_ap:
      df_all_ap = pd.DataFrame(all_ap)
      df_all_ap["Department"] = df_all_ap["department_id"].map(
          dept_map_reverse
      )

      # Helper to check strings safely
      df_all_ap["is_completed"] = df_all_ap["status"].apply(
          lambda x: str(x).lower() in ["completed", "dropped"]
      )
      active_df = df_all_ap[~df_all_ap["is_completed"]]

      unfeasible_df = active_df[
          active_df["status"].apply(
              lambda x: "feasible" in str(x).lower()
              or "review" in str(x).lower()
          )
      ]
      pending_df = active_df[
          ~active_df["status"].apply(
              lambda x: "feasible" in str(x).lower()
              or "review" in str(x).lower()
          )
      ]

      if not unfeasible_df.empty or not pending_df.empty:
        st.warning(
            f"⚠️ {len(active_df)} items ready for the next agenda"
            f" ({len(unfeasible_df)} require immediate review)."
        )

        agenda_text = "AGENDA FOR UPCOMING MEETING:\n\n"

        if not unfeasible_df.empty:
          agenda_text += "🔴 ITEMS FLAGGED AS NOT FEASIBLE (FOR REVIEW):\n"
          for idx, row in unfeasible_df.iterrows():
            officer = row.get("responsible_officer", "Unassigned")
            agenda_text += (
                f"- [{row['Department']}] {row['action_point']}\n"
                f"  Officer: {officer}\n  Reason:"
                f" {row.get('remarks', 'N/A')}\n\n"
            )

        if not pending_df.empty:
          agenda_text += "⏳ PENDING / OVERDUE COMMITMENTS:\n"
          for idx, row in pending_df.iterrows():
            officer = row.get("responsible_officer", "Unassigned")
            agenda_text += (
                f"- [{row['Department']}] {row['action_point']} (Officer:"
                f" {officer})\n"
            )

        st.text_area("Copy Agenda Text:", value=agenda_text, height=300)
      else:
        st.success("🎉 No pending items for the next meeting!")
    else:
      st.info("No action points in the system.")
