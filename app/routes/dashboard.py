from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.routes.auth import supabase
from datetime import datetime, timezone

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"]
)

@router.get("/summary")
def get_dashboard_summary():
    print("\n" + "="*50)
    print("🚀 [LOG] Endpoint GET /api/v1/dashboard/summary dipanggil!")
    
    try:
        # Mengambil semua data dari tabel inventory
        response = supabase.table("inventory").select("*").execute()
        
        data_inventory = response.data
        
        total_items = 0
        low_stock = 0
        potential_profit = 0
        dead_stock = 0
        dead_stock_list = []
        bestseller_name = None
        highest_sold_qty = -1
        
        if data_inventory:
            now = datetime.now(timezone.utc)
            for item in data_inventory:
                qty = item.get("qty", 0)
                total_items += qty
                
                # Menghitung produk yang sisa stoknya kurang dari 16
                if qty < 16:
                    low_stock += 1
                
                # Hitung Profit
                profit = item.get("total_profit") or 0
                potential_profit += profit
                
                # Hitung Dead Stock (90 hari)
                last_updated_str = item.get("last_updated")
                if last_updated_str:
                    try:
                        # Handle basic ISO format with Z or timezone offset
                        last_updated_date = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
                        days_diff = (now - last_updated_date).days
                        if days_diff > 90:
                            dead_stock += 1
                    except Exception as e:
                        pass
                
                # Bestseller (Tertinggi)
                sold_qty = item.get("sold_qty") or 0
                if sold_qty > highest_sold_qty and sold_qty > 0:
                    highest_sold_qty = sold_qty
                    bestseller_name = item.get("name", "Unknown")
                    
        print(f"✅ [SUCCESS] Perhitungan selesai -> Total Item: {total_items}, Low Stock: {low_stock}, Profit: {potential_profit}, Dead Stock: {dead_stock}")
        print("="*50 + "\n")
        
        return JSONResponse(
            status_code=200,
            content={
                "total_items": total_items,
                "low_stock": low_stock,
                "potential_profit": potential_profit,
                "dead_stock": dead_stock,
                "notifications": {
                    "bestseller": bestseller_name if bestseller_name else "Belum ada produk terjual",
                    "dead_stock_list": dead_stock_list
                }
            }
        )
        
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat get_dashboard_summary: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )

from datetime import timedelta
from collections import defaultdict
import calendar

@router.get("/stats")
def get_dashboard_stats():
    print("\n" + "="*50)
    print("🚀 [LOG] Endpoint GET /api/v1/dashboard/stats dipanggil!")
    
    try:
        # 1. Hitung total stok
        inv_response = supabase.table("inventory").select("qty").execute()
        total_inventory = sum(item.get("qty", 0) for item in inv_response.data) if inv_response.data else 0
        
        # 2. Hitung akumulasi potential_profit per bulan (12 bulan terakhir)
        now = datetime.now(timezone.utc)
        twelve_months_ago = now - timedelta(days=365)
        
        tx_response = supabase.table("transactions").select("profit, created_at").eq("scan_type", "out").gte("created_at", twelve_months_ago.isoformat()).execute()
        
        labels = []
        profit_data = []
        monthly_profits = defaultdict(float)
        
        if tx_response.data:
            for tx in tx_response.data:
                created_at_str = tx.get("created_at")
                profit = float(tx.get("profit") or 0)
                if created_at_str:
                    try:
                        tx_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        month_key = f"{tx_date.year}-{tx_date.month:02d}"
                        monthly_profits[month_key] += profit
                    except Exception:
                        pass
                        
        indonesian_months = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
            7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
        }
                        
        # Construct last 12 months from current month backwards
        for i in range(11, -1, -1):
            target_month = now.month - i
            target_year = now.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
                
            month_key = f"{target_year}-{target_month:02d}"
            labels.append(indonesian_months[target_month])
            profit_data.append(monthly_profits.get(month_key, 0.0))

        print(f"✅ [SUCCESS] Dashboard stats: Total Inventory: {total_inventory}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=200,
            content={
                "total_inventory": total_inventory,
                "profit_data": profit_data,
                "labels": labels
            }
        )
        
    except Exception as e:
        print(f"💥 [FATAL ERROR] Kesalahan saat get_dashboard_stats: {str(e)}")
        print("="*50 + "\n")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Terjadi kesalahan server: {str(e)}"}
        )
