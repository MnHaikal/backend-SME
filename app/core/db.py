from supabase import create_client, Client

# --- KONFIGURASI CLOUD SUPABASE ---
SUPABASE_URL = "https://nsutebinuhpwwwuudbrg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zdXRlYmludWhwd3d3dXVkYnJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxODU3MTEsImV4cCI6MjA5NDc2MTcxMX0.xUu6sdM8olwglQND_dCMJweqjSYQegaksLtbQgH9zX4"

# Inisialisasi Klien Koneksi Supabase Terpusat
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
