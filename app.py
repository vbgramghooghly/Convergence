import streamlit as st
import os

# ---------- PAGE CONFIG ----------
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

# ---------- IMPORT ALL MODULES SAFELY ----------
try:
    from modules.dashboard import show as show_dashboard
    from modules.convergence_register import show as show_convergence
    from modules.department_targets import show as show_targets
    from modules.implementation import show as show_implementation
    from modules.meetings import show as show_meetings
    from modules.reports import show as show_reports
    from modules.excel_import import show as show_import
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

st.sidebar.title("VB‑G RAM G Convergence")
st.sidebar.markdown(f"<span style='color: #495057; font-size: 0.9rem;'>FY 2026‑27</span><br><span style='font-size: 0.85rem;'>Logged in as:</span><br><b>{user.get('full_name', 'User')}</b> (<span style='color: #1F77B4; font-weight: bold;'>{role.upper()}</span>)", unsafe_allow_html=True)
st.sidebar.divider()

# ---------- FONT SIZE ACCESSIBILITY SLIDER ----------
st.sidebar.markdown("### 🔠 Accessibility")
global_font_size = st.sidebar.slider("Font Size Scaling", min_value=12, max_value=22, value=15, step=1)
st.sidebar.divider()

# ---------- DYNAMIC FONT SIZE & UI STYLING ----------
st.markdown(f"""
    <style>
        /* Main background and font scaling */
        .main {{
            background-color: #F8F9FA;
            font-size: {global_font_size}px !important;
        }}
        .main p, .main span, .main label, .main div {{
            font-size: {global_font_size}px !important;
        }}
        /* Sidebar styling */
        [data-testid="stSidebar"] {{
            background-color: #F1F3F5;
            border-right: 1px solid #E9ECEF;
            padding-bottom: 20px;
        }}
        /* Custom Headers */
        h1 {{
            font-size: {global_font_size + 12}px !important;
            color: #1F77B4;
        }}
        h2 {{
            font-size: {global_font_size + 8}px !important;
            color: #1F77B4;
        }}
        h3 {{
            font-size: {global_font_size + 4}px !important;
            color: #1F77B4;
        }}
        /* Metric Cards Accent */
        [data-testid="stMetricValue"] {{
            color: #2B8A3E;
            font-size: {global_font_size + 10}px !important;
        }}
        /* Enhance sidebar navigation menu visibility with larger font */
        [data-testid="stSidebar"] [role="radiogroup"] label {{
            font-size: {global_font_size + 1}px !important;
            font-weight: 700 !important;
            color: #2C3E50 !important;
            padding: 10px 14px !important;
            border-radius: 8px;
            margin-bottom: 6px;
            transition: all 0.2s ease-in-out;
        }}
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
            background-color: #E2E8F0 !important;
            color: #1F77B4 !important;
        }}
    </style>
""", unsafe_allow_html=True)

# ---------- ROLE‑BASED ACCESS CONTROL ----------
role_pages = {
    "superadmin": [
        "Dashboard",
        "Convergence Register",
        "Department Targets",
        "Implementation Monitoring",
        "Meetings",
        "Reports & Excel",
        "Excel Import",
        "Master Data",
        "User Directory",
        "User Management",
        "Audit Log",
        "🎨 UI/UX Controller",
    ],
    "district": [
        "Dashboard",
        "Convergence Register",
        "Department Targets",
        "Implementation Monitoring",
        "Meetings",
        "Reports & Excel",
        "User Directory",
    ],
    "block": [
        "Dashboard",
        "Convergence Register",
        "Implementation Monitoring",
        "Meetings",
        "User Directory",
    ],
    "department": [
        "Dashboard",
        "Department Targets",
        "Convergence Register",
        "Implementation Monitoring",
        "Reports & Excel",
        "User Directory",
    ],
}

allowed_pages = role_pages.get(role, [])
if not allowed_pages:
    st.error("Your user role is not configured correctly. Please contact the administrator.")
    logout()

# ---------- NAVIGATION MENU (PLACED FIRST) ----------
selection = st.sidebar.radio("Navigation", allowed_pages, label_visibility="collapsed")

# Spacer to push logout button to the bottom
st.sidebar.markdown("<br>" * 2, unsafe_allow_html=True)
st.sidebar.divider()

# ---------- LOGOUT BUTTON AT THE BOTTOM ----------
if st.sidebar.button("🔒 Logout", type="secondary", use_container_width=True):
    logout()

# ---------- IMPORT ALL MODULES FOR ROUTING ----------
menu = {
    "Dashboard": show_dashboard,
    "Convergence Register": show_convergence,
    "Department Targets": show_targets,
    "Implementation Monitoring": show_implementation,
    "Meetings": show_meetings,
    "Reports & Excel": show_reports,
    "Excel Import": show_import,
    "Master Data": show_masterdata,
    "User Directory": show_contacts,
    "User Management": show_users,
    "Audit Log": show_audit,
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
