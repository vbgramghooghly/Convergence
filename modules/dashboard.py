import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from auth.auth import get_current_user, require_role
from utils.db import get_supabase


def inject_custom_css():
  """Injects trendy CSS to elevate the UI elements, specifically KPI cards

  and hides the Streamlit toolbar (Fork/GitHub buttons).
  """
  st.markdown(
      """
    <style>
    /* Hide Streamlit toolbar (Fork and GitHub buttons) */
    .stAppToolbar {
        visibility: hidden !important;
    }
    
    /* Style the metric containers to look like sleek cards */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    /* Make subheaders look more modern */
    h3 {
        color: #2C3E50;
        font-weight: 600;
        padding-bottom: 10px;
        border-bottom: 2px solid #E9ECEF;
        margin-bottom: 20px;
    }
    /* Print Styles for the Plan */
    @media print {
        .no-print { display: none !important; }
    }
    </style>
    """,
      unsafe_allow_html=True,
  )


def show():
  require_role("superadmin", "district", "block", "department")

  # Apply custom UI styling (hides toolbar & styles cards)
  inject_custom_css()

  # Modern, clean title
  st.markdown(
      "<h1 style='text-align: center; color: #1F77B4; margin-bottom:"
      " 30px;'>Convergence Master Dashboard<br><span style='font-size: 0.5em;"
      " color: #7F8C8D;'>FY 2026‑27</span></h1>",
      unsafe_allow_html=True,
  )

  supabase = get_supabase()
  user = get_current_user()
  role = user["role"]

  # --- BRANDED COLOR PALETTE FOR PLOTLY ---
  CHART_COLORS = ["#2C3E50", "#18BC9C", "#F39C12", "#E74C3C", "#3498DB"]
  CHART_TEMPLATE = "plotly_white"

  # ---------- GLOBAL FILTERS ----------
  with st.sidebar:
    st.markdown("### 🎛️ Data Filters")
    districts_query = (
        supabase.table("districts").select("id,district_name").eq("active", True)
    )
    if role == "district":
      districts_query = districts_query.eq("id", user["district_id"])
    districts_data = districts_query.execute().data
    district_names = ["All"] + [d["district_name"] for d in districts_data]
    district_sel = st.selectbox("📍 District", district_names, key="district_filter")

    all_dept_data = (
        supabase.table("departments")
        .select("id,department_name")
        .eq("active", True)
        .execute()
        .data
    )
    dept_data = all_dept_data
    if role == "department":
      dept_data = [d for d in dept_data if d["id"] == user["department_id"]]
    dept_names = ["All"] + [d["department_name"] for d in dept_data]
    dept_sel = st.selectbox("🏢 Department", dept_names, key="dept_filter")

    theme_data = (
        supabase.table("themes")
        .select("id,theme_name")
        .eq("active", True)
        .execute()
        .data
    )
    theme_names = ["All"] + [t["theme_name"] for t in theme_data]
    theme_sel = st.selectbox("🎯 Theme", theme_names, key="theme_filter")

    status_list = [
        "All",
        "Planned",
        "Approved",
        "Under Implementation",
        "Completed",
        "Delayed",
    ]
    status_sel = st.selectbox("📊 Status", status_list, key="status_filter")

    # Fetch blocks for mapping in the plan
    blocks_data = supabase.table("blocks").select("id,block_name").execute().data

  # ---------- DATA FETCHING ----------
  query = supabase.table("convergence_register").select("*")
  if role == "district":
    query = query.eq("district_id", user["district_id"])
  elif role == "block":
    query = query.eq("block_id", user["block_id"])
  elif role == "department":
    query = query.eq("department_id", user["department_id"]).eq(
        "district_id", user["district_id"]
    )

  if district_sel != "All":
    dist_id = next(
        d["id"] for d in districts_data if d["district_name"] == district_sel
    )
    query = query.eq("district_id", dist_id)
  if dept_sel != "All":
    dept_id = next(
        d["id"] for d in dept_data if d["department_name"] == dept_sel
    )
    query = query.eq("department_id", dept_id)
  if theme_sel != "All":
    theme_id = next(t["id"] for t in theme_data if t["theme_name"] == theme_sel)
    query = query.eq("thematic_category_id", theme_id)
  if status_sel != "All":
    query = query.eq("current_status", status_sel)

  # Wrap execution in try/except
  try:
    data = query.execute().data
  except Exception as e:
    st.error(
        f"⚠️ Database Error: Please check your Supabase schema. Details:"
        f" {str(e)}"
    )
    st.stop()

  df = pd.DataFrame(data)

  if df.empty:
    st.info(
        "💡 No convergence activities match the current filters and your access"
        " level."
    )
    return

  # Helper function to style plots cleanly
  def apply_trendy_layout(fig, title):
    fig.update_layout(
        title=title,
        template=CHART_TEMPLATE,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#2C3E50"),
        margin=dict(t=50, l=10, r=10, b=10),
        hovermode="x unified",
    )
    return fig

  # Define Dynamic Tab Name for the Plan
  if role == "district" or role == "superadmin":
    plan_tab_name = "📄 District Convergence Plan"
  elif role == "block":
    plan_tab_name = "📄 Block Convergence Plan"
  else:
    plan_tab_name = "📄 Department Convergence Plan"

  # ======================== TABS LAYOUT ========================
  tab1, tab2 = st.tabs(["📊 Dashboard Overview", plan_tab_name])

  # -----------------------------------------------------------
  # TAB 1: DASHBOARD OVERVIEW (KPIs & Charts)
  # -----------------------------------------------------------
  with tab1:
    st.subheader("Key Performance Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
      st.metric("Total Activities", len(df))
    with col2:
      total_target = df.get("desired_target", pd.Series([0])).sum()
      st.metric("Total Target", f"{total_target:,}" if total_target else 0)
    with col3:
      total_dept_fund = df.get("department_fund", pd.Series([0])).sum()
      st.metric("Dept. Fund (₹ Lakhs)", f"₹{total_dept_fund:,.2f}")
    with col4:
      total_vbg_fund = df.get("vbgramg_fund", pd.Series([0])).sum()
      st.metric("VB-G RAM G Fund (₹ Lakhs)", f"₹{total_vbg_fund:,.2f}")
    with col5:
      # Calculate total converged fund dynamically if not explicitly in table
      df["total_converged_fund"] = df.get("department_fund", 0) + df.get(
          "vbgramg_fund", 0
      )
      total_converged = df["total_converged_fund"].sum()
      st.metric("Total Converged (₹ Lakhs)", f"₹{total_converged:,.2f}")

    st.write("")

    col6, col7, col8, col9, col10 = st.columns(5)
    with col6:
      expected_pd = df.get("expected_persondays", pd.Series([0])).sum()
      st.metric("Expected Persondays", f"{expected_pd:,}")
    with col7:
      actual_pd = df.get("persondays_generated", pd.Series([0])).sum()
      st.metric("Actual Persondays", f"{actual_pd:,}")
    with col8:
      completed = len(df[df.get("current_status", "") == "Completed"])
      total_acts = len(df)
      completion = (completed / total_acts * 100) if total_acts else 0
      st.metric("Completion %", f"{completion:.1f}%")
    with col9:
      phys_avg = df.get("physical_achievement", pd.Series([0])).mean()
      st.metric(
          "Avg Physical Ach.",
          f"{phys_avg:.1f}%" if not pd.isna(phys_avg) else "0.0%",
      )
    with col10:
      fin_avg = df.get("financial_achievement", pd.Series([0])).mean()
      st.metric(
          "Avg Financial Ach.",
          f"₹{fin_avg:,.2f} Lakhs" if not pd.isna(fin_avg) else "₹0 Lakhs",
      )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Performance Visualizations")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
      if not df.empty and "department_id" in df.columns:
        dept_perf = (
            df.groupby("department_id")
            .agg(
                Target=("desired_target", "sum"),
                Achievement=("physical_achievement", "mean"),
            )
            .reset_index()
        )
        dept_names_map = {
            d["id"]: d["department_name"] for d in all_dept_data
        }
        dept_perf["Department"] = dept_perf["department_id"].map(
            dept_names_map
        )

        fig1 = go.Figure(
            data=[
                go.Bar(
                    name="Target",
                    x=dept_perf["Department"],
                    y=dept_perf["Target"],
                    marker_color=CHART_COLORS[0],
                ),
                go.Bar(
                    name="Avg Achievement %",
                    x=dept_perf["Department"],
                    y=dept_perf["Achievement"],
                    marker_color=CHART_COLORS[1],
                ),
            ]
        )
        fig1 = apply_trendy_layout(fig1, "Department-wise Target vs Achievement")
        st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
      if not df.empty:
        fig3 = px.bar(
            df.groupby("department_id")[
                ["department_fund", "vbgramg_fund"]
            ].sum().reset_index(),
            x="department_id",
            y=["department_fund", "vbgramg_fund"],
            labels={"value": "Fund (₹ Lakhs)", "variable": "Source"},
            color_discrete_sequence=[CHART_COLORS[2], CHART_COLORS[4]],
        )
        fig3.update_xaxes(
            tickvals=df["department_id"].unique(),
            ticktext=[
                dept_names_map.get(x, "Unknown")
                for x in df["department_id"].unique()
            ],
        )
        fig3 = apply_trendy_layout(fig3, "Financial Convergence by Department")
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_pie1, col_pie2 = st.columns(2)

    with col_pie1:
      if "current_status" in df.columns:
        status_count = df["current_status"].value_counts().reset_index()
        status_count.columns = ["Status", "Count"]
        fig7 = px.pie(
            status_count,
            values="Count",
            names="Status",
            hole=0.4,
            color_discrete_sequence=CHART_COLORS,
        )
        fig7 = apply_trendy_layout(fig7, "Activity Status Distribution")
        st.plotly_chart(fig7, use_container_width=True)

    with col_pie2:
      if "thematic_category_id" in df.columns and theme_sel == "All":
        theme_perf = (
            df.groupby("thematic_category_id")
            .agg(
                Dept_Fund=("department_fund", "sum"),
                VBG_Fund=("vbgramg_fund", "sum"),
            )
            .reset_index()
        )
        theme_names_map = {t["id"]: t["theme_name"] for t in theme_data}
        theme_perf["Theme"] = theme_perf["thematic_category_id"].map(
            theme_names_map
        )
        fig4 = px.bar(
            theme_perf,
            x="Theme",
            y=["Dept_Fund", "VBG_Fund"],
            barmode="stack",
            labels={"value": "Fund (₹ Lakhs)", "variable": "Source"},
            color_discrete_sequence=[CHART_COLORS[0], CHART_COLORS[1]],
        )
        fig4 = apply_trendy_layout(fig4, "Financial Convergence by Theme")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Data Export")
    from utils.excel import dataframe_to_excel

    excel_data = dataframe_to_excel(df, "dashboard_data")

    st.download_button(
        label="📥 Download Raw Data (Excel)",
        data=excel_data,
        file_name="convergence_dashboard_export.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        type="primary",
    )

  # -----------------------------------------------------------
  # TAB 2: DYNAMIC CONVERGENCE PLAN (Aggregated Matrix)
  # -----------------------------------------------------------
  with tab2:
    st.subheader(plan_tab_name)
    st.caption(
        "Auto-generated convergence plan based on live departmental entries."
        " Updates in real-time."
    )

    # Prepare mapping dictionaries
    dept_map_all = {d["id"]: d["department_name"] for d in all_dept_data}
    block_map = {b["id"]: b["block_name"] for b in blocks_data}

    # Format Data for the Plan
    plan_df = df.copy()
    plan_df["Department"] = (
        plan_df.get("department_id").map(dept_map_all).fillna("Unknown")
    )
    plan_df["Block"] = (
        plan_df.get("block_id")
        .map(block_map)
        .fillna("District Level / General")
    )
    plan_df["Activity"] = plan_df.get(
        "activity_description", "Unnamed Activity"
    )

    # Ensure numeric columns are clean
    num_cols = [
        "desired_target",
        "department_fund",
        "vbgramg_fund",
        "total_converged_fund",
        "expected_persondays",
    ]
    for c in num_cols:
      if c not in plan_df.columns:
        plan_df[c] = 0
      plan_df[c] = pd.to_numeric(plan_df[c], errors="coerce").fillna(0)

    # Determine grouping hierarchy based on user role
    if role == "district" or role == "superadmin":
      group_cols = ["Department", "Block", "Activity"]
    elif role == "block":
      group_cols = ["Department", "Activity"]
    elif role == "department":
      group_cols = ["Block", "Activity"]

    # Aggregate the Plan
    plan_summary = (
        plan_df.groupby(group_cols)[num_cols].sum().reset_index()
    )

    # Rename columns for formal presentation
    plan_summary.rename(
        columns={
            "desired_target": "Physical Target",
            "department_fund": "Dept. Fund (₹ Lakhs)",
            "vbgramg_fund": "VB-G RAM G Fund (₹ Lakhs)",
            "total_converged_fund": "Total Fund (₹ Lakhs)",
            "expected_persondays": "Expected Persondays",
        },
        inplace=True,
    )

    # Display the formal plan
    st.dataframe(
        plan_summary.style.format({
            "Dept. Fund (₹ Lakhs)": "{:.2f}",
            "VB-G RAM G Fund (₹ Lakhs)": "{:.2f}",
            "Total Fund (₹ Lakhs)": "{:.2f}",
            "Physical Target": "{:,.0f}",
            "Expected Persondays": "{:,.0f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # Provide a specific download for the Plan
    st.markdown("<br>", unsafe_allow_html=True)
    col_dl, _ = st.columns([1, 3])
    with col_dl:
      buffer = io.BytesIO()
      with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        plan_summary.to_excel(
            writer, index=False, sheet_name="Convergence Plan"
        )

      st.download_button(
          label=f"📥 Download {plan_tab_name}",
          data=buffer.getvalue(),
          file_name=f"{plan_tab_name.replace('📄 ', '').replace(' ', '_')}.xlsx",
          mime=(
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ),
          use_container_width=True,
      )
