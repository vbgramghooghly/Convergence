import streamlit as st
import bcrypt
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
                        # Query users table
                        response = supabase.table("users").select("*").eq("username", username.strip()).execute()
                        users = response.data

                        if not users:
                            st.error(f"❌ User '{username}' not found in database.")
                        else:
                            user = users[0]
                            if not user.get("active", True):
                                st.error("🚫 This account has been deactivated. Contact Superadmin.")
                            else:
                                stored_hash = user.get("password_hash", "")
                                
                                login_success = False
                                # Try bcrypt check
                                try:
                                    if stored_hash and bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                                        login_success = True
                                except Exception:
                                    pass
                                
                                # Fallback: direct string comparison if hash column stores plain text or different format
                                if not login_success and stored_hash == password:
                                    login_success = True

                                if login_success:
                                    st.session_state.authenticated = True
                                    st.session_state.user = user
                                    st.success("✅ Login successful! Loading workspace...")
                                    st.rerun()
                                else:
                                    st.error("❌ Incorrect password.")
                    except Exception as e:
                        st.error(f"Database connection error: {e}")

    return False

def get_current_user():
    """Returns the dictionary of the currently logged-in user."""
    return st.session_state.get("user", None)

def logout():
    """Clears authentication session and reloads the landing page."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

def require_role(*allowed_roles):
    """Enforces role-based access control across pages."""
    user = get_current_user()
    if not user or user.get('role') not in allowed_roles:
        st.error("🚫 Access Denied: You do not have the required permissions to view this module.")
        st.stop()
