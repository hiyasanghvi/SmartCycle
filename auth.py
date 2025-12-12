# auth.py
import streamlit as st
from utils import create_user, get_user_by_email, update_last_login, hash_password, load_user_listings, init_db

# Initialize DB at start
init_db()
def require_auth():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    if st.session_state.user is None:
        login_signup_ui()

def login_signup_ui():
    st.markdown("## 🔐 Login / Sign Up")

    option = st.radio("Select option", ["Login", "Sign Up"], horizontal=True)

    name = st.text_input("Full Name") if option == "Sign Up" else ""
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    location = st.text_input("Location") if option == "Sign Up" else ""

    if st.button(option, use_container_width=True):

        # ============ VALIDATION ============ 
        if not email or not password or (option == "Sign Up" and (not name or not location)):
            st.error("Please fill all required fields")
            return

        # ============ SIGN UP ============
        if option == "Sign Up":
            success, msg = create_user(name, email, hash_password(password), location)

            if not success:
                st.error(msg)
                return

            st.session_state.user = {
                "name": name,
                "email": email,
                "location": location
            }

            st.session_state.item_list = load_user_listings(email)
            st.session_state.page = "Dashboard"
            st.rerun()

        # ============ LOGIN ============
        else:
            user = get_user_by_email(email)

            if not user:
                st.error("No user found with this email.")
                return

            if user[3] != hash_password(password):
                st.error("Incorrect password.")
                return

            st.session_state.user = {
                "name": user[1],
                "email": user[2],
                "location": user[4]
            }

            update_last_login(email)
            st.session_state.item_list = load_user_listings(email)

            st.success("Logged in successfully!")
            st.session_state.page = "Dashboard"
            st.rerun()

