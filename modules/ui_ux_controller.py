import streamlit as st
import pandas as pd
import plotly.express as px
from auth.auth import require_role, get_current_user
from utils.db import get_supabase
from utils.theme import load_theme, apply_global_theme

def init_ui_state():
    """Initializes session state from the database active theme."""
    if 'ui_initialized' not in st.session_state:
        active_theme = load_theme()
        
        # Load DB tokens into session state for the live editor
        st.session_state.ui_primary_color = active_theme.get('primary_color', '#1F77B4')
        st.session_state.ui_bg_color = active_theme.get('bg_color', '#F8F9FA')
        st.session_state.ui_app_name = active_theme.get('app_name', 'VB-G RAM G Convergence')
        st.session_state.ui_font = active_theme.get('font_family', 'sans serif')
        st.session_state.ui_card_shadow = active_theme.get('card_shadow', True)
        st.session_state.ui_border_radius = active_theme.get('border_radius', 12)
        
        st.session_state.ui_initialized = True

def save_to_database():
    """Upserts the current session state to the ui_settings database table."""
    supabase = get_supabase()
    user = get_current_user()
    
    payload = {
        "profile_name": "Custom Live Theme",
        "primary_color": st.session_state.ui_primary_color,
        "bg_color": st.session_state.ui_bg_color,
        "app_name": st.session_state.ui_app_name,
        "font_family": st.session_state.ui_font,
        "card_shadow": st.session_state.ui_card_shadow,
        "border_radius": st.session_state.ui_border_radius,
        "is_active": True, # Make this the active theme
        "updated_by": user["id"]
    }
    
    try:
        # Deactivate all other themes first (if supporting multiple profiles)
        supabase.table("ui_settings").update({"is_active": False}).neq("id", "0").execute()
        
        # Upsert the new live configuration
        # Assuming you have an ID '1' for the main global theme, or you insert a new active record
        result = supabase.table("ui_settings").upsert({"id": 1, **payload}).execute()
        return True
    except Exception as e:
        st.error(f"Failed to save to database: {e}")
        return False

def show():
    require_role('superadmin')
    init_ui_state()
    
    st.markdown("<h1 style='color: #2C3E50;'>🎨 System UI/UX Controller</h1>", unsafe_allow_html=True)
    st.markdown("Easily customize the application's appearance. **Changes preview instantly in the center. Click 'Publish to Live' to apply globally.**")
    st.markdown("---")

    col_design, col_preview, col_prop = st.columns([2, 5, 2.5])

    # ================= 1. DESIGN SELECTOR =================
    with col_design:
        st.subheader("🛠️ Design")
        design_category = st.radio(
            "Select Component",
            ["Theme & Colors", "Header Details", "Typography"],
            label_visibility="collapsed"
        )
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.info("💡 **Tip:** Adjust settings on the right to see them in the center preview.")

    # ================= 2. PROPERTIES PANEL =================
    with col_prop:
        st.subheader("⚙️ Properties")
        if design_category == "Theme & Colors":
            st.color_picker("Primary Color", key="ui_primary_color")
            st.color_picker("Background Color", key="ui_bg_color")
            st.checkbox("Enable Card Shadows", key="ui_card_shadow")
            st.slider("Border Radius (px)", min_value=0, max_value=24, step=2, key="ui_border_radius")
            
        elif design_category == "Header Details":
            st.text_input("Application Name", key="ui_app_name")
            
        elif design_category == "Typography":
            st.selectbox("Main Font Family", ["sans serif", "serif", "monospace", "Arial", "Inter"], key="ui_font")

    # ================= 3. LIVE PREVIEW =================
    with col_preview:
        st.subheader("👁️ Live Preview")
        
        shadow_css = "box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" if st.session_state.ui_card_shadow else "border: 1px solid #ddd;"
        primary = st.session_state.ui_primary_color
        bg = st.session_state.ui_bg_color
        radius = st.session_state.ui_border_radius
        font = st.session_state.ui_font
        
        preview_html = f"""
        <div style="background-color: {bg}; padding: 20px; border-radius: 8px; border: 2px dashed #ccc; font-family: {font};">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid {primary}; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="color: {primary}; margin: 0;">{st.session_state.ui_app_name}</h2>
                <div style="color: #666;">🔔 👤 Admin</div>
            </div>
            <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                <div style="flex: 1; background: white; padding: 15px; border-radius: {radius}px; {shadow_css} border-left: 5px solid {primary};">
                    <div style="font-size: 12px; color: #666;">Total Activities</div>
                    <div style="font-size: 24px; font-weight: bold; color: #333;">142</div>
                </div>
                <div style="flex: 1; background: white; padding: 15px; border-radius: {radius}px; {shadow_css} border-left: 5px solid {primary};">
                    <div style="font-size: 12px; color: #666;">Funds Converged</div>
                    <div style="font-size: 24px; font-weight: bold; color: #333;">₹ 25.5 L</div>
                </div>
                <div style="flex: 1; background: white; padding: 15px; border-radius: {radius}px; {shadow_css} border-left: 5px solid {primary};">
                    <div style="font-size: 12px; color: #666;">Completion</div>
                    <div style="font-size: 24px; font-weight: bold; color: #333;">84%</div>
                </div>
            </div>
            <button style="background-color: {primary}; color: white; border: none; padding: 10px 20px; border-radius: {radius}px; cursor: pointer; width: 100%;">
                Save Convergence Activity (Primary Button Preview)
            </button>
        </div>
        """
        st.markdown(preview_html, unsafe_allow_html=True)
        
        if design_category in ["Theme & Colors"]:
            st.markdown("<br>", unsafe_allow_html=True)
            mock_data = pd.DataFrame({'Department': ['Edu', 'Health', 'Agri'], 'Value': [45, 30, 25]})
            fig = px.bar(mock_data, x='Department', y='Value', title="Chart Color Preview")
            fig.update_traces(marker_color=primary)
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # ================= 4. ACTION BAR =================
    st.markdown("---")
    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    
    with action_col1:
        if st.button("🔄 Reset to Default", use_container_width=True):
            del st.session_state['ui_initialized']
            st.rerun()
            
    with action_col3:
        if st.button("🚀 Publish to Live", type="primary", use_container_width=True):
            success = save_to_database()
            if success:
                st.success("✅ Changes successfully published! All application pages now use this design.")
                st.balloons()
