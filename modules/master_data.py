import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role
from utils.audit import log_action

def show():
    require_role('superadmin')
    
    st.markdown("<h1 style='color: #1F77B4;'>Master Data Management</h1>", unsafe_allow_html=True)
    st.markdown("---")

    supabase = get_supabase()

    # Define Tabs
    tabs = st.tabs(["Districts", "Blocks", "Departments", "Themes", "Activities", "Financial Years"])

    # ---------------------------------------------------------
    # TAB 1: DISTRICTS
    # ---------------------------------------------------------
    with tabs[0]:
        st.subheader("📍 Manage Districts")
        dist_data = supabase.table("districts").select("*").execute().data
        df_dist = pd.DataFrame(dist_data)
        
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
                    st.error(f"Cannot delete. This district is in use by other records. (Database Error: 42300/Foreign Key)")

    # ---------------------------------------------------------
    # TAB 2: BLOCKS
    # ---------------------------------------------------------
    with tabs[1]:
        st.subheader("🗺️ Manage Blocks")
        block_data = supabase.table("blocks").select("*, districts(district_name)").execute().data
        df_block = pd.DataFrame(block_data)
        
        if not df_block.empty:
            df_block['district_name'] = df_block['districts'].apply(lambda x: x['district_name'] if isinstance(x, dict) else None)
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
            st.warning("⚠️ Warning: Deleting this will fail if users or convergence records are assigned to it.")
            if st.button("Permanently Delete Block", type="primary"):
                try:
                    supabase.table("blocks").delete().eq("id", blk_id).execute()
                    st.success("Deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Cannot delete. This block is in use by other records.")

    # ---------------------------------------------------------
    # HELPER: GENERIC CRUD FOR SIMPLE TABLES (Dept, Theme, FY)
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
    # TAB 3 & 4: DEPARTMENTS AND THEMES (Using Helper)
    # ---------------------------------------------------------
    with tabs[2]: render_simple_master_tab("departments", "department_name", "Department")
    with tabs[3]: render_simple_master_tab("themes", "theme_name", "Theme")

    # ---------------------------------------------------------
    # TAB 5: ACTIVITIES (Custom UI & Auto Importer)
    # ---------------------------------------------------------
    with tabs[4]:
        st.subheader("🛠️ Manage Activities & Department Mapping")
        
        # Fetch lookup data
        depts = supabase.table("departments").select("id, department_name").eq("active", True).execute().data
        themes = supabase.table("themes").select("id, theme_name").eq("active", True).execute().data
        
        # Fetch activities
        act_data = supabase.table("activities").select("*, departments(department_name), themes(theme_name)").execute().data
        df_act = pd.DataFrame(act_data)

        if not df_act.empty:
            df_act['Department'] = df_act['departments'].apply(lambda x: x['department_name'] if isinstance(x, dict) else 'Unassigned')
            df_act['Theme'] = df_act['themes'].apply(lambda x: x['theme_name'] if isinstance(x, dict) else 'Unassigned')
            
            st.dataframe(
                df_act[['id', 'category', 'activity_name', 'Department', 'Theme', 'active']], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No activities found. Please add or import records.")

        action_act = st.radio("Action", ["➕ Add New", "✏️ Edit", "🗑️ Delete"], horizontal=True, key="act_action")

        if action_act == "➕ Add New":
            with st.form("add_act"):
                col1, col2 = st.columns(2)
                
                dept_names = [d['department_name'] for d in depts]
                sel_dept = col1.selectbox("Department (Optional)", ["None"] + dept_names)
                
                theme_names = [t['theme_name'] for t in themes]
                sel_theme = col2.selectbox("Theme (Optional)", ["None"] + theme_names)
                
                cat_sel = col1.selectbox("Category", ["Category I", "Category II", "Category III", "Category IV", "None"])
                
                name = st.text_input("Activity Name")
                desc = st.text_area("Description")
                
                if st.form_submit_button("Save Activity", type="primary") and name:
                    dept_id = next((d['id'] for d in depts if d['department_name'] == sel_dept), None)
                    theme_id = next((t['id'] for t in themes if t['theme_name'] == sel_theme), None)
                    cat_val = None if cat_sel == "None" else cat_sel
                    
                    supabase.table("activities").insert({
                        "department_id": dept_id,
                        "theme_id": theme_id,
                        "category": cat_val,
                        "activity_name": name,
                        "description": desc,
                        "active": True
                    }).execute()
                    st.success(f"Successfully added: {name}")
                    st.rerun()

        elif action_act == "✏️ Edit" and not df_act.empty:
            act_id = st.selectbox(
                "Select Activity to Map / Edit", 
                df_act['id'].tolist(), 
                format_func=lambda x: df_act[df_act['id']==x]['activity_name'].values[0]
            )
            selected = df_act[df_act['id'] == act_id].iloc[0]
            
            with st.form("edit_act"):
                col1, col2 = st.columns(2)
                
                # Dept Dropdown mapping
                dept_names = [d['department_name'] for d in depts]
                curr_dept = selected.get('Department', 'Unassigned')
                dept_opts = ["None"] + dept_names
                dept_idx = dept_opts.index(curr_dept) if curr_dept in dept_opts else 0
                sel_dept = col1.selectbox("Assign Department", dept_opts, index=dept_idx)
                
                # Theme Dropdown mapping
                theme_names = [t['theme_name'] for t in themes]
                curr_theme = selected.get('Theme', 'Unassigned')
                theme_opts = ["None"] + theme_names
                theme_idx = theme_opts.index(curr_theme) if curr_theme in theme_opts else 0
                sel_theme = col2.selectbox("Assign Theme", theme_opts, index=theme_idx)
                
                # Category 
                cats = ["Category I", "Category II", "Category III", "Category IV", "None"]
                curr_cat = selected.get('category')
                cat_idx = cats.index(curr_cat) if curr_cat in cats else 4
                cat_sel = col1.selectbox("Category", cats, index=cat_idx)
                
                name = st.text_input("Activity Name", value=selected['activity_name'])
                desc = st.text_area("Description", value=selected.get('description', '') or '')
                active = st.checkbox("Active Status", value=bool(selected.get('active', True)))
                
                if st.form_submit_button("Update & Map Activity", type="primary"):
                    dept_id = next((d['id'] for d in depts if d['department_name'] == sel_dept), None)
                    theme_id = next((t['id'] for t in themes if t['theme_name'] == sel_theme), None)
                    cat_val = None if cat_sel == "None" else cat_sel
                    
                    supabase.table("activities").update({
                        "department_id": dept_id,
                        "theme_id": theme_id,
                        "category": cat_val,
                        "activity_name": name,
                        "description": desc,
                        "active": active
                    }).eq("id", act_id).execute()
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

        # --- AUTO IMPORTER ---
        st.markdown("---")
        with st.expander("🚀 One-Time Auto Importer (Bulk Upload 318 Works)"):
            st.info("Paste the contents of '318 works list.txt' below to bulk-insert them into the database. You can then map them to Departments using the 'Edit' tool above.")
            bulk_data = st.text_area("Paste text here (Format: 1 _ Name _ Category):", height=200)
            
            if st.button("Start Bulk Import", type="primary"):
                if bulk_data:
                    lines = bulk_data.strip().split('\n')
                    success_count = 0
                    progress_bar = st.progress(0)
                    
                    for i, line in enumerate(lines):
                        parts = line.split(' _ ')
                        if len(parts) >= 3:
                            act_name = parts[1].strip()
                            category = parts[2].strip()
                            
                            try:
                                supabase.table("activities").insert({
                                    "activity_name": act_name,
                                    "category": category,
                                    "active": True
                                }).execute()
                                success_count += 1
                            except Exception as e:
                                st.error(f"Failed to insert '{act_name}'. Error: {e}")
                        
                        # Update progress bar
                        progress_bar.progress((i + 1) / len(lines))
                    
                    st.success(f"✅ Successfully imported {success_count} activities! Refresh or check the table above.")
                else:
                    st.warning("Please paste the text data first.")

    # ---------------------------------------------------------
    # TAB 6: FINANCIAL YEARS (Using Helper)
    # ---------------------------------------------------------
    with tabs[5]: render_simple_master_tab("financial_years", "year_name", "Financial Year")
