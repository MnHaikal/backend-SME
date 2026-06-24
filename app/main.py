from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import json
from app.routes import auth, inventory, market, inventory_router, scan_router

# PASTIKAN BARIS INI TERTULIS DENGAN BENAR (HURUF KECIL):
app = FastAPI(
    title="Smart-SME Infrastructure AI API",
    description="Backend Server Penunjang Tiga Matkul Utama Capstone Proyek",
    version="2.0.0"
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        raw_body = await request.body()
        raw_body_str = raw_body.decode("utf-8")
    except Exception as e:
        raw_body_str = f"Gagal membaca raw body: {str(e)}"
        
    print("\n" + "="*60)
    print("❌ ERROR 422 - UNPROCESSABLE ENTITY")
    print(f"Request URL: {request.url}")
    print(f"\n(A) RAW JSON DARI FLUTTER:\n{raw_body_str}")
    
    print("\n(B) DETAIL ARRAY ERROR PYDANTIC:")
    for err in exc.errors():
        print(f"  - loc : {err.get('loc')}")
        print(f"  - msg : {err.get('msg')}")
        print(f"  - type: {err.get('type')}")
    print("="*60 + "\n")

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

# --- MATKUL KEAMANAN JARINGAN: CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "ngrok-skip-browser-warning"],
)

# Registrasi Modul Endpoint (Matkul: Web Service)
app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(inventory_router.router)
app.include_router(scan_router.router)
app.include_router(market.router)

@app.get("/", tags=["Root"])
async def root():
    return {
        "status": "Online",
        "framework": "FastAPI Python",
        "message": "Web Service & AI Engine is running smoothly."
    }