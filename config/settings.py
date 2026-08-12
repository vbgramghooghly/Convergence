import os
import streamlit as st

# Use Streamlit secrets in production
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]   # anon key for client
SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY", None)  # for admin operations

# Performance thresholds
DEFAULT_GREEN_THRESHOLD = 75
DEFAULT_AMBER_THRESHOLD = 50
