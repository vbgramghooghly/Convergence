import streamlit as st
import os
from utils.db import get_supabase
from utils.theme import apply_global_theme

# ---------- PAGE CONFIG ----------
# Layout MUST be "wide" for our central theme engine to control the website width dynamically.
st.set_page_config(
    page_title="VB-G RAM G Convergence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
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
# This single function handles all global font scaling, background colors, 
# tab bulkiness, and container width across the entire app!
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")
base_font = theme.get("base_font_size", 14)

# ---------- GLOBAL CSS & DYNAMIC SIDEBAR STYLING ----------
# Here we fix the disappearing sidebar toggle button by forcing the header to be visible,
# while keeping the standard Streamlit tools hidden. We also style the sidebar menu dynamically.
st.markdown(f"""
    <style>
        /* --- FIX FOR DISAPPEARING SIDEBAR TOGGLE --- */
        /* Force the header to be visible so the sidebar toggle button (>) NEVER disappears */
        header[data-testid="stHeader"] {{
            visibility: visible !important;
            background-color: transparent !important;
        }}
        
        /* Hide ONLY the specific right-side Streamlit tools (Deploy, GitHub, Options) */
        .stAppToolbar, [data-testid="stToolbar"] {{
            display: none !important;
            visibility: hidden !important;
        }}

        /* --- ULTRA-MODERN SAAS SIDEBAR NAVIGATION --- */
        [data-testid="stSidebar"] [role="radiogroup"] {{
            gap: 6px !important;
        }}
        
        [data-testid="stSidebar"] [role="radiogroup"] label {{
            background-color: transparent !important;
            border: 1px solid transparent !important;
            padding: 10px 14px !important;
            border-radius: 8px !important;
            margin-bottom: 2px !important;
            cursor: pointer !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        [data-testid="stSidebar"] [role="radiogroup"] label p, 
        [data-testid="stSidebar"] [role="radiogroup"] label span {{
            font-size: {base_font}px !important;
            font-weight: 600 !important;
            color: #4B5563 !important;
            transition: color 0.2s ease !important;
        }}
        
        /* Hover State */
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
            background-color: #F3F4F6 !important;
            transform: translateX(3px);
        }}
        
        [data-testid="stSidebar"] [role="radiogroup"] label:hover p,
        [data-testid="stSidebar"] [role="radiogroup"] label:hover span {{
            color: {primary_color} !important;
        }}
        
        /* Active / Selected State Styling */
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
            background-color: {primary_color} !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
        }}
        
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span {{
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }}
    </style>
""", unsafe_allow_html=True)

# ---------- IMPORT ALL MODULES SAFELY ----------
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

# ---------- SIDEBAR HEADER INFO ----------
logo_path = "assets/logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=180)

st.sidebar.title(theme.get("app_name", "VB‑G RAM G Convergence"))
st.sidebar.markdown(f"<span style='color: #4B5563; font-size: {base_font - 2}px;'>FY 2026‑27</span><br><span style='font-size: {base_font - 2}px; color: #6B7280;'>Logged in as:</span><br><b>{user.get('full_name', 'User')}</b> (<span style='color: {primary_color}; font-weight: bold;'>{role.upper()}</span>)", unsafe_allow_html=True)
st.sidebar.divider()

# ---------- SORTED & LOGICAL ROLE‑BASED NAVIGATION ----------
role_pages = {
    "superadmin": [
        "📊 Dashboard",
        "📋 Convergence Register",
        "🚀 Implementation & Targets",
        "🤝 Meetings",
        "📇 User Directory",
        "📈 Reports & Excel",
        "⚙️ Master Data",
        "👥 User Management",
        "🛡️ Audit Log",
        "🎨 UI/UX Controller",
    ],
    "district": [
        "📊 Dashboard",
        "📋 Convergence Register",
        "🚀 Implementation & Targets",
        "🤝 Meetings",
        "📇 User Directory",
        "📈 Reports & Excel",
    ],
    "block": [
        "📊 Dashboard",
        "📋 Convergence Register",
        "🚀 Implementation & Targets",
        "🤝 Meetings",
        "📇 User Directory",
    ],
    "department": [
        "📊 Dashboard",
        "📋 Convergence Register",
        "🚀 Implementation & Targets",
        "🤝 Meetings",
        "📇 User Directory",
        "📈 Reports & Excel",
    ],
}

allowed_pages = role_pages.get(role, [])
if not allowed_pages:
    st.error("Your user role is not configured correctly. Please contact the administrator.")
    logout()

# ---------- NAVIGATION MENU (TOP OF SIDEBAR) ----------
selection = st.sidebar.radio("Navigation", allowed_pages, label_visibility="collapsed")
st.sidebar.divider()

# ---------- ROUTING MAPPING (MATCHING EMOJIS) ----------
menu = {
    "📊 Dashboard": show_dashboard,
    "📋 Convergence Register": show_convergence,
    "🚀 Implementation & Targets": show_implementation,
    "🤝 Meetings": show_meetings,
    "📈 Reports & Excel": show_reports,
    "⚙️ Master Data": show_masterdata,
    "📇 User Directory": show_contacts,
    "👥 User Management": show_users,
    "🛡️ Audit Log": show_audit,
    "🎨 UI/UX Controller": show_ui_ux,
}

# ---------- CALL THE SELECTED PAGE ----------
if selection in menu:
    try:
        menu[selection]()
    except Exception as e:
        st.error(f"An error occurred while loading this page: {e}")
else:
    show_dashboard()

# ---------- ACCOUNT SECURITY & LOGOUT ----------
st.sidebar.markdown("<br>", unsafe_allow_html=True)
st.sidebar.markdown("### 🔐 Account Security")
with st.sidebar.expander("Change My Password"):
    with st.form("change_my_password_form"):
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        submit_pw = st.form_submit_button("Update Password", use_container_width=True)
        
        if submit_pw:
            if len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match.")
            else:
                try:
                    supabase = get_supabase()
                    supabase.auth.update_user({"password": new_pw})
                    st.success("✅ Password updated successfully! Use it on your next login.")
                except Exception as e:
                    st.error(f"Error updating password: {e}")

# Logout Button
st.sidebar.markdown("<br>", unsafe_allow_html=True)
if st.sidebar.button("🔒 Logout", type="secondary", use_container_width=True):
    logout()
