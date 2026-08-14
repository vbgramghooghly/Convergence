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
    
    # DEFAULT "MODEST OFFICIAL PORTAL" TOKENS
    return {
        "primary_color": "#0F4C81",  # Deep Official Navy Blue
        "bg_color": "#F4F6F9",       # Very light slate gray background
        "app_name": "VB-G RAM G Convergence",
        "font_family": "'Inter', 'Segoe UI', sans-serif",
        "border_radius": 4,          # Boxier, structured look (4px instead of 12px)
        "card_shadow": False         # Flat design is more typical for official portals
    }

def apply_global_theme(theme=None):
    """Generates and injects comprehensive global CSS based on the theme tokens."""
    if not theme:
        theme = load_theme()

    primary = theme.get("primary_color", "#0F4C81")
    bg = theme.get("bg_color", "#F4F6F9")
    radius = theme.get("border_radius", 4)
    font = theme.get("font_family", "sans-serif")
    
    # Official portals usually prefer flat borders over heavy shadows
    shadow = "0 1px 3px rgba(0,0,0,0.1)" if theme.get("card_shadow") else "none"
    border_css = "none" if theme.get("card_shadow") else "1px solid #D1D5DB"
    input_bg = "#FFFFFF"
    text_color = "#1F2937"

    custom_css = f"""
    <style>
        /* 1. GLOBAL BACKGROUND & TYPOGRAPHY */
        .stApp {{
            background-color: {bg};
            font-family: {font} !important;
            color: {text_color};
        }}
        
        /* Typography overriding */
        h1, h2, h3, h4, h5, h6 {{
            color: {primary} !important;
            font-weight: 600 !important;
        }}
        
        /* 2. SIDEBAR STYLING */
        [data-testid="stSidebar"] {{
            background-color: #FFFFFF !important;
            border-right: 2px solid #E5E7EB;
            box-shadow: 2px 0 5px rgba(0,0,0,0.02);
        }}
        /* Sidebar Logo Area separator */
        [data-testid="stSidebarNav"]::before {{
            content: "";
            display: block;
            border-bottom: 2px solid {primary};
            margin: 0 1rem 1rem 1rem;
        }}

        /* 3. BUTTONS (Structured & Official) */
        .stButton > button[kind="primary"] {{
            background-color: {primary} !important;
            color: #FFFFFF !important;
            border: 1px solid {primary} !important;
            border-radius: {radius}px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
            box-shadow: {shadow} !important;
            transition: all 0.2s ease-in-out;
        }}
        .stButton > button[kind="primary"]:hover {{
            background-color: #0B3A63 !important; /* Slightly darker on hover */
        }}
        .stButton > button[kind="secondary"] {{
            background-color: #F9FAFB !important;
            color: #374151 !important;
            border: 1px solid #D1D5DB !important;
            border-radius: {radius}px !important;
            font-weight: 500 !important;
        }}

        /* 4. INPUT FIELDS, SELECT BOXES & TEXT AREAS */
        .stTextInput input, 
        .stTextArea textarea, 
        .stSelectbox div[data-baseweb="select"],
        .stMultiSelect div[data-baseweb="select"] {{
            background-color: {input_bg} !important;
            border: 1px solid #9CA3AF !important;
            border-radius: {radius}px !important;
            color: {text_color} !important;
        }}
        /* Input Focus State */
        .stTextInput input:focus, 
        .stSelectbox div[data-baseweb="select"]:focus-within {{
            border-color: {primary} !important;
            box-shadow: 0 0 0 1px {primary} !important;
        }}

        /* 5. TABS (Clean Underline Style) */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 24px;
            border-bottom: 2px solid #E5E7EB;
        }}
        .stTabs [data-baseweb="tab"] {{
            padding-top: 10px;
            padding-bottom: 10px;
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
            border-bottom: 3px solid {primary} !important;
            color: {primary} !important;
            font-weight: 600 !important;
            background-color: transparent !important;
        }}

        /* 6. EXPANDERS / ACCORDIONS */
        [data-testid="stExpander"] {{
            background-color: #FFFFFF;
            border: {border_css} !important;
            border-radius: {radius}px !important;
            box-shadow: {shadow};
            margin-bottom: 10px;
        }}
        [data-testid="stExpander"] summary {{
            background-color: #F8FAFC;
            font-weight: 600;
            color: {primary};
        }}

        /* 7. DATA TABLES & DATAFRAMES (Container styling) */
        [data-testid="stDataFrameContainer"], [data-testid="stTable"] {{
            background-color: #FFFFFF;
            border: {border_css} !important;
            border-radius: {radius}px !important;
            padding: 5px;
        }}

        /* 8. METRIC CARDS / CONTAINERS */
        [data-testid="metric-container"] {{
            background-color: #FFFFFF;
            padding: 15px 20px;
            border-radius: {radius}px;
            box-shadow: {shadow};
            border: {border_css};
            border-top: 4px solid {primary}; /* Official accent line */
        }}

        /* Hide Streamlit elements */
        .stAppToolbar {{ visibility: hidden !important; }}
        footer {{ visibility: hidden !important; }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
    return theme
