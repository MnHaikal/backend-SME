from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import os
from supabase import create_client, Client

router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["Products"]
)

# Gunakan instance supabase yang sudah diinisialisasi di auth.py
from app.routes.auth import supabase

class ProductSchema(BaseModel):
    id: Optional[int] = None
    sku: str
    name: str
    category: str
    qty: int
    status: str
    image_url: Optional[str] = None



@router.get("", response_model=List[ProductSchema])
def get_products():
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        response = supabase.table("inventory").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.put("/{id}", response_model=ProductSchema)
def update_product(id: int, product: ProductSchema):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        product_dict = product.model_dump(exclude_none=True)
        response = supabase.table("inventory").update(product_dict).eq("id", id).execute()
        if response.data:
            return response.data[0]
        raise HTTPException(status_code=404, detail="Product not found or update failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
def delete_product(id: int):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        response = supabase.table("inventory").delete().eq("id", id).execute()
        if response.data:
            return {"message": "Product deleted successfully"}
        raise HTTPException(status_code=404, detail="Product not found or delete failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
