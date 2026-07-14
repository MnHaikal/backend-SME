from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.routes.auth import supabase
from app.utils.logger import create_activity_log
from app.core.security import get_current_user_id
import os
from pymongo import MongoClient
from datetime import datetime, timezone

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://muhammadazmi8978_db_user:azmi12345678@amiii.uoskbzh.mongodb.net/?appName=amiii")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["muhammadazmi8978_db_user"]
mongo_transactions = mongo_db["inventory_logs"]

router = APIRouter(
    prefix="/api/v1/scan",
    tags=["Scanner"]
)

class ScanInSchema(BaseModel):
    sku: str
    name: str
    category: str
    qty: int
    status: str
    image_url: str
    user_id: Optional[str] = None

class ScanOutSchema(BaseModel):
    sku: str
    qty_keluar: int
    user_id: Optional[str] = None

@router.post("/in")
def scan_in(data: ScanInSchema, current_user_id: str = Depends(get_current_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        # Menyiapkan payload MongoDB log
        mongo_log = {
            "user_id": current_user_id,
            "sku": data.sku,
            "name": data.name,
            "category": data.category,
            "qty": data.qty,
            "type": "IN",
            "scan_type": "in",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        # Cek apakah sku sudah ada untuk user ini
        check_response = supabase.table("inventory").select("*").eq("sku", data.sku).eq("user_id", current_user_id).execute()
        
        if check_response.data and len(check_response.data) > 0:
            # SKU ada, tambahkan qty
            existing_product = check_response.data[0]
            new_qty = existing_product["qty"] + data.qty
            
            update_response = supabase.table("inventory").update({"qty": new_qty}).eq("sku", data.sku).eq("user_id", current_user_id).execute()
            if update_response.data:
                # Insert log ke MongoDB
                mongo_transactions.insert_one(mongo_log)
                
                if current_user_id:
                    create_activity_log(current_user_id, "SCAN_IN", f"Scanned in product: {data.name}")
                return {
                    "message": "Stok berhasil ditambahkan",
                    "data": update_response.data[0]
                }
            raise HTTPException(status_code=400, detail="Gagal mengupdate stok produk")
        else:
            # SKU tidak ada, buat produk baru
            new_product = {
                "sku": data.sku,
                "name": data.name,
                "category": data.category,
                "qty": data.qty,
                "status": data.status,
                "image_url": data.image_url,
                "user_id": current_user_id
            }
            insert_response = supabase.table("inventory").insert(new_product).execute()
            if insert_response.data:
                # Insert log ke MongoDB
                mongo_transactions.insert_one(mongo_log)
                
                if current_user_id:
                    create_activity_log(current_user_id, "SCAN_IN", f"Scanned in product: {data.name}")
                return {
                    "message": "Produk baru berhasil ditambahkan",
                    "data": insert_response.data[0]
                }
            raise HTTPException(status_code=400, detail="Gagal menambahkan produk baru")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error Scan In: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal: {str(e)}")


@router.post("/out")
def scan_out(data: ScanOutSchema, current_user_id: str = Depends(get_current_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        # Cek apakah sku ada untuk user ini
        check_response = supabase.table("inventory").select("*").eq("sku", data.sku).eq("user_id", current_user_id).execute()
        
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(status_code=404, detail="Produk dengan SKU tersebut tidak ditemukan")
            
        existing_product = check_response.data[0]
        current_qty = existing_product["qty"]
        
        if current_qty < data.qty_keluar:
            raise HTTPException(status_code=400, detail="Stok tidak mencukupi untuk jumlah keluar yang diminta")
            
        new_qty = current_qty - data.qty_keluar
        update_response = supabase.table("inventory").update({"qty": new_qty}).eq("sku", data.sku).eq("user_id", current_user_id).execute()
        
        if update_response.data:
            # Insert log ke MongoDB
            mongo_log = {
                "user_id": current_user_id,
                "sku": data.sku,
                "name": existing_product.get("name", "Unknown"),
                "category": existing_product.get("category", "Uncategorized"),
                "qty": data.qty_keluar,
                "type": "OUT",
                "scan_type": "out",
                "harga_jual": existing_product.get("selling_price", 0),
                "total_harga": existing_product.get("selling_price", 0) * data.qty_keluar,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            mongo_transactions.insert_one(mongo_log)
            
            if current_user_id:
                product_name = existing_product.get("name", data.sku)
                create_activity_log(current_user_id, "SCAN_OUT", f"Scanned out product: {product_name}")
            return {
                "message": "Stok berhasil dikurangi",
                "data": update_response.data[0]
            }
        raise HTTPException(status_code=400, detail="Gagal mengupdate stok produk")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error Scan Out: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal: {str(e)}")

@router.post("/result")
def scan_result(data: ScanInSchema):
    # Dummy endpoint for standardization requirement
    print("\n" + "="*50)
    print(f"🚀 [LOG] Flutter mengakses halaman Scan (POST /result) (SKU: {data.sku})")
    print("="*50 + "\n")
    return {
        "status": "success",
        "message": "Hasil scan berhasil diterima",
        "data": data.model_dump()
    }
