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
    # 3. BASE QUERY & ROLE SCOPE (Unchanged Logic)
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
    # 4. MASTER DATA & MAPPINGS (Unchanged Logic)
    # ==========================================
    districts = supabase.table("districts").select("id,district_name").execute().data or []
    blocks = supabase.table("blocks").select("id,block_name").execute().data or []
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
    # 5. REPORT CONTROL CENTRE (MOVED FROM SIDEBAR)
    # ==========================================
    st.markdown("#### ⚙️ Report Generation Settings")
    with st.container(border=True):
        col_c1, col_c2 = st.columns(2)
        
        report_category = col_c1.selectbox("1. Select Report Category", [
            "Official Statutory Reports",
            "Executive & Performance Analytics",
            "Financial & Technical Analytics",
            "Risk, Delay & Master Statements",
            "Meeting & Resolution Register"
        ])

        # Cascading selectbox
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

    # =====================================================================
    # 6. RENDER THE SELECTED REPORT (Unchanged Logic & Data Generation)
    # =====================================================================
    if report_type == "Official VB-G RAM G Summary Report (Template)":
        st.subheader("Summary Report on Vikshit Bharat - G RAM G Convergence Plan with Line Departments for F.Y 2026-27")
        st.caption("Official statutory statement format matching state government export guidelines.")

        official_df = pd.DataFrame()
        official_df["District"] = df["district_name"]
        official_df["Converging Department"] = df["department_name"]
        official_df["Activity / Work / Infrastructure permissible under VB-G RAM G"] = df["activity_description"]
        official_df["Number / Status (e.g no of AWC in the district)"] = "1"
        official_df["Scheme of the Deptt."] = df.get("scheme_name", "VB-G RAM G Convergence")
        official_df["Scope under Annual Plan"] = df.get("work_dimensions", "Standard Scheme Scope")
        official_df["Desired Target for FY 2026-27"] = df["desired_target"]
        official_df["Type of Convergence Financial/Technical"] = df["convergence_type"]
        official_df["Fund to be provided by Dept. (Lakhs)"] = df["department_fund"]
        official_df["Fund to be provided by VB-G RAM G (Lakhs)"] = df["vbgramg_fund"]
        official_df["PIA for implementation"] = "Line Department / Block PIA"
        official_df["Expected Person-days to be generated"] = df["expected_persondays"]
        official_df["Duration of implementation"] = "12 Months"
        official_df["Remarks / Status"] = df["current_status"]

        st.dataframe(official_df, use_container_width=True, hide_index=True)

        excel = dataframe_to_excel(official_df, "Official_Summary_Report")
        st.download_button("📥 Download Official Format (Excel)", data=excel, file_name="VB_GRAM_G_Summary_Report_FY26_27.xlsx", type="primary")

    elif report_type == "District-wise Summary Report":
        st.subheader("District-wise Convergence Summary Report")
        district_summary = df.groupby("district_name").agg(
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
        dept_summary = df.groupby("department_name").agg(
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
        block_summary = df.groupby(["district_name", "block_name"]).agg(
            Activities=("id", "count"), Target=("desired_target", "sum"),
            Funds=("total_converged_fund", "sum"), Persondays=("expected_persondays", "sum"),
        ).reset_index()
        st.dataframe(block_summary, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(block_summary, "Block_Summary")
        st.download_button("📥 Download Block Summary (Excel)", excel, "block_summary_report.xlsx")

    elif report_type == "District Performance Dashboard":
        st.subheader("District Performance Analytics")
        if not df.empty:
            fig = px.bar(df, x="district_name", y="total_converged_fund", color="department_name", title="Total Converged Funds by District & Department")
            st.plotly_chart(fig, use_container_width=True)

    elif report_type == "Department Performance Dashboard":
        st.subheader("Department Performance Analytics")
        if not df.empty:
            fig = px.pie(df, names="department_name", values="desired_target", title="Department Target Distribution")
            st.plotly_chart(fig, use_container_width=True)

    elif report_type == "Block Performance Dashboard":
        st.subheader("Block Performance Analytics")
        if not df.empty:
            fig = px.bar(df, x="block_name", y="physical_achievement", color="department_name", barmode="group", title="Block-wise Physical Achievement %")
            st.plotly_chart(fig, use_container_width=True)

    elif report_type == "Scheme Performance Report":
        st.subheader("Scheme-wise Performance Report")
        scheme_perf = df.groupby(["activity_description", "department_name"]).agg(
            Target=("desired_target", "sum"), Physical_Ach=("physical_achievement", "mean"),
            Financial_Ach=("financial_achievement", "mean"), Persondays_Expected=("expected_persondays", "sum"),
            Persondays_Actual=("persondays_generated", "sum"),
        ).reset_index()
        st.dataframe(scheme_perf, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(scheme_perf, "Scheme_Performance")
        st.download_button("📥 Download Scheme Performance (Excel)", excel, "scheme_performance.xlsx")

    elif report_type == "Personday Generation Report":
        st.subheader("Personday Generation Analysis")
        pd_df = df.groupby("district_name").agg(Expected=("expected_persondays", "sum"), Actual=("persondays_generated", "sum")).reset_index()
        pd_df["Achievement%"] = (pd_df["Actual"] / pd_df["Expected"].replace(0, 1)) * 100
        st.dataframe(pd_df, use_container_width=True, hide_index=True)
        
        fig = px.bar(pd_df, x="district_name", y=["Expected", "Actual"], barmode="group", title="Expected vs Actual Persondays by District")
        st.plotly_chart(fig, use_container_width=True)
        
        excel = dataframe_to_excel(pd_df, "Personday_Report")
        st.download_button("📥 Download Personday Report (Excel)", excel, "personday_report.xlsx")

    elif report_type == "Financial Convergence Report (Fund Gap Analysis)":
        st.subheader("Financial Convergence & Funding Gap Analysis")
        fin_df = df.groupby("district_name").agg(
            Dept_Fund=("department_fund", "sum"), VBG_Fund=("vbgramg_fund", "sum"), Total_Converged=("total_converged_fund", "sum"),
        ).reset_index()
        st.dataframe(fin_df, use_container_width=True, hide_index=True)
        
        fig = px.bar(fin_df, x="district_name", y=["Dept_Fund", "VBG_Fund"], title="Financial Convergence Breakdown by District", barmode="stack")
        st.plotly_chart(fig, use_container_width=True)
        
        excel = dataframe_to_excel(fin_df, "Financial_Convergence")
        st.download_button("📥 Download Financial Report (Excel)", excel, "financial_convergence_report.xlsx")

    elif report_type == "Technical Convergence Report (NOC Status)":
        st.subheader("Technical Convergence & Zero-Fund NOC Report")
        tech_df = df[df["convergence_type"].str.contains("Technical", na=False, case=False)]
        if not tech_df.empty:
            tech_summary = tech_df.groupby("department_name").agg(Technical_Activities_Count=("id", "count")).reset_index()
            st.dataframe(tech_summary, use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(tech_summary, "Technical_Report")
            st.download_button("📥 Download Technical Report (Excel)", excel, "technical_convergence_report.xlsx")
        else:
            st.info("No technical convergence activities recorded.")

    elif report_type == "Pending / Delayed Activities Report":
        st.subheader("Risk & Delay Monitoring: Pending / Delayed Activities")
        delayed = df[df["current_status"].isin(["Planned", "Approved", "Delayed"]) | (df.get("delay_days", 0) > 0)]
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
        st.dataframe(df, use_container_width=True, hide_index=True)
        excel = dataframe_to_excel(df, "Master_Statement")
        st.download_button("📥 Download Master Statement (Excel)", excel, "master_convergence_statement_fy26_27.xlsx", type="primary")

    elif report_type == "District Convergence Meeting Register":
        st.subheader("District Convergence Meeting Register")
        meetings = supabase.table("meetings").select("*").eq("meeting_type", "District").execute().data or []
        if meetings:
            df_m = pd.DataFrame(meetings)
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
            st.dataframe(df_res[["Department", "action_point", "target", "deadline", "status", "remarks"]], use_container_width=True, hide_index=True)
            excel = dataframe_to_excel(df_res, "Resolution_Statement")
            st.download_button("📥 Download Resolution Statement (Excel)", excel, "department_resolutions_statement.xlsx")
        else:
            st.info("No resolutions recorded in the system.")
