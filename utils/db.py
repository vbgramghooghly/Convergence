from supabase import create_client
from config.settings import SUPABASE_URL, SUPABASE_KEY

def get_supabase():
    # Use Streamlit caching to reuse connection
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return st.session_state.supabase_client

def run_sql(sql: str):
    # Only for service key operations, e.g., seed data
    from supabase import create_client, Client
    service_client = create_client(SUPABASE_URL, SERVICE_KEY)
    return service_client.rpc('exec_sql', {'query': sql}).execute()
