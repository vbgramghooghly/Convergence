import streamlit as st
import os
from utils.db import get_supabase
from utils.theme import apply_global_theme

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="VB-G RAM G Portal",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed" # We collapse it natively, then kill it with CSS
)

# ---------- APPLY CENTRAL UI/UX THEME ----------
theme = apply_global_theme()
primary_color = theme.get("primary_color", "#0F4C81")

# ---------- GLOBAL CSS (NO SIDEBAR, TOP NAV STYLING) ----------
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

        /* 4. STYLE THE TOP RADIO BUTTONS TO LOOK LIKE A MODERN NAVBAR */
        /* Make the radio group a horizontal flexbox */
        div.row-widget.stRadio > div {{
            display: flex;
            flex-direction: row;
            flex-wrap: wrap;
            gap: 10px;
            padding: 5px;
            background: #F8FAFC;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
        }}
        
        /* Style the individual navigation pills */
        div.row-widget.stRadio > div > label {{
            background-color: transparent;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            margin: 0;
            transition: all 0.2s ease;
        }}
        
        /* Hide the actual radio circle circles */
        div[role="radiogroup"] > label > div:first-of-type {{
            display: none !important;
        }}
        
        /* Text styling inside the pills */
        div.row-widget.stRadio > div > label div[data-testid="stMarkdownContainer"] p {{
            font-weight: 600;
            color: #4A5568;
            font-size: 14px;
            margin: 0;
        }}

        /* Hover effect */
        div.row-widget.stRadio > div > label:hover {{
            background-color: #E2E8F0;
        }}

        /* Active/Selected state */
        div.row-widget.stRadio > div > label:has(input:checked) {{
            background-color: {primary_color};
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }}
        
        /* Active text color */
        div.row-widget.stRadio > div > label:has(input:checked) div[data-testid="stMarkdownContainer"] p {{
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
col_logo, col_nav, col_profile = st.columns([1.5, 7, 1.5], vertical_alignment="center")

with col_logo:
    st.markdown(f"<h3 style='color: {primary_color}; margin: 0; font-weight: 800;'>🏛️ VB-G RAM G</h3>", unsafe_allow_html=True)

# 1. Define allowed pages per role (Superadmin gets everything)
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

# 2. Render Primary Horizontal Navigation
with col_nav:
    selection = st.radio("Navigation", allowed_pages, horizontal=True, label_visibility="collapsed")

# 3. Render Profile Dropdown (Top Right)
with col_profile:
    first_name = user.get('full_name', 'User').split()[0]
    
    # st.popover acts as a perfect dropdown menu
    with st.popover(f"👤 {first_name} ▾", use_container_width=True):
        st.markdown(f"**{user.get('full_name')}**")
        st.caption(f"Role: {role.upper()}")
        st.divider()
        
        # FY Selector moved to profile menu
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
