import smtplib
import os
from email.message import EmailMessage

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # Menggunakan SSL

# MASUKKAN "Email Asli" DAN "16 Digit Sandi Aplikasi Google Tanpa Spasi"
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

def send_otp_email(receiver_email: str, otp_code: str):
    msg = EmailMessage()
    msg.set_content(f"Halo,\n\nKode OTP Anda untuk Smart-SME adalah: {otp_code}\n\nKode ini akan kedaluwarsa dalam 5 menit. Jangan berikan kode ini kepada siapa pun.")
    msg['Subject'] = 'Kode OTP Verifikasi Smart-SME'
    
    # 🔥 UPDATE: Menambahkan Nama Aplikasi agar terlihat profesional di Gmail user
    msg['From'] = f"Smart-SME <{SMTP_USER}>" 
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"=== EMAIL OTP: Berhasil dikirim ke {receiver_email} ===")
    except Exception as e:
        print(f"GAGAL AUTENTIKASI: Pastikan email benar dan Anda menggunakan 16 DIGIT SANDI APLIKASI (App Password) Google, BUKAN password email biasa! Error detail: {e}")
        raise Exception("Gagal mengirim email OTP, periksa konfigurasi server email.")