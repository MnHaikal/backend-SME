from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.routes.auth import supabase
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from app.core.security import get_current_user_id

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"]
)

@router.get("/monthly-recap")
async def get_monthly_recap(current_user_id: str = Depends(get_current_user_id)):
    print("\n" + "="*50)
    print("🚀 [LOG] Endpoint GET /api/v1/analytics/monthly-recap dipanggil!")
    
    try:
        # Mengambil data inventory khusus user ini
        inventory_res = supabase.table("inventory").select("*").eq("user_id", current_user_id).execute()
        inventory_data = inventory_res.data or []
        
        # GUARD CONDITION: Hitung total item terlebih dahulu
        total_items = sum(item.get("qty", 0) for item in inventory_data) if inventory_data else 0
        
        if total_items == 0:
            print("✅ [SUCCESS] New User / Empty Inventory -> Bypass logic for monthly recap")
            print("="*50 + "\n")
            return JSONResponse(
                status_code=200,
                content={
                    "total_items": 0,
                    "low_stock": 0,
                    "potential_profit": 0,
                    "dead_stock": 0,
                    "dead_stock_list": [],
                    "low_stock_list": [],
                    "top_selling_item": {
                        "name": "Belum ada data",
                        "total_sold": 0
                    }
                }
            )

        # Inisialisasi metrics
        low_stock = 0
        potential_profit = 0
        dead_stock = 0
        dead_stock_list = []
        low_stock_list = []
        
        # 1. Hitung low_stock, potential_profit
        for item in inventory_data:
            qty = item.get("qty", 0)
            
            if qty < 10:
                low_stock += 1
                low_stock_list.append({"sku": item.get("sku"), "name": item.get("name", "Unknown"), "qty": qty})
                
            harga_jual = item.get("selling_price", 0) or 0
            harga_beli = item.get("price", 0) or 0
            
            potential_profit += (harga_jual - harga_beli) * qty

        # 2. Ambil data transactions untuk dead_stock (30 hari terakhir) dan top_selling (bulan berjalan)
        now = datetime.now(timezone.utc)
        
        # Batas 30 hari terakhir untuk dead_stock
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        
        # Awal bulan berjalan untuk top_selling
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        # Query 1: Transactions in the last 30 days (for dead_stock) khusus user ini
        tx_30_days_res = supabase.table("transactions").select("sku").eq("user_id", current_user_id).eq("scan_type", "out").gte("created_at", thirty_days_ago).execute()
        tx_30_days_data = tx_30_days_res.data or []
        
        active_skus_30_days = set([tx["sku"] for tx in tx_30_days_data])
        
        # Hitung dead stock (ada stok tapi tidak laku dalam 30 hari terakhir)
        for item in inventory_data:
            sku = item.get("sku")
            qty = item.get("qty", 0)
            if qty > 0 and sku not in active_skus_30_days:
                dead_stock += 1
                dead_stock_list.append({"sku": sku, "name": item.get("name", "Unknown"), "qty": qty})
                
        # Query 2: Transactions this month (for top_selling_item) khusus user ini
        tx_this_month_res = supabase.table("transactions").select("sku, qty").eq("user_id", current_user_id).eq("scan_type", "out").gte("created_at", first_day_of_month).execute()
        tx_this_month_data = tx_this_month_res.data or []
        
        sku_sales = defaultdict(int)
        for tx in tx_this_month_data:
            sku = tx.get("sku")
            qty_out = tx.get("qty", 0)
            if sku:
                sku_sales[sku] += qty_out
                
        top_selling_item = {
            "name": "Belum ada data",
            "total_sold": 0
        }
        
        if sku_sales:
            top_sku = max(sku_sales, key=sku_sales.get)
            top_qty = sku_sales[top_sku]
            
            # Cari nama produk dari inventory
            top_name = "Unknown"
            for item in inventory_data:
                if item.get("sku") == top_sku:
                    top_name = item.get("name", "Unknown")
                    break
                    
            if top_qty > 0:
                top_selling_item = {
                    "name": top_name,
                    "total_sold": top_qty
                }
                
        print(f"✅ [SUCCESS] Perhitungan selesai -> Total Items: {total_items}, Low Stock: {low_stock}, Dead Stock: {dead_stock}, Profit: {potential_profit}")
        print("="*50 + "\n")
        
        return {
            "total_items": total_items,
            "low_stock": low_stock,
            "dead_stock": dead_stock,
            "potential_profit": potential_profit,
            "top_selling_item": top_selling_item,
            "low_stock_list": low_stock_list,
            "dead_stock_list": dead_stock_list
        }
        
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat get_monthly_recap: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )
