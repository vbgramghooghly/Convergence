import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role
from utils.theme import apply_global_theme

def inject_tab_css():
    """Injects modern, trendy CSS to elevate the UI of Streamlit tabs."""
    st.markdown("""
        <style>
        /* Base styling for all tabs (making them look like pills) */
        div[data-testid="stTabs"] button[role="tab"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 30px; /* Fully rounded pill shape */
            padding: 8px 20px;
            margin-right: 10px;
            font-weight: 600;
            color: #4B5563;
            transition: all 0.25s ease-in-out;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        
        /* Hover effect for unselected tabs */
        div[data-testid="stTabs"] button[role="tab"]:hover {
            background-color: #F3F4F6;
            border-color: #D1D5DB;
            color: #111827;
            transform: translateY(-1px);
        }
        
        /* Styling for the ACTIVE selected tab */
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background-color: #1F77B4 !important; /* Brand Blue */
            color: white !important;
            border-color: #1F77B4 !important;
            box-shadow: 0 4px 10px -2px rgba(31, 119, 180, 0.4) !important;
        }
        
        /* Hide the default Streamlit bottom blue highlight line */
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            display: none;
        }
        
        /* Add some breathing room below the tabs before the content starts */
        div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
            padding-top: 25px;
        }
        </style>
    """, unsafe_allow_html=True)

def show():
    require_role('superadmin')
    
    # Inject the fancy CSS
    inject_tab_css()
    
    st.markdown("<h1 style='color: #1F77B4;'>⚙️ Master Data Management</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()

    # Pre-fetch all master data tables globally for clean cross-tab usage & ordering safety
    dist_data = supabase.table("districts").select("*").order("district_name").execute().data
    dept_data = supabase.table("departments").select("*").order("department_name").execute().data
    theme_data = supabase.table("themes").select("*").order("theme_name").execute().data
    fy_data = supabase.table("financial_years").select("*").order("year_name").execute().data
    desig_data = supabase.table("designations").select("*").order("designation_name").execute().data

    # Added Emojis to all tabs for a modern look
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🗺️ Districts", 
        "🏘️ Blocks", 
        "🏢 Departments", 
        "🏛️ Wings/Parastatals", 
        "🎯 Themes", 
        "🛠️ Activities", 
        "📅 Financial Years", 
        "🎓 Designations"
    ])

    # ======================== TAB 1: DISTRICTS ========================
    with tab1:
        st.subheader("Manage Districts")
        if dist_data:
            st.dataframe(pd.DataFrame(dist_data)[['id', 'district_name', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("district_form"):
            dist_name = st.text_input("District Name")
            if st.form_submit_button("Save District", type="primary"):
                try:
                    supabase.table("districts").insert({"district_name": dist_name, "active": True}).execute()
                    st.success("District added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add district: {e}")

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
                try:
                    supabase.table("blocks").insert({"district_id": dist_dict[sel_dist], "block_name": block_name, "active": True}).execute()
                    st.success("Block added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add block: {e}")

    # ======================== TAB 3: DEPARTMENTS ========================
    with tab3:
        st.subheader("Manage Departments")
        if dept_data:
            st.dataframe(pd.DataFrame(dept_data)[['id', 'department_name', 'department_code', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("dept_form"):
            col_d1, col_d2 = st.columns(2)
            dept_name = col_d1.text_input("Department Name")
            dept_code = col_d2.text_input("Department Code (Optional)")
            if st.form_submit_button("Save Department", type="primary"):
                try:
                    supabase.table("departments").insert({"department_name": dept_name, "department_code": dept_code if dept_code else None, "active": True}).execute()
                    st.success("Department added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add department: {e}")

    # ======================== TAB 4: WINGS/PARASTATALS ========================
    with tab4:
        st.subheader("🏛️ Manage Department Wings, Schemes & Parastatals")
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
                try:
                    supabase.table("department_wings").insert({"department_id": dept_dict_w[sel_dept], "wing_name": wing_name, "entity_type": entity_type, "active": True}).execute()
                    st.success("Wing added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add wing: {e}")

    # ======================== TAB 5: THEMES ========================
    with tab5:
        st.subheader("Manage Themes")
        if theme_data:
            st.dataframe(pd.DataFrame(theme_data)[['id', 'theme_name', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("theme_form"):
            theme_name = st.text_input("Theme Name")
            if st.form_submit_button("Save Theme", type="primary"):
                try:
                    supabase.table("themes").insert({"theme_name": theme_name, "active": True}).execute()
                    st.success("Theme added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add theme: {e}")

    # ======================== TAB 6: ACTIVITIES ========================
    with tab6:
        st.subheader("Manage Activities")
        
        # 1. Fetch activities with Many-to-Many junction mapping (activity_departments)
        act_data = supabase.table("activities").select(
            "id, activity_name, active, themes(theme_name), activity_departments(departments(department_name))"
        ).order("activity_name").execute().data
        
        if act_data:
            df_a = pd.DataFrame(act_data)
            
            # Helper function to unpack the nested JSON array from the many-to-many relationship
            def extract_departments(mapping_list):
                if not isinstance(mapping_list, list): return ""
                dept_names = [
                    mapping.get('departments', {}).get('department_name', '') 
                    for mapping in mapping_list if mapping.get('departments')
                ]
                return ", ".join(filter(None, dept_names))
            
            # Safely process and extract nested data
            df_a['Departments'] = df_a.get('activity_departments', []).apply(extract_departments)
            df_a['Theme'] = df_a.get('themes', {}).apply(lambda x: x.get('theme_name', '') if isinstance(x, dict) else '')
            
            st.dataframe(df_a[['id', 'Departments', 'Theme', 'activity_name', 'active']], use_container_width=True, hide_index=True)
            
        dept_dict_act = {d['department_name']: d['id'] for d in dept_data} if dept_data else {}
        theme_dict = {t['theme_name']: t['id'] for t in theme_data} if theme_data else {}
        act_dict = {a['activity_name']: a['id'] for a in act_data} if act_data else {}

        # Toggle to switch between Mapping an existing activity or Creating a brand new one
        action = st.radio("Choose Action", ["Map / Edit Existing Activity", "Create New Activity"], horizontal=True)

        if action == "Map / Edit Existing Activity":
            # Placed outside the form so Streamlit can auto-update the multiselect defaults below
            selected_act_name = st.selectbox("Select Activity to Edit", list(act_dict.keys()) if act_dict else ["None"])
            
            # Determine current state for pre-filling
            current_theme_name = "None"
            current_dept_names = []
            
            if selected_act_name and selected_act_name != "None":
                act_info = next((a for a in act_data if a['activity_name'] == selected_act_name), None)
                if act_info:
                    current_theme_name = act_info.get('themes', {}).get('theme_name', 'None') if act_info.get('themes') else "None"
                    mappings = act_info.get('activity_departments', [])
                    if mappings:
                        current_dept_names = [m['departments']['department_name'] for m in mappings if m.get('departments')]

            with st.form("edit_activity_form"):
                col_a1, col_a2 = st.columns(2)
                
                # Pre-fill Departments
                default_depts = [d for d in current_dept_names if d in dept_dict_act]
                sel_depts = col_a1.multiselect("Parent Department(s)", list(dept_dict_act.keys()), default=default_depts)
                
                # Pre-fill Theme
                theme_opts = list(theme_dict.keys())
                theme_idx = theme_opts.index(current_theme_name) if current_theme_name in theme_opts else 0
                sel_theme = col_a2.selectbox("Parent Theme", theme_opts if theme_opts else ["None"], index=theme_idx)
                
                if st.form_submit_button("Update Mappings", type="primary"):
                    if not sel_depts:
                        st.error("Please select at least one department.")
                    else:
                        act_id = act_dict.get(selected_act_name)
                        
                        try:
                            # A. Update the Theme in the main activities table
                            resp_theme = supabase.table("activities").update({"theme_id": theme_dict.get(sel_theme)}).eq("id", act_id).execute()
                            if not (resp_theme.count and resp_theme.count > 0):
                                st.error("🔴 Theme update failed. Database security (RLS) prevented the update.")

                            # B. Clear old department mappings
                            resp_del = supabase.table("activity_departments").delete().eq("activity_id", act_id).execute()
                            if not (resp_del.count and resp_del.count > 0):
                                st.warning("No old mappings were found to delete.")

                            # C. Insert newly selected department mappings
                            junction_payloads = [{"activity_id": act_id, "department_id": dept_dict_act[dept]} for dept in sel_depts]
                            supabase.table("activity_departments").insert(junction_payloads).execute()
                            
                            st.success(f"Successfully updated mapping for '{selected_act_name}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating mappings: {e}")

        else:
            with st.form("create_activity_form"):
                col_a1, col_a2 = st.columns(2)
                sel_depts = col_a1.multiselect("Parent Department(s)", list(dept_dict_act.keys()) if dept_dict_act else [])
                sel_theme = col_a2.selectbox("Parent Theme", list(theme_dict.keys()) if theme_dict else ["None"])
                act_name = st.text_input("New Activity Name")
                
                if st.form_submit_button("Save New Activity", type="primary"):
                    if not sel_depts:
                        st.error("Please select at least one department.")
                    elif not act_name:
                        st.error("Please provide an activity name.")
                    else:
                        try:
                            # Insert Activity
                            act_payload = {"theme_id": theme_dict.get(sel_theme), "activity_name": act_name, "active": True}
                            response = supabase.table("activities").insert(act_payload).execute()
                            
                            # Insert mappings to Junction Table
                            if response.data:
                                new_activity_id = response.data[0]['id']
                                junction_payloads = [{"activity_id": new_activity_id, "department_id": dept_dict_act[dept]} for dept in sel_depts]
                                supabase.table("activity_departments").insert(junction_payloads).execute()
                                st.success("New Activity created and mapped successfully!")
                                st.rerun()
                            else:
                                st.error("🔴 Activity creation failed. Database security (RLS) may have prevented the insert.")
                        except Exception as e:
                            st.error(f"Failed to create activity: {e}")

    # ======================== TAB 7: FINANCIAL YEARS ========================
    with tab7:
        st.subheader("Manage Financial Years")
        if fy_data:
            st.dataframe(pd.DataFrame(fy_data)[['id', 'year_name', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("fy_form"):
            fy_name = st.text_input("Financial Year (e.g., 2026-27)")
            if st.form_submit_button("Save FY", type="primary"):
                try:
                    supabase.table("financial_years").insert({"year_name": fy_name, "active": True}).execute()
                    st.success("FY added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add FY: {e}")

    # ======================== TAB 8: DESIGNATIONS & COMMITTEE MEMBERS ========================
    with tab8:
        st.subheader("🎓 Manage Designations & Statutory Committee Roles")
        st.caption("Designations flagged as statutory members will automatically be pre-selected when scheduling a District or Block meeting.")
        
        if desig_data:
            df_desig = pd.DataFrame(desig_data)
            st.dataframe(df_desig[['id', 'designation_name', 'is_committee_member', 'committee_level', 'active']], use_container_width=True, hide_index=True)
            
        with st.form("desig_form"):
            col_des1, col_des2, col_des3 = st.columns([2, 1, 1])
            desig_name = col_des1.text_input("Designation Title")
            is_committee = col_des2.checkbox("Statutory Committee Member?")
            comm_level = col_des3.selectbox("Committee Level", ["None", "District", "Block"])
            
            if st.form_submit_button("Save Designation", type="primary"):
                try:
                    payload = {
                        "designation_name": desig_name, 
                        "is_committee_member": is_committee,
                        "committee_level": comm_level if is_committee else None,
                        "active": True
                    }
                    supabase.table("designations").insert(payload).execute()
                    st.success("Designation added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add designation: {e}")
