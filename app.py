import streamlit as st
import os
import pandas as pd
import io
import re
from utils.db import get_supabase
from utils.theme import load_theme, get_css 

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB G RAM G Convergence Hooghly",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------- AUTHENTICATION & SESSION LOCK ----------
from auth.auth import check_password, logout, get_current_user, check_active_session

if not check_password():
    st.stop()

# ENFORCE GLOBAL SINGLE SESSION
if not check_active_session():
    st.stop()

user = get_current_user()
if not user or 'role' not in user:
    st.error("Authentication session error. Please log in again.")
    logout()
    st.stop()

# =========================================================================
# SYNC LOGGED-IN USER DETAILS TO GLOBAL SESSION
# =========================================================================
if user:
    st.session_state['full_name'] = user.get('full_name', 'User')
    st.session_state['district_id'] = user.get('district_id')
    st.session_state['role'] = user.get('role')
    st.session_state['department_id'] = user.get('department_id')
    st.session_state['block_id'] = user.get('block_id')
# =========================================================================

role = user['role']

# ---------- APPLY GLOBAL THEME ----------
theme = load_theme()
st.markdown(f"<style>{get_css(theme)}</style>", unsafe_allow_html=True)
primary_color = theme.get('primary_color', '#0F4C81')

# ---------- GLOBAL CSS (ENTERPRISE NAVBAR & LANDING PAGE STYLES) ----------
st.markdown(f"""
    <style>
        [data-testid="collapsedControl"], [data-testid="stSidebar"], section[data-testid="stSidebar"] {{
            display: none !important; visibility: hidden !important; width: 0px !important;
        }}
        [data-testid="stToolbar"], header[data-testid="stHeader"] {{
            display: none !important; visibility: hidden !important; height: 0px !important;
        }}
        .block-container {{
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            max-width: 98% !important;
        }}
        /* TOP NAVIGATION BAR */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] {{
            background: #FFFFFF;
            border-bottom: 1px solid #E2E8F0;
            padding: 4px 16px;
            align-items: center;
            margin-bottom: 16px;
            min-height: 56px;
            flex-wrap: nowrap !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button {{
            border-radius: 20px !important;
            border: none !important;
            background-color: transparent !important;
            color: #4A5568 !important;
            font-weight: 600 !important;
            padding: 4px 12px !important;
            min-height: 36px !important;
            transition: all 0.2s ease !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button:hover {{
            background-color: #F0F4F8 !important;
            color: {primary_color} !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button[kind="primary"] {{
            background-color: {primary_color} !important;
            color: #FFFFFF !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button[kind="primary"] p {{
            color: #FFFFFF !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] button {{
            background-color: transparent !important;
            border: 1px solid transparent !important;
            color: #1E293B !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] button:hover {{
            background-color: #F1F5F9 !important;
        }}
        /* Tab styling */
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
            gap: 24px; border-bottom: 1px solid #E2E8F0; padding-bottom: 0px;
        }}
        div[data-testid="stTabs"] button[role="tab"] {{
            padding: 8px 4px !important; font-weight: 600 !important; color: #64748B !important;
            background-color: transparent !important; border: none !important;
            border-bottom: 3px solid transparent !important; border-radius: 0px !important; font-size: 14px !important;
        }}
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
            color: {primary_color} !important; border-bottom: 3px solid {primary_color} !important;
        }}
        /* Info boxes for home page */
        .info-box {{
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 12px 16px;
            height: 100%;
        }}
        .info-box h5 {{
            color: {primary_color};
            font-weight: 700;
            margin: 0 0 8px 0;
            font-size: 14px;
            border-bottom: 1px solid #E2E8F0;
            padding-bottom: 4px;
        }}
        .info-box ul {{ list-style: none; padding: 0; margin: 0; }}
        .info-box ul li {{ font-size: 13px; padding: 2px 0; color: #1E293B; display: flex; align-items: center; }}
        .info-box ul li::before {{ content: "•"; color: {primary_color}; font-weight: bold; margin-right: 6px; }}
        .whatsapp-link {{ color: #25D366; font-weight: 600; text-decoration: none; }}
        .whatsapp-link:hover {{ text-decoration: underline; }}
    </style>
""", unsafe_allow_html=True)

# ---------- ROUTING & STATE MANAGEMENT ----------
core_pages = ["Home", "Officials", "Progress", "Meetings", "Work Entry", "Reports", "Estimate"]
if role == "block":
    core_pages.remove("Reports")

admin_pages = [
    "Master Data", 
    "Estimate Master Data", 
    "User Management", 
    "Audit Logs", 
    "UI Settings"
]
allowed_admin = admin_pages if role == "superadmin" else []

if 'current_page' not in st.session_state:
    if role == "superadmin":
        st.session_state.current_page = "⚙️ Master Data"
    else:
        st.session_state.current_page = "Home"

# ---------- REUSABLE UI COMPONENTS ----------
def render_profile_menu():
    first_name = user.get('full_name', 'User').split()[0]
    with st.popover(f"👤 {first_name} ▾", use_container_width=True):
        st.markdown(f"<span style='font-size: 1rem; font-weight: 700; color: {primary_color};'>👤 My Profile</span>", unsafe_allow_html=True)
        st.caption(f"{user.get('full_name')} | {role.upper()}")
        st.divider()
        st.markdown("**📅 Active Financial Year**")
        if "selected_fy" not in st.session_state: st.session_state.selected_fy = "2026-27"
        fy_options = ["2026-27", "2027-28", "2028-29"]
        current_fy_idx = fy_options.index(st.session_state.selected_fy) if st.session_state.selected_fy in fy_options else 0
        st.session_state.selected_fy = st.selectbox("Select FY", fy_options, index=current_fy_idx, label_visibility="collapsed")
        st.divider()
        st.markdown("**🔐 Security**")
        with st.form("pw_form"):
            new_pw = st.text_input("New Password", type="password", placeholder="Min 6 chars")
            conf_pw = st.text_input("Confirm Password", type="password", placeholder="Match new password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if len(new_pw) < 6: st.error("Min 6 chars.")
                elif new_pw != conf_pw: st.error("Mismatch.")
                else:
                    try:
                        get_supabase().auth.update_user({"password": new_pw})
                        st.success("Updated.")
                    except Exception as e: st.error(f"Error: {e}")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True, type="primary"): logout()

def handle_nav(page_name):
    st.session_state.current_page = page_name
    st.rerun()

def render_top_navigation():
    if allowed_admin:
        cols = st.columns([2.2, 7, 1.2, 1.2], vertical_alignment="center")
    else:
        cols = st.columns([2.2, 8.3, 1.2], vertical_alignment="center")

    with cols[0]:
        st.markdown(f"""
        <div style="line-height: 1.1;">
            <span style="font-size: 2.00rem; font-weight: 1200; color: {primary_color}; white-space: nowrap;">VB G RAM G</span><br>
            <span style="font-size: 0.70rem; font-weight: 700; color: #64748B; letter-spacing: 0.5px; text-transform: uppercase;">District Convergence Portal</span>
        </div>
        """, unsafe_allow_html=True)

    with cols[1]:
        nav_cols = st.columns(len(core_pages))
        for i, page in enumerate(core_pages):
            with nav_cols[i]:
                is_active = st.session_state.current_page == page
                if st.button(page, type="primary" if is_active else "secondary", use_container_width=True):
                    st.session_state.current_page = page
                    st.rerun()

    if allowed_admin:
        with cols[2]:
            with st.popover("⚙️ Admin ▾", use_container_width=True):
                for page in allowed_admin:
                    btn_type = "primary" if st.session_state.current_page == page else "secondary"
                    if st.button(page, type=btn_type, use_container_width=True):
                        st.session_state.current_page = page
                        st.rerun()

    with cols[-1]:
        render_profile_menu()

render_top_navigation()

# ============================================================
# HOME PAGE – DISTRICT & BLOCK LEVEL TARGET COMPLIANCE REPORT
# ============================================================
def show_home():
    st.markdown("#### 📊 At a Glance Report")

    supabase = get_supabase()
    user_session = st.session_state
    role = user_session.get('role')
    district_id = user_session.get('district_id')
    block_id = user_session.get('block_id')
    department_id = user_session.get('department_id')

    @st.cache_data(ttl=600)
    def fetch_master():
        departments = supabase.table("departments").select("id,department_name").execute().data or []
        wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []
        blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data or []
        fys = supabase.table("financial_years").select("*").eq("active", True).execute().data or []
        return departments, wings, blocks, fys

    departments, wings, blocks, fys = fetch_master()
    dept_map = {d['id']: d['department_name'] for d in departments}
    wing_map = {w['id']: w for w in wings}
    block_map = {b['id']: b['block_name'] for b in blocks}
    block_name_to_id = {b['block_name']: b['id'] for b in blocks}

    active_fy = st.session_state.get("selected_fy", "2026-27")
    fy_id = None
    for f in fys:
        if f.get('year_name') == active_fy:
            fy_id = f['id']
            break
            
    if not fy_id:
        st.warning("No active financial year found. Please set one in your profile.")
    else:
        if role == 'block' and block_id:
            block_list = [b for b in blocks if b['id'] == block_id]
        elif role in ['district', 'department'] and district_id:
            block_list = [b for b in blocks if b['district_id'] == district_id]
        else:
            block_list = blocks

        q_t = supabase.table("department_targets").select("*").eq("financial_year", active_fy)
        if role == 'department' and department_id:
            q_t = q_t.eq("department_id", department_id)
        elif role == 'district' and district_id:
            q_t = q_t.eq("district_id", district_id)
        elif role == 'block' and block_id:
            q_t = q_t.eq("block_id", block_id)
        targets = q_t.execute().data or []

        if not targets:
            st.info("No targets found for the current financial year.")
        else:
            q_r = supabase.table("convergence_register").select("*").eq("financial_year_id", fy_id)
            if role == 'block' and block_id:
                q_r = q_r.eq("block_id", block_id)
            elif role == 'district' and district_id:
                q_r = q_r.eq("district_id", district_id)
            elif role == 'department' and department_id:
                q_r = q_r.eq("department_id", department_id)
            register = q_r.execute().data or []

            df_targets = pd.DataFrame(targets)
            df_register = pd.DataFrame(register)

            def match_activity(work_desc, target_act):
                target_words = set(re.findall(r'\w+', str(target_act).lower()))
                work_words = set(re.findall(r'\w+', str(work_desc).lower()))
                common = target_words.intersection(work_words)
                return len(common) >= 3

            entries_count = {}
            if not df_register.empty and 'activity_description' in df_register.columns:
                for _, row in df_register.iterrows():
                    reg_block = row.get('block_id')
                    reg_dept = row.get('department_id')
                    reg_wing = row.get('wing_id')
                    work_desc = row.get('activity_description', '')
                    for _, trow in df_targets.iterrows():
                        t_dept = trow.get('department_id')
                        t_wing = trow.get('wing_id')
                        t_act = trow.get('activity', '')
                        if reg_dept == t_dept and (reg_wing == t_wing or (reg_wing is None and t_wing is None)):
                            if match_activity(work_desc, t_act):
                                key = (reg_block, t_dept, t_wing, t_act)
                                entries_count[key] = entries_count.get(key, 0) + 1

            report_rows = []
            for _, trow in df_targets.iterrows():
                t_block = trow.get('block_id')
                t_dept = trow.get('department_id')
                t_wing = trow.get('wing_id')
                t_act = trow.get('activity', '')
                t_target = trow.get('desired_target', 0)

                dept_name = dept_map.get(t_dept, 'Unknown')
                wing_name = wing_map.get(t_wing, {}).get('wing_name', 'Main Dept.') if t_wing else 'Main Dept.'
                dept_display = f"{dept_name} → {wing_name}" if t_wing else dept_name
                block_name = block_map.get(t_block, 'All Blocks') if t_block else 'All Blocks'

                key = (t_block, t_dept, t_wing, t_act)
                entries = entries_count.get(key, 0)
                gap = entries - t_target
                status = "Less Entered (Needs Update)" if gap < 0 else "Extra Entered (Mismatch)" if gap > 0 else "Target Matched"

                report_rows.append({
                    "District": "Hooghly",
                    "Block": block_name,
                    "Department / Wing": dept_display,
                    "Target Activity": t_act,
                    "Target Set": t_target,
                    "Entries Captured": entries,
                    "Gap": gap,
                    "Status": status
                })

            df_report = pd.DataFrame(report_rows)

            if df_report.empty:
                st.info("No compliance data to display.")
            else:
                col_f1, col_f2 = st.columns(2)
                blocks_all = sorted(df_report['Block'].unique())
                selected_block = col_f1.selectbox("Filter by Block", options=["All"] + blocks_all)
                depts_all = sorted(df_report['Department / Wing'].unique())
                selected_dept = col_f2.selectbox("Filter by Department / Wing", options=["All"] + depts_all)

                if selected_block != "All":
                    df_report = df_report[df_report['Block'] == selected_block]
                if selected_dept != "All":
                    df_report = df_report[df_report['Department / Wing'] == selected_dept]

                total_targets = df_report['Target Set'].sum()
                total_entries = df_report['Entries Captured'].sum()
                total_gap = total_entries - total_targets
                compliance_pct = (total_entries / total_targets * 100) if total_targets > 0 else 0

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Targets", f"{int(total_targets):,}")
                col2.metric("Total Entries Captured", f"{int(total_entries):,}")
                col3.metric("Total Gap", f"{int(total_gap):,}", delta=total_gap)
                col4.metric("Compliance", f"{compliance_pct:.1f}%")

                st.markdown("<br>", unsafe_allow_html=True)

                def style_rows(row):
                    if row['Status'] != "Target Matched":
                        return ['background-color: #ffebee; color: #b71c1c; font-weight: bold;'] * len(row)
                    return ['background-color: #e8f5e9; color: #1b5e20; font-weight: bold;'] * len(row)

                st.dataframe(
                    df_report.style.apply(style_rows, axis=1),
                    use_container_width=True,
                    hide_index=True
                )

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_report.to_excel(writer, index=False, sheet_name='Compliance Report')
                st.download_button(
                    "📥 Download Report as Excel",
                    data=buffer.getvalue(),
                    file_name=f"compliance_report_{active_fy}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    st.markdown("---")
    st.markdown("#### 📌 Quick Reference")
    col_dep, col_block, col_dist, col_error = st.columns(4)

    with col_dep:
        st.markdown(f"""
        <div class="info-box">
            <h5>🏛️ DEPARTMENT</h5>
            <ul>
                <li>Target Entry</li>
                <li>Linked Work Entry &amp; Progress</li>
                <li>Meeting Commitments</li>
                <li>Contact Directory</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_block:
        st.markdown(f"""
        <div class="info-box">
            <h5>📌 BLOCK</h5>
            <ul>
                <li>Convergence Plan</li>
                <li>Block Meeting &amp; Attendance</li>
                <li>General / Department-wise Targets</li>
                <li>Support Department Progress</li>
                <li>Contact Directory</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_dist:
        st.markdown(f"""
        <div class="info-box">
            <h5>📍 DISTRICT</h5>
            <ul>
                <li>Convergence Plan</li>
                <li>District Meeting &amp; Attendance</li>
                <li>General / Department-wise Targets</li>
                <li>Scheme Planning &amp; Execution</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_error:
        st.markdown(f"""
        <div class="info-box" style="border-left: 4px solid #EF4444;">
            <h5 style="color: #DC2626;">⚠️ SYSTEM ERROR</h5>
            <ul>
                <li>📸 Take Screenshot</li>
                <li>📱 <a href="https://wa.me/919804939270" target="_blank" class="whatsapp-link">WhatsApp: 9804939270</a></li>
                <li>📝 Mention Brief Problem Description</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        """
        <div style='text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #E2E8F0; color: #64748B; font-size: 14px; font-weight: 600;'>
            Hooghly District Administration || District VB GRAM G Cell || Mail : nodal.hooghly@gmail.com
        </div>
        """, 
        unsafe_allow_html=True
    )

# ---------- IMPORT MODULES & ROUTING ----------
try:
    from modules.estimate_master_data import show as show_estimate_master_data

    if st.session_state.current_page == "Home":
        show_home()
    elif st.session_state.current_page == "Estimate":
        from modules.estimate_builder import show as show_estimate_builder
        show_estimate_builder()
    elif st.session_state.current_page == "Work Entry":
        from modules.convergence_register import show as show_convergence
        show_convergence()
    elif st.session_state.current_page == "Progress":
        from modules.implementation import show as show_implementation
        show_implementation()
    elif st.session_state.current_page == "Meetings":
        from modules.meetings import show as show_meetings
        show_meetings()
    elif st.session_state.current_page == "Officials":
        from modules.contacts import show as show_contacts
        show_contacts()
    elif st.session_state.current_page == "Reports":
        from modules.reports import show as show_reports
        show_reports()
    elif st.session_state.current_page == "Master Data":
        from modules.master_data import show as show_masterdata
        show_masterdata()
    elif st.session_state.current_page == "Estimate Master Data":
        show_estimate_master_data()
    elif st.session_state.current_page == "User Management":
        from modules.users import show as show_users
        show_users()
    elif st.session_state.current_page == "Audit Logs":
        from modules.audit import show as show_audit
        show_audit()
    elif st.session_state.current_page == "UI Settings":
        from modules.ui_ux_controller import show as show_ui_ux
        show_ui_ux()
    else:
        st.info("Welcome to the VB-G RAM G Convergence Portal, a unified platform for planning, coordinating, monitoring, and managing convergence initiatives and departmental interventions")
except Exception as e:
    st.error(f"Error loading module: {e}")
    st.info("If this is a database permission error, please make sure to run the SQL fixes provided in the instructions.")
