from auth.auth import get_current_user, require_role
import pandas as pd
import plotly.express as px
import streamlit as st
from utils.db import get_supabase
from utils.excel import dataframe_to_excel


def inject_custom_css():
  """Injects custom CSS to hide the Streamlit toolbar (Fork/GitHub buttons)."""
  st.markdown(
      """
    <style>
    /* Hide Streamlit toolbar (Fork and GitHub buttons) */
    .stAppToolbar {
        visibility: hidden !important;
    }
    </style>
    """,
      unsafe_allow_html=True,
  )


def show():
  # Allowed all operational roles so they can generate their own reports
  require_role("superadmin", "district", "block", "department")

  # Apply custom UI styling to hide top-right toolbar elements
  inject_custom_css()

  st.title("📊 Reports & Analytics")
  supabase = get_supabase()
  user = get_current_user()
  role = user["role"]

  # Base query with role scope
  query = supabase.table("convergence_register").select("*")
  if role == "district":
    query = query.eq("district_id", user["district_id"])
  elif role == "block":
    query = query.eq("block_id", user["block_id"])
  elif role == "department":
    query = query.eq("department_id", user["department_id"]).eq(
        "district_id", user["district_id"]
    )

  data = query.execute().data

  if not data:
    st.warning("No data available for your user.")
    return

  df = pd.DataFrame(data)

  # Helper to get names
  districts = (
      supabase.table("districts").select("id,district_name").execute().data
  )
  blocks = supabase.table("blocks").select("id,block_name").execute().data
  departments = (
      supabase.table("departments").select("id,department_name").execute().data
  )
  themes = supabase.table("themes").select("id,theme_name").execute().data

  dist_map = {d["id"]: d["district_name"] for d in districts}
  block_map = {b["id"]: b["block_name"] for b in blocks}
  dept_map = {d["id"]: d["department_name"] for d in departments}
  theme_map = {t["id"]: t["theme_name"] for t in themes}

  # Replace IDs with names in df safely
  df["district_name"] = df["district_id"].map(dist_map).fillna("")
  df["block_name"] = df["block_id"].map(block_map).fillna("")
  df["department_name"] = df["department_id"].map(dept_map).fillna("")
  df["theme_name"] = df["thematic_category_id"].map(theme_map).fillna("")

  # Ensure convergence_type exists to avoid errors on older data
  if "convergence_type" not in df.columns:
    df["convergence_type"] = ""

  report_type = st.selectbox(
      "Select Report",
      [
          (
              "Official VB-G RAM G Summary Report (Template)"
          ),  # Added as primary option
          "District-wise Convergence Report",
          "Department-wise Convergence Report",
          "Financial Convergence Report",
          "Technical Convergence Report",
          "Scheme Performance Report",
          "Personday Generation Report",
          "Pending/Delayed Activities",
          "District Convergence Meeting Report",
          "Block Convergence Report",
          "FY 2026–27 Master Convergence Statement",
      ],
  )

  # ========================================================
  # PRIMARY EXPORT FORMAT (Based on Official Image Template)
  # ========================================================
  if report_type == "Official VB-G RAM G Summary Report (Template)":
    st.subheader(
        "Summary Report on Vikshit Bharat -G RAM G Convergence Plan with Line"
        " Departments for F.Y 2026-27"
    )
    st.caption(
        "This format matches the official primary data export template. Missing"
        " fields are left blank for manual entry post-export."
    )

    # Build DataFrame with exact column names from the image
    official_df = pd.DataFrame()
    official_df["District"] = df["district_name"]
    official_df["Converging Department"] = df["department_name"]
    official_df[
        "Activity / Work / Infrastructure permissible under VB-G RAM G"
    ] = df["activity_description"]
    official_df["Number / Status (e.g no of AWC in the district)"] = (
        ""  # Placeholder
    )
    official_df["Scheme of the Deptt."] = ""  # Placeholder
    official_df["Scope under Annual Plan [in respect of column (4)]"] = (
        ""  # Placeholder
    )
    official_df["Desired Target for FY 2026-27 [in respect of column (6)]"] = (
        df["desired_target"]
    )
    official_df["Type of Convergence Financial/Technical"] = df[
        "convergence_type"
    ]
    official_df["Fund to be provided by Dept. (Cr.)"] = df["department_fund"]
    official_df["Fund to be provided by VB-G RAM G (Rs. Cr)"] = df[
        "vbgramg_fund"
    ]
    official_df["PIA for implementation"] = ""  # Placeholder
    official_df["Expected Person-days to be generated"] = df[
        "expected_persondays"
    ]
    official_df["Duration of implementation"] = ""  # Placeholder
    official_df["Remarks"] = df["current_status"]  # Using status as remark by default

    st.dataframe(official_df, use_container_width=True, hide_index=True)

    excel = dataframe_to_excel(official_df, "Official_Summary_Report")
    st.download_button(
        label="📥 Download Official Format (Excel)",
        data=excel,
        file_name="VB_GRAM_G_Summary_Report_FY26_27.xlsx",
        type="primary",
    )

  # ========================================================
  # OTHER ANALYTICAL REPORTS
  # ========================================================
  elif report_type == "District-wise Convergence Report":
    st.subheader("District-wise Convergence Report")
    if not df.empty:
      district_summary = (
          df.groupby("district_name")
          .agg(
              Activities=("id", "count"),
              Target=("desired_target", "sum"),
              Dept_Fund=("department_fund", "sum"),
              VBG_Fund=("vbgramg_fund", "sum"),
              Total_Fund=("total_converged_fund", "sum"),
              Expected_PD=("expected_persondays", "sum"),
              Actual_PD=("persondays_generated", "sum"),
              Completion_Avg=("physical_achievement", "mean"),
          )
          .reset_index()
      )
      st.dataframe(district_summary)
      excel = dataframe_to_excel(district_summary, "District_Report")
      st.download_button("📥 Download Excel", excel, "district_report.xlsx")

  elif report_type == "Department-wise Convergence Report":
    st.subheader("Department-wise Convergence Report")
    dept_summary = (
        df.groupby("department_name")
        .agg(
            Activities=("id", "count"),
            Target=("desired_target", "sum"),
            Dept_Fund=("department_fund", "sum"),
            VBG_Fund=("vbgramg_fund", "sum"),
            Total_Fund=("total_converged_fund", "sum"),
            Expected_PD=("expected_persondays", "sum"),
            Actual_PD=("persondays_generated", "sum"),
            Completion_Avg=("physical_achievement", "mean"),
        )
        .reset_index()
    )
    st.dataframe(dept_summary)
    excel = dataframe_to_excel(dept_summary, "Department_Report")
    st.download_button("📥 Download Excel", excel, "department_report.xlsx")

  elif report_type == "Financial Convergence Report":
    st.subheader("Financial Convergence (Dept Fund vs VB-G RAM G Fund)")
    fin_df = (
        df.groupby("district_name")
        .agg(
            Dept_Fund=("department_fund", "sum"),
            VBG_Fund=("vbgramg_fund", "sum"),
            Total=("total_converged_fund", "sum"),
        )
        .reset_index()
    )
    st.dataframe(fin_df)
    fig = px.bar(
        fin_df,
        x="district_name",
        y=["Dept_Fund", "VBG_Fund"],
        title="Financial Convergence by District",
        barmode="stack",
    )
    st.plotly_chart(fig, use_container_width=True)
    excel = dataframe_to_excel(fin_df, "Financial_Report")
    st.download_button("📥 Download Excel", excel, "financial_report.xlsx")

  elif report_type == "Technical Convergence Report":
    st.subheader("Technical Convergence Activities")
    # Ensure exact match with the new dropdown text from convergence register
    tech_df = df[
        df["convergence_type"].str.contains("Technical", na=False, case=False)
    ]
    if not tech_df.empty:
      tech_summary = (
          tech_df.groupby("department_name")
          .agg(Count=("id", "count"))
          .reset_index()
      )
      st.dataframe(tech_summary)
      excel = dataframe_to_excel(tech_summary, "Technical_Report")
      st.download_button("📥 Download Excel", excel, "technical_report.xlsx")
    else:
      st.info("No technical convergence activities recorded.")

  elif report_type == "Scheme Performance Report":
    st.subheader("Scheme-wise Performance")
    scheme_perf = (
        df.groupby(["activity_description", "department_name"])
        .agg(
            Target=("desired_target", "sum"),
            Physical_Ach=("physical_achievement", "mean"),
            Financial_Ach=("financial_achievement", "mean"),
            Persondays_Expected=("expected_persondays", "sum"),
            Persondays_Actual=("persondays_generated", "sum"),
        )
        .reset_index()
    )
    scheme_perf["Physical%"] = scheme_perf["Physical_Ach"]
    scheme_perf["Financial%"] = (
        scheme_perf["Financial_Ach"] / scheme_perf["Target"].replace(0, 1)
    ) * 100
    st.dataframe(scheme_perf)
    excel = dataframe_to_excel(scheme_perf, "Scheme_Performance")
    st.download_button("📥 Download Excel", excel, "scheme_performance.xlsx")

  elif report_type == "Personday Generation Report":
    st.subheader("Personday Generation Report")
    pd_df = (
        df.groupby("district_name")
        .agg(
            Expected=("expected_persondays", "sum"),
            Actual=("persondays_generated", "sum"),
        )
        .reset_index()
    )
    pd_df["Achievement%"] = (
        pd_df["Actual"] / pd_df["Expected"].replace(0, 1)
    ) * 100
    st.dataframe(pd_df)
    fig = px.bar(
        pd_df,
        x="district_name",
        y=["Expected", "Actual"],
        barmode="group",
        title="Persondays by District",
    )
    st.plotly_chart(fig, use_container_width=True)
    excel = dataframe_to_excel(pd_df, "Personday_Report")
    st.download_button("📥 Download Excel", excel, "personday_report.xlsx")

  elif report_type == "Pending/Delayed Activities":
    st.subheader("Pending / Delayed Activities")
    # Added .get() to safely check for delay_days in case it's missing in some schema states
    delayed = df[
        df["current_status"].isin(["Planned", "Approved", "Delayed"])
        | (df.get("delay_days", 0) > 0)
    ]
    if not delayed.empty:
      cols = [
          "id",
          "activity_description",
          "district_name",
          "department_name",
          "current_status",
      ]
      if "delay_days" in delayed.columns:
        cols.append("delay_days")
      st.dataframe(delayed[cols])
      excel = dataframe_to_excel(delayed, "Delayed_Activities")
      st.download_button(
          "📥 Download Excel", excel, "delayed_activities.xlsx"
      )
    else:
      st.success("No pending or delayed activities!")

  elif report_type == "District Convergence Meeting Report":
    st.subheader("District Convergence Meetings")
    meetings = (
        supabase.table("meetings")
        .select("*")
        .eq("meeting_type", "District")
        .execute()
        .data
    )
    if meetings:
      df_m = pd.DataFrame(meetings)
      st.dataframe(df_m)
      excel = dataframe_to_excel(df_m, "District_Meetings")
      st.download_button("📥 Download Excel", excel, "district_meetings.xlsx")
    else:
      st.info("No district meetings recorded.")

  elif report_type == "Block Convergence Report":
    st.subheader("Block-wise Convergence Summary")
    block_summary = (
        df.groupby(["district_name", "block_name"])
        .agg(
            Activities=("id", "count"),
            Target=("desired_target", "sum"),
            Funds=("total_converged_fund", "sum"),
            Persondays=("expected_persondays", "sum"),
        )
        .reset_index()
    )
    st.dataframe(block_summary)
    excel = dataframe_to_excel(block_summary, "Block_Report")
    st.download_button("📥 Download Excel", excel, "block_report.xlsx")

  elif report_type == "FY 2026–27 Master Convergence Statement":
    st.subheader("Master Convergence Statement FY 2026-27")
    st.dataframe(df)
    excel = dataframe_to_excel(df, "Master_Statement")
    st.download_button("📥 Download Excel", excel, "master_statement.xlsx")
