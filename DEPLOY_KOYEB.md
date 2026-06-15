# 🚀 Panduan Deployment GEUNID JASEB ke Koyeb

Dokumen ini menjelaskan langkah-langkah mendeploy aplikasi backend Bot Telegram (Python + SQLite) ke server **Koyeb**.

## Prasyarat
1. Akun Koyeb aktif (gratis/premium).
2. Repository GitHub berisi kode proyek ini (sudah di-push).

---

## Langkah 1: Siapkan Persistent Volume (PENTING ⚠️)
Karena proyek ini menggunakan database **SQLite (`data/jaseb.db`)**, semua data pengguna dan transaksi akan hilang jika server Koyeb melakukan restart (karena kontainer bersifat stateless).
Untuk mencegah hal tersebut, kita harus menggunakan **Koyeb Persistent Volume (PV)**:

1. Masuk ke console Koyeb.
2. Di menu navigasi samping, buka **Volumes**.
3. Klik **Create Volume**:
   - **Name:** `jaseb-db-vol`
   - **Size:** `1GB` (cukup untuk menyimpan jutaan baris data SQLite)
   - **Region:** Pilih region yang sama dengan layanan bot Anda nanti (misalnya Frankfurt `fra` atau Washington `was`).
4. Klik **Create**.

---

## Langkah 2: Deploy Layanan Baru di Koyeb
1. Di dasbor Koyeb, klik **Create Service**.
2. Pilih **GitHub** dan hubungkan akun GitHub Anda, lalu pilih repository proyek `Bot Jaseb` ini.
3. Konfigurasi Layanan:
   - **Builder:** Pilih **Dockerfile** (Koyeb akan membaca file [Dockerfile](file:///d:/Bot%20Jaseb/Dockerfile) yang sudah ada di proyek ini secara otomatis).
   - **Instance Size:** Pilih `Micro` atau `Nano` (Bot ini sangat ringan dan dioptimasi dengan baik, sehingga paket gratis Koyeb sudah sangat memadai).
   - **Ports:** Nonaktifkan port HTTP jika Anda hanya ingin menjalankan Bot Telegram murni. Namun, jika Anda berencana mengekspos API eksternal di masa mendatang, aktifkan port `8080`.

---

## Langkah 3: Mount Volume Database
Pada bagian konfigurasi service, scroll ke bawah ke bagian **Volumes**:
1. Klik **Add Volume**.
2. Pilih Volume yang sudah Anda buat sebelumnya (`jaseb-db-vol`).
3. Set **Mount Path** ke: `/app/data` (ini akan menghubungkan volume eksternal ke dalam folder database kontainer `/app/data`).

---

## Langkah 4: Konfigurasi Environment Variables (Env)
Tambahkan variabel lingkungan (Environment Variables) berikut di bagian **Environment Variables** Koyeb:

| Key | Value | Keterangan |
| :--- | :--- | :--- |
| `API_ID` | `1234567` | API ID Telegram Anda dari my.telegram.org |
| `API_HASH` | `abcdef123456...` | API Hash Telegram Anda |
| `BOT_TOKEN` | `12345:AA...` | Token Bot dari @BotFather |
| `ADMIN_ID` | `8844645901` | ID Telegram Owner/Admin Utama |
| `CHANNEL_USERNAME` | `@geunidk` | Username channel informasi resmi Anda (wajib join) |

---

## Langkah 5: Jalankan Deployment
1. Klik **Deploy**.
2. Koyeb akan mulai melakukan build image Docker dan menjalankannya.
3. Pantau log pada menu **Logs** di Koyeb untuk memastikan bot berjalan sukses dan database SQLite berhasil terinisialisasi.

Sekarang bot Anda aktif secara terus-menerus (24/7) di server Koyeb dengan database yang aman dari kehilangan data!
