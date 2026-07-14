import os
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

from app.core.email_utils import send_otp_email, send_otp_email_via_api

print("Testing SMTP Brevo...")
try:
    send_otp_email("haikal@example.com", "123456")
except Exception as e:
    print(f"SMTP Error: {e}")

print("\nTesting HTTP API Brevo...")
try:
    send_otp_email_via_api("haikal@example.com", "654321")
except Exception as e:
    print(f"API Error: {e}")
