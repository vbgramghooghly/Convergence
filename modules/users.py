import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action
from config.settings import SUPABASE_URL, SUPABASE_KEY, SERVICE_KEY   # add SERVICE_KEY

def show():
    require_role('superadmin')
    st.title("User Management")
    supabase = get_supabase()
    user = get_current_user()

    # ---------- VIEW EXISTING USERS ----------
    st.subheader("👥 Current Users")
    users_data = supabase.table("users").select("*").execute().data
    if not users_data:
        st.info("No users found in the system.")
        return

    df = pd.DataFrame(users_data)
    # Fetch district, block, department names for display
    districts = supabase.table("districts").select("id,district_name").execute().data
    blocks = supabase.table("blocks").select("id,block_name").execute().data
    depts = supabase.table("departments").select("id,department_name").execute().data
    dist_map = {d['id']: d['district_name'] for d in districts}
    block_map = {b['id']: b['block_name'] for b in blocks}
    dept_map = {d['id']: d['department_name'] for d in depts}

    df_display = df.copy()
    df_display['district_name'] = df_display['district_id'].map(dist_map)
    df_display['block_name'] = df_display['block_id'].map(block_map)
    df_display['department_name'] = df_display['department_id'].map(dept_map)
    st.dataframe(
        df_display[['full_name', 'role', 'district_name', 'block_name', 'department_name', 'active']],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # ---------- EDIT EXISTING USER ----------
    st.subheader("✏️ Edit User Role & Access")
    user_ids = df['id'].tolist()
    selected_uid = st.selectbox(
        "Select user to edit",
        user_ids,
        format_func=lambda x: df[df['id']==x]['full_name'].values[0]
    )
    selected_user = df[df['id'] == selected_uid].iloc[0].to_dict()

    roles = ['superadmin', 'district', 'block', 'department']
    current_role = selected_user['role']
    new_role = st.selectbox("Role", roles, index=roles.index(current_role))

    # District dropdown
    district_list = [d['district_name'] for d in districts]
    if new_role in ['district', 'block', 'department']:
        cur_dist_id = selected_user.get('district_id')
        dist_index = 0
        if cur_dist_id:
            for i, d in enumerate(districts):
                if d['id'] == cur_dist_id:
                    dist_index = i
                    break
        selected_dist_name = st.selectbox("District", district_list, index=dist_index)
        new_dist_id = next(d['id'] for d in districts if d['district_name'] == selected_dist_name)
    else:
        new_dist_id = None

    # Block dropdown (only for block role, filtered by selected district)
    if new_role == 'block' and new_dist_id is not None:
        filtered_blocks = [b for b in blocks if b['district_id'] == new_dist_id]
        if filtered_blocks:
            block_names = [b['block_name'] for b in filtered_blocks]
            cur_block_id = selected_user.get('block_id')
            block_index = 0
            if cur_block_id:
                for i, b in enumerate(filtered_blocks):
                    if b['id'] == cur_block_id:
                        block_index = i
                        break
            selected_block_name = st.selectbox("Block", block_names, index=block_index)
            new_block_id = next(b['id'] for b in filtered_blocks if b['block_name'] == selected_block_name)
        else:
            st.warning("No blocks available for this district.")
            new_block_id = None
    else:
        new_block_id = None

    # Department dropdown (only for department role)
    if new_role == 'department':
        dept_names = [d['department_name'] for d in depts]
        cur_dept_id = selected_user.get('department_id')
        dept_index = 0
        if cur_dept_id:
            for i, d in enumerate(depts):
                if d['id'] == cur_dept_id:
                    dept_index = i
                    break
        selected_dept_name = st.selectbox("Department", dept_names, index=dept_index)
        new_dept_id = next(d['id'] for d in depts if d['department_name'] == selected_dept_name)
    else:
        new_dept_id = None

    active = st.checkbox("Active Account", value=selected_user.get('active', True))

    if st.button("Update User", type="primary"):
        updates = {
            "role": new_role,
            "active": active,
            "district_id": new_dist_id,
            "block_id": new_block_id if new_role == 'block' else None,
            "department_id": new_dept_id if new_role == 'department' else None
        }
        old_vals = {k: selected_user[k] for k in updates if k in selected_user}
        try:
            supabase.table("users").update(updates).eq("id", selected_uid).execute()
            log_action(user, "UPDATE", "users", selected_uid, old_vals=old_vals, new_vals=updates)
            st.success("User updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to update user: {e}")

    # ---------- CREATE NEW USER ----------
    st.markdown("---")
    st.subheader("➕ Create New User")
    st.caption("A new user will be created in Supabase Auth and linked to the public.users table.")

    with st.form("create_user_form"):
        new_fullname = st.text_input("Full Name")
        new_email = st.text_input("Email Address")
        new_password = st.text_input("Password", type="password")
        new_user_role = st.selectbox("Initial Role", ['district', 'block', 'department'])
        new_dist_name = st.selectbox("District", district_list)
        new_block_name = None
        if new_user_role == 'block':
            # We'll filter after form submission
            st.caption("Block will be assigned after creation (editing required)")
        new_dept_name = None
        if new_user_role == 'department':
            new_dept_name = st.selectbox("Department", dept_names)

        submitted = st.form_submit_button("Create User")
        if submitted:
            # Check if service key is available
            if not SERVICE_KEY:
                st.error("Service key is not configured. Cannot create user automatically. Please create the user manually in Supabase Authentication and then assign the UUID here.")
                st.stop()

            # Map names to IDs
            new_dist_id = dist_map.get(new_dist_name)
            new_dept_id = dept_map.get(new_dept_name) if new_dept_name else None

            try:
                # Create the auth user via admin API
                admin_supabase = create_client(SUPABASE_URL, SERVICE_KEY)
                auth_response = admin_supabase.auth.admin.create_user({
                    "email": new_email,
                    "password": new_password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": new_fullname}
                })
                if not auth_response.user:
                    st.error("Auth user creation failed.")
                    st.stop()

                new_uuid = auth_response.user.id

                # Insert into public.users
                user_record = {
                    "id": new_uuid,
                    "full_name": new_fullname,
                    "role": new_user_role,
                    "district_id": new_dist_id,
                    "block_id": None,   # block can be assigned later via edit
                    "department_id": new_dept_id,
                    "active": True
                }
                supabase.table("users").insert(user_record).execute()
                log_action(user, "CREATE", "users", new_uuid, new_vals=user_record)
                st.success(f"User {new_fullname} created successfully! They can now log in.")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating user: {e}")
