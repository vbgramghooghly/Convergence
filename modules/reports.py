import pandas as pd
import plotly.express as px
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.db import get_supabase
from utils.excel import dataframe_to_excel
from utils.theme import apply_global_theme

def show():
    # 1. ENFORCE SECURITY & ACCESS RULES
    require_role("superadmin", "district", "block", "department")
    user = get_current_user()
    role = user["role"]
    supabase = get_supabase()

    # 2. GLOBAL THEME
    theme = apply_global_theme()
    primary_color = theme.get("primary_color", "#0F4C81")

    st.markdown("---")

    # ==========================================
    # 3. BASE QUERY & ROLE SCOPE
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
    # 4. MASTER DATA & MAPPINGS
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
    # 5. REPORT SELECTION (Same row columns)
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
            "Activity-Wise Convergence Report", # Added for your 318 activities
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
    # 6. ADVANCED FILTERS (Popover hidden by default)
    # ==========================================
    filtered_df = df.copy()
    filter_values = {}

    # Determine which filters to show
    show_filters = []
    if report_type in ["Official VB-G RAM G Summary Report (Template)", "District-wise Summary Report",
                       "Department-wise Summary Report", "Block-wise Summary Report",
                       "District Performance Dashboard", "Department Performance Dashboard",
                       "Block Performance Dashboard", "Activity-Wise Convergence Report",
                       "Scheme Performance Report", "Personday Generation Report",
                       "Financial Convergence Report (Fund Gap Analysis)",
                       "Pending / Delayed Activities Report", "FY 2026–27 Master Convergence Statement"]:
        show_filters = ["district", "department", "block", "theme", "status", "financial_year"]
    elif report_type == "Technical Convergence Report (NOC Status)":
        show_filters = ["district", "department", "block", "financial_year"]
    elif report_type in ["District Convergence Meeting Register", "Department-wise Resolution Statement"]:
        show_filters = ["district", "department", "financial_year"]

    # Remove unavailable columns
    available_cols = set(df.columns)
    if "financial_year" not in available_cols:
        show_filters = [f for f in show_filters if f != "financial_year"]
    if "current_status" not in available_cols:
        show_filters = [f for f in show_filters if f != "status"]
    if "theme_name" not in available_cols:
        show_filters = [f for f in show_filters if f != "theme"]

    if show_filters:
        with st.popover("🔍 Click to apply Advanced Filters"):
            cols = st.columns(min(3, len(show_filters)))
            for i, f in enumerate(show_filters):
                col = cols[i % 3]
                if f == "district":
                    districts_list = sorted(df["district_name"].unique())
                    if "Unknown" in districts_list: districts_list.remove("Unknown")
                    selected = col.multiselect("District", districts_list, default=[])
                    filter_values["district"] = selected
                elif f == "block":
                    district_vals = filter_values.get("district", [])
                    if district_vals:
                        block_options = sorted(df[df["district_name"].isin(district_vals)]["block_name"].unique())
                    else:
                        block_options = sorted(df["block_name"].unique())
                    if "Unknown" in block_options: block_options.remove("Unknown")
                    selected = col.multiselect("Block", block_options, default=[])
                    filter_values["block"] = selected
                elif f == "department":
                    dept_options = sorted(df["department_name"].unique())
                    if "Unknown" in dept_options: dept_options.remove("Unknown")
                    selected = col.multiselect("Department", dept_options, default=[])
                    filter_values["department"] = selected
                elif f == "theme":
                    theme_options = sorted(df["theme_name"].unique())
                    if "Unassigned" in theme_options: theme_options.remove("Unassigned")
                    selected = col.multiselect("Theme", theme_options, default=[])
                    filter_values["theme"] = selected
                elif f == "status":
                    status_options = sorted(df["current_status"].unique())
                    selected = col.multiselect("Status", status_options, default=[])
                    filter_values["status"] = selected
                elif f == "financial_year":
                    if "financial_year" in df.columns:
                        fy_options = sorted(df["financial_year"].unique())
                        selected = col.multiselect("Financial Year", fy_options, default=[])
                        filter_values["financial_year"] = selected
                    else:
                        selected = col.selectbox("Financial Year", ["2026-27"], index=0)
                        filter_values["financial_year"] = [selected]

            if st.button("Reset Filters"):
                st.rerun()

        # Apply filters
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

    # ==========================================
    # 7. PRINT CSS (Robust)
    # ==========================================
    print_css = """
    <style>
    @media print {
        header, footer, .stApp .stSidebar, .stApp [data-testid="stToolbar"], 
        .stApp [data-testid="stHeader"], .stApp [data-testid="stStatusWidget"],
        .stApp .st-emotion-cache-1v0mbdj, .stApp .st-emotion-cache-1wrcr25 {
            display: none !important;
        }
        .stApp .main .block-container, .print-content {
            max-width: 100% !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            display: block !important;
            visibility: visible !important;
        }
        table { width: 100% !important; font-size: 10px !important; }
        .stDataFrame { width: 100% !important; }
    }
    </style>
    """
    st.markdown(print_css, unsafe_allow_html=True)
    
    st.markdown('<div class="print-content">', unsafe_allow_html=True)

    # ==========================================
    # 8. RENDER STATUTORY REPORTS
    # ==========================================
    st.markdown(f"### 📄 {report_type}")

    # Shared Column Config for modern tables
    TABLE_CONFIG = {
        "desired_target": st.column_config.NumberColumn("Target", format="%d"),
        "department_fund": st.column_config.NumberColumn("Dept. Fund (₹ L)", format="₹ %.2f"),
        "vbgramg_fund": st.column_config.NumberColumn("VBG Fund (₹ L)", format="₹ %.2f"),
        "total_converged_fund": st.column_config.NumberColumn("Total Fund (₹ L)", format="₹ %.2f"),
        "physical_achievement": st.column_config.ProgressColumn("Achievement", min_value=0, max_value=100, format="%.0f%%"),
        "current_status": st.column_config.SelectboxColumn("Status", options=["Planned", "Approved", "Completed", "Delayed", "Mismatch"]),
        "expected_persondays": st.column_config.NumberColumn("Expected Persondays", format="%d")
    }

    if report_type == "Official VB-G RAM G Summary Report (Template)":
        official_df = pd.DataFrame()
        official_df["District"] = filtered_df["district_name"]
        official_df["Converging Department"] = filtered_df["department_name"]
        official_df["Activity / Work / Infrastructure"] = filtered_df["activity_description"]
        official_df["Scheme of the Deptt."] = filtered_df.get("scheme_name", "VB-G RAM G Convergence")
        official_df["Desired Target FY 2026-27"] = filtered_df["desired_target"]
        official_df["Dept. Fund (₹ Lakhs)"] = filtered_df["department_fund"]
        official_df["VB-G RAM G Fund (₹ Lakhs)"] = filtered_df["vbgramg_fund"]
        official_df["Expected Person-days"] = filtered_df["expected_persondays"]
        official_df["Status"] = filtered_df["current_status"]
        
        st.dataframe(official_df, use_container_width=True, hide_index=True, column_config=TABLE_CONFIG)
        excel = dataframe_to_excel(official_df, "Official_Summary_Report")
        st.download_button("📥 Download Official Format (Excel)", data=excel, file_name="VB_GRAM_G_Summary_Report_FY26_27.xlsx", type="primary")

    elif report_type in ["District-wise Summary Report", "Department-wise Summary Report", "Block-wise Summary Report"]:
        group_col = "district_name" if "District" in report_type else "department_name" if "Department" in report_type else "block_name"
        summary_df = filtered_df.groupby(group_col).agg(
            Activities=("id", "count"), Target=("desired_target", "sum"),
            Dept_Fund=("department_fund", "sum"), VBG_Fund=("vbgramg_fund", "sum"),
            Total_Fund=("total_converged_fund", "sum"), Completion_Avg=("physical_achievement", "mean"),
        ).reset_index()
        st.dataframe(summary_df, use_container_width=True, hide_index=True, column_config=TABLE_CONFIG)
        excel = dataframe_to_excel(summary_df, "Summary_Report")
        st.download_button("📥 Download Summary (Excel)", excel, f"{group_col}_summary_report.xlsx")

    elif report_type == "Activity-Wise Convergence Report":
        st.subheader("Activity-Wise Convergence & Department Mapping (Across All 318 Activities)")
        
        # Group by activity_description
        act_summary = filtered_df.groupby("activity_description").agg(
            Total_Target=("desired_target", "sum"),
            Total_Fund=("total_converged_fund", "sum"),
            Dept_Count=("department_name", "nunique"),
            Mapped_Departments=("department_name", lambda x: ", ".join(sorted(set(x))))
        ).reset_index().rename(columns={"activity_description": "Activity Name"}).sort_values(by="Total_Fund", ascending=False)
        
        st.dataframe(act_summary, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(act_summary, "Activity_Wise_Report")
        st.download_button("📥 Download Activity-Wise Report (Excel)", excel, "activity_wise_convergence_report.xlsx")

    elif report_type in ["District Performance Dashboard", "Department Performance Dashboard", "Block Performance Dashboard"]:
        if not filtered_df.empty:
            group_col = "district_name" if "District" in report_type else "department_name" if "Department" in report_type else "block_name"
            fig = px.bar(filtered_df, x=group_col, y="total_converged_fund", color="department_name", 
                         title=f"{group_col.replace('_', ' ').title()} Performance")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected filters.")

    elif report_type == "Scheme Performance Report":
        scheme_perf = filtered_df.groupby(["activity_description", "department_name"]).agg(
            Target=("desired_target", "sum"), Physical_Ach=("physical_achievement", "mean"),
            Financial_Ach=("financial_achievement", "mean"), Persondays_Expected=("expected_persondays", "sum"),
            Persondays_Actual=("persondays_generated", "sum"),
        ).reset_index()
        st.dataframe(scheme_perf, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(scheme_perf, "Scheme_Performance")
        st.download_button("📥 Download Scheme Performance (Excel)", excel, "scheme_performance.xlsx")

    elif report_type == "Personday Generation Report":
        pd_df = filtered_df.groupby("district_name").agg(Expected=("expected_persondays", "sum"), Actual=("persondays_generated", "sum")).reset_index()
        pd_df["Achievement%"] = (pd_df["Actual"] / pd_df["Expected"].replace(0, 1)) * 100
        st.dataframe(pd_df, use_container_width=True, hide_index=True)
        fig = px.bar(pd_df, x="district_name", y=["Expected", "Actual"], barmode="group", title="Expected vs Actual Persondays by District")
        st.plotly_chart(fig, use_container_width=True)
        excel = dataframe_to_excel(pd_df, "Personday_Report")
        st.download_button("📥 Download Personday Report (Excel)", excel, "personday_report.xlsx")

    elif report_type == "Financial Convergence Report (Fund Gap Analysis)":
        fin_df = filtered_df.groupby("district_name").agg(
            Dept_Fund=("department_fund", "sum"), VBG_Fund=("vbgramg_fund", "sum"), Total_Converged=("total_converged_fund", "sum"),
        ).reset_index()
        st.dataframe(fin_df, use_container_width=True, hide_index=True, column_config=TABLE_CONFIG)
        fig = px.bar(fin_df, x="district_name", y=["Dept_Fund", "VBG_Fund"], title="Financial Convergence Breakdown by District", barmode="stack")
        st.plotly_chart(fig, use_container_width=True)
        excel = dataframe_to_excel(fin_df, "Financial_Convergence")
        st.download_button("📥 Download Financial Report (Excel)", excel, "financial_convergence_report.xlsx")

    elif report_type == "Technical Convergence Report (NOC Status)":
        tech_df = filtered_df[filtered_df["convergence_type"].str.contains("Technical", na=False, case=False)]
        if not tech_df.empty:
            tech_summary = tech_df.groupby("department_name").agg(Technical_Activities_Count=("id", "count")).reset_index()
            st.dataframe(tech_summary, use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(tech_summary, "Technical_Report")
            st.download_button("📥 Download Technical Report (Excel)", excel, "technical_convergence_report.xlsx")
        else:
            st.info("No technical convergence activities recorded.")

    elif report_type == "Pending / Delayed Activities Report":
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
        st.dataframe(filtered_df, use_container_width=True, hide_index=True, column_config=TABLE_CONFIG)
        excel = dataframe_to_excel(filtered_df, "Master_Statement")
        st.download_button("📥 Download Master Statement (Excel)", excel, "master_convergence_statement_fy26_27.xlsx", type="primary")

    elif report_type == "District Convergence Meeting Register":
        meetings = supabase.table("meetings").select("*").eq("meeting_type", "District").execute().data or []
        if meetings:
            df_m = pd.DataFrame(meetings)
            if filter_values.get("district"):
                district_ids = [d["id"] for d in districts if d["district_name"] in filter_values["district"]]
                if district_ids: df_m = df_m[df_m["district_id"].isin(district_ids)]
            st.dataframe(df_m, use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(df_m, "District_Meetings")
            st.download_button("📥 Download Meeting Register (Excel)", excel, "district_convergence_meetings.xlsx")
        else:
            st.info("No district meetings recorded.")

    elif report_type == "Department-wise Resolution Statement":
        resolutions = supabase.table("meeting_action_points").select("*").execute().data or []
        if resolutions:
            df_res = pd.DataFrame(resolutions)
            df_res["Department"] = df_res["department_id"].map(dept_map).fillna("Unknown")
            if filter_values.get("department"): df_res = df_res[df_res["Department"].isin(filter_values["department"])]
            st.dataframe(df_res[["Department", "action_point", "target", "deadline", "status", "remarks"]], use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(df_res, "Resolution_Statement")
            st.download_button("📥 Download Resolution Statement (Excel)", excel, "department_resolutions_statement.xlsx")
        else:
            st.info("No resolutions recorded in the system.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # 9. PRINT / EXPORT BUTTON
    # ==========================================
    st.markdown('<div class="no-print">', unsafe_allow_html=True)
    if st.button("🖨️ Print / Export Report", type="primary", use_container_width=True):
        st.components.v1.html(
            """
            <script>
            window.print();
            </script>
            """,
            height=0,
        )
    st.markdown('</div>', unsafe_allow_html=True)
