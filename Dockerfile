# Gunakan image Python yang ringan namun stabil
FROM python:3.11-slim-bullseye

# Cegah Python membuat file .pyc dan buffering output agar log real-time di Railway
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependensi sistem yang diperlukan
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy file requirements dulu agar caching Docker lebih efisien
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file project
COPY . .

# Buat folder data untuk menyimpan database dan sesi userbot
# (Volume persistent di Railway akan di-mount di sini)
RUN mkdir -p data/sessions data/media

# Jalankan bot menggunakan python -m agar path relatif src.module berfungsi
CMD ["python", "-m", "src.main"]
