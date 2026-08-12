import streamlit as st
from auth.auth import check_password, logout, get_current_user
import importlib

st.set_page_config(
    page_title="VB-G RAM G Convergence",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📊"
)

# Authentication
if not check_password():
    st.stop()

user = get_current_user()
role = user['role']

# ---------- SIDEBAR ----------
st.sidebar.image("assets/logo.png", width=200)  # optional logo
st.sidebar.title("VB‑G RAM G Convergence")
st.sidebar.caption(f"FY 2026‑27 | {role.upper()}")

# Define full menu – some items hidden by role
menu = {
    "Dashboard": "modules.dashboard",
    "Convergence Register": "modules.convergence_register",
    "Department Targets": "modules.department_targets",
    "Implementation": "modules.implementation",
    "Meetings": "modules.meetings",
    "Reports & Excel": "modules.reports",
    "Master Data": "modules.master_data",
    "User Management": "modules.users",
    "Audit Log": "modules.audit",
}

# Role-based access
role_pages = {
    "superadmin": list(menu.keys()),
    "district": ["Dashboard", "Convergence Register", "Department Targets", "Implementation", "Meetings", "Reports & Excel"],
    "block": ["Dashboard", "Convergence Register", "Implementation", "Meetings"],
    "department": ["Dashboard", "Department Targets", "Convergence Register", "Implementation", "Reports & Excel"],
}

allowed_pages = role_pages.get(role, [])
# Remove logout from menu (handled separately)
allowed_pages = [p for p in allowed_pages if p != "Logout"]

# Logout button
if st.sidebar.button("Logout"):
    logout()

# Navigation – radio buttons for selected pages
selection = st.sidebar.radio("Go to", allowed_pages)

# Dynamically load the selected module
if selection in menu:
    module_path = menu[selection]
    module = importlib.import_module(module_path)
    if hasattr(module, 'show'):
        module.show()
    else:
        st.error(f"Module {selection} is not properly defined (missing show()).")
else:
    # Fallback to dashboard
    from modules.dashboard import show
    show()
