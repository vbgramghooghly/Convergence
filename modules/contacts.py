import streamlit as st
import pandas as pd
import base64
import io
from utils.db import get_supabase
from auth.auth import get_current_user

def inject_tab_css():
    """Injects modern, trendy CSS to elevate the UI of Streamlit tabs."""
    st.markdown("""
        <style>
        div[data-testid="stTabs"] button[role="tab"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 30px; 
            padding: 8px 20px;
            margin-right: 10px;
            font-weight: 600;
            color: #4B5563;
            transition: all 0.25s ease-in-out;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stTabs"] button[role="tab"]:hover {
            background-color: #F3F4F6;
            border-color: #D1D5DB;
            color: #111827;
            transform: translateY(-1px);
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background-color: #1F77B4 !important;
            color: white !important;
            border-color: #1F77B4 !important;
            box-shadow: 0 4px 10px -2px rgba(31, 119, 180, 0.4) !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none; }
        div[data-testid="stTabs"] [data-baseweb="tab-panel"] { padding-top: 25px; }
        </style>
    """, unsafe_allow_html=True)


def show():
    inject_tab_css()
    st.markdown("<h1 style='color: #1F77B4;'>📇 Official Contact Directory</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()
    user = get_current_user()

    # 1. Fetch Master Data
    designations = supabase.table("designations").select("id, designation_name").eq("active", True).execute().data
    districts = supabase.table("districts").select("id, district_name").execute().data
    blocks = supabase.table("blocks").select("id, block_name, district_id").execute().data
    departments = supabase.table("departments").select("id, department_name").eq("active", True).execute().data
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").eq("active", True).execute().data

    desig_dict = {d['designation_name']: d['id'] for d in designations}
    dist_dict = {d['district_name']: d['id'] for d in districts}
    block_dict = {b['block_name']: b['id'] for b in blocks}
    dept_dict = {d['department_name']: d['id'] for d in departments}

    OFFICE_LEVELS = ["State / Department", "District", "Sub Division", "Block", "Gram Panchayat"]
    COMMITTEE_ROLES = ["None", "Chairperson", "Co-Chairperson", "Member-Convener", "Member"]

    # 2. Fetch ALL Contacts with Hierarchical Joins
    query = supabase.table("contacts").select("*, designations(designation_name), districts(district_name), blocks(block_name), departments(department_name), department_wings(wing_name, entity_type)")
    contacts_data = query.execute().data
    df = pd.DataFrame(contacts_data)

    # 3. Tabbed Interface for Cleaner UX
    tab1, tab2 = st.tabs(["📋 View Directory List", "🔄 Profile Update & Transfer Module"])

    # ==============================================================
    # TAB 1: DIRECTORY LIST & EXPORT
    # ==============================================================
    with tab1:
        st.subheader("Official Directory & Statutory Roles")
        st.caption("Comprehensive list of all statutory officers, committee members, nodal points, and department heads.")
        
        if not df.empty:
            df['Designation'] = df['designations'].apply(lambda x: x.get('designation_name', 'Unassigned') if isinstance(x, dict) else 'Unassigned')
            df['District'] = df['districts'].apply(lambda x: x.get('district_name', 'District Office') if isinstance(x, dict) else 'District Office')
            df['Block'] = df['blocks'].apply(lambda x: x.get('block_name', 'N/A') if isinstance(x, dict) else 'N/A')
            df['Parent Dept'] = df['departments'].apply(lambda x: x.get('department_name', 'General Administration') if isinstance(x, dict) else 'General Administration')
            
            def format_wing(x):
                if isinstance(x, dict) and x.get('wing_name'):
                    return f"{x.get('wing_name')} ({x.get('entity_type', 'Wing')})"
                return "Direct Parent Dept"
                
            df['Wing / Scheme'] = df['department_wings'].apply(format_wing)
            
            def format_comm_blocks(block_ids):
                if not isinstance(block_ids, list) or not block_ids: return "N/A"
                names = [b_name for b_name, b_id in block_dict.items() if b_id in block_ids]
                return ", ".join(names)

            # Safely handle new columns if data is empty or missing
            for col in ['office_level', 'sub_division', 'office', 'sub_office', 'district_committee_role', 'block_committee_role', 'committee_blocks']:
                if col not in df.columns:
                    df[col] = None
            
            df['Tagged Comm. Blocks'] = df['committee_blocks'].apply(format_comm_blocks)
            df['Dist. Role'] = df['district_committee_role'].fillna('None')
            df['Block Role'] = df['block_committee_role'].fillna('None')
            
            display_df = df[['full_name', 'office_level', 'Designation', 'Parent Dept', 'Wing / Scheme', 'Dist. Role', 'Block Role', 'Tagged Comm. Blocks', 'contact_number', 'email_id']]
            display_df.columns = ['Name', 'Posting Level', 'Designation', 'Parent Dept', 'Wing / Scheme', 'Dist. Committee', 'Block Committee', 'Tagged Blocks', 'Contact Number', 'Email ID']
            
            col_dl, col_pr, _ = st.columns([1.5, 1.8, 6.7])
            
            buffer = io.BytesIO()
            try:
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Contacts')
                excel_data = buffer.getvalue()
                col_dl.download_button(label="📥 Download Excel", data=excel_data, file_name="official_contact_directory.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            except Exception:
                csv = display_df.to_csv(index=False).encode('utf-8')
                col_dl.download_button(label="📥 Download CSV", data=csv, file_name="official_contact_directory.csv", mime="text/csv", use_container_width=True)
            
            html_table = display_df.to_html(index=False)
            printable_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Official Contact Directory</title><style>body {{ font-family: Arial, sans-serif; padding: 20px; font-size: 11px; color: #333; }} h2 {{ text-align: center; color: #1F77B4; border-bottom: 2px solid #1F77B4; padding-bottom: 10px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }} th, td {{ border: 1px solid #dddddd; padding: 6px; text-align: left; }} th {{ background-color: #f2f2f2; color: #000; }} @page {{ size: A4 landscape; margin: 15mm; }} @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}</style></head><body onload="window.print()"><div class="no-print" style="text-align: center; margin-bottom: 20px; background-color: #f8f9fa; padding: 15px; border-radius: 8px;"><button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: #1F77B4; color: white; border: none; border-radius: 4px;">🖨️ Print or Save as PDF</button></div><h2>Official Contact Directory & Statutory Roles</h2>{html_table}</body></html>"""
            col_pr.download_button(label="🖨️ Download Printable Document", data=printable_html, file_name="Contact_Directory_Print.html", mime="text/html", use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No contact records found. Please update profile information in the next tab.")

    # ==============================================================
    # TAB 2: UPDATE & TRANSFER MODULE
    # ==============================================================
    with tab2:
        if user['role'] == 'superadmin':
            st.subheader("🛠️ User Management & Handover (Superadmin)")
            all_users = supabase.table("users").select("id, full_name, district_id, block_id, role").execute().data
            user_options = {u['id']: f"{u['full_name']} ({u['role'].upper()})" for u in all_users}
            target_user_id = st.selectbox("Select User Profile to Manage", options=list(user_options.keys()), format_func=lambda x: user_options[x])
            
            target_user_info = next((u for u in all_users if u['id'] == target_user_id), {})
            target_district_id = target_user_info.get('district_id')
            target_block_id = target_user_info.get('block_id')
            target_default_name = target_user_info.get('full_name', '')
            
        elif user['role'] == 'district':
            st.subheader("🛠️ Manage District Contacts (District Admin)")
            dist_users = supabase.table("users").select("id, full_name, district_id, block_id, role").eq("district_id", user['district_id']).execute().data
            user_options = {u['id']: f"{u['full_name']} ({u['role'].upper()})" for u in dist_users}
            target_user_id = st.selectbox("Select User Profile to Manage", options=list(user_options.keys()), format_func=lambda x: user_options[x])
            
            target_user_info = next((u for u in dist_users if u['id'] == target_user_id), {})
            target_district_id = target_user_info.get('district_id')
            target_block_id = target_user_info.get('block_id')
            target_default_name = target_user_info.get('full_name', '')
            
        else:
            st.subheader("🔄 Update Profile / Officer Handover")
            st.caption("If an officer is transferred, simply update the Name and Phone Number below to hand over this login profile to the new incumbent. The statutory roles remain permanently linked to the profile.")
            target_user_id = user['id']
            target_district_id = user.get('district_id')
            target_block_id = user.get('block_id')
            target_default_name = user.get('full_name', '')

        # Fetch existing record for the targeted user login
        user_contact = supabase.table("contacts").select("*").eq("user_id", target_user_id).execute().data
        existing_record = user_contact[0] if user_contact else {}

        with st.form("update_contact_form"):
            st.markdown("#### 1. Official Details")
            col1, col2 = st.columns(2)
            name = col1.text_input("Full Name of Incumbent Officer", value=existing_record.get('full_name', target_default_name))
            
            curr_desig_id = existing_record.get('designation_id')
            curr_desig_name = next((k for k, v in desig_dict.items() if v == curr_desig_id), list(desig_dict.keys())[0] if desig_dict else "")
            desig_idx = list(desig_dict.keys()).index(curr_desig_name) if curr_desig_name in desig_dict else 0
            sel_desig = col2.selectbox("Designation", options=list(desig_dict.keys()) if desig_dict else ["None"], index=desig_idx)

            st.markdown("#### 2. Department & Level Hierarchy")
            col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
            
            curr_lvl = existing_record.get('office_level', 'District')
            lvl_idx = OFFICE_LEVELS.index(curr_lvl) if curr_lvl in OFFICE_LEVELS else 1
            sel_lvl = col_l1.selectbox("Posting Level", OFFICE_LEVELS, index=lvl_idx)
            
            sub_div_val = existing_record.get('sub_division', '')
            if sel_lvl == "Sub Division":
                sel_sub_div = col_l2.text_input("Sub Division Name*", value=sub_div_val)
            else:
                sel_sub_div = col_l2.text_input("Sub Division Name (If Applicable)", value=sub_div_val)

            curr_dept_id = existing_record.get('department_id')
            curr_dept_name = next((k for k, v in dept_dict.items() if v == curr_dept_id), list(dept_dict.keys())[0] if dept_dict else "")
            dept_idx = list(dept_dict.keys()).index(curr_dept_name) if curr_dept_name in dept_dict else 0
            sel_parent_dept = col_l3.selectbox("Parent Department", options=list(dept_dict.keys()) if dept_dict else ["None"], index=dept_idx)
            selected_parent_id = dept_dict.get(sel_parent_dept)
            
            valid_wings = [w for w in wings if w['department_id'] == selected_parent_id]
            wing_options = {"Directly under Parent Department": None}
            for w in valid_wings:
                wing_options[f"{w['wing_name']} ({w['entity_type']})"] = w['id']
                
            curr_wing_id = existing_record.get('wing_id')
            curr_wing_name = next((k for k, v in wing_options.items() if v == curr_wing_id), list(wing_options.keys())[0])
            wing_idx = list(wing_options.keys()).index(curr_wing_name) if curr_wing_name in wing_options else 0
            sel_wing = st.selectbox("Specific Wing / Scheme / Parastatal", options=list(wing_options.keys()), index=wing_idx)

            st.markdown("#### 3. Contact & Location Information")
            col3, col4, col5 = st.columns(3)
            contact_no = col3.text_input("Mobile Number", value=existing_record.get('contact_number', ''))
            whatsapp_no = col4.text_input("WhatsApp Number", value=existing_record.get('whatsapp_number', ''))
            email = col5.text_input("Official Email ID", value=existing_record.get('email_id', ''))
            
            col6, col7 = st.columns(2)
            office = col6.text_input("Office Name / Address", value=existing_record.get('office', ''))
            sub_office = col7.text_input("Sub Office / Room No.", value=existing_record.get('sub_office', ''))

            # --- NEW: STATUTORY COMMITTEE ROLES ---
            st.markdown("#### 4. Statutory Committee Memberships")
            st.caption("Link this profile to specific statutory committees. If a sub-divisional officer is a member of multiple blocks, tag them below.")
            
            col_c1, col_c2 = st.columns(2)
            
            curr_dist_role = existing_record.get('district_committee_role', 'None') or 'None'
            dist_role_idx = COMMITTEE_ROLES.index(curr_dist_role) if curr_dist_role in COMMITTEE_ROLES else 0
            sel_dist_role = col_c1.selectbox("District Committee Role", COMMITTEE_ROLES, index=dist_role_idx)

            curr_block_role = existing_record.get('block_committee_role', 'None') or 'None'
            block_role_idx = COMMITTEE_ROLES.index(curr_block_role) if curr_block_role in COMMITTEE_ROLES else 0
            sel_block_role = col_c2.selectbox("Block Committee Role", COMMITTEE_ROLES, index=block_role_idx)
            
            curr_comm_blocks = existing_record.get('committee_blocks') or []
            default_blocks = [b for b in list(block_dict.keys()) if block_dict[b] in curr_comm_blocks]
            sel_comm_blocks = st.multiselect("Tagged Blocks for Committee Membership (Select multiple if applicable)", options=list(block_dict.keys()), default=default_blocks)

            if st.form_submit_button("Save Details / Complete Handover", type="primary"):
                if sel_lvl == "Sub Division" and not sel_sub_div.strip():
                    st.error("⚠️ Sub Division Name is required when 'Sub Division' level is selected.")
                else:
                    comm_block_ids = [block_dict[b] for b in sel_comm_blocks]

                    payload = {
                        "user_id": target_user_id,
                        "full_name": name,
                        "designation_id": desig_dict.get(sel_desig),
                        "department_id": selected_parent_id,
                        "wing_id": wing_options.get(sel_wing), 
                        "office_level": sel_lvl,
                        "sub_division": sel_sub_div.strip() if sel_sub_div.strip() else None,
                        "contact_number": contact_no,
                        "whatsapp_number": whatsapp_no,
                        "email_id": email,
                        "office": office if office.strip() else None,
                        "sub_office": sub_office if sub_office.strip() else None,
                        "district_committee_role": sel_dist_role if sel_dist_role != "None" else None,
                        "block_committee_role": sel_block_role if sel_block_role != "None" else None,
                        "committee_blocks": comm_block_ids,
                        "district_id": target_district_id,
                        "block_id": target_block_id,
                        "active": True
                    }

                    try:
                        if existing_record:
                            supabase.table("contacts").update(payload).eq("id", existing_record['id']).execute()
                        else:
                            supabase.table("contacts").insert(payload).execute()
                            
                        # Automatically update the core 'users' table name to match the new incumbent
                        supabase.table("users").update({"full_name": name}).eq("id", target_user_id).execute()

                        st.success("✅ Contact Record and Statutory Mapping updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving contact details: {e}")
