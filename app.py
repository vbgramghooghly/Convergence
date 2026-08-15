import streamlit as st
import os
from utils.db import get_supabase
from utils.theme import apply_global_theme

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB-G RAM G Convergence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- GLOBAL CSS (SAFE) ----------
# 1. We ONLY hide the right-side Streamlit tools.
# 2. We turn the st.radio into a modern row of Shortcut Buttons.
st.markdown("""
    <style>
        /* Hide Deploy, GitHub, and Options menu */
        [data-testid="stToolbar"] { display: none !important; }
        #MainMenu { display: none !important; }
        
        /* Reduce top padding to bring our custom panel higher */
        .block-container { padding-top: 2rem !important; }
        
        /* Style the top radio navigation to look like shortcut buttons */
        div.row-widget.stRadio > div {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        div.row-widget.stRadio > div > label {
            background-color: transparent;
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid #1F77B4;
            cursor: pointer;
        }
        div.row-widget.stRadio > div > label:hover {
            background-color: #F0F4F8;
        }
        div.row-widget.stRadio > div > label:has(input:checked) {
            background-color: #1F77B4;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        div.row-widget.stRadio > div > label:has(input:checked) p {
            color: #FFFFFF !important;
            font-weight: bold;
        }
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

# ---------- APPLY CENTRAL UI/UX THEME ----------
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")

# ---------- CUSTOM TOP PANEL (PORTAL NAME & SHORTCUTS) ----------
c_logo, c_nav = st.columns([1, 4])
with c_logo:
    st.markdown(f"<h3 style='color: {primary_color}; margin-top: 0; padding-top: 0;'>VB-G RAM G Portal</h3>", unsafe_allow_html=True)

# Define Roles
role_pages = {
    "superadmin": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials", "📈 Reports", "⚙️ Master Data", "👥 Users", "🛡️ Audit", "🎨 UI/UX"],
    "district": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials", "📈 Reports"],
    "block": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials"],
    "department": ["📊 Dashboard", "📋 Work Entry", "🚀 Progress", "🤝 Meetings", "📇 Officials", "📈 Reports"],
}
allowed_pages = role_pages.get(role, [])

with c_nav:
    # This renders as a sleek horizontal row of buttons thanks to the CSS above!
    selection = st.radio("Nav", allowed_pages, horizontal=True, label_visibility="collapsed")

st.markdown("---")

# ---------- SIDEBAR (SETTINGS, FY, PROFILE) ----------
logo_path = "assets/logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=180)

st.sidebar.markdown(f"**{user.get('full_name', 'User')}**<br><span style='color: {primary_color}; font-size: 0.9em;'>{role.upper()}</span>", unsafe_allow_html=True)
st.sidebar.divider()

st.sidebar.markdown("### 📅 Financial Year")
if "selected_fy" not in st.session_state:
    st.session_state.selected_fy = "2026-27"
fy_options = ["2026-27", "2027-28", "2028-29"]
current_fy_idx = fy_options.index(st.session_state.selected_fy) if st.session_state.selected_fy in fy_options else 0
st.session_state.selected_fy = st.sidebar.selectbox("Active FY", fy_options, index=current_fy_idx, label_visibility="collapsed")

st.sidebar.divider()
st.sidebar.markdown("### 🔐 Settings")
with st.sidebar.expander("Change Password"):
    with st.form("change_pw_form"):
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("Update", use_container_width=True):
            if len(new_pw) < 6: st.error("Min 6 characters.")
            elif new_pw != confirm_pw: st.error("No match.")
            else:
                get_supabase().auth.update_user({"password": new_pw})
                st.success("Updated!")

st.sidebar.markdown("<br>", unsafe_allow_html=True)
if st.sidebar.button("🔒 Logout", type="secondary", use_container_width=True):
    logout()

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
    "📊 Dashboard": show_dashboard, "📋 Work Entry": show_convergence, "🚀 Progress": show_implementation,
    "🤝 Meetings": show_meetings, "📈 Reports": show_reports, "⚙️ Master Data": show_masterdata,
    "📇 Officials": show_contacts, "👥 Users": show_users, "🛡️ Audit": show_audit, "🎨 UI/UX": show_ui_ux,
}

if selection in menu:
    menu[selection]()
else:
    show_dashboard()
