# utils/audit.py
import streamlit as st
from utils.db import get_supabase
from datetime import datetime

def log_action(user_id: str, action: str, details: str = ""):
    """Logs a user action to the database."""
    supabase = get_supabase()
    
    # Example insertion into an 'audit_logs' table
    data = {
        "user_id": user_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    
    # Execute the insert
    supabase.table("audit_logs").insert(data).execute()
