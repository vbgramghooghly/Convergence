import streamlit as st
from utils.db import get_supabase

def load_theme():
    """Fetches the active UI configuration from the database."""
    try:
        supabase = get_supabase()
        # Fetch the active theme profile
        response = supabase.table("ui_settings").select("*").eq("is_active", True).limit(1).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        print(f"Error loading theme: {e}")
        pass
    
    # Fallback Default Theme Tokens if DB fetch fails or is empty
    return {
        "primary_color": "#1F77B4",
        "bg_color": "#F8F9FA",
        "app_name": "VB-G RAM G Convergence",
        "font_family": "sans serif",
        "border_radius": 12,
        "card_shadow": True
    }

def apply_global_theme(theme=None):
    """Generates and injects global CSS based on the theme tokens."""
    if not theme:
        theme = load_theme()

    primary = theme.get("primary_color", "#1F77B4")
    bg = theme.get("bg_color", "#F8F9FA")
    radius = theme.get("border_radius", 12)
    font = theme.get("font_family", "sans serif")
    shadow = "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)" if theme.get("card_shadow", True) else "none"
    border_css = "none" if theme.get("card_shadow", True) else "1px solid #e5e7eb"

    # Injecting CSS to override Streamlit's default components globally
    custom_css = f"""
    <style>
        /* 1. Global Background & Typography */
        .stApp {{
            background-color: {bg};
            font-family: {font}, sans-serif !important;
        }}
        
        /* 2. Global Primary Buttons */
        .stButton > button[kind="primary"] {{
            background-color: {primary} !important;
            border-color: {primary} !important;
            border-radius: {radius}px !important;
            box-shadow: {shadow} !important;
        }}
        
        /* 3. Global Standard Buttons */
        .stButton > button[kind="secondary"] {{
            border-radius: {radius}px !important;
        }}
        
        /* 4. Global Input Fields & Select Boxes */
        .stTextInput > div > div > input, 
        .stSelectbox > div > div > div,
        .stMultiSelect > div > div > div {{
            border-radius: {radius}px !important;
        }}
        
        /* 5. Global Metrics & Cards (Assuming use of containers or columns for cards) */
        [data-testid="metric-container"] {{
            background-color: #ffffff;
            padding: 15px;
            border-radius: {radius}px;
            box-shadow: {shadow};
            border: {border_css};
            border-left: 5px solid {primary};
        }}

        /* 6. Tabs styling */
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
            border-bottom-color: {primary} !important;
            color: {primary} !important;
        }}

        /* 7. Hide Streamlit Toolbar */
        .stAppToolbar {{
            visibility: hidden !important;
        }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
    return theme
