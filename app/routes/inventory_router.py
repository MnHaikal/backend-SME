from fastapi import APIRouter, HTTPException, Depends, Form, File, UploadFile
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import uuid
from app.core.security import get_current_user_id
from pydantic import BaseModel
from typing import Optional, List
import os
from supabase import create_client, Client
from pymongo import MongoClient

# Setup MongoDB Connection untuk Analytics / Sales Performance
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://muhammadazmi8978_db_user:azmi12345678@amiii.uoskbzh.mongodb.net/?appName=amiii")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["muhammadazmi8978_db_user"]
mongo_transactions = mongo_db["inventory_logs"] # Sesuaikan dengan nama collection log transaksi Anda

router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["Products"]
)

# Gunakan instance supabase yang sudah diinisialisasi di auth.py
from app.routes.auth import supabase
from app.utils.logger import create_activity_log

class ProductSchema(BaseModel):
    id: Optional[int] = None
    sku: str
    name: Optional[str] = "Produk Tanpa Nama"
    category: Optional[str] = "Uncategorized"
    qty: int
    status: str
    image_url: Optional[str] = None
    user_id: Optional[str] = None



@router.get("", response_model=List[ProductSchema])
def get_products(current_user_id: str = Depends(get_current_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        response = supabase.table("inventory").select("*").eq("user_id", current_user_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.put("/{id}", response_model=ProductSchema)
def update_product(id: int, product: ProductSchema, current_user_id: str = Depends(get_current_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        product_dict = product.model_dump(exclude_none=True)
        user_id = product_dict.pop("user_id", None)
        response = supabase.table("inventory").update(product_dict).eq("id", id).eq("user_id", current_user_id).execute()
        if response.data:
            if user_id:
                print("Merekam log edit produk...")
                create_activity_log(user_id, "EDIT_PRODUCT", f"Updated product: {product.name}")
            return response.data[0]
        raise HTTPException(status_code=404, detail="Product not found or update failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
def delete_product(id: int, current_user_id: str = Depends(get_current_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        response = supabase.table("inventory").delete().eq("id", id).eq("user_id", current_user_id).execute()
        if response.data:
            return {"message": "Product deleted successfully"}
        raise HTTPException(status_code=404, detail="Product not found or delete failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add")
async def add_inventory(
    sku: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    size: str = Form(...),
    color: str = Form(...),
    price: int = Form(...),
    qty: int = Form(...),
    product_image: UploadFile = File(None),
    current_user_id: str = Depends(get_current_user_id)
):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
        
    image_url = None
    if product_image and product_image.filename:
        try:
            file_extension = product_image.filename.split(".")[-1]
            file_name = f"{uuid.uuid4()}.{file_extension}"
            
            file_bytes = await product_image.read()
            
            # Upload ke Supabase
            supabase.storage.from_("inventory_images").upload(
                file_name, 
                file_bytes, 
                {"content-type": product_image.content_type}
            )
            
            # Dapatkan URL
            image_url = supabase.storage.from_("inventory_images").get_public_url(file_name)
        except Exception as e:
            print(f"GAGAL UPLOAD FOTO PRODUK: {e}")
            
    try:
        data_insert = {
            "sku": sku.strip(),
            "name": name.strip(),
            "category": category.strip(),
            "size": size.strip(),
            "color": color.strip(),
            "price": price,
            "qty": qty,
            "status": "NORMAL",
            "image_url": image_url,
            "user_id": current_user_id
        }
        
        response = supabase.table("inventory").insert(data_insert).execute()
        
        return {
            "status": "success", 
            "message": "Barang berhasil ditambahkan", 
            "data": response.data[0] if response.data else data_insert
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan ke database: {str(e)}")

@router.post("/scan")
async def scan_inventory(
    sku: str = Form(...),
    scan_type: str = Form(...),
    qty: int = Form(...),
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    size: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    price: Optional[int] = Form(None),
    product_image: UploadFile = File(None),
    current_user_id: str = Depends(get_current_user_id)
):
    payload_variabel_kamu = {
        "sku": sku,
        "scan_type": scan_type,
        "qty": qty,
        "name": name,
        "category": category,
        "size": size,
        "color": color,
        "price": price
    }
    
    try:
        print(f"Data masuk dari Frontend: {payload_variabel_kamu}")
        
        scan_type_clean = scan_type.strip().lower()
        sku_clean = sku.strip()
        
        if scan_type_clean not in ['in', 'out']:
            return JSONResponse(status_code=400, content={"status": "error", "message": "scan_type harus 'in' atau 'out'"})
            
        # Cek Database
        response = supabase.table("inventory").select("*").eq("sku", sku_clean).eq("user_id", current_user_id).execute()
        
        # LOGIKA JIKA BARANG SUDAH ADA
        if response.data:
            barang_lama = response.data[0]
            stok_lama = barang_lama.get("qty", 0)
            
            if scan_type_clean == 'in':
                qty_baru = stok_lama + qty
                print(f"Scan In: Update qty dari {stok_lama} menjadi {qty_baru}")
            else: # scan_type == 'out'
                if stok_lama < qty:
                    return JSONResponse(status_code=400, content={"status": "error", "message": "Gagal: Stok tidak mencukupi"})
                qty_baru = stok_lama - qty
                print(f"Scan Out: Update qty dari {stok_lama} menjadi {qty_baru}")
                
            # Lakukan Update Database
            update_data = {
                "qty": qty_baru,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            # Eksekusi Update
            supabase.table("inventory").update(update_data).eq("sku", sku_clean).eq("user_id", current_user_id).execute()
            
            # Ambil data terbaru untuk dikembalikan
            barang_lama["qty"] = qty_baru
            barang_lama["last_updated"] = update_data["last_updated"]
            
            return {
                "status": "success",
                "message": f"Berhasil scan {scan_type_clean}",
                "data": barang_lama
            }
            
        # LOGIKA JIKA BARANG BELUM ADA (Baru)
        else:
            if scan_type_clean == 'out':
                return JSONResponse(status_code=404, content={"status": "error", "message": "Barang tidak ditemukan di gudang"})
                
            # Jika scan_type == 'in', insert barang baru
            print("Barang baru terdeteksi, mencoba insert ke database...")
            
            image_url = None
            if product_image and product_image.filename:
                try:
                    file_extension = product_image.filename.split(".")[-1]
                    file_name = f"{uuid.uuid4()}.{file_extension}"
                    
                    file_bytes = await product_image.read()
                    
                    supabase.storage.from_("inventory_images").upload(
                        file_name,
                        file_bytes,
                        {"content-type": product_image.content_type}
                    )
                    image_url = supabase.storage.from_("inventory_images").get_public_url(file_name)
                    print(f"Berhasil upload foto produk, URL: {image_url}")
                except Exception as e:
                    print(f"Error Upload: {e}")
            
            data_insert = {
                "sku": sku_clean,
                "name": name.strip() if name else "Produk Tanpa Nama",
                "category": category.strip() if category else "Uncategorized",
                "size": size.strip() if size else "-",
                "color": color.strip() if color else "-",
                "price": price if price else 0,
                "qty": qty,
                "status": "NORMAL",
                "image_url": image_url,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "user_id": current_user_id
            }
            
            supabase.table("inventory").insert(data_insert).execute()
            
            return {
                "status": "success",
                "message": "Barang baru berhasil ditambahkan",
                "data": data_insert
            }
            
    except Exception as e:
        print(f"ERROR DATABASE/SERVER: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/sales-performance")
def get_sales_performance(current_user_id: str = Depends(get_current_user_id)):
    """
    Endpoint untuk menghitung total omzet (uang masuk) dari barang yang di-Scan Out setiap bulannya.
    Menggunakan Aggregation Pipeline MongoDB.
    """
    try:
        pipeline = [
            # 0. Filter khusus user ini
            {
                "$match": { "user_id": current_user_id }
            },
            # 1. Filter HANYA pada transaksi barang keluar (penjualan)
            # Sesuaikan "type" atau "scan_type" dengan field di document MongoDB Anda
            {
                "$match": {
                    "$or": [
                        {"type": "OUT"},
                        {"scan_type": "out"}
                    ]
                }
            },
            # 2. Fix tipe data (String ke Date, dan String ke Angka)
            {
                "$addFields": {
                    "parsed_date": {
                        "$convert": {
                            "input": { "$ifNull": ["$timestamp", "$created_at"] },
                            "to": "date",
                            "onError": None,
                            "onNull": None
                        }
                    },
                    "parsed_qty": {
                        "$convert": { "input": "$qty", "to": "double", "onError": 0, "onNull": 0 }
                    },
                    "parsed_harga_jual": {
                        "$convert": { "input": { "$ifNull": ["$harga_jual", "$selling_price"] }, "to": "double", "onError": 0, "onNull": 0 }
                    },
                    "parsed_total_harga": {
                        "$convert": { "input": "$total_harga", "to": "double", "onError": 0, "onNull": 0 }
                    }
                }
            },
            # Buang document yang tanggalnya tidak bisa diparsing
            {
                "$match": { "parsed_date": { "$ne": None } }
            },
            # 3. Group berdasarkan bulan dan tahun dari tanggal transaksi, lalu Sum total omzet
            {
                "$group": {
                    "_id": {
                        "month": {"$month": "$parsed_date"},
                        "year": {"$year": "$parsed_date"}
                    },
                    "total_revenue": {
                        "$sum": {
                            "$cond": [
                                {"$gt": ["$parsed_total_harga", 0]},
                                "$parsed_total_harga",
                                {"$multiply": ["$parsed_qty", "$parsed_harga_jual"]}
                            ]
                        }
                    }
                }
            },
            # 3. Urutkan hasilnya dari bulan paling lama ke bulan terbaru
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1
                }
            },
            # 4. Format hasil kembalian (Project) agar menjadi array JSON rata
            {
                "$project": {
                    "_id": 0,
                    "month": "$_id.month",
                    "year": "$_id.year",
                    "total_revenue": 1
                }
            }
        ]

        # Eksekusi pipeline di MongoDB
        cursor = mongo_transactions.aggregate(pipeline)
        result = list(cursor)
        
        print(f"🚀 [LOG] /sales-performance result: {result}")

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        print(f"Error fetching sales performance: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal mengambil performa penjualan: {str(e)}")


@router.get("/monthly-profit")
def get_monthly_profit(current_user_id: str = Depends(get_current_user_id)):
    """
    Endpoint untuk menghitung grafik 'Performa Penjualan Bulanan' / Monthly Profit.
    Logika Profit meniru perhitungan sistem saat ini: (harga_jual - harga_beli) * qty
    Menggunakan Aggregation Pipeline MongoDB.
    """
    try:
        pipeline = [
            # 0. Filter khusus user ini
            {
                "$match": { "user_id": current_user_id }
            },
            # 1. Filter HANYA pada transaksi barang keluar (penjualan)
            {
                "$match": {
                    "$or": [
                        {"type": "OUT"},
                        {"scan_type": "out"}
                    ]
                }
            },
            # 2. Lookup ke koleksi produk/inventory untuk mengambil harga jika tidak ada di log
            {
                "$lookup": {
                    "from": "inventory", # Nama koleksi produk di MongoDB
                    "localField": "sku",
                    "foreignField": "sku",
                    "as": "product_info"
                }
            },
            {
                "$unwind": {
                    "path": "$product_info",
                    "preserveNullAndEmptyArrays": True
                }
            },
            # 3. Fix tipe data (String ke Date, dan String ke Angka) beserta Fallback Harga
            {
                "$addFields": {
                    "parsed_date": {
                        "$dateFromString": {
                            "dateString": { "$ifNull": ["$timestamp", "$created_at", "$createdAt"] },
                            "onError": None,
                            "onNull": None
                        }
                    },
                    "parsed_qty": {
                        "$convert": { "input": "$qty", "to": "double", "onError": 0, "onNull": 0 }
                    },
                    "parsed_harga_jual": {
                        "$convert": { 
                            "input": { 
                                "$ifNull": [
                                    "$harga_jual", 
                                    "$selling_price", 
                                    "$product_info.selling_price",
                                    "$product_info.harga_jual"
                                ] 
                            }, 
                            "to": "double", "onError": 0, "onNull": 0 
                        }
                    },
                    "parsed_harga_beli": {
                        "$convert": { 
                            "input": { 
                                "$ifNull": [
                                    "$harga_beli", 
                                    "$price", 
                                    "$product_info.price",
                                    "$product_info.harga_beli"
                                ] 
                            }, 
                            "to": "double", "onError": 0, "onNull": 0 
                        }
                    },
                    "parsed_profit": {
                        "$convert": { "input": "$profit", "to": "double", "onError": 0, "onNull": 0 }
                    }
                }
            },
            # Buang document yang tanggalnya tidak bisa diparsing
            {
                "$match": { "parsed_date": { "$ne": None } }
            },
            # 3. Group berdasarkan bulan dan tahun dari tanggal transaksi
            {
                "$group": {
                    "_id": {
                        "month": {"$month": "$parsed_date"},
                        "year": {"$year": "$parsed_date"}
                    },
                    "total_profit": {
                        "$sum": {
                            "$cond": [
                                {"$gt": ["$parsed_profit", 0]},
                                "$parsed_profit",
                                {
                                    "$multiply": [
                                        {"$subtract": ["$parsed_harga_jual", "$parsed_harga_beli"]},
                                        "$parsed_qty"
                                    ]
                                }
                            ]
                        }
                    }
                }
            },
            # 3. Urutkan hasilnya dari bulan paling lama ke bulan terbaru
            {
                "$sort": {
                    "_id.year": 1,
                    "_id.month": 1
                }
            },
            # 4. Format hasil
            {
                "$project": {
                    "_id": 0,
                    "month": "$_id.month",
                    "year": "$_id.year",
                    "total_profit": 1
                }
            }
        ]

        # Eksekusi pipeline di MongoDB
        cursor = mongo_transactions.aggregate(pipeline)
        result = list(cursor)

        print(f"🚀 [LOG] /monthly-profit Aggregation Pipeline Result SEBELUM Return: {result}")

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        print(f"Error fetching monthly profit: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal mengambil performa profit bulanan: {str(e)}")
