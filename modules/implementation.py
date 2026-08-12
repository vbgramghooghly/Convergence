import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin', 'district', 'block', 'department')
    st.title("Implementation Monitoring")

    supabase = get_supabase()
    user = get_current_user()

    # Fetch convergence activities based on role (RLS is also enforced)
    query = supabase.table("convergence_register").select("*")
    if user['role'] == 'district':
        query = query.eq("district_id", user['district_id'])
    elif user['role'] == 'block':
        query = query.eq("block_id", user['block_id'])
    elif user['role'] == 'department':
        query = query.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    activities = query.execute().data
    if not activities:
        st.info("No convergence activities found.")
        return

    df_activities = pd.DataFrame(activities)
    # Create a selection list with meaningful labels
    activity_options = [f"{a['id']} - {a['activity_description'][:50]}" for a in activities]
    activity_ids = [a['id'] for a in activities]

    # Select activity to update
    selected_label = st.selectbox("Select Convergence Activity", activity_options)
    selected_index = activity_options.index(selected_label)
    selected_activity = activities[selected_index]

    st.markdown("### Current Status: **{}**".format(selected_activity.get('current_status', 'N/A')))

    with st.form("update_progress"):
        st.subheader("Update Progress")

        # Status dropdown (configurable stages)
        status_list = ["Planned", "Approved", "Work Order Issued", "Labour Demand", "Material Procurement",
                       "Work Started", "Work in Progress", "Work Completed", "Asset Registered", "Verified", "Closed"]
        current_status_index = status_list.index(selected_activity['current_status']) if selected_activity['current_status'] in status_list else 0
        new_status = st.selectbox("New Status", status_list, index=current_status_index)

        # Physical & financial achievement
        physical_achievement = st.number_input("Physical Achievement (%)", min_value=0.0, max_value=100.0,
                                               value=float(selected_activity.get('physical_achievement', 0)), step=0.1)
        financial_achievement = st.number_input("Financial Achievement (₹ Cr.)", min_value=0.0,
                                                value=float(selected_activity.get('financial_achievement', 0)), format="%.2f")
        persondays_generated = st.number_input("Persondays Generated (cumulative)", min_value=0,
                                               value=int(selected_activity.get('persondays_generated', 0)))

        # Implementation dates
        start_date = st.date_input("Actual Start Date", value=selected_activity.get('target_start_date') or date.today())
        expected_completion = st.date_input("Expected Completion Date",
                                            value=selected_activity.get('target_completion_date') or date.today())
        actual_completion = st.date_input("Actual Completion Date (if completed)", value=None)

        remarks = st.text_area("Remarks", value=selected_activity.get('remarks', ''))

        submitted = st.form_submit_button("Save Progress")
        if submitted:
            # Calculate delay if completed
            delay_days = 0
            if actual_completion and expected_completion:
                delay_days = (actual_completion - expected_completion).days
                if delay_days < 0:
                    delay_days = 0

            updates = {
                "current_status": new_status,
                "physical_achievement": physical_achievement,
                "financial_achievement": financial_achievement,
                "persondays_generated": persondays_generated,
                "target_start_date": str(start_date),
                "target_completion_date": str(expected_completion),
                "duration_days": (expected_completion - start_date).days if expected_completion > start_date else 0,
                "remarks": remarks,
                "updated_by": user['id'],
                "updated_at": datetime.utcnow().isoformat()
            }
            if actual_completion:
                updates["actual_completion_date"] = str(actual_completion)
                updates["delay_days"] = delay_days

            # Save the main record
            old_vals = {k: selected_activity[k] for k in updates if k in selected_activity}
            result = supabase.table("convergence_register").update(updates).eq("id", selected_activity['id']).execute()
            if result.data:
                # Insert into progress_updates history
                history_entry = {
                    "convergence_id": selected_activity['id'],
                    "status": new_status,
                    "remarks": remarks,
                    "updated_by": user['id']
                }
                supabase.table("progress_updates").insert(history_entry).execute()
                log_action(user, "UPDATE_PROGRESS", "convergence_register", selected_activity['id'], old_vals=old_vals, new_vals=updates)
                st.success("Progress updated successfully!")
                st.rerun()
            else:
                st.error("Failed to update progress.")

    # Show progress history
    st.divider()
    st.subheader("Progress History")
    history = supabase.table("progress_updates").select("*").eq("convergence_id", selected_activity['id']).order("updated_at", desc=True).execute().data
    if history:
        df_hist = pd.DataFrame(history)
        st.dataframe(df_hist[['status', 'remarks', 'updated_at']], use_container_width=True)
    else:
        st.info("No progress updates recorded.")
