import streamlit as st
import os
from utils.db import get_supabase
from utils.theme import apply_global_theme

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB-G RAM G Portal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed" # Collapsed natively, then killed entirely by CSS
)

# ---------- GLOBAL CSS (STRICT SIDEBAR KILL & NAVBAR STYLING) ----------
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")

st.markdown(f"""
    <style>
        /* 1. COMPLETELY KILL THE SIDEBAR AND TOGGLE BUTTON */
        [data-testid="collapsedControl"] {{ display: none !important; visibility: hidden !important; width: 0 !important; }}
        [data-testid="stSidebar"] {{ display: none !important; visibility: hidden !important; width: 0 !important; }}
        section[data-testid="stSidebar"] {{ display: none !important; width: 0px !important; }}

        /* 2. HIDE STREAMLIT TOP-RIGHT TOOLS */
        [data-testid="stToolbar"], #MainMenu, header[data-testid="stHeader"] {{
            display: none !important;
            visibility: hidden !important;
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
            padding: 10px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border: 1px solid #E2E8F0;
            align-items: center;
            margin-bottom: 20px;
        }}
        
        /* Navbar Buttons (Inactive) */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] button {{
            border-radius: 20px !important;
            border: none !important;
            background-color: transparent !important;
            color: #4A5568 !important;
            font-weight: 600 !important;
            padding: 6px 16px !important;
            transition: all 0.2s ease !important;
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
            box-shadow: 0 4px 10px rgba(0,0,0,0.15) !important;
        }}
        
        /* Profile Popover Button overrides */
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] button {{
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            color: #1E293B !important;
        }}
        .main .block-container > div[data-testid="stVerticalBlock"] > div:first-child > div[data-testid="stHorizontalBlock"] div[data-testid="stPopover"] button:hover {{
            border-color: {primary_color} !important;
        }}
    </style>
""", unsafe_allow_html=True)

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

# ---------- ROUTING & STATE MANAGEMENT ----------
role_pages = {
    "superadmin": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials", "📈 Reports", "⚙️ Master Data", "👥 Users", "🛡️ Audit", "🎨 UI/UX"],
    "district": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials", "📈 Reports"],
    "block": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials"],
    "department": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials", "📈 Reports"],
}

allowed_pages = role_pages.get(role, [])
if not allowed_pages:
    st.error("Invalid role configuration.")
    logout()

# Initialize active page in session state
if 'current_page' not in st.session_state or st.session_state.current_page not in allowed_pages:
    st.session_state.current_page = allowed_pages[0]

# ---------- REUSABLE UI COMPONENTS ----------
def render_profile_menu():
    """Renders the top-right profile popover menu."""
    first_name = user.get('full_name', 'User').split()[0]
    
    with st.popover(f"👤 {first_name} ▾", use_container_width=True):
        st.markdown(f"<span style='font-size: 1.1rem; font-weight: 700; color: {primary_color};'>👤 My Profile</span>", unsafe_allow_html=True)
        st.markdown(f"**Name:** {user.get('full_name')}")
        st.markdown(f"**Role:** {role.upper()}")
        st.markdown(f"**Status:** {'🟢 Active' if user.get('active') else '🔴 Inactive'}")
        
        st.divider()
        st.markdown("**📅 Active Financial Year**")
        if "selected_fy" not in st.session_state:
            st.session_state.selected_fy = "2026-27"
        fy_options = ["2026-27", "2027-28", "2028-29"]
        current_fy_idx = fy_options.index(st.session_state.selected_fy) if st.session_state.selected_fy in fy_options else 0
        st.session_state.selected_fy = st.selectbox("Select FY", fy_options, index=current_fy_idx, label_visibility="collapsed")
        
        st.divider()
        st.markdown("**🔐 Change Password**")
        with st.form("pw_form"):
            new_pw = st.text_input("New Password", type="password", placeholder="Min 6 characters")
            conf_pw = st.text_input("Confirm Password", type="password", placeholder="Match new password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if len(new_pw) < 6: st.error("Min 6 characters.")
                elif new_pw != conf_pw: st.error("Passwords mismatch.")
                else:
                    try:
                        get_supabase().auth.update_user({"password": new_pw})
                        st.success("Updated successfully.")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            logout()

def render_top_navigation():
    """Renders the primary portal navigation bar."""
    col_logo, col_nav, col_profile = st.columns([2.5, 7, 2], vertical_alignment="center")

    # 1. Portal Brand
    with col_logo:
        st.markdown(f"""
        <div style="line-height: 1.2;">
            <span style="font-size: 1.4rem; font-weight: 800; color: {primary_color};">🏛️ VB-G RAM G</span><br>
            <span style="font-size: 0.75rem; font-weight: 700; color: #64748B; letter-spacing: 0.5px; text-transform: uppercase;">Convergence Portal</span>
        </div>
        """, unsafe_allow_html=True)

    # 2. Navigation Pills Array
    with col_nav:
        nav_cols = st.columns(len(allowed_pages))
        for i, page in enumerate(allowed_pages):
            with nav_cols[i]:
                is_active = st.session_state.current_page == page
                if st.button(page, type="primary" if is_active else "secondary", use_container_width=True, key=f"nav_{page}"):
                    st.session_state.current_page = page
                    st.rerun()

    # 3. Profile Popover
    with col_profile:
        render_profile_menu()

# ---------- RENDER THE PORTAL ----------
render_top_navigation()

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

menu = {
    "📊 Dashboard": show_dashboard,
    "📋 Work Entry": show_convergence,
    "🚀 Progress": show_implementation,
    "🤝 Meetings": show_meetings,
    "📈 Reports": show_reports,
    "⚙️ Master Data": show_masterdata,
    "📇 Officials": show_contacts,
    "👥 Users": show_users,
    "🛡️ Audit": show_audit,
    "🎨 UI/UX": show_ui_ux,
}

# Display the active page
if st.session_state.current_page in menu:
    try:
        menu[st.session_state.current_page]()
    except Exception as e:
        st.error(f"An error occurred while loading this page: {e}")
