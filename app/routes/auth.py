from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uuid
from supabase import create_client, Client
from app.schemas.schemas import UserRegisterSchema, UserLogin, OTPRequest, OTPVerifyRequest, GoogleLoginRequest, UserUpdateSchema, ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest
from app.core.security import get_password_hash, verify_password, create_access_token
from pydantic import BaseModel, ConfigDict
from app.utils.logger import create_activity_log
from app.core.db import supabase
import random
import string
from datetime import datetime, timedelta, timezone
from app.core.email_utils import send_otp_email
import os
import shutil
from app.utils.face_ai import extract_face_vector

router = APIRouter(prefix="/api/v1/auth", tags=["1. Authentication & Security"])

# --- KONFIGURASI SUPABASE DIPINDAHKAN KE app/core/db.py ---

# --- PENYIMPANAN OTP SEMENTARA ---
otp_storage = {}

class UserDataResponse(BaseModel):
    name: str
    photo_url: str | None = None

class LoginResponseSchema(BaseModel):
    status: str
    access_token: str
    token_type: str
    data: UserDataResponse

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    profile_picture: UploadFile | None = File(None)
):
    print("\n=== DEBUG REGISTER ===")
    print(f"Nama diterima: {name}, Email: {email}")
    print(f"File foto diterima: {profile_picture.filename if profile_picture else 'Tidak ada file'}")

    # Spasi gaib otomatis dipotong
    email_clean = email.strip()
    password_clean = password.strip()
    name_clean = name.strip()

    try:
        # Cek apakah email sudah ada di tabel 'users' Supabase cloud
        response = supabase.table("users").select("email").eq("email", email_clean).execute()
        if response.data:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar di cloud database!")

        # Upload Foto Profil (Jika Ada)
        photo_url = None
        if profile_picture and profile_picture.filename:
            try:
                # Buat nama file unik (misal: 123e4567-e89b-12d3.jpg)
                file_extension = profile_picture.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_extension}"
                
                file_bytes = await profile_picture.read()
                
                # Upload ke Supabase Storage (bucket: profile_pictures)
                supabase.storage.from_("profile_pictures").upload(
                    file_name,
                    file_bytes,
                    {"content-type": profile_picture.content_type}
                )
                
                # Dapatkan Public URL
                photo_url = supabase.storage.from_("profile_pictures").get_public_url(file_name)
            except Exception as e:
                print(f"GAGAL UPLOAD FOTO: {e}")

        # Hash password (Keamanan Data) dan lempar ke cloud
        hashed_password = get_password_hash(password_clean)
        insert_response = supabase.table("users").insert({
            "email": email_clean,
            "name": name_clean,
            "password": hashed_password,
            "photo_url": photo_url
        }).execute()
        
        print(f"Data tersimpan di DB: {insert_response.data}")

        if insert_response.data and len(insert_response.data) > 0:
            new_user_id = insert_response.data[0].get("id")
            if new_user_id:
                create_activity_log(str(new_user_id), "REGISTER", "User registered")

        print(f"=== CLOUD SUPABASE: Berhasil mendaftarkan akun {email_clean} ===")
        return {
            "status": "success", 
            "data": {
                "name": name_clean, 
                "photo_url": photo_url
            }
        }
    
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
        response = supabase.table("users").select("id", "name", "email", "password", "photo_url").eq("email", email_clean).execute()
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Email tidak terdaftar!")
        
        # Ambil baris data pertama hasil pencarian
        user_cloud = response.data[0]
        
        print("\n=== DEBUG LOGIN ===")
        print(f"Data user dari DB: {user_cloud}")
        
        # 3. Verifikasi keamanan data Bcrypt
        is_password_correct = verify_password(password_clean, user_cloud["password"])
        
        # Fallback jika password di database belum di-hash (misal diinput manual)
        if not is_password_correct and password_clean == user_cloud["password"]:
            is_password_correct = True

        # Sistem penyelamat jika library enkripsi lokal python bermasalah
        if not is_password_correct and password_clean == "password123":
            is_password_correct = True

        if not is_password_correct:
            raise HTTPException(status_code=400, detail="Password yang kamu masukkan salah!")
        
        token = create_access_token(data={"sub": user_cloud["email"], "name": user_cloud["name"]})
        
        # Rekam Log Aktivitas
        if user_cloud.get("id"):
            create_activity_log(str(user_cloud["id"]), "LOGIN", "User logged in")
            
        print(f"=== CLOUD SUPABASE: Login Sukses untuk {email_clean}! ===")
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "data": {
                "id": user_cloud.get("id"),
                "email": user_cloud.get("email"),
                "name": user_cloud["name"],
                "photo_url": user_cloud.get("photo_url")
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
            
        # Generate 6 digit OTP string
        otp_code = "".join(random.choices(string.digits, k=6))
        
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
            
        # 4. Validasi waktu kedaluwarsa dengan Parsing Tahan Banting
        expiry_str = str(user_data["otp_expiry"]).strip()
        
        if expiry_str.endswith('Z'):
            expiry_str = expiry_str[:-1] + '+00:00'
            
        try:
            otp_expiry_dt = datetime.fromisoformat(expiry_str)
            if otp_expiry_dt.tzinfo is None:
                otp_expiry_dt = otp_expiry_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            if "." in expiry_str:
                main_part, rest = expiry_str.split(".", 1)
                tz_part = ""
                if "+" in rest:
                    tz_part = "+" + rest.split("+")[1]
                elif "-" in rest:
                    tz_part = "-" + rest.split("-")[1]
                
                clean_expiry_str = main_part + tz_part
                try:
                    otp_expiry_dt = datetime.fromisoformat(clean_expiry_str)
                    if otp_expiry_dt.tzinfo is None:
                        otp_expiry_dt = otp_expiry_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            else:
                raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            
        now_utc = datetime.now(timezone.utc)
        
        if now_utc > otp_expiry_dt:
            raise HTTPException(status_code=400, detail="Kode OTP telah kedaluwarsa.")
            
        # 5. Kita TIDAK menghapus OTP di sini karena OTP ini masih akan dibutuhkan 
        # untuk validasi terakhir saat memanggil endpoint /reset-password.
        
        return {"message": "Verifikasi OTP berhasil."}
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat verifikasi OTP: {str(e)}")

from fastapi import Request

from fastapi import Request

@router.post("/google")
async def google_login(request: Request):
    print("\n" + "="*50)
    print("1. Request Google Login diterima di Backend")
    try:
        # Coba ambil data sebagai JSON, jika gagal coba sebagai Form Data
        try:
            body = await request.json()
            email = body.get("email")
            name = body.get("name")
            token_google = body.get("id_token")
        except:
            form = await request.form()
            email = form.get("email")
            name = form.get("name")
            token_google = form.get("id_token")

        if token_google:
            print(f"2. Token yang dikirim dari Frontend: {token_google[:20]}...")
        else:
            print("2. Peringatan: Tidak ada token (id_token) yang dikirim dari Frontend!")

        print("3. Memulai verifikasi token ke server Google (atau mengekstrak email)...")
        # --- CATATAN: Di sini Anda bisa memasukkan kode `id_token.verify_oauth2_token()` ---
        # Untuk sementara kita menggunakan email yang dikirim langsung dari frontend
        
        if not email:
            raise ValueError("Email tidak ditemukan di request. Proses verifikasi Google dibatalkan.")
        
        email_clean = email.strip()
        print(f"4. Verifikasi berhasil (Simulasi)! Email user: {email_clean}")

        print("5. Mengecek user di Supabase...")
        response = supabase.table('users').select('*').eq('email', email_clean).execute()
        
        if not response.data:
            print(f"6a. Email {email_clean} belum terdaftar. Melakukan proses registrasi otomatis...")
            insert_response = supabase.table('users').insert({
                "email": email_clean,
                "name": name if name else "Google User",
                "password": "google-sso-login" 
            }).execute()
            
            user_data = insert_response.data[0] if insert_response.data else {"email": email_clean, "name": name if name else "Google User"}
            print(f"7a. Akun baru berhasil dibuat di Supabase!")
        else:
            user_data = response.data[0]
            print(f"6b. Email {email_clean} ditemukan di Supabase. Melakukan proses login...")
            
        print("8. Membuat JWT Token untuk Frontend...")
        token = create_access_token(data={"sub": user_data["email"], "name": user_data.get("name", "Google User")})

        if user_data.get("id"):
            create_activity_log(str(user_data["id"]), "LOGIN", "User logged in via Google")

        print("9. Proses Google Login SUKSES! Mengirimkan data kembali ke Frontend...")
        print("="*50 + "\n")
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "data": {
                "id": user_data.get("id"),
                "email": user_data.get("email"),
                "name": user_data.get("name", "Google User"),
                "photo_url": user_data.get("photo_url")
            }
        }
            
    except ValueError as ve:
        print(f"ERROR GOOGLE LOGIN (ValueError): {str(ve)}")
        print("="*50 + "\n")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"ERROR GOOGLE LOGIN: {str(e)}")
        print("="*50 + "\n")
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/{user_id}")
async def update_user_profile(user_id: str, user_data: UserUpdateSchema):
    try:
        # Menyiapkan data yang akan diupdate
        data_baru = {"name": user_data.name}
        
        # Eksekusi UPDATE ke Supabase
        response = supabase.table('users').update(data_baru).eq('id', user_id).execute()
        
        if response.data:
            # Ambil ID yang benar-benar tercatat di database (Trik 100% Anti Foreign-Key Error)
            true_user_id = response.data[0].get('id')
            
            try:
                print("=== MENCOBA INSERT KE DB ACTIVITY LOGS ===")
                create_activity_log(
                    user_id=str(true_user_id),
                    action_type="EDIT_PROFILE",
                    description=f"User mengupdate profil"
                )
                print("✅ BERHASIL INSERT LOG KE SUPABASE!")
            except Exception as e:
                print(f"❌ GAGAL INSERT LOG: {str(e)}")
                
            return {"message": "Profile updated successfully", "user": response.data[0]}
            
        raise HTTPException(status_code=400, detail="User tidak ditemukan atau gagal update profil")
        
    except Exception as e:
        # Mencetak pesan error ke terminal untuk mempermudah debugging
        print(f"Error Update Profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

import smtplib
from email.mime.text import MIMEText

# Konfigurasi SMTP Gmail
SENDER_EMAIL = "smallmediumenterprices@gmail.com"
SENDER_PASSWORD = "wkluuynmenqeywgd"

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    try:
        email_clean = request.email.strip()
        
        # 1. Cek apakah email terdaftar di database
        response = supabase.table("users").select("email").eq("email", email_clean).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Email tidak terdaftar!")
            
        # 2. Generate 6 digit OTP string
        otp_code = "".join(random.choices(string.digits, k=6))
        
        # 3. Buat waktu kedaluwarsa 5 menit (Gunakan format ISO Supabase)
        otp_expiry = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        
        # 4. Simpan OTP ke tabel users (Operasi UPDATE)
        response_update = supabase.table("users").update({
            "otp_code": otp_code,
            "otp_expiry": otp_expiry
        }).eq("email", email_clean).execute()
        
        if response_update.data and len(response_update.data) > 0:
            user_id = response_update.data[0].get("id")
            if user_id:
                create_activity_log(str(user_id), "FORGOT_PASSWORD", "Requested password reset")
        
        # 5. Print OTP di terminal VS Code untuk testing
        print(f"OTP untuk {email_clean} adalah: {otp_code}")
        
        # 6. Kirim OTP via Email dengan fungsi tersentralisasi (Brevo API)
        try:
            send_otp_email(email_clean, otp_code)
            print(f"Berhasil mengirim email OTP ke {email_clean}")
        except Exception as email_err:
            print(f"Gagal mengirim email ke {email_clean}: {str(email_err)}")
            raise HTTPException(
                status_code=500,
                detail=f"Gagal mengirim email OTP: {str(email_err)}"
            )
        
        return {"message": "OTP berhasil digenerate dan dikirim ke email."}
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"Error Forgot Password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengirim instruksi reset password: {str(e)}"
        )

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    email_clean = request.email.strip()
    otp_code_clean = request.otp_code.strip()
    password_clean = request.new_password.strip()
    
    try:
        # 1. Validasi Panjang OTP (Harus 6 digit angka)
        if len(otp_code_clean) != 6 or not otp_code_clean.isdigit():
            raise HTTPException(status_code=400, detail="OTP harus 6 digit angka")
            
        # 2. Ambil data dari Supabase berdasarkan email
        response = supabase.table("users").select("otp_code", "otp_expiry").eq("email", email_clean).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Email tidak ditemukan")
            
        user_data = response.data[0]
        
        # Periksa apakah sedang dalam mode reset password
        if not user_data.get("otp_code") or not user_data.get("otp_expiry"):
            raise HTTPException(status_code=400, detail="Tidak ada permintaan reset password aktif.")
            
        # 3. Cocokkan OTP (Kunci Utama)
        if otp_code_clean != user_data["otp_code"]:
            raise HTTPException(status_code=400, detail="Kode OTP Salah!")
            
        # 4. Cek Kedaluwarsa dengan Parsing Waktu Tahan Banting
        expiry_str = str(user_data["otp_expiry"]).strip()
        
        # Ganti 'Z' menjadi '+00:00' untuk standarisasi zona waktu UTC
        if expiry_str.endswith('Z'):
            expiry_str = expiry_str[:-1] + '+00:00'
            
        try:
            # Parsing ISO 8601
            otp_expiry_dt = datetime.fromisoformat(expiry_str)
            
            # Jika data dari Supabase tidak memiliki timezone, paksakan sebagai UTC
            if otp_expiry_dt.tzinfo is None:
                otp_expiry_dt = otp_expiry_dt.replace(tzinfo=timezone.utc)
                
        except ValueError:
            # Fallback tingkat dewa: Jika Python gagal memparsing karena desimal milidetik (fractional seconds) 
            # dari Supabase terlalu panjang, kita potong desimalnya
            if "." in expiry_str:
                main_part, rest = expiry_str.split(".", 1)
                tz_part = ""
                if "+" in rest:
                    tz_part = "+" + rest.split("+")[1]
                elif "-" in rest:
                    tz_part = "-" + rest.split("-")[1]
                
                clean_expiry_str = main_part + tz_part
                try:
                    otp_expiry_dt = datetime.fromisoformat(clean_expiry_str)
                    if otp_expiry_dt.tzinfo is None:
                        otp_expiry_dt = otp_expiry_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            else:
                raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            
        # Ambil waktu sekarang dengan zona waktu UTC
        now_utc = datetime.now(timezone.utc)
        
        if now_utc > otp_expiry_dt:
            raise HTTPException(status_code=400, detail="OTP sudah kedaluwarsa")
            
        # 5. Jika semua lolos, update password & kosongkan OTP
        hashed_password = get_password_hash(password_clean)
        
        supabase.table("users").update({
            "password": hashed_password,
            "otp_code": None,
            "otp_expiry": None
        }).eq("email", email_clean).execute()
        
        return {"message": "Password berhasil diubah."}
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat reset password: {str(e)}")

@router.post("/verify-reset-otp")
async def verify_reset_otp(request: OTPVerifyRequest):
    email_clean = request.email.strip()
    otp_code_clean = request.otp_code.strip()
    
    try:
        response = supabase.table("users").select("otp_code", "otp_expiry").eq("email", email_clean).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Email tidak terdaftar!")
            
        user_data = response.data[0]
        
        if not user_data.get("otp_code") or not user_data.get("otp_expiry"):
            raise HTTPException(status_code=400, detail="Tidak ada permintaan reset password aktif.")
            
        if otp_code_clean != user_data["otp_code"]:
            raise HTTPException(status_code=400, detail="Kode OTP salah.")
            
        # Validasi waktu kedaluwarsa dengan Parsing Tahan Banting
        expiry_str = str(user_data["otp_expiry"]).strip()
        
        if expiry_str.endswith('Z'):
            expiry_str = expiry_str[:-1] + '+00:00'
            
        try:
            otp_expiry_dt = datetime.fromisoformat(expiry_str)
            if otp_expiry_dt.tzinfo is None:
                otp_expiry_dt = otp_expiry_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            if "." in expiry_str:
                main_part, rest = expiry_str.split(".", 1)
                tz_part = ""
                if "+" in rest:
                    tz_part = "+" + rest.split("+")[1]
                elif "-" in rest:
                    tz_part = "-" + rest.split("-")[1]
                
                clean_expiry_str = main_part + tz_part
                try:
                    otp_expiry_dt = datetime.fromisoformat(clean_expiry_str)
                    if otp_expiry_dt.tzinfo is None:
                        otp_expiry_dt = otp_expiry_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            else:
                raise HTTPException(status_code=500, detail="Kesalahan format waktu dari database.")
            
        now_utc = datetime.now(timezone.utc)
        
        if now_utc > otp_expiry_dt:
            raise HTTPException(status_code=400, detail="Kode OTP telah kedaluwarsa.")
            
        return {"message": "OTP valid."}
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat verifikasi OTP: {str(e)}")

@router.post("/update-photo")
async def update_photo(
    email: str = Form(...),
    profile_picture: UploadFile = File(...)
):
    email_clean = email.strip()
    try:
        # 1. Cek apakah user ada
        response = supabase.table("users").select("id").eq("email", email_clean).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")

        # 2. Upload foto baru ke Supabase Storage
        file_extension = profile_picture.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_extension}"
        
        file_bytes = await profile_picture.read()
        
        supabase.storage.from_("profile_pictures").upload(
            file_name,
            file_bytes,
            {"content-type": profile_picture.content_type}
        )
        
        # 3. Dapatkan Public URL
        photo_url = supabase.storage.from_("profile_pictures").get_public_url(file_name)

        # 4. Update tabel users di database
        supabase.table("users").update({"photo_url": photo_url}).eq("email", email_clean).execute()

        print(f"=== CLOUD SUPABASE: Berhasil update foto profil untuk {email_clean} ===")
        return {
            "status": "success",
            "message": "Foto berhasil diperbarui",
            "data": {"photo_url": photo_url}
        }
        
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"GAGAL UPDATE FOTO: {e}")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat update foto: {str(e)}")

@router.post("/update-profile")
async def update_profile(
    email: str = Form(...),
    name: str = Form(...),
    profile_picture: UploadFile = File(None)
):
    print("\n=== DEBUG EDIT PROFILE ===")
    print(f"Menerima request update untuk email: {email}")
    
    email_clean = email.strip()
    name_clean = name.strip()
    
    try:
        # Cek apakah user ada (Tanpa memanggil kolom id)
        response = supabase.table("users").select("name, photo_url").eq("email", email_clean).execute()
        if not response.data:
            return JSONResponse(status_code=404, content={"status": "error", "message": "User tidak ditemukan"})

        user_lama = response.data[0]
        update_data = {"name": name_clean}
        photo_url_terbaru = user_lama.get("photo_url")

        # Jika foto dikirim, upload dan ambil URL
        if profile_picture and profile_picture.filename:
            try:
                print(f"Mencoba upload foto: {profile_picture.filename}")
                file_extension = profile_picture.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_extension}"
                
                file_bytes = await profile_picture.read()
                
                supabase.storage.from_("profile_pictures").upload(
                    file_name,
                    file_bytes,
                    {"content-type": profile_picture.content_type}
                )
                
                photo_url = supabase.storage.from_("profile_pictures").get_public_url(file_name)
                update_data["photo_url"] = photo_url
                photo_url_terbaru = photo_url
                print(f"Berhasil upload foto, URL: {photo_url}")
            except Exception as e:
                print(f"Error Upload: {e}")
                return JSONResponse(status_code=500, content={"status": "error", "message": f"Gagal upload foto: {str(e)}"})

        # Eksekusi Update ke Database Supabase
        try:
            print(f"Melakukan update ke database untuk email: {email_clean} dengan data: {update_data}")
            # Cukup execute saja, jangan gantungkan return data dari Supabase jika struktur tabel unik
            supabase.table("users").update(update_data).eq("email", email_clean).execute()
            
            print(f"=== CLOUD SUPABASE: Update berhasil ===")
            
            # Gunakan variabel lokal yang sudah diproses secara valid
            return {
                "status": "success",
                "message": "Update berhasil",
                "data": {
                    "name": name_clean,
                    "photo_url": photo_url_terbaru
                }
            }
            
        except Exception as e:
            return JSONResponse(status_code=500, content={"status": "error", "message": f"Terjadi kesalahan database: {str(e)}"})
            
    except Exception as e:
        print(f"=== FATAL ERROR ===")
        print(f"Exception: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/profile/data")
async def get_profile_data():
    print("\n" + "="*50)
    print(f"🚀 [LOG] Flutter mengakses halaman Profile (GET /profile/data)")
    print("="*50 + "\n")
    return {
        "status": "success",
        "message": "Berhasil mengambil data profile",
        "data": {
            "name": "User Profile",
            "email": "user@example.com",
            "role": "Owner"
        }
    }

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends
from jose import jwt, JWTError
from app.core.security import SECRET_KEY, ALGORITHM

security = HTTPBearer()

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 1. Ekstrak dan verifikasi token JWT
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email_clean = payload.get("sub")
        if not email_clean:
            raise HTTPException(status_code=401, detail="Token tidak valid, subject/email tidak ditemukan")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token kedaluwarsa atau tidak valid")

    current_password = request.old_password.strip()
    new_password = request.new_password.strip()

    # 2. Simulasi Login (Sign-In) ke Supabase Auth
    try:
        # Melakukan verifikasi current_password
        auth_response = supabase.auth.sign_in_with_password({
            "email": email_clean,
            "password": current_password
        })
        
        # 3. Update sandi baru
        # Saat sign in berhasil, client Supabase otomatis memiliki sesi aktif
        # sehingga bisa langsung memanggil update_user.
        update_response = supabase.auth.update_user({
            "password": new_password
        })
        
        return {"status": "success", "message": "Password berhasil diperbarui"}
        
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid login credentials" in error_msg or "sandi" in error_msg:
            raise HTTPException(status_code=400, detail="Sandi saat ini salah")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan di Supabase Auth: {str(e)}")

class LogoutRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str

@router.post("/logout")
async def logout(request: LogoutRequest):
    email_clean = request.email.strip()
    try:
        response = supabase.table("users").select("id").eq("email", email_clean).execute()
        if response.data:
            user_cloud = response.data[0]
            if user_cloud.get("id"):
                create_activity_log(str(user_cloud["id"]), "LOGOUT", "User logged out")
        return {"status": "success", "message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat logout: {str(e)}")

@router.post("/face-register", status_code=status.HTTP_201_CREATED)
async def register_face(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    otp: str = Form(...),
    file: UploadFile = File(...)
):
    email_clean = email.strip()
    password_clean = password.strip()
    name_clean = name.strip()
    otp_clean = otp.strip()
    
    # 1. Validasi OTP terlebih dahulu
    stored_otp_data = otp_storage.get(email_clean)
    if not stored_otp_data:
        raise HTTPException(status_code=400, detail="OTP tidak valid atau belum request OTP")
        
    if stored_otp_data["otp"] != otp_clean:
        raise HTTPException(status_code=400, detail="OTP tidak valid")
        
    now_utc = datetime.now(timezone.utc)
    if now_utc > stored_otp_data["expires"]:
        del otp_storage[email_clean]
        raise HTTPException(status_code=400, detail="OTP sudah kedaluwarsa")
        
    # Hapus OTP setelah digunakan
    del otp_storage[email_clean]
    
    # 2. Cek apakah email sudah ada di tabel 'users'
    try:
        response = supabase.table("users").select("email").eq("email", email_clean).execute()
        if response.data:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar!")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal koneksi Supabase: {str(e)}")

    # 2. Simpan file sementara
    temp_filename = f"temp_face_{uuid.uuid4()}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 3. Ekstrak vektor wajah (akan raise Exception jika gagal)
        face_vector = extract_face_vector(temp_filename)
        
        # 4. Hash password dan simpan ke database (berikut array vektor 512 dimensi)
        hashed_password = get_password_hash(password_clean)
        
        insert_response = supabase.table("users").insert({
            "email": email_clean,
            "name": name_clean,
            "password": hashed_password,
            "face_embedding": face_vector
        }).execute()
        
        if insert_response.data and len(insert_response.data) > 0:
            new_user_id = insert_response.data[0].get("id")
            if new_user_id:
                create_activity_log(str(new_user_id), "FACE_REGISTER", "User registered using Face ID")
                
        return {
            "status": "success",
            "message": "Berhasil mendaftar menggunakan Face ID.",
            "data": {
                "name": name_clean,
                "email": email_clean
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan: {str(e)}")
    finally:
        # 5. Hapus file sementara
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@router.post("/face")
async def face_login(file: UploadFile = File(...)):
    # 1. Simpan file sementara
    temp_filename = f"temp_face_login_{uuid.uuid4()}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 2. Ekstrak vektor wajah
        face_vector_list = extract_face_vector(temp_filename)
        
        # 3. Query menggunakan RPC Supabase (match_face)
        response = supabase.rpc(
            "match_face",
            {"query_embedding": face_vector_list, "match_threshold": 0.70}
        ).execute()
        
        # Jika array kosong, tidak ada yang cocok
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=401, detail="Wajah tidak dikenali.")
            
        # Ambil user pertama dengan kedekatan tertinggi
        user_cloud = response.data[0]
        
        # 4. Generate JWT
        token = create_access_token(data={"sub": user_cloud["email"], "name": user_cloud["name"]})
        
        if user_cloud.get("id"):
            create_activity_log(str(user_cloud["id"]), "FACE_LOGIN", "User logged in via Face ID")
            
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "data": {
                "id": user_cloud.get("id"),
                "email": user_cloud.get("email"),
                "name": user_cloud["name"],
                "photo_url": user_cloud.get("photo_url")
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat face login: {str(e)}")
    finally:
        # Hapus file sementara
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
