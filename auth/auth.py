import uuid
import requests
import streamlit as st
from utils.db import get_supabase

# ---------- PDF ASSET FETCHER ----------
@st.cache_data(ttl=3600)
def fetch_pdf_bytes():
    """Fetches the PDF as bytes directly from the Supabase public URL for the download button."""
    try:
        url = "https://xosnfimmwrfnwjtosoqr.supabase.co/storage/v1/object/public/Images/CONVERGENCE_FINAL_compressed.pdf"
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
    except Exception:
        return None
    return None

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
    """Returns True if the user is authenticated, otherwise renders a streamlined login interface."""
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.authenticated:
        return True

    # ---------- HIGH-POLISH CSS STYLING ----------
    st.markdown("""
        <style>
            [data-testid="collapsedControl"], [data-testid="stSidebar"], section[data-testid="stSidebar"] { display: none !important; width: 0px !important;}
            header[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; height: 0px !important; }
            
            /* Professional Gradient Background */
            .stApp { 
                background: linear-gradient(135deg, #0F4C81 0%, #1E3A5F 55%, #E2E8F0 100%); 
                background-attachment: fixed;
            }
            .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 95% !important; }
            
            /* Balanced Glass Cards for Graphics */
            .banner-card {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.5);
                border-radius: 12px;
                padding: 12px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
                margin-bottom: 14px;
                text-align: center;
            }
            .banner-card img {
                max-height: 180px !important;
                width: auto !important;
                object-fit: contain;
                margin: 0 auto;
            }
            
            /* Clean Form Container */
            [data-testid="stForm"] {
                background: #FFFFFF !important;
                padding: 35px !important;
                border-radius: 14px !important;
                box-shadow: 0 12px 30px rgba(15, 76, 129, 0.2) !important;
                border: 1px solid #CBD5E1 !important;
                border-top: 6px solid #0F4C81 !important;
            }
            
            .login-header {
                font-size: 1.5rem;
                font-weight: 800;
                color: #0F4C81;
                margin-bottom: 2px;
            }
            .login-subheader {
                font-size: 0.9rem;
                color: #64748B;
                margin-bottom: 20px;
            }
            
            /* Modern Inputs */
            .stTextInput input {
                border-radius: 6px !important;
                border: 1px solid #CBD5E1 !important;
                padding: 8px 12px !important;
            }
            .stTextInput input:focus {
                border-color: #0F4C81 !important;
                box-shadow: 0 0 0 2px rgba(15, 76, 129, 0.15) !important;
            }
            
            /* Button Styling */
            .stButton button[kind="primary"] {
                border-radius: 6px !important;
                font-weight: 700 !important;
                background-color: #0F4C81 !important;
                padding: 8px 16px !important;
            }
            .stButton button[kind="primary"]:hover {
                background-color: #1A3A6A !important;
            }
        </style>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1.3, 1], gap="large")

    # ---------- LEFT COLUMN: RESIZED BANNER IMAGES & PDF ----------
    with col_left:
        st.markdown("<br>", unsafe_allow_html=True)
        
        img1_url = "https://xosnfimmwrfnwjtosoqr.supabase.co/storage/v1/object/public/Images/fa60c42a-2c6c-48be-a571-67aa4c5c7b34.png"
        img2_url = "https://xosnfimmwrfnwjtosoqr.supabase.co/storage/v1/object/public/Images/b18c63f2-d38d-4ca5-8c4e-b8cb2bda3297.png"
        
        try:
            st.markdown(f'<div class="banner-card"><img src="{img1_url}" style="max-width:100%; height:auto;"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="banner-card"><img src="{img2_url}" style="max-width:100%; height:auto;"></div>', unsafe_allow_html=True)
        except Exception:
            st.error("⚠️ Could not load graphics from Supabase.")
            
        st.markdown("<br>", unsafe_allow_html=True)
            
        # PDF Download Button
        pdf_bytes = fetch_pdf_bytes()
        if pdf_bytes:
            st.download_button(
                label="📥 Download VB-G RAM G Guidelines & Framework (PDF)",
                data=pdf_bytes,
                file_name="VB_G_RAM_G_Convergence_Guidelines.pdf",
                mime="application/pdf",
                type="secondary",
                use_container_width=True
            )

    # ---------- RIGHT COLUMN: CLEAN LOGIN FORM ----------
    with col_right:
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown('<p class="login-header">🔐 Portal Sign In</p>', unsafe_allow_html=True)
            st.markdown('<p class="login-subheader">Enter your authorized credentials to continue.</p>', unsafe_allow_html=True)
            
            username = st.text_input("Username / Email", placeholder="e.g. admin or email@hooghly.gov.in")
            password = st.text_input("Password", type="password", placeholder="••••••••")

            # ---------- CAPTCHA ----------
            question, correct_answer = get_captcha()
            captcha_input = st.text_input(f"Security Verification: What is {question}?", placeholder="Enter result")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_btn = st.form_submit_button("LOGIN TO WORKSPACE", type="primary", use_container_width=True)

            if submit_btn:
                # Validate CAPTCHA
                try:
                    user_answer = int(captcha_input.strip())
                except ValueError:
                    st.error("⚠️ Please enter a numeric answer for the security check.")
                    return False

                if user_answer != correct_answer:
                    st.error("❌ Incorrect security verification answer.")
                    clear_captcha()  
                    st.rerun()
                    return False

                clear_captcha()

                if not username or not password:
                    st.error("⚠️ Username and password are required.")
                else:
                    try:
                        supabase = get_supabase()
                        clean_input = username.strip()
                        login_email = clean_input if "@" in clean_input else f"{clean_input}@hooghly.gov.in"
                        
                        auth_response = supabase.auth.sign_in_with_password({"email": login_email, "password": password})
                        user_id = auth_response.user.id
                        users_data = supabase.table("users").select("*").eq("id", user_id).execute().data

                        if not users_data: 
                            st.error("❌ User profile not found in database.")
                        else:
                            user_profile = users_data[0]
                            if not user_profile.get("active", True):
                                st.error("🚫 This account has been deactivated.")
                            else:
                                # --- AUTOMATIC SESSION OVERWRITE (Last Login Wins) ---
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
                        st.error("❌ Invalid credentials. Please try again.")

    return False

def get_current_user():
    return st.session_state.get("user", None)

def logout(message=None):
    supabase = get_supabase()
    user_id = st.session_state.get('user', {}).get('id')
    
    if user_id:
        try:
            supabase.table("users").update({"current_session_token": None}).eq("id", user_id).execute()
        except Exception:
            pass

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
