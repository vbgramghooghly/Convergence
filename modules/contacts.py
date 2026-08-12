import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import get_current_user

def show():
    st.markdown("<h1 style='color: #1F77B4;'>📇 Official Contact Directory</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()

    # 1. Fetch Master Designations, Districts, Blocks
    designations = supabase.table("designations").select("id, designation_name").eq("active", True).execute().data
    districts = supabase.table("districts").select("id, district_name").execute().data
    blocks = supabase.table("blocks").select("id, block_name, district_id").execute().data

    desig_dict = {d['designation_name']: d['id'] for d in designations}
    dist_dict = {d['district_name']: d['id'] for d in districts}
    block_dict = {b['block_name']: b['id'] for b in blocks}

    # 2. Fetch Contacts with Joins
    query = supabase.table("contacts").select("*, designations(designation_name), districts(district_name), blocks(block_name)")
    
    # Role-based filtering
    if user['role'] == 'block':
        query = query.eq("block_id", user['block_id'])
    elif user['role'] == 'district':
        query = query.eq("district_id", user['district_id'])
    
    contacts_data = query.execute().data
    df = pd.DataFrame(contacts_data)

    # 3. Display Directory Table
    st.subheader("📋 Directory List")
    if not df.empty:
        df['Designation'] = df['designations'].apply(lambda x: x['designation_name'] if isinstance(x, dict) else 'Unassigned')
        df['District'] = df['districts'].apply(lambda x: x['district_name'] if isinstance(x, dict) else 'District Office')
        df['Block'] = df['blocks'].apply(lambda x: x['block_name'] if isinstance(x, dict) else 'N/A')
        
        display_df = df[['full_name', 'Designation', 'contact_number', 'whatsapp_number', 'email_id', 'District', 'Block']]
        display_df.columns = ['Name', 'Designation', 'Contact Number', 'WhatsApp Number', 'Email ID', 'District', 'Block']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No contact records found. Please update your profile information below.")

    st.markdown("---")
    st.subheader("✏️ Update My Contact Information")

    # Check if logged-in user already has a contact record
    user_contact = supabase.table("contacts").select("*").eq("user_id", user['id']).execute().data
    existing_record = user_contact[0] if user_contact else {}

    with st.form("update_contact_form"):
        col1, col2 = st.columns(2)
        
        name = col1.text_input("Full Name", value=existing_record.get('full_name', user.get('full_name', '')))
        
        # Designation dropdown controlled by Superadmin master data
        curr_desig_id = existing_record.get('designation_id')
        curr_desig_name = next((k for k, v in desig_dict.items() if v == curr_desig_id), list(desig_dict.keys())[0] if desig_dict else "")
        desig_idx = list(desig_dict.keys()).index(curr_desig_name) if curr_desig_name in desig_dict else 0
        
        sel_desig = col2.selectbox("Designation", options=list(desig_dict.keys()) if desig_dict else ["No Designations Found"], index=desig_idx if desig_dict else 0)

        col3, col4, col5 = st.columns(3)
        contact_no = col3.text_input("Contact Number", value=existing_record.get('contact_number', ''))
        whatsapp_no = col4.text_input("WhatsApp Number", value=existing_record.get('whatsapp_number', ''))
        email = col5.text_input("Email ID", value=existing_record.get('email_id', ''))

        # Auto-assign district and block based on user profile context
        assigned_district_id = user.get('district_id')
        assigned_block_id = user.get('block_id')

        submitted = st.form_submit_button("Save / Update Contact Details", type="primary")

        if submitted:
            payload = {
                "user_id": user['id'],
                "full_name": name,
                "designation_id": desig_dict.get(sel_desig) if desig_dict else None,
                "contact_number": contact_no,
                "whatsapp_number": whatsapp_no,
                "email_id": email,
                "district_id": assigned_district_id,
                "block_id": assigned_block_id,
                "active": True
            }

            if existing_record:
                # Update existing record
                supabase.table("contacts").update(payload).eq("id", existing_record['id']).execute()
            else:
                # Insert new record for this user login
                supabase.table("contacts").insert(payload).execute()

            st.success("✅ Contact information updated successfully!")
            st.rerun()
