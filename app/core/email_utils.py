import os
import json
import urllib.request

# Gunakan Email Sender yang diverifikasi di SendGrid
SMTP_USER = os.getenv("SMTP_USER", "smallmediumenterprices@gmail.com")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

def send_otp_email(receiver_email: str, otp_code: str):
    if not SENDGRID_API_KEY:
        print(f"PERINGATAN: SENDGRID_API_KEY belum diatur di environment. OTP: {otp_code}")
        # Jangan throw exception agar aplikasi tidak error selama masa transisi
        return
        
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "personalizations": [
            {
                "to": [{"email": receiver_email}],
                "subject": "Kode OTP Verifikasi Smart-SME"
            }
        ],
        "from": {"email": SMTP_USER, "name": "Smart-SME"},
        "content": [
            {
                "type": "text/html",
                "value": f"<html><body><p>Halo,</p><p>Kode OTP Anda untuk Smart-SME adalah: <strong style='font-size:24px;'>{otp_code}</strong></p><p>Kode ini akan kedaluwarsa dalam 5 menit. Jangan berikan kode ini kepada siapa pun.</p></body></html>"
            }
        ]
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            print(f"=== EMAIL OTP: Berhasil dikirim ke {receiver_email} via SendGrid ===")
    except Exception as e:
        print(f"Gagal mengirim email via SendGrid API: {e}")
        raise Exception("Gagal mengirim email OTP via SendGrid API.")