import streamlit as st
import pandas as pd
import plotly.express as px
from auth.auth import require_role, get_current_user
from utils.db import get_supabase
from utils.theme import load_theme, apply_global_theme

def init_ui_state():
    """Initializes a persistent dictionary for theme state."""
    if 'theme_state' not in st.session_state:
        active_theme = load_theme()
        
        # Load DB tokens into a separate dictionary so they survive widget unmounts
        st.session_state.theme_state = {
            'primary_color': active_theme.get('primary_color', '#1F77B4'),
            'bg_color': active_theme.get('bg_color', '#F8F9FA'),
            'app_name': active_theme.get('app_name', 'VB-G RAM G Convergence'),
            'font_family': active_theme.get('font_family', 'sans serif'),
            'card_shadow': active_theme.get('card_shadow', True),
            'border_radius': active_theme.get('border_radius', 12)
        }

def save_to_database():
    """Upserts the current theme_state to the ui_settings database table."""
    supabase = get_supabase()
    user = get_current_user()
    
    state = st.session_state.theme_state
    
    payload = {
        "profile_name": "Custom Live Theme",
        "primary_color": state['primary_color'],
        "bg_color": state['bg_color'],
        "app_name": state['app_name'],
        "font_family": state['font_family'],
        "card_shadow": state['card_shadow'],
        "border_radius": state['border_radius'],
        "is_active": True,
        "updated_by": user["id"]
    }
    
    try:
        supabase.table("ui_settings").update({"is_active": False}).neq("id", "0").execute()
        supabase.table("ui_settings").upsert({"id": 1, **payload}).execute()
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
        state = st.session_state.theme_state
        
        # Notice we assign the widget's return value directly to our persistent state
        if design_category == "Theme & Colors":
            state['primary_color'] = st.color_picker("Primary Color", value=state['primary_color'])
            state['bg_color'] = st.color_picker("Background Color", value=state['bg_color'])
            state['card_shadow'] = st.checkbox("Enable Card Shadows", value=state['card_shadow'])
            state['border_radius'] = st.slider("Border Radius (px)", min_value=0, max_value=24, step=2, value=state['border_radius'])
            
        elif design_category == "Header Details":
            state['app_name'] = st.text_input("Application Name", value=state['app_name'])
            
        elif design_category == "Typography":
            font_opts = ["sans serif", "serif", "monospace", "Arial", "Inter"]
            # Find current index to set as default
            current_idx = font_opts.index(state['font_family']) if state['font_family'] in font_opts else 0
            state['font_family'] = st.selectbox("Main Font Family", font_opts, index=current_idx)

    # ================= 3. LIVE PREVIEW =================
    with col_preview:
        st.subheader("👁️ Live Preview")
        
        # Read strictly from the persistent dictionary, never from widget keys
        state = st.session_state.theme_state
        shadow_css = "box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" if state['card_shadow'] else "border: 1px solid #ddd;"
        primary = state['primary_color']
        bg = state['bg_color']
        radius = state['border_radius']
        font = state['font_family']
        app_name = state['app_name']
        
        preview_html = f"""
        <div style="background-color: {bg}; padding: 20px; border-radius: 8px; border: 2px dashed #ccc; font-family: {font};">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid {primary}; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="color: {primary}; margin: 0;">{app_name}</h2>
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
            del st.session_state['theme_state']
            st.rerun()
            
    with action_col3:
        if st.button("🚀 Publish to Live", type="primary", use_container_width=True):
            success = save_to_database()
            if success:
                st.success("✅ Changes successfully published! All application pages now use this design.")
                st.balloons()
