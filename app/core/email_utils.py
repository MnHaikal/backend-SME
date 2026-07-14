import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ============================================================
# KONFIGURASI SMTP via BREVO (Sendinblue)
# SMTP Server: smtp-relay.brevo.com
# Port: 587 (TLS)
# Login: Email Anda yang terdaftar di Brevo
# Password: API Key Brevo (xkeysib-...)
# ============================================================

SMTP_USER = os.getenv("SMTP_USER", "smallmediumenterprices@gmail.com") 
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp-relay.brevo.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
BREVO_API_KEY = os.getenv("BREVO_API_KEY")


def _build_otp_html(otp_code: str) -> str:
    """Buat template HTML untuk email OTP."""
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #2563eb, #7c3aed); padding: 30px; border-radius: 10px; text-align: center;">
                <h1 style="color: white; margin: 0;">Smart-SME</h1>
                <p style="color: rgba(255,255,255,0.9); margin-top: 5px;">Verifikasi Akun Anda</p>
            </div>
            <div style="padding: 30px; background: #f9fafb; border-radius: 0 0 10px 10px;">
                <p style="color: #374151; font-size: 16px;">Halo,</p>
                <p style="color: #374151; font-size: 16px;">Kode OTP Anda untuk aplikasi Smart-SME adalah:</p>
                <div style="text-align: center; margin: 25px 0;">
                    <span style="font-size: 36px; font-weight: bold; color: #2563eb; letter-spacing: 8px; 
                                 background: #eff6ff; padding: 15px 30px; border-radius: 10px; border: 2px dashed #2563eb;">
                        {otp_code}
                    </span>
                </div>
                <p style="color: #6b7280; font-size: 14px;">⏱️ Kode ini akan kedaluwarsa dalam <strong>5 menit</strong>.</p>
                <p style="color: #6b7280; font-size: 14px;">🔒 Jangan berikan kode ini kepada siapa pun untuk alasan keamanan.</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                <p style="color: #9ca3af; font-size: 12px; text-align: center;">
                    Jika Anda tidak meminta kode ini, abaikan email ini.<br>
                    &copy; 2026 Smart-SME Team
                </p>
            </div>
        </body>
    </html>
    """


def send_otp_email(receiver_email: str, otp_code: str):
    """
    Kirim OTP via Brevo HTTP API (v3).
    Ini lebih stabil daripada SMTP Brevo.
    """
    import requests

    if not BREVO_API_KEY:
        print("PERINGATAN: BREVO_API_KEY belum diatur di .env!")
        print(f"OTP untuk {receiver_email}: {otp_code}")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY
    }
    payload = {
        "sender": {
            "name": "Smart-SME",
            "email": SMTP_USER
        },
        "to": [
            {
                "email": receiver_email
            }
        ],
        "subject": "Kode OTP Verifikasi Smart-SME",
        "htmlContent": _build_otp_html(otp_code)
    }

    try:
        print(f"[BREVO API] Mengirim email OTP ke {receiver_email}...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 201:
            print(f"=== [BREVO API] Email OTP berhasil dikirim ke {receiver_email} ===")
        else:
            print(f"[BREVO API] GAGAL: Status {response.status_code}, Response: {response.text}")
            raise Exception(f"Brevo API error: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"[BREVO API] ERROR: {e}")
        raise Exception(f"Gagal mengirim email OTP via Brevo API: {e}")