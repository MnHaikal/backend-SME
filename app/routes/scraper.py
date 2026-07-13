from fastapi import APIRouter, HTTPException, Query
from pymongo import MongoClient
from bson import ObjectId
from typing import List, Dict, Any
import os

router = APIRouter(prefix="/api/harga", tags=["Scraping - Tren & Rekomendasi Harga"])

# 1. Koneksi ke MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["Capstone_SME"] # Ganti dengan nama database Anda

# Definisikan kedua collection Anda di sini
collection_trend = db["Fashion_Trends"]         # Ganti dengan nama collection trend Anda
collection_rekomendasi = db["Price_Recommendations"]  # Ganti dengan nama collection rekomendasi Anda

# Helper untuk merapikan format data MongoDB agar bisa dibaca JSON frontend
def clean_data(item) -> dict:
    if item:
        item["id"] = str(item["_id"])
        if "_id" in item:
            del item["_id"]
    return item

# ==================== ENDPOINT 1: TREND HARGA ====================
@router.get("/trend", response_model=List[Dict[str, Any]])
def get_trend_harga(
    limit: int = Query(30, ge=1, le=100) # Default 30 data terakhir (misal untuk grafik sebulan)
):
    """
    Endpoint untuk mengambil data tren harga historis hasil scraping.
    Data diurutkan dari yang paling baru dimasukkan oleh GitHub Actions.
    """
    try:
        # Mengambil data terbaru berdasarkan _id mongo
        cursor = collection_trend.find().sort("_id", -1).limit(limit)
        return [clean_data(doc) for doc in cursor]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil data tren: {str(e)}")


# ==================== ENDPOINT 2: REKOMENDASI HARGA ====================
@router.get("/rekomendasi", response_model=List[Dict[str, Any]])
def get_rekomendasi_harga():
    """
    Endpoint untuk mengambil data rekomendasi harga terbaru dari MASING-MASING KATEGORI.
    """
    try:
        # Pipeline Agregasi MongoDB untuk mengambil 1 data terbaru dari setiap kategori
        pipeline = [
            {"$sort": {"_id": -1}}, # Urutkan dari yang paling baru
            {"$group": {
                "_id": "$kategori",
                "latest_data": {"$first": "$$ROOT"} # Ambil data pertama (terbaru) per kategori
            }},
            {"$replaceRoot": {"newRoot": "$latest_data"}} # Keluarkan data dari grouping agar formatnya rata
        ]
        
        cursor = collection_rekomendasi.aggregate(pipeline)
        hasil = [clean_data(doc) for doc in cursor]
        
        if not hasil:
            raise HTTPException(status_code=404, detail="Data rekomendasi belum tersedia")
            
        print(f"Total data dikirim: {len(hasil)}")
        print(f"Kategori yang ditemukan: {[d.get('kategori') for d in hasil]}")
        return hasil
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil data rekomendasi: {str(e)}")

# ==================== ENDPOINT 3: CEK KATEGORI ====================
@router.get("/cek-kategori")
def cek_kategori():
    """
    Endpoint bantuan sementara untuk mengecek kategori unik di database.
    """
    try:
        return collection_rekomendasi.distinct("kategori")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengecek kategori: {str(e)}")