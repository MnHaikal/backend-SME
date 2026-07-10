from datetime import datetime, timezone
from app.core.db import supabase

def create_activity_log(user_id: str, action_type: str, description: str):
    """
    Helper untuk merekam log aktivitas ke Supabase yang sudah tersinkron dengan kolom id tabel users.
    """
    try:
        # Menggunakan user_id (UUID string) murni yang berasal dari tabel users
        data = {
            "user_id": user_id, 
            "action_type": action_type, 
            "description": description
        }
        
        print(f"DEBUG: Menyimpan log untuk ID: {user_id}")
        response = supabase.table('activity_logs').insert(data).execute()
        
        print(f"✅ LOG TERSIMPAN UNTUK USER_ID: {user_id}")
    except Exception as e:
        print(f"❌ GAGAL MASUK DB: {str(e)}")
        raise Exception(str(e))
