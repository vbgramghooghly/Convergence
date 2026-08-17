import streamlit as st
import os
from utils.db import get_supabase
from utils.theme import apply_global_theme

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB-G RAM G Portal",
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
        /* 1. STRICTLY KILL SIDEBAR AND HEADER TOOLS */
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

        /* 3. APP LAUNCHER CARDS */
        .app-card {{
            background-color: #FFFFFF; 
            padding: 20px; 
            border-radius: 12px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
            border: 1px solid #E2E8F0;
            text-align: center;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-bottom: 12px;
        }}
        .app-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 15px rgba(0,0,0,0.1);
            border-color: {primary_color};
        }}
        .app-card-title {{
            font-weight: 700; font-size: 1.1rem; color: #1E293B; margin-top: 10px;
        }}
        .app-card-desc {{
            font-size: 0.85rem; color: #64748B; margin-top: 5px;
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
# UPDATED: The first page is now the "Portal Home" landing page
core_pages = ["🏠 Portal Home", "📐 Estimate Builder", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "👥 Officials", "📈 Reports"]
if role == "block":
    core_pages.remove("📈 Reports")

admin_pages = ["📊 Global Analytics", "⚙️ Master Data", "👥 User Management", "🛡️ Audit Logs", "🎨 UI / System Settings"]
allowed_admin = admin_pages if role == "superadmin" else []

if 'current_page' not in st.session_state:
    st.session_state.current_page = core_pages[0]

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

# ---------- STATS FETCHER ----------
@st.cache_data(ttl=60)
def fetch_landing_stats(role, user):
    supabase = get_supabase()
    stats = {}
    try:
        # Base Query
        q_reg = supabase.table("convergence_register").select("*", count="exact")
        q_targets = supabase.table("department_targets").select("*", count="exact")
        q_users = supabase.table("users").select("*", count="exact")
        q_blocks = supabase.table("blocks").select("*", count="exact")
        q_depts = supabase.table("departments").select("*", count="exact")

        # Apply Role Filters
        if role == 'district' and user.get('district_id'):
            q_reg = q_reg.eq("district_id", user['district_id'])
            q_targets = q_targets.eq("district_id", user['district_id'])
        elif role == 'block':
            if user.get('district_id'): q_reg = q_reg.eq("district_id", user['district_id'])
            if user.get('block_id'): q_reg = q_reg.eq("block_id", user['block_id'])
        elif role == 'department':
            if user.get('department_id'):
                q_reg = q_reg.eq("department_id", user['department_id'])
                q_targets = q_targets.eq("department_id", user['department_id'])

        # Execute Counts
        reg_res = q_reg.execute()
        targets_res = q_targets.execute()
        users_res = q_users.execute()
        blocks_res = q_blocks.execute()
        depts_res = q_depts.execute()

        stats['total_works'] = reg_res.count if reg_res.count else 0
        stats['total_targets'] = targets_res.count if targets_res.count else 0
        stats['total_users'] = users_res.count if users_res.count else 0
        stats['total_blocks'] = blocks_res.count if blocks_res.count else 0
        stats['total_depts'] = depts_res.count if depts_res.count else 0

        # Fetch Dataframes for detailed status
        if reg_res.data:
            df_reg = pd.DataFrame(reg_res.data)
            stats['status_counts'] = df_reg['current_status'].value_counts().to_dict() if 'current_status' in df_reg.columns else {}
            stats['converged_fund'] = df_reg['total_converged_fund'].sum() if 'total_converged_fund' in df_reg.columns else 0
        else:
            stats['status_counts'] = {}
            stats['converged_fund'] = 0

    except Exception as e:
        # If the DB permission or connection fails, don't crash the landing page, just show 0s
        stats = {'total_works': 0, 'total_targets': 0, 'total_users': 0, 'total_blocks': 0, 'total_depts': 0, 'status_counts': {}, 'converged_fund': 0}
    
    return stats

# ---------- LANDING PAGE RENDERER ----------
def render_landing_page():
    stats = fetch_landing_stats(role, user)

    st.markdown(f"### 👋 Welcome back, {user.get('full_name', 'User')}")
    
    if role in ['superadmin', 'district', 'block']:
        st.markdown("#### 📊 Governance & Execution Performance Overview")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏢 Active Blocks", stats['total_blocks'])
        col2.metric("🏛️ Departments Enrolled", stats['total_depts'])
        col3.metric("✅ Registered Works", stats['total_works'])
        col4.metric("💰 Converged Fund (₹ Lakhs)", f"{stats['converged_fund']:.2f}")

        st.markdown("---")
        c_status, c_fin = st.columns([2, 1])
        with c_status:
            st.caption("**Work Status Distribution**")
            if stats['status_counts']:
                # Convert to a simple DataFrame for charting
                df_status = pd.DataFrame(list(stats['status_counts'].items()), columns=['Status', 'Count'])
                st.bar_chart(df_status.set_index('Status'))
            else:
                st.info("No registered works found yet.")

    elif role == 'department':
        st.markdown("#### 🏛️ My Department Performance")
        col1, col2, col3 = st.columns(3)
        col1.metric("📋 My Active Targets", stats['total_targets'])
        col2.metric("🛠️ My Registered Works", stats['total_works'])
        col3.metric("💰 Dept. Converged Fund", f"₹{stats['converged_fund']:.2f} L")

    # ========== APP LAUNCHER ==========
    st.markdown("---")
    st.markdown("### 🚀 Launch an Application")
    st.caption("Select a module below to start working.")

    # Create 3 rows of columns for cards
    apps = [
        ("📐", "Estimate Builder", "Create and calculate estimates", "📐 Estimate Builder"),
        ("📋", "Work Entry", "Register individual activities", "📋 Work Entry"),
        ("🚀", "Progress", "Update implementation status", "🚀 Progress"),
        ("🤝", "Meetings", "Manage meeting commitments", "🤝 Meetings"),
        ("👥", "Officials", "View department officials", "👥 Officials"),
        ("📈", "Reports", "Generate statutory reports", "📈 Reports"),
    ]
    
    # Remove Reports if role is block (as per earlier logic)
    if role == "block":
        apps = [a for a in apps if a[3] != "📈 Reports"]

    for i in range(0, len(apps), 3):
        row_cols = st.columns(3)
        group = apps[i:i+3]
        for j, card in enumerate(group):
            icon, title, desc, page_name = card
            with row_cols[j]:
                # We use HTML wrapped inside st.markdown to mimic a clickable tile,
                # then a button below it for actual functionality.
                st.markdown(f"""
                <div class="app-card" onclick="document.getElementById('nav_{page_name}').click()">
                    <div style="font-size: 2.5rem;">{icon}</div>
                    <div class="app-card-title">{title}</div>
                    <div class="app-card-desc">{desc}</div>
                </div>
                """, unsafe_allow_html=True)
                # Hidden button that handles the actual navigation click
                if st.button(f"Launch {title}", key=f"btn_{page_name}", use_container_width=True):
                    st.session_state.current_page = page_name
                    st.rerun()

# ---------- MAIN NAVIGATION LOGIC ----------
def render_top_navigation():
    # No Admin buttons on the main landing page layout, keep it clean
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

    # Only show Nav Bar if not on the landing page
    if st.session_state.current_page != "🏠 Portal Home":
        with cols[1]:
            nav_cols = st.columns(len(core_pages))
            for i, page in enumerate(core_pages):
                with nav_cols[i]:
                    is_active = st.session_state.current_page == page
                    # Using standard button callback here resolves the no-op error
                    if st.button(page, type="primary" if is_active else "secondary", use_container_width=True):
                        st.session_state.current_page = page
                        st.rerun()

        if allowed_admin:
            with cols[2]:
                is_admin_active = st.session_state.current_page in allowed_admin
                with st.popover("⚙️ Admin ▾", use_container_width=True):
                    for page in allowed_admin:
                        btn_type = "primary" if st.session_state.current_page == page else "secondary"
                        if st.button(page, type=btn_type, use_container_width=True):
                            st.session_state.current_page = page
                            st.rerun()

    with cols[-1]:
        render_profile_menu()

# Render the Top Header always
render_top_navigation()

# ---------- IMPORT MODULES & ROUTING ----------
if st.session_state.current_page != "🏠 Portal Home":
    try:
        from modules.analytics import show as show_portal_analytics
        from modules.estimate_builder import show as show_estimate_builder
        from modules.convergence_register import show as show_convergence
        from modules.implementation import show as show_implementation
        from modules.meetings import show as show_meetings
        from modules.reports import show as show_reports
        from modules.master_data import show as show_masterdata
        from modules.users import show as show_users
        from modules.audit import show as show_audit
        from modules.contacts import show as show_contacts
        from modules.ui_ux_controller import show as show_ui_ux
    except Exception as e:
        st.error(f"Error importing modules: {e}")
        st.stop()

    menu = {
        "📐 Estimate Builder": show_estimate_builder,
        "📋 Work Entry": show_convergence,
        "🚀 Progress": show_implementation,
        "🤝 Meetings": show_meetings,
        "👥 Officials": show_contacts,
        "📈 Reports": show_reports,
        "📊 Global Analytics": show_portal_analytics,
        "⚙️ Master Data": show_masterdata,
        "👥 User Management": show_users,
        "🛡️ Audit Logs": show_audit,
        "🎨 UI / System Settings": show_ui_ux,
    }

    if st.session_state.current_page in menu:
        menu[st.session_state.current_page]()
else:
    # Render the Landing Page Stats and Launchpad
    render_landing_page()
