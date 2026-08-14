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

    # ---------- FETCH MASTER DATA GLOBALLY ----------
    districts = supabase.table("districts").select("id,district_name").execute().data or []
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data or []
    depts = supabase.table("departments").select("id,department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    
    dist_map = {d['id']: d['district_name'] for d in districts}
    block_map = {b['id']: b['block_name'] for b in blocks}
    dept_map = {d['id']: d['department_name'] for d in depts}
    wing_map = {w['id']: w for w in wings}

    # Build a combined option list for Departments & Wings
    dept_options = []
    
    # 1. Add Parent Departments
    for d in depts:
        dept_options.append({
            "label": d['department_name'],
            "dept_id": d['id'],
            "wing_id": None
        })
        
    # 2. Add Wings/Parastatals
    for w in wings:
        parent_name = dept_map.get(w['department_id'], "Unknown Department")
        dept_options.append({
            "label": f"{parent_name} ➔ {w['wing_name']} [{w['entity_type']}]",
            "dept_id": w['department_id'],
            "wing_id": w['id']
        })
    
    # Sort alphabetically by label for easy finding
    dept_options = sorted(dept_options, key=lambda x: x['label'])
    dept_labels = [opt['label'] for opt in dept_options]

    # ---------- VIEW EXISTING USERS ----------
    st.subheader("👥 Current Users")
    users_data = supabase.table("users").select("*").execute().data
    
    if not users_data:
        st.info("No users found in the system.")
        return

    df = pd.DataFrame(users_data)
    df_display = df.copy()
    
    df_display['district_name'] = df_display['district_id'].map(dist_map)
    df_display['block_name'] = df_display['block_id'].map(block_map)
    
    # Custom function to display "Department ➔ Wing" if applicable
    def format_dept_display(row):
        if pd.isna(row.get('department_id')):
            return None
        dept_name = dept_map.get(row['department_id'], 'Unknown')
        wing_id = row.get('wing_id')
        if pd.notna(wing_id) and wing_id in wing_map:
            return f"{dept_name} ➔ {wing_map[wing_id]['wing_name']}"
        return dept_name

    df_display['department_name'] = df_display.apply(format_dept_display, axis=1)
    
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

    # Department & Wing dropdown
    new_dept_id = None
    new_wing_id = None
    
    if new_role == 'department':
        dept_options_with_placeholder = ["-- Select Department or Wing --"] + dept_labels
        cur_dept_id = selected_user.get('department_id')
        cur_wing_id = selected_user.get('wing_id')
        
        dept_index = 0
        if cur_dept_id:
            # Match against the combined options
            for i, opt in enumerate(dept_options):
                # We check equality for both dept and wing. 
                # (e.g. if wing is None, we want the parent dept option)
                if opt['dept_id'] == cur_dept_id and opt['wing_id'] == cur_wing_id:
                    dept_index = i + 1 
                    break
                    
        selected_dept_label = st.selectbox("Department / Wing", dept_options_with_placeholder, index=dept_index)
        
        if selected_dept_label != "-- Select Department or Wing --":
            selected_opt = next(opt for opt in dept_options if opt['label'] == selected_dept_label)
            new_dept_id = selected_opt['dept_id']
            new_wing_id = selected_opt['wing_id']

    active = st.checkbox("Active Account", value=selected_user.get('active', True))

    if st.button("Update User Profile", type="primary"):
        if new_role == 'department' and not new_dept_id:
            st.error("Please select a valid Department or Wing from the dropdown.")
        else:
            updates = {
                "role": new_role,
                "active": active,
                "district_id": new_dist_id,
                "block_id": new_block_id if new_role == 'block' else None,
                "department_id": new_dept_id if new_role == 'department' else None
                # "wing_id" removed to prevent PGRST204 column missing error
            }
            try:
                # 1. Update Database
                supabase.table("users").update(updates).eq("id", selected_uid).execute()
                
                # 2. Log Action 
                log_action(user, "UPDATE", "users", selected_uid, new_vals=updates)
                
                st.success("User updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update user: {e}")
            
    # --- ADMIN PASSWORD ALTERNATION ---
    with st.expander("🔑 Change / Alternate User Password"):
        st.warning("This will immediately overwrite the user's current password.")
        new_pw = st.text_input("New Password", type="password", key="edit_pw_input")
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

    # ---------- CREATE NEW USER (MANUAL) ----------
    st.markdown("---")
    st.subheader("➕ Create Single User Manually")
    
    # Removed st.form, added unique keys to prevent DuplicateWidgetID errors
    new_fullname = st.text_input("Full Name (e.g. Nodal Officer WBSRDA)", key="create_fname")
    new_email = st.text_input("Username (without @domain)", key="create_uname")
    new_password = st.text_input("Password", type="password", key="create_pw")
    new_user_role = st.selectbox("Initial Role", ['district', 'block', 'department'], key="create_role")
    
    district_list_form = [d['district_name'] for d in districts]
    new_dist_name = st.selectbox("District", district_list_form, key="create_dist")
    
    new_dept_label = None
    if new_user_role == 'department':
        dept_names_form = ["-- Select Department or Wing --"] + dept_labels
        new_dept_label = st.selectbox("Department / Wing", dept_names_form, key="create_dept")

    submitted = st.button("Create User", type="primary")
    
    if submitted:
        if not SERVICE_KEY:
            st.error("Service key is not configured.")
            st.stop()
            
        if new_user_role == 'department' and new_dept_label == "-- Select Department or Wing --":
            st.error("You must select a specific department or wing for a Department user.")
            st.stop()
            
        if not new_email or not new_password or not new_fullname:
            st.error("Name, Username, and Password are required.")
            st.stop()

        new_dist_id = next((d['id'] for d in districts if d['district_name'] == new_dist_name), None)
        
        new_dept_id = None
        new_wing_id = None
        if new_user_role == 'department' and new_dept_label:
            selected_opt = next(opt for opt in dept_options if opt['label'] == new_dept_label)
            new_dept_id = selected_opt['dept_id']
            new_wing_id = selected_opt['wing_id']
        
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
                # "wing_id" removed to prevent PGRST204 column missing error
                "active": True
            }
            supabase.table("users").insert(user_record).execute()
            log_action(user, "CREATE", "users", new_uuid, new_vals=user_record)
            st.success(f"User {new_fullname} created successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Error creating user: {e}")
