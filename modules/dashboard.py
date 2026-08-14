import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role, get_current_user

def inject_custom_css():
    """Injects custom CSS to hide the Streamlit toolbar (Fork/GitHub buttons)."""
    st.markdown("""
        <style>
        .stAppToolbar { visibility: hidden !important; }
        </style>
        """, unsafe_allow_html=True)

def show():
    # Allow all execution and planning roles
    require_role('superadmin', 'district', 'block', 'department')
    
    inject_custom_css()
    
    user = get_current_user()
    role = user['role']
    supabase = get_supabase()

    st.markdown("<h1 style='color: #1F77B4;'>Convergence Master Dashboard</h1>", unsafe_allow_html=True)
    st.caption("FY 2026-27 | View and monitor real-time physical, financial, and target compliance metrics.")

    # ======================== 1. FETCH MASTER DATA ========================
    depts = supabase.table("departments").select("id,department_name").execute().data or []
    dept_map = {d['id']: d['department_name'] for d in depts}
    
    # Fetch Wings to accurately display Sub-departments
    wings = supabase.table("department_wings").select("id, department_id, wing_name").execute().data or []
    wing_map = {w['id']: w['wing_name'] for w in wings}

    # Fetch Users to identify the assigned Nodal Officers/Logins for Departments & Wings
    nodal_users = supabase.table("users").select("*").eq("role", "department").execute().data or []

    # ======================== 2. FETCH REGISTERS & TARGETS ========================
    q_targets = supabase.table("department_targets").select("*")
    q_reg = supabase.table("convergence_register").select("*")
    
    # Role-based Database Filtering
    if role == 'district':
        q_targets = q_targets.eq("district_id", user['district_id'])
        q_reg = q_reg.eq("district_id", user['district_id'])
    elif role == 'block':
        # Block sees district targets, but only their own register entries
        q_targets = q_targets.eq("district_id", user['district_id'])
        q_reg = q_reg.eq("block_id", user['block_id'])
    elif role == 'department':
        q_targets = q_targets.eq("department_id", user['department_id']).eq("district_id", user['district_id'])
        q_reg = q_reg.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    targets_data = q_targets.execute().data or []
    reg_data = q_reg.execute().data or []
    
    df_targets = pd.DataFrame(targets_data)
    df_reg = pd.DataFrame(reg_data)

    # ======================== 3. CALCULATE KPIs ========================
    total_activities = len(df_reg)
    total_target = df_targets['desired_target'].sum() if not df_targets.empty else 0
    
    dept_fund = df_reg['department_fund'].sum() if not df_reg.empty and 'department_fund' in df_reg.columns else 0.0
    vbg_fund = df_reg['vbgramg_fund'].sum() if not df_reg.empty and 'vbgramg_fund' in df_reg.columns else 0.0
    total_converged = dept_fund + vbg_fund
    
    exp_pd = df_reg['expected_persondays'].sum() if not df_reg.empty and 'expected_persondays' in df_reg.columns else 0
    act_pd = df_reg['persondays_generated'].sum() if not df_reg.empty and 'persondays_generated' in df_reg.columns else 0
    
    comp_pct = (act_pd / exp_pd * 100) if exp_pd > 0 else 0.0
    avg_phys = df_reg['physical_achievement'].mean() if not df_reg.empty and 'physical_achievement' in df_reg.columns else 0.0
    avg_fin = df_reg['financial_achievement'].mean() if not df_reg.empty and 'financial_achievement' in df_reg.columns else 0.0

    # ======================== 4. TABS LAYOUT ========================
    tab1, tab2 = st.tabs(["📊 Dashboard Overview", "📄 Convergence Plan Matrix"])

    with tab1:
        st.subheader("Key Performance Indicators")
        
        # KPI Row 1
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Activities", f"{total_activities}")
        col2.metric("Total Target", f"{total_target}")
        col3.metric("Dept. Fund (₹ Lakhs)", f"₹{dept_fund:,.2f}")
        col4.metric("VB-G RAM G Fund (₹ Lakhs)", f"₹{vbg_fund:,.2f}")
        col5.metric("Total Converged (₹ Lakhs)", f"₹{total_converged:,.2f}")

        # KPI Row 2
        col6, col7, col8, col9, col10 = st.columns(5)
        col6.metric("Expected Persondays", f"{exp_pd:,.0f}")
        col7.metric("Actual Persondays", f"{act_pd:,.0f}")
        col8.metric("Completion %", f"{comp_pct:.1f}%")
        col9.metric("Avg Physical Ach.", f"{avg_phys:.1f}%")
        col10.metric("Avg Financial Ach.", f"₹{avg_fin:,.2f} Lakhs")

        st.markdown("---")
        
        # =====================================================================
        # 🚨 NEW ALERT SECTION: ACTIVITY TARGET vs CAPTURE COMPLIANCE
        # =====================================================================
        st.markdown("<h3 style='color: #D32F2F;'>🚨 Activity-wise Target Compliance & Alert Tracker</h3>", unsafe_allow_html=True)
        st.caption("Highlights mismatches between Department/Wing Targets and actual entries. Displays the responsible Nodal Officer for immediate follow-up.")
        
        compliance_data = []
        if not df_targets.empty:
            for idx, row in df_targets.iterrows():
                d_id = row['department_id']
                w_id = row.get('wing_id')
                act = row['activity']
                target_val = int(row['desired_target'])
                
                # 1. Format Department / Wing Name
                d_name = dept_map.get(d_id, "Unknown")
                target_w_id_safe = None if pd.isna(w_id) else w_id
                
                if target_w_id_safe and target_w_id_safe in wing_map:
                    dept_display = f"{d_name} ➔ {wing_map[target_w_id_safe]}"
                else:
                    dept_display = f"{d_name} (Main Dept)"

                # 2. Map the responsible Nodal Officer(s) tied to this exact Dept & Wing
                contacts = []
                for u in nodal_users:
                    u_dept = u.get('department_id')
                    u_wing = u.get('wing_id')
                    user_w_id_safe = None if pd.isna(u_wing) else u_wing
                    
                    if u_dept == d_id and user_w_id_safe == target_w_id_safe:
                        name_desig = u.get('full_name', 'Unknown Officer')
                        # Check for a phone or mobile column dynamically
                        phone = u.get('phone', u.get('mobile', ''))
                        if phone:
                            contacts.append(f"{name_desig} (☎ {phone})")
                        else:
                            contacts.append(name_desig)
                
                nodal_display = " | ".join(contacts) if contacts else "⚠️ No Login Assigned"

                # 3. Calculate Gap
                entered_count = 0
                if not df_reg.empty:
                    # Filter register strictly to the same department
                    dept_reg = df_reg[df_reg['department_id'] == d_id]
                    # Check if the target activity name is present in the Work Name/Description
                    if 'activity_description' in dept_reg.columns:
                        entered_count = dept_reg['activity_description'].apply(lambda x: str(act).lower() in str(x).lower()).sum()
                        
                gap = entered_count - target_val
                
                # 4. Assign Status Texts
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

        # Styling function to highlight mismatches in RED and matches in GREEN
        def style_compliance(row):
            if row['Status'] in ["Less Entered (Needs Update)", "Extra Entered (Mismatch)"]:
                return ['background-color: #ffebee; color: #b71c1c; font-weight: bold;'] * len(row)
            return ['background-color: #e8f5e9; color: #1b5e20; font-weight: bold;'] * len(row)

        if not df_comp.empty:
            st.dataframe(df_comp.style.apply(style_compliance, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info("No Departmental Targets have been set yet. Check the 'Implementation & Targets' module.")

        st.markdown("---")

        # ======================== 5. VISUALIZATIONS ========================
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
                st.info("No financial data available.")
                
        with col_v2:
            st.markdown("##### Physical Achievement by Department")
            if not df_reg.empty and 'department_id' in df_reg.columns and 'physical_achievement' in df_reg.columns:
                df_phys = df_reg.groupby('department_id')['physical_achievement'].mean().reset_index()
                df_phys['Department'] = df_phys['department_id'].map(dept_map)
                df_phys.set_index('Department', inplace=True)
                st.bar_chart(df_phys['physical_achievement'])
            else:
                st.info("No achievement data available.")

    # ======================== TAB 2: DATA MATRIX ========================
    with tab2:
        st.subheader("Department Convergence Plan Matrix")
        st.caption("Auto-generated convergence plan based on live departmental entries. Updates in real-time.")
        
        if not df_reg.empty:
            df_display = df_reg.copy()
            df_display['Department'] = df_display['department_id'].map(dept_map)
            
            # Map columns cleanly for final display
            df_display.rename(columns={
                'activity_description': 'Work Name',
                'current_status': 'Status',
                'department_fund': 'Dept. Fund (₹ Lakhs)',
                'vbgramg_fund': 'VB-G RAM G Fund (₹ Lakhs)',
                'expected_persondays': 'Expected Persondays'
            }, inplace=True)
            
            # Ensure safe 1s for physical target visual matrix
            df_display['Physical Target'] = 1 
            df_display['Total Fund (₹ Lakhs)'] = df_display['Dept. Fund (₹ Lakhs)'] + df_display['VB-G RAM G Fund (₹ Lakhs)']
            
            cols_to_show = ['Department', 'Work Name', 'Status', 'Physical Target', 'Dept. Fund (₹ Lakhs)', 'VB-G RAM G Fund (₹ Lakhs)', 'Total Fund (₹ Lakhs)', 'Expected Persondays']
            available_cols = [c for c in cols_to_show if c in df_display.columns]
            
            st.dataframe(df_display[available_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No convergence plan data available for your jurisdiction.")
