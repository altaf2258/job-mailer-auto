import os
import yaml
from dotenv import load_dotenv

# Load .env file
load_dotenv(override=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # Override/fill secrets from environment
    cfg["rapidapi_key"] = os.getenv("RAPIDAPI_KEY", "")
    cfg["smtp_email"] = os.getenv("SMTP_EMAIL", "")
    cfg["smtp_password"] = os.getenv("SMTP_PASSWORD", "")
    cfg["gemini_api_key"] = os.getenv("GEMINI_API_KEY", "")
    return cfg

