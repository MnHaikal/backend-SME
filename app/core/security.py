from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
import os

# Menggunakan Bcrypt dengan skema standar industri (Sesuai Matkul Keamanan Data)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Konfigurasi JWT (Sesuai Matkul Web Service) - dibaca dari environment variable
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

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

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

def get_current_user_id(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    """Mengekstrak user_id dari token JWT, atau Header/Query param untuk Multi-Tenancy"""
    if credentials and credentials.credentials:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
            if user_id:
                return user_id
        except JWTError:
            pass
            
    # Fallback to headers
    header_user_id = request.headers.get("user_id") or request.headers.get("user-id")
    if header_user_id:
        return header_user_id
        
    # Fallback to query param
    query_user_id = request.query_params.get("user_id")
    if query_user_id:
        return query_user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )

security_optional = HTTPBearer(auto_error=False)

def get_optional_current_user_id(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)) -> Optional[str]:
    """Mengekstrak user_id dari token JWT, atau Header/Query, tidak error jika kosong"""
    
    print("\n--- DEBUG GET REQUEST ---")
    print(f"URL: {request.url}")
    print(f"Headers: {request.headers}")
    print(f"Query Params: {request.query_params}")
    if credentials:
        print(f"Token present: {credentials.credentials[:10]}...")
    else:
        print("No Authorization token found.")
    print("-------------------------\n")

    if credentials and credentials.credentials:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
            if user_id:
                return user_id
        except JWTError as e:
            print(f"JWT Decode Error: {e}")
            pass
            
    # Fallback to headers
    header_user_id = request.headers.get("user_id") or request.headers.get("user-id")
    if header_user_id:
        return header_user_id
        
    # Fallback to query param
    query_user_id = request.query_params.get("user_id")
    if query_user_id:
        return query_user_id
        
    return None