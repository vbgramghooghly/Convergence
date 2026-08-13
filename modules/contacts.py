import streamlit as st
import pandas as pd
import base64
import io
import json
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

    # 2. Fetch Contacts Scoped by District Visibility
    query = supabase.table("contacts").select(
        "*, designations(designation_name), districts(district_name), blocks(block_name), departments(department_name), department_wings(wing_name, entity_type)"
    )
    
    # Filter directory to only show contacts within the user's District (all roles except Superadmin)
    if user['role'] in ['district', 'block', 'department'] and user.get('district_id'):
        query = query.eq("district_id", user['district_id'])
        
    contacts_data = query.execute().data
    df = pd.DataFrame(contacts_data)

    # 3. Tabbed Interface
    tab1, tab2 = st.tabs(["📋 View Directory List", "🔄 Profile Update & Transfer Module"])

    # ==============================================================
    # TAB 1: DIRECTORY LIST & EXPORT (Visible to All within District)
    # ==============================================================
    with tab1:
        st.subheader("Official District Directory & Statutory Roles")
        st.caption("Comprehensive list of all departmental officers, statutory members, and nodal points within your jurisdiction.")
        
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
                if not block_ids: return "N/A"
                if isinstance(block_ids, str):
                    try:
                        block_ids = json.loads(block_ids)
                    except:
                        return "N/A"
                if not isinstance(block_ids, list) or not block_ids: return "N/A"
                
                str_block_ids = [str(x) for x in block_ids]
                names = [b_name for b_name, b_id in block_dict.items() if str(b_id) in str_block_ids]
                return ", ".join(names) if names else "N/A"

            for col in ['office_level', 'sub_division', 'office', 'sub_office', 'district_committee_role', 'block_committee_role', 'tagged_blocks']:
                if col not in df.columns:
                    df[col] = None
            
            df['Tagged Comm. Blocks'] = df['tagged_blocks'].apply(format_comm_blocks)
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
            st.info("No contact records found for your district jurisdiction.")

    # ==============================================================
    # TAB 2: UPDATE & PROFILE HANDOVER MODULE
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
            st.subheader("🛠️ Manage District Contacts & Statutory Roles (District Admin)")
            dist_users = supabase.table("users").select("id, full_name, district_id, block_id, role").eq("district_id", user['district_id']).execute().data
            user_options = {u['id']: f"{u['full_name']} ({u['role'].upper()})" for u in dist_users}
            target_user_id = st.selectbox("Select User Profile to Manage", options=list(user_options.keys()), format_func=lambda x: user_options[x])
            
            target_user_info = next((u for u in dist_users if u['id'] == target_user_id), {})
            target_district_id = target_user_info.get('district_id')
            target_block_id = target_user_info.get('block_id')
            target_default_name = target_user_info.get('full_name', '')

        elif user['role'] == 'block':
            st.subheader("🛠️ Manage Block Contacts & Statutory Roles (Block Admin)")
            block_users = supabase.table("users").select("id, full_name, district_id, block_id, role").eq("block_id", user['block_id']).execute().data
            user_options = {u['id']: f"{u['full_name']} ({u['role'].upper()})" for u in block_users}
            target_user_id = st.selectbox("Select User Profile to Manage", options=list(user_options.keys()), format_func=lambda x: user_options[x])
            
            target_user_info = next((u for u in block_users if u['id'] == target_user_id), {})
            target_district_id = target_user_info.get('district_id')
            target_block_id = target_user_info.get('block_id')
            target_default_name = target_user_info.get('full_name', '')
            
        else: # Department Role
            st.subheader("🔄 Department Official Profile Update")
            st.caption("Update your personal contact details, office location, and designation. Statutory committee roles are managed directly by District or Block administrators.")
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
            
            name_val = existing_record.get('full_name') or target_default_name
            name = col1.text_input("Full Name of Incumbent Officer", value=name_val)
            
            curr_desig_id = existing_record.get('designation_id')
            curr_desig_name = next((k for k, v in desig_dict.items() if v == curr_desig_id), list(desig_dict.keys())[0] if desig_dict else "")
            desig_idx = list(desig_dict.keys()).index(curr_desig_name) if curr_desig_name in desig_dict else 0
            sel_desig = col2.selectbox("Designation", options=list(desig_dict.keys()) if desig_dict else ["None"], index=desig_idx)

            st.markdown("#### 2. Department & Level Hierarchy")
            col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
            
            curr_lvl = existing_record.get('office_level') or 'District'
            lvl_idx = OFFICE_LEVELS.index(curr_lvl) if curr_lvl in OFFICE_LEVELS else 1
            sel_lvl = col_l1.selectbox("Posting Level", OFFICE_LEVELS, index=lvl_idx)
            
            # SAFEGUARD: Provide fallback `or ''` so it's guaranteed to be a string
            sub_div_val = existing_record.get('sub_division') or ''
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
            # SAFEGUARD: Convert None to ''
            contact_no = col3.text_input("Mobile Number", value=existing_record.get('contact_number') or '')
            whatsapp_no = col4.text_input("WhatsApp Number", value=existing_record.get('whatsapp_number') or '')
            email = col5.text_input("Official Email ID", value=existing_record.get('email_id') or '')
            
            col6, col7 = st.columns(2)
            # SAFEGUARD: Convert None to ''
            office = col6.text_input("Office Name / Address", value=existing_record.get('office') or '')
            sub_office = col7.text_input("Sub Office / Room No.", value=existing_record.get('sub_office') or '')

            # --- STATUTORY COMMITTEE ROLES (RESTRICTED MAPPING) ---
            st.markdown("#### 4. Statutory Committee Memberships")
            
            if user['role'] == 'department':
                st.caption("🔒 *Committee roles are managed exclusively by District & Block Administrations.*")
            elif user['role'] == 'district':
                st.caption("🔒 *As a District Admin, you can only map District Roles. Block Roles are managed by Block Admins.*")
            elif user['role'] == 'block':
                st.caption("🔒 *As a Block Admin, you can only map Block Roles. District Roles are managed by District Admins.*")
            else:
                st.caption("Link this official profile to statutory committees. District/Block roles enable targeted tracking.")
            
            col_c1, col_c2 = st.columns(2)
            
            # Cross-Validation: Check User Authority vs Target Posting Level
            allow_dist = (user['role'] in ['superadmin', 'district']) and (sel_lvl in ["State / Department", "District", "Sub Division"])
            allow_block = (user['role'] in ['superadmin', 'block']) and (sel_lvl in ["District", "Sub Division", "Block", "Gram Panchayat"])

            curr_dist_role = existing_record.get('district_committee_role') or 'None'
            dist_role_idx = COMMITTEE_ROLES.index(curr_dist_role) if curr_dist_role in COMMITTEE_ROLES else 0
            sel_dist_role = col_c1.selectbox("District Committee Role", COMMITTEE_ROLES, index=dist_role_idx, disabled=not allow_dist)
            final_dist_role = sel_dist_role if allow_dist else curr_dist_role

            curr_block_role = existing_record.get('block_committee_role') or 'None'
            block_role_idx = COMMITTEE_ROLES.index(curr_block_role) if curr_block_role in COMMITTEE_ROLES else 0
            sel_block_role = col_c2.selectbox("Block Committee Role", COMMITTEE_ROLES, index=block_role_idx, disabled=not allow_block)
            final_block_role = sel_block_role if allow_block else curr_block_role
            
            # Robust parsing for JSON/String arrays from Supabase
            curr_comm_blocks = existing_record.get('tagged_blocks') or []
            if isinstance(curr_comm_blocks, str):
                try:
                    curr_comm_blocks = json.loads(curr_comm_blocks)
                except:
                    curr_comm_blocks = []
            
            curr_comm_blocks = [str(x) for x in curr_comm_blocks]
            default_blocks = [b for b in list(block_dict.keys()) if str(block_dict[b]) in curr_comm_blocks]
            
            if not default_blocks and target_block_id and final_block_role != "None":
                primary_block_name = next((b_name for b_name, b_id in block_dict.items() if b_id == target_block_id), None)
                if primary_block_name:
                    default_blocks = [primary_block_name]
            
            sel_comm_blocks = st.multiselect(
                "Tagged Blocks for Committee Membership", 
                options=list(block_dict.keys()), 
                default=default_blocks,
                disabled=not allow_block
            )

            if st.form_submit_button("Save Profile Details", type="primary"):
                # Safe casting to avoid NoneType issues
                sel_sub_div = sel_sub_div or ""
                office = office or ""
                sub_office = sub_office or ""
                
                if sel_lvl == "Sub Division" and not sel_sub_div.strip():
                    st.error("⚠️ Sub Division Name is required when 'Sub Division' level is selected.")
                elif allow_block and final_block_role != "None" and not sel_comm_blocks:
                    st.error("⚠️ Please tag at least one block for the assigned Block Committee Role.")
                else:
                    # Safely retain existing block tags if the user does not have permission to alter block data
                    comm_block_ids = [block_dict[b] for b in sel_comm_blocks] if allow_block else [block_dict[b] for b in default_blocks]

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
                        "office": office.strip() if office.strip() else None,
                        "sub_office": sub_office.strip() if sub_office.strip() else None,
                        "district_committee_role": final_dist_role if final_dist_role != "None" else None,
                        "block_committee_role": final_block_role if final_block_role != "None" else None,
                        "tagged_blocks": comm_block_ids,
                        "district_id": target_district_id,
                        "block_id": target_block_id,
                        "active": True
                    }

                    try:
                        if existing_record:
                            supabase.table("contacts").update(payload).eq("id", existing_record['id']).execute()
                        else:
                            supabase.table("contacts").insert(payload).execute()
                            
                        # Automatically update core 'users' full_name
                        supabase.table("users").update({"full_name": name}).eq("id", target_user_id).execute()

                        st.success("✅ Profile details updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving contact details: {e}")
