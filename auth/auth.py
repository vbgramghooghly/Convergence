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
    /* Hide the right-side Streamlit toolbar (Fork, GitHub, Deploy buttons) */
    .stAppToolbar, [data-testid="stToolbar"] {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* FORCE the header to be visible so the sidebar toggle button (>) NEVER disappears */
    header[data-testid="stHeader"] {
        visibility: visible !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)

def check_password():
    """Returns True if the user is authenticated, otherwise renders a professional split-screen landing/login page."""
    
    # Apply custom UI styling
    inject_custom_css()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.authenticated:
        # ---------- PERSISTENT FY SELECTOR IN TOP LEFT SIDEBAR ----------
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
            /* The problematic 'header {visibility: hidden;}' has been removed from here */
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
        st.markdown("<div class='feature-item'>🔒 <b>Secure & Transparent:</b> Complete audit logging and streamlined activity registers.</div>", unsafe_allow_html=True)

        # ---------- USER MANUAL EXPANDER LINK ----------
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📘 View Portal User Manual (District, Block & Dept)"):
            st.markdown("""
            # 📘 User Manual: VB-G RAM G Convergence Management Portal

            Welcome to the **VB-G RAM G Convergence Management Portal** User Manual. This guide provides step-by-step instructions for **District Administrators**, **Block Level Officers**, and **Line Departments** to navigate and manage convergence activities, set annual targets, track progress, record statutory meeting proceedings, and generate official reports.

            ---

            ## 📑 Table of Contents
            1. [Portal Access & User Roles](#1-portal-access--user-roles)
            2. [Master Dashboard](#2-master-dashboard)
            3. [Convergence Register](#3-convergence-register)
               - [Viewing & Managing Entries](#viewing--managing-entries)
               - [Manual Data Entry](#manual-data-entry)
               - [Bulk CSV Upload](#bulk-csv-upload)
            4. [Implementation & Target Monitoring](#4-implementation--target-monitoring)
               - [Setting Department Targets](#setting-department-targets)
               - [Updating Implementation & MIS Progress](#updating-implementation--mis-progress)
               - [Syncing Meeting Commitments](#syncing-meeting-commitments)
            5. [Convergence Meeting & Resolution Tracker](#5-convergence-meeting--resolution-tracker)
               - [Scheduling Meetings](#scheduling-meetings)
               - [Recording Proceedings & Attendance](#recording-proceedings--attendance)
               - [Resolution Tracking & Agenda Prep](#resolution-tracking--agenda-prep)
            6. [Reports & Analytics](#6-reports--analytics)
            7. [Official Contact Directory](#7-official-contact-directory)

            ---

            ## 1. Portal Access & User Roles

            Access the portal via your browser. Your dashboard options and permissions automatically adjust based on your assigned role:

            | Role | Access Scope & Permissions |
            | :--- | :--- |
            | **District (Admin)** | Complete oversight across the district. Can schedule District-level meetings, manage all block entries, edit targets, and assign committee roles. |
            | **Block (Execution)** | Focused on block-level activities. Mandatory block-level tracking, scheduling Block meetings, and updating local progress. |
            | **Department** | Restricted to departmental jurisdiction. Input annual targets, register proposed schemes, update MIS codes, and fulfill meeting action points. |

            ---

            ## 2. Master Dashboard

            The **Master Dashboard** gives you a high-level overview of physical and financial progress across the active financial year.

            ### Key Features:
            * **Global Filters (Sidebar):** Filter data by **District**, **Department**, **Theme**, and **Status** (*Planned*, *Approved*, *Under Implementation*, *Completed*, *Delayed*).
            * **KPI Metrics:** View real-time totals for:
              * Total Activities & Physical Targets
              * Department Funds & VB-G RAM G Funds (in ₹ Lakhs)
              * Expected vs. Actual Generated Persondays
              * Completion Percentage & Achievement Averages
            * **Interactive Visualizations:** Analyze Department Target vs. Achievement, Financial Convergence breakdowns, and Activity Status distributions.
            * **Dynamic Convergence Plan Tab:** View auto-aggregated matrix tables (grouped dynamically by Department, Block, and Activity description) and export them directly to Excel.

            ---

            ## 3. Convergence Register

            The **Convergence Register** allows you to view, capture, edit, and bulk-upload individual convergence activities.

            ### Viewing & Managing Entries
            1. Navigate to **Convergence Register**.
            2. View existing entries filtered automatically by your administrative boundary.
            3. **Edit / Delete (District/Admin):** Expand **"🛠️ Manage Saved Entries"**, choose an activity from the dropdown, and update details or permanently delete records.

            ### Manual Data Entry
            1. Expand **"➕ Add New Convergence Activity"**.
            2. Select **Financial Year**, **District**, and mandatory **Block**.
            3. Select your **Department** and choose an approved **Activity / Work Description** (the *Thematic Category* auto-populates).
            4. Choose the **Convergence Type**:
               * *Technical Convergence (Zero Fund/NOC)* (Funds are automatically set to 0.0)
               * *Financial (as PIA)*
               * *Financial (as Non-PIA)*
            5. Fill in optional specifications (**Scheme Name**, **Geo Location**, **Work Dimensions**, **Unit**, **MIS Code**, and **Origin Source**).
            6. Enter **Physical Target**, **Expected Persondays**, and **Fund Commitments** (Dept Fund & VB-G RAM G Fund in ₹ Lakhs).
            7. Click **Save Convergence Activity**.

            ### Bulk CSV Upload
            1. Expand **"📂 Bulk Upload Activities"**.
            2. Review the template column requirements (`Financial Year`, `District`, `Block`, `Department`, `Activity`, `Convergence Type`, `Physical Target`, `Expected Persondays`, `Department Fund`, `VB-G RAM G Fund`, etc.).
            3. Upload your `.csv` file and click **Validate & Import Data**. The system validates master data and approved activity mappings before importing.

            ---

            ## 4. Implementation & Target Monitoring

            This module bridges annual planning, field-level physical execution, and meeting action points.

            ### Setting Department Targets (Tab 1)
            1. Select the **Department Targets** tab.
            2. Select the **Department**, **District**, and specify the activity description, asset count, annual plan scope, and financial expectations.
            3. Click **Save Target**. Existing records will automatically update, while new ones will be created.

            ### Updating Implementation & MIS Progress (Tab 2)
            1. Select the **Implementation Progress** tab.
            2. Choose the convergence activity from the dropdown.
            3. Update the **Status** (*Under Implementation*, *Completed*, etc.) and adjust the **Physical Achievement (%)** slider.
            4. **MIS Code Rule:** If moving an activity to **"Under Implementation"** or **"Completed"**, you **must** enter a valid portal MIS Code.
            5. Enter **Financial Achievement (₹ Lakhs)**, **Persondays Generated**, **Actual Start/Completion Dates**, and **Remarks**.
            6. Click **Save Progress** to log the update into the progress history timeline.

            ### Syncing Meeting Commitments (Tab 3)
            1. Select the **Meeting Commitments** tab to review action points assigned to your department from official meetings.
            2. Select a resolution ID and update its status (*Under Process*, *Executed*, *Completed*, or *Not Feasible*).
            3. **Not Feasible Rule:** If selecting *Not Feasible (Requires Review)*, you must enter a clear reason under **Remarks**. This automatically flags the item for the Chairperson's review in the next meeting agenda.

            ---

            ## 5. Convergence Meeting & Resolution Tracker

            Manage statutory committee meetings at the District (DM-chaired) or Block (BDO-chaired) levels.

            ```
            [Schedule Meeting] ➔ [Mark Attendance] ➔ [Record Minutes/Resolutions] ➔ [Lock Proceedings]
