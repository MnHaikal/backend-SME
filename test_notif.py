
from supabase import create_client
import os

url = "https://nsutebinuhpwwwuudbrg.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zdXRlYmludWhwd3d3dXVkYnJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxODU3MTEsImV4cCI6MjA5NDc2MTcxMX0.xUu6sdM8olwglQND_dCMJweqjSYQegaksLtbQgH9zX4"
supabase = create_client(url, key)

try:
    resp = supabase.table("notifications").select("*").limit(1).execute()
    print("Table exists!")
except Exception as e:
    print(f"Table does not exist: {e}")

