import os
import json
import urllib.request

# Gunakan Email Sender yang diverifikasi di akun Brevo teman Anda
SMTP_USER = os.getenv("SMTP_USER", "smallmediumenterprices@gmail.com") 
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

def send_otp_email(receiver_email: str, otp_code: str):
    if not BREVO_API_KEY:
        print(f"PERINGATAN: BREVO_API_KEY belum diatur di environment. OTP: {otp_code}")
        return
        
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    data = {
        "sender": {"name": "Smart-SME", "email": SMTP_USER},
        "to": [{"email": receiver_email}],
        "subject": "Kode OTP Verifikasi Smart-SME",
        "htmlContent": f"<html><body><p>Halo,</p><p>Kode OTP Anda untuk Smart-SME adalah: <strong style='font-size:24px;'>{otp_code}</strong></p><p>Kode ini akan kedaluwarsa dalam 5 menit. Jangan berikan kode ini kepada siapa pun.</p></body></html>"
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"=== EMAIL OTP: Berhasil dikirim ke {receiver_email} via Brevo API Teman ===")
    except Exception as e:
        print(f"Gagal mengirim email via Brevo API: {e}")
        raise Exception(f"Gagal mengirim email OTP via Brevo API. Pastikan SMTP_USER cocok dengan email teman Anda yang diverifikasi di Brevo.")