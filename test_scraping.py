import os
from pymongo import MongoClient
import random

# Koneksi ke MongoDB (Sesuaikan dengan URI Anda di scraper.py)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://muhammadazmi8978_db_user:azmi12345678@amiii.uoskbzh.mongodb.net/?appName=amiii")
client = MongoClient(MONGO_URI)
db = client["muhammadazmi8978_db_user"]

collection_trend = db["Fashion_Trends"]
collection_rekomendasi = db["Price_Recommendations"]

def insert_dummy_trends():
    print("Menghapus data tren lama...")
    collection_trend.delete_many({})
    
    months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni"]
    categories = ["Boxy Fit", "Fitted", "Oversize", "Regular Fit"]
    
    dummy_data = []
    
    # Generate data untuk tiap bulan dan kategori
    for month in months:
        for category in categories:
            # Random harga antara 100k - 300k
            base_price = random.randint(120, 280) * 1000
            
            dummy_data.append({
                "date": month,
                "category": category,
                "price": base_price
            })
            
    if dummy_data:
        print(f"Menambahkan {len(dummy_data)} data tren harga baru...")
        collection_trend.insert_many(dummy_data)
        print("Data tren harga berhasil ditambahkan!")

def insert_dummy_recommendation():
    print("Menghapus data rekomendasi lama...")
    collection_rekomendasi.delete_many({})
    
    dummy_rekomendasi = {
        "kategori": "Boxy Fit",
        "rekomendasi_harga": 185000,
        "status": "Sedang Tren",
        "gambar": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=500&q=60"
    }
    
    print("Menambahkan data rekomendasi terbaru...")
    collection_rekomendasi.insert_one(dummy_rekomendasi)
    print("Data rekomendasi berhasil ditambahkan!")

if __name__ == "__main__":
    print("Memulai simulasi scraping (Seed Dummy Data)...")
    try:
        insert_dummy_trends()
        insert_dummy_recommendation()
        print("Semua data dummy berhasil dimasukkan ke MongoDB!")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
