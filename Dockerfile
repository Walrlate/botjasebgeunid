# Gunakan image Python yang ringan
FROM python:3.10-slim-buster

# Set working directory
WORKDIR /app

# Install dependensi sistem yang diperlukan untuk Telethon
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy file requirements dulu agar caching lebih efisien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file project
COPY . .

# Buat folder data untuk menyimpan database dan sesi
RUN mkdir -p data

# Jalankan bot
CMD ["python", "-m", "src.main"]
