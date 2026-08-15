import pandas as pd
from datetime import date
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.db import get_supabase

def show():
    require_role("superadmin", "district", "block", "department")
    st.markdown("<h2 style='margin-bottom: 0px;'>🤝 Meeting Governance Tracker</h2>", unsafe_allow_html=True)
    st.caption("Schedule Meetings, Record Proceedings, and Track Resolutions.")

    supabase = get_supabase()
    user = get_current_user()
    role = user["role"]
    active_fy = st.session_state.get("selected_fy", "2026-27")

    q_meetings = supabase.table("meetings").select("*").eq("financial_year", active_fy)
    if role in ["district", "department"]: q_meetings = q_meetings.eq("district_id", user["district_id"])
    elif role == "block": q_meetings = q_meetings.eq("block_id", user["block_id"])
    meetings = q_meetings.execute().data or []
    
    tab1, tab2, tab3 = st.tabs(["🗓️ Schedule & Proceedings", "🎯 Resolution Action Tracker", "⏭️ Agenda Prep"])
    
    with tab1:
        st.markdown("#### Schedule & Proceedings are restricted to District and Block Admins.")
        st.dataframe(pd.DataFrame(meetings), use_container_width=True, hide_index=True) if meetings else st.info("No meetings scheduled.")
        
    with tab2:
        valid_meet_ids = [m['id'] for m in meetings]
        if valid_meet_ids:
            ap_data = supabase.table("meeting_action_points").select("*").in_("meeting_id", valid_meet_ids).execute().data
            if ap_data:
                st.dataframe(pd.DataFrame(ap_data)[['action_point', 'status', 'deadline']], use_container_width=True, hide_index=True)
            else: st.info("No action points generated yet.")
        else: st.info("No meetings found to track.")
