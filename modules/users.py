import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user
from utils.audit import log_action

def show():
    require_role('superadmin')
    
    # Modern UI Header
    st.markdown("<h1 style='color: #1F77B4;'>User Management</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()

    # Fetch all users
    users_data = supabase.table("users").select("*").execute().data
    if not users_data:
        st.info("💡 No users found in the system.")
        return

    df = pd.DataFrame(users_data)
    
    # Display current users elegantly
    st.subheader("👥 Current Users")
    st.dataframe(
        df[['id', 'full_name', 'role', 'district_id', 'block_id', 'department_id', 'active']], 
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.subheader("✏️ Edit User Profile & Roles")

    # Select User
    user_id = st.selectbox(
        "Select User to Edit", 
        df['id'].tolist(), 
        format_func=lambda x: df[df['id']==x]['full_name'].values[0]
    )
    selected_user = df[df['id'] == user_id].iloc[0].to_dict()

    st.markdown("#### Access Settings")
    
    # --- DYNAMIC UI SECTION (No st.form used here so dropdowns react instantly) ---
    
    roles = ['superadmin', 'district', 'block', 'department']
    current_role_index = roles.index(selected_user['role']) if selected_user['role'] in roles else 0
    new_role = st.selectbox("Role", roles, index=current_role_index)
    
    # Fetch Master Data for dropdowns
    districts = supabase.table("districts").select("id, district_name").eq("active", True).execute().data
    blocks = supabase.table("blocks").select("id, block_name, district_id").eq("active", True).execute().data
    departments = supabase.table("departments").select("id, department_name").eq("active", True).execute().data

    new_district = None
    new_block = None
    new_dept = None

    # Show District dropdown for roles that require it
    if new_role in ['district', 'block', 'department']:
        dist_names = [d['district_name'] for d in districts]
        
        # Safely find the current district index to prevent StopIteration crashes
        current_dist_id = selected_user.get('district_id')
        dist_idx = 0
        if current_dist_id:
            for i, d in enumerate(districts):
                if d['id'] == current_dist_id:
                    dist_idx = i
                    break
        
        sel_dist_name = st.selectbox("District", dist_names, index=dist_idx if dist_idx < len(dist_names) else 0)
        new_district = next(d['id'] for d in districts if d['district_name'] == sel_dist_name)

    # Show Block dropdown ONLY if role is block, and filter it by the selected District
    if new_role == 'block' and new_district:
        filtered_blocks = [b for b in blocks if b['district_id'] == new_district]
        
        if filtered_blocks:
            block_names = [b['block_name'] for b in filtered_blocks]
            
            current_block_id = selected_user.get('block_id')
            block_idx = 0
            if current_block_id:
                for i, b in enumerate(filtered_blocks):
                    if b['id'] == current_block_id:
                        block_idx = i
                        break
                        
            sel_block_name = st.selectbox("Block", block_names, index=block_idx if block_idx < len(block_names) else 0)
            new_block = next(b['id'] for b in filtered_blocks if b['block_name'] == sel_block_name)
        else:
            st.warning("⚠️ No blocks found for this district. Please check Master Data.")

    # Show Department dropdown ONLY if role is department
    if new_role == 'department':
        dept_names = [d['department_name'] for d in departments]
        
        current_dept_id = selected_user.get('department_id')
        dept_idx = 0
        if current_dept_id:
            for i, d in enumerate(departments):
                if d['id'] == current_dept_id:
                    dept_idx = i
                    break
                    
        sel_dept_name = st.selectbox("Department", dept_names, index=dept_idx if dept_idx < len(dept_names) else 0)
        new_dept = next(d['id'] for d in departments if d['department_name'] == sel_dept_name)

    active = st.checkbox("Active Account", value=selected_user.get('active', True))
    
    # Submit Action
    if st.button("Update User Profile", type="primary"):
        updates = {
            "role": new_role,
            "active": active,
            "district_id": new_district if new_role in ['district', 'block', 'department'] else None,
            "block_id": new_block if new_role == 'block' else None,
            "department_id": new_dept if new_role == 'department' else None
        }

        old = {k: selected_user.get(k) for k in updates}
        
        try:
            supabase.table("users").update(updates).eq("id", user_id).execute()
            log_action(user, "UPDATE", "users", user_id, old_vals=old, new_vals=updates)
            st.success(f"✅ User {selected_user['full_name']} updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to update user. Database Error: {str(e)}")
