import base64
import io
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from auth.auth import get_current_user, require_role
from utils.db import get_supabase
from utils.theme import apply_global_theme

def render_print_preview(html_content):
    wrapped_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Print Document</title>
        <style>
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0 !important; margin: 0 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                .page-break {{ page-break-after: always; }}
            }}
            body {{ font-family: Arial, sans-serif; padding: 20px; font-size: 11px; color: #000; line-height: 1.5; }}
            .print-toolbar {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; text-align: center; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .print-btn {{ padding: 10px 24px; font-size: 16px; font-weight: bold; background-color: #0F4C81; color: white; border: none; border-radius: 6px; cursor: pointer; transition: background 0.3s; }}
            .print-btn:hover {{ background-color: #0b3960; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }}
            th, td {{ border: 1px solid #000; padding: 6px; text-align: left; font-size: 10px; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="no-print print-toolbar">
            <h4 style="margin-top: 0; color: #333; font-family: Arial, sans-serif;">🖨️ Print Preview – Official Contact Directory</h4>
            <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
        </div>
        <div id="print-content">{html_content}</div>
    </body>
    </html>
    """
    components.html(wrapped_html, height=800, scrolling=True)

def show():
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()

    theme = apply_global_theme()
    primary_color = theme.get("primary_color", "#0F4C81")

    designations = supabase.table("designations").select("id, designation_name").eq("active", True).execute().data or []
    districts = supabase.table("districts").select("id, district_name").execute().data or []
    blocks = supabase.table("blocks").select("id, block_name, district_id").execute().data or []
    departments = supabase.table("departments").select("id, department_name").eq("active", True).execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").eq("active", True).execute().data or []

    desig_dict = {d["designation_name"]: d["id"] for d in designations}
    dist_dict = {d["district_name"]: d["id"] for d in districts}
    block_dict = {b["block_name"]: b["id"] for b in blocks}
    dept_dict = {d["department_name"]: d["id"] for d in departments}
    dept_map = {d["id"]: d["department_name"] for d in departments}

    OFFICE_LEVELS = ["State / Department", "District", "Sub Division", "Block", "Gram Panchayat"]
    COMMITTEE_ROLES = ["None", "Chairperson", "Co-Chairperson", "Member-Convener", "Member"]

    query = supabase.table("contacts").select(
        "*, designations(designation_name), districts(district_name), blocks(block_name), departments(department_name), department_wings(wing_name, entity_type)"
    )

    if role in ["district", "block", "department"] and user.get("district_id"):
        query = query.eq("district_id", user["district_id"])
    if role == "department":
        if user.get("department_id"): query = query.eq("department_id", user["department_id"])
        if user.get("wing_id"): query = query.eq("wing_id", user["wing_id"])

    contacts_data = query.execute().data or []
    df = pd.DataFrame(contacts_data) if contacts_data else pd.DataFrame()

    if not df.empty:
        # 🔥 FIXED: Convert SQL null values to string "None" before counting metrics
        df['district_committee_role'] = df['district_committee_role'].fillna('None')
        df['block_committee_role'] = df['block_committee_role'].fillna('None')

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Officials Mapped", len(df))
        c2.metric("District Level", len(df[df['office_level'] == 'District']))
        c3.metric("Block Level", len(df[df['office_level'] == 'Block']))
        # Now this correctly counts only those with active roles
        c4.metric("Committee Members", len(df[(df['district_committee_role'] != 'None') | (df['block_committee_role'] != 'None')]))
        st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 Master Directory List", "🛠️ Manage Official Profiles"])

    # --- TAB 1: DIRECTORY LIST & EXPORT ---
    with tab1:
        if not df.empty:
            df["Designation"] = df["designations"].apply(lambda x: x.get("designation_name", "Unassigned") if isinstance(x, dict) else "Unassigned")
            df["District"] = df["districts"].apply(lambda x: x.get("district_name", "District Office") if isinstance(x, dict) else "District Office")
            df["Block"] = df["blocks"].apply(lambda x: x.get("block_name", "N/A") if isinstance(x, dict) else "N/A")
            df["Parent Dept"] = df["departments"].apply(lambda x: x.get("department_name", "General Administration") if isinstance(x, dict) else "General Administration")

            def format_wing(x):
                if isinstance(x, dict) and x.get("wing_name"): return f"{x.get('wing_name')} ({x.get('entity_type', 'Wing')})"
                return "Direct Parent Dept"
            df["Wing / Scheme"] = df["department_wings"].apply(format_wing)

            def format_comm_blocks(block_ids):
                if not block_ids: return "N/A"
                if isinstance(block_ids, str):
                    try: block_ids = json.loads(block_ids)
                    except: return "N/A"
                if not isinstance(block_ids, list) or not block_ids: return "N/A"
                str_block_ids = [str(x) for x in block_ids]
                names = [b_name for b_name, b_id in block_dict.items() if str(b_id) in str_block_ids]
                return ", ".join(names) if names else "N/A"

            for col in ["office_level", "sub_division", "office", "sub_office", "district_committee_role", "block_committee_role", "committee_blocks"]:
                if col not in df.columns: df[col] = None

            df["Tagged Comm. Blocks"] = df["committee_blocks"].apply(format_comm_blocks)
            df["Dist. Role"] = df["district_committee_role"].fillna("None")
            df["Block Role"] = df["block_committee_role"].fillna("None")

            display_df = df[["full_name", "office_level", "Designation", "Parent Dept", "Wing / Scheme", "Dist. Role", "Block Role", "Tagged Comm. Blocks", "contact_number", "email_id"]].copy()
            display_df.columns = ["Name", "Posting Level", "Designation", "Parent Dept", "Wing / Scheme", "Dist. Committee", "Block Committee", "Tagged Blocks", "Contact Number", "Email ID"]

            search_query = st.text_input("🔍 Quick Search", placeholder="Search by name, designation, department, block...")
            filtered_df = display_df
            if search_query:
                mask = display_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False, na=False).any(), axis=1)
                filtered_df = display_df[mask]

            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
            st.markdown("<br>", unsafe_allow_html=True)

            col_dl, col_pr, col_print_preview = st.columns([1.5, 1.8, 1.8])
            buffer = io.BytesIO()
            try:
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    filtered_df.to_excel(writer, index=False, sheet_name="Contacts")
                col_dl.download_button("📥 Download Excel", data=buffer.getvalue(), file_name="official_contact_directory.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            except Exception:
                col_dl.download_button("📥 Download CSV", data=filtered_df.to_csv(index=False).encode("utf-8"), file_name="official_contact_directory.csv", mime="text/csv", use_container_width=True)

            html_table = filtered_df.to_html(index=False)
            printable_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Official Contact Directory</title><style>body {{ font-family: Arial, sans-serif; padding: 20px; font-size: 11px; color: #333; }} h2 {{ text-align: center; color: {primary_color}; border-bottom: 2px solid {primary_color}; padding-bottom: 10px; }} table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }} th, td {{ border: 1px solid #dddddd; padding: 6px; text-align: left; }} th {{ background-color: #f2f2f2; color: #000; }} @page {{ size: A4 landscape; margin: 15mm; }} @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}</style></head><body onload="window.print()"><div class="no-print" style="text-align: center; margin-bottom: 20px; background-color: #f8f9fa; padding: 15px; border-radius: 8px;"><button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: {primary_color}; color: white; border: none; border-radius: 4px;">🖨️ Print or Save as PDF</button></div><h2>Official Contact Directory & Statutory Roles</h2>{html_table}</body></html>"""
            col_pr.download_button("🖨️ Printable HTML", data=printable_html, file_name="Contact_Directory_Print.html", mime="text/html", use_container_width=True)

            if col_print_preview.button("🖨️ Print Table", use_container_width=True):
                html_preview = f"<div style='text-align:center; margin-bottom:20px;'><h2 style='color:{primary_color};'>Official Contact Directory & Statutory Roles</h2></div>{filtered_df.to_html(index=False)}"
                render_print_preview(html_preview)
        else:
            st.info("No contact records found for your jurisdiction.")

    # --- TAB 2: DIRECTORY MANAGER ---
    with tab2:
        existing_record = {}
        target_contact_id = None

        def safe_contact_desig(c_obj):
            desig_obj = c_obj.get('designations')
            if isinstance(desig_obj, dict): return desig_obj.get('designation_name', 'Unknown')
            return 'Unknown'

        if role in ["superadmin", "district", "block"]:
            st.markdown("#### 🛠️ Master Directory Configuration")
            action = st.radio("Action", ["➕ Add New Official", "✏️ Edit Existing Official"], horizontal=True)

            if action == "✏️ Edit Existing Official":
                query = supabase.table("contacts").select("*, designations(designation_name)")
                if role == "district": query = query.eq("district_id", user["district_id"])
                elif role == "block": query = query.eq("block_id", user["block_id"])
                contact_list = query.execute().data
                if contact_list:
                    contact_opts = {c["id"]: f"{c['full_name']} - {safe_contact_desig(c)}" for c in contact_list}
                    target_contact_id = st.selectbox("Select Official to Edit", options=list(contact_opts.keys()), format_func=lambda x: contact_opts[x])
                    existing_record = next((c for c in contact_list if c["id"] == target_contact_id), {})
                else:
                    st.warning("No officials found in your jurisdiction.")
        else:
            st.markdown(f"#### 🔄 Manage Department Personnel: **{dept_map.get(user.get('department_id'), 'Your Department')}**")
            dept_contacts_query = supabase.table("contacts").select("*, designations(designation_name)").eq("department_id", user["department_id"])
            if user.get("wing_id"): dept_contacts_query = dept_contacts_query.eq("wing_id", user["wing_id"])
            if user.get("district_id"): dept_contacts_query = dept_contacts_query.eq("district_id", user["district_id"])
            dept_contacts = dept_contacts_query.execute().data or []
            action_opts = ["➕ Add New Department Official"]
            if dept_contacts: action_opts.append("✏️ Edit / Delete Department Official")
            action = st.radio("Action", action_opts, horizontal=True)

            if action == "✏️ Edit / Delete Department Official" and dept_contacts:
                contact_opts = {c["id"]: f"{c['full_name']} - {safe_contact_desig(c)}" for c in dept_contacts}
                target_contact_id = st.selectbox("Select Official", options=list(contact_opts.keys()), format_func=lambda x: contact_opts[x])
                existing_record = next((c for c in dept_contacts if c["id"] == target_contact_id), {})
                if st.button("🗑️ Delete This Contact Record", type="secondary"):
                    try:
                        resp = supabase.table("contacts").delete().eq("id", target_contact_id).execute()
                        if resp.count and resp.count > 0: st.success("✅ Contact deleted successfully!"); st.rerun()
                        else: st.error("🔴 Delete failed. Database security (RLS) prevented the action.")
                    except Exception as e: st.error(f"Error deleting contact: {e}")

        # =================================================
        # DYNAMIC DEPT & WING DROPDOWN CHAINING
        # =================================================
        st.markdown("##### 2. Department & Level Hierarchy")
        col_l1, col_l2, col_l3 = st.columns([1, 1, 1])

        if role == "department":
            selected_parent_id = user.get("department_id")
            fixed_dept_name = dept_map.get(selected_parent_id, "Your Department")
            col_l3.text_input("Parent Department", value=fixed_dept_name, disabled=True)
        else:
            curr_dept_id = existing_record.get("department_id")
            curr_dept_name = next((k for k, v in dept_dict.items() if v == curr_dept_id), list(dept_dict.keys())[0] if dept_dict else "")
            dept_idx = list(dept_dict.keys()).index(curr_dept_name) if curr_dept_name in dept_dict else 0
            sel_parent_dept = col_l3.selectbox("Parent Department*", options=list(dept_dict.keys()) if dept_dict else ["None"], index=dept_idx)
            selected_parent_id = dept_dict.get(sel_parent_dept)

        # Dynamically filter wings based on selected_parent_id
        valid_wings = []
        if selected_parent_id:
            for w in wings:
                if str(w.get("department_id")) == str(selected_parent_id):
                    valid_wings.append(w)
        wing_options = {"Directly under Parent Department": None}
        for w in valid_wings:
            wing_options[f"{w['wing_name']} ({w['entity_type']})"] = w["id"]

        if role == "department" and not valid_wings:
            st.caption("ℹ️ No specific wings/schemes are currently mapped to this department.")
        if role == "department" and user.get("wing_id"):
            wing_options = {k: v for k, v in wing_options.items() if v == user.get("wing_id") or v is None}

        curr_wing_id = existing_record.get("wing_id") or user.get("wing_id")
        curr_wing_name = next((k for k, v in wing_options.items() if v == curr_wing_id), list(wing_options.keys())[0])
        wing_idx = list(wing_options.keys()).index(curr_wing_name) if curr_wing_name in wing_options else 0
        sel_wing_name = st.selectbox("Specific Wing / Scheme / Parastatal", options=list(wing_options.keys()), index=wing_idx)
        selected_wing_id = wing_options.get(sel_wing_name)

        # =================================================
        # REMAINING FORM
        # =================================================
        with st.form("update_contact_form"):
            st.markdown("##### 1. Official Details")
            col1, col2 = st.columns(2)
            name = col1.text_input("Full Name of Official*", value=existing_record.get("full_name", ""))
            curr_desig_id = existing_record.get("designation_id")
            curr_desig_name = next((k for k, v in desig_dict.items() if v == curr_desig_id), list(desig_dict.keys())[0] if desig_dict else "")
            desig_idx = list(desig_dict.keys()).index(curr_desig_name) if curr_desig_name in desig_dict else 0
            sel_desig = col2.selectbox("Designation*", options=list(desig_dict.keys()) if desig_dict else ["None"], index=desig_idx)

            curr_lvl = existing_record.get("office_level") or "District"
            lvl_idx = OFFICE_LEVELS.index(curr_lvl) if curr_lvl in OFFICE_LEVELS else 1
            sel_lvl = col_l1.selectbox("Posting Level*", OFFICE_LEVELS, index=lvl_idx)
            
            sub_div_val = existing_record.get("sub_division") or ""
            col_l2.text_input("Sub Division Name (If Applicable)", value=sub_div_val)

            st.markdown("##### 3. Primary Jurisdiction Mapping")
            col_j1, col_j2 = st.columns(2)

            curr_dist = existing_record.get("district_id") or user.get("district_id")
            if role in ["superadmin", "district"]:
                dist_names = list(dist_dict.keys())
                curr_dist_name = next((k for k, v in dist_dict.items() if v == curr_dist), dist_names[0]) if curr_dist else dist_names[0]
                idx = dist_names.index(curr_dist_name) if curr_dist_name in dist_names else 0
                sel_dist = col_j1.selectbox("Primary District*", dist_names, index=idx)
                target_district_id = dist_dict[sel_dist]
            else:
                curr_dist_name = next((k for k, v in dist_dict.items() if v == user.get("district_id")), "Unknown")
                col_j1.text_input("Primary District", value=curr_dist_name, disabled=True)
                target_district_id = user.get("district_id")

            if sel_lvl in ["Block", "Gram Panchayat"]:
                if role in ["block", "department"] and user.get("block_id"):
                    curr_block_name = next((k for k, v in block_dict.items() if v == user.get("block_id")), "Unknown")
                    col_j2.text_input("Primary Block", value=curr_block_name, disabled=True)
                    target_block_id = user.get("block_id")
                else:
                    valid_blocks = [b["block_name"] for b in blocks if b["district_id"] == target_district_id]
                    curr_block = existing_record.get("block_id")
                    curr_block_name = next((k for k, v in block_dict.items() if v == curr_block), valid_blocks[0] if valid_blocks else "") if curr_block else (valid_blocks[0] if valid_blocks else "")
                    idx = valid_blocks.index(curr_block_name) if curr_block_name in valid_blocks else 0
                    sel_block = col_j2.selectbox("Primary Block*", valid_blocks if valid_blocks else ["None"], index=idx)
                    target_block_id = block_dict.get(sel_block) if sel_block != "None" else None
            else:
                target_block_id = None
                col_j2.info("Block selection not applicable for this Posting Level.")

            st.markdown("##### 4. Contact & Location Information")
            col3, col4, col5 = st.columns(3)
            contact_no = col3.text_input("Mobile Number", value=existing_record.get("contact_number") or "")
            whatsapp_no = col4.text_input("WhatsApp Number", value=existing_record.get("whatsapp_number") or "")
            email = col5.text_input("Official Email ID", value=existing_record.get("email_id") or "")
            col6, col7 = st.columns(2)
            office = col6.text_input("Office Name / Address", value=existing_record.get("office") or "")
            sub_office = col7.text_input("Sub Office / Room No.", value=existing_record.get("sub_office") or "")

            st.markdown("##### 5. Statutory Committee Memberships")
            if role == "department": st.caption("🔒 *Committee roles are managed exclusively by District & Block Administrations.*")
            col_c1, col_c2 = st.columns(2)
            allow_dist = (role in ["superadmin", "district"]) and (sel_lvl in ["State / Department", "District", "Sub Division"])
            allow_block = (role in ["superadmin", "block"]) and (sel_lvl in ["District", "Sub Division", "Block", "Gram Panchayat"])
            curr_dist_role = existing_record.get("district_committee_role") or "None"
            dist_role_idx = COMMITTEE_ROLES.index(curr_dist_role) if curr_dist_role in COMMITTEE_ROLES else 0
            sel_dist_role = col_c1.selectbox("District Committee Role", COMMITTEE_ROLES, index=dist_role_idx, disabled=not allow_dist)
            final_dist_role = sel_dist_role if allow_dist else curr_dist_role
            curr_block_role = existing_record.get("block_committee_role") or "None"
            block_role_idx = COMMITTEE_ROLES.index(curr_block_role) if curr_block_role in COMMITTEE_ROLES else 0
            sel_block_role = col_c2.selectbox("Block Committee Role", COMMITTEE_ROLES, index=block_role_idx, disabled=not allow_block)
            final_block_role = sel_block_role if allow_block else curr_block_role

            curr_comm_blocks = existing_record.get("committee_blocks") or []
            if isinstance(curr_comm_blocks, str):
                try: curr_comm_blocks = json.loads(curr_comm_blocks)
                except: curr_comm_blocks = []
            curr_comm_blocks = [str(x) for x in curr_comm_blocks]
            default_blocks = [b for b in list(block_dict.keys()) if str(block_dict[b]) in curr_comm_blocks]
            if not default_blocks and target_block_id and final_block_role != "None":
                primary_block_name = next((b_name for b_name, b_id in block_dict.items() if b_id == target_block_id), None)
                if primary_block_name: default_blocks = [primary_block_name]
            sel_comm_blocks = st.multiselect("Tagged Blocks for Committee Membership", options=list(block_dict.keys()), default=default_blocks, disabled=not allow_block)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("Save Profile Details", type="primary"):
                # VALIDATION
                if not name.strip(): st.error("⚠️ Full Name is mandatory.")
                else:
                    comm_block_ids = [block_dict[b] for b in sel_comm_blocks] if allow_block else [block_dict[b] for b in default_blocks]
                    payload = {
                        "full_name": name,
                        "designation_id": desig_dict.get(sel_desig),
                        "department_id": selected_parent_id,
                        "wing_id": selected_wing_id,
                        "office_level": sel_lvl,
                        "sub_division": sub_div_val if sub_div_val.strip() else None,
                        "contact_number": contact_no,
                        "whatsapp_number": whatsapp_no,
                        "email_id": email,
                        "office": office.strip() if office.strip() else None,
                        "sub_office": sub_office.strip() if sub_office.strip() else None,
                        "district_committee_role": final_dist_role if final_dist_role != "None" else None,
                        "block_committee_role": final_block_role if final_block_role != "None" else None,
                        "committee_blocks": comm_block_ids,
                        "district_id": target_district_id,
                        "block_id": target_block_id,
                        "active": True,
                    }
                    try:
                        if target_contact_id:
                            resp = supabase.table("contacts").update(payload).eq("id", target_contact_id).execute()
                            if resp.data and len(resp.data) > 0: st.success("✅ Contact record updated successfully!"); st.rerun()
                            else: st.error("🔴 Update failed. Database security (RLS) prevented the update.")
                        else:
                            supabase.table("contacts").insert(payload).execute()
                            st.success("✅ Contact record saved successfully!")
                            st.rerun()
                    except Exception as e:
                        check_resp = supabase.table("contacts").select("id").eq("full_name", name).execute()
                        if check_resp.data and len(check_resp.data) > 0:
                            st.success("✅ Contact record saved successfully!")
                            st.rerun()
                        else:
                            st.error(f"Error saving contact details: {e}")
  # ---- Display Requested Global Footer Text ----
    st.markdown(
        """
        <div style='text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #E2E8F0; color: #64748B; font-size: 14px; font-weight: 600;'>
            Hooghly District Administration || VB GRAM G Cell || Mail @ nodal.hooghly@gmail.com
        </div>
        """, 
        unsafe_allow_html=True
    )
