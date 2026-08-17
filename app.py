import streamlit as st
import os
import pandas as pd
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

        /* 3. APP LAUNCHER BUTTON STYLES */
        .app-card {{
            background-color: #FFFFFF; 
            padding: 20px; 
            border-radius: 12px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
            border: 1px solid #E2E8F0;
            text-align: center;
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
core_pages = ["🏠 Portal Home", "👥 Officials", "🚀 Progress", "🤝 Meetings", "📋 Work Entry", "📈 Reports", "📐 Estimate Builder"]
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

    # ------------------ FIX: REMOVED CONDITIONAL CHECK ------------------
    # The navbar now ALWAYS renders, regardless of the current page.
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
            is_admin_active = st.session_state.current_page in allowed_admin
            with st.popover("⚙️ Admin ▾", use_container_width=True):
                for page in allowed_admin:
                    btn_type = "primary" if st.session_state.current_page == page else "secondary"
                    if st.button(page, type=btn_type, use_container_width=True):
                        st.session_state.current_page = page
                        st.rerun()

    with cols[-1]:
        render_profile_menu()

render_top_navigation()

# ---------- LANDING PAGE STATS ----------
def render_landing_page():
    try:
        from modules.analytics import show as show_portal_analytics
        show_portal_analytics()
    except Exception:
        st.error("Failed to load Portal Analytics. Please run the SQL fixes provided.")

# ---------- IMPORT MODULES & ROUTING (DEFERRED TO AVOID CACHE POISON) ----------
if st.session_state.current_page != "🏠 Portal Home":
    try:
        if st.session_state.current_page == "📐 Estimate Builder":
            from modules.estimate_builder import show as show_estimate_builder
            show_estimate_builder()
        elif st.session_state.current_page == "📋 Work Entry":
            from modules.convergence_register import show as show_convergence
            show_convergence()
        elif st.session_state.current_page == "🚀 Progress":
            from modules.implementation import show as show_implementation
            show_implementation()
        elif st.session_state.current_page == "🤝 Meetings":
            from modules.meetings import show as show_meetings
            show_meetings()
        elif st.session_state.current_page == "👥 Officials":
            from modules.contacts import show as show_contacts
            show_contacts()
        elif st.session_state.current_page == "📈 Reports":
            from modules.reports import show as show_reports
            show_reports()
        elif st.session_state.current_page == "📊 Global Analytics":
            from modules.analytics import show as show_portal_analytics
            show_portal_analytics()
        elif st.session_state.current_page == "⚙️ Master Data":
            from modules.master_data import show as show_masterdata
            show_masterdata()
        elif st.session_state.current_page == "👥 User Management":
            from modules.users import show as show_users
            show_users()
        elif st.session_state.current_page == "🛡️ Audit Logs":
            from modules.audit import show as show_audit
            show_audit()
        elif st.session_state.current_page == "🎨 UI / System Settings":
            from modules.ui_ux_controller import show as show_ui_ux
            show_ui_ux()
    except Exception as e:
        st.error(f"Error loading module: {e}")
        st.info("If this is a database permission error, please make sure to run the SQL fixes provided in the instructions.")
else:
    render_landing_page()
