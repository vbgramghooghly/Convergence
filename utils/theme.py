import streamlit as st
from utils.db import get_supabase

def load_theme():
    """Fetches the active UI configuration from the database."""
    try:
        supabase = get_supabase()
        response = supabase.table("ui_settings").select("*").eq("is_active", True).limit(1).execute()
        if response.data:
            return response.data[0]
    except Exception:
        pass
    
    # DEFAULT MODERN TOKENS
    return {
        "primary_color": "#0F4C81",
        "bg_color": "#F4F6F9",
        "app_name": "VB-G RAM G Portal",
        "font_family": "'Inter', sans-serif",
        "border_radius": 6,
        "base_font_size": 14,
        "tab_size": "Medium"
    }

def apply_global_theme(theme=None):
    """Generates and injects global CSS based on the theme tokens."""
    if not theme:
        theme = load_theme()

    primary = theme.get("primary_color", "#0F4C81")
    bg = theme.get("bg_color", "#F4F6F9")
    radius = theme.get("border_radius", 6)
    font = theme.get("font_family", "sans-serif")
    font_size = theme.get("base_font_size", 14)
    tab_size = theme.get("tab_size", "Medium")
    
    # Calculate Tab Sizing
    if tab_size == "Small":
        tab_pad, tab_font = "8px 16px", f"{font_size - 2}px"
    elif tab_size == "Large":
        tab_pad, tab_font = "16px 32px", f"{font_size + 2}px"
    else: # Medium
        tab_pad, tab_font = "12px 24px", f"{font_size}px"

    custom_css = f"""
    <style>
        /* 1. GLOBAL BACKGROUND, WIDTH & BASE FONT */
        .stApp {{
            background-color: {bg};
            font-family: {font} !important;
        }}
        
        /* Set base font size for all standard elements */
        html, body, p, div, span, label, input, button, select, textarea, [class*="st-"] {{
            font-size: {font_size}px !important;
        }}
        
        /* FORCE FULL SCREEN WIDE MODE */
        .block-container {{
            max-width: 98% !important;
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }}
        
        /* Headers scale based on base font size */
        h1 {{ font-size: {font_size * 2.2}px !important; color: {primary} !important; font-weight: 700 !important; }}
        h2 {{ font-size: {font_size * 1.8}px !important; color: {primary} !important; font-weight: 600 !important; }}
        h3 {{ font-size: {font_size * 1.5}px !important; color: {primary} !important; font-weight: 600 !important; }}
        
        /* 2. BUTTONS */
        .stButton > button[kind="primary"] {{
            background-color: {primary} !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: {radius}px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
            transition: opacity 0.2s;
        }}
        .stButton > button[kind="primary"]:hover {{
            opacity: 0.9 !important;
        }}

        /* 3. INPUTS */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {{
            border: 1px solid #D1D5DB !important;
            border-radius: {radius}px !important;
        }}
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within {{
            border-color: {primary} !important;
            box-shadow: 0 0 0 1px {primary} !important;
        }}

        /* 4. DYNAMIC TAB SIZING */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
            border-bottom: 2px solid #E5E7EB;
        }}
        .stTabs [data-baseweb="tab"] {{
            padding: {tab_pad} !important;
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
            border-bottom: 3px solid {primary} !important;
            color: {primary} !important;
            font-weight: 600 !important;
            background-color: transparent !important;
        }}
        .stTabs [data-baseweb="tab-list"] button p {{
            font-size: {tab_font} !important;
        }}

        /* 5. CONTAINERS / CARDS */
        [data-testid="stExpander"], [data-testid="stDataFrameContainer"], [data-testid="metric-container"] {{
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB !important;
            border-radius: {radius}px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        
        [data-testid="metric-container"] {{
            border-top: 4px solid {primary} !important; 
        }}

        /* HIDE DEFAULT STREAMLIT ARTIFACTS GLOBALLY */
        footer {{ visibility: hidden !important; }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
    return theme
