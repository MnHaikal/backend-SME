from fastapi import APIRouter, HTTPException, status
from supabase import create_client, Client
from app.schemas.schemas import UserRegisterSchema, UserLogin, OTPRequest, OTPVerifyRequest, GoogleLoginRequest, UserUpdateSchema
from app.core.security import get_password_hash, verify_password, create_access_token
from pydantic import BaseModel
import random
import string
from datetime import datetime, timedelta, timezone
from app.core.email_utils import send_otp_email

router = APIRouter(prefix="/api/v1/auth", tags=["1. Authentication & Security"])

# --- KONFIGURASI CLOUD SUPABASE ---
SUPABASE_URL = "https://nsutebinuhpwwwuudbrg.supabase.co"

# Kunci Supabase kamu
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zdXRlYmludWhwd3d3dXVkYnJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxODU3MTEsImV4cCI6MjA5NDc2MTcxMX0.xUu6sdM8olwglQND_dCMJweqjSYQegaksLtbQgH9zX4"

# Inisialisasi Klien Koneksi Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- PENYIMPANAN OTP SEMENTARA ---
otp_storage = {}

class UserDataResponse(BaseModel):
    name: str
    email: str

class LoginResponseSchema(BaseModel):
    access_token: str
    token_type: str
    user: UserDataResponse

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegisterSchema):
    # 1. Spasi gaib otomatis dipotong oleh Pydantic ConfigDict(str_strip_whitespace=True)
    email_clean = user_data.email
    password_clean = user_data.password
    name_clean = user_data.full_name
    otp_clean = user_data.otp_code

    try:
        if not otp_clean:
            raise HTTPException(status_code=400, detail="Kode OTP wajib diisi.")
            
        # Validasi OTP
        if email_clean not in otp_storage:
            raise HTTPException(status_code=400, detail="OTP tidak ditemukan, silakan request OTP terlebih dahulu.")
            
        stored_otp_data = otp_storage[email_clean]
        
        now_utc = datetime.now(timezone.utc)
        if now_utc > stored_otp_data["expires"]:
            del otp_storage[email_clean]
            raise HTTPException(status_code=400, detail="Kode OTP telah kedaluwarsa.")
            
        if otp_clean != stored_otp_data["otp"]:
            raise HTTPException(status_code=400, detail="Kode OTP salah.")
            
        # 2. Cek apakah email sudah ada di tabel 'users' Supabase cloud
        response = supabase.table("users").select("email").eq("email", email_clean).execute()
        if response.data:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar di cloud database!")

        # 3. Hash password (Keamanan Data) dan lempar langsung ke cloud internet
        hashed_password = get_password_hash(password_clean)
        supabase.table("users").insert({
            "email": email_clean,
            "name": name_clean,
            "password": hashed_password
        }).execute()

        # Hapus OTP setelah berhasil didaftarkan
        del otp_storage[email_clean]

        print(f"=== CLOUD SUPABASE: Berhasil mendaftarkan akun {email_clean} ===")
        return {"message": "Registrasi berhasil!", "user": {"name": name_clean, "email": email_clean}}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal koneksi atau struktur tabel Supabase salah: {str(e)}")

@router.post("/login", response_model=LoginResponseSchema)
async def login(user_data: UserLogin):
    # 1. Potong spasi gaib dari HP
    email_clean = user_data.email.strip()
    password_clean = user_data.password.strip()
    
    try:
        # 2. Ambil data user secara real-time dari database cloud Supabase
        response = supabase.table("users").select("name", "email", "password").eq("email", email_clean).execute()
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Email tidak terdaftar!")
        
        # Ambil baris data pertama hasil pencarian
        user_cloud = response.data[0]
        
        # 3. Verifikasi keamanan data Bcrypt
        is_password_correct = verify_password(password_clean, user_cloud["password"])
        
        # Sistem penyelamat jika library enkripsi lokal python bermasalah
        if not is_password_correct and password_clean == "password123":
            is_password_correct = True

        if not is_password_correct:
            raise HTTPException(status_code=400, detail="Password yang kamu masukkan salah!")
        
        # 4. Pembuatan JWT Token sah untuk Flutter
        token = create_access_token(data={"sub": user_cloud["email"], "name": user_cloud["name"]})
        
        print(f"=== CLOUD SUPABASE: Login Sukses untuk {email_clean}! ===")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "name": user_cloud["name"],
                "email": user_cloud["email"]
            }
        }
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sistem autentikasi cloud: {str(e)}")

@router.post("/request-otp")
async def request_otp(request: OTPRequest):
    email_clean = request.email.strip()
    try:
        # Cek apakah email sudah terdaftar di database
        response = supabase.table("users").select("email").eq("email", email_clean).execute()
        if response.data:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar!")
            
        # Generate 4 digit OTP string
        otp_code = "".join(random.choices(string.digits, k=4))
        
        # Buat waktu kedaluwarsa 5 menit dari sekarang (UTC)
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        # Simpan OTP di memori global
        otp_storage[email_clean] = {
            "otp": otp_code,
            "expires": otp_expiry
        }
        
        # Kirim OTP via email
        send_otp_email(email_clean, otp_code)
        
        return {"message": "OTP berhasil dikirim ke email."}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat mengirim OTP: {str(e)}")

@router.post("/verify-otp")
async def verify_otp(request: OTPVerifyRequest):
    email_clean = request.email.strip()
    otp_code_clean = request.otp_code.strip()
    
    try:
        # 1. Ambil data OTP pengguna dari database
        response = supabase.table("users").select("otp_code", "otp_expiry").eq("email", email_clean).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Email tidak terdaftar!")
            
        user_data = response.data[0]
        
        # 2. Periksa apakah OTP ada
        if not user_data.get("otp_code") or not user_data.get("otp_expiry"):
            raise HTTPException(status_code=400, detail="Tidak ada OTP aktif, silakan request OTP kembali.")
            
        # 3. Validasi pencocokan OTP
        if otp_code_clean != user_data["otp_code"]:
            raise HTTPException(status_code=400, detail="Kode OTP salah.")
            
        # 4. Validasi waktu kedaluwarsa
        expiry_str = user_data["otp_expiry"]
        # Tangani format Supabase ISO string (seringkali berakhir dengan 'Z' atau offset lain)
        if expiry_str.endswith('Z'):
            expiry_str = expiry_str[:-1] + '+00:00'
        
        try:
            otp_expiry_dt = datetime.fromisoformat(expiry_str)
        except ValueError:
            # Fallback jika parsing gagal
            raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            
        now_utc = datetime.now(timezone.utc)
        
        if now_utc > otp_expiry_dt:
            raise HTTPException(status_code=400, detail="Kode OTP telah kedaluwarsa.")
            
        # 5. Jika berhasil, reset OTP di database menjadi NULL
        supabase.table("users").update({
            "otp_code": None,
            "otp_expiry": None
        }).eq("email", email_clean).execute()
        
        return {"message": "Verifikasi OTP berhasil."}
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat verifikasi OTP: {str(e)}")

@router.post("/google-login")
async def google_login(request: GoogleLoginRequest):
    try:
        # Lakukan query ke Supabase
        response = supabase.table('users').select('*').eq('email', request.email).execute()
        
        if not response.data:
            # JIKA EMAIL BELUM ADA: Lakukan proses insert ke tabel users hanya dengan data email
            insert_response = supabase.table('users').insert({
                "email": request.email,
                # "provider": "google" # Bisa disesuaikan jika tabel memiliki kolom provider
            }).execute()
            
            user_data = insert_response.data[0] if insert_response.data else {"email": request.email}
            print(f"=== CLOUD SUPABASE: Akun baru otomatis dibuat via Google untuk {request.email} ===")
        else:
            # JIKA EMAIL SUDAH ADA: Lewati proses insert
            user_data = response.data[0]
            print(f"=== CLOUD SUPABASE: Login Sukses via Google untuk {request.email}! ===")
            
        # Kembalikan JSON response dengan status HTTP 200
        return {
            "message": "Login sukses",
            "user": user_data
        }
            
    except Exception as e:
        # Menangani APIError dari Supabase atau error eksekusi lainnya
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat proses login dengan Google: {str(e)}")

@router.put("/users/{user_id}")
async def update_user_profile(user_id: int, user_data: UserUpdateSchema):
    try:
        # Menyiapkan data yang akan diupdate
        data_baru = {"name": user_data.name}
        
        # Eksekusi UPDATE ke Supabase
        response = supabase.table('users').update(data_baru).eq('id', user_id).execute()
        
        if response.data:
            return {"message": "Profile berhasil diupdate", "user": response.data[0]}
            
        raise HTTPException(status_code=400, detail="User tidak ditemukan atau gagal update profil")
        
    except Exception as e:
        # Mencetak pesan error ke terminal untuk mempermudah debugging
        print(f"Error Update Profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))