# 🚀 PANDUAN DEPLOY KE RAILWAY — GEUNID JASEB BOT

## Penjelasan Singkat

Railway adalah platform cloud yang menjalankan bot kita 24/7 secara gratis (dengan limit $5/bulan credit). Bot akan berjalan otomatis terus tanpa perlu laptop atau PC menyala.

---

## Langkah 1: Siapkan GitHub Repository

Bot ini sudah terhubung ke GitHub. Pastikan kode terbaru sudah di-push:

```bash
git add .
git commit -m "feat: siap deploy Railway"
git push origin main
```

---

## Langkah 2: Daftar & Login Railway

1. Buka [https://railway.app](https://railway.app)
2. Klik **"Login"** → pilih **"Login with GitHub"**
3. Izinkan Railway mengakses akun GitHub Anda

---

## Langkah 3: Buat Project Baru

1. Di Railway Dashboard, klik **"New Project"**
2. Pilih **"Deploy from GitHub repo"**
3. Cari dan pilih repository **"Bot Jaseb"** (atau nama repo Anda)
4. Klik **"Deploy Now"**

Railway akan otomatis mendeteksi Dockerfile kita dan mulai build.

---

## Langkah 4: Setting Environment Variables (PALING PENTING)

Setelah project dibuat, klik tab **"Variables"** dan tambahkan semua variabel berikut:

| Variable | Value | Keterangan |
|---|---|---|
| `API_ID` | `33241986` | API ID Telegram |
| `API_HASH` | `3ac3dfb73b9b34f471a22b948cb0e6c9` | API Hash Telegram |
| `BOT_TOKEN` | `8901501719:AAG6kyPNUlM1FrgHNenEITth5GwkK44ZGF8` | Token Bot dari @BotFather |
| `ADMIN_ID` | `8844645901` | Telegram User ID Admin |
| `KLIKQRIS_API_KEY` | `MSkw9B8L40L9ywZH8i1nyvnEuZ72exKZsZOHVfVC` | API Key KlikQRIS |
| `KLIKQRIS_MERCHANT_ID` | `178075934651` | Merchant ID KlikQRIS |
| `CHANNEL_USERNAME` | `@geunidk` | Channel wajib join |
| `ADMIN_USERNAME` | `@Geun_ID` | Username admin |
| `DB_PATH` | `data/jaseb.db` | Path database SQLite |

> **PENTING:** Setelah menambahkan semua variable, klik **"Deploy"** agar perubahan diterapkan.

---

## Langkah 5: Tambahkan Volume Persisten (Untuk Session & Database)

Ini **sangat penting** agar session userbot dan database tidak hilang saat bot di-restart!

1. Di project Railway, klik **"New"** → **"Volume"**
2. Isi nama: `jaseb-data`
3. Mount path: `/app/data`
4. Klik **"Create Volume"**

Dengan ini, folder `data/` (yang berisi `jaseb.db` dan session userbot) akan tetap ada meskipun bot di-restart atau update.

---

## Langkah 6: Verifikasi Bot Berjalan

1. Klik tab **"Deployments"** di Railway
2. Lihat log build — tunggu sampai muncul pesan:
   ```
   Bot sedang berjalan...
   Scheduler Autopilot Aktif...
   ```
3. Buka Telegram, kirim `/start` ke bot Anda
4. Jika bot merespons → **DEPLOY SUKSES!** 🎉

---

## Langkah 7: Hubungkan Userbot Admin (Untuk Jaseb Regular/Forward)

Setelah bot berjalan di Railway, admin perlu menghubungkan akun userbot:

1. Chat dengan bot Anda di Telegram
2. Kirim perintah: `/install`
3. Ikuti petunjuk: masukkan nomor HP → OTP → selesai

Session userbot akan tersimpan di volume Railway dan tetap terhubung.

---

## Troubleshooting

### Bot tidak merespons
- Cek log di Railway: tab **"Deployments"** → klik deployment terbaru → lihat **"Logs"**
- Pastikan `BOT_TOKEN` sudah benar

### Database hilang setelah restart
- Pastikan Volume sudah terhubung ke `/app/data`
- Jika belum, tambahkan volume sesuai Langkah 5

### Userbot terputus
- Chat dengan bot, kirim `/install` lagi untuk reconnect
- Atau hubungi admin

---

## Biaya Railway

Railway memberikan **$5 credit gratis per bulan**. Bot ringan seperti ini biasanya hanya menggunakan **$0.50 - $2/bulan**, jadi masih **GRATIS** dengan credit yang ada.

Jika ingin meningkatkan ke plan berbayar untuk lebih banyak resource:
- **Hobby Plan**: $5/bulan (sangat direkomendasikan untuk produksi)

---

*Panduan ini ditulis untuk GEUNID JASEB BOT versi terbaru.*
*Jika ada masalah, hubungi admin di @Geun_ID*
