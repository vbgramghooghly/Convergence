import pandas as pd
import plotly.express as px
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.db import get_supabase
from utils.excel import dataframe_to_excel
from utils.theme import apply_global_theme

def show():
    # 1. ENFORCE SECURITY & ACCESS RULES (Unchanged)
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()

    # 2. GLOBAL THEME, HEADER & BREADCRUMB
    theme = apply_global_theme()
    primary_color = theme.get("primary_color", "#0F4C81")

    st.markdown("<div style='font-size: 0.85rem; color: #64748B; margin-bottom: 0.5rem;'>Home / Analytics / Master Reports</div>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='margin-bottom: 0px; color: {primary_color};'>📊 Reports & Analytics Centre</h2>", unsafe_allow_html=True)
    st.caption("Official reporting, analytical dashboards, and statutory export engine for VB-G RAM G Convergence.")
    st.markdown("---")

    # ==========================================
    # 3. BASE QUERY & ROLE SCOPE (Unchanged)
    # ==========================================
    query = supabase.table("convergence_register").select("*")
    if role == "district":
        query = query.eq("district_id", user["district_id"])
    elif role == "block":
        query = query.eq("block_id", user["block_id"])
    elif role == "department":
        query = query.eq("department_id", user["department_id"]).eq("district_id", user["district_id"])

    data = query.execute().data

    if not data:
        st.warning("No data available for your user jurisdiction.")
        return

    df = pd.DataFrame(data)

    # ==========================================
    # 4. MASTER DATA & MAPPINGS (Unchanged)
    # ==========================================
    districts = supabase.table("districts").select("id,district_name").execute().data or []
    blocks = supabase.table("blocks").select("id,block_name,district_id").execute().data or []
    departments = supabase.table("departments").select("id,department_name").execute().data or []
    themes = supabase.table("themes").select("id,theme_name").execute().data or []
    wings = supabase.table("department_wings").select("id, department_id, wing_name, entity_type").execute().data or []

    dist_map = {d["id"]: d["district_name"] for d in districts}
    block_map = {b["id"]: b["block_name"] for b in blocks}
    dept_map = {d["id"]: d["department_name"] for d in departments}
    theme_map = {t["id"]: t["theme_name"] for t in themes}
    wing_map = {w["id"]: w['wing_name'] for w in wings}

    # Replace IDs with names safely
    df["district_name"] = df["district_id"].map(dist_map).fillna("Unknown")
    df["block_name"] = df["block_id"].map(block_map).fillna("Unknown")
    df["department_name"] = df["department_id"].map(dept_map).fillna("Unknown")
    df["theme_name"] = df["thematic_category_id"].map(theme_map).fillna("Unassigned")

    if "convergence_type" not in df.columns: df["convergence_type"] = "Not Specified"
    if "total_converged_fund" not in df.columns: df["total_converged_fund"] = df.get("department_fund", 0.0) + df.get("vbgramg_fund", 0.0)

    # ==========================================
    # 5. REPORT SELECTION (Removed header)
    # ==========================================
    col_c1, col_c2 = st.columns(2)
    report_category = col_c1.selectbox("1. Select Report Category", [
        "Official Statutory Reports",
        "Executive & Performance Analytics",
        "Financial & Technical Analytics",
        "Risk, Delay & Master Statements",
        "Meeting & Resolution Register"
    ])

    # Cascading report type based on category
    if report_category == "Official Statutory Reports":
        report_opts = [
            "Official VB-G RAM G Summary Report (Template)",
            "District-wise Summary Report",
            "Department-wise Summary Report",
            "Block-wise Summary Report",
        ]
    elif report_category == "Executive & Performance Analytics":
        report_opts = [
            "District Performance Dashboard",
            "Department Performance Dashboard",
            "Block Performance Dashboard",
            "Scheme Performance Report",
            "Personday Generation Report",
        ]
    elif report_category == "Financial & Technical Analytics":
        report_opts = [
            "Financial Convergence Report (Fund Gap Analysis)",
            "Technical Convergence Report (NOC Status)",
        ]
    elif report_category == "Risk, Delay & Master Statements":
        report_opts = [
            "Pending / Delayed Activities Report",
            "FY 2026–27 Master Convergence Statement",
        ]
    else:
        report_opts = [
            "District Convergence Meeting Register",
            "Department-wise Resolution Statement",
        ]

    report_type = col_c2.selectbox("2. Select Specific Report Format", report_opts)

    st.markdown("---")

    # ==========================================
    # 6. CONTEXT-SENSITIVE FILTERS (based on report_type)
    # ==========================================
    # Build a filtered dataframe using the selected report's filters
    # We'll keep a copy of the original df for reset
    filtered_df = df.copy()

    # Define filter options based on report type
    # We'll collect filter values in a dict
    filter_values = {}

    # Determine which filters to show
    show_filters = []
    if report_type in ["Official VB-G RAM G Summary Report (Template)", "District-wise Summary Report",
                       "Department-wise Summary Report", "Block-wise Summary Report",
                       "District Performance Dashboard", "Department Performance Dashboard",
                       "Block Performance Dashboard", "Scheme Performance Report",
                       "Personday Generation Report", "Financial Convergence Report (Fund Gap Analysis)",
                       "Pending / Delayed Activities Report", "FY 2026–27 Master Convergence Statement"]:
        show_filters = ["district", "department", "block", "theme", "status", "financial_year"]
    elif report_type == "Technical Convergence Report (NOC Status)":
        show_filters = ["district", "department", "block", "financial_year"]  # status not needed
    elif report_type in ["District Convergence Meeting Register", "Department-wise Resolution Statement"]:
        show_filters = ["district", "department", "financial_year"]  # meetings have less fields

    # Remove filters that are not applicable based on available columns
    available_cols = set(df.columns)
    if "financial_year" not in available_cols:
        show_filters = [f for f in show_filters if f != "financial_year"]
    if "current_status" not in available_cols:
        show_filters = [f for f in show_filters if f != "status"]
    if "theme_name" not in available_cols:
        show_filters = [f for f in show_filters if f != "theme"]

    # Build filter UI
    if show_filters:
        st.subheader("🔍 Apply Filters")
        # Create columns for filters (3 per row)
        cols = st.columns(min(3, len(show_filters)))
        filter_cols = {}
        for i, f in enumerate(show_filters):
            col = cols[i % 3]
            if f == "district":
                # Get distinct districts (already mapped)
                districts_list = sorted(df["district_name"].unique())
                # Remove "Unknown" if present
                if "Unknown" in districts_list:
                    districts_list.remove("Unknown")
                selected = col.multiselect("District", districts_list, default=[])
                filter_values["district"] = selected
            elif f == "block":
                # Cascade: if district selected, show blocks from those districts
                district_vals = filter_values.get("district", [])
                if district_vals:
                    # Get block names where district_name in district_vals
                    block_options = sorted(df[df["district_name"].isin(district_vals)]["block_name"].unique())
                else:
                    block_options = sorted(df["block_name"].unique())
                if "Unknown" in block_options:
                    block_options.remove("Unknown")
                selected = col.multiselect("Block", block_options, default=[])
                filter_values["block"] = selected
            elif f == "department":
                dept_options = sorted(df["department_name"].unique())
                if "Unknown" in dept_options:
                    dept_options.remove("Unknown")
                selected = col.multiselect("Department", dept_options, default=[])
                filter_values["department"] = selected
            elif f == "theme":
                theme_options = sorted(df["theme_name"].unique())
                if "Unassigned" in theme_options:
                    theme_options.remove("Unassigned")
                selected = col.multiselect("Theme", theme_options, default=[])
                filter_values["theme"] = selected
            elif f == "status":
                status_options = sorted(df["current_status"].unique())
                selected = col.multiselect("Status", status_options, default=[])
                filter_values["status"] = selected
            elif f == "financial_year":
                # If column exists, get unique values
                if "financial_year" in df.columns:
                    fy_options = sorted(df["financial_year"].unique())
                    selected = col.multiselect("Financial Year", fy_options, default=[])
                    filter_values["financial_year"] = selected
                else:
                    # Provide a default FY selection (could be a fixed value)
                    # We'll create a dummy filter that doesn't affect data
                    selected = col.selectbox("Financial Year", ["2026-27"], index=0)
                    filter_values["financial_year"] = [selected]  # keep as list for consistency

        # Reset button
        if st.button("Reset Filters"):
            st.rerun()  # will reset all selections

        # Apply filters to filtered_df
        for key, vals in filter_values.items():
            if vals:
                if key == "district":
                    filtered_df = filtered_df[filtered_df["district_name"].isin(vals)]
                elif key == "block":
                    filtered_df = filtered_df[filtered_df["block_name"].isin(vals)]
                elif key == "department":
                    filtered_df = filtered_df[filtered_df["department_name"].isin(vals)]
                elif key == "theme":
                    filtered_df = filtered_df[filtered_df["theme_name"].isin(vals)]
                elif key == "status":
                    filtered_df = filtered_df[filtered_df["current_status"].isin(vals)]
                elif key == "financial_year":
                    if "financial_year" in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df["financial_year"].isin(vals)]

        st.markdown("---")
    else:
        # No filters to show, use original df
        filtered_df = df.copy()

    # ==========================================
    # 7. RENDER THE SELECTED REPORT (with filtered_df)
    # ==========================================
    # We'll capture the report output in a div for print.
    # Also add print CSS to hide UI elements.
    print_css = """
    <style>
    @media print {
        /* Hide all streamlit UI elements */
        .stApp > header, .stApp > .stSidebar, .stApp > .stToolbar, .stApp > .stStatusWidget,
        .stApp > .stException, .stApp > .stAlert, .stApp > .stButton, .stApp > .stSelectbox,
        .stApp > .stMultiselect, .stApp > .stColumns, .stApp > .stContainer,
        .stApp > .stMarkdown:not(.print-content), .stApp > .stSubheader, .stApp > .stCaption,
        .stApp > .stDownloadButton, .stApp > .stPlotlyChart, .stApp > .stDataFrame,
        .stApp > .stImage, .stApp > .stExpander, .stApp > .stTabs,
        .stApp > .stFileUploader, .stApp > .stDateInput, .stApp > .stTimeInput,
        .stApp > .stTextInput, .stApp > .stNumberInput, .stApp > .stTextArea,
        .stApp > .stSlider, .stApp > .stCheckbox, .stApp > .stRadio, .stApp > .stColorPicker,
        .stApp > .stProgress, .stApp > .stSpinner, .stApp > .stBalloon,
        .stApp > .stWarning, .stApp > .stInfo, .stApp > .stSuccess, .stApp > .stError,
        .stApp > .stPlaceholder, .stApp > .stMarkdown:not(.print-content),
        .stApp > .stBanner, .stApp > .stNotification, .stApp > .stToast,
        .stApp > .stSidebarContent, .stApp > .stMainBlock,
        .stApp > .stPage, .stApp > .stAppViewContainer, .stApp > .stMain,
        .stApp > .st-emotion-cache-1v3ma8w, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1c7y2kd, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1v0mbdj, .stApp > div[data-testid="stToolbar"],
        .stApp > div[data-testid="stSidebarCollapsedControl"],
        .stApp > div[data-testid="stDecoration"],
        .stApp > div[data-testid="stHeader"],
        .stApp > div[data-testid="stStatusWidget"],
        .stApp > div[data-testid="stCaptionContainer"],
        .stApp > div[data-testid="stImageCaption"],
        .stApp > div[data-testid="stBottom"],
        .stApp > footer, .stApp > .stFooter,
        .stApp > .stAppViewBlock, .stApp > .stBlock,
        .stApp > .st-emotion-cache-1jicfl2, .stApp > .st-emotion-cache-1r6slb0,
        .stApp > .st-emotion-cache-1wrcr25, .stApp > .st-emotion-cache-1dte6k3,
        .stApp > .st-emotion-cache-1hq8t5v, .stApp > .st-emotion-cache-16txtl3,
        .stApp > .st-emotion-cache-1v3ma8w, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1c7y2kd, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1v0mbdj, .stApp > .st-emotion-cache-1v3ma8w,
        .stApp > .st-emotion-cache-1r6slb0, .stApp > .st-emotion-cache-1wrcr25,
        .stApp > .st-emotion-cache-1dte6k3, .stApp > .st-emotion-cache-1hq8t5v,
        .stApp > .st-emotion-cache-16txtl3, .stApp > .st-emotion-cache-1v3ma8w,
        .stApp > .st-emotion-cache-1v0mbdj, .stApp > .st-emotion-cache-1c7y2kd,
        .stApp > .st-emotion-cache-1v0mbdj, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1v3ma8w, .stApp > .st-emotion-cache-1r6slb0,
        .stApp > .st-emotion-cache-1wrcr25, .stApp > .st-emotion-cache-1dte6k3,
        .stApp > .st-emotion-cache-1hq8t5v, .stApp > .st-emotion-cache-16txtl3,
        .stApp > .st-emotion-cache-1v3ma8w, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1c7y2kd, .stApp > .st-emotion-cache-1v0mbdj,
        .stApp > .st-emotion-cache-1v0mbdj {
            display: none !important;
        }
        /* Show only the print-content div */
        .print-content {
            display: block !important;
            visibility: visible !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 20px !important;
        }
        /* Table formatting */
        table {
            border-collapse: collapse;
            width: 100%;
            font-size: 12px;
        }
        th, td {
            border: 1px solid #000;
            padding: 6px;
            text-align: left;
            word-wrap: break-word;
        }
        th {
            background-color: #f2f2f2;
        }
        /* Landscape for wide tables */
        .landscape {
            page: landscape;
        }
        /* Signature area */
        .signature-area {
            margin-top: 40px;
            display: flex;
            justify-content: space-between;
        }
        .signature-item {
            text-align: center;
            width: 30%;
        }
        .signature-line {
            border-top: 1px solid #000;
            margin-top: 30px;
            padding-top: 5px;
        }
        /* Hide print button in print */
        .no-print {
            display: none !important;
        }
    }
    </style>
    """

    st.markdown(print_css, unsafe_allow_html=True)

    # Wrap report output in a div for print
    st.markdown('<div class="print-content">', unsafe_allow_html=True)

    # Determine if we should show signature for official reports
    show_signature = report_type in ["Official VB-G RAM G Summary Report (Template)", "District-wise Summary Report",
                                     "Department-wise Summary Report", "Block-wise Summary Report",
                                     "FY 2026–27 Master Convergence Statement"]

    # Report rendering (with filtered_df)
    if report_type == "Official VB-G RAM G Summary Report (Template)":
        st.subheader("Summary Report on Vikshit Bharat - G RAM G Convergence Plan with Line Departments for F.Y 2026-27")
        st.caption("Official statutory statement format matching state government export guidelines.")

        official_df = pd.DataFrame()
        official_df["District"] = filtered_df["district_name"]
        official_df["Converging Department"] = filtered_df["department_name"]
        official_df["Activity / Work / Infrastructure permissible under VB-G RAM G"] = filtered_df["activity_description"]
        official_df["Number / Status (e.g no of AWC in the district)"] = "1"
        official_df["Scheme of the Deptt."] = filtered_df.get("scheme_name", "VB-G RAM G Convergence")
        official_df["Scope under Annual Plan"] = filtered_df.get("work_dimensions", "Standard Scheme Scope")
        official_df["Desired Target for FY 2026-27"] = filtered_df["desired_target"]
        official_df["Type of Convergence Financial/Technical"] = filtered_df["convergence_type"]
        official_df["Fund to be provided by Dept. (Lakhs)"] = filtered_df["department_fund"]
        official_df["Fund to be provided by VB-G RAM G (Lakhs)"] = filtered_df["vbgramg_fund"]
        official_df["PIA for implementation"] = "Line Department / Block PIA"
        official_df["Expected Person-days to be generated"] = filtered_df["expected_persondays"]
        official_df["Duration of implementation"] = "12 Months"
        official_df["Remarks / Status"] = filtered_df["current_status"]

        st.dataframe(official_df, use_container_width=True, hide_index=True)
        # Excel download
        excel = dataframe_to_excel(official_df, "Official_Summary_Report")
        st.download_button("📥 Download Official Format (Excel)", data=excel, file_name="VB_GRAM_G_Summary_Report_FY26_27.xlsx", type="primary")

    elif report_type == "District-wise Summary Report":
        st.subheader("District-wise Convergence Summary Report")
        district_summary = filtered_df.groupby("district_name").agg(
            Activities=("id", "count"), Target=("desired_target", "sum"),
            Dept_Fund=("department_fund", "sum"), VBG_Fund=("vbgramg_fund", "sum"),
            Total_Fund=("total_converged_fund", "sum"), Expected_PD=("expected_persondays", "sum"),
            Actual_PD=("persondays_generated", "sum"), Completion_Avg=("physical_achievement", "mean"),
        ).reset_index()
        st.dataframe(district_summary, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(district_summary, "District_Summary")
        st.download_button("📥 Download District Summary (Excel)", excel, "district_summary_report.xlsx")

    elif report_type == "Department-wise Summary Report":
        st.subheader("Department-wise Convergence Summary Report")
        dept_summary = filtered_df.groupby("department_name").agg(
            Activities=("id", "count"), Target=("desired_target", "sum"),
            Dept_Fund=("department_fund", "sum"), VBG_Fund=("vbgramg_fund", "sum"),
            Total_Fund=("total_converged_fund", "sum"), Expected_PD=("expected_persondays", "sum"),
            Actual_PD=("persondays_generated", "sum"), Completion_Avg=("physical_achievement", "mean"),
        ).reset_index()
        st.dataframe(dept_summary, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(dept_summary, "Department_Summary")
        st.download_button("📥 Download Department Summary (Excel)", excel, "department_summary_report.xlsx")

    elif report_type == "Block-wise Summary Report":
        st.subheader("Block-wise Convergence Summary Report")
        block_summary = filtered_df.groupby(["district_name", "block_name"]).agg(
            Activities=("id", "count"), Target=("desired_target", "sum"),
            Funds=("total_converged_fund", "sum"), Persondays=("expected_persondays", "sum"),
        ).reset_index()
        st.dataframe(block_summary, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(block_summary, "Block_Summary")
        st.download_button("📥 Download Block Summary (Excel)", excel, "block_summary_report.xlsx")

    elif report_type == "District Performance Dashboard":
        st.subheader("District Performance Analytics")
        if not filtered_df.empty:
            fig = px.bar(filtered_df, x="district_name", y="total_converged_fund", color="department_name", title="Total Converged Funds by District & Department")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected filters.")

    elif report_type == "Department Performance Dashboard":
        st.subheader("Department Performance Analytics")
        if not filtered_df.empty:
            fig = px.pie(filtered_df, names="department_name", values="desired_target", title="Department Target Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected filters.")

    elif report_type == "Block Performance Dashboard":
        st.subheader("Block Performance Analytics")
        if not filtered_df.empty:
            fig = px.bar(filtered_df, x="block_name", y="physical_achievement", color="department_name", barmode="group", title="Block-wise Physical Achievement %")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected filters.")

    elif report_type == "Scheme Performance Report":
        st.subheader("Scheme-wise Performance Report")
        scheme_perf = filtered_df.groupby(["activity_description", "department_name"]).agg(
            Target=("desired_target", "sum"), Physical_Ach=("physical_achievement", "mean"),
            Financial_Ach=("financial_achievement", "mean"), Persondays_Expected=("expected_persondays", "sum"),
            Persondays_Actual=("persondays_generated", "sum"),
        ).reset_index()
        st.dataframe(scheme_perf, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(scheme_perf, "Scheme_Performance")
        st.download_button("📥 Download Scheme Performance (Excel)", excel, "scheme_performance.xlsx")

    elif report_type == "Personday Generation Report":
        st.subheader("Personday Generation Analysis")
        pd_df = filtered_df.groupby("district_name").agg(Expected=("expected_persondays", "sum"), Actual=("persondays_generated", "sum")).reset_index()
        pd_df["Achievement%"] = (pd_df["Actual"] / pd_df["Expected"].replace(0, 1)) * 100
        st.dataframe(pd_df, use_container_width=True, hide_index=True)
        fig = px.bar(pd_df, x="district_name", y=["Expected", "Actual"], barmode="group", title="Expected vs Actual Persondays by District")
        st.plotly_chart(fig, use_container_width=True)
        excel = dataframe_to_excel(pd_df, "Personday_Report")
        st.download_button("📥 Download Personday Report (Excel)", excel, "personday_report.xlsx")

    elif report_type == "Financial Convergence Report (Fund Gap Analysis)":
        st.subheader("Financial Convergence & Funding Gap Analysis")
        fin_df = filtered_df.groupby("district_name").agg(
            Dept_Fund=("department_fund", "sum"), VBG_Fund=("vbgramg_fund", "sum"), Total_Converged=("total_converged_fund", "sum"),
        ).reset_index()
        st.dataframe(fin_df, use_container_width=True, hide_index=True)
        fig = px.bar(fin_df, x="district_name", y=["Dept_Fund", "VBG_Fund"], title="Financial Convergence Breakdown by District", barmode="stack")
        st.plotly_chart(fig, use_container_width=True)
        excel = dataframe_to_excel(fin_df, "Financial_Convergence")
        st.download_button("📥 Download Financial Report (Excel)", excel, "financial_convergence_report.xlsx")

    elif report_type == "Technical Convergence Report (NOC Status)":
        st.subheader("Technical Convergence & Zero-Fund NOC Report")
        tech_df = filtered_df[filtered_df["convergence_type"].str.contains("Technical", na=False, case=False)]
        if not tech_df.empty:
            tech_summary = tech_df.groupby("department_name").agg(Technical_Activities_Count=("id", "count")).reset_index()
            st.dataframe(tech_summary, use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(tech_summary, "Technical_Report")
            st.download_button("📥 Download Technical Report (Excel)", excel, "technical_convergence_report.xlsx")
        else:
            st.info("No technical convergence activities recorded.")

    elif report_type == "Pending / Delayed Activities Report":
        st.subheader("Risk & Delay Monitoring: Pending / Delayed Activities")
        delayed = filtered_df[filtered_df["current_status"].isin(["Planned", "Approved", "Delayed"]) | (filtered_df.get("delay_days", 0) > 0)]
        if not delayed.empty:
            cols = ["id", "activity_description", "district_name", "department_name", "current_status"]
            if "delay_days" in delayed.columns: cols.append("delay_days")
            st.dataframe(delayed[cols], use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(delayed, "Delayed_Activities")
            st.download_button("📥 Download Delayed Activities (Excel)", excel, "delayed_activities_report.xlsx")
        else:
            st.success("🎉 No pending or delayed activities found!")

    elif report_type == "FY 2026–27 Master Convergence Statement":
        st.subheader("Master Convergence Statement FY 2026-27")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(filtered_df, "Master_Statement")
        st.download_button("📥 Download Master Statement (Excel)", excel, "master_convergence_statement_fy26_27.xlsx", type="primary")

    elif report_type == "District Convergence Meeting Register":
        st.subheader("District Convergence Meeting Register")
        meetings = supabase.table("meetings").select("*").eq("meeting_type", "District").execute().data or []
        if meetings:
            df_m = pd.DataFrame(meetings)
            # Apply district filter if any
            if filter_values.get("district"):
                # Map district names to IDs and filter
                district_ids = [d["id"] for d in districts if d["district_name"] in filter_values["district"]]
                if district_ids:
                    df_m = df_m[df_m["district_id"].isin(district_ids)]
            st.dataframe(df_m, use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(df_m, "District_Meetings")
            st.download_button("📥 Download Meeting Register (Excel)", excel, "district_convergence_meetings.xlsx")
        else:
            st.info("No district meetings recorded.")

    elif report_type == "Department-wise Resolution Statement":
        st.subheader("Department-wise Resolution & ATR Register")
        resolutions = supabase.table("meeting_action_points").select("*").execute().data or []
        if resolutions:
            df_res = pd.DataFrame(resolutions)
            df_res["Department"] = df_res["department_id"].map(dept_map).fillna("Unknown")
            # Apply department filter if any
            if filter_values.get("department"):
                df_res = df_res[df_res["Department"].isin(filter_values["department"])]
            st.dataframe(df_res[["Department", "action_point", "target", "deadline", "status", "remarks"]], use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(df_res, "Resolution_Statement")
            st.download_button("📥 Download Resolution Statement (Excel)", excel, "department_resolutions_statement.xlsx")
        else:
            st.info("No resolutions recorded in the system.")

    # ==========================================
    # 8. PRINT BUTTON (only show if data present)
    # ==========================================
    st.markdown('</div>', unsafe_allow_html=True)  # close print-content div

    # Add signature area for official reports
    if show_signature and not filtered_df.empty:
        st.markdown("""
        <div class="signature-area print-only">
            <div class="signature-item">
                <div class="signature-line">Prepared By</div>
            </div>
            <div class="signature-item">
                <div class="signature-line">Checked By</div>
            </div>
            <div class="signature-item">
                <div class="signature-line">Approved By</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Print button (outside print-content, will be hidden in print)
    st.markdown('<div class="no-print">', unsafe_allow_html=True)
    if st.button("🖨️ Print Report", type="primary"):
        # Use JavaScript to print
        st.components.v1.html(
            """
            <script>
            window.print();
            </script>
            """,
            height=0,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # 9. EXISTING EXPORTS (already present in each branch)
    # ==========================================
    # All exports remain as is.
