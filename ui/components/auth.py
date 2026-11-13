import re
import streamlit as st
from core.db import authenticate_user, register_user, create_session

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
NAME_REGEX = re.compile(r"^[a-zA-Z\s.'-]{2,60}$")
PHONE_REGEX = re.compile(r"^\+?[0-9\s\-]{7,15}$")

def validate_password_strength(password: str):
    """
    Validates password strength:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one numeric digit
    - At least one special character (!@#$%^&* etc.)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one numeric digit (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\\\/]", password):
        return False, "Password must include at least one special character (!@#$%^&* etc.)."
    return True, ""

def render_auth_gate():
    """Renders gated login and registration screen with full input validations."""
    st.markdown("<h2 style='text-align: center; margin-top: 3rem;'>💼 Job Mailer Pro</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #a0a0a0; margin-bottom: 2rem;'>Candidate Outreach & Automation Portal</p>", unsafe_allow_html=True)

    auth_col1, auth_col2, auth_col3 = st.columns([1, 1.8, 1])

    with auth_col2:
        tab_signin, tab_signup = st.tabs(["🔐 Sign In", "📝 Create Account"])

        with tab_signin:
            with st.form("signin_form"):
                st.markdown("#### Access Your Account")
                login_id = st.text_input("Username or Email", placeholder="e.g. nazimkhan or your@gmail.com")
                login_pwd = st.text_input("Password", type="password", placeholder="Enter your password")
                submit_login = st.form_submit_button("Sign In to Dashboard", type="primary", use_container_width=True)

                if submit_login:
                    cleaned_login = login_id.strip() if login_id else ""
                    if not cleaned_login:
                        st.error("⚠️ Please enter your username or registered email address.")
                    elif not login_pwd:
                        st.error("⚠️ Please enter your account password.")
                    elif len(login_pwd) < 6:
                        st.error("⚠️ Password must be at least 6 characters.")
                    else:
                        success, message, user = authenticate_user(cleaned_login, login_pwd)
                        if success:
                            token = create_session(user["id"])
                            st.query_params["session_token"] = token
                            st.session_state.authenticated = True
                            st.session_state.user_id = user["id"]
                            st.session_state.session_token = token
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")

        with tab_signup:
            with st.form("signup_form"):
                st.markdown("#### Register New Candidate")
                reg_username = st.text_input(
                    "Choose Username (Letters, numbers, underscores only)",
                    placeholder="e.g. nazim_khan24",
                    help="3-30 characters: letters, numbers, and underscores only. No spaces."
                )
                reg_name = st.text_input(
                    "Full Name (Letters and spaces only)",
                    placeholder="e.g. Nazim Khan",
                    help="Only alphabetic characters, spaces, dots, or hyphens allowed. No numbers."
                )
                reg_email = st.text_input(
                    "Sender Gmail / Email Address",
                    placeholder="e.g. nazim@gmail.com",
                    help="Valid email format required: example@domain.com"
                )
                reg_pwd = st.text_input(
                    "Create Password",
                    type="password",
                    placeholder="Min 8 chars: Upper, lower, digit & special char",
                    help="Must have at least 8 chars, 1 uppercase, 1 lowercase, 1 number, and 1 special symbol."
                )
                reg_pwd_confirm = st.text_input(
                    "Confirm Password",
                    type="password",
                    placeholder="Re-enter your password"
                )
                reg_title = st.text_input(
                    "Primary Job Title",
                    placeholder="e.g. Full-Stack Developer / SDE-2"
                )
                reg_phone = st.text_input(
                    "Phone Number (Digits only, optional + country code)",
                    placeholder="e.g. +91 9876543210",
                    help="Numbers only. May start with + followed by 7-15 digits."
                )
                reg_linkedin = st.text_input(
                    "LinkedIn Profile URL (Optional)",
                    placeholder="https://linkedin.com/in/nazimkhan"
                )
                reg_years = st.number_input(
                    "Years of Experience",
                    min_value=0,
                    max_value=40,
                    value=3
                )

                submit_signup = st.form_submit_button("Create Account & Launch Dashboard", type="primary", use_container_width=True)

                if submit_signup:
                    # Clean inputs
                    clean_user = reg_username.strip() if reg_username else ""
                    clean_name = reg_name.strip() if reg_name else ""
                    clean_email = reg_email.strip().lower() if reg_email else ""
                    clean_phone = reg_phone.strip() if reg_phone else ""
                    clean_linkedin = reg_linkedin.strip() if reg_linkedin else ""
                    clean_title = reg_title.strip() if reg_title else ""

                    errors = []

                    # 1. Username Validations
                    if not clean_user:
                        errors.append("Username is required.")
                    elif not USERNAME_REGEX.match(clean_user):
                        errors.append("Username must be 3–30 characters long and contain only letters, numbers, or underscores (no spaces or special symbols).")

                    # 2. Full Name Validations (Alphabets only)
                    if not clean_name:
                        errors.append("Full Name is required.")
                    elif not NAME_REGEX.match(clean_name):
                        errors.append("Full Name must contain only alphabets and spaces (no numbers or symbols).")
                    elif re.search(r"[0-9]", clean_name):
                        errors.append("Full Name cannot contain numbers.")

                    # 3. Email Validations
                    if not clean_email:
                        errors.append("Email address is required.")
                    elif not EMAIL_REGEX.match(clean_email):
                        errors.append("Please enter a valid email address (e.g., yourname@domain.com).")

                    # 4. Password Validations (Length, Uppercase, Lowercase, Number, Symbol)
                    if not reg_pwd:
                        errors.append("Password is required.")
                    else:
                        is_strong, pwd_err = validate_password_strength(reg_pwd)
                        if not is_strong:
                            errors.append(pwd_err)

                    # 5. Confirm Password Validation
                    if reg_pwd and reg_pwd != reg_pwd_confirm:
                        errors.append("Passwords do not match. Please ensure both password fields are identical.")

                    # 6. Phone Number Validations (Digits only, no letters)
                    if clean_phone:
                        # Check if letters exist in phone
                        if re.search(r"[a-zA-Z]", clean_phone):
                            errors.append("Phone number cannot contain alphabetic letters. Use only digits, spaces, hyphens, and an optional leading '+'.")
                        elif not PHONE_REGEX.match(clean_phone):
                            errors.append("Phone number must be between 7 and 15 digits (e.g. +91 9876543210).")

                    # 7. LinkedIn URL Validations
                    if clean_linkedin:
                        if not (clean_linkedin.startswith("http://") or clean_linkedin.startswith("https://")):
                            errors.append("LinkedIn URL must start with http:// or https://")
                        elif "linkedin.com" not in clean_linkedin.lower():
                            errors.append("LinkedIn URL must be a valid LinkedIn link (containing 'linkedin.com').")

                    # 8. Primary Title Validation
                    if clean_title and re.search(r"^[0-9]+$", clean_title):
                        errors.append("Job Title cannot be only numbers. Please enter a valid role name (e.g. Full Stack Developer).")

                    # Output errors or proceed
                    if errors:
                        for err in errors:
                            st.error(f"⚠️ {err}")
                    else:
                        ok, msg, new_uid = register_user(
                            username=clean_user,
                            full_name=clean_name,
                            email=clean_email,
                            password=reg_pwd,
                            phone=clean_phone,
                            linkedin=clean_linkedin,
                            years_exp=int(reg_years),
                            primary_title=clean_title or "Software Engineer"
                        )
                        if ok:
                            token = create_session(new_uid)
                            st.query_params["session_token"] = token
                            st.session_state.authenticated = True
                            st.session_state.user_id = new_uid
                            st.session_state.session_token = token
                            st.success(f"🎉 {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

    st.stop()

