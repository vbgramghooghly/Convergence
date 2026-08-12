import streamlit as st
import pandas as pd
import base64
import io
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

    # 2. Fetch ALL Contacts (Visibility open to everyone so anyone can find any number)
    query = supabase.table("contacts").select("*, designations(designation_name), districts(district_name), blocks(block_name)")
    contacts_data = query.execute().data
    df = pd.DataFrame(contacts_data)

    # 3. Display Directory Table & Export Options
    st.subheader("📋 Directory List")
    
    if not df.empty:
        # Format the fetched nested JSON into clean columns
        df['Designation'] = df['designations'].apply(lambda x: x['designation_name'] if isinstance(x, dict) else 'Unassigned')
        df['District'] = df['districts'].apply(lambda x: x['district_name'] if isinstance(x, dict) else 'District Office')
        df['Block'] = df['blocks'].apply(lambda x: x['block_name'] if isinstance(x, dict) else 'N/A')
        
        # Ensure new columns exist in dataframe to prevent KeyError
        if 'office' not in df.columns: df['office'] = ''
        if 'sub_office' not in df.columns: df['sub_office'] = ''
        
        display_df = df[['full_name', 'Designation', 'office', 'sub_office', 'contact_number', 'whatsapp_number', 'email_id', 'District', 'Block']]
        display_df.columns = ['Name', 'Designation', 'Office', 'Sub Office', 'Contact Number', 'WhatsApp Number', 'Email ID', 'District', 'Block']
        
        # Export & Print Buttons
        col_dl, col_pr, _ = st.columns([1.5, 1.8, 6.7])
        
        # Download button (Excel)
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name='Contacts')
            excel_data = buffer.getvalue()
            
            col_dl.download_button(
                label="📥 Download Excel",
                data=excel_data,
                file_name="official_contact_directory.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception:
            csv = display_df.to_csv(index=False).encode('utf-8')
            col_dl.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="official_contact_directory.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # Print / PDF button (Generates a clean HTML file formatted for A4 Landscape)
        html_table = display_df.to_html(index=False)
        printable_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Official Contact Directory</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; font-size: 12px; color: #333; }}
                h2 {{ text-align: center; color: #1F77B4; border-bottom: 2px solid #1F77B4; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #dddddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; color: #000; }}
                /* Force A4 Landscape formatting for Print/PDF */
                @page {{ size: A4 landscape; margin: 15mm; }}
                @media print {{
                    .no-print {{ display: none; }}
                    body {{ padding: 0; }}
                }}
            </style>
        </head>
        <body onload="window.print()">
            <div class="no-print" style="text-align: center; margin-bottom: 20px; background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
                <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: #1F77B4; color: white; border: none; border-radius: 4px;">🖨️ Print or Save as PDF</button>
                <p style="margin-top: 10px; color: #555;">If the print dialog doesn't open automatically, press <b>Ctrl + P</b>.</p>
            </div>
            <h2>Official Contact Directory - VB-G RAM G Convergence</h2>
            {html_table}
        </body>
        </html>
        """
        
        # Download Printable HTML instead of opening in a blocked new tab
        col_pr.download_button(
            label="🖨️ Download Printable Document",
            data=printable_html,
            file_name="Contact_Directory_Print.html",
            mime="text/html",
            use_container_width=True
        )

        st.caption("💡 *Tip: For a perfect A4 PDF, click 'Download Printable Document', open the downloaded file, and click 'Save as PDF'.*")

        # Show the actual dataframe
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No contact records found. Please update profile information below.")

    # 4. Update Profile Form (Role-Based Editing)
    st.markdown("---")
    
    # EDITING RESTRICTIONS
    if user['role'] == 'superadmin':
        st.subheader("🛠️ Manage Any Contact (Superadmin)")
        all_users = supabase.table("users").select("id, full_name, district_id, block_id, role").execute().data
        user_options = {u['id']: f"{u['full_name']} ({u['role'].upper()})" for u in all_users}
        target_user_id = st.selectbox("Select User to Edit", options=list(user_options.keys()), format_func=lambda x: user_options[x])
        
        target_user_info = next((u for u in all_users if u['id'] == target_user_id), {})
        target_district_id = target_user_info.get('district_id')
        target_block_id = target_user_info.get('block_id')
        target_default_name = target_user_info.get('full_name', '')
        
    elif user['role'] == 'district':
        st.subheader("🛠️ Manage District Contacts (District Admin)")
        # District admins can edit anyone inside their district
        dist_users = supabase.table("users").select("id, full_name, district_id, block_id, role").eq("district_id", user['district_id']).execute().data
        user_options = {u['id']: f"{u['full_name']} ({u['role'].upper()})" for u in dist_users}
        target_user_id = st.selectbox("Select User to Edit", options=list(user_options.keys()), format_func=lambda x: user_options[x])
        
        target_user_info = next((u for u in dist_users if u['id'] == target_user_id), {})
        target_district_id = target_user_info.get('district_id')
        target_block_id = target_user_info.get('block_id')
        target_default_name = target_user_info.get('full_name', '')
        
    else:
        st.subheader("✏️ Update My Contact Information")
        # Block and Department users can ONLY edit themselves
        target_user_id = user['id']
        target_district_id = user.get('district_id')
        target_block_id = user.get('block_id')
        target_default_name = user.get('full_name', '')

    # Check if target user already has a contact record
    user_contact = supabase.table("contacts").select("*").eq("user_id", target_user_id).execute().data
    existing_record = user_contact[0] if user_contact else {}

    with st.form("update_contact_form"):
        col1, col2 = st.columns(2)
        
        name = col1.text_input("Full Name", value=existing_record.get('full_name', target_default_name))
        
        # Designation dropdown controlled by Master data
        curr_desig_id = existing_record.get('designation_id')
        curr_desig_name = next((k for k, v in desig_dict.items() if v == curr_desig_id), list(desig_dict.keys())[0] if desig_dict else "")
        desig_idx = list(desig_dict.keys()).index(curr_desig_name) if curr_desig_name in desig_dict else 0
        
        sel_desig = col2.selectbox("Designation", options=list(desig_dict.keys()) if desig_dict else ["No Designations Found"], index=desig_idx if desig_dict else 0)

        col3, col4, col5 = st.columns(3)
        contact_no = col3.text_input("Contact Number", value=existing_record.get('contact_number', ''))
        whatsapp_no = col4.text_input("WhatsApp Number", value=existing_record.get('whatsapp_number', ''))
        email = col5.text_input("Email ID", value=existing_record.get('email_id', ''))
        
        # Row for Office and Sub Office (Optional)
        col6, col7 = st.columns(2)
        office = col6.text_input("Office (Optional)", value=existing_record.get('office', ''))
        sub_office = col7.text_input("Sub Office (Optional)", value=existing_record.get('sub_office', ''))

        submitted = st.form_submit_button("Save / Update Contact Details", type="primary")

        if submitted:
            payload = {
                "user_id": target_user_id,
                "full_name": name,
                "designation_id": desig_dict.get(sel_desig) if desig_dict else None,
                "contact_number": contact_no,
                "whatsapp_number": whatsapp_no,
                "email_id": email,
                "office": office if office.strip() else None,
                "sub_office": sub_office if sub_office.strip() else None,
                "district_id": target_district_id,
                "block_id": target_block_id,
                "active": True
            }

            if existing_record:
                # Update existing record
                supabase.table("contacts").update(payload).eq("id", existing_record['id']).execute()
            else:
                # Insert new record for this user
                supabase.table("contacts").insert(payload).execute()

            st.success("✅ Contact information updated successfully!")
            st.rerun()
