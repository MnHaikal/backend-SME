import os
from supabase import create_client, Client

# --- KONFIGURASI CLOUD SUPABASE (via Environment Variable) ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inisialisasi Klien Koneksi Supabase Terpusat
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
