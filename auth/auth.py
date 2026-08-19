import uuid
import streamlit as st
from utils.db import get_supabase

# ---------- CAPTCHA ----------
def get_captcha():
    """Return a (question, answer) tuple. Stored in session to avoid regeneration on reruns."""
    if "captcha" not in st.session_state:
        import random
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        op = random.choice(['+', '-', '*'])
        if op == '+':
            answer = a + b
            question = f"{a} + {b}"
        elif op == '-':
            a, b = max(a, b), min(a, b)
            answer = a - b
            question = f"{a} - {b}"
        else:
            answer = a * b
            question = f"{a} × {b}"
        st.session_state.captcha = {"question": question, "answer": answer}
    return st.session_state.captcha["question"], st.session_state.captcha["answer"]

def clear_captcha():
    if "captcha" in st.session_state:
        del st.session_state.captcha

# ---------- SESSION VALIDATOR ----------
def check_active_session():
    """
    Validates that the current browser still holds the valid session.
    Run this at the top of every page.
    """
    if not st.session_state.get('authenticated'):
        return False
        
    user_id = st.session_state.get('user', {}).get('id')
    local_token = st.session_state.get('session_token')
    
    if not user_id or not local_token:
        logout("Session details missing. Please log in again.")
        return False
        
    try:
        supabase = get_supabase()
        db_response = supabase.table("users").select("current_session_token").eq("id", user_id).execute()
        
        if db_response.data:
            active_db_token = db_response.data[0].get('current_session_token')
            
            # If the DB token doesn't match the local browser token, log them out
            if local_token != active_db_token:
                logout("Your session expired because your account was logged into from another device or browser.")
                return False
                
        return True
    except Exception:
        return False

# ---------- AUTHENTICATION ----------
def check_password():
    """Returns True if the user is authenticated, otherwise renders a login page with CAPTCHA."""
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.authenticated:
        return True

    # ---------- STYLING FOR THE LANDING / LOGIN PAGE ----------
    st.markdown("""
        <style>
            [data-testid="collapsedControl"], [data-testid="stSidebar"], section[data-testid="stSidebar"] { display: none !important; width: 0px !important;}
            header[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; height: 0px !important; }
            
            .stApp { background: linear-gradient(135deg, #F0F4F8 0%, #D9E2EC 100%); }
            .block-container { padding-top: 3rem !important; }
            
            [data-testid="stForm"] {
                background: #FFFFFF; padding: 35px; border-radius: 12px;
                box-shadow: 0 10px 25px rgba(31, 119, 180, 0.15);
                border: 1px solid #E2E8F0; border-top: 5px solid #0F4C81;
            }
            .portal-title { font-size: 2.2rem; font-weight: 800; color: #0F4C81; margin-bottom: 0px; }
            .portal-subtitle { font-size: 1.1rem; color: #64748B; margin-bottom: 25px; }
            .feature-item { font-size: 1.05rem; color: #334155; margin-bottom: 12px; font-weight: 500; }
        </style>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1.3, 1], gap="large")

    with col_left:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 class='portal-title'>🏛️ VB-G RAM G Convergence Portal, Hooghly</h1>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🌟 Portal Highlights")
        st.markdown("<div class='feature-item'>📈 <b>Real-Time Execution:</b> Monitor physical & financial achievements.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🏛️ <b>Multi-Tier Governance:</b> District, Block, and Department controls.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🤝 <b>Meeting Resolutions:</b> Automatic action point and ATR syncing.</div>", unsafe_allow_html=True)
        st.markdown("<div class='feature-item'>🔒 <b>Enterprise Security:</b> Complete audit logging and controlled workflows.</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown("<h3 style='margin-bottom: 5px;'>🔐 Secure Login</h3>", unsafe_allow_html=True)
            st.caption("Enter your credentials to access the workspace.")
            
            username = st.text_input("Username / Email")
            password = st.text_input("Password", type="password")

            # ---------- CAPTCHA ----------
            question, correct_answer = get_captcha()
            captcha_input = st.text_input(f"Security Check: What is {question}?", placeholder="Your answer")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("Sign In to Portal", type="primary", use_container_width=True)

            if submit_btn:
                # Validate CAPTCHA
                try:
                    user_answer = int(captcha_input.strip())
                except ValueError:
                    st.error("⚠️ Please enter a numeric answer for the security check.")
                    return False

                if user_answer != correct_answer:
                    st.error("❌ Incorrect security answer. Please try again.")
                    clear_captcha()  
                    st.rerun()
                    return False

                # CAPTCHA passed
                clear_captcha()

                if not username or not password:
                    st.error("⚠️ Credentials required.")
                else:
                    try:
                        supabase = get_supabase()
                        clean_input = username.strip()
                        login_email = clean_input if "@" in clean_input else f"{clean_input}@hooghly.gov.in"
                        
                        auth_response = supabase.auth.sign_in_with_password({"email": login_email, "password": password})
                        user_id = auth_response.user.id
                        users_data = supabase.table("users").select("*").eq("id", user_id).execute().data

                        if not users_data: 
                            st.error("❌ Profile not found.")
                        else:
                            user_profile = users_data[0]
                            if not user_profile.get("active", True):
                                st.error("🚫 Account deactivated.")
                            else:
                                # --- AUTOMATIC SESSION OVERWRITE (Last Login Wins) ---
                                # Automatically override any ghost sessions left from closed browsers
                                new_session_token = str(uuid.uuid4())
                                supabase.table("users").update({
                                    "current_session_token": new_session_token
                                }).eq("id", user_id).execute()

                                st.session_state.authenticated = True
                                st.session_state.user = user_profile
                                st.session_state.session_token = new_session_token
                                st.session_state.current_page = "Home"
                                st.rerun()
                    except Exception:
                        st.error("❌ Incorrect credentials.")

    return False

def get_current_user():
    return st.session_state.get("user", None)

def logout(message=None):
    supabase = get_supabase()
    user_id = st.session_state.get('user', {}).get('id')
    
    # 1. Clear the session token in the database
    if user_id:
        try:
            supabase.table("users").update({"current_session_token": None}).eq("id", user_id).execute()
        except Exception:
            pass

    # 2. Clear local session
    try: 
        supabase.auth.sign_out()
    except Exception: 
        pass 
        
    for key in list(st.session_state.keys()):
        del st.session_state[key]
        
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.current_page = None
    st.session_state.session_token = None
    
    if message:
        st.error(f"⚠️ {message}")
        
    st.rerun()

def require_role(*allowed_roles):
    user = get_current_user()
    if not user or user.get('role') not in allowed_roles:
        st.error("🚫 Access Denied: You lack the permissions to view this module.")
        st.stop()
