from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.routes.auth import supabase
from app.core.security import get_current_user_id
from datetime import datetime, timezone, timedelta

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"]
)

@router.get("")
def get_notifications(current_user_id: str = Depends(get_current_user_id)):
    print("\n" + "="*50)
    print("🚀 [LOG] Endpoint GET /api/v1/notifications dipanggil!")
    try:
        notifications = []
        
        # 1. & 2. Cek transaksi hari ini dengan zona waktu Asia/Jakarta (WIB)
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        try:
            # Ambil transaksi hari ini
            resp_trans = supabase.table("transactions").select("*").eq("user_id", current_user_id).gte("created_at", today_start).execute()
            data_trans = resp_trans.data or []
            
            # Hitung profit harian dan cari best seller harian
            profit_harian = 0
            qty_per_sku = {}
            
            for t in data_trans:
                profit_harian += t.get("profit") or 0
                s = t.get("sku")
                # Kolom qty bisa qty_out (lama) atau qty (baru)
                q = t.get("qty") or t.get("qty_out") or 0
                if s:
                    qty_per_sku[s] = qty_per_sku.get(s, 0) + q
                    
            if profit_harian > 1000000:
                notifications.append({
                    "title": "Info Cuan",
                    "message": "Cuan banyak hari ini",
                    "type": "profit"
                })
                
            # Cek Best Seller Harian > 120 pcs
            for sku, total_q in qty_per_sku.items():
                if total_q > 120:
                    # Ambil kategori produk dari inventory
                    resp_inv = supabase.table("inventory").select("category").eq("user_id", current_user_id).eq("sku", sku).execute()
                    cat = "Produk"
                    if resp_inv.data:
                        cat = resp_inv.data[0].get("category") or "Produk"
                    
                    notifications.append({
                        "title": "Produk Terlaris Harian",
                        "message": f"[{cat}] penjual terlaris hari ini",
                        "type": "bestseller"
                    })
                    break # Cukup 1 notif best seller per request
        except Exception as e:
            print(f"⚠️ [WARNING] Gagal cek transaksi: {e}")
            
        # 3. & 4. Cek Low Stock dan Dead Stock
        try:
            resp_inv_all = supabase.table("inventory").select("name, qty, last_updated").eq("user_id", current_user_id).execute()
            data_inv = resp_inv_all.data or []
            
            for item in data_inv:
                name = item.get("name") or "Unknown"
                qty = item.get("qty") or 0
                last_updated_str = item.get("last_updated")
                
                # Low Stock
                if qty < 16:
                    notifications.append({
                        "title": "Stok Menipis",
                        "message": f"Perlu Restoke kembali: [{name}]",
                        "type": "low_stock"
                    })
                    
                # Dead Stock
                if last_updated_str:
                    try:
                        last_updated_date = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
                        # Konversi last_updated_date ke WIB untuk perbandingan aman
                        if last_updated_date.tzinfo is None:
                            last_updated_date = last_updated_date.replace(tzinfo=timezone.utc)
                        last_updated_date_wib = last_updated_date.astimezone(wib)
                        
                        days_diff = (now - last_updated_date_wib).days
                        if days_diff > 90:
                            notifications.append({
                                "title": "Dead Stock Terdeteksi",
                                "message": f"Dead Stock: [{name}] tidak laku > 3 bulan",
                                "type": "dead_stock"
                            })
                    except Exception as e:
                        pass
        except Exception as e:
            print(f"⚠️ [WARNING] Gagal cek inventory: {e}")

        print(f"✅ [SUCCESS] Berhasil generate {len(notifications)} notifikasi")
        print("="*50 + "\n")
        
        return JSONResponse(
            status_code=200,
            content={"notifications": notifications}
        )
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat get_notifications: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )
