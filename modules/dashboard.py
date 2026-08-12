import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.db import get_supabase
from auth.auth import get_current_user, require_role

def inject_custom_css():
    """Injects trendy CSS to elevate the UI elements, specifically KPI cards."""
    st.markdown("""
        <style>
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
        </style>
    """, unsafe_allow_html=True)

def show():
    require_role('superadmin', 'district', 'block', 'department')
    
    # Apply custom UI styling
    inject_custom_css()
    
    # Modern, clean title
    st.markdown("<h1 style='text-align: center; color: #1F77B4; margin-bottom: 30px;'>Convergence Master Dashboard<br><span style='font-size: 0.5em; color: #7F8C8D;'>FY 2026‑27</span></h1>", unsafe_allow_html=True)

    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # --- BRANDED COLOR PALETTE FOR PLOTLY ---
    # Slate, Teal, Muted Gold, Soft Coral, Steel Blue
    CHART_COLORS = ['#2C3E50', '#18BC9C', '#F39C12', '#E74C3C', '#3498DB']
    CHART_TEMPLATE = "plotly_white"

    # ---------- GLOBAL FILTERS ----------
    with st.sidebar:
        st.markdown("### 🎛️ Data Filters")
        districts_query = supabase.table("districts").select("id,district_name").eq("active", True)
        if role == 'district':
            districts_query = districts_query.eq("id", user['district_id'])
        districts_data = districts_query.execute().data
        district_names = ["All"] + [d['district_name'] for d in districts_data]
        district_sel = st.selectbox("📍 District", district_names, key="district_filter")

        dept_data = supabase.table("departments").select("id,department_name").eq("active", True).execute().data
        if role == 'department':
            dept_data = [d for d in dept_data if d['id'] == user['department_id']]
        dept_names = ["All"] + [d['department_name'] for d in dept_data]
        dept_sel = st.selectbox("🏢 Department", dept_names, key="dept_filter")

        theme_data = supabase.table("themes").select("id,theme_name").eq("active", True).execute().data
        theme_names = ["All"] + [t['theme_name'] for t in theme_data]
        theme_sel = st.selectbox("🎯 Theme", theme_names, key="theme_filter")

        status_list = ["All", "Planned", "Approved", "Under Implementation", "Completed", "Delayed"]
        status_sel = st.selectbox("📊 Status", status_list, key="status_filter")

    # ---------- DATA FETCHING ----------
    query = supabase.table("convergence_register").select("*")
    if role == 'district':
        query = query.eq("district_id", user['district_id'])
    elif role == 'block':
        query = query.eq("block_id", user['block_id'])
    elif role == 'department':
        query = query.eq("department_id", user['department_id']).eq("district_id", user['district_id'])

    if district_sel != "All":
        dist_id = next(d['id'] for d in districts_data if d['district_name'] == district_sel)
        query = query.eq("district_id", dist_id)
    if dept_sel != "All":
        dept_id = next(d['id'] for d in dept_data if d['department_name'] == dept_sel)
        query = query.eq("department_id", dept_id)
    if theme_sel != "All":
        theme_id = next(t['id'] for t in theme_data if t['theme_name'] == theme_sel)
        query = query.eq("thematic_category_id", theme_id)
    if status_sel != "All":
        query = query.eq("current_status", status_sel)

    # Wrap execution in try/except to catch the exact API error
    try:
        data = query.execute().data
    except Exception as e:
        st.error(f"⚠️ Database Error: Please check your Supabase schema. Details: {str(e)}")
        st.stop()

    df = pd.DataFrame(data)

    if df.empty:
        st.info("💡 No convergence activities match the current filters and your access level.")
        return

    # ---------- KPI CARDS ----------
    st.subheader("Key Performance Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Activities", len(df))
    with col2:
        total_target = df.get('desired_target', pd.Series([0])).sum()
        st.metric("Total Target", f"{total_target:,}" if total_target else 0)
    with col3:
        total_dept_fund = df.get('department_fund', pd.Series([0])).sum()
        st.metric("Dept. Fund (₹ Lakhs)", f"₹{total_dept_fund:,.2f}")
    with col4:
        total_vbg_fund = df.get('vbgramg_fund', pd.Series([0])).sum()
        st.metric("VB-G RAM G Fund (₹ Lakhs)", f"₹{total_vbg_fund:,.2f}")
    with col5:
        total_converged = df.get('total_converged_fund', pd.Series([0])).sum()
        st.metric("Total Converged (₹ Lakhs)", f"₹{total_converged:,.2f}")

    # Add a visual spacer
    st.write("") 

    col6, col7, col8, col9, col10 = st.columns(5)
    with col6:
        expected_pd = df.get('expected_persondays', pd.Series([0])).sum()
        st.metric("Expected Persondays", f"{expected_pd:,}")
    with col7:
        actual_pd = df.get('persondays_generated', pd.Series([0])).sum()
        st.metric("Actual Persondays", f"{actual_pd:,}")
    with col8:
        completed = len(df[df.get('current_status', '') == 'Completed'])
        total_acts = len(df)
        completion = (completed / total_acts * 100) if total_acts else 0
        st.metric("Completion %", f"{completion:.1f}%")
    with col9:
        phys_avg = df.get('physical_achievement', pd.Series([0])).mean()
        st.metric("Avg Physical Ach.", f"{phys_avg:.1f}%")
    with col10:
        fin_avg = df.get('financial_achievement', pd.Series([0])).mean()
        st.metric("Avg Financial Ach.", f"₹{fin_avg:,.2f} Lakhs" if not pd.isna(fin_avg) else "₹0 Lakhs")

    # ---------- CHARTS ----------
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Performance Visualizations")

    # Helper function to style plots cleanly
    def apply_trendy_layout(fig, title):
        fig.update_layout(
            title=title,
            template=CHART_TEMPLATE,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#2C3E50'),
            margin=dict(t=50, l=10, r=10, b=10),
            hovermode="x unified"
        )
        return fig

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        # Chart 1: Department-wise Target vs Achievement
        if not df.empty and 'department_id' in df.columns:
            dept_perf = df.groupby('department_id').agg(
                Target=('desired_target', 'sum'),
                Achievement=('physical_achievement', 'mean')
            ).reset_index()
            dept_names_map = {d['id']: d['department_name'] for d in dept_data}
            dept_perf['Department'] = dept_perf['department_id'].map(dept_names_map)
            
            fig1 = go.Figure(data=[
                go.Bar(name='Target', x=dept_perf['Department'], y=dept_perf['Target'], marker_color=CHART_COLORS[0]),
                go.Bar(name='Avg Achievement %', x=dept_perf['Department'], y=dept_perf['Achievement'], marker_color=CHART_COLORS[1])
            ])
            fig1 = apply_trendy_layout(fig1, "Department-wise Target vs Achievement")
            st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        # Chart 3: Department Fund vs VB-G RAM G Fund
        if not df.empty:
            fig3 = px.bar(
                df.groupby('department_id')[['department_fund', 'vbgramg_fund']].sum().reset_index(),
                x='department_id', y=['department_fund', 'vbgramg_fund'],
                labels={'value': 'Fund (₹ Lakhs)', 'variable': 'Source'},
                color_discrete_sequence=[CHART_COLORS[2], CHART_COLORS[4]]
            )
            fig3 = apply_trendy_layout(fig3, "Financial Convergence by Department")
            st.plotly_chart(fig3, use_container_width=True)

    # Chart 7: Activity Status Pie
    st.markdown("<br>", unsafe_allow_html=True)
    col_pie1, col_pie2 = st.columns(2)
    
    with col_pie1:
        if 'current_status' in df.columns:
            status_count = df['current_status'].value_counts().reset_index()
            status_count.columns = ['Status', 'Count']
            fig7 = px.pie(
                status_count, values='Count', names='Status', 
                hole=0.4, # Makes it a trendy donut chart
                color_discrete_sequence=CHART_COLORS
            )
            fig7 = apply_trendy_layout(fig7, "Activity Status Distribution")
            st.plotly_chart(fig7, use_container_width=True)

    with col_pie2:
        # Chart 4: Financial Convergence by Theme
        if 'thematic_category_id' in df.columns and theme_sel == "All":
            theme_perf = df.groupby('thematic_category_id').agg(
                Dept_Fund=('department_fund', 'sum'),
                VBG_Fund=('vbgramg_fund', 'sum')
            ).reset_index()
            theme_names_map = {t['id']: t['theme_name'] for t in theme_data}
            theme_perf['Theme'] = theme_perf['thematic_category_id'].map(theme_names_map)
            fig4 = px.bar(
                theme_perf, x='Theme', y=['Dept_Fund', 'VBG_Fund'], 
                barmode='stack',
                labels={'value': 'Fund (₹ Lakhs)', 'variable': 'Source'},
                color_discrete_sequence=[CHART_COLORS[0], CHART_COLORS[1]]
            )
            fig4 = apply_trendy_layout(fig4, "Financial Convergence by Theme")
            st.plotly_chart(fig4, use_container_width=True)

    # ---------- DELAYED ACTIVITIES ----------
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Delayed Activities")
    delayed = df[df.get('delay_days', 0) > 0] if 'delay_days' in df.columns else pd.DataFrame()
    if not delayed.empty:
        st.dataframe(
            delayed[['activity_description', 'current_status', 'delay_days']].head(10),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ No delayed activities in current view.")

    # ---------- EXCEL EXPORT ----------
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Data Export")
    from utils.excel import dataframe_to_excel
    excel_data = dataframe_to_excel(df, "dashboard_data")
    
    st.download_button(
        label="📥 Download Filtered Data (Excel)", 
        data=excel_data, 
        file_name="convergence_dashboard_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
