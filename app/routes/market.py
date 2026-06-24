from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/market", tags=["3. AI Market Intelligence"])

@router.get("/tracked-products")
async def get_tracked_market():
    return [
        {
            "name": "Wireless Pro Headphones",
            "status": "Competitive",
            "shop_price": "Rp 1.250k",
            "modal_price": "Rp 950k",
            "shopee_price": "Rp 1.280k",
            "tokopedia_price": "Rp 1.265k",
            "trend": "Match Market"
        },
        {
            "name": "Smart Fit Gen 5",
            "status": "Price Gap Detected",
            "shop_price": "Rp 2.100k",
            "modal_price": "Rp 1.600k",
            "shopee_price": "Rp 1.850k",
            "tokopedia_price": "Rp 1.890k",
            "trend": "Discount 12%"
        }
    ]

@router.post("/apply-bulk-adjustments")
async def apply_ai_pricing():
    return {
        "status": "Success",
        "algorithm_used": "Dynamic Pricing Optimizer v2.4 (LSTM Feedback Loop)",
        "adjusted_items_count": 12,
        "message": "Successfully adjusted 12 product prices to match market trends."
    }