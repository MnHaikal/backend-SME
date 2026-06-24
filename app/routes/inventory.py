from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/inventory", tags=["2. Inventory Management"])

@router.get("/products")
async def get_products():
    return [
        {
            "name": "Organic Soap",
            "category": "PERSONAL CARE",
            "qty": 120,
            "status": "NORMAL",
            "image": "https://images.unsplash.com/photo-1600857062241-98e5dba7f214?q=80&w=500"
        },
        {
            "name": "Hand Sanitizer",
            "category": "HEALTHCARE",
            "qty": 5,
            "status": "CRITICAL",
            "image": "https://images.unsplash.com/photo-1584622781564-1d9876a13d00?q=80&w=500"
        },
        {
            "name": "Old Model Case",
            "category": "ACCESSORIES",
            "qty": 50,
            "status": "DEAD STOCK",
            "image": "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?q=80&w=500"
        }
    ]