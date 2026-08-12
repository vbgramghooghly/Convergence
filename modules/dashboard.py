import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.db import get_supabase
from auth.auth import get_current_user, require_role
from datetime import datetime

def show():
    require_role('superadmin', 'district', 'block', 'department')
    st.title("Convergence Master Dashboard – FY 2026‑27")

    supabase = get_supabase()
    user = get_current_user()
    role = user['role']

    # ---------- GLOBAL FILTERS ----------
    st.sidebar.header("Filters")
    districts_query = supabase.table("districts").select("id,district_name").eq("active", True)
    if role == 'district':
        districts_query = districts_query.eq("id", user['district_id'])
    districts_data = districts_query.execute().data
    district_names = ["All"] + [d['district_name'] for d in districts_data]
    district_sel = st.sidebar.selectbox("District", district_names, key="district_filter")

    dept_data = supabase.table("departments").select("id,department_name").eq("active", True).execute().data
    if role == 'department':
        dept_data = [d for d in dept_data if d['id'] == user['department_id']]
    dept_names = ["All"] + [d['department_name'] for d in dept_data]
    dept_sel = st.sidebar.selectbox("Department", dept_names, key="dept_filter")

    theme_data = supabase.table("themes").select("id,theme_name").eq("active", True).execute().data
    theme_names = ["All"] + [t['theme_name'] for t in theme_data]
    theme_sel = st.sidebar.selectbox("Theme", theme_names, key="theme_filter")

    status_list = ["All", "Planned", "Approved", "Under Implementation", "Completed", "Delayed"]
    status_sel = st.sidebar.selectbox("Status", status_list, key="status_filter")

    # ---------- DATA FETCHING (scoped) ----------
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

    data = query.execute().data
    df = pd.DataFrame(data)

    if df.empty:
        st.info("No convergence activities match the current filters and your access level.")
        return

    # ---------- KPI CARDS ----------
    st.subheader("Key Performance Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Activities", len(df))
    with col2:
        total_target = df['desired_target'].sum()
        st.metric("Total Target", f"{total_target:,}" if total_target else 0)
    with col3:
        total_dept_fund = df['department_fund'].sum()
        st.metric("Dept. Fund (₹ Cr.)", f"₹{total_dept_fund:.2f}")
    with col4:
        total_vbg_fund = df['vbgramg_fund'].sum()
        st.metric("VB-G RAM G Fund (₹ Cr.)", f"₹{total_vbg_fund:.2f}")
    with col5:
        total_converged = df['total_converged_fund'].sum()
        st.metric("Total Converged (₹ Cr.)", f"₹{total_converged:.2f}")

    col6, col7, col8, col9, col10 = st.columns(5)
    with col6:
        expected_pd = df['expected_persondays'].sum()
        st.metric("Expected Persondays", f"{expected_pd:,}")
    with col7:
        actual_pd = df['persondays_generated'].sum()
        st.metric("Actual Persondays", f"{actual_pd:,}")
    with col8:
        completed = len(df[df['current_status'] == 'Completed'])
        total_acts = len(df)
        completion = (completed / total_acts * 100) if total_acts else 0
        st.metric("Completion %", f"{completion:.1f}%")
    with col9:
        phys_avg = df['physical_achievement'].mean()
        st.metric("Avg Physical Ach.", f"{phys_avg:.1f}%")
    with col10:
        fin_avg = df['financial_achievement'].mean()
        st.metric("Avg Financial Ach.", f"₹{fin_avg:.2f} Cr." if fin_avg else "₹0")

    # ---------- CHARTS ----------
    st.markdown("---")
    st.subheader("Performance Visualizations")

    # Chart 1: Department-wise Target vs Achievement
    if not df.empty and 'department_id' in df.columns:
        dept_perf = df.groupby('department_id').agg(
            Target=('desired_target', 'sum'),
            Achievement=('physical_achievement', 'mean'),
            Department_Fund=('department_fund', 'sum'),
            VBGFund=('vbgramg_fund', 'sum')
        ).reset_index()
        dept_names_map = {d['id']: d['department_name'] for d in dept_data}
        dept_perf['Department'] = dept_perf['department_id'].map(dept_names_map)
        fig1 = go.Figure(data=[
            go.Bar(name='Target (count)', x=dept_perf['Department'], y=dept_perf['Target']),
            go.Bar(name='Avg Physical Ach. %', x=dept_perf['Department'], y=dept_perf['Achievement'])
        ])
        fig1.update_layout(barmode='group', title="Department-wise Target vs Achievement")
        st.plotly_chart(fig1, use_container_width=True)

    # Chart 2: District-wise Target vs Achievement
    if 'district_id' in df.columns:
        dist_perf = df.groupby('district_id').agg(
            Target=('desired_target', 'sum'),
            Achievement=('physical_achievement', 'mean')
        ).reset_index()
        dist_names_map = {d['id']: d['district_name'] for d in districts_data}
        dist_perf['District'] = dist_perf['district_id'].map(dist_names_map)
        fig2 = px.bar(dist_perf, x='District', y=['Target', 'Achievement'], barmode='group',
                      title="District-wise Target vs Achievement")
        st.plotly_chart(fig2, use_container_width=True)

    # Chart 3: Department Fund vs VB-G RAM G Fund
    if not df.empty:
        fig3 = px.bar(df.groupby('department_id')[['department_fund', 'vbgramg_fund']].sum().reset_index(),
                      x='department_id', y=['department_fund', 'vbgramg_fund'],
                      labels={'value': 'Fund (₹ Cr.)', 'variable': 'Source'},
                      title="Financial Convergence by Department")
        st.plotly_chart(fig3, use_container_width=True)

    # Chart 4: Financial Convergence by Theme
    if 'thematic_category_id' in df.columns and theme_sel == "All":
        theme_perf = df.groupby('thematic_category_id').agg(
            Dept_Fund=('department_fund', 'sum'),
            VBG_Fund=('vbgramg_fund', 'sum')
        ).reset_index()
        theme_names_map = {t['id']: t['theme_name'] for t in theme_data}
        theme_perf['Theme'] = theme_perf['thematic_category_id'].map(theme_names_map)
        fig4 = px.bar(theme_perf, x='Theme', y=['Dept_Fund', 'VBG_Fund'], barmode='stack',
                      title="Financial Convergence by Theme")
        st.plotly_chart(fig4, use_container_width=True)

    # Chart 5: Technical Convergence by Department
    tech_df = df[df['convergence_type'].isin(['Technical', 'Financial + Technical'])]
    if not tech_df.empty:
        tech_count = tech_df.groupby('department_id').size().reset_index(name='Count')
        tech_count['Department'] = tech_count['department_id'].map(dept_names_map)
        fig5 = px.bar(tech_count, x='Department', y='Count', title="Technical Convergence Activities by Department")
        st.plotly_chart(fig5, use_container_width=True)

    # Chart 6: Expected vs Actual Persondays
    if not df.empty:
        pd_comp = df.groupby('district_id').agg(
            Expected=('expected_persondays', 'sum'),
            Actual=('persondays_generated', 'sum')
        ).reset_index()
        pd_comp['District'] = pd_comp['district_id'].map(dist_names_map)
        fig6 = go.Figure(data=[
            go.Bar(name='Expected', x=pd_comp['District'], y=pd_comp['Expected']),
            go.Bar(name='Actual', x=pd_comp['District'], y=pd_comp['Actual'])
        ])
        fig6.update_layout(barmode='group', title="Expected vs Actual Persondays by District")
        st.plotly_chart(fig6, use_container_width=True)

    # Chart 7: Activity Status Pie
    status_count = df['current_status'].value_counts().reset_index()
    status_count.columns = ['Status', 'Count']
    fig7 = px.pie(status_count, values='Count', names='Status', title="Activity Status Distribution")
    st.plotly_chart(fig7, use_container_width=True)

    # Chart 9: Top 10 Performing Departments
    if not df.empty:
        top_dept = df.groupby('department_id')['physical_achievement'].mean().nlargest(10).reset_index()
        top_dept['Department'] = top_dept['department_id'].map(dept_names_map)
        fig9 = px.bar(top_dept, x='Department', y='physical_achievement',
                      title="Top 10 Performing Departments (Avg Physical Ach.)")
        st.plotly_chart(fig9, use_container_width=True)

    # Chart 10: Top 10 Performing Districts
    if 'district_id' in df.columns:
        top_dist = df.groupby('district_id')['physical_achievement'].mean().nlargest(10).reset_index()
        top_dist['District'] = top_dist['district_id'].map(dist_names_map)
        fig10 = px.bar(top_dist, x='District', y='physical_achievement',
                       title="Top 10 Performing Districts (Avg Physical Ach.)")
        st.plotly_chart(fig10, use_container_width=True)

    # ---------- PERFORMANCE SCORE ----------
    st.subheader("Overall Performance Score")
    weights = {"physical": 0.3, "financial": 0.3, "personday": 0.2, "timeliness": 0.2}
    try:
        settings = supabase.table("system_settings").select("*").execute().data
        if settings:
            ws = next((s['value'] for s in settings if s['key'] == 'performance_weights'), None)
            if ws:
                weights = ws
    except:
        pass

    df['score_physical'] = df['physical_achievement'] * weights['physical']
    df['score_financial'] = (df['financial_achievement'] / (df['total_converged_fund'] + 0.001)) * 100 * weights['financial']
    df['score_personday'] = (df['persondays_generated'] / (df['expected_persondays'] + 0.001)).clip(0, 1) * 100 * weights['personday']
    df['delay_days'] = df.get('delay_days', 0)
    df['score_timeliness'] = ((1 - (df['delay_days'] / (df['duration_days'] + 1)).clip(0,1)) * 100) * weights['timeliness']
    df['overall_score'] = df[['score_physical','score_financial','score_personday','score_timeliness']].sum(axis=1)

    avg_score = df['overall_score'].mean()
    st.metric("Average Performance Score", f"{avg_score:.1f} / 100")

    def score_label(x):
        if x >= 75: return "Excellent"
        elif x >= 50: return "Good"
        elif x >= 25: return "Needs Attention"
        else: return "Critical"
    df['Performance'] = df['overall_score'].apply(score_label)
    perf_counts = df['Performance'].value_counts().reset_index()
    perf_counts.columns = ['Category', 'Count']
    fig_perf = px.pie(perf_counts, values='Count', names='Category', title="Performance Categories")
    st.plotly_chart(fig_perf, use_container_width=True)

    # ---------- MEETING ACTION POINTS ----------
    if role in ['superadmin', 'district']:
        st.subheader("Convergence Meeting Action Points")
        ap_data = supabase.table("meeting_action_points").select("status").execute().data
        if ap_data:
            ap_df = pd.DataFrame(ap_data)
            ap_summary = ap_df['status'].value_counts().reset_index()
            ap_summary.columns = ['Status', 'Count']
            fig_ap = px.bar(ap_summary, x='Status', y='Count', title="Action Point Status Summary")
            st.plotly_chart(fig_ap, use_container_width=True)
        else:
            st.info("No action points recorded.")

    # ---------- DELAYED ACTIVITIES ----------
    st.subheader("Delayed Activities")
    delayed = df[df['delay_days'] > 0] if 'delay_days' in df.columns else pd.DataFrame()
    if not delayed.empty:
        st.dataframe(delayed[['id', 'activity_description', 'district_id', 'department_id', 'current_status', 'delay_days']].head(10),
                     use_container_width=True)
    else:
        st.success("No delayed activities in current view.")

    # ---------- EXCEL EXPORT ----------
    st.divider()
    st.subheader("Export Data")
    from utils.excel import dataframe_to_excel
    excel_data = dataframe_to_excel(df, "dashboard_data")
    st.download_button(label="Download Filtered Data (Excel)", data=excel_data, file_name="dashboard_export.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
