import streamlit as st
import pandas as pd
from datetime import date
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block', 'department')
    
    st.title("Implementation Monitoring")
    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # 1. Fetch Convergence Activities based on role scope
    query = supabase.table("convergence_register").select("*")
    if role == 'district':
        query = query.eq("district_id", user['district_id'])
    elif role == 'block':
        query = query.eq("block_id", user['block_id'])
    elif role == 'department':
        query = query.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    activities = query.execute().data

    if not activities:
        st.info("No convergence activities found to monitor.")
        return

    # Create a clean label for the selectbox
    activity_map = {
        a['id']: f"{a.get('id', '')} - {a.get('activity_description', 'Unnamed Activity')}"
        for a in activities
    }

    selected_act_id = st.selectbox(
        "Select Convergence Activity",
        options=list(activity_map.keys()),
        format_func=lambda x: activity_map[x]
    )

    selected_activity = next((a for a in activities if a['id'] == selected_act_id), None)

    if selected_activity:
        st.markdown(f"### Current Status: **{selected_activity.get('current_status', 'Planned')}**")
        
        with st.form("update_progress_form"):
            st.subheader("Update Progress")
            
            status_options = ["Planned", "Approved", "Under Implementation", "Completed", "Delayed"]
            current_status = selected_activity.get('current_status', 'Planned')
            status_idx = status_options.index(current_status) if current_status in status_options else 0
            
            new_status = st.selectbox("New Status", status_options, index=status_idx)
            
            col1, col2, col3 = st.columns(3)
            phys_ach = col1.number_input("Physical Achievement (%)", min_value=0.0, max_value=100.0, value=float(selected_activity.get('physical_achievement', 0.0) or 0.0))
            # FIXED: Changed from Cr. to Lakhs
            fin_ach = col2.number_input("Financial Achievement (₹ Lakhs)", min_value=0.0, value=float(selected_activity.get('financial_achievement', 0.0) or 0.0))
            persondays_gen = col3.number_input("Persondays Generated (cumulative)", min_value=0, value=int(selected_activity.get('persondays_generated', 0) or 0))

            col4, col5, col6 = st.columns(3)
            start_date = col4.date_input("Actual Start Date", value=date.today())
            exp_date = col5.date_input("Expected Completion Date", value=date.today())
            act_date = col6.date_input("Actual Completion Date (if completed)", value=None)

            remarks = st.text_area("Remarks", value=selected_activity.get('remarks', '') or '')

            submitted = st.form_submit_button("Save Progress", type="primary")
            
            if submitted:
                update_data = {
                    "current_status": new_status,
                    "physical_achievement": phys_ach,
                    "financial_achievement": fin_ach,
                    "persondays_generated": persondays_gen,
                    "actual_start_date": str(start_date) if start_date else None,
                    "expected_completion_date": str(exp_date) if exp_date else None,
                    "actual_completion_date": str(act_date) if act_date else None,
                    "remarks": remarks
                }
                
                try:
                    # 1. Update main register
                    supabase.table("convergence_register").update(update_data).eq("id", selected_act_id).execute()
                    
                    # 2. Log progress history entry
                    history_payload = {
                        "convergence_id": selected_act_id,
                        "status": new_status,
                        "physical_achievement": phys_ach,
                        "financial_achievement": fin_ach,
                        "persondays_generated": persondays_gen,
                        "remarks": remarks
                    }
                    supabase.table("progress_updates").insert(history_payload).execute()
                    
                    try:
                        log_action(user.get('id'), f"UPDATE progress convergence_register {selected_act_id}")
                    except Exception:
                        pass
                        
                    st.success("✅ Progress updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving progress: {e}")

    # ==========================================
    # PROGRESS HISTORY TABLE (FIXED SORTING ERROR)
    # ==========================================
    st.markdown("---")
    st.subheader("Progress History")
    
    try:
        # FIXED: Changed from 'updated_at' to 'created_at' to match standard Supabase schemas
        history_query = supabase.table("progress_updates").select("*").eq("convergence_id", selected_act_id).order("created_at", desc=True).execute()
        history_data = history_query.data
        
        if history_data:
            df_history = pd.DataFrame(history_data)
            st.dataframe(df_history, use_container_width=True, hide_index=True)
        else:
            st.info("No historical updates recorded for this activity yet.")
    except Exception as e:
        # Fallback query if created_at is also missing
        try:
            fallback_query = supabase.table("progress_updates").select("*").eq("convergence_id", selected_act_id).execute()
            df_history = pd.DataFrame(fallback_query.data)
            if not df_history.empty:
                st.dataframe(df_history, use_container_width=True, hide_index=True)
            else:
                st.info("No historical updates recorded for this activity yet.")
        except Exception as inner_e:
            st.warning(f"Could not load history table: {inner_e}")
