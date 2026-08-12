import streamlit as st
from auth.auth import check_password, logout, get_current_user
import importlib

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

# ---------- SIDEBAR HEADER ----------
st.sidebar.image("assets/logo.png", width=200)   # optional logo
st.sidebar.title("VB‑G RAM G Convergence")
st.sidebar.caption(f"FY 2026‑27 | Logged in as: **{user['full_name']}** ({role.upper()})")
st.sidebar.divider()

# ---------- NAVIGATION MENU ----------
menu = {
    "Dashboard":                   "modules.dashboard",
    "Convergence Register":        "modules.convergence_register",
    "Department Targets":          "modules.department_targets",
    "Implementation Monitoring":   "modules.implementation",
    "Meetings":                    "modules.meetings",
    "Reports & Excel":             "modules.reports",
    "Excel Import":                "modules.excel_import",
    "Master Data":                 "modules.master_data",
    "User Management":             "modules.users",
    "Audit Log":                   "modules.audit",
}

# ---------- ROLE‑BASED ACCESS CONTROL ----------
role_pages = {
    "superadmin": list(menu.keys()),   # everything
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

# Safety: if role is invalid, log out
if not allowed_pages:
    st.error("Your user role is not configured correctly. Please contact the administrator.")
    logout()

# ---------- LOGOUT BUTTON ----------
if st.sidebar.button("🔒 Logout"):
    logout()

# ---------- NAVIGATION RADIO ----------
selection = st.sidebar.radio("Navigation", allowed_pages)

# ---------- DYNAMIC MODULE LOADING ----------
if selection in menu:
    module_path = menu[selection]
    try:
        module = importlib.import_module(module_path)
        if hasattr(module, 'show'):
            module.show()
        else:
            st.error(f"Module '{selection}' is not properly defined (missing show() function).")
    except Exception as e:
        st.error(f"Could not load module {selection}: {e}")
else:
    # Fallback to dashboard
    from modules.dashboard import show
    show()
