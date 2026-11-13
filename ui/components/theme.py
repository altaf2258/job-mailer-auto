import streamlit as st

def apply_custom_theme():
    """Injects modern, compact styles and custom sidebar appearance."""
    st.markdown("""
        <style>
        /* Remove default Streamlit excessive top padding */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        
        /* Keep header minimal for sidebar toggle arrow */
        header[data-testid="stHeader"] {
            background-color: transparent !important;
            height: 2.2rem !important;
            z-index: 99 !important;
        }
        
        /* Sidebar collapse/expand button style */
        button[data-testid="stSidebarCollapseButton"],
        button[data-testid="stSidebarHeaderCollapseButton"] {
            color: #e0e0e0 !important;
            background-color: #222230 !important;
            border-radius: 6px !important;
            border: 1px solid #3c3c52 !important;
            transition: all 0.2s ease;
        }
        button[data-testid="stSidebarCollapseButton"]:hover,
        button[data-testid="stSidebarHeaderCollapseButton"]:hover {
            background-color: #3b3b55 !important;
            border-color: #ff4b4b !important;
        }

        /* Responsive sidebar styling with slim scrollbar */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111119 0%, #161623 100%) !important;
            border-right: 1px solid #28283c !important;
            box-shadow: 2px 0 15px rgba(0, 0, 0, 0.4);
        }
        section[data-testid="stSidebar"] > div {
            padding-top: 0.6rem !important;
            padding-bottom: 0.6rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            overflow-y: auto !important;
            scrollbar-width: thin;
            scrollbar-color: #3b3b55 transparent;
        }
        section[data-testid="stSidebar"] > div::-webkit-scrollbar {
            width: 5px;
        }
        section[data-testid="stSidebar"] > div::-webkit-scrollbar-track {
            background: transparent;
        }
        section[data-testid="stSidebar"] > div::-webkit-scrollbar-thumb {
            background: #3b3b55;
            border-radius: 4px;
        }
        section[data-testid="stSidebar"] > div::-webkit-scrollbar-thumb:hover {
            background: #ff4b4b;
        }

        /* User Profile Card */
        .user-profile-badge {
            background: linear-gradient(135deg, #1b1b2a 0%, #202034 100%);
            border: 1px solid #33334d;
            border-radius: 10px;
            padding: 9px 12px;
            margin-bottom: 6px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25);
        }
        .user-profile-badge h4 {
            margin: 0 !important;
            color: #ffffff;
            font-size: 1.02rem;
            font-weight: 700;
            letter-spacing: -0.3px;
        }
        .user-profile-badge p {
            margin: 1px 0 0 0 !important;
            color: #b0b0cc;
            font-size: 0.78rem;
            line-height: 1.25;
        }

        /* Sidebar Navigation Tile Buttons */
        div[data-testid="stSidebar"] div.stButton {
            margin-bottom: 0px !important;
        }
        div[data-testid="stSidebar"] div.stButton > button {
            width: 100% !important;
            min-height: 2.2rem !important;
            background-color: #1a1a27 !important;
            color: #d1d1e4 !important;
            border: 1px solid #2d2d42 !important;
            border-radius: 8px !important;
            padding: 6px 12px !important;
            text-align: left !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: center !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            margin-bottom: 3px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15) !important;
        }
        div[data-testid="stSidebar"] div.stButton > button:hover {
            background-color: #26263b !important;
            border-color: #4f4f72 !important;
            color: #ffffff !important;
            transform: translateX(3px) !important;
        }
        /* Active Tile Style */
        div[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #2b1f28 0%, #3a1c25 100%) !important;
            border: 1px solid #ff4b4b !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 3px 10px rgba(255, 75, 75, 0.22) !important;
            transform: translateX(3px) !important;
        }
        div[data-testid="stSidebar"] div.stButton > button p {
            font-size: 0.88rem !important;
            text-align: left !important;
            margin: 0 !important;
            line-height: 1.2 !important;
        }
        /* Logout Tile */
        div[data-testid="stSidebar"] div.stButton:last-child > button {
            background: #191419 !important;
            border-color: #3d232a !important;
            color: #d48b94 !important;
            justify-content: center !important;
            text-align: center !important;
            margin-top: 4px !important;
        }
        div[data-testid="stSidebar"] div.stButton:last-child > button:hover {
            background: #2a151b !important;
            border-color: #ff4b4b !important;
            color: #ffffff !important;
        }

        /* Compact Metric Cards */
        div[data-testid="stMetric"] {
            background-color: #171722;
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid #2c2c3e;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }

        /* Compact headings */
        h1, h2, h3, h4 {
            margin-top: 0.2rem !important;
            margin-bottom: 0.4rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

