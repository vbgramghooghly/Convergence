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

# ---------- APPLY CENTRAL UI/UX THEME ----------
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")

# ---------- GLOBAL CSS (BULLETPROOF TOP NAV STYLING) ----------
st.markdown(f"""
    <style>
        /* 1. COMPLETELY KILL THE SIDEBAR AND TOGGLE BUTTON */
        [data-testid="collapsedControl"] {{ display: none !important; }}
        [data-testid="stSidebar"] {{ display: none !important; }}
        section[data-testid="stSidebar"] {{ width: 0px !important; }}

        /* 2. HIDE STREAMLIT TOP-RIGHT TOOLS */
        [data-testid="stToolbar"], #MainMenu, header[data-testid="stHeader"] {{
            display: none !important;
            visibility: hidden !important;
        }}

        /* 3. REDUCE WASTED TOP SPACE */
        .block-container {{
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 98% !important;
        }}

        /* 4. SAFE RADIO-TO-NAVBAR CSS */
        /* Target the exact radio circle element safely without hiding text */
        [data-testid="stRadio"] [data-baseweb="radio"] {{
            display: none !important;
        }}
        
        /* Make the radio group a horizontal flex container */
        [data-testid="stRadio"] > div[role="radiogroup"] {{
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 10px !important;
            background-color: #F8FAFC !important;
            padding: 8px 12px !important;
            border-radius: 8px !important;
            border: 1px solid #E2E8F0 !important;
        }}
        
        /* Style the individual navigation pills */
        [data-testid="stRadio"] > div[role="radiogroup"] > label {{
            background-color: transparent !important;
            padding: 8px 16px !important;
            border-radius: 6px !important;
            cursor: pointer !important;
            margin: 0 !important;
            transition: all 0.2s ease !important;
        }}

        /* Hover effect */
        [data-testid="stRadio"] > div[role="radiogroup"] > label:hover {{
            background-color: #E2E8F0 !important;
        }}

        /* Active/Selected state */
        [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked),
        [data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] {{
            background-color: {primary_color} !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
        }}
        
        /* Text styling inside the pills */
        [data-testid="stRadio"] > div[role="radiogroup"] > label p {{
            font-weight: 600 !important;
            color: #4A5568 !important;
            font-size: 15px !important;
            margin: 0 !important;
        }}
        
        /* Active text color */
        [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p,
        [data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] p {{
            color: #FFFFFF !important;
        }}
        
        /* Sub-navigation (Tabs) Modernization */
        div[data-testid="stTabs"] button[role="tab"] {{
            font-weight: 600;
            color: #4A5568;
            border-radius: 4px;
            padding: 6px 16px;
            margin-right: 4px;
            border: 1px solid transparent;
        }}
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
            color: {primary_color};
            background-color: #F0F4F8;
            border: 1px solid #CBD5E1;
            border-bottom: 2px solid {primary_color};
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

# ---------- TOP NAVIGATION BAR & PROFILE MENU ----------
# Layout: Logo (Left) | Navigation (Center) | Profile (Right)
col_logo, col_nav, col_profile = st.columns([1.5, 7, 1.5])

with col_logo:
    st.markdown(f"<h3 style='color: {primary_color}; margin-top: 8px; font-weight: 800;'>🏛️ VB-G RAM G</h3>", unsafe_allow_html=True)

# 1. Define allowed pages per role
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

# 2. Render Primary Horizontal Navigation safely
with col_nav:
    selection = st.radio("Navigation", allowed_pages, horizontal=True, label_visibility="collapsed")
    if not selection:
        selection = allowed_pages[0]

# 3. Render Profile Dropdown (Top Right)
with col_profile:
    first_name = user.get('full_name', 'User').split()[0]
    
    with st.popover(f"👤 {first_name} ▾", use_container_width=True):
        st.markdown(f"**{user.get('full_name')}**")
        st.caption(f"Role: {role.upper()}")
        st.divider()
        
        st.markdown("**📅 Active Financial Year**")
        if "selected_fy" not in st.session_state:
            st.session_state.selected_fy = "2026-27"
        
        fy_options = ["2026-27", "2027-28", "2028-29"]
        current_fy_idx = fy_options.index(st.session_state.selected_fy) if st.session_state.selected_fy in fy_options else 0
        
        st.session_state.selected_fy = st.selectbox(
            "Select FY", 
            fy_options, 
            index=current_fy_idx, 
            label_visibility="collapsed"
        )
        
        st.divider()
        st.markdown("**🔐 Security**")
        with st.expander("Change Password"):
            with st.form("pw_form"):
                new_pw = st.text_input("New Password", type="password")
                conf_pw = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Update", use_container_width=True):
                    if len(new_pw) < 6: st.error("Min 6 characters.")
                    elif new_pw != conf_pw: st.error("Passwords mismatch.")
                    else:
                        try:
                            get_supabase().auth.update_user({"password": new_pw})
                            st.success("Updated successfully.")
                        except Exception as e:
                            st.error(f"Error: {e}")
        
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            logout()

st.markdown("---") # Divider between Nav and Page Content

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

if selection in menu:
    try:
        menu[selection]()
    except Exception as e:
        st.error(f"An error occurred while loading this page: {e}")
else:
    show_dashboard()
