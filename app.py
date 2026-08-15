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

role = user['role']

# ---------- APPLY CENTRAL UI/UX THEME ----------
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")

# ---------- GLOBAL CSS (STRICT SIDEBAR KILL & NAVBAR STYLING) ----------
st.markdown(f"""
    <style>
        /* 1. COMPLETELY KILL THE SIDEBAR AND TOGGLE BUTTON */
        [data-testid="collapsedControl"], [data-testid="stSidebar"], section[data-testid="stSidebar"] {{
            display: none !important; visibility: hidden !important; width: 0px !important;
        }}

        /* 2. HIDE STREAMLIT TOP-RIGHT TOOLS & NATIVE HEADER */
        [data-testid="stToolbar"], #MainMenu, header[data-testid="stHeader"] {{
            display: none !important; visibility: hidden !important; height: 0px !important;
        }}

        /* 3. REDUCE WASTED TOP SPACE */
        .block-container {{
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 98% !important;
        }}

        /* 4. PREMIUM TOP NAVIGATION BAR STYLING */
        /* Targets the very first horizontal block in the app (our Navbar) */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] {{
            background: #FFFFFF;
            padding: 8px 16px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #E2E8F0;
            align-items: center;
            margin-bottom: 10px;
            min-height: 56px;
        }}
        
        /* Navbar Buttons (Inactive) */
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
        
        /* Force single line text (No Wrapping) */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button p {{
            white-space: nowrap !important;
            margin: 0 !important;
            font-size: 14px !important;
        }}
        
        /* Navbar Buttons (Hover) */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button:hover {{
            background-color: #F0F4F8 !important;
            color: {primary_color} !important;
        }}
        
        /* Navbar Button (Active State - Primary) */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button[kind="primary"] {{
            background-color: {primary_color} !important;
            color: #FFFFFF !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15) !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button[kind="primary"] p {{
            color: #FFFFFF !important;
        }}
        
        /* Profile & Admin Popover Button overrides */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] button {{
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            color: #1E293B !important;
            min-height: 36px !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] button:hover {{
            border-color: {primary_color} !important;
        }}

        /* 5. SLIM SECONDARY NAVIGATION (TABS) */
        div[data-testid="stTabs"] button[role="tab"] {{
            padding: 8px 16px !important;
            font-weight: 600 !important;
            color: #64748B !important;
            background-color: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            border-radius: 0px !important;
        }}
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
            color: {primary_color} !important;
            border-bottom: 2px solid {primary_color} !important;
            background-color: #F8FAFC !important;
        }}
    </style>
""", unsafe_allow_html=True)

# ---------- ROUTING & STATE MANAGEMENT ----------
# Strictly exactly 6 primary core modules
core_pages = ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "👥 Officials", "📈 Reports"]
admin_pages = ["⚙️ Master Data", "👥 User Management", "🛡️ Audit Logs", "🎨 UI / System Settings"]

# Filter based on role
allowed_primary = core_pages.copy()
if role == "block":
    allowed_primary.remove("📈 Reports")

allowed_admin = admin_pages if role == "superadmin" else []

# Initialize active page in session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = allowed_primary[0]

# Restrict manual navigation bypass
if st.session_state.current_page not in allowed_primary and st.session_state.current_page not in allowed_admin:
    st.session_state.current_page = allowed_primary[0]

# ---------- REUSABLE UI COMPONENTS ----------
def render_profile_menu():
    """Renders the top-right compact profile popover."""
    first_name = user.get('full_name', 'User').split()[0]
    
    with st.popover(f"👤 {first_name} ▾", use_container_width=True):
        st.markdown(f"<span style='font-size: 1.1rem; font-weight: 700; color: {primary_color};'>👤 My Profile</span>", unsafe_allow_html=True)
        st.markdown(f"**Name:** {user.get('full_name')}")
        st.markdown(f"**Role:** {role.upper()}")
        
        st.divider()
        st.markdown("**📅 Active Financial Year**")
        if "selected_fy" not in st.session_state:
            st.session_state.selected_fy = "2026-27"
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
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            logout()

def render_top_navigation():
    """Renders the single-line primary portal navigation bar."""
    
    # Adjust layout columns dynamically based on whether the Admin menu is required
    if allowed_admin:
        col_brand, col_nav, col_admin, col_profile = st.columns([2.5, 6, 1.2, 1.5], vertical_alignment="center")
    else:
        col_brand, col_nav, col_profile = st.columns([2.5, 7.5, 1.5], vertical_alignment="center")

    # 1. Portal Brand
    with col_brand:
        st.markdown(f"""
        <div style="line-height: 1.1; margin-top: 2px;">
            <span style="font-size: 1.2rem; font-weight: 800; color: {primary_color};">🏛️ VB-G RAM G</span><br>
            <span style="font-size: 0.65rem; font-weight: 700; color: #64748B; letter-spacing: 0.5px; text-transform: uppercase;">Convergence Portal</span>
        </div>
        """, unsafe_allow_html=True)

    # 2. Navigation Array (Core Modules Only)
    with col_nav:
        nav_cols = st.columns(len(allowed_primary))
        for i, page in enumerate(allowed_primary):
            with nav_cols[i]:
                is_active = st.session_state.current_page == page
                if st.button(page, type="primary" if is_active else "secondary", use_container_width=True, key=f"nav_{page}"):
                    st.session_state.current_page = page
                    st.rerun()

    # 3. Hidden Admin Popover (Only for Authorized Users)
    if allowed_admin:
        with col_admin:
            is_admin_active = st.session_state.current_page in allowed_admin
            with st.popover("⚙️ Admin ▾", use_container_width=True):
                for page in allowed_admin:
                    btn_type = "primary" if st.session_state.current_page == page else "secondary"
                    if st.button(page, type=btn_type, use_container_width=True, key=f"nav_admin_{page}"):
                        st.session_state.current_page = page
                        st.rerun()

    # 4. Profile Popover
    with col_profile:
        render_profile_menu()

# ---------- RENDER THE PORTAL ----------
render_top_navigation()

# Subtle divider below navigation removed to keep things compact
st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ---------- IMPORT MODULES & ROUTING ----------
try:
    from modules.dashboard import show as show_dashboard
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

# Map the visual menu names directly to the function calls
menu = {
    "📊 Dashboard": show_dashboard,
    "📋 Work Entry": show_convergence,
    "🚀 Progress": show_implementation,
    "🤝 Meetings": show_meetings,
    "👥 Officials": show_contacts,
    "📈 Reports": show_reports,
    "⚙️ Master Data": show_masterdata,
    "👥 User Management": show_users,
    "🛡️ Audit Logs": show_audit,
    "🎨 UI / System Settings": show_ui_ux,
}

# Display the active page securely
if st.session_state.current_page in menu:
    try:
        menu[st.session_state.current_page]()
    except Exception as e:
        st.error(f"An error occurred while loading this page: {e}")
