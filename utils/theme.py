import streamlit as st
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
    payload = {
        "profile_name": "Active Custom Theme",
        **theme_dict,
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
# BACKWARD-COMPATIBLE WRAPPER – ensures existing imports still work
# ============================================================
def apply_global_theme(theme=None):
    """
    Legacy function to apply the theme globally.
    This is kept for backward compatibility with older modules.
    """
    if theme is None:
        theme = load_theme()
    st.markdown(f"<style>{get_css(theme)}</style>", unsafe_allow_html=True)
    return theme
