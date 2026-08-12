import streamlit as st
import pandas as pd
import plotly.express as px
from auth.auth import require_role, get_current_user

def init_ui_state():
    defaults = {
        'ui_primary_color': '#1F77B4',
        'ui_bg_color': '#F8F9FA',
        'ui_app_name': 'VB-G RAM G Convergence',
        'ui_sidebar_state': 'expanded',
        'ui_font': 'sans serif',
        'ui_card_shadow': True,
        'ui_border_radius': 12
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def show():
    require_role('superadmin')
    init_ui_state()
    
    st.markdown("<h1 style='color: #2C3E50;'>🎨 System UI/UX Controller</h1>", unsafe_allow_html=True)
    st.markdown("Easily customize the application's appearance without technical knowledge. Changes preview instantly.")
    st.markdown("---")

    col_design, col_preview, col_prop = st.columns([2, 5, 2.5])

    with col_design:
        st.subheader("🛠️ Design")
        design_category = st.radio(
            "Select Component",
            ["Theme & Colors", "Header Details", "Sidebar & Layout", "Dashboard Components", "Typography"],
            label_visibility="collapsed"
        )
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.info("💡 **Tip:** Select a component above, adjust its settings on the right, and see it instantly in the center preview.")

    with col_prop:
        st.subheader("⚙️ Properties")
        if design_category == "Theme & Colors":
            st.color_picker("Primary Color", key="ui_primary_color")
            st.color_picker("Background Color", key="ui_bg_color")
            st.checkbox("Enable Card Shadows", key="ui_card_shadow")
            st.slider("Border Radius (px)", min_value=0, max_value=24, step=2, key="ui_border_radius")
        elif design_category == "Header Details":
            st.text_input("Application Name", key="ui_app_name")
            st.file_uploader("Upload App Logo (PNG/JPG)", type=['png', 'jpg'])
            st.checkbox("Show Notification Bell", value=True)
            st.checkbox("Show User Profile", value=True)
        elif design_category == "Sidebar & Layout":
            st.radio("Default Sidebar State", ["expanded", "collapsed"], key="ui_sidebar_state")
            st.radio("Menu Style", ["Solid Background", "Transparent with Borders"])
            st.checkbox("Enable Collapsible Sub-menus", value=True)
        elif design_category == "Dashboard Components":
            st.markdown("**Toggle Widgets:**")
            st.checkbox("Show KPI Metric Cards", value=True)
            st.checkbox("Show Performance Charts", value=True)
            st.checkbox("Show Recent Activities Table", value=True)
        elif design_category == "Typography":
            st.selectbox("Main Font Family", ["sans serif", "serif", "monospace"], key="ui_font")
            st.slider("Base Font Size", min_value=12, max_value=20, value=14)

    with col_preview:
        st.subheader("👁️ Live Preview")
        
        shadow_css = "box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" if st.session_state.ui_card_shadow else "border: 1px solid #ddd;"
        primary_color = st.session_state.ui_primary_color
        bg_color = st.session_state.ui_bg_color
        b_radius = st.session_state.ui_border_radius
        font_family = st.session_state.ui_font
        
        preview_html = f"""
        <div style="background-color: {bg_color}; padding: 20px; border-radius: 8px; border: 2px dashed #ccc; font-family: {font_family};">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid {primary_color}; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="color: {primary_color}; margin: 0;">{st.session_state.ui_app_name}</h2>
                <div style="color: #666;">🔔 👤 Admin</div>
            </div>
            <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                <div style="flex: 1; background: white; padding: 15px; border-radius: {b_radius}px; {shadow_css} border-left: 5px solid {primary_color};">
                    <div style="font-size: 12px; color: #666;">Total Activities</div>
                    <div style="font-size: 24px; font-weight: bold; color: #333;">142</div>
                </div>
                <div style="flex: 1; background: white; padding: 15px; border-radius: {b_radius}px; {shadow_css} border-left: 5px solid {primary_color};">
                    <div style="font-size: 12px; color: #666;">Funds Converged</div>
                    <div style="font-size: 24px; font-weight: bold; color: #333;">₹ 25.5 L</div>
                </div>
                <div style="flex: 1; background: white; padding: 15px; border-radius: {b_radius}px; {shadow_css} border-left: 5px solid {primary_color};">
                    <div style="font-size: 12px; color: #666;">Completion</div>
                    <div style="font-size: 24px; font-weight: bold; color: #333;">84%</div>
                </div>
            </div>
            <button style="background-color: {primary_color}; color: white; border: none; padding: 10px 20px; border-radius: {b_radius}px; cursor: pointer; width: 100%;">
                Save Convergence Activity (Primary Button Preview)
            </button>
        </div>
        """
        st.markdown(preview_html, unsafe_allow_html=True)
        
        if design_category in ["Theme & Colors", "Dashboard Components"]:
            st.markdown("<br>", unsafe_allow_html=True)
            mock_data = pd.DataFrame({'Department': ['Edu', 'Health', 'Agri'], 'Value': [45, 30, 25]})
            fig = px.bar(mock_data, x='Department', y='Value', title="Chart Color Preview")
            fig.update_traces(marker_color=primary_color)
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    st.markdown("---")
    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    
    with action_col1:
        if st.button("💾 Save Draft", use_container_width=True):
            st.info("Draft saved to version history. Not visible to users yet.")
    with action_col2:
        if st.button("🔄 Restore Previous Version", use_container_width=True):
            st.warning("Restored to previous UI version.")
    with action_col3:
        if st.button("🚀 Publish to Live", type="primary", use_container_width=True):
            st.success("Changes successfully published! All users will see the new design upon refresh.")
            st.balloons()
