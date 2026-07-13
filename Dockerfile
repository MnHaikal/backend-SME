# Menggunakan base image Python yang ringan
FROM python:3.10-slim

# Mencegah Python menulis file .pyc ke disk (menghemat storage)
ENV PYTHONDONTWRITEBYTECODE=1
# Memastikan output log langsung muncul di terminal Railway
ENV PYTHONUNBUFFERED=1
# Mengatur lokasi modul agar Python menemukannya dengan pasti
ENV PYTHONPATH=/app

# Install dependencies sistem yang diperlukan
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement dan install semua library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh isi proyek ke dalam container
COPY . .

# Pastikan folder app dapat diakses
RUN chmod -R 755 /app

# Jalankan Uvicorn
CMD sh -c "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"