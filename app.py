import streamlit as st
from auth.auth import check_password, logout, get_current_user
import os

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB-G RAM G Convergence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- AUTHENTICATION ----------
if not check_password():
    st.stop()

user = get_current_user()
role = user['role']

# ---------- IMPORT ALL MODULES (avoids dynamic loading issues) ----------
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

# ---------- SIDEBAR HEADER ----------
logo_path = "assets/logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=200)

st.sidebar.title("VB‑G RAM G Convergence")
st.sidebar.caption(f"FY 2026‑27 | Logged in as: **{user['full_name']}** ({role.upper()})")
st.sidebar.divider()

# ---------- NAVIGATION MENU ----------
menu = {
    "Dashboard":                   show_dashboard,
    "Convergence Register":        show_convergence,
    "Department Targets":          show_targets,
    "Implementation Monitoring":   show_implementation,
    "Meetings":                    show_meetings,
    "Reports & Excel":             show_reports,
    "Excel Import":                show_import,
    "Master Data":                 show_masterdata,
    "User Management":             show_users,
    "Audit Log":                   show_audit,
}

# ---------- ROLE‑BASED ACCESS CONTROL ----------
role_pages = {
    "superadmin": list(menu.keys()),
    "district": [
        "Dashboard",
        "Convergence Register",
        "Department Targets",
        "Implementation Monitoring",
        "Meetings",
        "Reports & Excel",
    ],
    "block": [
        "Dashboard",
        "Convergence Register",
        "Implementation Monitoring",
        "Meetings",
    ],
    "department": [
        "Dashboard",
        "Department Targets",
        "Convergence Register",
        "Implementation Monitoring",
        "Reports & Excel",
    ],
}

allowed_pages = role_pages.get(role, [])
if not allowed_pages:
    st.error("Your user role is not configured correctly. Please contact the administrator.")
    logout()

# ---------- LOGOUT BUTTON ----------
if st.sidebar.button("🔒 Logout"):
    logout()

# ---------- NAVIGATION RADIO ----------
selection = st.sidebar.radio("Navigation", allowed_pages)

# ---------- CALL THE SELECTED PAGE ----------
if selection in menu:
    menu[selection]()   # Call the show function directly
else:
    show_dashboard()
