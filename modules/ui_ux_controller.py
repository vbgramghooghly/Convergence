import streamlit as st
import pandas as pd
from auth.auth import require_role, get_current_user
from utils.db import get_supabase

# ------------- DEFAULT THEME -------------
DEFAULT_THEME = {
    "primary_color": "#0F4C81",
    "secondary_color": "#1E3A5F",
    "accent_color": "#E11D48",
    "bg_color": "#F4F6F9",
    "card_color": "#FFFFFF",
    "text_color": "#1F2937",
    "border_color": "#E2E8F0",
    "button_color": "#0F4C81",
    "button_hover_color": "#1A3A6A",
    "header_color": "#0F4C81",
    "sidebar_color": "#F8FAFC",
    "active_nav_color": "#0F4C81",
    "input_color": "#FFFFFF",
    "table_header_color": "#F1F5F9",
    "success_color": "#10B981",
    "warning_color": "#F59E0B",
    "error_color": "#EF4444",
    "font_family": "'Inter', system-ui, -apple-system, sans-serif",
    "base_font_size": 14,
    "border_radius": 6,
    "shadow_intensity": 1,
    "component_spacing": 1,
    "layout_density": "comfortable",
    "corner_radius": "soft",
    "shadow": "subtle",
    "nav_style": "standard",
    "card_style": "elevated",
    "dark_mode": False,
    "content_width": 75
}

# ---------- PRESET THEMES (including Orange variants) ----------
PRESETS = {
    "Government Navy": {"primary_color": "#0F4C81", "bg_color": "#F4F6F9", "border_radius": 6, "font_family": "'Inter', sans-serif"},
    "Eco Green": {"primary_color": "#166534", "bg_color": "#F0FDF4", "border_radius": 8, "font_family": "'Segoe UI', sans-serif"},
    "Corporate Slate": {"primary_color": "#334155", "bg_color": "#F8FAFC", "border_radius": 0, "font_family": "Arial, sans-serif"},
    "Modern Purple": {"primary_color": "#6366F1", "bg_color": "#FAFAFA", "border_radius": 12, "font_family": "'Segoe UI', sans-serif"},
    "Ocean Blue": {"primary_color": "#0EA5E9", "bg_color": "#F0F9FF", "border_radius": 10, "font_family": "'Inter', sans-serif"},
    "Emerald": {"primary_color": "#059669", "bg_color": "#ECFDF5", "border_radius": 8, "font_family": "'Inter', sans-serif"},
    "Teal": {"primary_color": "#0D9488", "bg_color": "#F0FDFA", "border_radius": 8, "font_family": "'Inter', sans-serif"},
    "Warm Professional": {"primary_color": "#B45309", "bg_color": "#FFFBEB", "border_radius": 6, "font_family": "'Inter', sans-serif"},
    "Slate": {"primary_color": "#475569", "bg_color": "#F8FAFC", "border_radius": 6, "font_family": "'Inter', sans-serif"},
    "Sunset Orange": {"primary_color": "#EA580C", "bg_color": "#FFF7ED", "border_radius": 8, "font_family": "'Segoe UI', sans-serif"},
    "Burnt Orange": {"primary_color": "#C2410C", "bg_color": "#FFF2EB", "border_radius": 6, "font_family": "'Inter', sans-serif"},
    "Amber": {"primary_color": "#D97706", "bg_color": "#FFFBEB", "border_radius": 8, "font_family": "'Inter', sans-serif"},
}

def load_theme():
    """Load the active theme from the database, or fall back to defaults."""
    try:
        supabase = get_supabase()
        result = supabase.table("ui_settings").select("*").eq("is_active", True).execute()
        if result.data and len(result.data) > 0:
            theme = result.data[0]
            # Merge with defaults so any missing keys fall back
            merged = DEFAULT_THEME.copy()
            for key in DEFAULT_THEME.keys():
                if key in theme:
                    merged[key] = theme[key]
            return merged
    except Exception:
        pass
    return DEFAULT_THEME.copy()

def save_theme(theme_dict):
    """Save the given theme as active in the database."""
    supabase = get_supabase()
    user = st.session_state.get('user', {})
    
    # Safely remove keys that might not exist in the database schema yet to prevent crashes
    safe_payload = theme_dict.copy()
    unsupported_db_keys = ['dark_mode', 'content_width', 'corner_radius', 'shadow', 'nav_style', 'card_style']
    for key in unsupported_db_keys:
        safe_payload.pop(key, None)

    payload = {
        "profile_name": "Active Custom Theme",
        **safe_payload,
        "is_active": True,
        "updated_by": user.get('id')
    }
    
    try:
        # Deactivate all other themes
        supabase.table("ui_settings").update({"is_active": False}).neq("id", "0").execute()
        # Upsert the new active theme
        supabase.table("ui_settings").upsert({"id": 1, **payload}).execute()
        return True
    except Exception as e:
        st.error(f"Failed to save theme: {e}")
        return False

def get_css(theme):
    """Generate the full global CSS based on the theme dictionary."""
    p = theme['primary_color']
    s = theme['secondary_color']
    a = theme['accent_color']
    bg = theme['bg_color']
    card = theme['card_color']
    text = theme['text_color']
    border = theme['border_color']
    btn = theme['button_color']
    btn_hover = theme['button_hover_color']
    header = theme['header_color']
    sidebar = theme['sidebar_color']
    active_nav = theme['active_nav_color']
    input_bg = theme['input_color']
    table_header = theme['table_header_color']
    success = theme['success_color']
    warning = theme['warning_color']
    error = theme['error_color']
    font = theme['font_family']
    base_font = theme['base_font_size']
    radius = theme['border_radius']
    shadow = theme['shadow_intensity']
    spacing = theme['component_spacing']
    dark = theme.get('dark_mode', False)

    # Dark mode overrides
    if dark:
        bg = "#0F172A"
        card = "#1E293B"
        text = "#F1F5F9"
        border = "#334155"
        sidebar = "#1E293B"
        input_bg = "#1E293B"
        table_header = "#334155"

    # Shadow intensity map
    shadow_map = {0: "none", 1: "0 1px 3px rgba(0,0,0,0.06)", 2: "0 4px 6px rgba(0,0,0,0.1)", 3: "0 10px 15px rgba(0,0,0,0.15)"}
    shadow_val = shadow_map.get(shadow, "0 1px 3px rgba(0,0,0,0.06)")

    # Build CSS
    css = f"""
    /* ---------- GLOBAL RESET ---------- */
    body, .stApp, .main {{
        font-family: {font} !important;
        background-color: {bg} !important;
        color: {text} !important;
        font-size: {base_font}px !important;
    }}
    /* ---------- HIDE STREAMLIT DEFAULTS ---------- */
    [data-testid="collapsedControl"], [data-testid="stSidebar"], section[data-testid="stSidebar"] {{
        display: none !important; visibility: hidden !important; width: 0px !important;
    }}
    [data-testid="stToolbar"], header[data-testid="stHeader"] {{
        display: none !important; visibility: hidden !important; height: 0px !important;
    }}
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 98% !important;
        background-color: {bg} !important;
    }}
    /* ---------- CARDS ---------- */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {{
        background: {card} !important;
        border: 1px solid {border} !important;
        border-radius: {radius}px !important;
        box-shadow: {shadow_val} !important;
        padding: 1.25rem !important;
        margin-bottom: 1rem !important;
    }}
    /* ---------- BUTTONS ---------- */
    .stButton button {{
        border-radius: {radius}px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        border: none !important;
        background-color: {btn} !important;
        color: white !important;
    }}
    .stButton button:hover {{
        background-color: {btn_hover} !important;
        transform: translateY(-1px);
        box-shadow: {shadow_val};
    }}
    .stButton button[kind="secondary"] {{
        background-color: transparent !important;
        color: {text} !important;
        border: 1px solid {border} !important;
    }}
    .stButton button[kind="secondary"]:hover {{
        background-color: {table_header} !important;
    }}
    /* ---------- INPUTS ---------- */
    .stTextInput input, .stSelectbox select, .stTextArea textarea {{
        background-color: {input_bg} !important;
        color: {text} !important;
        border: 1px solid {border} !important;
        border-radius: {radius}px !important;
        font-family: {font} !important;
    }}
    /* ---------- TABLES ---------- */
    div[data-testid="stDataFrame"] thead tr th {{
        background-color: {table_header} !important;
        color: {text} !important;
        font-weight: 600 !important;
    }}
    /* ---------- TABS ---------- */
    div[data-testid="stTabs"] button[role="tab"] {{
        color: {text} !important;
        border-bottom: 3px solid transparent !important;
        padding: 8px 12px !important;
        font-weight: 600 !important;
    }}
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
        color: {p} !important;
        border-bottom: 3px solid {p} !important;
    }}
    /* ---------- METRICS ---------- */
    div[data-testid="stMetric"] {{
        background: {card} !important;
        border: 1px solid {border} !important;
        border-radius: {radius}px !important;
        padding: 0.75rem !important;
        box-shadow: {shadow_val};
    }}
    div[data-testid="stMetric"] label {{
        color: {text} !important;
        font-size: {base_font-1}px !important;
    }}
    /* ---------- HEADINGS ---------- */
    h1, h2, h3, h4, h5, h6 {{
        color: {header} !important;
        font-family: {font} !important;
    }}
    /* ---------- STATUS BADGES ---------- */
    .status-badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: {base_font-2}px;
        font-weight: 600;
        background: {table_header};
        color: {text};
    }}
    .status-badge.success {{ background: {success}; color: white; }}
    .status-badge.warning {{ background: {warning}; color: white; }}
    .status-badge.error {{ background: {error}; color: white; }}
    """
    return css

# ============================================================
# BACKWARD-COMPATIBLE WRAPPER
# ============================================================
def apply_global_theme(theme=None):
    if theme is None:
        theme = load_theme()
    st.markdown(f"<style>{get_css(theme)}</style>", unsafe_allow_html=True)
    return theme

# ============================================================
# UI CONTROLLER SHOW FUNCTION
# ============================================================
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

    # ---- No header title ----
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

        # 1. Quick Presets
        with st.expander("🎨 Quick Presets", expanded=True):
            # Arrange presets in 3 columns for compactness
            preset_cols = st.columns(3)
            presets = list(PRESETS.keys())
            for i, p in enumerate(presets):
                if preset_cols[i % 3].button(p, use_container_width=True):
                    apply_preset(p)
                    st.rerun()

        # 2. Custom Colors
        with st.expander("🖌️ Custom Colors", expanded=False):
            state['primary_color'] = st.color_picker("Primary Color", value=state['primary_color'])
            state['bg_color'] = st.color_picker("Background Color", value=state['bg_color'])
            state['card_color'] = st.color_picker("Card Background", value=state['card_color'])
            state['text_color'] = st.color_picker("Text Color", value=state['text_color'])
            state['border_color'] = st.color_picker("Border Color", value=state['border_color'])

        # 3. Layout & Density
        with st.expander("📏 Layout & Spacing", expanded=False):
            state['content_width'] = st.slider("Content Width (%)", min_value=50, max_value=100, value=state['content_width'], step=5)
            state['border_radius'] = st.slider("Border Radius (px)", min_value=0, max_value=24, step=2, value=state['border_radius'])
            state['shadow_intensity'] = st.select_slider("Shadow Intensity", options=[0, 1, 2, 3], value=state['shadow_intensity'])
            state['layout_density'] = st.select_slider("Layout Density", options=["compact", "comfortable", "spacious"], value=state['layout_density'])
            # Fix: ensure float type for component_spacing slider
            if isinstance(state['component_spacing'], int):
                state['component_spacing'] = float(state['component_spacing'])
            state['component_spacing'] = st.slider(
                "Component Spacing",
                min_value=0.5, max_value=2.0, value=state['component_spacing'], step=0.1
            )

        # 4. Typography
        with st.expander("🔤 Typography", expanded=False):
            font_opts = ["'Inter', system-ui, sans-serif", "'Segoe UI', sans-serif", "Arial, sans-serif", "Georgia, serif", "monospace"]
            cur_font = state['font_family'] if state['font_family'] in font_opts else font_opts[0]
            state['font_family'] = st.selectbox("Font Family", font_opts, index=font_opts.index(cur_font))
            state['base_font_size'] = st.slider("Base Font Size (px)", min_value=12, max_value=20, value=state['base_font_size'], step=1)

        # 5. Dark Mode
        with st.expander("🌓 Dark / Light Mode", expanded=False):
            dark = state.get('dark_mode', False)
            state['dark_mode'] = st.toggle("Enable Dark Mode", value=dark)

    # ------------------------------------------------------------
    # LIVE PREVIEW
    # ------------------------------------------------------------
    with col_preview:
        st.subheader("👁️ Live Preview")
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

        # Optionally show generated CSS
        with st.expander("🧪 Generated CSS (debug)"):
            st.code(get_css(state), language="css")
