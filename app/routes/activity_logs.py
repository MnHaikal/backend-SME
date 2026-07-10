from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from app.core.db import supabase

router = APIRouter(prefix="/api/v1/logs", tags=["Activity Logs"])

@router.get("")
def get_activity_logs(user_id: Optional[str] = Query(None)):
    try:
        # Jika ada user_id, filter, jika tidak, ambil semua
        query = supabase.table("activity_logs").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
            
        response = query.order("created_at", desc=True).execute()
            
        return {
            "status": "success",
            "message": "Berhasil menarik riwayat aktivitas",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sistem gagal merespon data log: {str(e)}")
