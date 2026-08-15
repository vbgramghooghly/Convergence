from datetime import date, datetime
import base64
import json
import io
from utils.db import get_supabase
import streamlit as st

def inject_custom_css():
    """Injects custom CSS to hide the Streamlit toolbar and FIX the sidebar toggle."""
    st.markdown("""
    <style>
        /* 1. Force the Header to be visible but transparent */
        header, header[data-testid="stHeader"], .stAppHeader {
            visibility: visible !important;
            display: block !important;
            background: transparent !important;
            z-index: 99998 !important;
        }
        
        /* 2. Turn the Sidebar Toggle (>) into a highly visible Floating Button */
        [data-testid="collapsedControl"] {
            visibility: visible !important;
            display: flex !important;
            z-index: 99999 !important;
            background-color: #ffffff !important;
            border-radius: 50% !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
            top: 15px !important;
            left: 15px !important;
        }
        
        /* 3. STRICTLY hide ONLY the top-right Streamlit tools (Deploy, GitHub, Options) */
        .stAppToolbar, [data-testid="stToolbar"], [data-testid="stStatusWidget"], #MainMenu {
            display: none !important;
            visibility: hidden !important;
        }
    </style>
    """, unsafe_allow_html=True)

def check_password():
    """Returns True if the user is authenticated, otherwise renders a login page."""
    
    inject_custom_css()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.authenticated:
        if "selected_fy" not in st.session_state:
            st.session_state.selected_fy = "2026-27"

        with st.sidebar:
            st.markdown("### 📅 Financial Year")
            fy_options = ["2026-27", "2027-28", "2028-29"]
            current_fy_idx = fy_options.index(st.session_state.selected_fy) if st.session_state.selected_fy in fy_options else 0
            st.session_state.selected_fy = st.selectbox(
                "Select Active FY", 
                fy_options, 
                index=current_fy_idx, 
                label_visibility="collapsed"
            )
            st.markdown("---")

        return True

    # ---------- STYLING FOR THE LANDING / LOGIN PAGE ----------
    st.markdown("""
        <style>
            .stApp {
                background: linear-gradient(135deg, #F0F4F8 0%, #D9E2EC 100%);
            }
            [data-testid="stForm"] {
                background: #FFFFFF;
                padding: 35px;
                border-radius: 16px;
                box-shadow: 0 12px 30px -10px rgba(31, 119, 180, 0.25);
                border: 2px solid #1F77B4;
                border-top: 6px solid #1F77B4;
            }
            .portal-title {
                font-size: 2.3rem;
                font-weight: 800;
                color: #1F77B4;
                margin-bottom: 0px;
            }
            .portal-subtitle {
                font-size: 1.1rem;
                color: #4A5568;
                margin-bottom: 25px;
            }
            .feature-item {
                font-size: 1.05rem;
                color: #2D3748;
                margin-bottom: 14px;
                font-weight: 500;
            }
        </style>
    """, unsafe_allow_html=True)

    # ---------- SPLIT-SCREEN LAYOUT ----------
    col_left, col_right = st.columns([1.3, 1], gap="large")

    with col_left:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 class='portal-title'>📊 VB-G RAM G Convergence</h1>", unsafe_allow_html=True)
        st.markdown("<p class='portal-subtitle'>Unified District, Block, and Department Level Convergence Management Portal</p>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🌟 Key Portal Highlights")
        st.markdown("<div class='feature-item'>📈 <b>Real-Time Progress Tracking:</b> Monitor physical & financial achievements instantly.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🏛️ <b>Multi-Tier Governance:</b> Role-based access for Districts, Blocks, and Departments.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>📊 <b>Dynamic Visualizations:</b> Automated analytics, dashboards, and instant Excel/PDF reporting.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🔒 <b>Secure & Transparent:</b> Complete audit logging and streamlined work entries.</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📘 View Portal User Manual (District, Block & Dept)"):
            st.markdown("""
            # 📘 User Manual: VB-G RAM G Convergence Management Portal

            Welcome to the **VB-G RAM G Convergence Management Portal** User Manual. This guide provides step-by-step instructions for **District Administrators**, **Block Level Officers**, and **Line Departments** to navigate and manage convergence activities, set annual targets, track progress, record statutory meeting proceedings, and generate official reports.

            ---

            ## 📑 Table of Contents
            1. Portal Access & User Roles
            2. Master Dashboard
            3. Work Entry
            4. Progress Tracking
            5. Convergence Meeting & Resolution Tracker
            6. Reports
            7. Officials Directory

            ---

            ## 1. Portal Access & User Roles
            | Role | Access Scope & Permissions |
            | :--- | :--- |
            | **District (Admin)** | Complete oversight across the district. Can schedule District-level meetings, manage all block entries, edit targets, and assign committee roles. |
            | **Block (Execution)** | Focused on block-level activities. Mandatory block-level tracking, scheduling Block meetings, and updating local progress. |
            | **Department** | Restricted to departmental jurisdiction. Input annual targets, register proposed schemes, update MIS codes, and fulfill meeting action points. |

            ---

            ## 2. Master Dashboard
            The **Master Dashboard** gives you a high-level overview of physical and financial progress across the active financial year. Use the global sidebar filters to navigate dynamic data.

            ---

            ## 3. Work Entry
            ### Manual Data Entry
            1. Expand **"➕ Add New Convergence Activity"**.
            2. Select **Financial Year**, **District**, and mandatory **Block**.
            3. Select your **Department** and choose an approved **Activity**.
            4. Choose the **Convergence Type** (Technical or Financial).
            5. Enter Targets, Persondays, and Fund Commitments.
            6. Click **Save**.

            ---

            ## 4. Progress
            ### Updating Implementation & MIS Progress (Tab 2)
            1. Select the **Implementation Progress** tab.
            2. Choose the convergence activity from the dropdown.
            3. Update the **Status**. If moving to "Under Implementation", a valid **MIS Code** is mandatory.
            4. Enter **Financial Achievement**, **Persondays**, and Dates.
            5. Click **Save Progress** to log the update into the history timeline.

            ---

            ## 5. Convergence Meeting & Resolution Tracker
            Manage statutory committee meetings at the District or Block levels.
            `[Schedule Meeting] ➔ [Mark Attendance] ➔ [Record Minutes/Resolutions] ➔ [Lock Proceedings]`

            ### Syncing Meeting Commitments
            1. Select the **Meeting Commitments** tab.
            2. Update assigned action points to *Completed* or *Under Process*.
            3. If selecting *Not Feasible*, a clear reason must be provided under **Remarks** for Chairperson review.

            ---

            ### ❓ Support & Assistance
            If you run into database errors or account mapping issues, contact your **District Superadmin**.
            """)

    with col_right:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        st.markdown("### 🔐 Portal Login")
        st.markdown("<p style='color: #718096; font-size: 0.9rem; margin-bottom: 15px;'>Enter your credentials to access your workspace.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username / Email", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("Sign In to Workspace", type="primary", use_container_width=True)

            if submit_btn:
                if not username or not password:
                    st.error("⚠️ Please enter both username and password.")
                else:
                    try:
                        supabase = get_supabase()
                        
                        clean_input = username.strip()
                        login_email = clean_input if "@" in clean_input else f"{clean_input}@hooghly.gov.in"
                        
                        auth_response = supabase.auth.sign_in_with_password({
                            "email": login_email,
                            "password": password
                        })
                        
                        user_id = auth_response.user.id
                        profile_response = supabase.table("users").select("*").eq("id", user_id).execute()
                        users_data = profile_response.data

                        if not users_data:
                            st.error("❌ User profile not found in the database.")
                        else:
                            user_profile = users_data[0]
                            if not user_profile.get("active", True):
                                st.error("🚫 This account has been deactivated. Contact Superadmin.")
                            else:
                                st.session_state.authenticated = True
                                st.session_state.user = user_profile
                                st.success("✅ Login successful! Loading workspace...")
                                st.rerun()

                    except Exception as e:
                        st.error("❌ Incorrect username or password.")

    return False

def get_current_user():
    """Returns the dictionary of the currently logged-in user."""
    return st.session_state.get("user", None)

def logout():
    """Clears authentication session and reloads the landing page."""
    try:
        supabase = get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass 
        
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

def require_role(*allowed_roles):
    """Enforces role-based access control across pages."""
    user = get_current_user()
    if not user or user.get('role') not in allowed_roles:
        st.error("🚫 Access Denied: You do not have the required permissions to view this module.")
        st.stop()
