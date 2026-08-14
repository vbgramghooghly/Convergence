import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user

def inject_custom_css():
    """Injects custom CSS to hide the Streamlit toolbar and format metric cards."""
    st.markdown("""
        <style>
        .stAppToolbar { visibility: hidden !important; }
        .metric-card { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-top: 4px solid #1F77B4; }
        </style>
        """, unsafe_allow_html=True)

def show():
    # Allow all execution and planning roles
    require_role('superadmin', 'district', 'block', 'department')
    
    inject_custom_css()
    
    user = get_current_user()
    role = user['role']
    supabase = get_supabase()

    # Retrieve the active Financial Year selected in the top-left sidebar
    active_fy = st.session_state.get("selected_fy", "2026-27")

    st.markdown("<h1 style='color: #1F77B4;'>Convergence Master Dashboard</h1>", unsafe_allow_html=True)
    st.caption(f"FY {active_fy} | Real-time Onboarding, Activity Linkage, Target Compliance & Convergence Health Metrics.")

    # ======================== 1. MASTER DATA FETCH ========================
    departments = supabase.table("departments").select("id, department_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
    districts = supabase.table("districts").select("id, district_name").execute().data or []
    blocks = supabase.table("blocks").select("id, block_name, district_id").execute().data or []
    activities = supabase.table("activities").select("id, activity_name").execute().data or []
    act_dept_mapping = supabase.table("activity_departments").select("*").execute().data or []
    
    # Fetch Users/Officials directory safely
    users_data = supabase.table("users").select("id, full_name, role, department_id, wing_id, district_id, block_id").execute().data or []
    
    dept_map = {d['id']: d['department_name'] for d in departments}
    wing_map = {w['id']: w for w in wings}
    dist_map = {d['id']: d['district_name'] for d in districts}
    block_map = {b['id']: b['block_name'] for b in blocks}
    act_map = {a['id']: a['activity_name'] for a in activities}

    # ======================== 2. FETCH REGISTERS & TARGETS (FILTERED BY FY) ========================
    q_targets = supabase.table("department_targets").select("*").eq("financial_year", active_fy)
    
    try:
        q_reg = supabase.table("convergence_register").select("*").eq("financial_year", active_fy)
    except Exception:
        q_reg = supabase.table("convergence_register").select("*")

    # Role-based Database Filtering
    if role == 'district':
        q_targets = q_targets.eq("district_id", user['district_id'])
        q_reg = q_reg.eq("district_id", user['district_id'])
    elif role == 'block':
        q_targets = q_targets.eq("district_id", user['district_id'])
        q_reg = q_reg.eq("block_id", user['block_id'])
    elif role == 'department':
        q_targets = q_targets.eq("department_id", user['department_id']).eq("district_id", user['district_id'])
        q_reg = q_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    targets_data = q_targets.execute().data or []
    reg_data = q_reg.execute().data or []
    
    df_targets = pd.DataFrame(targets_data)
    df_reg = pd.DataFrame(reg_data)

    # ======================== 3. ADVANCED KPIS & METRICS ========================
    total_depts_wings = len(departments) + len(wings)
    
    district_officials_count = len([u for u in users_data if u.get('role') in ['district', 'department'] and u.get('block_id') is None])
    block_officials_count = len([u for u in users_data if u.get('block_id') is not None])
    
    blocks_covered = df_reg['block_id'].nunique() if not df_reg.empty and 'block_id' in df_reg.columns else 0
    
    total_activities_master = len(activities)
    linked_activity_ids = set([m['activity_id'] for m in act_dept_mapping])
    linked_activities_count = len(linked_activity_ids)
    unlinked_activities_count = total_activities_master - linked_activities_count
    
    depts_with_activities = set([m['department_id'] for m in act_dept_mapping])
    depts_active_count = len(depts_with_activities)
    
    activity_dept_counts = {}
    for m in act_dept_mapping:
        act_id = m['activity_id']
        activity_dept_counts[act_id] = activity_dept_counts.get(act_id, 0) + 1
    multi_dept_activities_count = len([act_id for act_id, count in activity_dept_counts.items() if count > 1])

    # ======================== 4. TABS LAYOUT ========================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Master Dashboard & Health", 
        "🏢 Department Onboarding Matrix", 
        "🏘️ Block Coverage Matrix", 
        "🔗 Activity Convergence", 
        "🚨 Target Compliance Tracker"
    ])

    # =====================================================================
    # TAB 1: MASTER DASHBOARD & HEALTH
    # =====================================================================
    with tab1:
        st.subheader(f"At-a-Glance Convergence Metrics ({active_fy})")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Departments / Wings Onboarded", total_depts_wings)
        c2.metric("District-Level Officials", district_officials_count)
        c3.metric("Block-Level Officials", block_officials_count)
        c4.metric("Activities Linked", f"{linked_activities_count} / {total_activities_master}")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Blocks Covered", f"{blocks_covered} / {len(blocks)}")
        c6.metric("Depts with Activities", depts_active_count)
        c7.metric("Unlinked Activities", unlinked_activities_count)
        c8.metric("Multi-Dept Activities", multi_dept_activities_count)

        st.markdown("---")
        
        st.markdown("### 🟢 Convergence Health Status")
        h1, h2, h3 = st.columns(3)
        
        fully_onboarded = len([d for d in departments if d['id'] in depts_with_activities])
        partially_onboarded = len(wings)
        not_onboarded = total_depts_wings - fully_onboarded - len(wings)
        
        h1.metric("🟢 Fully Onboarded Depts", fully_onboarded)
        h2.metric("🟡 Parastatals / Wings", partially_onboarded)
        h3.metric("🔴 Inactive / Unlinked Depts", max(0, not_onboarded))

        st.markdown("---")
        st.subheader("Performance Visualizations")
        col_v1, col_v2 = st.columns(2)
        
        with col_v1:
            st.markdown("##### Financial Convergence by Department")
            if not df_reg.empty and 'department_id' in df_reg.columns:
                df_fin = df_reg.groupby('department_id')[['department_fund', 'vbgramg_fund']].sum().reset_index()
                df_fin['Department'] = df_fin['department_id'].map(dept_map)
                df_fin.set_index('Department', inplace=True)
                st.bar_chart(df_fin[['department_fund', 'vbgramg_fund']])
            else:
                st.info(f"No financial data available for FY {active_fy}.")
                
        with col_v2:
            st.markdown("##### Physical Achievement by Department")
            if not df_reg.empty and 'department_id' in df_reg.columns and 'physical_achievement' in df_reg.columns:
                df_phys = df_reg.groupby('department_id')['physical_achievement'].mean().reset_index()
                df_phys['Department'] = df_phys['department_id'].map(dept_map)
                df_phys.set_index('Department', inplace=True)
                st.bar_chart(df_phys['physical_achievement'])
            else:
                st.info(f"No achievement data available for FY {active_fy}.")

    # =====================================================================
    # TAB 2: DEPARTMENT ONBOARDING MATRIX
    # =====================================================================
    with tab2:
        st.subheader("Department-Wise Onboarding & Linkage Matrix")
        st.caption("Detailed breakdown of district officials, block officials, and linked activities per department/wing.")

        matrix_rows = []
        for d in departments:
            d_id = d['id']
            d_name = d['department_name']
            
            d_dist_offs = len([u for u in users_data if u.get('department_id') == d_id and u.get('wing_id') is None and u.get('block_id') is None])
            d_blk_offs = len([u for u in users_data if u.get('department_id') == d_id and u.get('wing_id') is None and u.get('block_id') is not None])
            d_acts = len([m for m in act_dept_mapping if m.get('department_id') == d_id])
            d_blocks = df_reg[df_reg['department_id'] == d_id]['block_id'].nunique() if not df_reg.empty and 'department_id' in df_reg.columns else 0
            status = "Active" if d_acts > 0 else "Pending"

            matrix_rows.append({
                "Department / Wing": f"{d_name} (Main)",
                "Onboarded": "✓",
                "District Officials": d_dist_offs,
                "Block Officials": d_blk_offs,
                "Activities Linked": d_acts,
                "Blocks Covered": d_blocks,
                "Status": status
            })

        for w in wings:
            w_id = w['id']
            d_id = w['department_id']
            parent_name = dept_map.get(d_id, "Unknown")
            w_name = w['wing_name']
            
            w_dist_offs = len([u for u in users_data if u.get('wing_id') == w_id and u.get('block_id') is None])
            w_blk_offs = len([u for u in users_data if u.get('wing_id') == w_id and u.get('block_id') is not None])
            w_acts = len([m for m in act_dept_mapping if m.get('department_id') == d_id])
            w_blocks = 0

            matrix_rows.append({
                "Department / Wing": f"{parent_name} ➔ {w_name}",
                "Onboarded": "✓",
                "District Officials": w_dist_offs,
                "Block Officials": w_blk_offs,
                "Activities Linked": w_acts,
                "Blocks Covered": w_blocks,
                "Status": "Active" if w_acts > 0 else "Pending"
            })

        df_matrix = pd.DataFrame(matrix_rows)
        st.dataframe(df_matrix, use_container_width=True, hide_index=True)

    # =====================================================================
    # TAB 3: BLOCK COVERAGE MATRIX
    # =====================================================================
    with tab3:
        st.subheader("Block-Level Coverage & Onboarding Matrix")
        st.caption("Summary of departmental presence, official deployment, and active works across blocks.")

        block_rows = []
        for b in blocks:
            b_id = b['id']
            b_name = b['block_name']
            
            b_users = [u for u in users_data if str(u.get('block_id')) == str(b_id)]
            b_depts_onboarded = len(set([u.get('department_id') for u in b_users if u.get('department_id')]))
            b_dist_mapped = len([u for u in b_users if u.get('role') == 'district'])
            b_blk_mapped = len([u for u in b_users if u.get('role') == 'block'])
            
            b_reg = df_reg[df_reg['block_id'] == b_id] if not df_reg.empty and 'block_id' in df_reg.columns else pd.DataFrame()
            b_acts_linked = len(b_reg)
            completed_works = len(b_reg[b_reg.get('current_status', '') == 'Completed']) if not b_reg.empty else 0
            ongoing_works = len(b_reg[b_reg.get('current_status', '') == 'Under Implementation']) if not b_reg.empty else 0
            pending_works = len(b_reg[b_reg.get('current_status', '') == 'Planned']) if not b_reg.empty else 0

            block_rows.append({
                "Block": b_name,
                "Departments Onboarded": b_depts_onboarded,
                "District Officials Mapped": b_dist_mapped,
                "Block Officials Mapped": b_blk_mapped,
                "Total Activities": b_acts_linked,
                "Completed": completed_works,
                "Ongoing": ongoing_works,
                "Pending": pending_works
            })

        df_block_cov = pd.DataFrame(block_rows)
        st.dataframe(df_block_cov, use_container_width=True, hide_index=True)

    # =====================================================================
    # TAB 4: ACTIVITY CONVERGENCE
    # =====================================================================
    with tab4:
        st.subheader("Activity ➔ Department / Wing Convergence Matrix")
        st.caption("Shows primary and supporting department allocations across all active master activities.")

        conv_rows = []
        for a in activities:
            a_id = a['id']
            a_name = a['activity_name']
            
            mapped_depts = [m['department_id'] for m in act_dept_mapping if m['activity_id'] == a_id]
            dept_names_str = ", ".join([dept_map.get(d_id, "Unknown") for d_id in mapped_depts]) if mapped_depts else "Unlinked"
            
            exec_count = 0
            if not df_reg.empty and 'activity_description' in df_reg.columns:
                exec_count = df_reg['activity_description'].apply(lambda x: str(a_name).lower() in str(x).lower()).sum()

            conv_rows.append({
                "Activity Name": a_name,
                "Linked Departments": dept_names_str,
                "Total Linkages": len(mapped_depts),
                "Field Executions Captured": exec_count,
                "Status": "Active Convergence" if len(mapped_depts) > 1 else ("Single Dept" if len(mapped_depts) == 1 else "Unlinked")
            })

        df_conv = pd.DataFrame(conv_rows)
        st.dataframe(df_conv, use_container_width=True, hide_index=True)

    # =====================================================================
    # TAB 5: TARGET COMPLIANCE TRACKER
    # =====================================================================
    with tab5:
        st.subheader("🚨 Activity-wise Target Compliance & Alert Tracker")
        st.caption(f"Highlights mismatches between Department/Wing Targets and actual entries for FY {active_fy}.")
        
        compliance_data = []
        if not df_targets.empty:
            for idx, row in df_targets.iterrows():
                d_id = row['department_id']
                w_id = row.get('wing_id')
                act = row['activity']
                target_val = int(row['desired_target'])
                
                d_name = dept_map.get(d_id, "Unknown")
                target_w_id_safe = None if pd.isna(w_id) else w_id
                
                if target_w_id_safe and target_w_id_safe in wing_map:
                    dept_display = f"{d_name} ➔ {wing_map[target_w_id_safe]}"
                else:
                    dept_display = f"{d_name} (Main Dept)"

                contacts = []
                for u in users_data:
                    u_dept = u.get('department_id')
                    u_wing = u.get('wing_id')
                    user_w_id_safe = None if pd.isna(u_wing) else u_wing
                    
                    if u_dept == d_id and user_w_id_safe == target_w_id_safe:
                        contacts.append(u.get('full_name', 'Unknown Officer'))
                
                nodal_display = " | ".join(contacts) if contacts else "⚠️ No Login Assigned"

                entered_count = 0
                if not df_reg.empty:
                    dept_reg = df_reg[df_reg['department_id'] == d_id]
                    if 'activity_description' in dept_reg.columns:
                        entered_count = dept_reg['activity_description'].apply(lambda x: str(act).lower() in str(x).lower()).sum()
                        
                gap = entered_count - target_val
                
                if gap < 0:
                    status = "Less Entered (Needs Update)"
                elif gap > 0:
                    status = "Extra Entered (Mismatch)"
                else:
                    status = "Target Matched"
                    
                compliance_data.append({
                    "Department / Wing": dept_display,
                    "Nodal Person (Login)": nodal_display,
                    "Target Activity": act,
                    "Target Set": target_val,
                    "Entries Captured": entered_count,
                    "Gap": gap,
                    "Status": status
                })

        df_comp = pd.DataFrame(compliance_data)

        def style_compliance(row):
            if row['Status'] in ["Less Entered (Needs Update)", "Extra Entered (Mismatch)"]:
                return ['background-color: #ffebee; color: #b71c1c; font-weight: bold;'] * len(row)
            return ['background-color: #e8f5e9; color: #1b5e20; font-weight: bold;'] * len(row)

        if not df_comp.empty:
            st.dataframe(df_comp.style.apply(style_compliance, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info(f"No Departmental Targets have been set yet for FY {active_fy}.")
