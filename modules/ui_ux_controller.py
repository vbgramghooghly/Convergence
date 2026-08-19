import streamlit as st
import pandas as pd
from auth.auth import require_role, get_current_user
from utils.db import get_supabase
from utils.theme import load_theme, save_theme, get_css, DEFAULT_THEME, PRESETS

def init_ui_state():
    """Load theme into session state for live editing."""
    if 'theme_state' not in st.session_state:
        active = load_theme()
        st.session_state.theme_state = active.copy()
    # Ensure all keys exist
    for key, val in DEFAULT_THEME.items():
        if key not in st.session_state.theme_state:
            st.session_state.theme_state[key] = val

def apply_preset(preset):
    """Apply a preset theme."""
    if preset in PRESETS:
        for key, val in PRESETS[preset].items():
            st.session_state.theme_state[key] = val
    else:
        # Reset to default
        for key, val in DEFAULT_THEME.items():
            st.session_state.theme_state[key] = val

def show():
    require_role('superadmin')
    init_ui_state()
    state = st.session_state.theme_state

    st.markdown("<h1 style='margin-bottom: 0px;'>🎨 Portal Design Studio</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #6B7280; font-size: 16px;'>Configure the global aesthetics of the application. Changes preview instantly.</p>", unsafe_allow_html=True)
    st.markdown("---")

    col_controls, col_preview = st.columns([1, 2.5], gap="large")

    with col_controls:
        # Save & Reset
        c1, c2 = st.columns(2)
        if c1.button("🚀 Save Theme", type="primary", use_container_width=True):
            if save_theme(state):
                st.success("✅ Theme saved successfully!")
                st.balloons()
        if c2.button("↺ Reset to Default", use_container_width=True):
            apply_preset("reset")
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # 1. Quick Presets (including orange)
        with st.expander("🎨 1. Quick Presets", expanded=True):
            preset_cols = st.columns(3)
            presets = list(PRESETS.keys())
            for i, p in enumerate(presets):
                if preset_cols[i % 3].button(p, use_container_width=True):
                    apply_preset(p)
                    st.rerun()

        # 2. Custom Colors
        with st.expander("🖌️ 2. Custom Colors", expanded=False):
            state['primary_color'] = st.color_picker("Primary Color (e.g. Orange)", value=state['primary_color'])
            state['bg_color'] = st.color_picker("Background Color", value=state['bg_color'])
            state['card_color'] = st.color_picker("Card Background", value=state['card_color'])
            state['text_color'] = st.color_picker("Text Color", value=state['text_color'])
            state['border_color'] = st.color_picker("Border Color", value=state['border_color'])

        # 3. Layout & Density
        with st.expander("📏 3. Layout & Spacing", expanded=False):
            state['content_width'] = st.slider("Content Width (%)", min_value=50, max_value=100, value=state['content_width'], step=5)
            state['border_radius'] = st.slider("Border Radius (px)", min_value=0, max_value=24, step=2, value=state['border_radius'])
            state['shadow_intensity'] = st.select_slider("Shadow Intensity", options=[0,1,2,3], value=state['shadow_intensity'])
            state['layout_density'] = st.select_slider("Layout Density", options=["compact", "comfortable", "spacious"], value=state['layout_density'])
            state['component_spacing'] = st.slider("Component Spacing", min_value=0.5, max_value=2.0, value=state['component_spacing'], step=0.1)

        # 4. Typography
        with st.expander("🔤 4. Typography", expanded=False):
            font_opts = ["'Inter', system-ui, sans-serif", "'Segoe UI', sans-serif", "Arial, sans-serif", "Georgia, serif", "monospace"]
            cur_font = state['font_family'] if state['font_family'] in font_opts else font_opts[0]
            state['font_family'] = st.selectbox("Font Family", font_opts, index=font_opts.index(cur_font))
            state['base_font_size'] = st.slider("Base Font Size (px)", min_value=12, max_value=20, value=state['base_font_size'], step=1)

        # 5. Dark Mode
        with st.expander("🌓 5. Dark / Light Mode", expanded=False):
            dark = state.get('dark_mode', False)
            state['dark_mode'] = st.toggle("Enable Dark Mode", value=dark)

    # ------------------------------------------------------------
    # LIVE PREVIEW (updated with orange-friendly design)
    # ------------------------------------------------------------
    with col_preview:
        st.subheader("👁️ Live Portal Preview")
        # Generate preview using current theme
        primary = state['primary_color']
        bg = state['bg_color']
        card = state['card_color']
        text = state['text_color']
        border = state['border_color']
        radius = state['border_radius']
        font = state['font_family']
        base_font = state['base_font_size']
        width = state['content_width']
        shadow = state['shadow_intensity']
        dark = state.get('dark_mode', False)

        # Build a realistic portal preview
        preview_html = f"""
        <div style="background: {bg}; padding: 20px; border: 1px solid {border}; border-radius: {radius}px; font-family: {font}; color: {text};">
            <!-- Simulated Header -->
            <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 15px; border-bottom: 1px solid {border}; margin-bottom: 20px;">
                <div>
                    <span style="font-size: {base_font*1.8}px; font-weight: 800; color: {primary};">🏛️ VB-G RAM G</span>
                    <span style="font-size: {base_font*0.7}px; color: #64748B; display: block; text-transform: uppercase; letter-spacing: 0.5px;">Convergence Portal</span>
                </div>
                <div style="display: flex; gap: 12px;">
                    <span style="background: {primary}; color: white; padding: 6px 16px; border-radius: 20px; font-size: {base_font}px; font-weight: 600;">Home</span>
                    <span style="background: transparent; color: {text}; padding: 6px 16px; border-radius: 20px; font-size: {base_font}px;">Progress</span>
                    <span style="background: transparent; color: {text}; padding: 6px 16px; border-radius: 20px; font-size: {base_font}px;">Meetings</span>
                </div>
            </div>
            <!-- KPI Cards -->
            <div style="display: flex; gap: 20px; margin-bottom: 25px; flex-wrap: wrap;">
                <div style="flex:1; min-width:120px; background:{card}; padding: 16px; border-radius: {radius}px; border:1px solid {border}; border-top: 4px solid {primary}; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="font-size:{base_font-2}px; color:#6B7280;">Total Targets</div>
                    <div style="font-size:{base_font*1.8}px; font-weight:bold; color:{text};">128</div>
                </div>
                <div style="flex:1; min-width:120px; background:{card}; padding: 16px; border-radius: {radius}px; border:1px solid {border}; border-top: 4px solid {primary};">
                    <div style="font-size:{base_font-2}px; color:#6B7280;">Entries Captured</div>
                    <div style="font-size:{base_font*1.8}px; font-weight:bold; color:{text};">96</div>
                </div>
                <div style="flex:1; min-width:120px; background:{card}; padding: 16px; border-radius: {radius}px; border:1px solid {border}; border-top: 4px solid {primary};">
                    <div style="font-size:{base_font-2}px; color:#6B7280;">Compliance</div>
                    <div style="font-size:{base_font*1.8}px; font-weight:bold; color:#10B981;">75%</div>
                </div>
            </div>
            <!-- Sample Table -->
            <div style="background:{card}; border-radius: {radius}px; border:1px solid {border}; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <table style="width:100%; border-collapse: collapse; font-size:{base_font}px;">
                    <thead style="background:{border}; color:{text};">
                        <tr><th style="padding:10px; text-align:left;">Block</th><th style="padding:10px; text-align:left;">Target</th><th style="padding:10px; text-align:left;">Status</th></tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom:1px solid {border};"><td style="padding:10px;">Chinsurah Mogra</td><td style="padding:10px;">28</td><td style="padding:10px;"><span style="background:#10B981; color:white; padding:2px 12px; border-radius:20px; font-size:{base_font-2}px;">Matched</span></td></tr>
                        <tr style="border-bottom:1px solid {border};"><td style="padding:10px;">Polba Dadpur</td><td style="padding:10px;">14</td><td style="padding:10px;"><span style="background:#F59E0B; color:white; padding:2px 12px; border-radius:20px; font-size:{base_font-2}px;">Needs Update</span></td></tr>
                        <tr><td style="padding:10px;">Singur</td><td style="padding:10px;">22</td><td style="padding:10px;"><span style="background:#EF4444; color:white; padding:2px 12px; border-radius:20px; font-size:{base_font-2}px;">Mismatch</span></td></tr>
                    </tbody>
                </table>
            </div>
            <!-- Sample Button -->
            <div style="margin-top: 20px;">
                <button style="background:{primary}; color:white; border:none; padding:10px 24px; border-radius:{radius}px; font-weight:600; font-size:{base_font}px; cursor:default;">Save Targets</button>
                <button style="background:transparent; color:{text}; border:1px solid {border}; padding:10px 24px; border-radius:{radius}px; font-weight:600; font-size:{base_font}px; margin-left:12px; cursor:default;">Cancel</button>
            </div>
        </div>
        """
        st.markdown(preview_html, unsafe_allow_html=True)

        # Show current CSS for debugging (optional)
        with st.expander("🧪 Generated CSS (preview)"):
            st.code(get_css(state), language="css")
