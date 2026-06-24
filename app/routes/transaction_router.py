from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime

router = APIRouter(
    prefix="/api/v1/transaction",
    tags=["Transaction"]
)

class TransactionRequest(BaseModel):
    sku: str
    description: str
    category: str
    size: str
    color: str
    type: str  # 'IN' or 'OUT'
    quantity: int

class TransactionLog(BaseModel):
    id: int
    sku: str
    description: str
    category: str
    size: str
    color: str
    type: str
    quantity: int
    timestamp: datetime

class Product(BaseModel):
    id: int
    sku: str
    description: str
    category: str
    size: str
    color: str
    stock: int

# Database In-Memory
inventory_db: List[Product] = []
transaction_db: List[TransactionLog] = []

@router.post("/scan")
def process_transaction(req: TransactionRequest):
    if req.type not in ["IN", "OUT"]:
        raise HTTPException(status_code=400, detail="Type harus 'IN' atau 'OUT'")
    
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity harus lebih besar dari 0")

    # Pencarian produk berdasarkan 4 atribut: sku, category, size, dan color
    product_idx = None
    for idx, p in enumerate(inventory_db):
        if p.sku == req.sku and p.category == req.category and p.size == req.size and p.color == req.color:
            product_idx = idx
            break

    if req.type == "IN":
        if product_idx is not None:
            # Jika ketemu, tambahkan stock
            inventory_db[product_idx].stock += req.quantity
            current_stock = inventory_db[product_idx].stock
        else:
            # Jika tidak ketemu, buat entri produk baru
            new_id = max([p.id for p in inventory_db], default=0) + 1
            new_product = Product(
                id=new_id,
                sku=req.sku,
                description=req.description,
                category=req.category,
                size=req.size,
                color=req.color,
                stock=req.quantity
            )
            inventory_db.append(new_product)
            current_stock = new_product.stock
            
    elif req.type == "OUT":
        # Jika type == 'OUT'
        if product_idx is None:
            raise HTTPException(status_code=400, detail="Produk tidak ditemukan")
            
        if inventory_db[product_idx].stock < req.quantity:
            raise HTTPException(status_code=400, detail="Stok tidak cukup")
            
        # Jika aman, kurangi stok
        inventory_db[product_idx].stock -= req.quantity
        current_stock = inventory_db[product_idx].stock

    # Simpan riwayat transaksi ke transaction_db
    new_log_id = max([t.id for t in transaction_db], default=0) + 1
    new_log = TransactionLog(
        id=new_log_id,
        sku=req.sku,
        description=req.description,
        category=req.category,
        size=req.size,
        color=req.color,
        type=req.type,
        quantity=req.quantity,
        timestamp=datetime.now()
    )
    transaction_db.append(new_log)

    # Kembalikan response JSON message sukses dan sisa stok
    return {
        "message": f"Transaksi {req.type} berhasil",
        "current_stock": current_stock,
        "log": new_log
    }
