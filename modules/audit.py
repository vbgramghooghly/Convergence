import streamlit as st
import pandas as pd
from utils.db import get_supabase
from auth.auth import require_role
from utils.theme import apply_global_theme

def show():
    # 1. Apply the global theme immediately
    theme = apply_global_theme()
    
    # 2. Render Page Content
    # Use the app_name from the global theme if needed
    st.markdown(f"<h1>{theme.get('app_name')} Dashboard</h1>", unsafe_allow_html=True)
    
def show():
    require_role('superadmin')
    st.title("Audit Log")
    supabase = get_supabase()
    data = supabase.table("audit_logs").select("*").order("timestamp", desc=True).limit(500).execute().data
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    # Export
    if not df.empty:
        from utils.excel import dataframe_to_excel
        excel = dataframe_to_excel(df, "audit_log")
        st.download_button("Download Audit Log", excel, "audit_log.xlsx")
