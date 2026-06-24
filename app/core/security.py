from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt

# Menggunakan Bcrypt dengan skema standar industri (Sesuai Matkul Keamanan Data)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Konfigurasi JWT (Sesuai Matkul Web Service)
SECRET_KEY = "SUPER_SECRET_KEY_CAPSTONE_SME_JWT_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi apakah password murni cocok dengan hash Bcrypt di DB"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Mengubah password murni menjadi hash Bcrypt panjang ($2b$12...)"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Membuat enkripsi JWT Token untuk sesi Login Flutter"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt