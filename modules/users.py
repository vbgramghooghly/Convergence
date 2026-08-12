import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin')
    st.title("User Management")

    supabase = get_supabase()
    user = get_current_user()

    # Fetch all users (join with auth.users to get email)
    # Supabase RPC or separate query: we get from our users table
    users_data = supabase.table("users").select("*").execute().data
    if not users_data:
        st.info("No users found.")
        return

    df = pd.DataFrame(users_data)
    st.dataframe(df[['id','full_name','role','district_id','block_id','department_id','active']], use_container_width=True)

    st.subheader("Edit User")
    user_id = st.selectbox("Select User", df['id'].tolist(), format_func=lambda x: df[df['id']==x]['full_name'].values[0])
    selected_user = df[df['id'] == user_id].iloc[0].to_dict()

    with st.form("edit_user"):
        new_role = st.selectbox("Role", ['superadmin','district','block','department'], index=['superadmin','district','block','department'].index(selected_user['role']))
        # Update district/block/dept based on role
        districts = supabase.table("districts").select("id,district_name").eq("active",True).execute().data
        blocks = supabase.table("blocks").select("id,block_name").eq("active",True).execute().data
        departments = supabase.table("departments").select("id,department_name").eq("active",True).execute().data

        dist_dict = {d['district_name']: d['id'] for d in districts}
        block_dict = {b['block_name']: b['id'] for b in blocks}
        dept_dict = {d['department_name']: d['id'] for d in departments}

        new_district = None
        new_block = None
        new_dept = None

        if new_role in ['district','block','department']:
            new_district = st.selectbox("District", list(dist_dict.keys()), index=list(dist_dict.keys()).index(next(k for k,v in dist_dict.items() if v==selected_user.get('district_id'))) if selected_user.get('district_id') else 0)
        if new_role == 'block':
            new_block = st.selectbox("Block", list(block_dict.keys()), index=list(block_dict.keys()).index(next(k for k,v in block_dict.items() if v==selected_user.get('block_id'))) if selected_user.get('block_id') else 0)
        if new_role == 'department':
            new_dept = st.selectbox("Department", list(dept_dict.keys()), index=list(dept_dict.keys()).index(next(k for k,v in dept_dict.items() if v==selected_user.get('department_id'))) if selected_user.get('department_id') else 0)

        active = st.checkbox("Active", value=selected_user['active'])
        submitted = st.form_submit_button("Update User")
        if submitted:
            updates = {
                "role": new_role,
                "active": active
            }
            if new_role in ['district','block','department']:
                updates["district_id"] = dist_dict[new_district]
            else:
                updates["district_id"] = None
            if new_role == 'block':
                updates["block_id"] = block_dict[new_block]
            else:
                updates["block_id"] = None
            if new_role == 'department':
                updates["department_id"] = dept_dict[new_dept]
            else:
                updates["department_id"] = None

            old = {k: selected_user[k] for k in updates}
            supabase.table("users").update(updates).eq("id", user_id).execute()
            log_action(user, "UPDATE", "users", user_id, old_vals=old, new_vals=updates)
            st.success("User updated")
            st.rerun()
