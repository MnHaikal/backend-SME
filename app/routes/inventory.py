from fastapi import APIRouter, Form, File, UploadFile, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel
from app.core.security import get_current_user_id, get_optional_current_user_id
import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://muhammadazmi8978_db_user:azmi12345678@amiii.uoskbzh.mongodb.net/?appName=amiii")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["muhammadazmi8978_db_user"]
mongo_transactions = mongo_db["inventory_logs"]

# Impor instance Supabase yang sudah ada, misalnya dari auth
from app.routes.auth import supabase

router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["Inventory"]
)

@router.post("/scan")
async def scan_inventory(
    sku: str = Form(...),
    scan_type: str = Form(...),
    qty: int = Form(...),
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    price: Optional[int] = Form(None),
    size: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    product_image: UploadFile = File(None),
    selling_price: Optional[int] = Form(None),
    user_id: Optional[str] = Form(None),
    token_user_id: Optional[str] = Depends(get_optional_current_user_id)
):
    current_user_id = token_user_id or user_id
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated: user_id missing")
        
    print("\n" + "="*50)
    print("🚀 [LOG] Endpoint /api/v1/inventory/scan dipanggil!")
    
    # 0. VALIDASI QTY (Wajib Positif)
    try:
        qty = int(qty)
    except ValueError:
        raise HTTPException(status_code=400, detail="Quantity harus berupa angka")
        
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity harus lebih dari 0")
        
    try:
        scan_type_clean = scan_type.strip().lower()
        sku_clean = sku.strip()
        
        print(f"📦 Data Diterima:")
        print(f"   - SKU      : {sku_clean}")
        print(f"   - Tipe Scan: {scan_type_clean}")
        print(f"   - QTY      : {qty}")
        
        if scan_type_clean not in ['in', 'out']:
            return JSONResponse(
                status_code=400, 
                content={"status": "error", "message": "scan_type harus 'in' atau 'out'"}
            )

        # Proses Upload Gambar KHUSUS untuk Scan IN
        image_url = None
        if scan_type_clean == 'in' and product_image and product_image.filename:
            print(f"📸 [FOTO] Terdeteksi foto produk untuk Scan IN: {product_image.filename}")
            try:
                file_extension = product_image.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_extension}"
                file_bytes = await product_image.read()
                
                # WAJIB gunakan file_options
                file_options = {"content-type": product_image.content_type}
                supabase.storage.from_("inventory_images").upload(
                    file_name,
                    file_bytes,
                    file_options=file_options
                )
                image_url = supabase.storage.from_("inventory_images").get_public_url(file_name)
                print(f"✅ [SUCCESS] Foto berhasil di-upload: {image_url}")
            except Exception as e:
                print(f"❌ [ERROR UPLOAD] Gagal upload foto: {e}")
            
        print(f"🔍 Mencari SKU '{sku_clean}' di tabel inventory Supabase...")
        response = supabase.table("inventory").select("*").eq("sku", sku_clean).eq("user_id", current_user_id).execute()
        
        if response.data:
            print("✅ [INFO] SKU DITEMUKAN di database (Restock / Scan Out)!")
            barang = response.data[0]
            stok_lama = barang.get("qty", 0)
            
            waktu_transaksi = datetime.now(timezone.utc).isoformat()
            update_data = {
                "last_updated": waktu_transaksi
            }
            
            if scan_type_clean == 'in':
                # Logika SCAN IN (Restock)
                qty_baru = stok_lama + qty
                print(f"📈 [ACTION] Update STOK MASUK (Restock): {stok_lama} -> {qty_baru}")
                update_data["qty"] = qty_baru
                
                # Jika ada gambar baru saat restock, update juga image_url-nya
                if image_url:
                    update_data["image_url"] = image_url
                    
                # Insert log ke MongoDB
                mongo_log = {
                    "user_id": current_user_id,
                    "sku": sku_clean,
                    "name": barang.get("name", "Unknown"),
                    "category": barang.get("category", "Uncategorized"),
                    "qty": qty,
                    "type": "IN",
                    "scan_type": "in",
                    "timestamp": waktu_transaksi
                }
                mongo_transactions.insert_one(mongo_log)
                    
                if current_user_id:
                    create_activity_log(current_user_id, "SCAN_IN", f"Scanned in product: {sku_clean}")
                    
                message = "Berhasil update stok masuk"
            else: 
                # Logika SCAN OUT & ANTI-STOK MINUS (Failsafe)
                if stok_lama < qty:
                    print(f"❌ [ERROR] STOK TIDAK MENCUKUPI (Stok: {stok_lama}, Diminta: {qty})")
                    return JSONResponse(
                        status_code=400, 
                        content={"status": "error", "message": "Gagal! Stok tidak mencukupi"}
                    )
                qty_baru = stok_lama - qty
                print(f"📉 [ACTION] Update STOK KELUAR: {stok_lama} -> {qty_baru}")
                update_data["qty"] = qty_baru
                
                # --- LOGIKA PROFIT SCAN OUT ---
                # 1. Ambil nilai price (harga modal) dari database
                try:
                    harga_beli = int(barang.get("price") or 0)
                except (ValueError, TypeError):
                    harga_beli = 0
                    
                # 2. Ambil selling_price dari frontend
                try:
                    harga_jual = int(selling_price) if selling_price is not None else harga_beli
                except (ValueError, TypeError):
                    harga_jual = harga_beli
                    
                # 3. Kalkulasi Profit
                profit_transaksi = (harga_jual - harga_beli) * qty
                
                # 4. Ambil total_profit lama dari database
                try:
                    total_profit_lama = int(barang.get("total_profit") or 0)
                except (ValueError, TypeError):
                    total_profit_lama = 0
                    
                # 5. Update profit & sold_qty
                update_data["total_profit"] = total_profit_lama + profit_transaksi
                
                try:
                    sold_lama = int(barang.get("sold_qty") or 0)
                except (ValueError, TypeError):
                    sold_lama = 0
                    
                update_data["sold_qty"] = sold_lama + qty
                
                # 6. Catat ke tabel riwayat (transactions)
                try:
                    waktu_transaksi = datetime.now(timezone.utc).isoformat()
                    transaksi_data = {
                        "sku": sku_clean,
                        "scan_type": "out",
                        "qty": qty,
                        "selling_price": harga_jual,
                        "profit": profit_transaksi,
                        "created_at": waktu_transaksi,
                        "user_id": current_user_id
                    }
                    supabase.table("transactions").insert(transaksi_data).execute()
                    
                    # Insert log ke MongoDB
                    mongo_log = {
                        "user_id": current_user_id,
                        "sku": sku_clean,
                        "name": barang.get("name", "Unknown"),
                        "category": barang.get("category", "Uncategorized"),
                        "qty": qty,
                        "type": "OUT",
                        "scan_type": "out",
                        "harga_jual": harga_jual,
                        "total_harga": profit_transaksi,
                        "timestamp": waktu_transaksi
                    }
                    mongo_transactions.insert_one(mongo_log)
                    
                    print(f"📝 [LOG] Riwayat transaksi berhasil dicatat.")
                except Exception as e:
                    print(f"⚠️ [WARNING] Gagal mencatat riwayat transaksi: {e}")
                
                if current_user_id:
                    create_activity_log(current_user_id, "SCAN_OUT", f"Scanned out product: {sku_clean}")
                    
                message = "Berhasil update stok keluar"
                
            # Eksekusi Update ke Database
            supabase.table("inventory").update(update_data).eq("sku", sku_clean).eq("user_id", current_user_id).execute()
            print("✅ [SUCCESS] Stok dan last_updated berhasil di-update ke database!")
            
            barang.update(update_data) # Update response data
            
            print("="*50 + "\n")
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": message, "data": barang}
            )
            
        else:
            print("⚠️ [INFO] SKU TIDAK DITEMUKAN di database!")
            if scan_type_clean == 'out':
                # Logika SCAN OUT jika barang tidak ada
                print("❌ [ERROR] Tidak bisa Scan Out karena barang tidak ada.")
                return JSONResponse(
                    status_code=404, 
                    content={"status": "error", "message": "Barang tidak ditemukan"}
                )
                
            # Logika SCAN IN (New Entry)
            print("✨ [ACTION] Memproses INSERT barang baru (New Entry)...")
            waktu_transaksi = datetime.now(timezone.utc).isoformat()
            data_insert = {
                "sku": sku_clean,
                "name": name.strip() if name else f"Produk {sku_clean}",
                "category": category.strip() if category else "Uncategorized",
                "price": price if price else 0,
                "size": size.strip() if size else "-",
                "color": color.strip() if color else "-",
                "qty": qty,
                "status": "NORMAL",
                "image_url": image_url,
                "last_updated": waktu_transaksi,
                "user_id": current_user_id
            }
            
            supabase.table("inventory").insert(data_insert).execute()
            
            # Insert log ke MongoDB
            mongo_log = {
                "user_id": current_user_id,
                "sku": sku_clean,
                "name": data_insert["name"],
                "category": data_insert["category"],
                "qty": qty,
                "type": "IN",
                "scan_type": "in",
                "timestamp": waktu_transaksi
            }
            mongo_transactions.insert_one(mongo_log)
            
            if current_user_id:
                create_activity_log(current_user_id, "SCAN_IN", f"Scanned in new product: {sku_clean}")
            print(f"✅ [SUCCESS] Barang baru (New Entry) berhasil ditambahkan ke database!")
            
            print("="*50 + "\n")
            return JSONResponse(
                status_code=201,
                content={"status": "success", "message": "Barang baru berhasil ditambahkan", "data": data_insert}
            )
            
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat scan_inventory: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )


@router.get("/all")
def get_all_inventory(
    search: Optional[str] = None, 
    user_id: Optional[str] = Query(None),
    token_user_id: Optional[str] = Depends(get_optional_current_user_id)
):
    current_user_id = token_user_id or user_id
    if not current_user_id:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Not authenticated: user_id missing"})

    print("\n" + "="*50)
    print(f"🚀 [LOG] Flutter mengakses halaman Inventory (GET /all) (search={search})")
    try:
        if search:
            print(f"🔍 Mencari data inventory dengan kata kunci: '{search}'...")
            response = supabase.table("inventory").select("*").eq("user_id", current_user_id).or_(f"name.ilike.%{search}%,category.ilike.%{search}%").order("last_updated", desc=True).execute()
        else:
            print("🔍 Mengambil seluruh data inventory MURNI dari Supabase...")
            # Mengambil semua data asli dari tabel, diurutkan berdasarkan last_updated (paling baru di atas)
            response = supabase.table("inventory").select("*").eq("user_id", current_user_id).order("last_updated", desc=True).execute()
        
        data_count = len(response.data) if response.data else 0
        print(f"✅ [SUCCESS] Berhasil mengambil {data_count} data murni dari database!")
        print("="*50 + "\n")
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "data": response.data}
        )
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat get_all_inventory: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )

# Skema JSON untuk Update Produk
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[int] = None
    size: Optional[str] = None
    color: Optional[str] = None
    status: Optional[str] = None
    qty: Optional[int] = None
    image_url: Optional[str] = None
    image: Optional[str] = None
    user_id: Optional[str] = None

@router.delete("/{item_id}")
def delete_inventory(item_id: int, current_user_id: str = Depends(get_current_user_id)):
    print("\n" + "="*50)
    print(f"🚀 [LOG] Endpoint DELETE /api/v1/inventory/{item_id} dipanggil!")
    try:
        # Cek apakah data ada
        cek_data = supabase.table("inventory").select("id").eq("id", item_id).eq("user_id", current_user_id).execute()
        if not cek_data.data:
            print(f"❌ [ERROR] Gagal DELETE. ID '{item_id}' tidak ditemukan.")
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": f"Data dengan ID {item_id} tidak ditemukan"}
            )
            
        # Eksekusi Delete
        supabase.table("inventory").delete().eq("id", item_id).eq("user_id", current_user_id).execute()
        print(f"✅ [SUCCESS] Berhasil menghapus ID: {item_id}")
        print("="*50 + "\n")
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": f"Data produk berhasil dihapus"}
        )
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat DELETE inventory: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )

# Import logger di bagian atas file jika belum ada
from app.utils.logger import create_activity_log

@router.put("/{item_id}")
async def update_inventory(
    item_id: int,
    name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    price: Optional[int] = Form(None),
    size: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    qty: Optional[int] = Form(None),
    product_image: UploadFile = File(None),
    user_id: Optional[str] = Form(None),
    token_user_id: Optional[str] = Depends(get_optional_current_user_id)
):
    current_user_id = token_user_id or user_id
    if not current_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated: user_id missing")
        
    print("\n" + "="*50)
    print(f"🚀 [LOG] Endpoint PUT /api/v1/inventory/{item_id} dipanggil!")
    try:
        # Cek apakah data ada
        cek_data = supabase.table("inventory").select("*").eq("id", item_id).eq("user_id", current_user_id).execute()
        if not cek_data.data:
            print(f"❌ [ERROR] Gagal UPDATE. ID '{item_id}' tidak ditemukan.")
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": f"Data dengan ID {item_id} tidak ditemukan"}
            )
            
        update_data = {}
        if name is not None: update_data["name"] = name
        if category is not None: update_data["category"] = category
        if price is not None: update_data["price"] = price
        if size is not None: update_data["size"] = size
        if color is not None: update_data["color"] = color
        if status is not None: update_data["status"] = status
        if qty is not None: update_data["qty"] = qty
        
        # Proses upload gambar jika ada
        if product_image and product_image.filename:
            print(f"📸 [FOTO] Terdeteksi foto produk untuk Update: {product_image.filename}")
            try:
                file_extension = product_image.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_extension}"
                file_bytes = await product_image.read()
                
                file_options = {"content-type": product_image.content_type}
                supabase.storage.from_("inventory_images").upload(
                    file_name,
                    file_bytes,
                    file_options=file_options
                )
                image_url = supabase.storage.from_("inventory_images").get_public_url(file_name)
                print(f"✅ [SUCCESS] Foto berhasil di-upload: {image_url}")
                update_data["image_url"] = image_url
            except Exception as e:
                print(f"❌ [ERROR UPLOAD] Gagal upload foto: {e}")
        
        if not update_data:
            print(f"⚠️ [WARNING] Tidak ada data yang diubah untuk ID '{item_id}'.")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Tidak ada data yang dikirim untuk diupdate"}
            )
            
        # Otomatis update waktu
        update_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        # Eksekusi Update
        response = supabase.table("inventory").update(update_data).eq("id", item_id).eq("user_id", current_user_id).execute()
        print(f"✅ [SUCCESS] Berhasil memperbarui data ID: {item_id}")
        
        # LOG ACTIVITY JIKA BERHASIL
        if current_user_id:
            try:
                print(f"Merekam log edit produk untuk user {current_user_id}...")
                create_activity_log(current_user_id, "EDIT_PRODUCT", f"Updated product: {name or 'Produk'}")
            except Exception as log_e:
                print(f"⚠️ [WARNING] Gagal merekam log aktivitas: {log_e}")
                
        print(f"📦 Data yang diubah: {update_data}")
        print("="*50 + "\n")
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": f"Data produk berhasil diperbarui", "data": response.data[0]}
        )
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat UPDATE inventory: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )