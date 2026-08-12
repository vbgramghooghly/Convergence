# utils/audit.py
from utils.db import get_supabase
from datetime import datetime

def log_action(user, action, table_name, record_id=None, old_vals=None, new_vals=None):
    try:
        supabase = get_supabase()
        entry = {
            "user_id": user['id'],
            "user_role": user['role'],
            "action": action,
            "table_name": table_name,
            "record_id": record_id,
            "old_values": old_vals,
            "new_values": new_vals,
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("audit_logs").insert(entry).execute()
    except Exception as e:
        print(f"Audit log error: {e}")
