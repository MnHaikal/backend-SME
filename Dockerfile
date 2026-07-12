# Menggunakan base image Python yang ringan
FROM python:3.10-slim

# Install dependencies sistem yang diperlukan untuk MediaPipe/OpenCV dan database
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory di /app agar struktur path tetap konsisten
WORKDIR /app

# Copy requirements dan install semua library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh isi proyek ke dalam container
COPY . .

# Set PYTHONPATH agar Python bisa menemukan modul di folder /app
ENV PYTHONPATH=/app

# Perintah untuk menjalankan Uvicorn
# Railway akan mendeteksi port 8080 secara otomatis
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]