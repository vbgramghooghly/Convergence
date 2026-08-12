import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block')
    st.title("Convergence Meetings")

    supabase = get_supabase()
    user = get_current_user()

    # Tab layout
    tab1, tab2, tab3 = st.tabs(["Schedule Meeting", "View Meetings", "Action Points"])

    # ======================== Schedule Meeting ========================
    with tab1:
        st.subheader("Schedule New Meeting")
        with st.form("meeting_form"):
            if user['role'] in ['superadmin', 'district']:
                meeting_type = st.radio("Meeting Level", ['District', 'Block'], horizontal=True)
            else:  # block user can only schedule Block meeting
                meeting_type = 'Block'

            if meeting_type == 'District':
                districts = supabase.table("districts").select("id,district_name").eq("active", True).execute().data
                dist_dict = {d['district_name']: d['id'] for d in districts}
                if user['role'] == 'district':
                    dist_sel = next((name for name, id in dist_dict.items() if id == user['district_id']), None)
                    st.text(f"District: {dist_sel}")
                else:
                    dist_sel = st.selectbox("District", list(dist_dict.keys()))
                block_sel = None
            else:
                # Block meeting
                blocks = supabase.table("blocks").select("id,block_name,district_id").eq("active", True).execute().data
                if user['role'] == 'block':
                    block_sel_list = [b for b in blocks if b['id'] == user['block_id']]
                    if block_sel_list:
                        block_sel = block_sel_list[0]['block_name']
                    else:
                        block_sel = None
                    dist_sel = None
                else:
                    # Superadmin or district – choose block
                    block_sel = st.selectbox("Block", [b['block_name'] for b in blocks])
                    # Fetch corresponding district for the selected block
                    selected_block = next(b for b in blocks if b['block_name'] == block_sel)
                    dist_sel = selected_block['district_id']  # not shown, used internally

            meeting_date = st.date_input("Meeting Date", date.today())
            chairperson = st.text_input("Chairperson")
            agenda = st.text_area("Agenda")
            decisions = st.text_area("Decisions / Minutes")

            submitted = st.form_submit_button("Save Meeting")
            if submitted:
                meeting_data = {
                    "meeting_type": meeting_type,
                    "meeting_date": str(meeting_date),
                    "chairperson": chairperson,
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
                        # find block id
                        block_obj = next(b for b in blocks if b['block_name'] == block_sel)
                        meeting_data["block_id"] = block_obj['id']
                        meeting_data["district_id"] = block_obj['district_id']  # optional

                result = supabase.table("meetings").insert(meeting_data).execute()
                if result.data:
                    st.success("Meeting recorded.")
                    # Fixed: Changed new_vals to details
                    log_action(user, "CREATE", "meetings", result.data[0]['id'], details=meeting_data)
                    st.rerun()
                else:
                    st.error("Failed to save meeting.")

    # ======================== View Meetings ========================
    with tab2:
        st.subheader("Meeting List")
        query = supabase.table("meetings").select("*")
        if user['role'] == 'district':
            query = query.eq("district_id", user['district_id']).eq("meeting_type", "District")  # assume district sees district meetings
        elif user['role'] == 'block':
            query = query.eq("block_id", user['block_id'])
        meetings = query.order("meeting_date", desc=True).execute().data
        if meetings:
            df_meetings = pd.DataFrame(meetings)
            st.dataframe(df_meetings, use_container_width=True)
            # Select meeting to view action points
            meeting_sel = st.selectbox("Select Meeting to manage action points", df_meetings['id'].tolist(),
                                       format_func=lambda x: f"{df_meetings[df_meetings['id']==x]['meeting_date'].values[0]} - {df_meetings[df_meetings['id']==x]['meeting_type'].values[0]}")
            st.session_state['selected_meeting_id'] = meeting_sel
        else:
            st.info("No meetings found.")

    # ======================== Action Points ========================
    with tab3:
        st.subheader("Action Points")
        selected_meeting = st.session_state.get('selected_meeting_id', None)
        if not selected_meeting and meetings:
            selected_meeting = meetings[0]['id']

        if selected_meeting:
            # Add action point
            with st.form("add_action"):
                action_text = st.text_input("Action Point")
                responsible = st.text_input("Responsible Officer")
                deadline = st.date_input("Deadline", date.today())
                status = st.selectbox("Status", ['Open', 'In Progress', 'Completed', 'Overdue'])
                add_submit = st.form_submit_button("Add Action Point")
                if add_submit:
                    action_data = {
                        "meeting_id": selected_meeting,
                        "action_point": action_text,
                        "responsible_officer": responsible,
                        "deadline": str(deadline),
                        "status": status
                    }
                    res = supabase.table("meeting_action_points").insert(action_data).execute()
                    if res.data:
                        st.success("Action point added.")
                        # Fixed: Changed new_vals to details
                        log_action(user, "CREATE", "meeting_action_points", res.data[0]['id'], details=action_data)
                        st.rerun()
                    else:
                        st.error("Failed to add.")

            # View existing action points for this meeting
            st.subheader("Existing Action Points")
            ap_query = supabase.table("meeting_action_points").select("*").eq("meeting_id", selected_meeting).execute().data
            if ap_query:
                df_ap = pd.DataFrame(ap_query)
                st.dataframe(df_ap[['id','action_point','responsible_officer','deadline','status']], use_container_width=True)

                # Update action point status inline
                ap_id = st.selectbox("Action Point ID to update", df_ap['id'].tolist(), key="ap_update")
                new_ap_status = st.selectbox("New Status", ['Open', 'In Progress', 'Completed', 'Overdue'], key="ap_status")
                if st.button("Update Action Point"):
                    supabase.table("meeting_action_points").update({"status": new_ap_status}).eq("id", ap_id).execute()
                    # Fixed: Changed new_vals to details
                    log_action(user, "UPDATE", "meeting_action_points", ap_id, details={"status": new_ap_status})
                    st.rerun()
            else:
                st.info("No action points for this meeting yet.")
