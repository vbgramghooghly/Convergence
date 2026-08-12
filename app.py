import streamlit as st
from auth.auth import check_password, logout, require_role

st.set_page_config(
    page_title="VB-G RAM G Convergence",
    layout="wide",
    initial_sidebar_state="expanded"
)

if not check_password():
    st.stop()

# Sidebar navigation based on role
role = st.session_state.role
st.sidebar.title(f"VB-G RAM G Convergence\nFY 2026-27")
st.sidebar.write(f"Logged in as: {st.session_state.user['full_name']} ({role})")

# Define menu structure
pages = {
    "Dashboard": "modules.dashboard",
    "Convergence Register": "modules.convergence_register",
    "Department Targets": "modules.department_targets",
    "Meetings": "modules.meetings",
    "Reports & Excel": "modules.reports",
    "Master Data": "modules.master_data",
    "User Management": "modules.users",
    "Audit Log": "modules.audit",
    "Logout": None
}

# Filter pages by role
if role == 'superadmin':
    allowed = list(pages.keys())
elif role == 'district':
    allowed = ["Dashboard", "Convergence Register", "Department Targets", "Meetings", "Reports & Excel"]
elif role == 'block':
    allowed = ["Dashboard", "Convergence Register", "Meetings"]
elif role == 'department':
    allowed = ["Dashboard", "Department Targets", "Convergence Register", "Reports & Excel"]
else:
    allowed = []

selection = st.sidebar.radio("Navigation", allowed)

if selection == "Logout":
    logout()

# Dynamic module loading
if selection in pages and pages[selection] is not None:
    module = __import__(pages[selection], fromlist=['show'])
    module.show()
else:
    # Default dashboard
    from modules.dashboard import show
    show()
