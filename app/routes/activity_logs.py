from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.core.db import supabase
from app.core.security import get_current_user_id

router = APIRouter(prefix="/api/v1/logs", tags=["Activity Logs"])

@router.get("")
def get_activity_logs(current_user_id: str = Depends(get_current_user_id)):
    try:
        # Hanya ambil log yang spesifik milik user yang sedang login
        response = supabase.table("activity_logs").select("*").eq("user_id", current_user_id).order("created_at", desc=True).execute()
            
        return {
            "status": "success",
            "message": "Berhasil menarik riwayat aktivitas",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sistem gagal merespon data log: {str(e)}")

@router.delete("/{log_id}")
def delete_activity_log(log_id: int, current_user_id: str = Depends(get_current_user_id)):
    try:
        # Menghapus log dengan ID tertentu dan harus milik current_user_id (keamanan ekstra)
        response = supabase.table("activity_logs").delete().eq("id", log_id).eq("user_id", current_user_id).execute()
        
        if response.data:
            return {
                "status": "success",
                "message": "Log aktivitas berhasil dihapus"
            }
        else:
            raise HTTPException(status_code=404, detail="Log aktivitas tidak ditemukan atau Anda tidak berhak menghapusnya")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghapus log aktivitas: {str(e)}")
