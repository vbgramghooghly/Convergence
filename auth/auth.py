import streamlit as st
from supabase import create_client
import bcrypt
import pandas as pd
from config.settings import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_password():
    """Return True if user is authenticated."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.role = None
        st.session_state.district_id = None
        st.session_state.block_id = None
        st.session_state.department_id = None

    if not st.session_state.authenticated:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in"):
                try:
                    # Use Supabase Auth
                    auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if auth_response.user:
                        # Get user details from our users table
                        user_data = supabase.table("users").select("*").eq("id", auth_response.user.id).single().execute()
                        if user_data.data and user_data.data["active"]:
                            st.session_state.authenticated = True
                            st.session_state.user = user_data.data
                            st.session_state.role = user_data.data["role"]
                            st.session_state.district_id = user_data.data.get("district_id")
                            st.session_state.block_id = user_data.data.get("block_id")
                            st.session_state.department_id = user_data.data.get("department_id")
                            st.rerun()
                        else:
                            st.error("User not active or not found.")
                    else:
                        st.error("Invalid credentials")
                except Exception as e:
                    st.error(f"Login failed: {e}")
        return False
    return True

def logout():
    st.session_state.authenticated = False
    supabase.auth.sign_out()
    st.rerun()

def require_role(*allowed_roles):
    """Decorator to protect pages."""
    if not st.session_state.authenticated:
        st.error("Please log in")
        st.stop()
    if st.session_state.role not in allowed_roles:
        st.error("You do not have permission to access this page.")
        st.stop()

# Cache user info for fast access
def get_current_user():
    return st.session_state.user
