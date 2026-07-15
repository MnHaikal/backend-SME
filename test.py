
from supabase import create_client
import os

url = "https://nsutebinuhpwwwuudbrg.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zdXRlYmludWhwd3d3dXVkYnJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxODU3MTEsImV4cCI6MjA5NDc2MTcxMX0.xUu6sdM8olwglQND_dCMJweqjSYQegaksLtbQgH9zX4"
supabase = create_client(url, key)

current_user_id = "f9ea984c-9147-446e-813d-34985e0d0ab1"

from datetime import datetime, timezone, timedelta
wib = timezone(timedelta(hours=7))
now = datetime.now(wib)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
print("today_start", today_start)

resp_trans = supabase.table("transactions").select("*").eq("user_id", current_user_id).gte("created_at", today_start).execute()
data_trans = resp_trans.data or []
profit_harian = 0
for t in data_trans:
    profit_harian += t.get("profit") or 0

print(f"Profit harian is: {profit_harian}")
if profit_harian > 1000000:
    print("Info Cuan notification appended")
else:
    print("NO Info Cuan notification")

