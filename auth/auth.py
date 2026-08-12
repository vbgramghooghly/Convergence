import streamlit as st
from utils.db import get_supabase

def check_password():
    """Returns True if the user is authenticated, otherwise renders a professional split-screen landing/login page."""
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.authenticated:
        return True

    # ---------- STYLING FOR THE LANDING / LOGIN PAGE ----------
    st.markdown("""
        <style>
            header {visibility: hidden;}
            .stApp {
                background: linear-gradient(135deg, #F0F4F8 0%, #D9E2EC 100%);
            }
            [data-testid="stForm"] {
                background: #FFFFFF;
                padding: 35px;
                border-radius: 16px;
                box-shadow: 0 12px 30px -10px rgba(31, 119, 180, 0.25);
                border: 2px solid #1F77B4;
                border-top: 6px solid #1F77B4;
            }
            .portal-title {
                font-size: 2.3rem;
                font-weight: 800;
                color: #1F77B4;
                margin-bottom: 0px;
            }
            .portal-subtitle {
                font-size: 1.1rem;
                color: #4A5568;
                margin-bottom: 25px;
            }
            .feature-item {
                font-size: 1.05rem;
                color: #2D3748;
                margin-bottom: 14px;
                font-weight: 500;
            }
        </style>
    """, unsafe_allow_html=True)

    # ---------- SPLIT-SCREEN LAYOUT ----------
    col_left, col_right = st.columns([1.3, 1], gap="large")

    with col_left:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 class='portal-title'>📊 VB-G RAM G Convergence</h1>", unsafe_allow_html=True)
        st.markdown("<p class='portal-subtitle'>Unified District, Block, and Department Level Convergence Management Portal</p>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🌟 Key Portal Highlights")
        st.markdown("<div class='feature-item'>📈 <b>Real-Time Progress Tracking:</b> Monitor physical & financial achievements instantly.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🏛️ <b>Multi-Tier Governance:</b> Role-based access for Superadmins, Districts, Blocks, and Departments.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>📊 <b>Dynamic Visualizations:</b> Automated analytics, dashboards, and instant Excel/PDF reporting.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🔒 <b>Secure & Transparent:</b> Complete audit logging and streamlined activity registers.</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        st.markdown("### 🔐 Portal Login")
        st.markdown("<p style='color: #718096; font-size: 0.9rem; margin-bottom: 15px;'>Enter your credentials to access your workspace.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username / Email", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("Sign In to Workspace", type="primary", use_container_width=True)

            if submit_btn:
                if not username or not password:
                    st.error("⚠️ Please enter both username and password.")
                else:
                    try:
                        supabase = get_supabase()
                        
                        # 1. Format the input to match the email structure generated in users.py
                        clean_input = username.strip()
                        login_email = clean_input if "@" in clean_input else f"{clean_input}@hooghly.gov.in"
                        
                        # 2. Authenticate securely using Supabase Auth
                        auth_response = supabase.auth.sign_in_with_password({
                            "email": login_email,
                            "password": password
                        })
                        
                        # 3. If successful, fetch the user's role profile from the public.users table
                        user_id = auth_response.user.id
                        profile_response = supabase.table("users").select("*").eq("id", user_id).execute()
                        users_data = profile_response.data

                        if not users_data:
                            st.error("❌ User profile not found in the database.")
                        else:
                            user_profile = users_data[0]
                            if not user_profile.get("active", True):
                                st.error("🚫 This account has been deactivated. Contact Superadmin.")
                            else:
                                st.session_state.authenticated = True
                                st.session_state.user = user_profile
                                st.success("✅ Login successful! Loading workspace...")
                                st.rerun()

                    except Exception as e:
                        # Supabase auth errors (like wrong password) will trigger this block
                        st.error("❌ Incorrect username or password.")

    return False

def get_current_user():
    """Returns the dictionary of the currently logged-in user."""
    return st.session_state.get("user", None)

def logout():
    """Clears authentication session and reloads the landing page."""
    try:
        supabase = get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass # Fail silently if no active backend session
        
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

def require_role(*allowed_roles):
    """Enforces role-based access control across pages."""
    user = get_current_user()
    if not user or user.get('role') not in allowed_roles:
        st.error("🚫 Access Denied: You do not have the required permissions to view this module.")
        st.stop()
