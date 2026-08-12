import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role

def show():
    require_role('superadmin')
    st.markdown("<h1 style='color: #1F77B4;'>⚙️ Master Data Management</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Districts", "Blocks", "Departments", "🏢 Wings/Parastatals", 
        "Themes", "Activities", "Financial Years", "🎓 Designations"
    ])

    # ======================== TAB 1: DISTRICTS ========================
    with tab1:
        st.subheader("Manage Districts")
        dist_data = supabase.table("districts").select("*").order("district_name").execute().data
        if dist_data:
            st.dataframe(pd.DataFrame(dist_data)[['id', 'district_name', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("district_form"):
            dist_name = st.text_input("District Name")
            if st.form_submit_button("Save District", type="primary"):
                supabase.table("districts").insert({"district_name": dist_name, "active": True}).execute()
                st.success("District added!")
                st.rerun()

    # ======================== TAB 2: BLOCKS ========================
    with tab2:
        st.subheader("Manage Blocks")
        blocks_data = supabase.table("blocks").select("*, districts(district_name)").order("block_name").execute().data
        if blocks_data:
            df_b = pd.DataFrame(blocks_data)
            df_b['District'] = df_b['districts'].apply(lambda x: x['district_name'] if isinstance(x, dict) else '')
            st.dataframe(df_b[['id', 'District', 'block_name', 'active']], use_container_width=True, hide_index=True)
            
        dist_dict = {d['district_name']: d['id'] for d in dist_data} if dist_data else {}
        with st.form("block_form"):
            sel_dist = st.selectbox("Parent District", list(dist_dict.keys()) if dist_dict else ["None"])
            block_name = st.text_input("Block Name")
            if st.form_submit_button("Save Block", type="primary"):
                supabase.table("blocks").insert({"district_id": dist_dict[sel_dist], "block_name": block_name, "active": True}).execute()
                st.success("Block added!")
                st.rerun()

    # ======================== TAB 3: DEPARTMENTS ========================
    with tab3:
        st.subheader("Manage Departments")
        dept_data = supabase.table("departments").select("*").order("department_name").execute().data
        if dept_data:
            st.dataframe(pd.DataFrame(dept_data)[['id', 'department_name', 'department_code', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("dept_form"):
            col_d1, col_d2 = st.columns(2)
            dept_name = col_d1.text_input("Department Name")
            dept_code = col_d2.text_input("Department Code (Optional)")
            if st.form_submit_button("Save Department", type="primary"):
                supabase.table("departments").insert({"department_name": dept_name, "department_code": dept_code if dept_code else None, "active": True}).execute()
                st.success("Department added!")
                st.rerun()

    # ======================== TAB 4: WINGS/PARASTATALS ========================
    with tab4:
        st.subheader("🏢 Manage Department Wings, Schemes & Parastatals")
        dept_dict_w = {d['department_name']: d['id'] for d in dept_data} if dept_data else {}
        wings_data = supabase.table("department_wings").select("*, departments(department_name)").order("department_id").execute().data
        
        if wings_data:
            df_wings = pd.DataFrame(wings_data)
            df_wings['Parent Department'] = df_wings['departments'].apply(lambda x: x['department_name'] if isinstance(x, dict) else 'Unknown')
            st.dataframe(df_wings[['id', 'Parent Department', 'wing_name', 'entity_type', 'active']], use_container_width=True, hide_index=True)

        with st.form("wing_form"):
            col_w1, col_w2 = st.columns(2)
            sel_dept = col_w1.selectbox("Parent Department", list(dept_dict_w.keys()) if dept_dict_w else ["None"])
            wing_name = col_w2.text_input("Wing / Parastatal Name")
            entity_type = st.selectbox("Entity Type", ["Wing", "Parastatal", "Scheme", "Directorate", "Sub-Department"])
            
            if st.form_submit_button("Save Sub-Entity", type="primary"):
                supabase.table("department_wings").insert({"department_id": dept_dict_w[sel_dept], "wing_name": wing_name, "entity_type": entity_type, "active": True}).execute()
                st.success("Wing added!")
                st.rerun()

    # ======================== TAB 5: THEMES ========================
    with tab5:
        st.subheader("Manage Themes")
        theme_data = supabase.table("themes").select("*").order("theme_name").execute().data
        if theme_data:
            st.dataframe(pd.DataFrame(theme_data)[['id', 'theme_name', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("theme_form"):
            theme_name = st.text_input("Theme Name")
            if st.form_submit_button("Save Theme", type="primary"):
                supabase.table("themes").insert({"theme_name": theme_name, "active": True}).execute()
                st.success("Theme added!")
                st.rerun()

    # ======================== TAB 6: ACTIVITIES ========================
    with tab6:
        st.subheader("Manage Activities")
        act_data = supabase.table("activities").select("*, themes(theme_name)").order("activity_name").execute().data
        if act_data:
            df_a = pd.DataFrame(act_data)
            df_a['Theme'] = df_a['themes'].apply(lambda x: x['theme_name'] if isinstance(x, dict) else '')
            st.dataframe(df_a[['id', 'Theme', 'activity_name', 'active']], use_container_width=True, hide_index=True)
            
        theme_dict = {t['theme_name']: t['id'] for t in theme_data} if theme_data else {}
        with st.form("activity_form"):
            sel_theme = st.selectbox("Parent Theme", list(theme_dict.keys()) if theme_dict else ["None"])
            act_name = st.text_input("Activity Name")
            if st.form_submit_button("Save Activity", type="primary"):
                supabase.table("activities").insert({"theme_id": theme_dict[sel_theme], "activity_name": act_name, "active": True}).execute()
                st.success("Activity added!")
                st.rerun()

    # ======================== TAB 7: FINANCIAL YEARS ========================
    with tab7:
        st.subheader("Manage Financial Years")
        fy_data = supabase.table("financial_years").select("*").order("year_name").execute().data
        if fy_data:
            st.dataframe(pd.DataFrame(fy_data)[['id', 'year_name', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("fy_form"):
            fy_name = st.text_input("Financial Year (e.g., 2026-27)")
            if st.form_submit_button("Save FY", type="primary"):
                supabase.table("financial_years").insert({"year_name": fy_name, "active": True}).execute()
                st.success("FY added!")
                st.rerun()

    # ======================== TAB 8: DESIGNATIONS & COMMITTEE MEMBERS ========================
    with tab8:
        st.subheader("🎓 Manage Designations & Statutory Committee Roles")
        st.caption("Designations flagged as statutory members will automatically be pre-selected when scheduling a District or Block meeting.")
        
        desig_data = supabase.table("designations").select("*").order("designation_name").execute().data
        if desig_data:
            df_desig = pd.DataFrame(desig_data)
            st.dataframe(df_desig[['id', 'designation_name', 'is_committee_member', 'committee_level', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("desig_form"):
            col_des1, col_des2, col_des3 = st.columns([2, 1, 1])
            desig_name = col_des1.text_input("Designation Title")
            is_committee = col_des2.checkbox("Statutory Committee Member?")
            comm_level = col_des3.selectbox("Committee Level", ["None", "District", "Block"])
            
            if st.form_submit_button("Save Designation", type="primary"):
                payload = {
                    "designation_name": desig_name, 
                    "is_committee_member": is_committee,
                    "committee_level": comm_level if is_committee else None,
                    "active": True
                }
                supabase.table("designations").insert(payload).execute()
                st.success("Designation added!")
                st.rerun()
