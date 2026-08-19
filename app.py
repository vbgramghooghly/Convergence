import streamlit as st
import os
import pandas as pd
import io
import re
from utils.db import get_supabase
from utils.theme import apply_global_theme

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB-G RAM G Convergence Hooghly",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------- AUTHENTICATION ----------
from auth.auth import check_password, logout, get_current_user

if not check_password():
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

# ---------- APPLY CENTRAL UI/UX THEME ----------
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")

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

        /* 2. TOP NAVIGATION BAR */
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

# Set default landing page
if 'current_page' not in st.session_state:
    if role == "superadmin":
        st.session_state.current_page = "⚙️ Master Data"
    else:
        st.session_state.current_page = "Home"  # <-- Changed to Home

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
            <span style="font-size: 1.25rem; font-weight: 800; color: {primary_color}; white-space: nowrap;">🏛️ VB-G RAM G</span><br>
            <span style="font-size: 0.65rem; font-weight: 700; color: #64748B; letter-spacing: 0.5px; text-transform: uppercase;">Convergence Portal</span>
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
    st.markdown("#### 📊 District & Block Level Target Compliance Report")

    supabase = get_supabase()
    user = st.session_state

    # Fetch master data
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

    # Determine active FY
    active_fy = st.session_state.get("selected_fy", "2026-27")
    fy_id = None
    for f in fys:
        if f.get('year_name') == active_fy:
            fy_id = f['id']
            break
    if not fy_id:
        st.warning("No active financial year found. Please set one in your profile.")
        return

    # Fetch targets and register data
    q_t = supabase.table("department_targets").select("*").eq("financial_year", active_fy)
    q_r = supabase.table("convergence_register").select("*")
    # Apply role-based filters (if user is block, only their block)
    if user.get('role') == 'block' and user.get('block_id'):
        q_r = q_r.eq("block_id", user['block_id'])
    elif user.get('role') == 'district' and user.get('district_id'):
        q_r = q_r.eq("district_id", user['district_id'])
    elif user.get('role') == 'department' and user.get('department_id'):
        q_r = q_r.eq("department_id", user['department_id'])

    targets = q_t.execute().data or []
    register = q_r.execute().data or []

    if not targets:
        st.info("No targets found for the current financial year.")
        return

    df_targets = pd.DataFrame(targets)
    df_register = pd.DataFrame(register)

    # ---- Helper: token-based matching ----
    def match_activity(work_desc, target_act):
        target_words = set(re.findall(r'\w+', str(target_act).lower()))
        work_words = set(re.findall(r'\w+', str(work_desc).lower()))
        common = target_words.intersection(work_words)
        return len(common) >= 3

    # ---- Compute entries captured per (block, dept, activity) ----
    entries_count = {}
    if not df_register.empty and 'activity_description' in df_register.columns:
        for _, row in df_register.iterrows():
            block_id = row.get('block_id')
            dept_id = row.get('department_id')
            work_desc = row.get('activity_description', '')
            # For each target, check if it matches
            for _, trow in df_targets.iterrows():
                t_block = trow.get('block_id')
                t_dept = trow.get('department_id')
                t_act = trow.get('activity', '')
                if t_block == block_id and t_dept == dept_id and match_activity(work_desc, t_act):
                    key = (block_id, dept_id, t_act)
                    entries_count[key] = entries_count.get(key, 0) + 1

    # ---- Build report table ----
    report_rows = []
    for _, trow in df_targets.iterrows():
        block_id = trow.get('block_id')
        dept_id = trow.get('department_id')
        wing_id = trow.get('wing_id')
        target_act = trow.get('activity', '')
        target_set = trow.get('desired_target', 0)

        key = (block_id, dept_id, target_act)
        entries = entries_count.get(key, 0)

        gap = entries - target_set
        status = "Less Entered (Needs Update)" if gap < 0 else "Extra Entered (Mismatch)" if gap > 0 else "Target Matched"

        dept_name = dept_map.get(dept_id, 'Unknown')
        wing_name = wing_map.get(wing_id, {}).get('wing_name', 'Main Dept.') if wing_id else 'Main Dept.'
        dept_display = f"{dept_name} → {wing_name}" if wing_id else dept_name

        block_name = block_map.get(block_id, 'Unknown')

        report_rows.append({
            "District": "Hooghly",  # fixed for this portal
            "Block": block_name,
            "Department / Wing": dept_display,
            "Target Activity": target_act,
            "Target Set": target_set,
            "Entries Captured": entries,
            "Gap": gap,
            "Status": status
        })

    df_report = pd.DataFrame(report_rows)

    if df_report.empty:
        st.info("No compliance data to display.")
        return

    # ---- Filters ----
    col_f1, col_f2 = st.columns(2)
    blocks_all = sorted(df_report['Block'].unique())
    selected_block = col_f1.selectbox("Filter by Block", options=["All"] + blocks_all)
    depts_all = sorted(df_report['Department / Wing'].unique())
    selected_dept = col_f2.selectbox("Filter by Department / Wing", options=["All"] + depts_all)

    if selected_block != "All":
        df_report = df_report[df_report['Block'] == selected_block]
    if selected_dept != "All":
        df_report = df_report[df_report['Department / Wing'] == selected_dept]

    # ---- KPIs ----
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

    # ---- Display table with styling ----
    def style_rows(row):
        if row['Status'] != "Target Matched":
            return ['background-color: #ffebee; color: #b71c1c; font-weight: bold;'] * len(row)
        return ['background-color: #e8f5e9; color: #1b5e20; font-weight: bold;'] * len(row)

    st.dataframe(
        df_report.style.apply(style_rows, axis=1),
        use_container_width=True,
        hide_index=True
    )

    # ---- Export to Excel ----
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_report.to_excel(writer, index=False, sheet_name='Compliance Report')
    st.download_button(
        "📥 Download Report as Excel",
        data=buffer.getvalue(),
        file_name=f"compliance_report_{active_fy}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
        # Fallback (should not happen)
        st.info("Welcome to the VB-G RAM G Convergence Portal. Please select a module from the navigation bar.")
except Exception as e:
    st.error(f"Error loading module: {e}")
    st.info("If this is a database permission error, please make sure to run the SQL fixes provided in the instructions.")
