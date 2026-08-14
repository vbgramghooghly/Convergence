import streamlit as st
import pandas as pd
from auth.auth import require_role, get_current_user
from utils.db import get_supabase
from utils.theme import load_theme

def init_ui_state():
    """Initializes the persistent theme dictionary safely."""
    active = load_theme()
    
    if 'theme_state' not in st.session_state:
        st.session_state.theme_state = {}
        
    defaults = {
        'primary_color': active.get('primary_color', '#0F4C81'),
        'bg_color': active.get('bg_color', '#F4F6F9'),
        'app_name': active.get('app_name', 'VB-G RAM G Convergence'),
        'font_family': active.get('font_family', "'Inter', sans-serif"),
        'border_radius': active.get('border_radius', 6),
        'base_font_size': active.get('base_font_size', 14),
        'content_width': active.get('content_width', 75),
        'tab_size': active.get('tab_size', 'Medium')
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state.theme_state:
            st.session_state.theme_state[key] = default_value

def apply_preset(primary, bg, radius, font):
    """Helper to apply quick color presets."""
    st.session_state.theme_state.update({
        'primary_color': primary, 
        'bg_color': bg, 
        'border_radius': radius, 
        'font_family': font
    })

def save_to_database():
    """Saves the current design to the database."""
    supabase = get_supabase()
    user = get_current_user()
    state = st.session_state.theme_state
    
    payload = {
        "profile_name": "Active Custom Theme",
        "primary_color": state['primary_color'],
        "bg_color": state['bg_color'],
        "app_name": state['app_name'],
        "font_family": state['font_family'],
        "border_radius": state['border_radius'],
        "base_font_size": state['base_font_size'],
        "content_width": state['content_width'],
        "tab_size": state['tab_size'],
        "is_active": True,
        "updated_by": user["id"]
    }
    
    try:
        supabase.table("ui_settings").update({"is_active": False}).neq("id", "0").execute()
        supabase.table("ui_settings").upsert({"id": 1, **payload}).execute()
        return True
    except Exception as e:
        st.error(f"Failed to save to database. Ensure all columns exist! Error: {e}")
        return False

def show():
    require_role('superadmin')
    init_ui_state()
    state = st.session_state.theme_state
    
    st.markdown("""<style>
        .stAppToolbar {visibility: hidden;} 
        .block-container {max-width: 95rem !important;}
    </style>""", unsafe_allow_html=True)
    
    st.markdown("<h1 style='color: #1F2937; margin-bottom: 0px;'>✨ Portal Design Studio</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #6B7280; font-size: 16px;'>Configure the global aesthetics of the application. Changes preview instantly.</p>", unsafe_allow_html=True)
    st.markdown("---")

    col_controls, col_preview = st.columns([1, 2.5], gap="large")

    # ================= 1. CONTROLS (LEFT COLUMN) =================
    with col_controls:
        if st.button("🚀 Publish Design to Live App", type="primary", use_container_width=True):
            if save_to_database():
                st.success("✅ Global Theme Updated Successfully!")
                st.balloons()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.expander("🎨 1. Quick Presets", expanded=True):
            c1, c2 = st.columns(2)
            if c1.button("🏛️ Gov Navy", use_container_width=True): apply_preset('#0F4C81', '#F4F6F9', 4, "'Segoe UI', sans-serif")
            if c2.button("🌲 Eco Green", use_container_width=True): apply_preset('#166534', '#F0FDF4', 8, "'Segoe UI', sans-serif")
            if c1.button("🏢 Corp Slate", use_container_width=True): apply_preset('#334155', '#F8FAFC', 0, "Arial, sans-serif")
            if c2.button("🔮 Modern Purp", use_container_width=True): apply_preset('#6366F1', '#FAFAFA', 12, "'Segoe UI', sans-serif")
            
        with st.expander("🖌️ 2. Custom Colors & Identity"):
            state['app_name'] = st.text_input("Portal Name", value=state['app_name'])
            state['primary_color'] = st.color_picker("Primary Accent Color", value=state['primary_color'])
            state['bg_color'] = st.color_picker("Page Background Color", value=state['bg_color'])

        with st.expander("📏 3. Layout & Sizing"):
            st.caption("Website Width (Rem units)")
            state['content_width'] = st.slider("Container Max Width", min_value=50, max_value=120, value=state['content_width'], step=5)
            
            st.caption("Component Structure")
            state['border_radius'] = st.slider("Corner Roundness (px)", min_value=0, max_value=24, step=2, value=state['border_radius'])
            
            st.caption("Navigation Tabs Sizing")
            tab_opts = ["Small", "Medium", "Large"]
            state['tab_size'] = st.select_slider("Tab Bulkiness", options=tab_opts, value=state['tab_size'])

        with st.expander("🔤 4. Typography"):
            font_opts = ["'Segoe UI', sans-serif", "Arial, sans-serif", "Georgia, serif", "monospace"]
            cur_font = state['font_family'] if state['font_family'] in font_opts else font_opts[0]
            state['font_family'] = st.selectbox("Global Font Family", font_opts, index=font_opts.index(cur_font))
            
            state['base_font_size'] = st.slider("Base Font Size (px)", min_value=12, max_value=20, value=state['base_font_size'], step=1)

    # ================= 2. LIVE PREVIEW (RIGHT COLUMN) =================
    with col_preview:
        st.subheader("👁️ Live Interactive Preview")
        
        primary = state['primary_color']
        bg = state['bg_color']
        radius = state['border_radius']
        font = state['font_family']
        base_font = state['base_font_size']
        width = state['content_width']
        tab_sz = state['tab_size']
        app_name = state['app_name']
        
        tab_p = "8px 16px" if tab_sz == "Small" else "16px 32px" if tab_sz == "Large" else "12px 24px"
        tab_f = f"{base_font - 2}px" if tab_sz == "Small" else f"{base_font + 2}px" if tab_sz == "Large" else f"{base_font}px"
        
        # ZERO INDENTATION HTML STRING (Prevents Markdown Code Block bugs)
        preview_html = f"""
<div style="background: #E5E7EB; padding: 15px; border-radius: 10px 10px 0 0; display: flex; gap: 8px;">
<div style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f56;"></div>
<div style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></div>
<div style="width: 12px; height: 12px; border-radius: 50%; background: #27c93f;"></div>
</div>
<div style="background-color: {bg}; padding: 30px; border: 1px solid #D1D5DB; border-top: none; border-radius: 0 0 10px 10px; font-family: {font}; min-height: 500px; display: flex; flex-direction: column; align-items: center;">
<div style="width: 100%; max-width: {width}%; transition: max-width 0.3s ease;">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid {primary}; padding-bottom: 10px; margin-bottom: 20px;">
<h2 style="color: {primary}; margin: 0; font-size: {base_font * 1.8}px; font-weight: 700;">{app_name}</h2>
<div style="color: #6B7280; font-size: {base_font}px;">👤 User Profile</div>
</div>
<div style="display: flex; gap: 10px; border-bottom: 2px solid #E5E7EB; margin-bottom: 25px;">
<div style="padding: {tab_p}; border-bottom: 3px solid {primary}; color: {primary}; font-weight: 600; font-size: {tab_f}; cursor: pointer;">Dashboard</div>
<div style="padding: {tab_p}; color: #6B7280; font-size: {tab_f}; cursor: pointer;">Reports</div>
<div style="padding: {tab_p}; color: #6B7280; font-size: {tab_f}; cursor: pointer;">Settings</div>
</div>
<div style="display: flex; gap: 20px; margin-bottom: 25px; flex-wrap: wrap;">
<div style="flex: 1; min-width: 150px; background: white; padding: 20px; border-radius: {radius}px; border: 1px solid #E5E7EB; border-top: 4px solid {primary}; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
<div style="font-size: {base_font - 2}px; color: #6B7280; margin-bottom: 5px;">Total Users</div>
<div style="font-size: {base_font * 1.8}px; font-weight: bold; color: #1F2937;">1,284</div>
</div>
<div style="flex: 1; min-width: 150px; background: white; padding: 20px; border-radius: {radius}px; border: 1px solid #E5E7EB; border-top: 4px solid {primary}; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
<div style="font-size: {base_font - 2}px; color: #6B7280; margin-bottom: 5px;">Server Status</div>
<div style="font-size: {base_font * 1.8}px; font-weight: bold; color: #10B981;">Online</div>
</div>
</div>
<div style="background: white; padding: 20px; border-radius: {radius}px; border: 1px solid #E5E7EB; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
<h3 style="color: {primary}; margin-top: 0; font-size: {base_font * 1.3}px;">Quick Action Form</h3>
<label style="font-size: {base_font}px; color: #374151; display: block; margin-bottom: 5px;">Search Query</label>
<input type="text" placeholder="Enter keywords..." disabled style="width: 100%; padding: 10px; border-radius: {radius}px; border: 1px solid #D1D5DB; margin-bottom: 15px; font-size: {base_font}px; font-family: {font}; box-sizing: border-box;">
<button style="background-color: {primary}; color: white; border: none; padding: 10px 20px; border-radius: {radius}px; cursor: pointer; font-size: {base_font}px; font-weight: 500; font-family: {font};">
Submit Query (Primary Button)
</button>
</div>
</div>
</div>
"""
        st.markdown(preview_html, unsafe_allow_html=True)
