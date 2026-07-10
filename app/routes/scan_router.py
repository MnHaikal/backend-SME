from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.routes.auth import supabase
from app.utils.logger import create_activity_log

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
def scan_in(data: ScanInSchema):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        # Cek apakah sku sudah ada
        check_response = supabase.table("inventory").select("*").eq("sku", data.sku).execute()
        
        if check_response.data and len(check_response.data) > 0:
            # SKU ada, tambahkan qty
            existing_product = check_response.data[0]
            new_qty = existing_product["qty"] + data.qty
            
            update_response = supabase.table("inventory").update({"qty": new_qty}).eq("sku", data.sku).execute()
            if update_response.data:
                if data.user_id:
                    create_activity_log(data.user_id, "SCAN_IN", f"Scanned in product: {data.name}")
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
                "image_url": data.image_url
            }
            insert_response = supabase.table("inventory").insert(new_product).execute()
            if insert_response.data:
                if data.user_id:
                    create_activity_log(data.user_id, "SCAN_IN", f"Scanned in product: {data.name}")
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
def scan_out(data: ScanOutSchema):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        # Cek apakah sku ada
        check_response = supabase.table("inventory").select("*").eq("sku", data.sku).execute()
        
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(status_code=404, detail="Produk dengan SKU tersebut tidak ditemukan")
            
        existing_product = check_response.data[0]
        current_qty = existing_product["qty"]
        
        if current_qty < data.qty_keluar:
            raise HTTPException(status_code=400, detail="Stok tidak mencukupi untuk jumlah keluar yang diminta")
            
        new_qty = current_qty - data.qty_keluar
        update_response = supabase.table("inventory").update({"qty": new_qty}).eq("sku", data.sku).execute()
        
        if update_response.data:
            if data.user_id:
                product_name = existing_product.get("name", data.sku)
                create_activity_log(data.user_id, "SCAN_OUT", f"Scanned out product: {product_name}")
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
