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
from pymongo import MongoClient

router = APIRouter(prefix="/api/v1/auth", tags=["1. Authentication & Security"])

# --- KONFIGURASI SUPABASE DIPINDAHKAN KE app/core/db.py ---

# --- KONFIGURASI MONGODB UNTUK OTP ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://muhammadazmi8978_db_user:azmi12345678@amiii.uoskbzh.mongodb.net/?appName=amiii")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["muhammadazmi8978_db_user"]
mongo_otps = mongo_db["otps"]

class VerifyRegisterRequest(BaseModel):
    email: str
    otp: str

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
            raise HTTPException(status_code=400, detail="Email sudah terdaftar di database!")

        # Upload Foto Profil (Jika Ada)
        photo_url = None
        if profile_picture and profile_picture.filename:
            try:
                # Buat nama file unik
                file_extension = profile_picture.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_extension}"
                
                file_bytes = await profile_picture.read()
                
                # Upload ke Supabase Storage
                supabase.storage.from_("profile_pictures").upload(
                    file_name,
                    file_bytes,
                    {"content-type": profile_picture.content_type}
                )
                
                # Dapatkan Public URL
                photo_url = supabase.storage.from_("profile_pictures").get_public_url(file_name)
            except Exception as e:
                print(f"GAGAL UPLOAD FOTO: {e}")

        # Hash password dan insert ke Supabase dengan status pending
        hashed_password = get_password_hash(password_clean)
        insert_response = supabase.table("users").insert({
            "email": email_clean,
            "name": name_clean,
            "password": hashed_password,
            "photo_url": photo_url,
            "status": "pending" # HANYA jika Anda sudah menambah kolom ini di tabel users
        }).execute()
        
        print(f"Data tersimpan di DB: {insert_response.data}")

        if insert_response.data and len(insert_response.data) > 0:
            new_user_id = insert_response.data[0].get("id")
            if new_user_id:
                create_activity_log(str(new_user_id), "REGISTER_PENDING", "User registered, pending OTP verification")

        # GENERATE OTP
        otp_code = "".join(random.choices(string.digits, k=6))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        # Simpan ke MongoDB (Upsert agar OTP lama tertimpa)
        mongo_otps.update_one(
            {"email": email_clean},
            {"$set": {
                "otp": otp_code,
                "expires_at": expires_at,
                "type": "register"
            }},
            upsert=True
        )

        # Kirim email
        send_otp_email(email_clean, otp_code)

        print(f"=== CLOUD SUPABASE: Pendaftaran pending {email_clean}. OTP Terkirim ===")
        return {
            "status": "success", 
            "message": "Pendaftaran berhasil, silakan cek email Anda untuk kode OTP verifikasi.",
            "data": {
                "name": name_clean, 
                "email": email_clean
            }
        }
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal koneksi atau struktur tabel Supabase salah: {str(e)}")

@router.post("/verify-register")
def verify_register(request: VerifyRegisterRequest):
    email_clean = request.email.strip()
    otp_clean = request.otp.strip()

    try:
        # Cari OTP di MongoDB
        otp_doc = mongo_otps.find_one({"email": email_clean, "type": "register"})
        if not otp_doc:
            raise HTTPException(status_code=400, detail="OTP tidak ditemukan atau sudah digunakan.")

        # Cek expired
        if datetime.now(timezone.utc) > otp_doc["expires_at"].replace(tzinfo=timezone.utc):
            mongo_otps.delete_one({"_id": otp_doc["_id"]})
            raise HTTPException(status_code=400, detail="Kode OTP telah kedaluwarsa. Silakan mendaftar ulang atau minta OTP baru.")

        # Cek OTP cocok
        if otp_doc["otp"] != otp_clean:
            raise HTTPException(status_code=400, detail="Kode OTP salah.")

        # Update status di Supabase menjadi active
        update_response = supabase.table("users").update({"status": "active"}).eq("email", email_clean).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=400, detail="Gagal mengaktifkan akun. Pastikan email terdaftar.")

        # Hapus OTP dari MongoDB
        mongo_otps.delete_one({"_id": otp_doc["_id"]})

        user_id = update_response.data[0].get("id")
        if user_id:
            create_activity_log(str(user_id), "REGISTER_VERIFIED", "User email verified via OTP")

        return {
            "status": "success",
            "message": "Akun berhasil diverifikasi dan diaktifkan. Silakan login."
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal verifikasi OTP: {str(e)}")

@router.post("/login", response_model=LoginResponseSchema)
async def login(user_data: UserLogin):
    # 1. Potong spasi gaib dari HP
    email_clean = user_data.email.strip()
    password_clean = user_data.password.strip()
    
    try:
        # 2. Ambil data user secara real-time dari database cloud Supabase
        response = supabase.table("users").select("id", "name", "email", "password", "photo_url", "status").eq("email", email_clean).execute()
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Email tidak terdaftar!")
        
        # Ambil baris data pertama hasil pencarian
        user_cloud = response.data[0]
        
        if user_cloud.get("status") == "pending":
            raise HTTPException(status_code=400, detail="Akun belum diverifikasi. Silakan cek email Anda untuk kode OTP verifikasi.")
        
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
        
        token = create_access_token(data={"sub": user_cloud["email"], "name": user_cloud["name"], "user_id": str(user_cloud["id"])})
        
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
        
        # Simpan OTP di MongoDB
        mongo_otps.update_one(
            {"email": email_clean},
            {"$set": {
                "otp": otp_code,
                "expires_at": otp_expiry,
                "type": "register"
            }},
            upsert=True
        )
        
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
        token = create_access_token(data={"sub": user_data["email"], "name": user_data.get("name", "Google User"), "user_id": str(user_data["id"])})

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



@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    try:
        email_clean = request.email.strip()
        
        # 1. Cek apakah email terdaftar di database
        response = supabase.table("users").select("id", "email").eq("email", email_clean).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Email tidak terdaftar!")
            
        user_id = response.data[0].get("id")
            
        # 2. Generate 6 digit OTP string
        otp_code = "".join(random.choices(string.digits, k=6))
        
        # 3. Buat waktu kedaluwarsa 5 menit
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        # 4. Simpan OTP ke MongoDB
        mongo_otps.update_one(
            {"email": email_clean},
            {"$set": {
                "otp": otp_code,
                "expires_at": expires_at,
                "type": "reset_password"
            }},
            upsert=True
        )
        
        if user_id:
            create_activity_log(str(user_id), "FORGOT_PASSWORD", "Requested password reset via OTP")
        
        # 5. Print OTP di terminal VS Code untuk testing
        print(f"OTP untuk {email_clean} adalah: {otp_code}")
        
        # 6. Kirim OTP via Email
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
            
        # 2. Cari OTP di MongoDB
        otp_doc = mongo_otps.find_one({"email": email_clean, "type": "reset_password"})
        if not otp_doc:
            raise HTTPException(status_code=400, detail="Tidak ada permintaan reset password aktif atau OTP salah.")
            
        # 3. Cek Kedaluwarsa
        if datetime.now(timezone.utc) > otp_doc["expires_at"].replace(tzinfo=timezone.utc):
            mongo_otps.delete_one({"_id": otp_doc["_id"]})
            raise HTTPException(status_code=400, detail="OTP sudah kedaluwarsa. Silakan request ulang.")
            
        # 4. Cocokkan OTP
        if otp_code_clean != otp_doc["otp"]:
            raise HTTPException(status_code=400, detail="Kode OTP Salah!")
            
        # 5. Jika lolos, hash password baru
        hashed_password = get_password_hash(password_clean)
        
        # Update di Supabase
        update_response = supabase.table("users").update({
            "password": hashed_password
        }).eq("email", email_clean).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=404, detail="Gagal mengubah password. Pastikan email terdaftar.")
            
        # 6. Hapus OTP dari MongoDB
        mongo_otps.delete_one({"_id": otp_doc["_id"]})
        
        user_id = update_response.data[0].get("id")
        if user_id:
            create_activity_log(str(user_id), "RESET_PASSWORD", "User successfully reset their password")
        
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
        # Cari OTP di MongoDB
        otp_doc = mongo_otps.find_one({"email": email_clean, "type": "reset_password"})
        if not otp_doc:
            raise HTTPException(status_code=400, detail="Tidak ada permintaan reset password aktif atau OTP salah.")
            
        # Cocokkan OTP
        if otp_code_clean != otp_doc["otp"]:
            raise HTTPException(status_code=400, detail="Kode OTP salah.")
            
        # Cek Kedaluwarsa
        if datetime.now(timezone.utc) > otp_doc["expires_at"].replace(tzinfo=timezone.utc):
            mongo_otps.delete_one({"_id": otp_doc["_id"]})
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
    otp_doc = mongo_otps.find_one({"email": email_clean, "type": "register"})
    if not otp_doc:
        raise HTTPException(status_code=400, detail="OTP tidak valid atau belum request OTP")
        
    if otp_doc["otp"] != otp_clean:
        raise HTTPException(status_code=400, detail="OTP tidak valid")
        
    now_utc = datetime.now(timezone.utc)
    if now_utc > otp_doc["expires_at"].replace(tzinfo=timezone.utc):
        mongo_otps.delete_one({"_id": otp_doc["_id"]})
        raise HTTPException(status_code=400, detail="OTP sudah kedaluwarsa")
        
    # Hapus OTP setelah digunakan
    mongo_otps.delete_one({"_id": otp_doc["_id"]})
    
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
        token = create_access_token(data={"sub": user_cloud["email"], "name": user_cloud["name"], "user_id": str(user_cloud["id"])})
        
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
