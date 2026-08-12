import streamlit as st
import pandas as pd
from supabase import create_client
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action
from config.settings import SUPABASE_URL, SUPABASE_KEY, SERVICE_KEY   

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
    
    # Fetch master data
    districts = supabase.table("districts").select("id,district_name").execute().data
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data
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
        format_func=lambda x: f"{df[df['id']==x]['full_name'].values[0]} ({df[df['id']==x]['role'].values[0].upper()})"
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

    # Block dropdown 
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

    # Department dropdown (Prevent auto-selecting Agriculture)
    if new_role == 'department':
        dept_names = ["-- Select Department --"] + [d['department_name'] for d in depts]
        cur_dept_id = selected_user.get('department_id')
        dept_index = 0
        if cur_dept_id:
            for i, d in enumerate(depts):
                if d['id'] == cur_dept_id:
                    dept_index = i + 1 # +1 to account for the "-- Select --" placeholder
                    break
        selected_dept_name = st.selectbox("Department", dept_names, index=dept_index)
        new_dept_id = next((d['id'] for d in depts if d['department_name'] == selected_dept_name), None)
    else:
        new_dept_id = None

    active = st.checkbox("Active Account", value=selected_user.get('active', True))

    if st.button("Update User Profile", type="primary"):
        if new_role == 'department' and not new_dept_id:
            st.error("Please select a valid Department from the dropdown.")
        else:
            updates = {
                "role": new_role,
                "active": active,
                "district_id": new_dist_id,
                "block_id": new_block_id if new_role == 'block' else None,
                "department_id": new_dept_id if new_role == 'department' else None
            }
            try:
                # 1. Update Database
                supabase.table("users").update(updates).eq("id", selected_uid).execute()
                
                # 2. Log Action (FIXED: Removed old_vals argument)
                log_action(user, "UPDATE", "users", selected_uid, new_vals=updates)
                
                st.success("User updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update user: {e}")
            
    # --- ADMIN PASSWORD ALTERNATION ---
    with st.expander("🔑 Change / Alternate User Password"):
        st.warning("This will immediately overwrite the user's current password.")
        new_pw = st.text_input("New Password", type="password")
        if st.button("Reset Password"):
            if not SERVICE_KEY:
                st.error("Service key is required to alter passwords.")
            elif len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    admin_supabase = create_client(SUPABASE_URL, SERVICE_KEY)
                    admin_supabase.auth.admin.update_user_by_id(
                        selected_uid,
                        {"password": new_pw}
                    )
                    st.success(f"Password for {selected_user['full_name']} updated successfully!")
                except Exception as e:
                    st.error(f"Error resetting password: {e}")

    st.markdown("---")

    # ---------- BULK CREATE USERS FROM MASTER DATA ----------
    st.subheader("📂 Bulk Create Users from Master Data")
    st.caption("Upload a CSV with columns: `Administrative Unit`, `Role`, `Username`, `Default Password`")
    
    # Define District for this batch (Needed for Department & Block users)
    bulk_dist_name = st.selectbox("Assign these imported users to District:", [d['district_name'] for d in districts])
    
    uploaded_file = st.file_uploader("Choose Master Data CSV", type="csv")
    
    if uploaded_file:
        bulk_df = pd.read_csv(uploaded_file)
        st.dataframe(bulk_df.head(), use_container_width=True)
        
        if st.button("Run Bulk Import", type="primary"):
            if not SERVICE_KEY:
                st.error("Service key is required for bulk user creation.")
                st.stop()
                
            admin_supabase = create_client(SUPABASE_URL, SERVICE_KEY)
            
            # Reverse maps for quick ID lookup by name
            name_to_dist = {d['district_name'].lower().strip(): d['id'] for d in districts}
            name_to_block = {b['block_name'].lower().strip(): b for b in blocks} 
            name_to_dept = {d['department_name'].lower().strip(): d['id'] for d in depts}
            
            success_count = 0
            
            with st.spinner("Provisioning users..."):
                for index, row in bulk_df.iterrows():
                    admin_name = str(row.get('Administrative Unit', '')).strip()
                    role = str(row.get('Role', '')).strip().lower()
                    username = str(row.get('Username', '')).strip()
                    password = str(row.get('Default Password', '')).strip()
                    
                    if not all([admin_name, role, username, password]):
                        st.warning(f"Row {index+2}: Missing data, skipping.")
                        continue
                        
                    email = f"{username}@hooghly.gov.in"
                    
                    # Assume district based on the dropdown above
                    dist_id = name_to_dist.get(bulk_dist_name.lower().strip())
                    block_id = None
                    dept_id = None
                    
                    # 1. Map string names to DB UUIDs
                    if role == 'district':
                        lookup_name = admin_name.lower().replace(" district", "")
                        dist_id = name_to_dist.get(lookup_name)
                        if not dist_id:
                            st.error(f"Row {index+2}: Could not find district matching '{admin_name}'")
                            continue
                            
                    elif role == 'block':
                        block_data = name_to_block.get(admin_name.lower())
                        if block_data:
                            block_id = block_data['id']
                            dist_id = block_data['district_id']
                        else:
                            st.error(f"Row {index+2}: Could not find block matching '{admin_name}'")
                            continue
                            
                    elif role == 'department':
                        dept_id = name_to_dept.get(admin_name.lower())
                        if not dept_id:
                            st.error(f"Row {index+2}: Could not find department matching '{admin_name}' in Master Data.")
                            continue
                            
                    # 2. Create Auth User
                    try:
                        auth_response = admin_supabase.auth.admin.create_user({
                            "email": email,
                            "password": password,
                            "email_confirm": True,
                            "user_metadata": {"full_name": admin_name}
                        })
                        new_uuid = auth_response.user.id
                        
                        # 3. Create Public Profile
                        user_record = {
                            "id": new_uuid,
                            "full_name": admin_name,
                            "role": role,
                            "district_id": dist_id,
                            "block_id": block_id,
                            "department_id": dept_id,
                            "active": True
                        }
                        supabase.table("users").insert(user_record).execute()
                        success_count += 1
                        
                    except Exception as e:
                        st.error(f"Failed to create {username}: {str(e)}")
                        
            st.success(f"Bulk import complete! {success_count} users created.")
            st.rerun()

    # ---------- CREATE NEW USER (MANUAL) ----------
    st.markdown("---")
    st.subheader("➕ Create Single User Manually")
    
    with st.form("create_user_form"):
        new_fullname = st.text_input("Full Name")
        new_email = st.text_input("Username (without @domain)")
        new_password = st.text_input("Password", type="password")
        new_user_role = st.selectbox("Initial Role", ['district', 'block', 'department'])
        
        district_list_form = [d['district_name'] for d in districts]
        new_dist_name = st.selectbox("District", district_list_form)
        
        new_dept_name = None
        if new_user_role == 'department':
            dept_names_form = ["-- Select Department --"] + [d['department_name'] for d in depts]
            new_dept_name = st.selectbox("Department", dept_names_form)

        submitted = st.form_submit_button("Create User")
        if submitted:
            if not SERVICE_KEY:
                st.error("Service key is not configured.")
                st.stop()
                
            if new_user_role == 'department' and new_dept_name == "-- Select Department --":
                st.error("You must select a specific department for a Department user.")
                st.stop()
                
            if not new_email or not new_password or not new_fullname:
                st.error("Name, Username, and Password are required.")
                st.stop()

            new_dist_id = next((d['id'] for d in districts if d['district_name'] == new_dist_name), None)
            new_dept_id = next((d['id'] for d in depts if d['department_name'] == new_dept_name), None) if new_dept_name else None
            
            # Format email
            formatted_email = f"{new_email.strip()}@hooghly.gov.in"

            try:
                admin_supabase = create_client(SUPABASE_URL, SERVICE_KEY)
                auth_response = admin_supabase.auth.admin.create_user({
                    "email": formatted_email,
                    "password": new_password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": new_fullname}
                })
                
                new_uuid = auth_response.user.id
                user_record = {
                    "id": new_uuid,
                    "full_name": new_fullname,
                    "role": new_user_role,
                    "district_id": new_dist_id,
                    "block_id": None,   
                    "department_id": new_dept_id,
                    "active": True
                }
                supabase.table("users").insert(user_record).execute()
                log_action(user, "CREATE", "users", new_uuid, new_vals=user_record)
                st.success(f"User {new_fullname} created successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating user: {e}")
