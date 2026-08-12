import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role

def show():
    require_role('superadmin')
    
    st.markdown("<h1 style='color: #1F77B4;'>Master Data Management</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()

    # Define Tabs (Includes Designations as the 7th tab)
    tabs = st.tabs(["Districts", "Blocks", "Departments", "Themes", "Activities", "Financial Years", "Designations"])

    # ==========================================
    # GLOBAL FETCH: Load base tables to avoid SQL Join errors
    # ==========================================
    try:
        raw_districts = supabase.table("districts").select("*").execute().data
        df_dist = pd.DataFrame(raw_districts)
        dist_map = {d['id']: d['district_name'] for d in raw_districts} if raw_districts else {}
        
        raw_depts = supabase.table("departments").select("*").execute().data
        dept_map = {d['id']: d['department_name'] for d in raw_depts} if raw_depts else {}
        
        raw_themes = supabase.table("themes").select("*").execute().data
        theme_map = {t['id']: t['theme_name'] for t in raw_themes} if raw_themes else {}
    except Exception as e:
        st.error(f"Error loading master data: {e}")
        return

    # ---------------------------------------------------------
    # TAB 1: DISTRICTS
    # ---------------------------------------------------------
    with tabs[0]:
        st.subheader("📍 Manage Districts")
        
        if not df_dist.empty:
            st.dataframe(df_dist[['id', 'district_name', 'district_code', 'active']], use_container_width=True, hide_index=True)
        else:
            st.info("No districts found.")

        action = st.radio("Action", ["➕ Add New", "✏️ Edit", "🗑️ Delete"], horizontal=True, key="dist_action")

        if action == "➕ Add New":
            with st.form("add_dist"):
                col1, col2 = st.columns(2)
                name = col1.text_input("District Name")
                code = col2.text_input("District Code")
                if st.form_submit_button("Save District", type="primary") and name:
                    supabase.table("districts").insert({"district_name": name, "district_code": code, "active": True}).execute()
                    st.success(f"Added {name}!")
                    st.rerun()

        elif action == "✏️ Edit" and not df_dist.empty:
            dist_id = st.selectbox("Select District to Edit", df_dist['id'].tolist(), format_func=lambda x: df_dist[df_dist['id']==x]['district_name'].values[0])
            selected = df_dist[df_dist['id'] == dist_id].iloc[0]
            
            with st.form("edit_dist"):
                col1, col2 = st.columns(2)
                name = col1.text_input("District Name", value=selected['district_name'])
                code = col2.text_input("District Code", value=selected['district_code'])
                active = st.checkbox("Active Status", value=bool(selected.get('active', True)))
                if st.form_submit_button("Update District", type="primary"):
                    supabase.table("districts").update({"district_name": name, "district_code": code, "active": active}).eq("id", dist_id).execute()
                    st.success("Updated successfully!")
                    st.rerun()

        elif action == "🗑️ Delete" and not df_dist.empty:
            dist_id = st.selectbox("Select District to Delete", df_dist['id'].tolist(), format_func=lambda x: df_dist[df_dist['id']==x]['district_name'].values[0])
            st.warning("⚠️ Warning: Deleting this will fail if blocks or users are currently assigned to it.")
            if st.button("Permanently Delete District", type="primary"):
                try:
                    supabase.table("districts").delete().eq("id", dist_id).execute()
                    st.success("Deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Cannot delete. This district is in use by other records.")

    # ---------------------------------------------------------
    # TAB 2: BLOCKS
    # ---------------------------------------------------------
    with tabs[1]:
        st.subheader("🗺️ Manage Blocks")
        block_data = supabase.table("blocks").select("*").execute().data
        df_block = pd.DataFrame(block_data)
        
        if not df_block.empty:
            df_block['district_name'] = df_block['district_id'].map(dist_map).fillna("Unknown")
            st.dataframe(df_block[['id', 'district_name', 'block_name', 'block_code', 'active']], use_container_width=True, hide_index=True)
        else:
            st.info("No blocks found.")

        action_blk = st.radio("Action", ["➕ Add New", "✏️ Edit", "🗑️ Delete"], horizontal=True, key="blk_action")

        if action_blk == "➕ Add New":
            if df_dist.empty:
                st.warning("Please add a District first.")
            else:
                with st.form("add_blk"):
                    dist_id = st.selectbox("Assign to District", df_dist['id'].tolist(), format_func=lambda x: df_dist[df_dist['id']==x]['district_name'].values[0])
                    col1, col2 = st.columns(2)
                    name = col1.text_input("Block Name")
                    code = col2.text_input("Block Code")
                    if st.form_submit_button("Save Block", type="primary") and name:
                        supabase.table("blocks").insert({"district_id": dist_id, "block_name": name, "block_code": code, "active": True}).execute()
                        st.success(f"Added {name}!")
                        st.rerun()

        elif action_blk == "✏️ Edit" and not df_block.empty:
            blk_id = st.selectbox("Select Block to Edit", df_block['id'].tolist(), format_func=lambda x: df_block[df_block['id']==x]['block_name'].values[0])
            selected = df_block[df_block['id'] == blk_id].iloc[0]
            
            with st.form("edit_blk"):
                dist_idx = df_dist['id'].tolist().index(selected['district_id']) if selected['district_id'] in df_dist['id'].tolist() else 0
                dist_id = st.selectbox("Assign to District", df_dist['id'].tolist(), index=dist_idx, format_func=lambda x: df_dist[df_dist['id']==x]['district_name'].values[0])
                
                col1, col2 = st.columns(2)
                name = col1.text_input("Block Name", value=selected['block_name'])
                code = col2.text_input("Block Code", value=selected['block_code'])
                active = st.checkbox("Active Status", value=bool(selected.get('active', True)))
                
                if st.form_submit_button("Update Block", type="primary"):
                    supabase.table("blocks").update({"district_id": dist_id, "block_name": name, "block_code": code, "active": active}).eq("id", blk_id).execute()
                    st.success("Updated successfully!")
                    st.rerun()

        elif action_blk == "🗑️ Delete" and not df_block.empty:
            blk_id = st.selectbox("Select Block to Delete", df_block['id'].tolist(), format_func=lambda x: df_block[df_block['id']==x]['block_name'].values[0])
            st.warning("⚠️ Warning: Deleting this will fail if users or records are assigned to it.")
            if st.button("Permanently Delete Block", type="primary"):
                try:
                    supabase.table("blocks").delete().eq("id", blk_id).execute()
                    st.success("Deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Cannot delete. This block is in use by other records.")

    # ---------------------------------------------------------
    # HELPER: GENERIC CRUD FOR SIMPLE TABLES
    # ---------------------------------------------------------
    def render_simple_master_tab(table_name, display_col, label):
        st.subheader(f"🗃️ Manage {label}s")
        data = supabase.table(table_name).select("*").execute().data
        df = pd.DataFrame(data)
        
        if not df.empty:
            st.dataframe(df[['id', display_col, 'active']], use_container_width=True, hide_index=True)
        else:
            st.info(f"No {label.lower()}s found.")

        act = st.radio("Action", ["➕ Add New", "✏️ Edit", "🗑️ Delete"], horizontal=True, key=f"act_{table_name}")

        if act == "➕ Add New":
            with st.form(f"add_{table_name}"):
                val = st.text_input(f"{label} Name")
                if st.form_submit_button(f"Save {label}", type="primary") and val:
                    supabase.table(table_name).insert({display_col: val, "active": True}).execute()
                    st.success("Added successfully!")
                    st.rerun()
                    
        elif act == "✏️ Edit" and not df.empty:
            record_id = st.selectbox(f"Select {label} to Edit", df['id'].tolist(), format_func=lambda x: df[df['id']==x][display_col].values[0])
            selected = df[df['id'] == record_id].iloc[0]
            with st.form(f"edit_{table_name}"):
                val = st.text_input(f"{label} Name", value=selected[display_col])
                active = st.checkbox("Active Status", value=bool(selected.get('active', True)))
                if st.form_submit_button(f"Update {label}", type="primary"):
                    supabase.table(table_name).update({display_col: val, "active": active}).eq("id", record_id).execute()
                    st.success("Updated successfully!")
                    st.rerun()
                    
        elif act == "🗑️ Delete" and not df.empty:
            record_id = st.selectbox(f"Select {label} to Delete", df['id'].tolist(), format_func=lambda x: df[df['id']==x][display_col].values[0])
            st.warning("⚠️ Warning: Ensure this record is not tied to active projects before deleting.")
            if st.button(f"Permanently Delete {label}", type="primary", key=f"del_btn_{table_name}"):
                try:
                    supabase.table(table_name).delete().eq("id", record_id).execute()
                    st.success("Deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Cannot delete. This record is linked to existing data.")

    # ---------------------------------------------------------
    # RENDER SIMPLE TABS (Departments, Themes, Financial Years, Designations)
    # ---------------------------------------------------------
    with tabs[2]: render_simple_master_tab("departments", "department_name", "Department")
    with tabs[3]: render_simple_master_tab("themes", "theme_name", "Theme")
    with tabs[5]: render_simple_master_tab("financial_years", "year_name", "Financial Year")
    with tabs[6]: render_simple_master_tab("designations", "designation_name", "Designation")

    # ---------------------------------------------------------
    # TAB 5: ACTIVITIES (Multi-Department Mapping)
    # ---------------------------------------------------------
    with tabs[4]:
        st.subheader("🛠️ Manage Activities & Multi-Department Mapping")
        
        active_depts = [d for d in raw_depts if d.get('active', True)]
        active_themes = [t for t in raw_themes if t.get('active', True)]
        
        dept_names_map = {d['department_name']: d['id'] for d in active_depts}
        theme_names_map = {t['theme_name']: t['id'] for t in active_themes}

        act_data = supabase.table("activities").select("*").execute().data
        mapping_data = supabase.table("activity_departments").select("*").execute().data
        
        df_act = pd.DataFrame(act_data)
        df_map = pd.DataFrame(mapping_data)

        if not df_act.empty:
            df_act['Theme'] = df_act['theme_id'].map(theme_map).fillna('Unassigned')
            
            if not df_map.empty:
                df_map['dept_name'] = df_map['department_id'].map(dept_map)
                dept_agg = df_map.dropna(subset=['dept_name']).groupby('activity_id')['dept_name'].apply(lambda x: ', '.join(x)).reset_index(name='Departments')
                df_act = df_act.merge(dept_agg, left_on='id', right_on='activity_id', how='left')
            else:
                df_act['Departments'] = 'Unassigned'
                
            df_act['Departments'] = df_act['Departments'].fillna('Unassigned')
            
            st.dataframe(
                df_act[['id', 'activity_name', 'Departments', 'Theme', 'active']], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No activities found.")

        action_act = st.radio("Action", ["➕ Add New", "✏️ Edit / Map", "🗑️ Delete"], horizontal=True, key="act_action")

        if action_act == "➕ Add New":
            with st.form("add_act"):
                col1, col2 = st.columns(2)
                
                sel_depts = col1.multiselect("Assign Departments (Multiple allowed)", options=list(dept_names_map.keys()))
                sel_theme = col2.selectbox("Theme (Category)", ["None"] + list(theme_names_map.keys()))
                
                name = st.text_input("Activity Name")
                desc = st.text_area("Description")
                
                if st.form_submit_button("Save Activity", type="primary") and name:
                    theme_id = theme_names_map.get(sel_theme, None)
                    
                    res = supabase.table("activities").insert({
                        "theme_id": theme_id,
                        "activity_name": name,
                        "description": desc,
                        "active": True
                    }).execute()
                    
                    if res.data:
                        new_act_id = res.data[0]['id']
                        for d_name in sel_depts:
                            supabase.table("activity_departments").insert({
                                "activity_id": new_act_id,
                                "department_id": dept_names_map[d_name]
                            }).execute()
                            
                    st.success(f"Successfully added: {name}")
                    st.rerun()

        elif action_act == "✏️ Edit / Map" and not df_act.empty:
            act_id = st.selectbox(
                "Select Activity to Map / Edit", 
                df_act['id'].tolist(), 
                format_func=lambda x: df_act[df_act['id']==x]['activity_name'].values[0]
            )
            selected = df_act[df_act['id'] == act_id].iloc[0]
            
            if not df_map.empty:
                current_mapped_depts = df_map[df_map['activity_id'] == act_id]['department_id'].map(dept_map).dropna().tolist()
            else:
                current_mapped_depts = []

            with st.form("edit_act"):
                col1, col2 = st.columns(2)
                
                sel_depts = col1.multiselect("Assign Departments", options=list(dept_names_map.keys()), default=current_mapped_depts)
                
                curr_theme = selected.get('Theme', 'Unassigned')
                theme_opts = ["None"] + list(theme_names_map.keys())
                theme_idx = theme_opts.index(curr_theme) if curr_theme in theme_opts else 0
                sel_theme = col2.selectbox("Assign Theme", theme_opts, index=theme_idx)
                
                name = st.text_input("Activity Name", value=selected['activity_name'])
                desc = st.text_area("Description", value=selected.get('description', '') or '')
                active = st.checkbox("Active Status", value=bool(selected.get('active', True)))
                
                if st.form_submit_button("Update & Map Activity", type="primary"):
                    theme_id = theme_names_map.get(sel_theme, None)
                    
                    supabase.table("activities").update({
                        "theme_id": theme_id,
                        "activity_name": name,
                        "description": desc,
                        "active": active
                    }).eq("id", act_id).execute()
                    
                    supabase.table("activity_departments").delete().eq("activity_id", act_id).execute()
                    for d_name in sel_depts:
                        supabase.table("activity_departments").insert({
                            "activity_id": act_id,
                            "department_id": dept_names_map[d_name]
                        }).execute()
                        
                    st.success("Successfully Mapped and Updated!")
                    st.rerun()

        elif action_act == "🗑️ Delete" and not df_act.empty:
            act_id = st.selectbox(
                "Select Activity to Delete", 
                df_act['id'].tolist(), 
                format_func=lambda x: df_act[df_act['id']==x]['activity_name'].values[0]
            )
            if st.button("Permanently Delete Activity", type="primary"):
                try:
                    supabase.table("activities").delete().eq("id", act_id).execute()
                    st.success("Deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Cannot delete. This activity is linked to existing projects.")
